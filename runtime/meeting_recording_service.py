#!/usr/bin/env python3
"""Meeting recording runtime service.

This module owns the product boundary between the resident agent and Skribby:
the agent orders a recording job here, and this runtime hides provider details,
state persistence, and secret handling.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import hashlib
import json
import os
from pathlib import Path
import secrets
from typing import Any
from urllib.parse import parse_qsl, quote, urlparse, urlunparse

from runtime.meeting_recording_store import MeetingRecordingStore
from runtime.meeting_transcript_capture import EmptyTranscriptError, capture_finished_bot
from runtime.openclaw_wakeup import wake_meeting_transcript
from runtime.skribby_client import SkribbyClient, SkribbyClientError


SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "key",
    "password",
    "pwd",
    "secret",
    "signature",
    "token",
    "webhook_nonce",
}
RAW_SOURCE_KEYS = {"transcript", "transcripts", "transcript_segments"}
REQUIRED_ORDER_FIELDS = ("meeting_url", "business_id", "source_id", "chat_ref", "requested_by")


class MeetingRecordingError(RuntimeError):
    """Base class for runtime failures safe to show after redaction."""


class ValidationError(MeetingRecordingError):
    pass


class ProviderCreateError(MeetingRecordingError):
    pass


class ProviderFetchError(MeetingRecordingError):
    pass


class UnknownRecordingJobError(MeetingRecordingError):
    pass


class BotMismatchError(MeetingRecordingError):
    pass


class EmptyTranscriptRuntimeError(MeetingRecordingError):
    pass


class WebhookAuthError(MeetingRecordingError):
    pass


@dataclass
class MeetingRecordingConfig:
    public_base_url: str
    workspace_root: Path = Path(".")
    bot_name: str = "Ontology Agent recorder"
    transcription_model: str = "whisper"
    default_stop_options: dict[str, Any] = field(default_factory=dict)
    openclaw_wakeup_url: str | None = None
    openclaw_hooks_token: str | None = None


class MeetingRecordingRuntime:
    def __init__(
        self,
        config: MeetingRecordingConfig,
        *,
        store: MeetingRecordingStore,
        skribby_client: Any,
        id_factory: Any | None = None,
    ) -> None:
        self.config = config
        self.store = store
        self.skribby_client = skribby_client
        self._id_factory = id_factory or generate_job_id

    def order_recording(self, request: dict[str, Any]) -> dict[str, Any]:
        normalized = _validate_order_request(request)
        service = infer_meeting_service(normalized["meeting_url"])
        if service is None:
            raise ValidationError("unsupported meeting URL")

        job_id = self._id_factory()
        webhook_nonce = secrets.token_urlsafe(24)
        webhook_url = f"{self.config.public_base_url.rstrip('/')}/webhooks/skribby"
        provider_payload = {
            "meeting_url": normalized["meeting_url"],
            "service": service,
            "bot_name": self.config.bot_name,
            "transcription_model": self.config.transcription_model,
            "webhook_url": webhook_url,
            "custom_metadata": {
                "job_id": job_id,
                "business_id": normalized["business_id"],
                "source_id": normalized["source_id"],
                "chat_ref": normalized["chat_ref"],
                "requested_by": normalized["requested_by"],
                "webhook_nonce": webhook_nonce,
            },
        }
        if self.config.default_stop_options:
            provider_payload["stop_options"] = dict(self.config.default_stop_options)

        self.store.create_requested_job(
            {
                "job_id": job_id,
                "provider": "skribby",
                "meeting_url_hash": hash_meeting_url(normalized["meeting_url"]),
                "meeting_url_display": sanitize_url(normalized["meeting_url"]),
                "service": service,
                "business_id": normalized["business_id"],
                "source_id": normalized["source_id"],
                "chat_ref": normalized["chat_ref"],
                "requested_by": normalized["requested_by"],
                "webhook_nonce_hash": hash_secret(webhook_nonce),
                "provider_payload": redact_provider_payload(provider_payload),
            }
        )

        try:
            create_result = self.skribby_client.create_bot(provider_payload)
        except SkribbyClientError as exc:
            self.store.mark_failed(
                job_id,
                error_code="provider-create-failed",
                error_message="Skribby create-bot request failed",
            )
            raise ProviderCreateError("Skribby create-bot request failed") from exc

        bot_id = _provider_bot_id(create_result)
        if not bot_id:
            self.store.mark_failed(
                job_id,
                error_code="provider-missing-bot-id",
                error_message="Skribby create-bot response did not include bot id",
            )
            raise ProviderCreateError("Skribby create-bot response did not include bot id")

        self.store.mark_bot_created(
            job_id,
            bot_id=bot_id,
            provider_payload=redact_provider_payload(create_result),
        )
        return {
            "job_id": job_id,
            "provider": "skribby",
            "bot_id": bot_id,
            "status": "bot_created",
        }

    def handle_skribby_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        job_id = _webhook_job_id(payload)
        bot_id = _webhook_bot_id(payload)
        try:
            job = self.store.get_job(job_id)
        except KeyError as exc:
            raise UnknownRecordingJobError("unknown job") from exc
        if str(job.get("bot_id") or "") != bot_id:
            raise BotMismatchError("bot mismatch for recording job")
        _verify_webhook_nonce(job, payload)

        if not _is_finished_webhook(payload):
            return {"status": "ignored"}
        if job["status"] == "packet_ready" and job.get("packet_path"):
            return {"status": "packet_ready", "packet_path": job["packet_path"]}

        if job["status"] == "bot_created":
            self.store.mark_finished_received(job_id, webhook_payload=redact_provider_payload(payload))
        elif job["status"] not in {"finished_received", "transcript_fetched"}:
            raise ValidationError(f"recording job is not ready for finished webhook: {job['status']}")

        try:
            bot_payload = self.skribby_client.fetch_bot(bot_id)
        except SkribbyClientError as exc:
            raise ProviderFetchError("Skribby fetch-bot request failed") from exc
        except Exception as exc:
            raise ProviderFetchError("Skribby fetch-bot request failed") from exc
        if self.store.get_job(job_id)["status"] != "transcript_fetched":
            self.store.mark_transcript_fetched(
                job_id,
                provider_payload=redact_provider_payload(bot_payload),
                provider_finished_at=str(bot_payload.get("finished_at") or "") or None,
            )
        try:
            capture = capture_finished_bot(
                self.store.get_job(job_id),
                bot_payload,
                self.config.workspace_root,
            )
        except EmptyTranscriptError as exc:
            self.store.mark_failed(
                job_id,
                error_code="empty-transcript",
                error_message="Skribby finished webhook did not yield transcript segments",
            )
            raise EmptyTranscriptRuntimeError("finished webhook did not yield transcript segments") from exc

        wakeup = wake_meeting_transcript(
            capture.packet_path,
            hook_url=self.config.openclaw_wakeup_url,
            token=self.config.openclaw_hooks_token,
        )
        self.store.mark_packet_ready(
            job_id,
            packet_path=str(capture.packet_path),
            transcript_hash=capture.transcript_hash,
            wakeup_pending=wakeup.pending,
        )
        return {
            "status": "packet_ready",
            "packet_path": str(capture.packet_path),
            "transcript_hash": capture.transcript_hash,
            "wakeup_pending": wakeup.pending,
        }


class RecordingApp:
    def __init__(self, runtime: MeetingRecordingRuntime):
        self.runtime = runtime

    def handle_post_recordings(
        self,
        body: bytes,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, str], bytes]:
        content_type = _header_value(headers, "content-type").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            return _json_response(415, {"error": "content-type must be application/json"})
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            return _json_response(400, {"error": "request body must be valid JSON"})
        if not isinstance(payload, dict):
            return _json_response(400, {"error": "request body must be a JSON object"})

        try:
            result = self.runtime.order_recording(payload)
        except ValidationError as exc:
            return _json_response(400, {"error": str(exc)})
        except ProviderCreateError as exc:
            return _json_response(502, {"error": str(exc)})
        except Exception:
            return _json_response(500, {"error": "internal meeting recording runtime error"})
        return _json_response(200, result)

    def handle_post_skribby(
        self,
        body: bytes,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, str], bytes]:
        content_type = _header_value(headers, "content-type").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            return _json_response(415, {"error": "content-type must be application/json"})
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            return _json_response(400, {"error": "request body must be valid JSON"})
        if not isinstance(payload, dict):
            return _json_response(400, {"error": "request body must be a JSON object"})

        try:
            result = self.runtime.handle_skribby_webhook(payload)
        except ValidationError as exc:
            return _json_response(400, {"error": str(exc)})
        except ProviderFetchError as exc:
            return _json_response(502, {"error": str(exc)})
        except UnknownRecordingJobError as exc:
            return _json_response(404, {"error": str(exc)})
        except WebhookAuthError as exc:
            return _json_response(401, {"error": str(exc)})
        except BotMismatchError as exc:
            return _json_response(409, {"error": str(exc)})
        except EmptyTranscriptRuntimeError as exc:
            return _json_response(422, {"error": str(exc)})
        except Exception:
            return _json_response(500, {"error": "internal meeting recording webhook error"})
        status = 202 if result.get("status") == "ignored" else 200
        return _json_response(status, result)

    def handle_health(self) -> tuple[int, dict[str, str], bytes]:
        return _json_response(200, {"status": "ok"})


def build_app(runtime: MeetingRecordingRuntime) -> RecordingApp:
    return RecordingApp(runtime)


def make_handler(app: RecordingApp) -> type[BaseHTTPRequestHandler]:
    class MeetingRecordingHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if urlparse(self.path).path == "/health":
                self._send(*app.handle_health())
                return
            self._send(*_json_response(404, {"error": "not found"}))

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path not in {"/recordings", "/webhooks/skribby"}:
                self._send(*_json_response(404, {"error": "not found"}))
                return
            length = int(self.headers.get("content-length", "0"))
            headers = {key.lower(): value for key, value in self.headers.items()}
            body = self.rfile.read(length)
            if path == "/recordings":
                self._send(*app.handle_post_recordings(body, headers))
                return
            self._send(*app.handle_post_skribby(body, headers))

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send(self, status: int, headers: dict[str, str], body: bytes) -> None:
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return MeetingRecordingHandler


def run_http_server(host: str, port: int, app: RecordingApp) -> None:
    server = HTTPServer((host, port), make_handler(app))
    try:
        server.serve_forever()
    finally:
        server.server_close()


def build_runtime_from_env(db_path: Path | None = None) -> MeetingRecordingRuntime:
    api_key = os.environ.get("SKRIBBY_API_KEY")
    public_base_url = os.environ.get("MEETING_RECORDING_PUBLIC_BASE_URL")
    resolved_db_path = db_path or Path(os.environ.get("MEETING_RECORDING_DB", "meeting-recordings.sqlite3"))
    workspace_root = Path(os.environ.get("MEETING_RECORDING_WORKSPACE", "."))
    if not api_key:
        raise ValidationError("SKRIBBY_API_KEY environment variable is required")
    if not public_base_url:
        raise ValidationError("MEETING_RECORDING_PUBLIC_BASE_URL environment variable is required")
    store = MeetingRecordingStore.connect(resolved_db_path)
    store.initialize()
    return MeetingRecordingRuntime(
        MeetingRecordingConfig(
            public_base_url=public_base_url,
            workspace_root=workspace_root,
            openclaw_wakeup_url=os.environ.get("OPENCLAW_MEETING_PROCESS_HOOK_URL"),
            openclaw_hooks_token=os.environ.get("OPENCLAW_HOOKS_TOKEN"),
        ),
        store=store,
        skribby_client=SkribbyClient(api_key=api_key),
    )


def infer_meeting_service(meeting_url: str) -> str | None:
    host = urlparse(meeting_url).netloc.lower()
    if host.endswith("zoom.us") or host.endswith("zoom.com"):
        return "zoom"
    if host == "meet.google.com":
        return "gmeet"
    if host == "teams.microsoft.com" or host.endswith(".teams.microsoft.com"):
        return "teams"
    if host == "teams.live.com" or host.endswith(".teams.live.com"):
        return "teams"
    return None


def generate_job_id() -> str:
    from datetime import datetime, timezone
    import secrets

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"mtgrec-{stamp}-{secrets.token_hex(4)}"


def sanitize_url(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.query:
        return value
    query = [
        f"{quote(key)}={_redacted_query_value(key, item_value)}"
        for key, item_value in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    return urlunparse(parsed._replace(query="&".join(query)))


def hash_meeting_url(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_secret(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def redact_provider_payload(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text == "meeting_url" and isinstance(item, str):
                redacted[key] = sanitize_url(item)
            elif _is_raw_source_key(key_text):
                redacted[key] = _redacted_source_value(item)
            elif _is_sensitive_key(key_text):
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_provider_payload(item)
        return redacted
    if isinstance(value, list):
        return [redact_provider_payload(item) for item in value]
    if isinstance(value, str):
        return sanitize_url(value) if value.startswith(("http://", "https://")) else value
    return value


def _validate_order_request(request: dict[str, Any]) -> dict[str, str]:
    missing = [field for field in REQUIRED_ORDER_FIELDS if not str(request.get(field, "")).strip()]
    if missing:
        raise ValidationError("missing required field(s): " + ", ".join(missing))
    return {field: str(request[field]).strip() for field in REQUIRED_ORDER_FIELDS}


def _provider_bot_id(create_result: dict[str, Any]) -> str | None:
    value = create_result.get("id") or create_result.get("bot_id")
    return str(value) if value else None


def _webhook_job_id(payload: dict[str, Any]) -> str:
    metadata = payload.get("custom_metadata")
    if not isinstance(metadata, dict) or not metadata.get("job_id"):
        raise ValidationError("missing custom_metadata.job_id")
    return str(metadata["job_id"])


def _webhook_bot_id(payload: dict[str, Any]) -> str:
    if not payload.get("bot_id"):
        raise ValidationError("missing bot_id")
    return str(payload["bot_id"])


def _verify_webhook_nonce(job: dict[str, Any], payload: dict[str, Any]) -> None:
    metadata = payload.get("custom_metadata")
    nonce = metadata.get("webhook_nonce") if isinstance(metadata, dict) else None
    if not nonce:
        raise WebhookAuthError("webhook authentication failed")
    expected = str(job.get("webhook_nonce_hash") or "")
    actual = hash_secret(str(nonce))
    if not expected or not hmac.compare_digest(expected, actual):
        raise WebhookAuthError("webhook authentication failed")


def _is_finished_webhook(payload: dict[str, Any]) -> bool:
    data = payload.get("data")
    return (
        payload.get("type") == "status_update"
        and isinstance(data, dict)
        and data.get("new_status") == "finished"
    )


def _header_value(headers: dict[str, str], name: str) -> str:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return ""


def _json_response(status: int, payload: dict[str, Any]) -> tuple[int, dict[str, str], bytes]:
    return (
        status,
        {"content-type": "application/json"},
        (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8"),
    )


def _redacted_query_value(key: str, value: str) -> str:
    return "[redacted]"


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return (
        normalized in SENSITIVE_QUERY_KEYS
        or "token" in normalized
        or "secret" in normalized
        or "nonce" in normalized
        or normalized.endswith("_key")
    )


def _is_raw_source_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in RAW_SOURCE_KEYS or normalized.endswith("_transcript")


def _redacted_source_value(value: Any) -> dict[str, Any]:
    count = len(value) if isinstance(value, list) else 1
    return {"redacted": True, "count": count}

#!/usr/bin/env python3
"""Agent-facing CLI for the meeting recording runtime."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
import urllib.request

from runtime.meeting_recording_service import (
    ValidationError,
    redact_provider_payload,
    resolve_meeting_raw_source_root,
)
from runtime.meeting_recording_store import MeetingRecordingStore
from runtime.meeting_transcript_capture import EmptyTranscriptError, capture_finished_bot
from runtime.openclaw_wakeup import wake_meeting_transcript
from runtime.skribby_client import SkribbyClient, SkribbyClientError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Interact with the meeting recording runtime.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    order = subparsers.add_parser("order", description="Order a meeting recorder bot.")
    order.add_argument("--service-url", required=True)
    order.add_argument("--meeting-url", required=True)
    order.add_argument("--business-id", required=True)
    order.add_argument("--source-id", required=True)
    order.add_argument("--chat-ref", required=True)
    order.add_argument("--requested-by", required=True)
    order.add_argument("--agent-mentioned", action="store_true")
    order.add_argument("--return-channel")
    order.add_argument("--timeout", type=int, default=30)

    recover = subparsers.add_parser("recover", description="Recover a finished provider transcript after a lost webhook.")
    recover.add_argument("--db", type=Path, required=True)
    recover.add_argument("--workspace", type=Path, required=True)
    recover.add_argument("--runtime-config", type=Path)
    recover.add_argument("--job-id", required=True)
    recover.add_argument("--timeout", type=int, default=30)

    retry_wakeup = subparsers.add_parser("retry-wakeup", description="Retry a pending OpenClaw wakeup for a ready packet.")
    retry_wakeup.add_argument("--db", type=Path, required=True)
    retry_wakeup.add_argument("--job-id", required=True)
    retry_wakeup.add_argument("--hook-url", default=os.environ.get("OPENCLAW_MEETING_PROCESS_HOOK_URL", ""))
    retry_wakeup.add_argument("--token", default=os.environ.get("OPENCLAW_HOOKS_TOKEN", ""))
    retry_wakeup.add_argument("--timeout", type=int, default=10)

    args = parser.parse_args(_normalize_dash_values(list(sys.argv[1:] if argv is None else argv)))
    if args.command == "order":
        return _order(args)
    if args.command == "recover":
        return _recover(args)
    if args.command == "retry-wakeup":
        return _retry_wakeup(args)
    parser.error(f"unsupported command: {args.command}")
    return 2


def _order(args: argparse.Namespace) -> int:
    payload = {
        "meeting_url": args.meeting_url,
        "business_id": args.business_id,
        "source_id": args.source_id,
        "chat_ref": args.chat_ref,
        "requested_by": args.requested_by,
        "agent_mentioned": bool(args.agent_mentioned),
    }
    if args.return_channel:
        payload["return_channel"] = args.return_channel

    request = urllib.request.Request(
        urljoin(args.service_url.rstrip("/") + "/", "recordings"),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        body = _read_error_body(exc)
        print(f"meeting recording runtime rejected request: {_safe_error_body(body)}", file=sys.stderr)
        return 3
    except URLError:
        print("meeting recording runtime unreachable", file=sys.stderr)
        return 4

    try:
        result: Any = json.loads(body)
    except Exception:
        print("meeting recording runtime returned invalid JSON", file=sys.stderr)
        return 4
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _recover(args: argparse.Namespace) -> int:
    api_key = os.environ.get("SKRIBBY_API_KEY")
    if not api_key:
        print("SKRIBBY_API_KEY environment variable is required", file=sys.stderr)
        return 2
    try:
        with MeetingRecordingStore.connect(args.db) as store:
            store.initialize()
            job = store.get_job(args.job_id)
            bot_id = str(job.get("bot_id") or "")
            if not bot_id:
                print("meeting recording job has no bot_id", file=sys.stderr)
                return 3
            if job["status"] == "packet_ready" and job.get("packet_path"):
                result = _packet_ready_result(job, args.workspace)
                print(json.dumps(result, indent=2, sort_keys=True))
                return 0

            client = SkribbyClient(api_key=api_key, timeout=args.timeout)
            bot_payload = client.fetch_bot(bot_id)
            if str(bot_payload.get("status") or "") != "finished":
                print("Skribby bot is not finished", file=sys.stderr)
                return 5
            if job["status"] in {"bot_created", "finished_received"}:
                store.mark_transcript_recovered(
                    args.job_id,
                    provider_payload=redact_provider_payload(bot_payload),
                    provider_finished_at=str(bot_payload.get("finished_at") or "") or None,
                )
            elif job["status"] != "transcript_fetched":
                print(f"recording job cannot be recovered from status {job['status']}", file=sys.stderr)
                return 3

            raw_source_root = resolve_meeting_raw_source_root(
                args.workspace,
                runtime_config_path=args.runtime_config,
            )

            capture = capture_finished_bot(
                store.get_job(args.job_id),
                bot_payload,
                raw_source_root,
                observed_at=str(bot_payload.get("finished_at") or "") or None,
            )
            store.mark_packet_ready(
                args.job_id,
                packet_path=str(capture.packet_path),
                transcript_hash=capture.transcript_hash,
                wakeup_pending=True,
            )
            result = _packet_ready_result(store.get_job(args.job_id), args.workspace)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
    except KeyError:
        print("unknown meeting recording job", file=sys.stderr)
        return 3
    except SkribbyClientError:
        print("Skribby fetch-bot request failed", file=sys.stderr)
        return 4
    except EmptyTranscriptError:
        print("Skribby bot response did not contain transcript segments", file=sys.stderr)
        return 5
    except ValidationError as exc:
        print(f"meeting recording configuration error: {exc}", file=sys.stderr)
        return 2


def _packet_ready_result(job: dict[str, Any], workspace: Path) -> dict[str, Any]:
    packet_path = Path(str(job.get("packet_path") or ""))
    packet = {}
    if packet_path.is_file():
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    return {
        "job_id": job["job_id"],
        "bot_id": job.get("bot_id"),
        "status": job["status"],
        "completion_source": job.get("completion_source") or "",
        "provider_finished_at": job.get("provider_finished_at") or "",
        "webhook_received_at": job.get("webhook_received_at") or "",
        "packet_path": str(packet_path),
        "transcript_hash": job.get("transcript_hash") or "",
        "segments_count": len(packet.get("segments") or []),
        "workspace": str(workspace),
    }


def _retry_wakeup(args: argparse.Namespace) -> int:
    if not args.hook_url or not args.token:
        print("OPENCLAW_MEETING_PROCESS_HOOK_URL and OPENCLAW_HOOKS_TOKEN are required", file=sys.stderr)
        return 2
    try:
        with MeetingRecordingStore.connect(args.db) as store:
            store.initialize()
            job = store.get_job(args.job_id)
            if job["status"] != "packet_ready":
                print(f"recording job is not packet_ready: {job['status']}", file=sys.stderr)
                return 3
            packet_path = Path(str(job.get("packet_path") or ""))
            if not packet_path.is_file():
                print("recording job packet_path is missing", file=sys.stderr)
                return 3
            wakeup = wake_meeting_transcript(
                packet_path,
                hook_url=args.hook_url,
                token=args.token,
                timeout=args.timeout,
            )
            if wakeup.pending:
                print("OpenClaw wakeup is still pending", file=sys.stderr)
                return 4
            store.mark_wakeup_delivered(args.job_id)
            print(
                json.dumps(
                    {
                        "job_id": args.job_id,
                        "status": "wakeup_delivered",
                        "wakeup_pending": False,
                        "packet_path": str(packet_path),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
    except KeyError:
        print("unknown meeting recording job", file=sys.stderr)
        return 3


def _read_error_body(exc: HTTPError) -> str:
    try:
        return exc.read().decode("utf-8")
    except Exception:
        return f"HTTP {exc.code}"


def _safe_error_body(value: str) -> str:
    flattened = value.replace("\n", " ").strip()
    return re.sub(r"([?&][A-Za-z0-9_.:-]+=[^&\\s\"'}]+)", _redact_query_pair, flattened)


def _redact_query_pair(match: re.Match[str]) -> str:
    pair = match.group(1)
    key, _, _ = pair.partition("=")
    return f"{key}=[redacted]"


def _normalize_dash_values(argv: list[str]) -> list[str]:
    flags = {"--chat-ref"}
    normalized: list[str] = []
    index = 0
    while index < len(argv):
        current = argv[index]
        next_is_dash_value = (
            index + 1 < len(argv)
            and argv[index + 1].startswith("-")
            and not argv[index + 1].startswith("--")
        )
        if current in flags and next_is_dash_value:
            normalized.append(f"{current}={argv[index + 1]}")
            index += 2
            continue
        normalized.append(current)
        index += 1
    return normalized


if __name__ == "__main__":
    raise SystemExit(main())

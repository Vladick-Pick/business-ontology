#!/usr/bin/env python3
"""Order a Skribby meeting bot with provenance metadata.

The script intentionally only covers the create-bot request. Fetching the final
transcript is deploy-time work because the Skribby docs currently expose more
than one bot/transcript retrieval path.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import urllib.request


DEFAULT_API_URL = "https://platform.skribby.io/api/v1/bot"
SERVICES = {"zoom", "gmeet", "teams"}
SENSITIVE_QUERY_KEYS = {"token", "key", "secret", "signature"}


class UsageError(ValueError):
    pass


def infer_service(meeting_url: str) -> str | None:
    host = urlparse(meeting_url).netloc.lower()
    if host.endswith("zoom.us") or host.endswith("zoom.com"):
        return "zoom"
    if host == "meet.google.com":
        return "gmeet"
    if "teams.microsoft.com" in host or "teams.live.com" in host:
        return "teams"
    return None


def build_payload(
    *,
    meeting_url: str,
    service: str | None,
    bot_name: str,
    transcription_model: str,
    webhook_url: str | None,
    business_id: str,
    chat_id: str,
    source_id: str,
    telegram_message_ref: str,
) -> dict[str, object]:
    resolved_service = service or infer_service(meeting_url)
    if not resolved_service:
        raise UsageError("Could not infer meeting service; pass --service zoom|gmeet|teams")
    if resolved_service not in SERVICES:
        raise UsageError(f"Unsupported service: {resolved_service}")

    payload: dict[str, object] = {
        "meeting_url": meeting_url,
        "service": resolved_service,
        "bot_name": bot_name,
        "transcription_model": transcription_model,
        "custom_metadata": {
            "business_id": business_id or "unknown",
            "chat_id": chat_id or "unknown",
            "source_id": source_id or "unknown",
            "telegram_message_ref": telegram_message_ref or "unknown",
        },
    }
    if webhook_url:
        payload["webhook_url"] = webhook_url
    return payload


def order_bot(payload: dict[str, object], *, api_url: str, api_key: str, timeout: int = 30) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        api_url,
        data=body,
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    return {
        "bot_id": result.get("bot_id"),
        "status": result.get("status"),
    }


def dry_run_payload(payload: dict[str, object]) -> dict[str, object]:
    printable = dict(payload)
    webhook_url = printable.get("webhook_url")
    if isinstance(webhook_url, str):
        printable["webhook_url"] = _redact_url_query(webhook_url)
    return printable


def _redact_url_query(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.query:
        return value
    query = [
        (key, "[redacted]" if _is_sensitive_query_key(key) else item_value)
        for key, item_value in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    return urlunparse(parsed._replace(query=urlencode(query)))


def _is_sensitive_query_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return (
        normalized in SENSITIVE_QUERY_KEYS
        or "token" in normalized
        or "secret" in normalized
        or normalized == "api_key"
        or normalized.endswith("_key")
    )


def _normalize_dash_values(argv: list[str] | None) -> list[str] | None:
    if argv is None:
        return None
    flags = {"--chat-id", "--telegram-message-ref"}
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Order a Skribby meeting recorder bot.")
    parser.add_argument("--meeting-url", required=True)
    parser.add_argument("--service", choices=sorted(SERVICES))
    parser.add_argument("--bot-name", required=True)
    parser.add_argument("--transcription-model", default="whisper")
    parser.add_argument("--webhook-url")
    parser.add_argument("--business-id", default="unknown")
    parser.add_argument("--chat-id", default="unknown")
    parser.add_argument("--source-id", default="unknown")
    parser.add_argument("--telegram-message-ref", default="unknown")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--allow-non-default-api-url", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(_normalize_dash_values(argv))

    try:
        payload = build_payload(
            meeting_url=args.meeting_url,
            service=args.service,
            bot_name=args.bot_name,
            transcription_model=args.transcription_model,
            webhook_url=args.webhook_url,
            business_id=args.business_id,
            chat_id=args.chat_id,
            source_id=args.source_id,
            telegram_message_ref=args.telegram_message_ref,
        )
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(json.dumps(dry_run_payload(payload), indent=2, sort_keys=True))
        return 0

    if args.api_url != DEFAULT_API_URL and not args.allow_non_default_api_url:
        print(
            "error: --api-url requires --allow-non-default-api-url",
            file=sys.stderr,
        )
        return 2

    api_key = os.environ.get("SKRIBBY_API_KEY")
    if not api_key:
        print("error: SKRIBBY_API_KEY environment variable is required", file=sys.stderr)
        return 2

    try:
        result = order_bot(payload, api_url=args.api_url, api_key=api_key)
    except Exception as exc:  # pragma: no cover - network errors are host-specific.
        print(f"error: Skribby create-bot request failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

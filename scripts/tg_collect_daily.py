#!/usr/bin/env python3
"""Collect daily Telegram export data into a structured interpretation packet.

Supported inputs:
- Telegram Desktop JSON exports: any `result.json` under `--exports-dir`.
- JSONL dumps: any `*.jsonl` under `--exports-dir`, one message object per line.

The collector normalizes messages, cursors, refs, and attachment pointers. It
does not infer business meaning from the text.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.request
from zoneinfo import ZoneInfo


CONTACT_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+?\d[\d\s().-]{7,}\d)")
SLUG_RE = re.compile(r"[^a-z0-9]+")


def collect_daily(
    exports_dir: Path | str,
    cursors_file: Path | str,
    out_dir: Path | str,
    chat_map_path: Path | str,
    *,
    tz: str = "UTC",
    backfill_days: int = 30,
    no_wake: bool = False,
    run_id: str | None = None,
    wake_url: str = "http://127.0.0.1:3000/hooks/wake",
) -> dict[str, object]:
    exports_dir = Path(exports_dir)
    cursors_file = Path(cursors_file)
    out_dir = Path(out_dir)
    chat_map_path = Path(chat_map_path)
    zone = ZoneInfo(tz)
    generated_at = _utc_now()
    run_id = run_id or generated_at.replace(":", "").replace("-", "")
    run_dir = out_dir / run_id
    chats_dir = run_dir / "chats"
    run_dir.mkdir(parents=True, exist_ok=True)
    chats_dir.mkdir(parents=True, exist_ok=True)

    chat_map = _load_json(chat_map_path, default={})
    cursors = _load_json(cursors_file, default={})
    if not isinstance(cursors, dict):
        cursors = {}

    lower_bound = datetime.now(timezone.utc) - timedelta(days=max(0, int(backfill_days)))
    input_chats = _load_input_chats(exports_dir, zone)
    packet_messages: list[dict[str, object]] = []
    chat_manifests: list[dict[str, object]] = []
    next_cursors = dict(cursors)

    for chat in input_chats:
        chat_id = chat["chat_id"]
        cursor_before = cursors.get(chat_id) if isinstance(cursors.get(chat_id), dict) else {}
        messages = [
            message
            for message in sorted(chat["messages"], key=lambda item: (item["ts_sort"], item["message_id"]))
            if _is_after_cursor(message, cursor_before, lower_bound)
        ]
        chat_meta = _chat_meta(chat_id, chat.get("chat_slug"), chat_map)
        normalized = [
            _normalize_message(message, chat_meta)
            for message in messages
        ]
        packet_messages.extend(normalized)
        cursor_after = _cursor_after(cursor_before, messages)
        if messages:
            next_cursors[chat_id] = cursor_after
        manifest = {
            "chat_id": chat_id,
            "chat_slug": chat_meta["chat_slug"],
            "business": chat_meta["business"],
            "source_id": chat_meta["source_id"],
            "input_files": chat["input_files"],
            "message_count": len(messages),
            "first_ts": normalized[0]["ts"] if normalized else None,
            "last_ts": normalized[-1]["ts"] if normalized else None,
            "cursor_before": cursor_before or None,
            "cursor_after": cursor_after if messages else cursor_before or None,
        }
        chat_dir = chats_dir / chat_meta["chat_slug"]
        chat_dir.mkdir(parents=True, exist_ok=True)
        _write_json(chat_dir / "chat_manifest.json", manifest)
        chat_manifests.append({**manifest, "path": str((chat_dir / "chat_manifest.json").relative_to(run_dir))})

    packet = {
        "run_id": run_id,
        "generated_at": generated_at,
        "timezone": tz,
        "messages": packet_messages,
    }
    packet_path = run_dir / "interpretation_packet.json"
    _write_json(packet_path, packet)

    run_manifest = {
        "run_id": run_id,
        "generated_at": generated_at,
        "exports_dir": str(exports_dir),
        "out_dir": str(run_dir),
        "timezone": tz,
        "backfill_days": int(backfill_days),
        "chat_count": len([chat for chat in chat_manifests if chat["message_count"]]),
        "message_count": len(packet_messages),
        "no_op": len(packet_messages) == 0,
        "interpretation_packet_path": str(packet_path),
        "chats": chat_manifests,
    }
    _write_json(run_dir / "run_manifest.json", run_manifest)
    _write_json_atomic(cursors_file, next_cursors)

    if not no_wake:
        _wake(wake_url, f"Daily ingest packet ready: {packet_path}")

    return run_manifest


def _load_input_chats(exports_dir: Path, zone: ZoneInfo) -> list[dict[str, object]]:
    chats: dict[str, dict[str, object]] = {}
    for path in sorted(exports_dir.rglob("result.json")):
        payload = _load_json(path, default={})
        chat_id = str(payload.get("id") or path.parent.name)
        chat = chats.setdefault(
            chat_id,
            {
                "chat_id": chat_id,
                "chat_slug": _slug(str(payload.get("name") or path.parent.name)),
                "input_files": [],
                "messages": [],
            },
        )
        chat["input_files"].append(str(path))
        for item in payload.get("messages") or []:
            if isinstance(item, dict):
                message = _from_desktop_message(item, chat_id, zone)
                if message:
                    chat["messages"].append(message)

    for path in sorted(exports_dir.rglob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                continue
            message = _from_jsonl_message(payload, zone)
            if not message:
                continue
            chat_id = message["chat_id"]
            chat = chats.setdefault(
                chat_id,
                {
                    "chat_id": chat_id,
                    "chat_slug": message.get("chat_slug") or _slug(path.stem),
                    "input_files": [],
                    "messages": [],
                },
            )
            if str(path) not in chat["input_files"]:
                chat["input_files"].append(str(path))
            chat["messages"].append(message)
    return list(chats.values())


def _from_desktop_message(item: dict[str, object], chat_id: str, zone: ZoneInfo) -> dict[str, object] | None:
    ts = _parse_ts(str(item.get("date") or item.get("date_unixtime") or ""), zone)
    if ts is None:
        return None
    message_id = int(item.get("id") or 0)
    sender = item.get("from") or item.get("from_id") or "unknown"
    return {
        "chat_id": chat_id,
        "message_id": message_id,
        "ts": _format_ts(ts),
        "ts_sort": ts.timestamp(),
        "sender": sender,
        "text": _flatten_text(item.get("text")),
        "reply_to": item.get("reply_to_message_id"),
        "attachments": _desktop_attachments(item),
    }


def _from_jsonl_message(item: dict[str, object], zone: ZoneInfo) -> dict[str, object] | None:
    chat_id = str(item.get("chat_id") or item.get("chat") or item.get("chat_slug") or "")
    if not chat_id:
        return None
    ts = _parse_ts(str(item.get("ts") or item.get("date") or item.get("timestamp") or ""), zone)
    if ts is None:
        return None
    message_id = int(item.get("message_id") or item.get("id") or 0)
    return {
        "chat_id": chat_id,
        "chat_slug": item.get("chat_slug"),
        "message_id": message_id,
        "ts": _format_ts(ts),
        "ts_sort": ts.timestamp(),
        "sender": item.get("sender") or item.get("from") or "unknown",
        "text": _flatten_text(item.get("text")),
        "reply_to": item.get("reply_to") or item.get("reply_to_message_id"),
        "attachments": _jsonl_attachments(item.get("attachments")),
    }


def _normalize_message(message: dict[str, object], chat_meta: dict[str, str]) -> dict[str, object]:
    sender_name = _sender_name(message.get("sender"))
    return {
        "chat": {
            "chat_id": message["chat_id"],
            "chat_slug": chat_meta["chat_slug"],
            "business": chat_meta["business"],
            "source_id": chat_meta["source_id"],
        },
        "message_id": message["message_id"],
        "ts": message["ts"],
        "sender": {"slug": _slug(sender_name), "label": _redact(sender_name)},
        "text": _redact(str(message.get("text") or "")),
        "reply_to": message.get("reply_to"),
        "attachments": message.get("attachments") or [],
    }


def _is_after_cursor(
    message: dict[str, object],
    cursor: dict[str, object],
    lower_bound: datetime,
) -> bool:
    message_ts = datetime.fromtimestamp(float(message["ts_sort"]), tz=timezone.utc)
    if not cursor:
        return message_ts >= lower_bound
    last_ts = _parse_ts(str(cursor.get("last_ts") or ""), ZoneInfo("UTC"))
    last_id = int(cursor.get("last_id") or 0)
    if last_ts is None:
        return message_ts >= lower_bound
    message_id = int(message["message_id"])
    if message_ts < last_ts:
        return False
    if message_ts == last_ts and message_id <= last_id:
        return False
    return True


def _cursor_after(cursor_before: dict[str, object], messages: list[dict[str, object]]) -> dict[str, object]:
    if not messages:
        return dict(cursor_before)
    last = messages[-1]
    return {"last_ts": last["ts"], "last_id": int(last["message_id"])}


def _chat_meta(chat_id: str, source_slug: object, chat_map: object) -> dict[str, str]:
    mapping = chat_map if isinstance(chat_map, dict) else {}
    value = mapping.get(chat_id)
    if value is None and source_slug:
        value = mapping.get(str(source_slug))
    slug = _slug(str(source_slug or chat_id))
    if isinstance(value, str):
        return {
            "chat_slug": slug,
            "business": value,
            "source_id": f"tg-group-{_slug(value)}",
        }
    if isinstance(value, dict):
        business = str(value.get("business") or "unknown")
        return {
            "chat_slug": _slug(str(value.get("chat_slug") or source_slug or chat_id)),
            "business": business,
            "source_id": str(value.get("source_id") or f"tg-group-{_slug(business)}"),
        }
    return {"chat_slug": slug, "business": "unknown", "source_id": f"tg-group-{slug}"}


def _parse_ts(value: str, zone: ZoneInfo) -> datetime | None:
    if not value:
        return None
    if value.isdigit():
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(timezone.utc)


def _format_ts(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _flatten_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
        return "".join(parts)
    return str(value)


def _desktop_attachments(item: dict[str, object]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for field in ("file", "photo", "thumbnail"):
        value = item.get(field)
        if isinstance(value, str) and value:
            refs.append({"path": value, "kind": field})
    media_type = item.get("media_type")
    if isinstance(media_type, str) and media_type and not refs:
        refs.append({"kind": media_type})
    return refs


def _jsonl_attachments(value: object) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    if not isinstance(value, list):
        return refs
    for item in value:
        if not isinstance(item, dict):
            continue
        ref = {
            key: str(item[key])
            for key in ("path", "name", "kind", "media_type", "mime_type")
            if key in item and item[key]
        }
        if ref:
            refs.append(ref)
    return refs


def _sender_name(sender: object) -> str:
    if isinstance(sender, dict):
        for key in ("name", "username", "id"):
            if sender.get(key):
                return str(sender[key])
        return "unknown"
    return str(sender or "unknown")


def _redact(value: str) -> str:
    return CONTACT_RE.sub("[redacted-contact]", value)


def _slug(value: str) -> str:
    slug = SLUG_RE.sub("-", value.lower()).strip("-")
    return slug or "unknown"


def _load_json(path: Path, default: object) -> object:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp_name = handle.name
    Path(temp_name).replace(path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _wake(wake_url: str, text: str) -> None:
    token = os.environ.get("OPENCLAW_HOOKS_TOKEN")
    if not token:
        raise RuntimeError("OPENCLAW_HOOKS_TOKEN is required unless --no-wake is set")
    body = json.dumps({"text": text, "mode": "now"}).encode("utf-8")
    request = urllib.request.Request(
        wake_url,
        data=body,
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        response.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect Telegram exports into a daily packet.")
    parser.add_argument("--exports-dir", type=Path, required=True)
    parser.add_argument("--cursors-file", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--chat-map", type=Path, required=True)
    parser.add_argument("--tz", default="UTC")
    parser.add_argument("--backfill-days", type=int, default=30)
    parser.add_argument("--run-id")
    parser.add_argument("--wake-url", default="http://127.0.0.1:3000/hooks/wake")
    parser.add_argument("--no-wake", action="store_true")
    args = parser.parse_args(argv)
    result = collect_daily(
        args.exports_dir,
        args.cursors_file,
        args.out_dir,
        args.chat_map,
        tz=args.tz,
        backfill_days=args.backfill_days,
        no_wake=args.no_wake,
        run_id=args.run_id,
        wake_url=args.wake_url,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

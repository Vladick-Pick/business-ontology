#!/usr/bin/env python3
"""Export Telegram native-folder messages through an MTProto user session.

This is the source acquisition layer for Telegram. It connects with Telethon,
resolves a native Telegram folder by title, writes per-chat JSONL files, and
maintains a raw-fetch cursor. `scripts/tg_collect_daily.py` then consumes the
JSONL folder and builds the interpretation packet for the resident agent.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib
from typing import Any
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class TelegramSettings:
    api_id: int
    api_hash: str
    session_path: Path
    folder_title: str


@dataclass(frozen=True)
class RuntimeSettings:
    timezone: str = "UTC"
    backfill_days: int = 1
    max_messages_per_chat: int | None = None
    download_media: bool = True


@dataclass(frozen=True)
class StorageSettings:
    exports_dir: Path
    cursor_file: Path


@dataclass(frozen=True)
class MtprotoExportConfig:
    telegram: TelegramSettings
    runtime: RuntimeSettings
    storage: StorageSettings


def load_config(path: Path | str) -> MtprotoExportConfig:
    config_path = Path(path)
    base_dir = config_path.parent
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)

    telegram = _section(raw, "telegram")
    runtime = raw.get("runtime") if isinstance(raw.get("runtime"), dict) else {}
    storage = _section(raw, "storage")

    api_id = _env_value(telegram, "api_id", "api_id_env", "TELEGRAM_API_ID")
    api_hash = _env_value(telegram, "api_hash", "api_hash_env", "TELEGRAM_API_HASH")
    max_messages = runtime.get("max_messages_per_chat")

    return MtprotoExportConfig(
        telegram=TelegramSettings(
            api_id=int(api_id),
            api_hash=str(api_hash),
            session_path=_session_path(base_dir, telegram.get("session_path")),
            folder_title=str(_required(telegram, "folder_title")),
        ),
        runtime=RuntimeSettings(
            timezone=str(runtime.get("timezone") or "UTC"),
            backfill_days=int(runtime.get("backfill_days") or 1),
            max_messages_per_chat=int(max_messages) if max_messages not in (None, "") else None,
            download_media=bool(runtime.get("download_media", True)),
        ),
        storage=StorageSettings(
            exports_dir=_config_path(base_dir, _required(storage, "exports_dir")),
            cursor_file=_config_path(base_dir, _required(storage, "cursor_file")),
        ),
    )


def bootstrap_login(config: MtprotoExportConfig, *, phone: str | None = None) -> Path:
    from telethon.sync import TelegramClient

    config.telegram.session_path.parent.mkdir(parents=True, exist_ok=True)
    with TelegramClient(
        str(config.telegram.session_path),
        config.telegram.api_id,
        config.telegram.api_hash,
    ) as client:
        client.start(phone=phone)
    return config.telegram.session_path


class TelethonGateway:
    def __init__(self, settings: TelegramSettings) -> None:
        self.settings = settings
        self.client = None
        self.functions = None

    def __enter__(self) -> "TelethonGateway":
        from telethon import functions
        from telethon.sync import TelegramClient

        self.functions = functions
        self.client = TelegramClient(
            str(self.settings.session_path),
            self.settings.api_id,
            self.settings.api_hash,
        )
        self.client.connect()
        if not self.client.is_user_authorized():
            raise RuntimeError(
                "Telegram session is not authorized. Run tg_mtproto_export.py --bootstrap-login first."
            )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.client is not None:
            self.client.disconnect()
        self.client = None

    def list_folder_chats(self, folder_title: str) -> list[dict[str, Any]]:
        self._require_client()
        filters_result = self.client(self.functions.messages.GetDialogFiltersRequest())
        filters = list(getattr(filters_result, "filters", filters_result))
        folder = _find_filter_by_title(filters, folder_title)
        dialogs = self.client.get_dialogs()
        return [chat_ref_from_dialog(dialog) for dialog in select_dialogs_for_filter(dialogs, folder)]

    def iter_new_messages(
        self,
        chat_ref: dict[str, Any],
        *,
        after_message_id: int | None,
        after_date: datetime | None,
        limit: int | None,
    ) -> list[Any]:
        self._require_client()
        entity = chat_ref["entity"]
        if after_message_id is not None:
            return list(
                self.client.iter_messages(
                    entity,
                    min_id=int(after_message_id),
                    limit=limit,
                    reverse=True,
                )
            )
        return list(
            self.client.iter_messages(
                entity,
                offset_date=after_date,
                limit=limit,
                reverse=True,
            )
        )

    def download_media(self, message: Any, target_dir: Path) -> str | None:
        self._require_client()
        if getattr(message, "file", None) is None:
            return None
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / message_file_name(message)
        return self.client.download_media(message, file=str(target_path))

    def _require_client(self) -> None:
        if self.client is None:
            raise RuntimeError("TelethonGateway must be used as a context manager")


def run_export(
    config: MtprotoExportConfig,
    *,
    telegram: Any,
    now: datetime | None = None,
    run_id: str | None = None,
    allow_partial: bool = False,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    generated_at = _format_ts(current_time)
    run_id = run_id or f"mtproto-{current_time.strftime('%Y%m%dT%H%M%SZ')}"
    zone = ZoneInfo(config.runtime.timezone)
    lower_bound = current_time.astimezone(zone) - timedelta(days=max(0, config.runtime.backfill_days))
    lower_bound = lower_bound.astimezone(timezone.utc)

    run_dir = config.storage.exports_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    cursors = _load_json(config.storage.cursor_file, default={})
    if not isinstance(cursors, dict):
        cursors = {}
    next_cursors = dict(cursors)

    total_messages = 0
    exported_chats = 0
    failed_chats: list[dict[str, str]] = []
    jsonl_paths: list[str] = []
    chats: list[dict[str, Any]] = []

    for chat_ref in telegram.list_folder_chats(config.telegram.folder_title):
        chat_id = str(chat_ref["id"])
        chat_slug = str(chat_ref.get("slug") or _slug(str(chat_ref.get("title") or chat_id)))
        cursor = cursors.get(chat_id) if isinstance(cursors.get(chat_id), dict) else {}
        last_id = int(cursor.get("last_id")) if cursor and cursor.get("last_id") is not None else None
        after_date = None if last_id is not None else lower_bound
        try:
            raw_messages = telegram.iter_new_messages(
                chat_ref,
                after_message_id=last_id,
                after_date=after_date,
                limit=config.runtime.max_messages_per_chat,
            )
            normalized: list[dict[str, Any]] = []
            attachments_dir = run_dir / "attachments" / chat_slug
            for message in raw_messages:
                downloaded_path = None
                if config.runtime.download_media:
                    downloaded_path = telegram.download_media(message, attachments_dir)
                normalized.append(message_to_jsonl(message, chat_ref=chat_ref, downloaded_path=downloaded_path))

            jsonl_path = run_dir / f"{chat_slug}.jsonl"
            if normalized:
                _write_jsonl(jsonl_path, normalized)
                jsonl_paths.append(str(jsonl_path))
                total_messages += len(normalized)
                exported_chats += 1
                last = normalized[-1]
                next_cursors[chat_id] = {"last_id": int(last["message_id"]), "last_ts": last["ts"]}
            chats.append(
                {
                    "chat_id": chat_id,
                    "chat_slug": chat_slug,
                    "title": chat_ref.get("title"),
                    "message_count": len(normalized),
                    "jsonl_path": str(jsonl_path) if normalized else None,
                    "cursor_before": cursor or None,
                    "cursor_after": next_cursors.get(chat_id),
                }
            )
        except Exception as exc:
            failed_chats.append({"chat_id": chat_id, "chat_slug": chat_slug, "error": str(exc)})

    cursor_committed = not failed_chats or allow_partial
    _write_json_atomic(config.storage.cursor_file, next_cursors if cursor_committed else cursors)
    manifest = {
        "source_mode": "mtproto-session",
        "run_id": run_id,
        "generated_at": generated_at,
        "folder_title": config.telegram.folder_title,
        "exports_dir": str(config.storage.exports_dir),
        "run_dir": str(run_dir),
        "cursor_file": str(config.storage.cursor_file),
        "cursor_committed": cursor_committed,
        "chat_count": exported_chats,
        "total_messages": total_messages,
        "failed_chats": failed_chats,
        "jsonl_paths": jsonl_paths,
        "chats": chats,
        "next_command": "python3 scripts/tg_collect_daily.py --exports-dir <run_dir> --cursors-file <packet-cursors.json> --out-dir <packet-runs> --chat-map <chat-map.json>",
    }
    _write_json(run_dir / "mtproto_run_manifest.json", manifest)
    return manifest


def chat_ref_from_dialog(dialog: Any) -> dict[str, Any]:
    entity = getattr(dialog, "entity", None) or dialog
    title = (
        getattr(entity, "title", None)
        or getattr(dialog, "name", None)
        or getattr(entity, "username", None)
        or str(getattr(entity, "id", getattr(dialog, "id", "unknown")))
    )
    chat_id = getattr(dialog, "id", None)
    if chat_id is None:
        chat_id = getattr(entity, "id")
    return {
        "id": int(chat_id),
        "title": title,
        "slug": _slug(str(title)),
        "type": _chat_type(dialog, entity),
        "username": getattr(entity, "username", None),
        "entity": entity,
    }


def select_dialogs_for_filter(dialogs: list[Any], filter_obj: Any) -> list[Any]:
    include_keys = {
        _peer_key(peer)
        for peer in list(getattr(filter_obj, "pinned_peers", []) or [])
        + list(getattr(filter_obj, "include_peers", []) or [])
    }
    exclude_keys = {_peer_key(peer) for peer in list(getattr(filter_obj, "exclude_peers", []) or [])}

    selected: list[Any] = []
    for dialog in dialogs:
        try:
            dialog_key = _peer_key(getattr(dialog, "input_entity", None) or getattr(dialog, "entity", None))
        except ValueError:
            continue
        if dialog_key in exclude_keys:
            continue
        if include_keys and dialog_key in include_keys:
            selected.append(dialog)
            continue
        if not include_keys and _dialog_matches_folder_flags(dialog, filter_obj):
            selected.append(dialog)
    return selected


def message_file_name(message: Any) -> str:
    file_obj = getattr(message, "file", None)
    name = getattr(file_obj, "name", None)
    if isinstance(name, str) and name.strip():
        return Path(name).name
    ext = getattr(file_obj, "ext", None) or ""
    return f"message-{int(getattr(message, 'id'))}{ext}"


def message_to_jsonl(message: Any, *, chat_ref: dict[str, Any], downloaded_path: str | None) -> dict[str, Any]:
    sender = getattr(message, "sender", None)
    reply_to = getattr(message, "reply_to", None)
    return {
        "chat_id": str(chat_ref["id"]),
        "chat_slug": chat_ref.get("slug") or _slug(str(chat_ref.get("title") or chat_ref["id"])),
        "message_id": int(getattr(message, "id")),
        "ts": _format_ts(_message_date(message)),
        "sender": {
            "id": _optional_int(_get(sender, "id") or _get(message, "sender_id")),
            "username": _get(sender, "username"),
            "name": _display_name(sender),
        },
        "text": _message_text(message),
        "reply_to": _optional_int(_get(reply_to, "reply_to_msg_id") or _get(message, "reply_to_msg_id")),
        "thread": {
            "is_forum_topic": bool(_get(reply_to, "forum_topic")),
            "top_message_id": _optional_int(_get(reply_to, "reply_to_top_id")),
        }
        if reply_to is not None
        else None,
        "attachments": _attachments(message, downloaded_path),
    }


def _attachments(message: Any, downloaded_path: str | None) -> list[dict[str, str]]:
    file_obj = getattr(message, "file", None)
    media_kind = _media_kind(message)
    if file_obj is None and media_kind == "text":
        return []
    ref: dict[str, str] = {"kind": media_kind}
    if downloaded_path:
        ref["path"] = downloaded_path
    name = getattr(file_obj, "name", None)
    if isinstance(name, str) and name.strip():
        ref["name"] = Path(name).name
    mime_type = getattr(file_obj, "mime_type", None)
    if isinstance(mime_type, str) and mime_type:
        ref["mime_type"] = mime_type
        ref["media_type"] = media_kind
    size = getattr(file_obj, "size", None)
    if size is not None:
        ref["size"] = str(size)
    file_id = getattr(file_obj, "id", None)
    if file_id is not None:
        ref["telegram_file_id"] = str(file_id)
    return [ref]


def _media_kind(message: Any) -> str:
    media = getattr(message, "media", None)
    explicit_kind = getattr(media, "kind", None)
    if explicit_kind:
        return str(explicit_kind)
    file_obj = getattr(message, "file", None)
    mime_type = (getattr(file_obj, "mime_type", None) or "").lower()
    if mime_type.startswith("audio/"):
        return "audio"
    if mime_type.startswith("image/"):
        return "image"
    if mime_type:
        return "document"
    return "text"


def _message_text(message: Any) -> str:
    for field in ("raw_text", "message", "text"):
        value = getattr(message, field, None)
        if isinstance(value, str) and value:
            return value
    return ""


def _message_date(message: Any) -> datetime:
    value = getattr(message, "date", None)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    raise ValueError(f"Message {getattr(message, 'id', 'unknown')} has no datetime date")


def _display_name(sender: Any) -> str | None:
    if sender is None:
        return None
    username = _get(sender, "username")
    if isinstance(username, str) and username.strip():
        return username.strip()
    parts = [
        str(value).strip()
        for value in (_get(sender, "first_name"), _get(sender, "last_name"))
        if value
    ]
    return " ".join(parts) if parts else None


def _find_filter_by_title(filters: list[Any], desired_title: str) -> Any:
    desired = desired_title.strip().casefold()
    for item in filters:
        title = getattr(getattr(item, "title", None), "text", getattr(item, "title", None))
        if isinstance(title, str) and title.strip().casefold() == desired:
            return item
    raise ValueError(f"Telegram folder not found: {desired_title}")


def _peer_key(peer: Any) -> tuple[str, int]:
    if peer is None:
        raise ValueError("Peer is required")
    if hasattr(peer, "user_id"):
        return ("user", int(getattr(peer, "user_id")))
    if hasattr(peer, "chat_id"):
        return ("chat", int(getattr(peer, "chat_id")))
    if hasattr(peer, "channel_id"):
        return ("channel", int(getattr(peer, "channel_id")))

    type_name = type(peer).__name__.lower()
    if "self" in type_name:
        raise ValueError("Self peer is not part of folder matching")
    peer_id = getattr(peer, "id", None)
    if peer_id is None:
        raise ValueError("Peer id is required")
    if "user" in type_name:
        return ("user", int(peer_id))
    if "channel" in type_name:
        return ("channel", int(peer_id))
    return ("chat", int(peer_id))


def _dialog_matches_folder_flags(dialog: Any, filter_obj: Any) -> bool:
    entity = getattr(dialog, "entity", None) or dialog
    is_group = bool(getattr(dialog, "is_group", False) or getattr(entity, "megagroup", False))
    is_channel = bool(getattr(dialog, "is_channel", False))
    is_user = bool(getattr(dialog, "is_user", False))
    is_bot = bool(getattr(entity, "bot", False))
    if bool(getattr(filter_obj, "groups", False)) and is_group:
        return True
    if bool(getattr(filter_obj, "broadcasts", False)) and is_channel and not is_group:
        return True
    if bool(getattr(filter_obj, "bots", False)) and is_bot:
        return True
    if bool(getattr(filter_obj, "contacts", False)) and is_user and not is_bot:
        return True
    if bool(getattr(filter_obj, "non_contacts", False)) and is_user and not is_bot:
        return True
    return False


def _chat_type(dialog: Any, entity: Any) -> str:
    if bool(getattr(dialog, "is_group", False) or getattr(entity, "megagroup", False)):
        return "group"
    if bool(getattr(dialog, "is_channel", False)):
        return "channel"
    if bool(getattr(dialog, "is_user", False)):
        return "user"
    return "chat"


def _section(raw: dict[str, Any], name: str) -> dict[str, Any]:
    section = raw.get(name)
    if not isinstance(section, dict):
        raise ValueError(f"Missing required section: {name}")
    return section


def _required(section: dict[str, Any], key: str) -> Any:
    value = section.get(key)
    if value in (None, ""):
        raise ValueError(f"Missing required value: {key}")
    return value


def _config_path(base_dir: Path, value: Any) -> Path:
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path
    return base_dir / path


def _session_path(config_dir: Path, value: Any) -> Path:
    if value not in (None, ""):
        return _config_path(config_dir, value)
    workspace_dir = config_dir.parent if config_dir.name == "source-setup" else config_dir
    return workspace_dir / "secrets" / "telegram" / "telegram-user.session"


def _env_value(section: dict[str, Any], value_key: str, env_key: str, default_env: str) -> str:
    if section.get(value_key) not in (None, ""):
        raise ValueError(f"{value_key} must be provided through {env_key}, not as a literal config value")
    env_name = str(section.get(env_key) or default_env)
    value = os.environ.get(env_name)
    if not value:
        raise ValueError(f"Environment variable {env_name} is required")
    return value


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _get(obj: Any, field: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(field)
    return getattr(obj, field, None)


def _slug(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    return "-".join(part for part in safe.split("-") if part) or "chat"


def _format_ts(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temp_name = handle.name
    Path(temp_name).replace(path)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Telegram folder messages through MTProto.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--bootstrap-login", action="store_true")
    parser.add_argument("--phone")
    parser.add_argument("--run-id")
    parser.add_argument("--now", help="ISO timestamp for deterministic tests or backfills.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Return success even when one or more selected chats failed to export.",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.bootstrap_login:
        session_path = bootstrap_login(config, phone=args.phone)
        print(session_path)
        return 0

    now = datetime.fromisoformat(args.now) if args.now else None
    with TelethonGateway(config.telegram) as telegram:
        manifest = run_export(
            config,
            telegram=telegram,
            now=now,
            run_id=args.run_id,
            allow_partial=args.allow_partial,
        )
    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(manifest["run_dir"])
    if manifest.get("failed_chats") and not args.allow_partial:
        print(
            f"Telegram export failed for {len(manifest['failed_chats'])} chat(s); refusing partial success.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

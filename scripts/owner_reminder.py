#!/usr/bin/env python3
"""Render one owner reminder from current requests and system health."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
for import_root in (SCRIPT_DIR, REPO_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from runtime.operational_store import OperationalStore  # noqa: E402


NO_REPLY = "NO_REPLY"
HIGH_PRIORITY_KINDS = {"review", "migration", "live-proof", "source-access"}
UNSAFE_CHAT_PATTERN = re.compile(
    r"(?:[/\\][A-Za-z0-9._-]+|\b(?:hreq|mcpkg|srcevt|src|rev|job|cron)[_:#-][A-Za-z0-9])",
    re.IGNORECASE,
)


def _read_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _runtime_config(workspace: Path) -> dict[str, Any]:
    for name in ("runtime-config.json", "runtime-config.example.json"):
        payload = _read_object(workspace / name)
        if payload is not None:
            return payload
    return {}


def _workspace_path(workspace: Path, value: object, fallback: str) -> Path:
    candidate = Path(str(value or fallback))
    resolved = candidate.resolve() if candidate.is_absolute() else (workspace / candidate).resolve()
    try:
        resolved.relative_to(workspace.resolve())
    except ValueError as exc:
        raise ValueError("configured store path escapes workspace") from exc
    return resolved


def _parse_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _minutes(value: str) -> int:
    match = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", value)
    if not match:
        raise ValueError("quiet window must use HH:MM-HH:MM")
    return int(match.group(1)) * 60 + int(match.group(2))


def _in_quiet_window(local_now: datetime, value: object) -> bool:
    if not isinstance(value, str) or "-" not in value:
        raise ValueError("quiet window is not configured")
    start_text, end_text = (part.strip() for part in value.split("-", 1))
    start = _minutes(start_text)
    end = _minutes(end_text)
    current = local_now.hour * 60 + local_now.minute
    if start == end:
        return True
    if start < end:
        return start <= current < end
    return current >= start or current < end


def _request_priority(request: dict[str, object]) -> tuple[object, ...]:
    blocks = request.get("blocks")
    urgent = bool(isinstance(blocks, list) and blocks) or str(request.get("kind") or "") in HIGH_PRIORITY_KINDS
    due_or_asked = str(request.get("dueAt") or request.get("askedAt") or "")
    return (0 if urgent else 1, due_or_asked, str(request.get("askedAt") or ""), str(request.get("requestId") or ""))


def _open_requests(workspace: Path) -> tuple[list[dict[str, object]], str]:
    config = _runtime_config(workspace)
    try:
        store_path = _workspace_path(
            workspace,
            config.get("store_path"),
            "agent-state/operational-store.sqlite",
        )
    except ValueError:
        return [], "invalid-store-path"
    if not store_path.is_file():
        return [], "missing-store"
    try:
        with OperationalStore.open_readonly(store_path) as store:
            requests = store.list_open_human_requests(limit=50)
    except Exception as exc:
        return [], f"read-failed:{type(exc).__name__}"
    return sorted(requests, key=_request_priority), "ok"


def _plain(value: object, fallback: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().strip("`")
    if not text or text.count("?") > 1 or UNSAFE_CHAT_PATTERN.search(text):
        return fallback
    return text


def _request_message(request: dict[str, object], total: int, language: str) -> str:
    if language == "ru":
        prompt = _plain(
            request.get("prompt"),
            "Один открытый вопрос всё ещё ждёт вашего решения. Попросите меня показать текущий вопрос.",
        )
        recommendation = _plain(
            request.get("recommendedAnswer"),
            "Сначала ответьте на этот вопрос: сейчас он блокирует самую раннюю незавершённую работу.",
        )
        return (
            f"Незакрытых вопросов: {total}. "
            f"Сейчас нужен ответ: {prompt}\n\n"
            f"Рекомендация: {recommendation}\n\n"
            "Последствие: пока ответа нет, связанная с ним работа остаётся на паузе."
        )
    prompt = _plain(
        request.get("prompt"),
        "One open item still needs your decision. Ask me for the current question.",
    )
    recommendation = _plain(
        request.get("recommendedAnswer"),
        "Answer this item first because it is currently blocking the oldest pending work.",
    )
    prefix = f"You have {total} open item{'s' if total != 1 else ''}. "
    return (
        f"{prefix}Current: {prompt}\n\n"
        f"Recommendation: {recommendation}\n\n"
        "Consequence: if it remains unanswered, the work behind it stays paused."
    )


def _health_message(language: str) -> str:
    if language == "ru":
        return (
            "Бизнес-аналитику нужно внимание: последняя внутренняя проверка системы не прошла.\n\n"
            "Рекомендация: попросите меня повторно проверить состояние системы до следующего сканирования источников.\n\n"
            "Последствие: пока проверка не пройдена, готовность источников и напоминаний не доказана."
        )
    return (
        "The analyst needs attention: its latest internal system check is not healthy.\n\n"
        "Recommendation: ask me to check the system again before the next source scan.\n\n"
        "Consequence: until that check passes, source and reminder readiness remain unproven."
    )


def render_reminder(workspace: Path, agent_id: str, now: datetime) -> str:
    scheduling = _read_object(workspace / "agent-state" / "managed-scheduling.json")
    if scheduling is None or scheduling.get("agent_id") != agent_id:
        return NO_REPLY
    reminder = scheduling.get("owner_reminder")
    if not isinstance(reminder, dict) or reminder.get("configured") is not True:
        return NO_REPLY
    if (
        reminder.get("setup_status") != "configured"
        or reminder.get("requires_owner_confirmation") is not False
    ):
        return NO_REPLY
    required = (
        "cadence",
        "cron",
        "timezone",
        "channel",
        "delivery_target",
        "quiet_window",
        "language",
        "confirmation_ref",
        "confirmed_at",
    )
    if any(not reminder.get(key) for key in required):
        return NO_REPLY
    try:
        local_now = now.astimezone(ZoneInfo(str(reminder["timezone"])))
        if _in_quiet_window(local_now, reminder["quiet_window"]):
            return NO_REPLY
    except (ValueError, ZoneInfoNotFoundError):
        return NO_REPLY

    requests, request_status = _open_requests(workspace)
    health = _read_object(workspace / "agent-state" / "system-health.json") or {}
    health_status = str(health.get("overall_status") or "unknown")
    language = "ru" if str(reminder.get("language")) == "ru" else "en"
    if requests:
        return _request_message(requests[0], len(requests), language)
    if request_status != "ok" or health_status != "ok":
        return _health_message(language)
    return NO_REPLY


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render one owner reminder or NO_REPLY.")
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--now", help="Deterministic timestamp for tests.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(NO_REPLY)
        return 0
    try:
        message = render_reminder(workspace, args.agent_id, _parse_now(args.now))
    except ValueError:
        print(NO_REPLY)
        return 0
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

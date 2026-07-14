#!/usr/bin/env python3
"""Resolve one inbound owner reply against one open human request.

The reply body is read from stdin so raw private-message text does not need to
appear in a process argument. The body is used for validation only and is not
stored or returned.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
for import_root in (SCRIPT_DIR, REPO_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from runtime.operational_store import OperationalStore  # noqa: E402


MAX_REPLY_CHARS = 65_536
OPEN_REQUEST_STATUSES = {"open", "deferred"}
REVIEW_KINDS = {"review"}
HIGH_RISK_NON_REVIEW_KINDS = {"migration", "live-proof", "source-access"}
GENERIC_ACK_RE = re.compile(
    r"^\s*(?:"
    r"yes|yep|yeah|ok|okay|all good|everything(?:'s| is)? fine|looks good|"
    r"да|ага|ок|окей|хорошо|всё ок|все ок|всё хорошо|все хорошо"
    r")[.!\s]*$",
    re.IGNORECASE,
)
EXPLICIT_ACTION_RE = re.compile(
    r"\b(?:accept|approve|authorize|reject|defer|cancel|run|start|use|connect|grant|"
    r"принять|принимаю|одобрить|одобряю|разрешить|разрешаю|отклонить|"
    r"откладываю|отменить|запустить|запускай|использовать|подключить|выдать)\b",
    re.IGNORECASE,
)
CONTENT_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё-]{3,}")
ACTION_WORDS = {
    "accept",
    "approve",
    "authorize",
    "reject",
    "defer",
    "cancel",
    "start",
    "connect",
    "grant",
    "принять",
    "принимаю",
    "одобрить",
    "одобряю",
    "разрешить",
    "разрешаю",
    "отклонить",
    "откладываю",
    "отменить",
    "запустить",
    "запускай",
    "использовать",
    "подключить",
    "выдать",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clarification_rendering(language: str) -> str:
    if language == "ru":
        return (
            "Не удалось безопасно связать ответ с одним текущим вопросом. "
            "На какой один текущий вопрос вы отвечаете?\n\n"
            "Рекомендация: ответьте прямым reply на один вопрос и назовите "
            "нужное действие.\n\n"
            "Последствие: все текущие запросы и review-решения останутся "
            "без изменений, пока ответ не станет однозначным."
        )
    return (
        "I could not safely match that reply to one actionable current question. "
        "Which single current question are you answering?\n\n"
        "Recommendation: reply directly to that one question and state the intended action.\n\n"
        "Consequence: all current requests and review decisions stay unchanged until "
        "the reply is unambiguous."
    )


def _clarification_id(
    *,
    channel: str,
    actor: str,
    reply_to_message_ref: str,
    inbound_message_ref: str,
    reply_text: str,
) -> str:
    fingerprint = "\0".join(
        (channel, actor, reply_to_message_ref, inbound_message_ref, reply_text.strip())
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:20]
    return f"hreq-reply-clarification-{digest}"


def _has_explicit_action_and_object(text: str) -> bool:
    if EXPLICIT_ACTION_RE.search(text) is None:
        return False
    content_words = {
        word.casefold()
        for word in CONTENT_WORD_RE.findall(text)
        if word.casefold() not in ACTION_WORDS
    }
    return bool(content_words)


def _clarification_result(
    store: OperationalStore,
    *,
    channel: str,
    actor: str,
    reply_to_message_ref: str,
    inbound_message_ref: str,
    reply_text: str,
    received_at: str,
    language: str,
    reason: str,
) -> dict[str, Any]:
    rendering = _clarification_rendering(language)
    request_id = _clarification_id(
        channel=channel,
        actor=actor,
        reply_to_message_ref=reply_to_message_ref,
        inbound_message_ref=inbound_message_ref,
        reply_text=reply_text,
    )
    existing = store.get_human_request(request_id)
    created = existing is None
    if created:
        store.record_human_request(
            {
                "requestId": request_id,
                "kind": "clarification",
                "status": "open",
                "owner": actor,
                "channel": channel,
                "messageRef": "",
                "prompt": rendering.split("\n\n", 1)[0],
                "recommendedAnswer": (
                    "Ответьте прямым reply на один вопрос и назовите действие."
                    if language == "ru"
                    else "Reply directly to one question and state the intended action."
                ),
                "blocks": [],
                "sourceRef": inbound_message_ref,
                "askedAt": received_at,
            }
        )
    return {
        "status": "clarification-required",
        "reason": reason,
        "answeredRequestIds": [],
        "reviewDecisionIds": [],
        "clarificationCount": 1,
        "clarificationCreated": created,
        "clarification": {
            "requestId": request_id,
            "rendering": rendering,
        },
    }


def _exact_open_match(
    store: OperationalStore,
    *,
    channel: str,
    reply_to_message_ref: str,
) -> dict[str, object] | None:
    if not reply_to_message_ref:
        return None

    indexed = store.find_human_request_by_message_ref(channel, reply_to_message_ref)
    if indexed is None or str(indexed.get("status") or "") not in OPEN_REQUEST_STATUSES:
        return None

    matches = [
        request
        for request in store.list_open_human_requests(limit=10_000)
        if request.get("channel") == channel
        and request.get("messageRef") == reply_to_message_ref
    ]
    if len(matches) != 1:
        return None
    if matches[0].get("requestId") != indexed.get("requestId"):
        return None
    return matches[0]


def resolve_owner_reply(
    store: OperationalStore,
    *,
    channel: str,
    actor: str,
    reply_to_message_ref: str,
    reply_text: str,
    inbound_message_ref: str = "",
    received_at: str | None = None,
    language: str = "en",
) -> dict[str, Any]:
    """Resolve one reply without applying review decisions or storing raw text."""

    timestamp = received_at or _now()
    text = reply_text.strip()
    match = _exact_open_match(
        store,
        channel=channel,
        reply_to_message_ref=reply_to_message_ref.strip(),
    )
    if match is None:
        return _clarification_result(
            store,
            channel=channel,
            actor=actor,
            reply_to_message_ref=reply_to_message_ref,
            inbound_message_ref=inbound_message_ref,
            reply_text=reply_text,
            received_at=timestamp,
            language=language,
            reason="no-exact-open-message-ref",
        )

    routed_owner = str(match.get("owner") or "unknown")
    if routed_owner not in {"", "unknown", actor}:
        return _clarification_result(
            store,
            channel=channel,
            actor=actor,
            reply_to_message_ref=reply_to_message_ref,
            inbound_message_ref=inbound_message_ref,
            reply_text=reply_text,
            received_at=timestamp,
            language=language,
            reason="actor-not-authorized",
        )

    kind = str(match.get("kind") or "")
    if kind in REVIEW_KINDS:
        reason = (
            "review-action-not-explicit"
            if not text or GENERIC_ACK_RE.fullmatch(text)
            else "review-validation-required"
        )
        if reason == "review-action-not-explicit":
            return _clarification_result(
                store,
                channel=channel,
                actor=actor,
                reply_to_message_ref=reply_to_message_ref,
                inbound_message_ref=inbound_message_ref,
                reply_text=reply_text,
                received_at=timestamp,
                language=language,
                reason=reason,
            )
        return {
            "status": "review-validation-required",
            "reason": reason,
            "matchedRequestId": str(match["requestId"]),
            "packageId": str(match.get("packageId") or ""),
            "answeredRequestIds": [],
            "reviewDecisionIds": [],
            "clarificationCount": 0,
        }

    if kind in HIGH_RISK_NON_REVIEW_KINDS and not _has_explicit_action_and_object(text):
        return _clarification_result(
            store,
            channel=channel,
            actor=actor,
            reply_to_message_ref=reply_to_message_ref,
            inbound_message_ref=inbound_message_ref,
            reply_text=reply_text,
            received_at=timestamp,
            language=language,
            reason="high-risk-action-not-explicit",
        )

    if not text:
        return _clarification_result(
            store,
            channel=channel,
            actor=actor,
            reply_to_message_ref=reply_to_message_ref,
            inbound_message_ref=inbound_message_ref,
            reply_text=reply_text,
            received_at=timestamp,
            language=language,
            reason="empty-reply",
        )

    request_id = str(match["requestId"])
    store.mark_human_request_answered(
        request_id,
        answer_summary="Owner answered the exact referenced request.",
        answered_at=timestamp,
    )
    return {
        "status": "answered",
        "reason": "exact-open-message-ref",
        "answeredRequestIds": [request_id],
        "reviewDecisionIds": [],
        "clarificationCount": 0,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve one owner reply from stdin against one exact open human-request messageRef."
        )
    )
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reply-to-message-ref", default="")
    parser.add_argument("--inbound-message-ref", default="")
    parser.add_argument("--received-at")
    parser.add_argument("--language", choices=("en", "ru"), default="en")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    store_path = args.store.resolve()
    if not store_path.is_file():
        print(json.dumps({"status": "error", "error": "operational store does not exist"}))
        return 2

    reply_text = sys.stdin.read(MAX_REPLY_CHARS + 1)
    if len(reply_text) > MAX_REPLY_CHARS:
        print(json.dumps({"status": "error", "error": "reply exceeds safe input limit"}))
        return 2

    with OperationalStore.connect(store_path) as store:
        result = resolve_owner_reply(
            store,
            channel=args.channel,
            actor=args.actor,
            reply_to_message_ref=args.reply_to_message_ref,
            reply_text=reply_text,
            inbound_message_ref=args.inbound_message_ref,
            received_at=args.received_at,
            language=args.language,
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

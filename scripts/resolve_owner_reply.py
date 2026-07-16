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
from runtime.review_authority import (  # noqa: E402
    channels_equivalent,
    is_review_actor,
    load_review_authority,
)


MAX_REPLY_CHARS = 65_536
MIN_FORWARDED_PROMPT_CHARS = 24
REVIEW_KINDS = {"review"}
HIGH_RISK_NON_REVIEW_KINDS = {"migration", "live-proof", "source-access"}
GENERIC_ACK_RE = re.compile(
    r"^\s*(?:"
    r"yes|yep|yeah|ok|okay|all good|everything(?:'s| is)? fine|looks good|"
    r"да(?:[\s,!]+да){0,2}|ага|ок|окей|хорошо|всё ок|все ок|всё хорошо|все хорошо"
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


def _authorization_rendering(language: str) -> str:
    if language == "ru":
        return (
            "Я вижу, на какой вопрос вы ответили, но у этого участника нет "
            "права принять это изменение в данном чате. Решение не изменено."
        )
    return (
        "I can see which question this answers, but this participant is not "
        "authorized to accept that change in this chat. The decision is unchanged."
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
                "messageRef": f"pending:{request_id}",
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


def _open_requests(
    store: OperationalStore,
    *,
    channel: str,
    authority_policy: dict[str, object] | None,
    context_refs: list[dict[str, object]],
) -> list[dict[str, object]]:
    request_ids_visible_through_context = {
        str(ref.get("requestId") or "")
        for ref in context_refs
        if channels_equivalent(
            authority_policy,
            str(ref.get("channel") or ""),
            channel,
        )
    }
    return [
        request
        for request in store.list_open_human_requests(limit=10_000)
        if (
            channels_equivalent(
                authority_policy,
                str(request.get("channel") or ""),
                channel,
            )
            or str(request.get("requestId") or "")
            in request_ids_visible_through_context
        )
    ]


def _request_matches_message_ref(
    request: dict[str, object],
    *,
    channel: str,
    message_ref: str,
    authority_policy: dict[str, object] | None,
    context_refs: list[dict[str, object]],
) -> bool:
    if request.get("messageRef") == message_ref and channels_equivalent(
        authority_policy,
        str(request.get("channel") or ""),
        channel,
    ):
        return True
    request_id = str(request.get("requestId") or "")
    return any(
        ref.get("requestId") == request_id
        and ref.get("messageRef") == message_ref
        and channels_equivalent(
            authority_policy,
            str(ref.get("channel") or ""),
            channel,
        )
        for ref in context_refs
    )


def _open_match(
    store: OperationalStore,
    *,
    channel: str,
    reply_to_message_ref: str,
    authority_policy: dict[str, object] | None,
) -> tuple[dict[str, object] | None, str]:
    context_refs = store.list_human_request_context_refs(limit=10_000)
    requests = _open_requests(
        store,
        channel=channel,
        authority_policy=authority_policy,
        context_refs=context_refs,
    )
    if reply_to_message_ref:
        exact = [
            request
            for request in requests
            if _request_matches_message_ref(
                request,
                channel=channel,
                message_ref=reply_to_message_ref,
                authority_policy=authority_policy,
                context_refs=context_refs,
            )
        ]
        if len(exact) == 1:
            return exact[0], "exact-message-ref"
        if len(exact) > 1:
            return None, "duplicate-message-ref"

        pending = [
            request
            for request in requests
            if str(request.get("messageRef") or "").startswith("pending:")
        ]
        if len(pending) == 1:
            return pending[0], "provisional-message-ref"
        return None, "no-exact-open-message-ref"

    pending = [
        request
        for request in requests
        if str(request.get("messageRef") or "").startswith("pending:")
    ]
    if len(pending) == 1:
        return pending[0], "single-current-question"
    if len(pending) > 1:
        return None, "multiple-provisional-questions"
    delivered = [
        request
        for request in requests
        if request.get("kind") != "clarification"
        and str(request.get("messageRef") or "")
        and not str(request.get("messageRef") or "").startswith("pending:")
    ]
    if len(delivered) == 1:
        return delivered[0], "single-current-question"
    return None, "no-single-current-question"


def _actor_is_authorized(
    match: dict[str, object],
    *,
    actor: str,
    channel: str,
    authority_policy: dict[str, object] | None,
) -> bool:
    routed_owner = str(match.get("owner") or "unknown")
    if str(match.get("kind") or "") == "review" and authority_policy is not None:
        return is_review_actor(authority_policy, actor=actor, channel=channel)
    return routed_owner == actor


def _normalized_context_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def _matches_forwarded_prompt(forwarded_body: str, prompt: str) -> bool:
    normalized_body = _normalized_context_text(forwarded_body)
    normalized_prompt = _normalized_context_text(prompt)
    if len(normalized_prompt) < MIN_FORWARDED_PROMPT_CHARS:
        return False
    return normalized_body == normalized_prompt or normalized_body.startswith(
        normalized_prompt + " "
    )


def anchor_forwarded_question(
    store: OperationalStore,
    *,
    channel: str,
    actor: str,
    inbound_message_ref: str,
    forwarded_body: str,
    language: str = "en",
    authority_policy: dict[str, object] | None = None,
) -> dict[str, Any]:
    """Anchor one forwarded question without treating the forward as an answer."""

    message_ref = inbound_message_ref.strip()
    if not message_ref:
        return {
            "status": "context-not-matched",
            "reason": "forwarded-message-ref-missing",
            "answeredRequestIds": [],
            "reviewDecisionIds": [],
            "clarificationCount": 0,
        }
    candidates = [
        request
        for request in store.list_open_human_requests(limit=10_000)
        if request.get("kind") != "clarification"
        and _matches_forwarded_prompt(
            forwarded_body,
            str(request.get("prompt") or ""),
        )
    ]
    if len(candidates) != 1:
        return {
            "status": "context-not-matched",
            "reason": (
                "multiple-forwarded-question-matches"
                if len(candidates) > 1
                else "no-forwarded-question-match"
            ),
            "answeredRequestIds": [],
            "reviewDecisionIds": [],
            "clarificationCount": 0,
        }
    match = candidates[0]
    if not _actor_is_authorized(
        match,
        actor=actor,
        channel=channel,
        authority_policy=authority_policy,
    ):
        return {
            "status": "authorization-required",
            "reason": "actor-not-authorized",
            "matchedRequestId": str(match["requestId"]),
            "answeredRequestIds": [],
            "reviewDecisionIds": [],
            "clarificationCount": 0,
            "rendering": _authorization_rendering(language),
        }
    request_id = str(match["requestId"])
    store.record_human_request_context_ref(
        request_id,
        channel=channel,
        message_ref=message_ref,
        source="forwarded-question",
    )
    return {
        "status": "context-anchored",
        "reason": "forwarded-question-prompt",
        "matchedRequestId": request_id,
        "correlation": "forwarded-question-context-ref",
        "answeredRequestIds": [],
        "reviewDecisionIds": [],
        "clarificationCount": 0,
    }


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
    authority_policy: dict[str, object] | None = None,
) -> dict[str, Any]:
    """Resolve one reply without applying review decisions or storing raw text."""

    timestamp = received_at or _now()
    text = reply_text.strip()
    if inbound_message_ref:
        replayed_clarification = next(
            (
                request
                for request in store.list_open_human_requests(kind="clarification", limit=10_000)
                if request.get("sourceRef") == inbound_message_ref
                and request.get("owner") == actor
                and channels_equivalent(
                    authority_policy,
                    str(request.get("channel") or ""),
                    channel,
                )
            ),
            None,
        )
        if replayed_clarification is not None:
            return _clarification_result(
                store,
                channel=channel,
                actor=actor,
                reply_to_message_ref=reply_to_message_ref,
                inbound_message_ref=inbound_message_ref,
                reply_text=reply_text,
                received_at=timestamp,
                language=language,
                reason="replayed-unmatched-reply",
            )
    match, match_source = _open_match(
        store,
        channel=channel,
        reply_to_message_ref=reply_to_message_ref.strip(),
        authority_policy=authority_policy,
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
            reason=match_source,
        )

    if not _actor_is_authorized(
        match,
        actor=actor,
        channel=channel,
        authority_policy=authority_policy,
    ):
        return {
            "status": "authorization-required",
            "reason": "actor-not-authorized",
            "matchedRequestId": str(match["requestId"]),
            "answeredRequestIds": [],
            "reviewDecisionIds": [],
            "clarificationCount": 0,
            "rendering": _authorization_rendering(language),
        }

    if str(match.get("messageRef") or "").startswith("pending:") and reply_to_message_ref.strip():
        store.bind_human_request_message_ref(
            str(match["requestId"]),
            message_ref=reply_to_message_ref.strip(),
        )
        match_source = "provisional-message-ref"
        match = dict(match)
        match["messageRef"] = reply_to_message_ref.strip()

    kind = str(match.get("kind") or "")
    if kind in REVIEW_KINDS:
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
        recommendation_confirmed = bool(GENERIC_ACK_RE.fullmatch(text))
        return {
            "status": "review-validation-required",
            "reason": (
                "referenced-recommendation-confirmed"
                if recommendation_confirmed
                else "review-validation-required"
            ),
            "matchedRequestId": str(match["requestId"]),
            "packageId": str(match.get("packageId") or ""),
            "correlation": match_source,
            "recommendationConfirmed": recommendation_confirmed,
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
        "reason": match_source,
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
    parser.add_argument("--authority-policy", type=Path)
    parser.add_argument(
        "--forwarded-context-only",
        action="store_true",
        help=(
            "Treat stdin as one forwarded question to anchor, not as an answer. "
            "Requires --inbound-message-ref."
        ),
    )
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

    authority_policy = None
    if args.authority_policy is not None:
        try:
            authority_policy = load_review_authority(args.authority_policy.resolve())
        except ValueError as exc:
            print(json.dumps({"status": "error", "error": str(exc)}))
            return 2

    with OperationalStore.connect(store_path) as store:
        store.initialize()
        if args.forwarded_context_only:
            result = anchor_forwarded_question(
                store,
                channel=args.channel,
                actor=args.actor,
                inbound_message_ref=args.inbound_message_ref,
                forwarded_body=reply_text,
                language=args.language,
                authority_policy=authority_policy,
            )
        else:
            result = resolve_owner_reply(
                store,
                channel=args.channel,
                actor=args.actor,
                reply_to_message_ref=args.reply_to_message_ref,
                reply_text=reply_text,
                inbound_message_ref=args.inbound_message_ref,
                received_at=args.received_at,
                language=args.language,
                authority_policy=authority_policy,
            )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

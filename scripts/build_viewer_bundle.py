#!/usr/bin/env python3
"""Compile an accepted ontology export into one JSON bundle for the viewer.

The viewer (`viewer/index.html`) reads a single `ontology.json` file: cards with
their frontmatter, body sections, and typed links, plus derived edges, the
source map, open questions, and health counts. This generator produces that file
from a Markdown/Git model export, reusing the repository's own dependency-free
frontmatter parser so the viewer never disagrees with the validator.

It is read-only: it never writes to the model, promotes anything, or contacts a
source. It only projects accepted cards into a shape a browser can render.

Usage:
    python3 scripts/build_viewer_bundle.py <model-root> --out viewer/ontology.json
    python3 scripts/build_viewer_bundle.py <model-root> --out viewer/ontology.json \
        --module acquisition --revision git:abc123 --as-of 2026-06-30
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import sys
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from links_validate import (  # noqa: E402
    FRONTMATTER_RE,
    CARD_TYPES,
    looks_like_card,
    normalize_links,
    parse_frontmatter_block,
)

SKIP_DIRS = {".git", "node_modules", "__pycache__", "staged", "registry", "viewer"}
UNKNOWN_OWNER = {"", "unknown", "not applicable", "n/a", "none", "unassigned"}
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
REVIEW_ITEM_LIMIT = 80
REVIEW_TEXT_LIMIT = 320
HUMAN_REQUEST_LIMIT = 50
REVIEW_KIND_ORDER = {
    "human-request": 0,
    "source-gap": 1,
    "drift": 2,
    "open-question": 3,
    "stale-audit": 4,
    "status-risk": 5,
}
REVIEW_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _split_sections(body: str) -> tuple[str, list[dict]]:
    title = ""
    sections: list[dict] = []
    current = None
    for line in body.splitlines():
        heading = HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            text = heading.group(2).strip()
            if level == 1 and not title:
                title = text
                continue
            if current:
                current["body"] = current["body"].strip()
                sections.append(current)
            current = {"heading": text, "body": ""}
            continue
        if current is not None:
            current["body"] += line + "\n"
    if current:
        current["body"] = current["body"].strip()
        sections.append(current)
    return title, sections


def _scalar(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _bounded_text(value: Any, limit: int = REVIEW_TEXT_LIMIT) -> str:
    text = _scalar(value)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _string_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in (_scalar(v) for v in value) if item]
    text = _scalar(value)
    return [text] if text else []


def _human_request_value(request: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = request.get(key)
        if value is not None:
            return _scalar(value)
    return ""


def _human_request_projection(request: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(request, dict):
        return None
    request_id = _human_request_value(request, "requestId", "request_id")
    if not request_id:
        return None
    status = _human_request_value(request, "status") or "open"
    if status not in {"open", "deferred"}:
        return None
    projected = {
        "requestId": request_id,
        "kind": _human_request_value(request, "kind") or "clarification",
        "status": status,
        "owner": _human_request_value(request, "owner") or "unknown",
        "channel": _human_request_value(request, "channel") or "unknown",
        "messageRef": _human_request_value(request, "messageRef", "message_ref"),
        "prompt": _bounded_text(_human_request_value(request, "prompt"), 700),
        "recommendedAnswer": _bounded_text(
            _human_request_value(request, "recommendedAnswer", "recommended_answer", "recommendation"),
            700,
        ),
        "blocks": _string_list(request.get("blocks")),
        "sourceRef": _human_request_value(request, "sourceRef", "source_ref"),
        "packageId": _human_request_value(request, "packageId", "package_id"),
        "askedAt": _human_request_value(request, "askedAt", "asked_at"),
        "dueAt": _human_request_value(request, "dueAt", "due_at"),
    }
    return {key: value for key, value in projected.items() if value not in ("", [], None)}


def _human_request_projections(requests: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for request in requests or []:
        item = _human_request_projection(request)
        if item is not None:
            projected.append(item)
        if len(projected) >= HUMAN_REQUEST_LIMIT:
            break
    return projected


def _is_ru(language: str | None) -> bool:
    normalized = _scalar(language).strip().lower()
    return normalized.startswith("ru") or "рус" in normalized or normalized == "russian"


def _review_phrase(language: str | None, key: str, **values: str) -> str:
    ru = _is_ru(language)
    if key == "global_question_action":
        return (
            "Проверить общий журнал drift/open questions и решить, нужен ли model-change package."
            if ru
            else "Review the global drift/open-questions ledger and decide whether a model-change package is needed."
        )
    if key == "card_question_action":
        return (
            "Открыть карточку, проверить нерешённый пункт, затем подготовить пакет изменений или явно отложить."
            if ru
            else "Open the card, verify the unresolved point, then stage a package or keep it explicitly deferred."
        )
    if key == "no_source_text":
        return (
            f"У карточки {values['card_id']} не разрешён source."
            if ru
            else f"Card {values['card_id']} has no resolved source."
        )
    if key == "no_source_action":
        return (
            "Добавить или исправить source карточки до того, как полагаться на этот факт."
            if ru
            else "Add or correct the card source before relying on this accepted fact."
        )
    if key == "missing_source_text":
        return (
            f"Карточка {values['card_id']} ссылается на source {values['source_id']}, но его нет в 02-source-map.md."
            if ru
            else f"Card {values['card_id']} references source {values['source_id']}, but that source is not in 02-source-map.md."
        )
    if key == "missing_source_action":
        return (
            "Зарегистрировать source или исправить source id в карточке."
            if ru
            else "Register the source or fix the card source id."
        )
    if key == "failed_source_text":
        return (
            f"Источник {values['source_id']} имеет failed readiness."
            if ru
            else f"Source {values['source_id']} has failed readiness."
        )
    if key == "failed_source_action":
        return (
            "Починить подключение источника или пометить зависимые свидетельства как устаревшие."
            if ru
            else "Fix the source connection or mark dependent evidence stale before trusting live-currentness."
        )
    if key == "stale_audit_text":
        return (
            f"Аудит карточки {values['card_id']} просрочен: {values['next_audit']} раньше {values['as_of']}."
            if ru
            else f"Card {values['card_id']} audit date {values['next_audit']} is before {values['as_of']}."
        )
    if key == "stale_audit_action":
        return (
            "Перепроверить карточку по источнику и обновить audit state через review."
            if ru
            else "Re-check the card against its source and update audit state through review."
        )
    if key == "human_request_text":
        prompt = values.get("prompt") or values["request_id"]
        recommendation = values.get("recommended_answer") or ""
        if ru:
            return f"{prompt} Рекомендация: {recommendation}" if recommendation else prompt
        return f"{prompt} Recommendation: {recommendation}" if recommendation else prompt
    if key == "human_request_action":
        return (
            "Ответить, отложить или заменить запрос; viewer только показывает незакрытую работу."
            if ru
            else "Answer, defer, or supersede the request; the viewer only shows the unresolved work."
        )
    if key == "human_request_aggregate_text":
        count = values["count"]
        return (
            f"Открыто запросов к человеку: {count}."
            if ru
            else f"{count} human request(s) are still open."
        )
    if key == "human_request_aggregate_action":
        return (
            "Ответить, отложить или заменить открытые запросы до вывода, что модель полностью актуальна."
            if ru
            else "Answer, defer, or supersede open requests before treating the model as fully current."
        )
    if key == "status_risk_text":
        return (
            f"Карточка {values['card_id']} имеет статус {values['status']}, не accepted."
            if ru
            else f"Card {values['card_id']} status is {values['status']}, not accepted."
        )
    if key == "status_risk_action":
        return (
            "Разобрать статус карточки до использования как принятой бизнес-истины."
            if ru
            else "Resolve this card before using it as accepted business truth."
        )
    raise KeyError(key)


def _flatten_search_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        parts: list[str] = []
        for key in sorted(value):
            parts.append(_scalar(key))
            parts.extend(_flatten_search_value(value[key]))
        return parts
    if isinstance(value, list):
        parts = []
        for item in value:
            parts.extend(_flatten_search_value(item))
        return parts
    return [_scalar(value)]


def _card_search_text(card: dict) -> str:
    parts: list[str] = []
    for key in (
        "id",
        "type",
        "status",
        "source",
        "owner",
        "lastReviewed",
        "nextAudit",
        "volatility",
        "title",
        "file",
    ):
        parts.append(_scalar(card.get(key)))
    parts.extend(_string_list(card.get("evidence")))
    parts.extend(_string_list(card.get("aliases")))
    for section in card.get("sections") or []:
        if isinstance(section, dict):
            parts.append(_scalar(section.get("heading")))
            parts.append(_scalar(section.get("body")))
    parts.extend(_flatten_search_value(card.get("attrs")))
    parts.extend(_flatten_search_value(card.get("links")))
    return _bounded_text(" ".join(part for part in parts if part), 20_000)


def _card_from_file(path: Path, root: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    parsed = parse_frontmatter_block(text, str(path))
    if parsed is None:
        return None
    data = parsed.data
    if not isinstance(data, dict) or not looks_like_card(data):
        return None
    if data.get("type") not in CARD_TYPES:
        return None
    body = text[match.end():]
    title, sections = _split_sections(body)
    links = normalize_links(data.get("links"), str(path), [])
    attrs = data.get("attrs") if isinstance(data.get("attrs"), dict) else {}
    return {
        "id": _scalar(data.get("id")),
        "type": _scalar(data.get("type")),
        "status": _scalar(data.get("status")),
        "source": _scalar(data.get("source")),
        "owner": _scalar(data.get("owner")),
        "lastReviewed": _scalar(data.get("last-reviewed")),
        "nextAudit": _scalar(data.get("next-audit")),
        "volatility": _scalar(data.get("volatility")),
        "evidence": _string_list(data.get("evidence")),
        "aliases": _string_list(data.get("aliases")),
        "attrs": attrs,
        "links": {rel: list(targets) for rel, targets in links.items()},
        "title": title or _scalar(data.get("id")),
        "sections": sections,
        "file": str(path.relative_to(root)),
    }


def _stage_rows(card: dict, cards_by_id: dict[str, dict]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    stages = card.get("attrs", {}).get("stages")
    if not isinstance(stages, list):
        return rows
    for index, raw in enumerate(stages):
        if isinstance(raw, dict):
            state = _scalar(raw.get("state") or raw.get("id"))
            row_id = _scalar(raw.get("id")) or f"{card['id']}-stage-{index + 1}"
            state_card = cards_by_id.get(state)
            label = _scalar(raw.get("label")) or (state_card or {}).get("title") or state or row_id
            row = {
                "id": row_id,
                "state": state,
                "label": label,
                "processes": _string_list(raw.get("processes")),
                "roles": _string_list(raw.get("roles")),
            }
        else:
            state = _scalar(raw)
            state_card = cards_by_id.get(state)
            row = {
                "id": state,
                "state": state,
                "label": (state_card or {}).get("title") or state,
                "processes": [],
                "roles": [],
            }
        if row["id"]:
            rows.append(row)
    return rows


def _step_id(raw: Any, index: int) -> str:
    if isinstance(raw, dict):
        return _scalar(raw.get("id")) or f"step-{index + 1}"
    return _scalar(raw) or f"step-{index + 1}"


def _process_steps(card: dict) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    steps = card.get("attrs", {}).get("steps")
    if not isinstance(steps, list):
        return rows
    for index, raw in enumerate(steps):
        if not isinstance(raw, dict):
            sid = _step_id(raw, index)
            rows.append(
                {
                    "id": sid,
                    "label": sid,
                    "shape": "start" if index == 0 else "rect",
                }
            )
            continue
        sid = _step_id(raw, index)
        decision = raw.get("decision") if isinstance(raw.get("decision"), dict) else {}
        yes = _scalar(raw.get("yes") or decision.get("yes"))
        no = _scalar(raw.get("no") or decision.get("no"))
        next_step = _scalar(raw.get("next"))
        shape = _scalar(raw.get("shape"))
        if not shape:
            is_decision = raw.get("type") == "decision" or bool(decision) or bool(yes or no)
            shape = "diamond" if is_decision else ("start" if index == 0 else "rect")
        activity = _scalar(raw.get("does"))
        decision_question = _scalar(decision.get("question"))
        row: dict[str, Any] = {
            "id": sid,
            "label": _scalar(decision_question or raw.get("text") or raw.get("label") or activity or sid),
            "shape": shape,
        }
        if activity and activity != row["label"]:
            row["activity"] = activity
        for key in ("role", "input", "output", "rule"):
            value = _scalar(raw.get(key))
            if value:
                row[key] = value
        if raw.get("warn"):
            row["warn"] = True
        if yes:
            row["yes"] = yes
        if no:
            row["no"] = no
        if next_step:
            row["next"] = next_step
        rows.append(row)
    return rows


def _production_system_ids_for_business(card: dict, cards: list[dict], cards_by_id: dict[str, dict]) -> list[str]:
    ids: list[str] = []

    def add(candidate: str) -> None:
        target = cards_by_id.get(candidate)
        if target and target.get("type") == "production-system" and candidate not in ids:
            ids.append(candidate)

    for candidate in card.get("links", {}).get("owns", []):
        add(candidate)
    for other in cards:
        if other.get("type") != "production-system":
            continue
        links = other.get("links", {})
        attrs = other.get("attrs", {})
        if card["id"] in links.get("part-of", []) or attrs.get("business") == card["id"]:
            add(other["id"])
    return ids


def _interface_ids_for_business(card: dict, cards: list[dict], participant_key: str) -> list[str]:
    ids: list[str] = []
    for other in cards:
        if other.get("type") != "interface":
            continue
        participants = other.get("attrs", {}).get("participants")
        if not isinstance(participants, dict):
            continue
        if card["id"] in _string_list(participants.get(participant_key)):
            ids.append(other["id"])
    return ids


def _ids_with_type(cards_by_id: dict[str, dict], ids: list[str], expected_type: str) -> list[str]:
    return [card_id for card_id in ids if _type_of(cards_by_id, card_id) == expected_type]


def _attach_viewer_projection(cards: list[dict]) -> None:
    cards_by_id = {card["id"]: card for card in cards}
    for card in cards:
        viewer: dict[str, Any] = {}
        if card["type"] == "production-system":
            viewer["stages"] = _stage_rows(card, cards_by_id)
        elif card["type"] == "process":
            viewer["processSteps"] = _process_steps(card)
        elif card["type"] == "business":
            links = card.get("links", {})
            viewer["productionSystems"] = _production_system_ids_for_business(card, cards, cards_by_id)
            viewer["inputArtifacts"] = _ids_with_type(cards_by_id, _string_list(links.get("consumes")), "artifact")
            viewer["outputArtifacts"] = _string_list(links.get("produces"))
            viewer["inboundInterfaces"] = _interface_ids_for_business(card, cards, "customer")
            viewer["outboundInterfaces"] = _interface_ids_for_business(card, cards, "supplier")
        if viewer:
            card["viewer"] = viewer


def _type_of(cards_by_id: dict[str, dict], card_id: str) -> str:
    card = cards_by_id.get(card_id)
    return _scalar(card.get("type")) if card else "missing"


def _looks_like_card_id(value: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9]*-[A-Za-z0-9_-]+$", value))


def _expect_card_type(
    diagnostics: list[dict[str, str]],
    cards_by_id: dict[str, dict],
    *,
    owner: dict,
    field: str,
    target_id: str,
    expected_type: str,
) -> None:
    if not target_id:
        return
    actual_type = _type_of(cards_by_id, target_id)
    if actual_type != expected_type:
        diagnostics.append(
            {
                "card_id": owner["id"],
                "card_type": owner["type"],
                "field": field,
                "target_id": target_id,
                "expected_type": expected_type,
                "actual_type": actual_type,
            }
        )


def viewer_projection_diagnostics(cards: list[dict]) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    cards_by_id = {card["id"]: card for card in cards}
    for card in cards:
        viewer = card.get("viewer") if isinstance(card.get("viewer"), dict) else {}
        if card["type"] == "business":
            for target_id in _string_list(viewer.get("productionSystems")):
                _expect_card_type(
                    diagnostics,
                    cards_by_id,
                    owner=card,
                    field="viewer.productionSystems",
                    target_id=target_id,
                    expected_type="production-system",
                )
            for field in ("inputArtifacts", "outputArtifacts"):
                for target_id in _string_list(viewer.get(field)):
                    _expect_card_type(
                        diagnostics,
                        cards_by_id,
                        owner=card,
                        field=f"viewer.{field}",
                        target_id=target_id,
                        expected_type="artifact",
                    )
        elif card["type"] == "production-system":
            for stage in viewer.get("stages") or []:
                if not isinstance(stage, dict):
                    continue
                stage_id = _scalar(stage.get("id"))
                _expect_card_type(
                    diagnostics,
                    cards_by_id,
                    owner=card,
                    field=f"viewer.stages[{stage_id}].state",
                    target_id=_scalar(stage.get("state")),
                    expected_type="state",
                )
                for target_id in _string_list(stage.get("processes")):
                    _expect_card_type(
                        diagnostics,
                        cards_by_id,
                        owner=card,
                        field=f"viewer.stages[{stage_id}].processes",
                        target_id=target_id,
                        expected_type="process",
                    )
                for target_id in _string_list(stage.get("roles")):
                    _expect_card_type(
                        diagnostics,
                        cards_by_id,
                        owner=card,
                        field=f"viewer.stages[{stage_id}].roles",
                        target_id=target_id,
                        expected_type="role",
                    )
        elif card["type"] == "process":
            steps = [step for step in viewer.get("processSteps") or [] if isinstance(step, dict)]
            step_ids = {_scalar(step.get("id")) for step in steps}
            for step in steps:
                step_id = _scalar(step.get("id"))
                for field in ("next", "yes", "no"):
                    target_id = _scalar(step.get(field))
                    if target_id and target_id not in step_ids:
                        diagnostics.append(
                            {
                                "card_id": card["id"],
                                "card_type": card["type"],
                                "field": f"viewer.processSteps[{step_id}].{field}",
                                "target_id": target_id,
                                "expected_type": "process-step",
                                "actual_type": "missing",
                            }
                        )
                _expect_card_type(
                    diagnostics,
                    cards_by_id,
                    owner=card,
                    field=f"viewer.processSteps[{step_id}].role",
                    target_id=_scalar(step.get("role")),
                    expected_type="role",
                )
        elif card["type"] == "state":
            transitions = card.get("attrs", {}).get("transitions")
            if not isinstance(transitions, list):
                continue
            for index, transition in enumerate(transitions):
                if not isinstance(transition, dict):
                    continue
                authority = _scalar(transition.get("authority"))
                if not authority or not _looks_like_card_id(authority):
                    continue
                actual_type = _type_of(cards_by_id, authority)
                if actual_type not in {"role", "decision"}:
                    diagnostics.append(
                        {
                            "card_id": card["id"],
                            "card_type": card["type"],
                            "field": f"viewer.transitions[{index}].authority",
                            "target_id": authority,
                            "expected_type": "role|decision",
                            "actual_type": actual_type,
                        }
                    )
    return diagnostics


def _read_source_map(root: Path) -> list[dict]:
    path = root / "02-source-map.md"
    if not path.exists():
        return []
    rows: list[dict] = []
    seen_header = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        joined = " ".join(cells).lower()
        if "source id" in joined:
            seen_header = True
            continue
        if not seen_header or set("".join(cells)) <= {"-", ":", " "}:
            continue
        cells += [""] * (6 - len(cells))
        rows.append(
            {
                "id": cells[0].strip("`"),
                "trust": cells[1],
                "owner": cells[2],
                "accessMode": cells[3],
                "readPolicy": cells[4],
                "meaning": cells[5],
            }
        )
    return rows


def _read_open_questions(root: Path) -> list[str]:
    path = root / "08-drift-and-open-questions.md"
    if not path.exists():
        return []
    items: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            items.append(stripped[2:].strip())
    return items


def _review_section_kind(heading: str) -> str | None:
    normalized = re.sub(r"[^a-zа-яё ]+", " ", heading.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if "drift" in normalized or "дрейф" in normalized:
        return "drift"
    if "open question" in normalized or ("открыт" in normalized and "вопрос" in normalized):
        return "open-question"
    return None


def _add_review_item(
    items: list[dict[str, str]],
    seen: set[tuple[str, str, str, str, str]],
    *,
    kind: str,
    severity: str,
    text: str,
    action: str,
    card_id: str = "",
    source_id: str = "",
    owner: str = "unknown",
    request_id: str = "",
    package_id: str = "",
    message_ref: str = "",
    due_at: str = "",
) -> None:
    safe_text = _bounded_text(text)
    if not safe_text:
        return
    item = {
        "kind": kind,
        "severity": severity if severity in REVIEW_SEVERITY_ORDER else "medium",
        "owner": owner or "unknown",
        "text": safe_text,
        "action": _bounded_text(action, 220),
    }
    if card_id:
        item["cardId"] = card_id
    if source_id:
        item["sourceId"] = source_id
    if request_id:
        item["requestId"] = request_id
    if package_id:
        item["packageId"] = package_id
    if message_ref:
        item["messageRef"] = message_ref
    if due_at:
        item["dueAt"] = due_at
    key = (
        item["kind"],
        item.get("cardId", ""),
        item.get("sourceId", ""),
        item.get("requestId", ""),
        item["text"],
    )
    if key not in seen:
        seen.add(key)
        items.append(item)


def _review_items(
    cards: list[dict],
    sources: list[dict],
    source_readiness: dict[str, Any],
    *,
    as_of: str | None,
    open_questions: list[str],
    open_human_request_count: int,
    open_human_requests: list[dict[str, Any]],
    company_model_language: str,
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    source_by_id = {source["id"]: source for source in sources}

    for text in open_questions:
        _add_review_item(
            items,
            seen,
            kind="open-question",
            severity="medium",
            owner="unknown",
            text=text,
            action=_review_phrase(company_model_language, "global_question_action"),
        )

    for card in cards:
        for section in card.get("sections") or []:
            if not isinstance(section, dict):
                continue
            kind = _review_section_kind(_scalar(section.get("heading")))
            if not kind:
                continue
            _add_review_item(
                items,
                seen,
                kind=kind,
                severity="medium" if kind == "open-question" else "high",
                card_id=card["id"],
                owner=card.get("owner") or "unknown",
                text=section.get("body") or section.get("heading"),
                action=_review_phrase(company_model_language, "card_question_action"),
            )

    for card in cards:
        source_id = _scalar(card.get("source"))
        if not source_id or source_id.lower() == "unknown":
            _add_review_item(
                items,
                seen,
                kind="source-gap",
                severity="high",
                card_id=card["id"],
                owner=card.get("owner") or "unknown",
                text=_review_phrase(company_model_language, "no_source_text", card_id=card["id"]),
                action=_review_phrase(company_model_language, "no_source_action"),
            )
        elif source_id not in source_by_id:
            _add_review_item(
                items,
                seen,
                kind="source-gap",
                severity="high",
                card_id=card["id"],
                source_id=source_id,
                owner=card.get("owner") or "unknown",
                text=_review_phrase(
                    company_model_language,
                    "missing_source_text",
                    card_id=card["id"],
                    source_id=source_id,
                ),
                action=_review_phrase(company_model_language, "missing_source_action"),
            )

    by_status = source_readiness.get("sourceInstanceIdsByStatus")
    if isinstance(by_status, dict):
        for source_id in _string_list(by_status.get("failed")):
            source = source_by_id.get(source_id, {})
            _add_review_item(
                items,
                seen,
                kind="source-gap",
                severity="high",
                source_id=source_id,
                owner=_scalar(source.get("owner")) or "unknown",
                text=_review_phrase(company_model_language, "failed_source_text", source_id=source_id),
                action=_review_phrase(company_model_language, "failed_source_action"),
            )

    if as_of:
        for card in cards:
            next_audit = _scalar(card.get("nextAudit"))
            if next_audit and next_audit < as_of:
                _add_review_item(
                    items,
                    seen,
                    kind="stale-audit",
                    severity="high" if card.get("volatility") == "high" else "medium",
                    card_id=card["id"],
                    owner=card.get("owner") or "unknown",
                    text=_review_phrase(
                        company_model_language,
                        "stale_audit_text",
                        card_id=card["id"],
                        next_audit=next_audit,
                        as_of=as_of,
                    ),
                    action=_review_phrase(company_model_language, "stale_audit_action"),
                )

    for request in open_human_requests:
        _add_review_item(
            items,
            seen,
            kind="human-request",
            severity="high",
            owner=_scalar(request.get("owner")) or "owner",
            text=_review_phrase(
                company_model_language,
                "human_request_text",
                request_id=_scalar(request.get("requestId")),
                prompt=_scalar(request.get("prompt")),
                recommended_answer=_scalar(request.get("recommendedAnswer")),
            ),
            action=_review_phrase(company_model_language, "human_request_action"),
            request_id=_scalar(request.get("requestId")),
            package_id=_scalar(request.get("packageId")),
            message_ref=_scalar(request.get("messageRef")),
            due_at=_scalar(request.get("dueAt")),
        )

    hidden_human_request_count = max(0, open_human_request_count - len(open_human_requests))
    if hidden_human_request_count > 0:
        _add_review_item(
            items,
            seen,
            kind="human-request",
            severity="high",
            owner="owner",
            text=_review_phrase(
                company_model_language,
                "human_request_aggregate_text",
                count=str(hidden_human_request_count),
            ),
            action=_review_phrase(company_model_language, "human_request_aggregate_action"),
        )

    for card in cards:
        status = _scalar(card.get("status"))
        if status and status not in {"accepted", "implemented"}:
            _add_review_item(
                items,
                seen,
                kind="status-risk",
                severity="high" if status == "conflict" else "medium",
                card_id=card["id"],
                owner=card.get("owner") or "unknown",
                text=_review_phrase(
                    company_model_language,
                    "status_risk_text",
                    card_id=card["id"],
                    status=status,
                ),
                action=_review_phrase(company_model_language, "status_risk_action"),
            )

    return sorted(
        items,
        key=lambda item: (
            REVIEW_SEVERITY_ORDER.get(item["severity"], 9),
            REVIEW_KIND_ORDER.get(item["kind"], 9),
            item.get("cardId", ""),
            item.get("sourceId", ""),
            item["text"],
        ),
    )[:REVIEW_ITEM_LIMIT]


def _source_gap_card_ids(cards: list[dict], sources: list[dict]) -> tuple[list[str], list[str]]:
    source_ids = {s["id"] for s in sources}
    unresolved: list[str] = []
    unknown: list[str] = []
    for card in cards:
        source = _scalar(card.get("source"))
        if not source or source.lower() == "unknown":
            unknown.append(card["id"])
            unresolved.append(card["id"])
        elif source not in source_ids:
            unresolved.append(card["id"])
    return unresolved, unknown


def _source_readiness_status(source_id: str, source_readiness: dict[str, Any]) -> str:
    by_status = source_readiness.get("sourceInstanceIdsByStatus")
    if not isinstance(by_status, dict):
        return "unknown"
    for status in ("failed", "live-proven", "scheduled", "source-connected", "configured"):
        if source_id in _string_list(by_status.get(status)):
            return status
    return "unknown"


def _source_trust_projection(
    cards: list[dict],
    sources: list[dict],
    source_readiness: dict[str, Any],
) -> dict[str, Any]:
    cards_by_source: dict[str, list[str]] = {}
    for card in cards:
        source = _scalar(card.get("source")) or "unknown"
        cards_by_source.setdefault(source, []).append(card["id"])
    unresolved, unknown = _source_gap_card_ids(cards, sources)
    proof_by_source = source_readiness.get("lastProofIdsBySource")
    if not isinstance(proof_by_source, dict):
        proof_by_source = {}
    projected_sources = []
    for source in sources:
        source_id = source["id"]
        dependent_ids = sorted(cards_by_source.get(source_id, []))
        projected_sources.append(
            {
                **source,
                "dependentCardIds": dependent_ids,
                "dependentCardCount": len(dependent_ids),
                "readinessStatus": _source_readiness_status(source_id, source_readiness),
                "lastProofId": _scalar(proof_by_source.get(source_id)),
            }
        )
    return {
        "sources": projected_sources,
        "cardsBySource": {key: sorted(value) for key, value in sorted(cards_by_source.items())},
        "unresolvedSourceCardIds": unresolved,
        "unknownSourceCardIds": unknown,
    }


def _health(cards: list[dict], sources: list[dict], as_of: str | None) -> dict:
    counts: dict[str, int] = {}
    for card in cards:
        counts[card["status"]] = counts.get(card["status"], 0) + 1
    total = len(cards) or 1
    owned = sum(1 for c in cards if c["owner"].lower() not in UNKNOWN_OWNER)
    unresolved, unknown = _source_gap_card_ids(cards, sources)
    sourced = len(cards) - len(unresolved)
    stale = None
    if as_of:
        stale = sum(
            1 for c in cards if c["nextAudit"] and c["nextAudit"] < as_of
        )
    return {
        "total": len(cards),
        "byStatus": counts,
        "ownerCoveragePct": round(100 * owned / total),
        "sourceResolvedPct": round(100 * sourced / total),
        "unresolvedSourceCardIds": unresolved,
        "unknownSourceCardIds": unknown,
        "stalePastNextAudit": stale,
        "conflicts": counts.get("conflict", 0),
        "hypotheses": counts.get("hypothesis", 0),
    }


def empty_source_readiness() -> dict[str, Any]:
    return {
        "configuredCount": 0,
        "sourceConnectedCount": 0,
        "liveProvenCount": 0,
        "scheduledCount": 0,
        "failedCount": 0,
        "sourceInstanceIdsByStatus": {
            "configured": [],
            "source-connected": [],
            "live-proven": [],
            "scheduled": [],
            "failed": [],
        },
        "lastProofIdsBySource": {},
    }


def build_bundle(
    root: Path,
    module: str,
    revision: str,
    as_of: str | None,
    *,
    company_model_language: str = "pending-owner-selection",
    package_version: str = "unknown",
    package_commit: str = "unknown",
    model_revision: str | None = None,
    source_readiness: dict[str, Any] | None = None,
    open_human_request_count: int = 0,
    open_human_requests: list[dict[str, Any]] | None = None,
    validation_status: str = "not-run",
) -> dict:
    cards: list[dict] = []
    for path in sorted(root.rglob("*.md")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        card = _card_from_file(path, root)
        if card:
            cards.append(card)
    cards.sort(key=lambda c: (c["type"], c["id"]))
    _attach_viewer_projection(cards)
    for card in cards:
        card["searchText"] = _card_search_text(card)
    diagnostics = viewer_projection_diagnostics(cards)
    edges = [
        {"from": c["id"], "to": target, "type": rel}
        for c in cards
        for rel, targets in c["links"].items()
        for target in targets
    ]
    sources = _read_source_map(root)
    source_readiness_value = source_readiness or empty_source_readiness()
    open_questions = _read_open_questions(root)
    open_human_request_items = _human_request_projections(open_human_requests)
    effective_open_human_request_count = max(open_human_request_count, len(open_human_request_items))
    return {
        "module": module,
        "companyModelLanguage": company_model_language,
        "packageVersion": package_version,
        "packageCommit": package_commit,
        "modelRevision": model_revision or revision,
        "sourceReadiness": source_readiness_value,
        "sourceTrust": _source_trust_projection(cards, sources, source_readiness_value),
        "openHumanRequestCount": effective_open_human_request_count,
        "openHumanRequests": open_human_request_items,
        "validationStatus": validation_status,
        "revision": revision,
        "asOf": as_of or "",
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cards": cards,
        "viewerDiagnostics": diagnostics,
        "edges": edges,
        "sources": sources,
        "openQuestions": open_questions,
        "reviewItems": _review_items(
            cards,
            sources,
            source_readiness_value,
            as_of=as_of,
            open_questions=open_questions,
            open_human_request_count=effective_open_human_request_count,
            open_human_requests=open_human_request_items,
            company_model_language=company_model_language,
        ),
        "health": _health(cards, sources, as_of),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Compile an ontology export for the viewer.")
    parser.add_argument("root", help="model export root (folder with the cards)")
    parser.add_argument("--out", default="viewer/ontology.json", help="output JSON path")
    parser.add_argument("--module", default=None, help="module id (defaults to root folder name)")
    parser.add_argument("--revision", default="local-export", help="revision label to display")
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD to compute stale-audit count")
    parser.add_argument(
        "--company-model-language",
        default="pending-owner-selection",
        help="Language code selected by the owner for human-facing model text.",
    )
    parser.add_argument("--package-version", default="unknown", help="Installed package version.")
    parser.add_argument("--package-commit", default="unknown", help="Installed package commit.")
    parser.add_argument("--model-revision", default=None, help="Accepted model revision.")
    parser.add_argument(
        "--source-readiness-json",
        default=None,
        help="Path to source readiness JSON metadata.",
    )
    parser.add_argument(
        "--open-human-request-count",
        type=int,
        default=0,
        help="Open human requests count for this workspace.",
    )
    parser.add_argument(
        "--open-human-requests-json",
        default=None,
        help="Path to a JSON file with human_requests or a list of open human request envelopes.",
    )
    parser.add_argument("--validation-status", default="not-run", help="Model validation status.")
    args = parser.parse_args(argv[1:])

    root = Path(args.root).resolve()
    module = args.module or root.name
    source_readiness = None
    if args.source_readiness_json:
        source_readiness = json.loads(Path(args.source_readiness_json).read_text(encoding="utf-8"))
    open_human_requests = None
    if args.open_human_requests_json:
        data = json.loads(Path(args.open_human_requests_json).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            value = data.get("human_requests")
            open_human_requests = value if isinstance(value, list) else []
        elif isinstance(data, list):
            open_human_requests = data
        else:
            open_human_requests = []
    bundle = build_bundle(
        root,
        module,
        args.revision,
        args.as_of,
        company_model_language=args.company_model_language,
        package_version=args.package_version,
        package_commit=args.package_commit,
        model_revision=args.model_revision,
        source_readiness=source_readiness,
        open_human_request_count=args.open_human_request_count,
        open_human_requests=open_human_requests,
        validation_status=args.validation_status,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"viewer bundle: {len(bundle['cards'])} cards, {len(bundle['edges'])} edges, "
        f"{len(bundle['sources'])} sources -> {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

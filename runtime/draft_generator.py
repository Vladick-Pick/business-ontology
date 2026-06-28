#!/usr/bin/env python3
"""Generate a reviewable draft ontology from model packs and source events."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from runtime.model_compiler import CompilerRefusal, compile_model_change


def generate_draft_ontology(
    *,
    model_pack: dict[str, object],
    source_events: list[dict[str, object]],
    accepted_context: dict[str, object] | None = None,
) -> dict[str, object]:
    """Compile source events into bounded review packages and binding suggestions.

    The draft is review material. It never marks generated model content as
    accepted and never mutates accepted model state.
    """

    accepted_context = accepted_context or {}
    packages: list[dict[str, object]] = []
    refusals: list[dict[str, object]] = []
    for source_event in source_events:
        event_id = str(source_event.get("eventId") or "unknown")
        try:
            package = compile_model_change(
                model_pack=model_pack,
                source_event=source_event,
                accepted_context=accepted_context,
            )
        except CompilerRefusal as exc:
            refusals.append({"eventId": event_id, "reason": str(exc)})
            continue
        packages.append(package)

    binding_suggestions = _binding_suggestions(packages, source_events)
    return {
        "kind": "draftOntology",
        "moduleId": _required_str(model_pack, "moduleId"),
        "modelPackId": _required_str(model_pack, "modelPackId"),
        "modelPackVersion": _required_str(model_pack, "version"),
        "generatedAt": str(
            accepted_context.get("generatedAt")
            or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        ),
        "status": _draft_status(packages, refusals),
        "summary": {
            "sourceEventCount": len(source_events),
            "packageCount": len(packages),
            "bindingSuggestionCount": len(binding_suggestions),
            "refusalCount": len(refusals),
        },
        "packages": packages,
        "bindingSuggestions": binding_suggestions,
        "refusals": refusals,
        "safety": {
            "noAcceptedMutation": True,
            "noRawPayload": True,
            "reviewRequired": True,
        },
    }


def _binding_suggestions(
    packages: list[dict[str, object]],
    source_events: list[dict[str, object]],
) -> list[dict[str, object]]:
    event_map = {
        str(event.get("eventId")): event
        for event in source_events
        if isinstance(event.get("eventId"), str)
    }
    suggestions: list[dict[str, object]] = []
    seen: set[str] = set()
    for package in packages:
        for change in _mapping_list(package.get("changes")):
            card = change.get("candidateCard")
            if not isinstance(card, dict):
                continue
            item_id = _required_str(card, "id")
            property_name = _suggested_property_name(card)
            for evidence in _mapping_list(change.get("evidence")):
                source_event_id = _required_str(evidence, "sourceEventId")
                source_event = event_map.get(source_event_id, {})
                source_id = str(source_event.get("sourceId") or card.get("source") or "unknown")
                suggestion_id = f"bind-suggest-{item_id}-{_slug(source_event_id)}-{property_name}"
                if suggestion_id in seen:
                    continue
                seen.add(suggestion_id)
                suggestions.append(
                    {
                        "binding_id": suggestion_id,
                        "item_id": item_id,
                        "property_name": property_name,
                        "source_id": source_id,
                        "source_kind": str(source_event.get("sourceKind") or "unknown"),
                        "source_locator": _required_str(evidence, "locator"),
                        "source_field": "unknown",
                        "value_type": "string",
                        "key_field": "unknown",
                        "refresh_policy": "manual-review",
                        "status": "suggested",
                    }
                )
    return suggestions


def _suggested_property_name(card: dict[str, object]) -> str:
    card_type = str(card.get("type") or "")
    if card_type == "state":
        return "state"
    if card_type == "interface":
        return "handoff"
    if card_type == "decision":
        return "decision"
    return "definition"


def _draft_status(packages: list[dict[str, object]], refusals: list[dict[str, object]]) -> str:
    if packages and refusals:
        return "partial"
    if packages:
        return "drafted"
    if refusals:
        return "refused"
    return "empty"


def _required_str(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing required string field {key!r}")
    return value


def _mapping_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _slug(value: str) -> str:
    chars = [ch if ch.isalnum() else "-" for ch in value.lower()]
    return "-".join("".join(chars).split("-")).strip("-")

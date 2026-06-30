"""Dependency-free source-event contract validation.

The JSON Schema in schemas/source-event.schema.json is the public contract.
This module mirrors the runtime-critical subset so reference code can reject
unsafe events without adding a jsonschema dependency.
"""
from __future__ import annotations

import re
from typing import Any


SOURCE_KINDS = {
    "human-session",
    "telegram-export",
    "meeting-transcript",
    "dashboard-snapshot",
    "crm-export",
    "document",
    "manual-drop",
    "google-drive",
    "calendar-event",
}
CONNECTOR_MODES = {"manual-export", "api-read", "file-drop"}
TRUST_FLOORS = {"candidate", "hypothesis", "conflict", "deprecated", "unknown"}
CLAIM_KINDS = {
    "observed-fact",
    "owner-claim",
    "regulation",
    "dashboard-reading",
    "agent-inference",
    "human-decision",
    "unknown",
}
EVIDENCE_GRADES = {
    "measured",
    "instance",
    "external",
    "claim",
    "inference",
    "hypothesis",
    "framing",
    "unknown",
}
SOURCE_RISKS = {
    "no-known-risk",
    "stale-document",
    "partial-export",
    "manual-memory",
    "formula-unknown",
    "conflicting-source",
    "raw-source-unavailable",
    "owner-unknown",
    "unknown",
}
PROVENANCE_ACTIVITY_TYPES = {
    "manual-export",
    "api-read",
    "file-drop",
    "agent-extraction",
    "human-confirmation",
    "dashboard-read",
    "document-read",
    "unknown",
}
PROVENANCE_ACTOR_TYPES = {"human", "agent", "connector", "system", "unknown"}
SEGMENT_TYPES = {"time-range", "line-range", "cell-range", "record-class", "section", "widget"}
TOP_LEVEL_KEYS = {
    "eventId",
    "sourceId",
    "sourceKind",
    "observedAt",
    "connector",
    "authority",
    "trustFloor",
    "claimKind",
    "evidenceGrade",
    "sourceRisk",
    "provenanceActivity",
    "redaction",
    "evidence",
    "contentSummary",
    "hash",
}
CONNECTOR_KEYS = {"name", "version", "mode", "readOnly"}
AUTHORITY_KEYS = {"owner", "accessMode", "registered"}
REDACTION_KEYS = {"piiExcluded", "rawPayloadIncluded", "redactionNotes"}
EVIDENCE_KEYS = {"locator", "segmentType", "start", "end", "excerpt", "notes"}
PROVENANCE_KEYS = {"activityType", "actor", "actorType", "createdAt", "sourceLocator", "method"}

EVENT_ID_RE = re.compile(r"^srcevt-[a-z0-9][a-z0-9-]*$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
HASH_RE = re.compile(r"^sha256:[a-f0-9]{64}$")


def validate_source_event_contract(event: dict[str, Any]) -> None:
    """Raise ValueError if an event violates the source-event contract."""

    if not isinstance(event, dict):
        raise ValueError("source event must be an object")
    _reject_extra_fields(event, TOP_LEVEL_KEYS, "source event")
    _require_fields(event, TOP_LEVEL_KEYS, "source event")

    event_id = _required_string(event, "eventId", "source event")
    if not EVENT_ID_RE.match(event_id):
        raise ValueError("source event eventId must match ^srcevt-[a-z0-9][a-z0-9-]*$")

    source_id = _required_string(event, "sourceId", "source event")
    if not ID_RE.match(source_id):
        raise ValueError("source event sourceId must match ^[a-z0-9][a-z0-9-]*$")

    source_kind = _required_string(event, "sourceKind", "source event")
    if source_kind not in SOURCE_KINDS:
        raise ValueError(f"source event sourceKind is not allowed: {source_kind}")

    _required_string(event, "observedAt", "source event")

    connector = _required_mapping(event, "connector", "source event")
    _reject_extra_fields(connector, CONNECTOR_KEYS, "connector")
    _require_fields(connector, CONNECTOR_KEYS, "connector")
    _required_string(connector, "name", "connector")
    _required_string(connector, "version", "connector")
    mode = _required_string(connector, "mode", "connector")
    if mode not in CONNECTOR_MODES:
        raise ValueError(f"connector mode is not allowed: {mode}")
    if connector.get("readOnly") is not True:
        raise ValueError("source event connector is not read-only")

    authority = _required_mapping(event, "authority", "source event")
    _reject_extra_fields(authority, AUTHORITY_KEYS, "authority")
    _require_fields(authority, AUTHORITY_KEYS, "authority")
    _required_string(authority, "owner", "authority")
    _required_string(authority, "accessMode", "authority")
    if not isinstance(authority.get("registered"), bool):
        raise ValueError("authority registered must be boolean")

    trust_floor = _required_string(event, "trustFloor", "source event")
    if trust_floor not in TRUST_FLOORS:
        raise ValueError(f"source event trustFloor is not allowed: {trust_floor}")

    claim_kind = _required_string(event, "claimKind", "source event")
    if claim_kind not in CLAIM_KINDS:
        raise ValueError(f"source event claimKind is not allowed: {claim_kind}")

    evidence_grade = _required_string(event, "evidenceGrade", "source event")
    if evidence_grade not in EVIDENCE_GRADES:
        raise ValueError(f"source event evidenceGrade is not allowed: {evidence_grade}")
    if claim_kind == "agent-inference" and evidence_grade not in {"inference", "hypothesis"}:
        raise ValueError("source event agent-inference evidenceGrade must be inference or hypothesis")

    source_risk = event.get("sourceRisk")
    if not isinstance(source_risk, list) or not source_risk:
        raise ValueError("source event sourceRisk must be a non-empty array")
    seen_risks = set()
    for index, item in enumerate(source_risk):
        if not isinstance(item, str) or not item:
            raise ValueError(f"source event sourceRisk[{index}] must be a non-empty string")
        if item not in SOURCE_RISKS:
            raise ValueError(f"source event sourceRisk[{index}] is not allowed: {item}")
        if item in seen_risks:
            raise ValueError(f"source event sourceRisk[{index}] duplicates {item}")
        seen_risks.add(item)
    if "unknown" in seen_risks and len(seen_risks) > 1:
        raise ValueError("source event sourceRisk unknown must not be combined with classified risks")
    if "no-known-risk" in seen_risks and len(seen_risks) > 1:
        raise ValueError("source event sourceRisk no-known-risk must be used alone")

    provenance = _required_mapping(event, "provenanceActivity", "source event")
    _validate_provenance_activity(provenance)

    redaction = _required_mapping(event, "redaction", "source event")
    _reject_extra_fields(redaction, REDACTION_KEYS, "redaction")
    _require_fields(redaction, {"piiExcluded", "rawPayloadIncluded"}, "redaction")
    if redaction.get("piiExcluded") is not True:
        raise ValueError("source event does not prove PII exclusion")
    if redaction.get("rawPayloadIncluded") is not False:
        raise ValueError("source event includes raw payload")
    notes = redaction.get("redactionNotes")
    if notes is not None and not isinstance(notes, str):
        raise ValueError("redaction redactionNotes must be a string")

    evidence = event.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("source event evidence must be a non-empty array")
    for index, item in enumerate(evidence):
        _validate_evidence(item, index)

    summary = _required_string(event, "contentSummary", "source event")
    if len(summary) > 1000:
        raise ValueError("source event contentSummary exceeds 1000 characters")

    event_hash = _required_string(event, "hash", "source event")
    if not HASH_RE.match(event_hash):
        raise ValueError("source event hash must match sha256:<64 lowercase hex chars>")


def _validate_provenance_activity(activity: dict[str, object]) -> None:
    _reject_extra_fields(activity, PROVENANCE_KEYS, "provenanceActivity")
    _require_fields(activity, PROVENANCE_KEYS, "provenanceActivity")
    activity_type = _required_string(activity, "activityType", "provenanceActivity")
    if activity_type not in PROVENANCE_ACTIVITY_TYPES:
        raise ValueError(f"provenanceActivity activityType is not allowed: {activity_type}")
    actor_type = _required_string(activity, "actorType", "provenanceActivity")
    if actor_type not in PROVENANCE_ACTOR_TYPES:
        raise ValueError(f"provenanceActivity actorType is not allowed: {actor_type}")
    _required_string(activity, "actor", "provenanceActivity")
    _required_string(activity, "createdAt", "provenanceActivity")
    _required_string(activity, "sourceLocator", "provenanceActivity")
    _required_string(activity, "method", "provenanceActivity")


def _validate_evidence(item: object, index: int) -> None:
    if not isinstance(item, dict):
        raise ValueError(f"evidence[{index}] must be an object")
    _reject_extra_fields(item, EVIDENCE_KEYS, f"evidence[{index}]")
    _require_fields(item, {"locator", "segmentType", "excerpt"}, f"evidence[{index}]")
    _required_string(item, "locator", f"evidence[{index}]")
    segment_type = _required_string(item, "segmentType", f"evidence[{index}]")
    if segment_type not in SEGMENT_TYPES:
        raise ValueError(f"evidence[{index}] segmentType is not allowed: {segment_type}")
    excerpt = _required_string(item, "excerpt", f"evidence[{index}]")
    if len(excerpt) > 280:
        raise ValueError(f"evidence[{index}] excerpt exceeds 280 characters")
    for key in ("start", "end", "notes"):
        value = item.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"evidence[{index}] {key} must be a string")


def _reject_extra_fields(mapping: dict[str, object], allowed: set[str], label: str) -> None:
    extra = sorted(set(mapping) - allowed)
    if extra:
        raise ValueError(f"{label} has unexpected field: {extra[0]}")


def _require_fields(mapping: dict[str, object], required: set[str], label: str) -> None:
    missing = sorted(required - set(mapping))
    if missing:
        raise ValueError(f"{label} missing required field: {missing[0]}")


def _required_mapping(mapping: dict[str, object], key: str, label: str) -> dict[str, object]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{label} {key} must be an object")
    return value


def _required_string(mapping: dict[str, object], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} {key} must be a non-empty string")
    return value

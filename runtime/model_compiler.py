#!/usr/bin/env python3
"""Deterministic reference compiler for model-change packages.

This is not the production semantic or LLM compiler. It is a dependency-free
contract harness: given one model pack, one normalized source event, and optional
accepted context, it emits a model-change package without writing accepted cards
or staged proposals.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import links_validate  # noqa: E402

COMPILER_NAME = "reference-model-compiler"
COMPILER_VERSION = "0.1"
DEFAULT_ONTOLOGY_REVISION = "runtime:unversioned"
ID_RE = re.compile(r"[^a-z0-9]+")
STATUS_STRENGTH = {
    "unknown": 0,
    "hypothesis": 1,
    "candidate": 2,
    "conflict": 2,
    "deprecated": 3,
    "accepted": 3,
}
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
    "auto-transcription-risk",
    "speaker-attribution-uncertain",
    "meeting-scope-unconfirmed",
    "provider-transcript-unverified",
    "unknown",
}


class CompilerRefusal(ValueError):
    """Raised when a source event cannot safely produce a package."""


@dataclass(frozen=True)
class SourceEvidence:
    source_event_id: str
    locator: str
    excerpt: str


def compile_model_change(
    *,
    model_pack: dict[str, object],
    source_event: dict[str, object],
    accepted_context: dict[str, object] | None = None,
) -> dict[str, object]:
    """Compile one normalized source event into one model-change package."""

    accepted_context = accepted_context or {}
    _assert_safe_source_event(source_event)
    source_kind = _required_str(source_event, "sourceKind")
    _assert_source_kind_allowed(model_pack, source_kind)
    status_ceiling = _status_ceiling(model_pack, source_event)

    event_id = _required_str(source_event, "eventId")
    summary = _required_str(source_event, "contentSummary")
    _assert_safe_text(summary, "contentSummary")
    evidence = _evidence_items(source_event, model_pack)
    processed_events = set(_string_list(accepted_context.get("processedEventIds")))
    processed_hashes = set(_string_list(accepted_context.get("processedHashes")))

    if (
        event_id in processed_events
        or _required_str(source_event, "hash") in processed_hashes
        or _looks_like_noise(summary)
    ):
        changes = [_noop_change(event_id, evidence)]
        review = {
            "overallAction": "no-review-needed",
            "owner": _review_owner(model_pack),
            "reason": "The source event is duplicate/noise for the current review queue.",
        }
    elif source_kind == "dashboard-snapshot" or "dashboard" in summary.lower():
        changes = [_dashboard_metric_concern(event_id, evidence)]
        review = {
            "overallAction": "human-review",
            "owner": _owner_for_scope(model_pack, "measurement", fallback="role:analytics-owner"),
            "reason": "Measurement convention changes are high-risk and require review.",
        }
    elif "handoff" in summary.lower() or "supplies" in summary.lower():
        changes = [_handoff_change(source_event, evidence, status_ceiling)]
        review = {
            "overallAction": "human-review",
            "owner": _primary_owner(model_pack),
            "reason": "A handoff/interface change affects ownership and should be reviewed.",
        }
    elif source_kind == "crm-export" or "stage" in summary.lower():
        changes = [_new_state_change(source_event, evidence, status_ceiling)]
        review = {
            "overallAction": "human-review",
            "owner": _owner_from_source(source_event, fallback=_primary_owner(model_pack)),
            "reason": "Working-system state drift should be reviewed before staging.",
        }
    else:
        changes = [_noop_change(event_id, evidence)]
        review = {
            "overallAction": "no-review-needed",
            "owner": _review_owner(model_pack),
            "reason": "No deterministic reference compiler rule matched this source event.",
        }

    claim_metadata = _claim_metadata(source_event)
    for change in changes:
        change.update(claim_metadata)

    return {
        "packageId": f"mcpkg-{_slug(event_id.removeprefix('srcevt-'))}",
        "moduleId": _required_str(model_pack, "moduleId"),
        "modelPackId": _required_str(model_pack, "modelPackId"),
        "modelPackVersion": _required_str(model_pack, "version"),
        "ontologyRevision": str(
            accepted_context.get("ontologyRevision")
            or accepted_context.get("revision")
            or DEFAULT_ONTOLOGY_REVISION
        ),
        "compiler": {
            "name": COMPILER_NAME,
            "version": COMPILER_VERSION,
            "mode": "automated",
        },
        "sourceEventIds": [event_id],
        "generatedAt": str(accepted_context.get("generatedAt") or source_event.get("observedAt") or "unknown"),
        "summary": _package_summary(source_kind, summary),
        "changes": changes,
        "review": review,
        "safety": {
            "noPii": True,
            "noSecrets": True,
            "noRawPayload": True,
            "noAcceptedMutation": True,
        },
    }


def _assert_safe_source_event(source_event: dict[str, object]) -> None:
    connector = _mapping(source_event.get("connector"), "connector")
    redaction = _mapping(source_event.get("redaction"), "redaction")
    if connector.get("readOnly") is not True:
        raise CompilerRefusal("source event connector is not read-only")
    if redaction.get("piiExcluded") is not True:
        raise CompilerRefusal("source event does not prove PII exclusion")
    if redaction.get("rawPayloadIncluded") is not False:
        raise CompilerRefusal("source event includes raw payload")


def _claim_metadata(source_event: dict[str, object]) -> dict[str, object]:
    claim_kind = _required_str(source_event, "claimKind")
    evidence_grade = _required_str(source_event, "evidenceGrade")
    source_risk = source_event.get("sourceRisk")
    if claim_kind not in CLAIM_KINDS:
        raise CompilerRefusal(f"source event claimKind is not allowed: {claim_kind}")
    if evidence_grade not in EVIDENCE_GRADES:
        raise CompilerRefusal(f"source event evidenceGrade is not allowed: {evidence_grade}")
    if claim_kind == "agent-inference" and evidence_grade not in {"inference", "hypothesis"}:
        raise CompilerRefusal("source event agent-inference evidenceGrade must be inference or hypothesis")
    if not isinstance(source_risk, list) or not source_risk:
        raise CompilerRefusal("source event sourceRisk must be a non-empty array")
    risks: list[str] = []
    seen = set()
    for index, item in enumerate(source_risk):
        if not isinstance(item, str) or not item:
            raise CompilerRefusal(f"source event sourceRisk[{index}] must be a non-empty string")
        if item not in SOURCE_RISKS:
            raise CompilerRefusal(f"source event sourceRisk[{index}] is not allowed: {item}")
        if item in seen:
            raise CompilerRefusal(f"source event sourceRisk[{index}] duplicates {item}")
        seen.add(item)
        risks.append(item)
    if "unknown" in seen and len(seen) > 1:
        raise CompilerRefusal("source event sourceRisk unknown must not be combined with classified risks")
    if "no-known-risk" in seen and len(seen) > 1:
        raise CompilerRefusal("source event sourceRisk no-known-risk must be used alone")
    return {
        "claimKind": claim_kind,
        "evidenceGrade": evidence_grade,
        "sourceRisk": risks,
    }


def _assert_source_kind_allowed(model_pack: dict[str, object], source_kind: str) -> None:
    for rule in _list_of_mappings(model_pack.get("sourceAuthority")):
        if rule.get("sourceKind") == source_kind:
            return
    raise CompilerRefusal(f"source kind {source_kind!r} is outside the model pack authority")


def _status_ceiling(model_pack: dict[str, object], source_event: dict[str, object]) -> str:
    source_kind = _required_str(source_event, "sourceKind")
    trust_floor = _required_str(source_event, "trustFloor")
    max_status = "unknown"
    for rule in _list_of_mappings(model_pack.get("sourceAuthority")):
        if rule.get("sourceKind") == source_kind and isinstance(rule.get("maxStatus"), str):
            max_status = str(rule["maxStatus"])
            break
    return _weaker_status(trust_floor, max_status)


def _weaker_status(first: str, second: str) -> str:
    if STATUS_STRENGTH.get(first, 0) <= STATUS_STRENGTH.get(second, 0):
        return first
    return second


def _evidence_items(
    source_event: dict[str, object],
    model_pack: dict[str, object],
) -> list[dict[str, object]]:
    event_id = _required_str(source_event, "eventId")
    max_items = _max_evidence_items(model_pack)
    items: list[dict[str, object]] = []
    for item in _list_of_mappings(source_event.get("evidence"))[:max_items]:
        evidence = SourceEvidence(
            source_event_id=event_id,
            locator=str(item.get("locator") or "unknown"),
            excerpt=str(item.get("excerpt") or "")[:280],
        )
        _assert_safe_text(evidence.excerpt, f"evidence excerpt {evidence.locator}")
        items.append(
            {
                "sourceEventId": evidence.source_event_id,
                "locator": evidence.locator,
                "excerpt": evidence.excerpt,
            }
        )
    if not items:
        raise CompilerRefusal("source event has no usable evidence")
    return items


def _max_evidence_items(model_pack: dict[str, object]) -> int:
    hints = model_pack.get("compilerHints")
    if isinstance(hints, dict) and isinstance(hints.get("maxEvidenceItems"), int):
        return max(1, int(hints["maxEvidenceItems"]))
    return 5


def _dashboard_metric_concern(
    event_id: str,
    evidence: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "changeId": f"chg-{_slug(event_id.removeprefix('srcevt-'))}",
        "kind": "dashboard-metric-concern",
        "confidence": "medium",
        "risk": "high",
        "affectedIds": ["lead-quality"],
        "evidence": evidence,
        "proposedAction": "review-dashboard-metric",
        "drift": {
            "was": "Accepted metric convention appears to include all closed outcomes.",
            "now": "Dashboard evidence suggests manually overridden outcomes are excluded.",
            "reason": "The source event suggests a measurement convention mismatch.",
        },
    }


def _handoff_change(
    source_event: dict[str, object],
    evidence: list[dict[str, object]],
    status_ceiling: str,
) -> dict[str, object]:
    event_id = _required_str(source_event, "eventId")
    return {
        "changeId": f"chg-{_slug(event_id.removeprefix('srcevt-'))}",
        "kind": "new-agreement",
        "confidence": "medium",
        "risk": "medium",
        "affectedIds": ["unknown"],
        "evidence": evidence,
        "proposedAction": "prepare-staged-proposal",
        "candidateCard": {
            "id": "if-acquisition-sales-handoff",
            "type": "interface",
            "status": _candidate_status(status_ceiling),
            "source": _required_str(source_event, "sourceId"),
            "owner": "role:acquisition-owner",
            "links": {"supplies-to": ["role-sales-customer"]},
            "attrs": {
                "participants": {
                    "supplier": ["role-attraction-supplier"],
                    "customer": ["role-sales-customer"],
                    "subject": ["qualified-lead"],
                },
                "quality-criterion": "Qualification notes are visible before sales acceptance.",
                "outcome": "Qualified lead accepted into the sales queue.",
            },
            "summary": "Candidate interface proposed from a redacted source event.",
        },
    }


def _new_state_change(
    source_event: dict[str, object],
    evidence: list[dict[str, object]],
    status_ceiling: str,
) -> dict[str, object]:
    event_id = _required_str(source_event, "eventId")
    return {
        "changeId": f"chg-{_slug(event_id.removeprefix('srcevt-'))}",
        "kind": "new-object",
        "confidence": "medium",
        "risk": "medium",
        "affectedIds": ["lead-lifecycle"],
        "evidence": evidence,
        "proposedAction": "prepare-staged-proposal",
        "candidateCard": {
            "id": "state-partner-review",
            "type": "state",
            "status": _candidate_status(status_ceiling),
            "source": _required_str(source_event, "sourceId"),
            "owner": _owner_from_source(source_event, fallback="role:systems-owner"),
            "attrs": {"entity": "prospective-participant"},
            "summary": "Candidate funnel state proposed from a redacted CRM export.",
        },
    }


def _noop_change(
    event_id: str,
    evidence: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "changeId": f"chg-noop-{_slug(event_id.removeprefix('srcevt-'))}",
        "kind": "no-op",
        "confidence": "high",
        "risk": "low",
        "affectedIds": [],
        "evidence": evidence,
        "proposedAction": "record-no-op",
    }


def _package_summary(source_kind: str, summary: str) -> str:
    summary = summary.strip()
    if len(summary) > 900:
        summary = summary[:897].rstrip() + "..."
    return f"Reference compiler package for {source_kind}: {summary}"


def _candidate_status(status_ceiling: str) -> str:
    if status_ceiling in {"unknown", "hypothesis", "conflict"}:
        return status_ceiling
    if status_ceiling == "accepted":
        return "candidate"
    return "candidate"


def _assert_safe_text(value: str, label: str) -> None:
    for finding, pattern in links_validate.PII_PATTERNS:
        if pattern.search(value):
            raise CompilerRefusal(f"{label} contains possible {finding}")


def _owner_for_scope(model_pack: dict[str, object], scope: str, fallback: str) -> str:
    for rule in _list_of_mappings(model_pack.get("reviewOwners")):
        if rule.get("scope") == scope and isinstance(rule.get("owner"), str):
            return str(rule["owner"])
    return fallback


def _primary_owner(model_pack: dict[str, object]) -> str:
    owners = model_pack.get("owners")
    if isinstance(owners, dict) and isinstance(owners.get("primary"), str):
        return str(owners["primary"])
    return "role:ontology-reviewer"


def _review_owner(model_pack: dict[str, object]) -> str:
    owners = model_pack.get("owners")
    if isinstance(owners, dict) and isinstance(owners.get("review"), str):
        return str(owners["review"])
    return "role:ontology-reviewer"


def _owner_from_source(source_event: dict[str, object], fallback: str) -> str:
    authority = source_event.get("authority")
    if isinstance(authority, dict) and isinstance(authority.get("owner"), str):
        return str(authority["owner"])
    return fallback


def _looks_like_noise(summary: str) -> bool:
    lowered = summary.lower()
    return "duplicate" in lowered or "noise" in lowered


def _required_str(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise CompilerRefusal(f"missing required string field {key!r}")
    return value


def _mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CompilerRefusal(f"{name} must be an object")
    return value


def _list_of_mappings(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _slug(value: str) -> str:
    slug = ID_RE.sub("-", value.lower()).strip("-")
    return slug or "unknown"

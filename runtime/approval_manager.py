#!/usr/bin/env python3
"""Approval manager for model-change review packages.

This module is a dependency-free reference harness. It prepares bounded review
packages and records review decisions; it never writes accepted ontology,
creates commits, promotes staged cards, or talks to source systems.
"""
from __future__ import annotations

from copy import deepcopy
import re

from runtime.review_authority import (
    ReviewAuthorityError,
    is_review_authorized,
    validate_review_authority,
)


PACKAGE_ID_RE = re.compile(r"^mcpkg-[a-z0-9][a-z0-9-]*$")
REVIEW_ID_RE = re.compile(r"^rev-[a-z0-9][a-z0-9-]*$")
MODULE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MODEL_PACK_ID_RE = re.compile(r"^mp-[a-z0-9][a-z0-9-]*$")
CHANGE_ID_RE = re.compile(r"^chg-[a-z0-9][a-z0-9-]*$")
SOURCE_EVENT_ID_RE = re.compile(r"^srcevt-[a-z0-9][a-z0-9-]*$")
SYSTEM_ANALYSIS_RESULT_ID_RE = re.compile(r"^sysres-[a-z0-9][a-z0-9-]*$")
SENSITIVE_PATTERNS = [
    ("email address", re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")),
    (
        "phone number",
        re.compile(r"(?<![\w-])(?:\+\d{1,3}[\s-]?)?(?:\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4})(?![\w-])"),
    ),
    ("card/account number", re.compile(r"(?<!\d)\d{13,19}(?!\d)")),
    (
        "secret / credential",
        re.compile(
            r"(?i)\b(api[_\-]?key|secret|token|password|passwd|bearer|"
            r"private[_\-]?key)\b\s*[:=]\s*\S+"
        ),
    ),
]
MODEL_PACKAGE_SAFETY_FLAGS = ("noPii", "noSecrets", "noRawPayload", "noAcceptedMutation")
REVIEW_SAFETY_FLAGS = ("noAcceptedMutation", "noAutoPromotion", "noCommit", "noSourceWriteback")
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
CHANGE_KINDS = {
    "new-object",
    "new-definition",
    "new-decision",
    "new-agreement",
    "drift",
    "conflict",
    "source-of-truth-change",
    "dashboard-metric-concern",
    "stale-area",
    "no-op",
    "system-analysis-result",
}
SYSTEM_ANALYSIS_CLASSIFICATIONS = {
    "recommendation-only",
    "experiment",
    "model-change-candidate",
    "drift-item",
    "decision-candidate",
    "no-op",
}
CONFIDENCES = {"high", "medium", "low"}
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
REVIEW_EVIDENCE_MODES = {
    "document-review-only",
    "source-locator-checked",
    "owner-confirmed",
    "live-runtime-checked",
    "not-checked",
}
SOURCE_ADEQUACY = {
    "sufficient",
    "partial",
    "conflicting",
    "stale",
    "missing-owner",
    "insufficient",
}
SLA_BANDS = {"high-risk-48h", "definition-interface-7d", "normal", "needs-owner"}
CHANGE_ACTIONS = {
    "prepare-staged-proposal",
    "open-drift-review",
    "open-conflict-review",
    "review-source-of-truth",
    "review-dashboard-metric",
    "review-system-analysis-result",
    "needs-info",
    "record-no-op",
}
PACKAGE_ACTIONS = {"human-review", "needs-owner", "no-review-needed"}
REVIEW_STATUSES = {
    "pending",
    "approved",
    "rejected",
    "needs-info",
    "superseded",
    "staged-proposal-ready",
}
UNKNOWN_OWNER_VALUES = {"", "unknown", "not applicable", "n/a", "none", "unassigned"}
HIGH_RISK_KINDS = {"source-of-truth-change", "dashboard-metric-concern"}
HIGH_RISK_ACTION_MARKERS = {
    "review-dashboard-metric": {"measurement-convention", "affected-kpis"},
    "review-source-of-truth": {"source-of-truth"},
}
HIGH_RISK_NORMATIVE_FIELDS = {
    "decision-owner",
    "transition-authority",
    "measurement-convention",
    "affected-kpis",
    "propagation-sla",
    "override-policy",
    "exception-path",
    "blast-radius",
    "source-of-truth",
}
DECISION_STATUS = {
    "approve": "approved",
    "approved": "approved",
    "reject": "rejected",
    "rejected": "rejected",
    "needs-info": "needs-info",
    "needs_info": "needs-info",
    "supersede": "superseded",
    "superseded": "superseded",
}


class ApprovalManagerRefusal(ValueError):
    """Raised when a review package or decision is unsafe or malformed."""


def prepare_review_package(
    model_change_package: dict[str, object],
    model_pack: dict[str, object],
) -> dict[str, object]:
    """Prepare a bounded review package from one model-change package."""

    package = deepcopy(model_change_package)
    pack = deepcopy(model_pack)
    package_id = _required_pattern(package, "packageId", PACKAGE_ID_RE, "model_change_package")
    module_id = _required_pattern(package, "moduleId", MODULE_ID_RE, "model_change_package")
    package_model_pack_id = _required_pattern(package, "modelPackId", MODEL_PACK_ID_RE, "model_change_package")
    package_model_pack_version = _required_str(package, "modelPackVersion", "model_change_package")
    pack_id = _required_pattern(pack, "modelPackId", MODEL_PACK_ID_RE, "model_pack")
    pack_module_id = _required_pattern(pack, "moduleId", MODULE_ID_RE, "model_pack")
    pack_version = _required_str(pack, "version", "model_pack")
    if module_id != pack_module_id:
        raise ApprovalManagerRefusal("model-change package moduleId does not match model pack")
    if package_model_pack_id != pack_id or package_model_pack_version != pack_version:
        raise ApprovalManagerRefusal("model-change package was compiled against a different model pack")

    changes = _strict_mapping_list(package.get("changes"), "model-change package changes")
    if not changes:
        raise ApprovalManagerRefusal("model-change package has no reviewable changes")

    review = _mapping(package.get("review"), "review")
    safety = _mapping(package.get("safety"), "safety")
    extra_safety = sorted(set(safety) - set(MODEL_PACKAGE_SAFETY_FLAGS))
    if extra_safety:
        raise ApprovalManagerRefusal("model-change package safety has unexpected fields")
    for flag in MODEL_PACKAGE_SAFETY_FLAGS:
        if safety.get(flag) is not True:
            raise ApprovalManagerRefusal(f"model-change package safety flag {flag} must be true")

    for change in changes:
        _assert_reviewable_change(change)

    change_markers, high_risk_reasons = _high_risk_markers(changes, pack)
    package_risk = _max_risk(changes)
    high_risk = package_risk == "high" or any(high_risk_reasons.values())
    overall_action = _required_enum(review.get("overallAction"), PACKAGE_ACTIONS, "review overallAction")
    review_reason = _required_str(review, "reason", "review")
    _assert_safe_text(review_reason, "review reason")
    owner = _route_owner(
        package_review=review,
        model_pack=pack,
        markers=change_markers,
        high_risk=high_risk,
        force_owner_assignment=overall_action == "needs-owner",
    )
    owner_missing = not _known_owner(owner) or overall_action == "needs-owner"

    if owner_missing:
        status = "needs-info"
        owner = "unknown"
    elif overall_action == "no-review-needed":
        status = "superseded"
    else:
        status = "pending"

    return {
        "reviewId": f"rev-{package_id.removeprefix('mcpkg-')}",
        "packageId": package_id,
        "moduleId": module_id,
        "status": status,
        "owner": owner,
        "risk": package_risk,
        "summary": _bounded_summary(package),
        "decisionImpact": _decision_impact(changes, review_reason, routed_owner=owner),
        "reviewEvidenceMode": "not-checked",
        "sourceAdequacy": _source_adequacy(changes),
        "slaBand": _sla_band(changes, high_risk, owner_missing),
        "changes": [
            _review_change(change, high_risk_reasons.get(_change_id(change), []))
            for change in changes
        ],
        "requiredActions": _required_actions(
            package_id=package_id,
            overall_action=overall_action,
            review_reason=review_reason,
            changes=changes,
            status=status,
            owner_missing=owner_missing,
        ),
        "decisions": [],
        "audit": [
            _audit_event(
                actor="agent",
                action="prepare-review-package",
                timestamp=str(package.get("generatedAt") or "unknown"),
                summary=f"Prepared review package {package_id} for {owner}.",
                result=status,
            )
        ],
        "safety": _review_safety(),
    }


def record_review_decision(
    review_package: dict[str, object],
    decision: dict[str, object],
    *,
    authority_policy: dict[str, object] | None = None,
) -> dict[str, object]:
    """Record an owner decision without mutating accepted truth."""

    package = deepcopy(review_package)
    decision_copy = deepcopy(decision)
    _assert_review_package_safety(package)
    _assert_review_package_history(package)
    _assert_review_package_contract(package)

    current_status = str(package.get("status") or "")
    if current_status != "pending":
        raise ApprovalManagerRefusal("review decisions can only be recorded for pending review packages")

    decision_status = _decision_status(decision_copy)
    actor = _required_decision_actor(decision_copy)
    owner = _required_str(package, "owner", "review_package")
    if not _known_owner(owner):
        raise ApprovalManagerRefusal("review package has no assigned owner")
    channel = str(decision_copy.get("channel") or "").strip()
    authority_scope = (
        "high-risk"
        if package.get("slaBand") == "high-risk-48h" or package.get("risk") == "high"
        else "routine"
    )
    if authority_policy is None:
        if actor != owner:
            raise ApprovalManagerRefusal("review decision actor does not match the routed owner")
        if channel:
            raise ApprovalManagerRefusal(
                "review decision channel requires a review authority policy"
            )
    else:
        try:
            authority_policy = validate_review_authority(authority_policy)
            if authority_policy["businessId"] != package.get("moduleId"):
                raise ApprovalManagerRefusal(
                    "review authority policy belongs to a different business"
                )
            authorized = bool(channel) and is_review_authorized(
                authority_policy,
                actor=actor,
                channel=channel,
                scope=authority_scope,
            )
        except ReviewAuthorityError as exc:
            raise ApprovalManagerRefusal("review authority policy is invalid") from exc
        if not authorized:
            raise ApprovalManagerRefusal(
                "review decision actor is not authorized in this channel and scope"
            )
    reason = str(decision_copy.get("reason") or "No reason provided.")
    _assert_safe_text(reason, "review decision reason")
    decided_at = str(decision_copy.get("decidedAt") or decision_copy.get("timestamp") or "unknown")
    package_id = _required_str(package, "packageId", "review_package")

    resulting_status = _resulting_status(decision_status)
    decisions = _strict_mapping_list(package.get("decisions"), "review package decisions")
    recorded_decision = {
        "decision": decision_status,
        "actor": actor,
        "reason": reason,
        "decidedAt": decided_at,
        "resultingStatus": resulting_status,
    }
    if authority_policy is not None:
        recorded_decision["channel"] = channel
        recorded_decision["authorityScope"] = authority_scope
    decisions.append(recorded_decision)

    audit = _strict_mapping_list(package.get("audit"), "review package audit")
    audit.append(
        _audit_event(
            actor=actor,
            action=f"record-review-decision:{decision_status}",
            timestamp=decided_at,
            summary=f"Review decision recorded for {package_id}: {decision_status}.",
            result=resulting_status,
        )
    )

    package["status"] = resulting_status
    package["decisions"] = decisions
    package["audit"] = audit
    package["requiredActions"] = _post_decision_actions(package_id, decision_status, resulting_status)
    package["safety"] = _review_safety()
    return package


def _decision_impact(
    changes: list[dict[str, object]],
    decision_use: str,
    *,
    routed_owner: str,
) -> dict[str, object]:
    affected_workflows: list[str] = []
    affected_metrics: list[str] = []
    affected_interfaces: list[str] = []
    affected_owners: list[str] = []
    blast_radius: list[str] = []

    for change in changes:
        candidate = change.get("candidateCard")
        affected_ids = _strict_string_list(change.get("affectedIds"), f"change {_change_id(change)} affectedIds")
        for item_id in affected_ids:
            if _metric_review_change(change) and item_id != "unknown":
                _append_unique(affected_metrics, item_id)
                continue
            _append_classified_impact_id(
                item_id,
                affected_workflows=affected_workflows,
                affected_metrics=affected_metrics,
                affected_interfaces=affected_interfaces,
            )

        if not isinstance(candidate, dict):
            continue

        candidate_id = candidate.get("id")
        candidate_type = str(candidate.get("type") or "")
        if isinstance(candidate_id, str) and candidate_id.strip():
            if candidate_type == "interface":
                _append_unique(affected_interfaces, candidate_id.strip())
            else:
                _append_classified_impact_id(
                    candidate_id.strip(),
                    affected_workflows=affected_workflows,
                    affected_metrics=affected_metrics,
                    affected_interfaces=affected_interfaces,
                )

        owner = candidate.get("owner")
        if isinstance(owner, str) and _known_owner(owner):
            _append_unique(affected_owners, owner.strip())

        attrs = candidate.get("attrs")
        if isinstance(attrs, dict):
            _append_attr_values(attrs.get("affected-workflows"), affected_workflows)
            _append_attr_values(attrs.get("affected-kpis"), affected_metrics)
            _append_attr_values(attrs.get("decision-owner"), affected_owners)
            _append_attr_values(attrs.get("transition-authority"), affected_owners)
            _append_attr_values(attrs.get("blast-radius"), blast_radius)

        links = candidate.get("links")
        if isinstance(links, dict):
            _append_attr_values(links.get("measured-by"), affected_metrics)

    if _known_owner(routed_owner):
        _append_unique(affected_owners, routed_owner.strip())

    decision_use = decision_use.strip()
    _assert_safe_text(decision_use, "review decisionUse")
    radius = "; ".join(blast_radius) if blast_radius else "unknown"
    _assert_safe_text(radius, "review blastRadius")

    return {
        "affectedWorkflows": affected_workflows,
        "affectedMetrics": affected_metrics,
        "affectedInterfaces": affected_interfaces,
        "affectedOwners": affected_owners,
        "decisionUse": decision_use,
        "blastRadius": radius,
    }


def _append_classified_impact_id(
    item_id: str,
    *,
    affected_workflows: list[str],
    affected_metrics: list[str],
    affected_interfaces: list[str],
) -> None:
    if item_id.startswith("wf-"):
        _append_unique(affected_workflows, item_id)
    elif item_id.startswith("metric-") or item_id.startswith("kpi-"):
        _append_unique(affected_metrics, item_id)
    elif item_id.startswith("if-"):
        _append_unique(affected_interfaces, item_id)


def _metric_review_change(change: dict[str, object]) -> bool:
    return (
        change.get("kind") == "dashboard-metric-concern"
        or change.get("proposedAction") == "review-dashboard-metric"
    )


def _append_attr_values(value: object, target: list[str]) -> None:
    if isinstance(value, str):
        if value.strip():
            _assert_safe_text(value, "review decision impact value")
            _append_unique(target, value.strip())
        return
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                _assert_safe_text(item, "review decision impact value")
                _append_unique(target, item.strip())


def _append_unique(target: list[str], value: str) -> None:
    if value not in target:
        target.append(value)


def _source_adequacy(changes: list[dict[str, object]]) -> str:
    risks: set[str] = set()
    for change in changes:
        risks.update(_strict_source_risks(change.get("sourceRisk"), f"change {_change_id(change)} sourceRisk"))

    if not risks or "unknown" in risks:
        return "insufficient"
    if risks == {"no-known-risk"}:
        return "sufficient"
    if "conflicting-source" in risks:
        return "conflicting"
    if "owner-unknown" in risks:
        return "missing-owner"
    if "stale-document" in risks:
        return "stale"
    if risks.intersection({"partial-export", "manual-memory", "formula-unknown", "raw-source-unavailable"}):
        return "partial"
    return "sufficient"


def _sla_band(changes: list[dict[str, object]], high_risk: bool, owner_missing: bool) -> str:
    if owner_missing:
        return "needs-owner"
    if high_risk:
        return "high-risk-48h"
    if any(_definition_or_interface_change(change) for change in changes):
        return "definition-interface-7d"
    return "normal"


def _definition_or_interface_change(change: dict[str, object]) -> bool:
    if str(change.get("kind") or "") == "new-definition":
        return True
    candidate = change.get("candidateCard")
    if isinstance(candidate, dict):
        if candidate.get("type") == "interface":
            return True
        candidate_id = candidate.get("id")
        if isinstance(candidate_id, str) and candidate_id.startswith("if-"):
            return True
    return any(item_id.startswith("if-") for item_id in _string_list(change.get("affectedIds")))


def _high_risk_markers(
    changes: list[dict[str, object]],
    model_pack: dict[str, object],
) -> tuple[set[str], dict[str, list[str]]]:
    high_risk_fields = set(_string_list(model_pack.get("highRiskFields")))
    high_risk_fields.update(HIGH_RISK_NORMATIVE_FIELDS)
    markers: set[str] = set()
    reasons_by_change: dict[str, list[str]] = {}

    for change in changes:
        change_id = _change_id(change)
        reasons: list[str] = []
        risk = str(change["risk"])
        kind = str(change["kind"])
        action = str(change["proposedAction"])

        if risk == "high":
            reasons.append("change risk is high")
        if kind in HIGH_RISK_KINDS:
            markers.add("source-of-truth" if kind == "source-of-truth-change" else "measurement-convention")
            reasons.append(f"change kind {kind} requires explicit review")
        if action in HIGH_RISK_ACTION_MARKERS:
            markers.update(HIGH_RISK_ACTION_MARKERS[action])
            reasons.append(f"proposed action {action} requires explicit review")

        candidate = change.get("candidateCard")
        if isinstance(candidate, dict):
            attrs = candidate.get("attrs")
            if isinstance(attrs, dict):
                for field in sorted(high_risk_fields & set(attrs)):
                    markers.add(field)
                    reasons.append(f"candidate touches high-risk field {field}")
            links = candidate.get("links")
            if isinstance(links, dict) and _has_nonempty_link(links, "source-of-truth"):
                markers.add("source-of-truth")
                reasons.append("candidate changes source-of-truth links")
            if candidate.get("type") == "interface":
                markers.add("handoff-interface")

        if reasons:
            reasons_by_change[change_id] = reasons

    return markers, reasons_by_change


def _route_owner(
    *,
    package_review: dict[str, object],
    model_pack: dict[str, object],
    markers: set[str],
    high_risk: bool,
    force_owner_assignment: bool,
) -> str:
    if force_owner_assignment:
        return "unknown"

    matched_owners: list[str] = []
    for rule in _list_of_mappings(model_pack.get("reviewOwners")):
        applies_to = set(_string_list(rule.get("appliesTo")))
        if not markers.intersection(applies_to):
            continue
        if rule.get("highRiskOnly") is True and not high_risk:
            continue
        owner = str(rule.get("owner") or "")
        if _known_owner(owner):
            matched_owners.append(owner)

    distinct_owners = sorted(set(matched_owners))
    if len(distinct_owners) == 1:
        return distinct_owners[0]
    if len(distinct_owners) > 1:
        return _escalation_owner(model_pack)

    if high_risk:
        return "unknown"

    package_owner = str(package_review.get("owner") or "")
    if _known_owner(package_owner):
        return package_owner

    owners = model_pack.get("owners")
    if isinstance(owners, dict):
        review_owner = str(owners.get("review") or "")
        if _known_owner(review_owner):
            return review_owner
        primary_owner = str(owners.get("primary") or "")
        if _known_owner(primary_owner):
            return primary_owner
    return "unknown"


def _review_change(change: dict[str, object], high_risk_reasons: list[str]) -> dict[str, object]:
    review_change = {
        "changeId": _change_id(change),
        "kind": str(change["kind"]),
        "confidence": str(change["confidence"]),
        "risk": str(change["risk"]),
        "claimKind": str(change["claimKind"]),
        "evidenceGrade": str(change["evidenceGrade"]),
        "sourceRisk": _strict_source_risks(change.get("sourceRisk"), f"change {_change_id(change)} sourceRisk"),
        "affectedIds": _strict_string_list(change.get("affectedIds"), f"change {_change_id(change)} affectedIds"),
        "evidence": _bounded_evidence(change),
        "proposedAction": str(change["proposedAction"]),
        "highRiskReasons": high_risk_reasons,
    }
    if "systemAnalysisResultId" in change:
        review_change["systemAnalysisResultId"] = str(change["systemAnalysisResultId"])
    if "systemAnalysisClassification" in change:
        review_change["systemAnalysisClassification"] = str(change["systemAnalysisClassification"])
    return review_change


def _required_actions(
    *,
    package_id: str,
    overall_action: str,
    review_reason: str,
    changes: list[dict[str, object]],
    status: str,
    owner_missing: bool,
) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()

    if status == "needs-info":
        package_action = "needs-owner" if owner_missing else "needs-info"
    else:
        package_action = overall_action
    _append_action(actions, seen, package_action, package_id, review_reason)
    for change in changes:
        change_id = _change_id(change)
        proposed_action = str(change["proposedAction"])
        if proposed_action == "prepare-staged-proposal":
            continue
        _append_action(
            actions,
            seen,
            proposed_action,
            change_id,
            f"Review change {change_id} before any staged proposal.",
        )
    return actions


def _append_action(
    actions: list[dict[str, object]],
    seen: set[tuple[str, str]],
    action: str,
    change_id: str,
    reason: str,
) -> None:
    key = (action, change_id)
    if key in seen:
        return
    seen.add(key)
    actions.append({"action": action, "changeId": change_id, "reason": reason})


def _post_decision_actions(
    package_id: str,
    decision_status: str,
    resulting_status: str,
) -> list[dict[str, object]]:
    if resulting_status == "staged-proposal-ready":
        return [
            {
                "action": "prepare-staged-proposal",
                "changeId": package_id,
                "reason": "Review approved; prepare a staged proposal. Do not commit accepted truth.",
            }
        ]
    if decision_status == "needs-info":
        return [
            {
                "action": "needs-info",
                "changeId": package_id,
                "reason": "Owner requested more information before review can continue.",
            }
        ]
    return []


def _resulting_status(decision_status: str) -> str:
    if decision_status == "approved":
        return "staged-proposal-ready"
    return decision_status


def _decision_status(decision: dict[str, object]) -> str:
    raw = str(decision.get("decision") or decision.get("status") or "").strip().lower()
    status = DECISION_STATUS.get(raw)
    if not status:
        raise ApprovalManagerRefusal(f"unsupported review decision {raw!r}")
    return status


def _required_decision_actor(decision: dict[str, object]) -> str:
    actor = decision.get("actor")
    if not isinstance(actor, str) or not actor.strip():
        raise ApprovalManagerRefusal("review decision missing required actor")
    return actor.strip()


def _bounded_summary(package: dict[str, object]) -> str:
    summary = _required_str(package, "summary", "model_change_package").strip()
    _assert_safe_text(summary, "model-change package summary")
    if len(summary) > 1000:
        raise ApprovalManagerRefusal("model-change package summary exceeds review package bound")
    return summary


def _assert_reviewable_change(change: dict[str, object]) -> None:
    change_id = _required_pattern(change, "changeId", CHANGE_ID_RE, "model-change package change")
    _required_enum(change.get("kind"), CHANGE_KINDS, f"change {change_id} kind")
    _required_enum(change.get("confidence"), CONFIDENCES, f"change {change_id} confidence")
    _required_enum(change.get("risk"), set(RISK_ORDER), f"change {change_id} risk")
    claim_kind = _required_enum(change.get("claimKind"), CLAIM_KINDS, f"change {change_id} claimKind")
    evidence_grade = _required_enum(change.get("evidenceGrade"), EVIDENCE_GRADES, f"change {change_id} evidenceGrade")
    if claim_kind == "agent-inference" and evidence_grade not in {"inference", "hypothesis"}:
        raise ApprovalManagerRefusal(
            f"change {change_id} agent-inference evidenceGrade must be inference or hypothesis"
        )
    _strict_source_risks(change.get("sourceRisk"), f"change {change_id} sourceRisk")
    _required_enum(change.get("proposedAction"), CHANGE_ACTIONS, f"change {change_id} proposedAction")
    affected_ids = _strict_string_list(change.get("affectedIds"), f"change {change_id} affectedIds")
    if len(affected_ids) != len(set(affected_ids)):
        raise ApprovalManagerRefusal(f"change {change_id} affectedIds must be unique")
    _assert_system_analysis_reference(change)
    _assert_bounded_evidence(change)


def _assert_system_analysis_reference(change: dict[str, object]) -> None:
    has_result_id = "systemAnalysisResultId" in change
    has_classification = "systemAnalysisClassification" in change
    requires_reference = (
        change.get("kind") == "system-analysis-result"
        or change.get("proposedAction") == "review-system-analysis-result"
    )
    if has_result_id != has_classification:
        raise ApprovalManagerRefusal("system-analysis change reference requires id and classification")
    if requires_reference and not has_result_id:
        raise ApprovalManagerRefusal("system-analysis review change requires result id and classification")
    if not has_result_id:
        return
    result_id = change.get("systemAnalysisResultId")
    if not isinstance(result_id, str) or not SYSTEM_ANALYSIS_RESULT_ID_RE.fullmatch(result_id):
        raise ApprovalManagerRefusal("system-analysis result id has invalid format")
    classification = change.get("systemAnalysisClassification")
    if classification not in SYSTEM_ANALYSIS_CLASSIFICATIONS:
        raise ApprovalManagerRefusal("system-analysis classification is outside the contract")


def _strict_source_risks(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ApprovalManagerRefusal(f"{label} must be a non-empty array")
    risks = _strict_string_list(value, label)
    seen = set()
    for index, risk in enumerate(risks):
        if risk not in SOURCE_RISKS:
            raise ApprovalManagerRefusal(f"{label}[{index}] is outside the contract")
        if risk in seen:
            raise ApprovalManagerRefusal(f"{label}[{index}] duplicates {risk}")
        seen.add(risk)
    if "unknown" in seen and len(seen) > 1:
        raise ApprovalManagerRefusal(f"{label} unknown must not be combined with classified risks")
    if "no-known-risk" in seen and len(seen) > 1:
        raise ApprovalManagerRefusal(f"{label} no-known-risk must be used alone")
    return risks


def _bounded_evidence(change: dict[str, object]) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    for item in _strict_evidence_items(change):
        evidence.append(
            {
                "sourceEventId": str(item["sourceEventId"]),
                "locator": str(item["locator"]),
                "excerpt": str(item["excerpt"]),
            }
        )
    return evidence


def _assert_bounded_evidence(change: dict[str, object]) -> None:
    evidence = _strict_evidence_items(change)
    change_id = _change_id(change)
    if not evidence:
        raise ApprovalManagerRefusal(f"model-change package change {change_id} has no bounded evidence")

    for index, item in enumerate(evidence, start=1):
        source_event_id = item.get("sourceEventId")
        locator = item.get("locator")
        excerpt = item.get("excerpt")
        extra_keys = sorted(set(item) - {"sourceEventId", "locator", "excerpt"})
        if extra_keys:
            raise ApprovalManagerRefusal(
                f"model-change package change {change_id} evidence {index} has unexpected fields"
            )
        if not isinstance(source_event_id, str) or not SOURCE_EVENT_ID_RE.fullmatch(source_event_id):
            raise ApprovalManagerRefusal(
                f"model-change package change {change_id} evidence {index} has invalid sourceEventId"
            )
        if not isinstance(locator, str) or not locator.strip():
            raise ApprovalManagerRefusal(
                f"model-change package change {change_id} evidence {index} has no locator"
            )
        if not isinstance(excerpt, str) or not excerpt.strip() or len(excerpt) > 280:
            raise ApprovalManagerRefusal(
                f"model-change package change {change_id} evidence {index} has invalid excerpt"
            )
        _assert_safe_text(excerpt, f"model-change package change {change_id} evidence {index}")


def _strict_evidence_items(change: dict[str, object]) -> list[dict[str, object]]:
    value = change.get("evidence")
    change_id = _change_id(change)
    if not isinstance(value, list):
        raise ApprovalManagerRefusal(f"model-change package change {change_id} evidence must be a list")
    evidence: list[dict[str, object]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ApprovalManagerRefusal(
                f"model-change package change {change_id} evidence {index} must be an object"
            )
        evidence.append(item)
    return evidence


def _assert_review_package_safety(package: dict[str, object]) -> None:
    _required_pattern(package, "reviewId", REVIEW_ID_RE, "review_package")
    _required_pattern(package, "packageId", PACKAGE_ID_RE, "review_package")
    _required_pattern(package, "moduleId", MODULE_ID_RE, "review_package")
    status = str(package.get("status") or "")
    if status not in REVIEW_STATUSES:
        raise ApprovalManagerRefusal(f"unsupported review package status {status!r}")
    safety = _mapping(package.get("safety"), "safety")
    extra_safety = sorted(set(safety) - set(REVIEW_SAFETY_FLAGS))
    if extra_safety:
        raise ApprovalManagerRefusal("review package safety has unexpected fields")
    for flag in REVIEW_SAFETY_FLAGS:
        if safety.get(flag) is not True:
            raise ApprovalManagerRefusal(f"review package safety flag {flag} must be true")


def _assert_review_package_contract(package: dict[str, object]) -> None:
    status = _required_enum(package.get("status"), REVIEW_STATUSES, "review package status")
    _required_enum(package.get("risk"), set(RISK_ORDER), "review package risk")
    _required_str(package, "owner", "review_package")
    summary = _required_str(package, "summary", "review_package")
    _assert_safe_text(summary, "review package summary")
    _assert_decision_impact(package.get("decisionImpact"))
    _required_enum(package.get("reviewEvidenceMode"), REVIEW_EVIDENCE_MODES, "review package reviewEvidenceMode")
    _required_enum(package.get("sourceAdequacy"), SOURCE_ADEQUACY, "review package sourceAdequacy")
    _required_enum(package.get("slaBand"), SLA_BANDS, "review package slaBand")

    changes = _strict_mapping_list(package.get("changes"), "review package changes")
    if not changes:
        raise ApprovalManagerRefusal("review package changes must be non-empty")
    for change in changes:
        allowed = {
            "changeId",
            "kind",
            "confidence",
            "risk",
            "claimKind",
            "evidenceGrade",
            "sourceRisk",
            "affectedIds",
            "evidence",
            "proposedAction",
            "highRiskReasons",
            "systemAnalysisResultId",
            "systemAnalysisClassification",
        }
        extra = sorted(set(change) - allowed)
        if extra:
            raise ApprovalManagerRefusal(f"review package change {_change_id(change)} has unexpected fields")
        _assert_reviewable_change(change)
        _strict_string_list(change.get("highRiskReasons"), f"review package change {_change_id(change)} highRiskReasons")

    actions = _strict_mapping_list(package.get("requiredActions"), "review package requiredActions")
    if status == "pending" and not actions:
        raise ApprovalManagerRefusal("pending review package must have required actions")
    has_staged_action = False
    allowed_actions = PACKAGE_ACTIONS | CHANGE_ACTIONS
    for index, action in enumerate(actions, start=1):
        extra = sorted(set(action) - {"action", "changeId", "reason"})
        if extra:
            raise ApprovalManagerRefusal(f"review package requiredActions item {index} has unexpected fields")
        action_name = _required_enum(action.get("action"), allowed_actions, f"required action {index}")
        _required_str(action, "changeId", f"required action {index}")
        reason = _required_str(action, "reason", f"required action {index}")
        _assert_safe_text(reason, f"required action {index} reason")
        if action_name == "prepare-staged-proposal":
            has_staged_action = True

    if status != "staged-proposal-ready" and has_staged_action:
        raise ApprovalManagerRefusal("only staged-proposal-ready review packages may request staged proposals")
    if status == "staged-proposal-ready" and not has_staged_action:
        raise ApprovalManagerRefusal("staged-proposal-ready review packages must request staged proposal preparation")


def _assert_decision_impact(value: object) -> None:
    impact = _mapping(value, "decisionImpact")
    allowed = {
        "affectedWorkflows",
        "affectedMetrics",
        "affectedInterfaces",
        "affectedOwners",
        "decisionUse",
        "blastRadius",
    }
    extra = sorted(set(impact) - allowed)
    if extra:
        raise ApprovalManagerRefusal("review package decisionImpact has unexpected fields")
    for field in ["affectedWorkflows", "affectedMetrics", "affectedInterfaces", "affectedOwners"]:
        values = _strict_string_list(impact.get(field), f"review package decisionImpact {field}")
        if len(values) != len(set(values)):
            raise ApprovalManagerRefusal(f"review package decisionImpact {field} must be unique")
    decision_use = _required_str(impact, "decisionUse", "review package decisionImpact")
    _assert_safe_text(decision_use, "review package decisionImpact decisionUse")
    blast_radius = _required_str(impact, "blastRadius", "review package decisionImpact")
    _assert_safe_text(blast_radius, "review package decisionImpact blastRadius")


def _assert_review_package_history(package: dict[str, object]) -> None:
    for index, decision in enumerate(
        _strict_mapping_list(package.get("decisions"), "review package decisions"),
        start=1,
    ):
        extra = sorted(
            set(decision)
            - {
                "decision",
                "actor",
                "reason",
                "decidedAt",
                "resultingStatus",
                "channel",
                "authorityScope",
            }
        )
        if extra:
            raise ApprovalManagerRefusal(f"review package decision {index} has unexpected fields")
        _required_enum(
            decision.get("decision"),
            {"approved", "rejected", "needs-info", "superseded"},
            f"review package decision {index}",
        )
        _required_str(decision, "actor", f"review package decision {index}")
        reason = _required_str(decision, "reason", f"review package decision {index}")
        _assert_safe_text(reason, f"review package decision {index} reason")
        _required_str(decision, "decidedAt", f"review package decision {index}")
        channel = decision.get("channel")
        authority_scope = decision.get("authorityScope")
        if (channel is None) != (authority_scope is None):
            raise ApprovalManagerRefusal(
                f"review package decision {index} has incomplete authority evidence"
            )
        if channel is not None:
            _required_str(decision, "channel", f"review package decision {index}")
            _required_enum(
                authority_scope,
                {"routine", "high-risk"},
                f"review package decision {index} authorityScope",
            )
        _required_enum(
            decision.get("resultingStatus"),
            REVIEW_STATUSES,
            f"review package decision {index} resultingStatus",
        )

    for index, event in enumerate(
        _strict_mapping_list(package.get("audit"), "review package audit"),
        start=1,
    ):
        extra = sorted(set(event) - {"actor", "action", "timestamp", "summary", "result"})
        if extra:
            raise ApprovalManagerRefusal(f"review package audit {index} has unexpected fields")
        _required_str(event, "actor", f"review package audit {index}")
        _required_str(event, "action", f"review package audit {index}")
        _required_str(event, "timestamp", f"review package audit {index}")
        summary = _required_str(event, "summary", f"review package audit {index}")
        _assert_safe_text(summary, f"review package audit {index} summary")
        _required_str(event, "result", f"review package audit {index}")


def _review_safety() -> dict[str, bool]:
    return {
        "noAcceptedMutation": True,
        "noAutoPromotion": True,
        "noCommit": True,
        "noSourceWriteback": True,
    }


def _audit_event(
    *,
    actor: str,
    action: str,
    timestamp: str,
    summary: str,
    result: str,
) -> dict[str, str]:
    return {
        "actor": actor,
        "action": action,
        "timestamp": timestamp,
        "summary": summary,
        "result": result,
    }


def _max_risk(changes: list[dict[str, object]]) -> str:
    risk = "low"
    for change in changes:
        candidate = str(change["risk"])
        if RISK_ORDER.get(candidate, 0) > RISK_ORDER[risk]:
            risk = candidate
    return risk


def _change_id(change: dict[str, object]) -> str:
    value = change.get("changeId")
    if isinstance(value, str):
        return value
    return "chg-unknown"


def _escalation_owner(model_pack: dict[str, object]) -> str:
    owners = model_pack.get("owners")
    if isinstance(owners, dict):
        owner = str(owners.get("escalation") or "")
        if _known_owner(owner):
            return owner
    return "unknown"


def _known_owner(owner: str) -> bool:
    return owner.strip().lower() not in UNKNOWN_OWNER_VALUES


def _has_nonempty_link(links: dict[str, object], relation: str) -> bool:
    value = links.get(relation)
    return isinstance(value, list) and any(isinstance(item, str) and item for item in value)


def _required_str(mapping: dict[str, object], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ApprovalManagerRefusal(f"{label} missing required string field {key!r}")
    return value


def _required_pattern(
    mapping: dict[str, object],
    key: str,
    pattern: re.Pattern[str],
    label: str,
) -> str:
    value = _required_str(mapping, key, label)
    if not pattern.fullmatch(value):
        raise ApprovalManagerRefusal(f"{label} field {key!r} has invalid format")
    return value


def _required_enum(value: object, allowed: set[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ApprovalManagerRefusal(f"{label} is outside the allowed contract")
    return value


def _assert_safe_text(value: str, label: str) -> None:
    for finding, pattern in SENSITIVE_PATTERNS:
        if pattern.search(value):
            raise ApprovalManagerRefusal(f"{label} contains possible {finding}")


def _mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ApprovalManagerRefusal(f"{name} must be an object")
    return value


def _strict_mapping_list(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ApprovalManagerRefusal(f"{label} must be a list")
    items: list[dict[str, object]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ApprovalManagerRefusal(f"{label} item {index} must be an object")
        items.append(item)
    return items


def _strict_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ApprovalManagerRefusal(f"{label} must be a list")
    items: list[str] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item:
            raise ApprovalManagerRefusal(f"{label} item {index} must be a non-empty string")
        items.append(item)
    return items


def _list_of_mappings(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]

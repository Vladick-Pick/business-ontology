#!/usr/bin/env python3
"""Store/export projections for ontology canvas, bindings, and instance graph.

The functions in this module are read-only shape builders. They do not query
external sources, mutate accepted truth, or expose raw source payloads.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
import re


FORBIDDEN_ATTRIBUTE_KEYS = {
    "raw_payload",
    "rawPayload",
    "raw_value",
    "rawValue",
    "hidden_reasoning",
    "credential_value",
    "secret_value",
}

SYSTEM_ANALYSIS_KINDS = {
    "system-diagram-coach",
    "stock-flow-builder",
    "leverage-finder",
    "constraint-finder",
    "triz-dissolve",
    "why-tree",
}
SYSTEM_ANALYSIS_RESULT_CLASSIFICATIONS = {
    "recommendation-only",
    "experiment",
    "model-change-candidate",
    "drift-item",
    "decision-candidate",
    "no-op",
}
SYSTEM_ANALYSIS_REVIEW_REQUIRED = {
    "recommendation-only": False,
    "experiment": True,
    "model-change-candidate": True,
    "drift-item": True,
    "decision-candidate": True,
    "no-op": False,
}
SYSTEM_ANALYSIS_NEXT_ACTION = {
    "recommendation-only": "none",
    "experiment": "review-system-analysis-result",
    "model-change-candidate": "review-system-analysis-result",
    "drift-item": "open-drift-review",
    "decision-candidate": "review-system-analysis-result",
    "no-op": "record-no-op",
}
SYSTEM_ANALYSIS_RESULT_ID_RE = re.compile(r"^sysres-[a-z0-9][a-z0-9-]*$")
MODULE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MODEL_PACK_ID_RE = re.compile(r"^mp-[a-z0-9][a-z0-9-]*$")
SOURCE_EVENT_ID_RE = re.compile(r"^srcevt-[a-z0-9][a-z0-9-]*$")
UNKNOWN_OWNER_VALUES = {"", "unknown", "not applicable", "n/a", "none", "unassigned"}


def build_configuration_canvas(
    *,
    module_id: str,
    revision: str,
    items: list[dict[str, object]],
    workflows: list[dict[str, object]] | None = None,
    data_bindings: list[dict[str, object]] | None = None,
    instance_graph: dict[str, object] | None = None,
    pending_packages: list[dict[str, object]] | None = None,
    open_questions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Build a visual-canvas-ready projection from accepted model slices."""

    workflows = workflows or []
    data_bindings = data_bindings or []
    pending_packages = pending_packages or []
    open_questions = open_questions or []

    binding_counts = _binding_counts(data_bindings)
    nodes = [_canvas_item_node(item, binding_counts) for item in items]
    nodes.extend(_canvas_workflow_node(workflow) for workflow in workflows)
    edges: list[dict[str, object]] = []
    for workflow in workflows:
        edges.extend(_workflow_edges(workflow))
    if instance_graph:
        nodes.extend(_canvas_instance_node(node) for node in _mapping_list(instance_graph.get("nodes")))
        node_ids = {_string(node.get("id")) for node in nodes}
        for edge in _mapping_list(instance_graph.get("edges")):
            from_id = _string(edge.get("from")) or _string(edge.get("from_instance_id"))
            to_id = _string(edge.get("to")) or _string(edge.get("to_instance_id"))
            if from_id not in node_ids or to_id not in node_ids:
                continue
            edges.append(
                {
                    "id": _string(edge.get("id")) or _string(edge.get("relation_id")),
                    "kind": "instance-relation",
                    "from": from_id,
                    "to": to_id,
                    "label": _string(edge.get("relationType")) or _string(edge.get("relation_type")),
                    "sourceId": _string(edge.get("sourceId")) or _string(edge.get("source_id")),
                }
            )

    return {
        "kind": "configurationCanvas",
        "moduleId": module_id,
        "revision": revision,
        "nodes": sorted(nodes, key=lambda node: (str(node.get("group", "")), str(node.get("id", "")))),
        "edges": sorted(edges, key=lambda edge: str(edge.get("id", ""))),
        "reviewSummary": {
            "pendingPackageCount": len(pending_packages),
            "packageIds": [_string(item.get("packageId")) for item in pending_packages[:25]],
            "highestRisk": _highest_risk(pending_packages),
        },
        "openQuestionSummary": {
            "openQuestionCount": len(open_questions),
            "questionIds": [_string(item.get("question_id")) for item in open_questions[:25]],
        },
    }


def build_data_binding_projection(
    *,
    module_id: str,
    revision: str,
    bindings: list[dict[str, object]],
) -> dict[str, object]:
    """Build a safe data-binding projection without raw source values."""

    safe_bindings = [_safe_binding(binding) for binding in bindings]
    bound_items = sorted({binding["itemId"] for binding in safe_bindings if binding["itemId"]})
    return {
        "kind": "dataBindingProjection",
        "moduleId": module_id,
        "revision": revision,
        "bindings": safe_bindings,
        "coverage": {
            "bindingCount": len(safe_bindings),
            "boundItemCount": len(bound_items),
            "boundItemIds": bound_items[:100],
        },
    }


def build_instance_graph_projection(
    *,
    module_id: str,
    revision: str,
    instances: list[dict[str, object]],
    relations: list[dict[str, object]],
    root_id: str | None = None,
    limit: int = 50,
) -> dict[str, object]:
    """Build a bounded instance graph projection."""

    selected_instances = _select_instances(instances, relations, root_id=root_id, limit=limit)
    selected_ids = {node["instanceId"] for node in selected_instances}
    selected_relations = [
        _safe_instance_relation(relation)
        for relation in relations
        if _string(relation.get("from_instance_id")) in selected_ids
        and _string(relation.get("to_instance_id")) in selected_ids
    ]
    return {
        "kind": "instanceGraph",
        "moduleId": module_id,
        "revision": revision,
        "rootId": root_id or "",
        "nodes": selected_instances,
        "edges": selected_relations,
        "truncated": len(instances) > len(selected_instances),
    }


def build_system_analysis_projection(
    *,
    module_id: str,
    revision: str,
    objective: str,
    analysis_intent: str,
    items: list[dict[str, object]],
    definitions: list[dict[str, object]] | None = None,
    workflows: list[dict[str, object]] | None = None,
    metrics: list[dict[str, object]] | None = None,
    rules: list[dict[str, object]] | None = None,
    constraints: list[dict[str, object]] | None = None,
    delays: list[dict[str, object]] | None = None,
    drift_items: list[dict[str, object]] | None = None,
    unknowns: list[dict[str, object]] | None = None,
    competency_questions: list[dict[str, object]] | None = None,
    review_packages: list[dict[str, object]] | None = None,
    source_events: list[dict[str, object]] | None = None,
    limit: int = 50,
) -> dict[str, object]:
    """Build a bounded input projection for systems-thinking skills."""

    limit = max(1, int(limit))
    definitions = definitions or []
    workflows = workflows or []
    metrics = metrics or []
    rules = rules or []
    constraints = constraints or []
    delays = delays or []
    drift_items = drift_items or []
    unknowns = unknowns or []
    competency_questions = competency_questions or []
    review_packages = review_packages or []
    source_events = source_events or []

    safe_items = [_safe_model_item(item) for item in items]
    safe_definitions = [_safe_definition(definition) for definition in definitions[:limit]]
    safe_workflows = [_safe_system_workflow(workflow, limit=limit) for workflow in workflows[:limit]]
    state_items = [item for item in safe_items if item["kind"] == "state"][:limit]
    metric_items = [item for item in safe_items if item["kind"] == "metric"]
    safe_metrics = [_safe_metric(metric) for metric in [*metric_items, *metrics][:limit]]
    safe_rules = [_safe_note(rule) for rule in rules[:limit]]
    safe_constraints = [_safe_note(constraint) for constraint in constraints[:limit]]
    safe_delays = [_safe_note(delay) for delay in delays[:limit]]
    safe_drift = [_safe_drift(item) for item in drift_items[:limit]]
    safe_unknowns = [_safe_unknown(item) for item in unknowns[:limit]]
    safe_questions = [_safe_competency_question(item) for item in competency_questions[:limit]]

    return {
        "kind": "systemAnalysisProjection",
        "moduleId": module_id,
        "revision": revision,
        "objective": objective or "unknown",
        "analysisIntent": analysis_intent or "unknown",
        "modelIds": _projection_model_ids(
            safe_items,
            safe_definitions,
            safe_workflows,
            safe_metrics,
            safe_rules,
            safe_constraints,
            safe_delays,
            safe_drift,
            safe_questions,
            limit=limit * 4,
        ),
        "definitions": safe_definitions,
        "workflow": {
            "workflowIds": [_string(workflow.get("workflowId")) for workflow in safe_workflows],
            "workflows": safe_workflows,
        },
        "states": state_items,
        "metrics": safe_metrics,
        "rules": safe_rules,
        "constraints": safe_constraints,
        "delays": safe_delays,
        "drift": safe_drift,
        "unknowns": safe_unknowns,
        "evidenceQuality": _evidence_quality(review_packages),
        "competencyQuestions": safe_questions,
        "sourceSummary": _source_summary(
            safe_items,
            safe_definitions,
            safe_workflows,
            safe_metrics,
            safe_rules,
            safe_constraints,
            safe_delays,
            review_packages,
            source_events,
        ),
    }


def evaluate_system_analysis_readiness(
    projection: dict[str, object],
    analysis_kind: str,
) -> dict[str, object]:
    """Return fail-closed readiness for a downstream systems-thinking skill."""

    kind = _string(analysis_kind)
    requirements = _readiness_requirements(kind)
    missing: list[str] = []
    warnings: list[str] = []

    if projection.get("kind") != "systemAnalysisProjection":
        missing.append("kind:systemAnalysisProjection")

    if requirements is None:
        missing.append("analysisKind")
        warnings.append(f"unsupported analysisKind {kind or 'unknown'}")
    else:
        for field, predicate in requirements:
            if not predicate(projection):
                missing.append(field)

    source_adequacy = _list_strings(
        _mapping(projection.get("evidenceQuality")).get("sourceAdequacy")
    )
    weak_adequacy = sorted(set(source_adequacy) - {"sufficient"})
    if weak_adequacy:
        warnings.append("sourceAdequacy:" + ",".join(weak_adequacy))

    return {
        "analysisKind": kind or "unknown",
        "ready": not missing,
        "missingFields": missing,
        "warnings": warnings,
        "recommendedQuestion": "" if not missing else _recommended_question(kind, missing[0]),
    }


def build_system_analysis_result(
    *,
    result_id: str,
    projection: dict[str, object],
    analysis_kind: str,
    classification: str,
    summary: str,
    affected_ids: list[str] | None = None,
) -> dict[str, object]:
    """Classify a systems-thinking output without accepting model truth."""

    if not SYSTEM_ANALYSIS_RESULT_ID_RE.fullmatch(result_id):
        raise ValueError("system-analysis result_id must match sysres-*")
    kind = _string(analysis_kind)
    if kind not in SYSTEM_ANALYSIS_KINDS:
        raise ValueError("system-analysis result analysis_kind is unsupported")
    result_class = _string(classification)
    if result_class not in SYSTEM_ANALYSIS_RESULT_CLASSIFICATIONS:
        raise ValueError("system-analysis result classification is unsupported")
    result_summary = _string(summary).strip()
    if not result_summary:
        raise ValueError("system-analysis result summary is required")
    if projection.get("kind") != "systemAnalysisProjection":
        raise ValueError("system-analysis result projection must be a systemAnalysisProjection")
    projection_id = _string(projection.get("revision")).strip()
    if not projection_id or projection_id == "unknown":
        raise ValueError("system-analysis result projection revision is required")
    module_id = _string(projection.get("moduleId")).strip()
    if module_id == "unknown" or not MODULE_ID_RE.fullmatch(module_id):
        raise ValueError("system-analysis result projection moduleId is invalid")

    source_summary = _mapping(projection.get("sourceSummary"))
    source_event_ids = [
        source_event_id
        for source_event_id in _list_strings(source_summary.get("sourceEventIds"))
        if SOURCE_EVENT_ID_RE.fullmatch(source_event_id)
    ]

    return {
        "kind": "systemAnalysisResult",
        "resultId": result_id,
        "projectionId": projection_id,
        "moduleId": module_id,
        "analysisKind": kind,
        "classification": result_class,
        "summary": result_summary[:1000],
        "affectedIds": _unique_string_list(affected_ids or []),
        "sourceEventIds": source_event_ids,
        "evidenceQuality": _result_evidence_quality(projection.get("evidenceQuality")),
        "reviewRequired": SYSTEM_ANALYSIS_REVIEW_REQUIRED[result_class],
        "nextAction": SYSTEM_ANALYSIS_NEXT_ACTION[result_class],
        "safety": _system_result_safety(),
    }


def build_model_health_projection(
    *,
    module_id: str,
    revision: str,
    as_of: str,
    items: list[dict[str, object]],
    competency_questions: list[dict[str, object]] | None = None,
    review_packages: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Build read-only model health and review WIP metrics from supplied state."""

    competency_questions = competency_questions or []
    review_packages_supplied = review_packages is not None
    review_packages = review_packages or []
    missing_inputs: list[str] = []
    as_of_date = _parse_date(as_of)
    if as_of_date is None:
        missing_inputs.append("asOf")

    status_counts = _status_counts(items)
    stale_count, stale_missing = _stale_past_next_audit_count(items, as_of_date)
    if stale_missing:
        missing_inputs.append("items.nextAudit")

    owner_percent = _percent_known(items, _has_known_owner)
    source_locator_percent = _percent_known(items, _has_source_locator)
    if items and not any(_has_source_locator(item) for item in items):
        missing_inputs.append("items.sourceLocator")

    average_age, age_missing = _average_review_age_days(review_packages, as_of_date)
    if age_missing:
        missing_inputs.append("reviewPackages.createdAt")
    if not review_packages_supplied:
        missing_inputs.append("reviewPackages")

    high_risk_packages = [
        package for package in review_packages
        if _is_review_wip(package) and _string(package.get("risk")) == "high"
    ]
    blocked_package_ids = [
        _package_id(package) for package in review_packages
        if _is_review_wip(package) and _blocked_by_missing_owner(package)
    ]
    high_risk_ids = [_package_id(package) for package in high_risk_packages]
    high_risk_limit = 5
    if not review_packages_supplied:
        high_risk_status = "unknown"
    elif len(high_risk_packages) > high_risk_limit:
        high_risk_status = "over-limit"
    else:
        high_risk_status = "within-limit"

    return {
        "kind": "modelHealth",
        "moduleId": module_id,
        "revision": revision,
        "asOf": as_of,
        "metrics": {
            "acceptedItemCount": status_counts.get("accepted", 0),
            "candidateCount": status_counts.get("candidate", 0),
            "hypothesisCount": status_counts.get("hypothesis", 0),
            "conflictCount": status_counts.get("conflict", 0),
            "stalePastNextAuditCount": stale_count,
            "averageReviewAgeDays": average_age,
            "claimsWithOwnerPercent": owner_percent,
            "claimsWithSourceLocatorPercent": source_locator_percent,
            "unansweredCompetencyQuestionCount": _unanswered_competency_questions(competency_questions),
            "proposalsBlockedByMissingOwner": len([item for item in blocked_package_ids if item]),
            "highRiskReviewWipCount": len(high_risk_packages),
        },
        "reviewWip": {
            "highRiskLimit": high_risk_limit,
            "highRiskStatus": high_risk_status,
            "highRiskPackageIds": _unique_string_list(high_risk_ids),
            "blockedPackageIds": _unique_string_list(blocked_package_ids),
        },
        "missingInputs": _unique_string_list(missing_inputs),
    }


def model_change_package_from_system_analysis_result(
    result: dict[str, object],
    *,
    model_pack_id: str,
    model_pack_version: str,
    ontology_revision: str,
    generated_at: str,
    owner: str,
) -> dict[str, object] | None:
    """Route review-required system-analysis results into model-change review."""

    _assert_system_analysis_result(result)
    if result["reviewRequired"] is not True:
        return None
    if not MODEL_PACK_ID_RE.fullmatch(model_pack_id):
        raise ValueError("model_pack_id must match mp-*")
    if not _string(model_pack_version):
        raise ValueError("model_pack_version is required")
    if not _string(ontology_revision):
        raise ValueError("ontology_revision is required")
    if not _string(generated_at):
        raise ValueError("generated_at is required")

    source_event_ids = _list_strings(result.get("sourceEventIds"))
    if not source_event_ids:
        raise ValueError("review-required system-analysis result needs sourceEventIds")

    result_id = _string(result["resultId"])
    package_slug = result_id.removeprefix("sysres-")
    classification = _string(result["classification"])
    proposed_action = _string(result["nextAction"])
    change_kind = "drift" if classification == "drift-item" else "system-analysis-result"

    return {
        "packageId": f"mcpkg-{package_slug}",
        "moduleId": _string(result["moduleId"]),
        "modelPackId": model_pack_id,
        "modelPackVersion": model_pack_version,
        "ontologyRevision": ontology_revision,
        "compiler": {
            "name": "system-analysis-return-path",
            "version": "0.1.0",
            "mode": "automated",
        },
        "sourceEventIds": source_event_ids,
        "generatedAt": generated_at,
        "summary": _string(result["summary"]),
        "changes": [
            {
                "changeId": f"chg-{package_slug}",
                "kind": change_kind,
                "confidence": "low",
                "risk": _system_result_risk(result),
                "claimKind": "agent-inference",
                "evidenceGrade": "hypothesis",
                "sourceRisk": _system_result_source_risk(result),
                "affectedIds": _list_strings(result.get("affectedIds")) or ["unknown"],
                "evidence": [
                    {
                        "sourceEventId": source_event_ids[0],
                        "locator": f"system-analysis-result:{result_id}",
                        "excerpt": _string(result["summary"])[:280],
                    }
                ],
                "proposedAction": proposed_action,
                "systemAnalysisResultId": result_id,
                "systemAnalysisClassification": classification,
            }
        ],
        "review": {
            "overallAction": "human-review",
            "owner": _string(owner) or "unknown",
            "reason": "System-analysis result requires human review before any model change.",
        },
        "safety": {
            "noPii": True,
            "noSecrets": True,
            "noRawPayload": True,
            "noAcceptedMutation": True,
        },
    }


def _readiness_requirements(kind: str) -> list[tuple[str, Any]] | None:
    gates: dict[str, list[tuple[str, Any]]] = {
        "system-diagram-coach": [
            ("variables-or-states", _has_variables_or_states),
            ("flows-or-transitions", _has_flows_or_transitions),
            ("loops-or-explicit-unknown-loops", _has_loops_or_unknown_loops),
            ("delays", _has_delays),
            ("goal", _has_goal),
        ],
        "stock-flow-builder": [
            ("stocks", lambda projection: _has_token(projection, "stock")),
            ("flows", lambda projection: _has_token(projection, "flow")),
            ("equations", _has_equations),
            ("parameters", lambda projection: _has_token(projection, "parameter")),
            ("time-step", lambda projection: _has_token(projection, "time step")),
            ("reference-mode", lambda projection: _has_token(projection, "reference mode")),
            ("measurable-goal-or-contradiction", _has_measurable_goal_or_contradiction),
        ],
        "leverage-finder": [
            ("model-slice", lambda projection: bool(_list_strings(projection.get("modelIds")))),
            ("measurable-target", _has_measurable_target),
            ("stated-vs-enacted-goal-check", _has_stated_vs_enacted_goal_check),
        ],
        "constraint-finder": [
            ("process-or-workflow", _has_workflow),
            ("throughput-unit", _has_throughput_unit),
            ("wip-or-queue-evidence", _has_wip_or_queue_evidence),
            ("capacity-or-rate", _has_capacity_or_rate),
            ("rules-or-policies", _has_rules_or_policies),
        ],
        "triz-dissolve": [
            ("explicit-contradiction-improving-x-worsens-y", _has_contradiction),
        ],
        "why-tree": [
            ("gap-vs-goal", lambda projection: _has_token(projection, "gap")),
            ("baseline", lambda projection: _has_token(projection, "baseline")),
            ("target", _has_measurable_target),
            ("evidence-quality", _has_evidence_quality),
            ("refutable-branches-or-missing-data-request", _has_refutable_branch_or_missing_data),
        ],
    }
    return gates.get(kind)


def _canvas_item_node(
    item: dict[str, object],
    binding_counts: dict[str, int],
) -> dict[str, object]:
    item_id = _string(item.get("id")) or _string(item.get("item_id"))
    binding_count = binding_counts.get(item_id, 0)
    warnings = []
    if binding_count == 0:
        warnings.append("missing-data-binding")
    if _string(item.get("source_id")) in {"", "unknown"}:
        warnings.append("missing-source")
    return {
        "id": item_id,
        "kind": _string(item.get("kind")),
        "group": "accepted-item",
        "label": _string(item.get("name")) or item_id,
        "status": _string(item.get("status")),
        "sourceId": _string(item.get("source_id")),
        "confidence": _string(item.get("confidence")),
        "bindingCount": binding_count,
        "warnings": warnings,
    }


def _canvas_workflow_node(workflow: dict[str, object]) -> dict[str, object]:
    workflow_id = _string(workflow.get("workflow_id"))
    return {
        "id": workflow_id,
        "kind": "workflow",
        "group": "accepted-workflow",
        "label": _string(workflow.get("name")) or workflow_id,
        "status": _string(workflow.get("status")),
        "sourceId": _string(workflow.get("source_id")),
        "confidence": _string(workflow.get("confidence")),
        "bindingCount": 0,
        "warnings": [],
    }


def _canvas_instance_node(instance: dict[str, object]) -> dict[str, object]:
    instance_id = _string(instance.get("instanceId")) or _string(instance.get("instance_id"))
    return {
        "id": instance_id,
        "kind": "instance",
        "group": "accepted-instance",
        "label": _string(instance.get("label")) or instance_id,
        "status": _string(instance.get("status")),
        "sourceId": _string(instance.get("sourceId")) or _string(instance.get("source_id")),
        "itemId": _string(instance.get("itemId")) or _string(instance.get("item_id")),
        "bindingCount": 0,
        "warnings": [],
    }


def _workflow_edges(workflow: dict[str, object]) -> list[dict[str, object]]:
    workflow_id = _string(workflow.get("workflow_id"))
    edges: list[dict[str, object]] = []
    for participant in _mapping_list(workflow.get("participants")):
        participant_id = _string(participant.get("participant_id"))
        edges.append(
            {
                "id": f"{workflow_id}:{participant_id}",
                "kind": "workflow-participant",
                "from": workflow_id,
                "to": _string(participant.get("role_id")),
                "label": _string(participant.get("participant_type")),
                "sourceId": _string(participant.get("source_id")),
            }
        )
    for transition in _mapping_list(workflow.get("transitions")):
        transition_id = _string(transition.get("transition_id"))
        edges.append(
            {
                "id": transition_id,
                "kind": "workflow-transition",
                "from": _string(transition.get("from_state_id")),
                "to": _string(transition.get("to_state_id")),
                "label": _string(transition.get("trigger")),
                "sourceId": _string(transition.get("source_id")),
            }
        )
    for metric in _mapping_list(workflow.get("metrics")):
        metric_id = _string(metric.get("metric_id"))
        edges.append(
            {
                "id": f"{workflow_id}:{metric_id}",
                "kind": "workflow-metric",
                "from": workflow_id,
                "to": metric_id,
                "label": _string(metric.get("role")),
                "sourceId": _string(metric.get("source_id")),
            }
        )
    return edges


def _safe_binding(binding: dict[str, object]) -> dict[str, object]:
    return {
        "bindingId": _string(binding.get("binding_id")),
        "itemId": _string(binding.get("item_id")),
        "propertyName": _string(binding.get("property_name")),
        "sourceId": _string(binding.get("source_id")),
        "sourceKind": _string(binding.get("source_kind")),
        "sourceLocator": _string(binding.get("source_locator")),
        "sourceField": _string(binding.get("source_field")),
        "valueType": _string(binding.get("value_type")),
        "keyField": _string(binding.get("key_field")),
        "refreshPolicy": _string(binding.get("refresh_policy")),
    }


def _safe_instance(instance: dict[str, object]) -> dict[str, object]:
    return {
        "instanceId": _string(instance.get("instance_id")),
        "itemId": _string(instance.get("item_id")),
        "label": _string(instance.get("label")),
        "status": _string(instance.get("status")),
        "sourceId": _string(instance.get("source_id")),
        "evidenceId": _string(instance.get("evidence_id")),
        "decisionId": _string(instance.get("decision_id")),
        "attributes": _safe_attributes(instance.get("attributes")),
    }


def _safe_instance_relation(relation: dict[str, object]) -> dict[str, object]:
    return {
        "id": _string(relation.get("relation_id")),
        "from": _string(relation.get("from_instance_id")),
        "to": _string(relation.get("to_instance_id")),
        "relationType": _string(relation.get("relation_type")),
        "sourceId": _string(relation.get("source_id")),
        "evidenceId": _string(relation.get("evidence_id")),
        "decisionId": _string(relation.get("decision_id")),
    }


def _select_instances(
    instances: list[dict[str, object]],
    relations: list[dict[str, object]],
    *,
    root_id: str | None,
    limit: int,
) -> list[dict[str, object]]:
    limit = max(1, int(limit))
    if root_id:
        connected_ids = {root_id}
        for relation in relations:
            source = _string(relation.get("from_instance_id"))
            target = _string(relation.get("to_instance_id"))
            if source == root_id:
                connected_ids.add(target)
            if target == root_id:
                connected_ids.add(source)
        selected = [instance for instance in instances if _string(instance.get("instance_id")) in connected_ids]
    else:
        selected = list(instances)
    return [_safe_instance(instance) for instance in selected[:limit]]


def _safe_model_item(item: dict[str, object]) -> dict[str, object]:
    item_id = _string(item.get("id")) or _string(item.get("item_id"))
    return {
        "id": item_id,
        "kind": _string(item.get("kind")) or "unknown",
        "name": _string(item.get("name")) or item_id or "unknown",
        "status": _string(item.get("status")) or "unknown",
        "sourceId": _string(item.get("sourceId")) or _string(item.get("source_id")) or "unknown",
        "evidenceId": _string(item.get("evidenceId")) or _string(item.get("evidence_id")),
        "decisionId": _string(item.get("decisionId")) or _string(item.get("decision_id")),
        "confidence": _string(item.get("confidence")) or "unknown",
    }


def _safe_definition(definition: dict[str, object]) -> dict[str, object]:
    return {
        "definitionId": _string(definition.get("definitionId")) or _string(definition.get("definition_id")),
        "itemId": _string(definition.get("itemId")) or _string(definition.get("item_id")),
        "text": _string(definition.get("text")) or "unknown",
        "sourceId": _string(definition.get("sourceId")) or _string(definition.get("source_id")) or "unknown",
        "evidenceId": _string(definition.get("evidenceId")) or _string(definition.get("evidence_id")),
        "decisionId": _string(definition.get("decisionId")) or _string(definition.get("decision_id")),
        "confidence": _string(definition.get("confidence")) or "unknown",
    }


def _safe_system_workflow(workflow: dict[str, object], *, limit: int) -> dict[str, object]:
    workflow_id = _string(workflow.get("workflowId")) or _string(workflow.get("workflow_id"))
    return {
        "workflowId": workflow_id,
        "name": _string(workflow.get("name")) or workflow_id or "unknown",
        "status": _string(workflow.get("status")) or "unknown",
        "sourceId": _string(workflow.get("sourceId")) or _string(workflow.get("source_id")),
        "evidenceId": _string(workflow.get("evidenceId")) or _string(workflow.get("evidence_id")),
        "decisionId": _string(workflow.get("decisionId")) or _string(workflow.get("decision_id")),
        "startStateId": _string(workflow.get("startStateId")) or _string(workflow.get("start_state_id")),
        "endStateId": _string(workflow.get("endStateId")) or _string(workflow.get("end_state_id")),
        "valueStageId": _string(workflow.get("valueStageId")) or _string(workflow.get("value_stage_id")),
        "businessObjectIds": _unique_strings(workflow.get("businessObjectIds"))
        or _unique_strings(workflow.get("business_object_ids")),
        "participants": [_safe_note(item) for item in _mapping_list(workflow.get("participants"))[:limit]],
        "steps": [_safe_note(item) for item in _mapping_list(workflow.get("steps"))[:limit]],
        "transitions": [_safe_transition(item) for item in _mapping_list(workflow.get("transitions"))[:limit]],
        "exceptions": [_safe_note(item) for item in _mapping_list(workflow.get("exceptions"))[:limit]],
        "metrics": [_safe_workflow_metric(item) for item in _mapping_list(workflow.get("metrics"))[:limit]],
    }


def _safe_transition(transition: dict[str, object]) -> dict[str, object]:
    return {
        "transitionId": _string(transition.get("transitionId")) or _string(transition.get("transition_id")),
        "fromStateId": _string(transition.get("fromStateId")) or _string(transition.get("from_state_id")),
        "toStateId": _string(transition.get("toStateId")) or _string(transition.get("to_state_id")),
        "trigger": _string(transition.get("trigger")),
        "evidenceRule": _string(transition.get("evidenceRule")) or _string(transition.get("evidence_rule")),
        "authorityId": _string(transition.get("authorityId")) or _string(transition.get("authority_id")),
        "sourceId": _string(transition.get("sourceId")) or _string(transition.get("source_id")),
    }


def _safe_workflow_metric(metric: dict[str, object]) -> dict[str, object]:
    return {
        "metricId": _string(metric.get("metricId")) or _string(metric.get("metric_id")),
        "role": _string(metric.get("role")),
        "sourceId": _string(metric.get("sourceId")) or _string(metric.get("source_id")),
    }


def _safe_metric(metric: dict[str, object]) -> dict[str, object]:
    metric_id = _string(metric.get("id")) or _string(metric.get("item_id")) or _string(metric.get("metric_id"))
    return {
        "id": metric_id,
        "name": _string(metric.get("name")) or metric_id or "unknown",
        "status": _string(metric.get("status")) or "unknown",
        "sourceId": _string(metric.get("sourceId")) or _string(metric.get("source_id")) or "unknown",
        "evidenceId": _string(metric.get("evidenceId")) or _string(metric.get("evidence_id")),
        "decisionId": _string(metric.get("decisionId")) or _string(metric.get("decision_id")),
        "confidence": _string(metric.get("confidence")) or "unknown",
        "formula": _string(metric.get("formula")) or _string(metric.get("measurement_convention")),
        "owner": _string(metric.get("owner")),
        "sourceOfTruth": _string(metric.get("sourceOfTruth")) or _string(metric.get("source_of_truth")),
    }


def _safe_note(item: dict[str, object]) -> dict[str, object]:
    item_id = (
        _string(item.get("id"))
        or _string(item.get("item_id"))
        or _string(item.get("rule_id"))
        or _string(item.get("constraint_id"))
        or _string(item.get("delay_id"))
        or _string(item.get("participant_id"))
        or _string(item.get("step_id"))
        or _string(item.get("exception_id"))
    )
    summary = (
        _string(item.get("summary"))
        or _string(item.get("name"))
        or _string(item.get("text"))
        or _string(item.get("description"))
        or item_id
        or "unknown"
    )
    return {
        "id": item_id or "unknown",
        "summary": summary,
        "sourceId": _string(item.get("sourceId")) or _string(item.get("source_id")),
        "evidenceId": _string(item.get("evidenceId")) or _string(item.get("evidence_id")),
    }


def _safe_drift(item: dict[str, object]) -> dict[str, object]:
    return {
        "id": _string(item.get("id")) or _string(item.get("item_id")) or "unknown",
        "status": _string(item.get("status")) or "unknown",
        "affectedIds": _unique_strings(item.get("affectedIds")) or _unique_strings(item.get("affected_ids")),
        "summary": _string(item.get("summary")) or "unknown",
        "owner": _string(item.get("owner")) or "unknown",
    }


def _safe_unknown(item: dict[str, object]) -> dict[str, object]:
    return {
        "id": _string(item.get("id")) or _string(item.get("item_id")) or _string(item.get("field")) or "unknown",
        "field": _string(item.get("field")) or "unknown",
        "reason": _string(item.get("reason")) or _string(item.get("summary")) or "unknown",
    }


def _safe_competency_question(item: dict[str, object]) -> dict[str, object]:
    return {
        "questionId": _string(item.get("questionId")) or "unknown",
        "scopeId": _string(item.get("scopeId")) or "unknown",
        "question": _string(item.get("question")) or "unknown",
        "decisionUse": _string(item.get("decisionUse")) or "unknown",
        "answerStatus": _string(item.get("answerStatus")) or "unknown",
        "answeredByIds": _unique_strings(item.get("answeredByIds")),
        "missingFields": _unique_strings(item.get("missingFields")),
        "owner": _string(item.get("owner")) or "unknown",
        "lastReviewedAt": _string(item.get("lastReviewedAt")) or "unknown",
    }


def _evidence_quality(review_packages: list[dict[str, object]]) -> dict[str, object]:
    risks = [_string(package.get("risk")) for package in review_packages if _string(package.get("risk"))]
    return {
        "highestReviewRisk": _highest_risk(review_packages),
        "reviewEvidenceModes": _sorted_unique(
            _string(package.get("reviewEvidenceMode")) for package in review_packages
        ),
        "sourceAdequacy": _sorted_unique(_string(package.get("sourceAdequacy")) for package in review_packages),
        "slaBands": _sorted_unique(_string(package.get("slaBand")) for package in review_packages),
        "notes": ["no review packages supplied"] if not risks else [],
    }


def _source_summary(
    items: list[dict[str, object]],
    definitions: list[dict[str, object]],
    workflows: list[dict[str, object]],
    metrics: list[dict[str, object]],
    rules: list[dict[str, object]],
    constraints: list[dict[str, object]],
    delays: list[dict[str, object]],
    review_packages: list[dict[str, object]],
    source_events: list[dict[str, object]],
) -> dict[str, object]:
    source_ids: list[str] = []
    evidence_ids: list[str] = []
    for record in [*items, *definitions, *metrics, *rules, *constraints, *delays]:
        _append_if_present(source_ids, _string(record.get("sourceId")))
        _append_if_present(evidence_ids, _string(record.get("evidenceId")))
    for workflow in workflows:
        _append_if_present(source_ids, _string(workflow.get("sourceId")))
        _append_if_present(evidence_ids, _string(workflow.get("evidenceId")))
        for transition in workflow.get("transitions", []):
            if isinstance(transition, dict):
                _append_if_present(source_ids, _string(transition.get("sourceId")))
        for metric in workflow.get("metrics", []):
            if isinstance(metric, dict):
                _append_if_present(source_ids, _string(metric.get("sourceId")))
    return {
        "sourceIds": sorted(source_ids),
        "evidenceIds": sorted(evidence_ids),
        "reviewPackageIds": _sorted_unique(_string(package.get("packageId")) for package in review_packages),
        "sourceEventIds": _sorted_unique(
            _string(event.get("eventId")) or _string(event.get("sourceEventId"))
            for event in source_events
        ),
    }


def _projection_model_ids(
    items: list[dict[str, object]],
    definitions: list[dict[str, object]],
    workflows: list[dict[str, object]],
    metrics: list[dict[str, object]],
    rules: list[dict[str, object]],
    constraints: list[dict[str, object]],
    delays: list[dict[str, object]],
    drift: list[dict[str, object]],
    questions: list[dict[str, object]],
    *,
    limit: int,
) -> list[str]:
    ids: list[str] = []
    for item in items:
        _append_if_present(ids, _string(item.get("id")))
    for definition in definitions:
        _append_if_present(ids, _string(definition.get("itemId")))
    for workflow in workflows:
        _append_if_present(ids, _string(workflow.get("workflowId")))
        _append_if_present(ids, _string(workflow.get("valueStageId")))
        for business_object_id in workflow.get("businessObjectIds", []):
            if isinstance(business_object_id, str):
                _append_if_present(ids, business_object_id)
        for transition in workflow.get("transitions", []):
            if isinstance(transition, dict):
                _append_if_present(ids, _string(transition.get("fromStateId")))
                _append_if_present(ids, _string(transition.get("toStateId")))
        for metric in workflow.get("metrics", []):
            if isinstance(metric, dict):
                _append_if_present(ids, _string(metric.get("metricId")))
    for metric in metrics:
        _append_if_present(ids, _string(metric.get("id")))
    for note in [*rules, *constraints, *delays]:
        _append_if_present(ids, _string(note.get("id")))
    for item in drift:
        for affected_id in item.get("affectedIds", []):
            if isinstance(affected_id, str):
                _append_if_present(ids, affected_id)
    for question in questions:
        for answered_id in question.get("answeredByIds", []):
            if isinstance(answered_id, str):
                _append_if_present(ids, answered_id)
    return ids[:limit]


def _append_if_present(target: list[str], value: str) -> None:
    if value and value != "unknown" and value not in target:
        target.append(value)


def _status_counts(items: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        status = _string(item.get("status")).strip().lower() or "unknown"
        counts[status] = counts.get(status, 0) + 1
    return counts


def _stale_past_next_audit_count(
    items: list[dict[str, object]],
    as_of_date: date | None,
) -> tuple[int, bool]:
    if not items or as_of_date is None:
        return 0, bool(items)
    saw_next_audit = False
    stale = 0
    for item in items:
        raw = (
            _string(item.get("nextAudit"))
            or _string(item.get("next_audit"))
            or _string(item.get("next-audit"))
        )
        if not raw or raw == "unknown":
            continue
        saw_next_audit = True
        audit_date = _parse_date(raw)
        if audit_date is not None and audit_date < as_of_date:
            stale += 1
    return stale, not saw_next_audit


def _percent_known(items: list[dict[str, object]], predicate: Any) -> float | None:
    if not items:
        return None
    known = sum(1 for item in items if predicate(item))
    return round(known * 100 / len(items), 2)


def _has_known_owner(item: dict[str, object]) -> bool:
    owner = _string(item.get("owner")).strip().lower()
    return owner not in UNKNOWN_OWNER_VALUES


def _has_source_locator(item: dict[str, object]) -> bool:
    locator = _string(item.get("sourceLocator")) or _string(item.get("source_locator"))
    return bool(locator and locator != "unknown")


def _unanswered_competency_questions(questions: list[dict[str, object]]) -> int:
    unanswered = 0
    for question in questions:
        status = _string(question.get("answerStatus")) or _string(question.get("answer_status"))
        if status != "answered":
            unanswered += 1
    return unanswered


def _average_review_age_days(
    review_packages: list[dict[str, object]],
    as_of_date: date | None,
) -> tuple[float | None, bool]:
    wip_packages = [package for package in review_packages if _is_review_wip(package)]
    if not wip_packages or as_of_date is None:
        return None, bool(wip_packages)
    ages: list[int] = []
    missing = False
    for package in wip_packages:
        created_at = (
            _string(package.get("createdAt"))
            or _string(package.get("created_at"))
            or _string(package.get("generatedAt"))
            or _string(package.get("generated_at"))
        )
        created_date = _parse_date(created_at)
        if created_date is None:
            missing = True
            continue
        ages.append(max(0, (as_of_date - created_date).days))
    if not ages:
        return None, missing
    return round(sum(ages) / len(ages), 2), missing


def _is_review_wip(package: dict[str, object]) -> bool:
    status = _string(package.get("status")).strip().lower() or "pending"
    return status in {"pending", "needs-info"}


def _blocked_by_missing_owner(package: dict[str, object]) -> bool:
    owner = _string(package.get("owner")).strip().lower()
    if owner in UNKNOWN_OWNER_VALUES:
        return True
    for action in _mapping_list(package.get("requiredActions")):
        if _string(action.get("action")) == "needs-owner":
            return True
    return False


def _package_id(package: dict[str, object]) -> str:
    return _string(package.get("packageId")) or _string(package.get("package_id"))


def _parse_date(value: str) -> date | None:
    raw = _string(value).strip()
    if not raw or raw == "unknown":
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None


def _assert_system_analysis_result(result: dict[str, object]) -> None:
    if result.get("kind") != "systemAnalysisResult":
        raise ValueError("system-analysis result kind must be systemAnalysisResult")
    result_id = _string(result.get("resultId"))
    if not SYSTEM_ANALYSIS_RESULT_ID_RE.fullmatch(result_id):
        raise ValueError("system-analysis resultId must match sysres-*")
    if _string(result.get("analysisKind")) not in SYSTEM_ANALYSIS_KINDS:
        raise ValueError("system-analysis result analysisKind is unsupported")
    classification = _string(result.get("classification"))
    if classification not in SYSTEM_ANALYSIS_RESULT_CLASSIFICATIONS:
        raise ValueError("system-analysis result classification is unsupported")
    if result.get("reviewRequired") is not SYSTEM_ANALYSIS_REVIEW_REQUIRED[classification]:
        raise ValueError("system-analysis result reviewRequired does not match classification")
    if _string(result.get("nextAction")) != SYSTEM_ANALYSIS_NEXT_ACTION[classification]:
        raise ValueError("system-analysis result nextAction does not match classification")
    module_id = _string(result.get("moduleId"))
    if not MODULE_ID_RE.fullmatch(module_id):
        raise ValueError("system-analysis result moduleId has invalid format")
    summary = _string(result.get("summary"))
    if not summary or len(summary) > 1000:
        raise ValueError("system-analysis result summary is required")
    _assert_unique_string_list(result, "affectedIds")
    source_event_ids = _assert_unique_string_list(result, "sourceEventIds")
    for source_event_id in source_event_ids:
        if not SOURCE_EVENT_ID_RE.fullmatch(source_event_id):
            raise ValueError("system-analysis result sourceEventIds must match srcevt-*")
    safety = _mapping(result.get("safety"))
    if safety != _system_result_safety():
        raise ValueError("system-analysis result safety flags are invalid")


def _assert_unique_string_list(mapping: dict[str, object], field: str) -> list[str]:
    value = mapping.get(field)
    if not isinstance(value, list):
        raise ValueError(f"system-analysis result {field} must be a list")
    items = _list_strings(value)
    if len(items) != len(value):
        raise ValueError(f"system-analysis result {field} entries must be strings")
    if len(items) != len(set(items)):
        raise ValueError(f"system-analysis result {field} entries must be unique")
    return items


def _result_evidence_quality(value: object) -> dict[str, object]:
    evidence = _mapping(value)
    return {
        "highestReviewRisk": _string(evidence.get("highestReviewRisk")) or "unknown",
        "reviewEvidenceModes": _unique_string_list(evidence.get("reviewEvidenceModes")),
        "sourceAdequacy": _unique_string_list(evidence.get("sourceAdequacy")),
        "slaBands": _unique_string_list(evidence.get("slaBands")),
        "notes": _unique_string_list(evidence.get("notes")),
    }


def _system_result_risk(result: dict[str, object]) -> str:
    evidence = _mapping(result.get("evidenceQuality"))
    risk = _string(evidence.get("highestReviewRisk"))
    return risk if risk in {"low", "medium", "high"} else "medium"


def _system_result_source_risk(result: dict[str, object]) -> list[str]:
    evidence = _mapping(result.get("evidenceQuality"))
    adequacy = set(_list_strings(evidence.get("sourceAdequacy")))
    if not adequacy:
        return ["unknown"]
    if "conflicting" in adequacy:
        return ["conflicting-source"]
    if "stale" in adequacy:
        return ["stale-document"]
    if "missing-owner" in adequacy:
        return ["owner-unknown"]
    if adequacy.intersection({"partial", "insufficient"}):
        return ["partial-export"]
    return ["raw-source-unavailable"] if "sufficient" not in adequacy else ["no-known-risk"]


def _system_result_safety() -> dict[str, bool]:
    return {
        "noAcceptedMutation": True,
        "noAutoPromotion": True,
        "noSourceWriteback": True,
        "noRawPayload": True,
    }


def _unique_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item and item not in result:
            result.append(item)
    return result


def _unique_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return _sorted_unique(_string(item) for item in value)


def _sorted_unique(values: object) -> list[str]:
    result = []
    for value in values:
        if isinstance(value, str) and value and value != "unknown" and value not in result:
            result.append(value)
    return sorted(result)


def _has_variables_or_states(projection: dict[str, object]) -> bool:
    return bool(_mapping_list(projection.get("states"))) or _has_token(projection, "variable")


def _has_flows_or_transitions(projection: dict[str, object]) -> bool:
    if _workflow_transition_count(projection) > 0:
        return True
    return _has_token(projection, "flow")


def _has_loops_or_unknown_loops(projection: dict[str, object]) -> bool:
    return _has_token(projection, "loop") or _unknown_field_mentions(projection, "loop")


def _has_delays(projection: dict[str, object]) -> bool:
    return bool(_mapping_list(projection.get("delays"))) or _has_token(projection, "delay")


def _has_goal(projection: dict[str, object]) -> bool:
    objective = _string(projection.get("objective")).strip().lower()
    return bool(objective and objective != "unknown")


def _has_equations(projection: dict[str, object]) -> bool:
    for metric in _mapping_list(projection.get("metrics")):
        if _string(metric.get("formula")).strip():
            return True
    return _has_token(projection, "equation")


def _has_measurable_goal_or_contradiction(projection: dict[str, object]) -> bool:
    return _has_measurable_target(projection) or _has_contradiction(projection)


def _has_measurable_target(projection: dict[str, object]) -> bool:
    objective = _string(projection.get("objective"))
    if re.search(r"\d", objective):
        return True
    return any(_string(metric.get("formula")).strip() for metric in _mapping_list(projection.get("metrics")))


def _has_stated_vs_enacted_goal_check(projection: dict[str, object]) -> bool:
    text = _projection_text(projection)
    return "stated" in text and "enacted" in text and "goal" in text


def _has_workflow(projection: dict[str, object]) -> bool:
    workflow = _mapping(projection.get("workflow"))
    return bool(_mapping_list(workflow.get("workflows"))) or bool(_list_strings(workflow.get("workflowIds")))


def _has_throughput_unit(projection: dict[str, object]) -> bool:
    return _has_token_in_sections(projection, "throughput", ["metrics", "rules", "constraints"])


def _has_wip_or_queue_evidence(projection: dict[str, object]) -> bool:
    return _has_token_in_sections(projection, "wip", ["metrics", "rules", "constraints"]) or _has_token_in_sections(
        projection,
        "queue",
        ["metrics", "rules", "constraints"],
    )


def _has_capacity_or_rate(projection: dict[str, object]) -> bool:
    return _has_token_in_sections(projection, "capacity", ["metrics", "rules", "constraints"]) or _has_token_in_sections(
        projection,
        "rate",
        ["metrics", "rules", "constraints"],
    )


def _has_rules_or_policies(projection: dict[str, object]) -> bool:
    return bool(_mapping_list(projection.get("rules"))) or _has_token(projection, "policy")


def _has_contradiction(projection: dict[str, object]) -> bool:
    text = _projection_text(projection)
    return "contradiction" in text or ("improving" in text and "worsens" in text)


def _has_evidence_quality(projection: dict[str, object]) -> bool:
    evidence = _mapping(projection.get("evidenceQuality"))
    return bool(
        _list_strings(evidence.get("reviewEvidenceModes"))
        or _list_strings(evidence.get("sourceAdequacy"))
        or _list_strings(evidence.get("slaBands"))
    )


def _has_refutable_branch_or_missing_data(projection: dict[str, object]) -> bool:
    return _has_token(projection, "branch") or bool(_mapping_list(projection.get("unknowns")))


def _workflow_transition_count(projection: dict[str, object]) -> int:
    workflow = _mapping(projection.get("workflow"))
    count = 0
    for item in _mapping_list(workflow.get("workflows")):
        count += len(_mapping_list(item.get("transitions")))
    return count


def _unknown_field_mentions(projection: dict[str, object], token: str) -> bool:
    token = token.lower()
    for item in _mapping_list(projection.get("unknowns")):
        if token in _string(item.get("field")).lower() or token in _string(item.get("reason")).lower():
            return True
    return False


def _has_token(projection: dict[str, object], token: str) -> bool:
    text = re.sub(r"[-_/]+", " ", _projection_text(projection))
    normalized = re.sub(r"[-_/]+", " ", token.lower()).strip()
    if not normalized:
        return False
    if " " in normalized:
        return re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", text) is not None

    variants = {normalized}
    if not normalized.endswith("s"):
        variants.add(normalized + "s")
    if normalized.endswith("y"):
        variants.add(normalized[:-1] + "ies")
    return any(re.search(rf"(?<!\w){re.escape(variant)}(?!\w)", text) for variant in variants)


def _has_token_in_sections(projection: dict[str, object], token: str, keys: list[str]) -> bool:
    return _has_token({key: projection.get(key) for key in keys}, token)


def _projection_text(value: object, *, include_unknowns: bool = False) -> str:
    strings: list[str] = []

    def walk(item: object) -> None:
        if isinstance(item, str):
            strings.append(item.lower())
            return
        if isinstance(item, list):
            for child in item:
                walk(child)
            return
        if isinstance(item, dict):
            for key, child in item.items():
                if not include_unknowns and _projection_text_excluded_key(key):
                    continue
                walk(child)

    walk(value)
    return " ".join(strings)


def _projection_text_excluded_key(key: str) -> bool:
    lowered = key.lower()
    return (
        lowered in {"analysisintent", "unknowns", "modelids", "sourcesummary"}
        or lowered == "id"
        or lowered.endswith("id")
        or lowered.endswith("ids")
    )


def _list_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _recommended_question(kind: str, missing_field: str) -> str:
    labels = {
        "system-diagram-coach": "What accepted model field supplies",
        "stock-flow-builder": "What source-backed value supplies",
        "leverage-finder": "What measurable target supplies",
        "constraint-finder": "What workflow evidence supplies",
        "triz-dissolve": "What explicit contradiction supplies",
        "why-tree": "What evidence supplies",
    }
    prefix = labels.get(kind, "What source-backed input supplies")
    return f"{prefix} `{missing_field}`?"


def _binding_counts(bindings: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for binding in bindings:
        item_id = _string(binding.get("item_id"))
        if item_id:
            counts[item_id] = counts.get(item_id, 0) + 1
    return counts


def _highest_risk(packages: list[dict[str, object]]) -> str:
    rank = {"low": 0, "medium": 1, "high": 2}
    highest = "low"
    for package in packages:
        risk = _string(package.get("risk"))
        if rank.get(risk, -1) > rank[highest]:
            highest = risk
    return highest if packages else "none"


def _safe_attributes(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            continue
        if key in FORBIDDEN_ATTRIBUTE_KEYS:
            continue
        if isinstance(item, (str, int, float, bool)) or item is None:
            safe[key] = item
    return safe


def _mapping_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string(value: object) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)

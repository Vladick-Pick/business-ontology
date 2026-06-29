#!/usr/bin/env python3
"""Store/export projections for ontology canvas, bindings, and instance graph.

The functions in this module are read-only shape builders. They do not query
external sources, mutate accepted truth, or expose raw source payloads.
"""
from __future__ import annotations

from typing import Any


FORBIDDEN_ATTRIBUTE_KEYS = {
    "raw_payload",
    "rawPayload",
    "raw_value",
    "rawValue",
    "hidden_reasoning",
    "credential_value",
    "secret_value",
}


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

#!/usr/bin/env python3
"""Render an accepted workflow from the SQLite operational store."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.operational_store import OperationalStore  # noqa: E402


def render_workflow_markdown(workflow: dict[str, object]) -> str:
    title = _string(workflow.get("name")) or _string(workflow.get("workflow_id")) or "Workflow"
    sections = [
        f"# {title}",
        "",
        _render_mermaid(workflow),
        "",
        "## Participants",
        "",
        _table(
            ["Role", "Type"],
            [
                [
                    _string(participant.get("role_id")),
                    _string(participant.get("participant_type")),
                ]
                for participant in _mapping_list(workflow.get("participants"))
            ],
        ),
        "",
        "## Steps",
        "",
        _table(
            ["#", "Actor", "Action", "Inputs", "Outputs"],
            [
                [
                    str(step.get("ordinal", "")),
                    _string(step.get("actor_id")),
                    _string(step.get("action")),
                    ", ".join(_string_list(step.get("input_ids"))),
                    ", ".join(_string_list(step.get("output_ids"))),
                ]
                for step in _mapping_list(workflow.get("steps"))
            ],
        ),
        "",
        "## Exceptions",
        "",
        _table(
            ["Condition", "Handling", "Severity"],
            [
                [
                    _string(exception.get("condition")),
                    _string(exception.get("handling")),
                    _string(exception.get("severity")),
                ]
                for exception in _mapping_list(workflow.get("exceptions"))
            ],
        ),
        "",
        "## Metrics",
        "",
        _table(
            ["Metric", "Role"],
            [
                [
                    _string(metric.get("metric_id")),
                    _string(metric.get("role")),
                ]
                for metric in _mapping_list(workflow.get("metrics"))
            ],
        ),
        "",
    ]
    return "\n".join(sections)


def _render_mermaid(workflow: dict[str, object]) -> str:
    state_ids = _ordered_state_ids(workflow)
    node_ids = {state_id: f"s{index}" for index, state_id in enumerate(state_ids, 1)}
    lines = ["```mermaid", "flowchart LR"]
    for state_id in state_ids:
        lines.append(f'  {node_ids[state_id]}["{_mermaid_label(state_id)}"]')
    for transition in _mapping_list(workflow.get("transitions")):
        from_state = _string(transition.get("from_state_id"))
        to_state = _string(transition.get("to_state_id"))
        if not from_state or not to_state:
            continue
        trigger = _string(transition.get("trigger"))
        authority = _string(transition.get("authority_id"))
        label = " / ".join(part for part in [trigger, authority] if part)
        lines.append(f"  {node_ids[from_state]} -->|{_mermaid_label(label)}| {node_ids[to_state]}")
    lines.append("```")
    return "\n".join(lines)


def _ordered_state_ids(workflow: dict[str, object]) -> list[str]:
    state_ids: list[str] = []
    for state_id in [
        _string(workflow.get("start_state_id")),
        *[
            _string(transition.get("from_state_id"))
            for transition in _mapping_list(workflow.get("transitions"))
        ],
        *[
            _string(transition.get("to_state_id"))
            for transition in _mapping_list(workflow.get("transitions"))
        ],
        _string(workflow.get("end_state_id")),
    ]:
        if state_id and state_id not in state_ids:
            state_ids.append(state_id)
    return state_ids


def _table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_No records._"
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    body = [
        "| " + " | ".join(_markdown_cell(value) for value in row) + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def _markdown_cell(value: str) -> str:
    return value.replace("\n", " ").replace("|", "\\|")


def _mermaid_label(value: str) -> str:
    return value.replace("\n", " ").replace('"', "'")


def _string(value: object) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _mapping_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True, type=Path, help="Path to operational SQLite store.")
    parser.add_argument("--workflow-id", required=True, help="Accepted workflow id to render.")
    parser.add_argument("--format", choices=["mermaid"], default="mermaid")
    parser.add_argument("--out", type=Path, help="Optional Markdown output path.")
    args = parser.parse_args(argv)

    store = OperationalStore.connect(args.store)
    try:
        store.initialize()
        workflow = store.get_accepted_workflow(args.workflow_id)
    finally:
        store.close()

    if workflow is None:
        print(f"workflow not found: {args.workflow_id}", file=sys.stderr)
        return 2

    output = render_workflow_markdown(workflow)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

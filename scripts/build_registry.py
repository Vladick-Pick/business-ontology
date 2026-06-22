#!/usr/bin/env python3
"""Compile accepted ontology cards into registry JSON.

The registry is a derived graph. Cards are the source of truth; this compiler
validates them first, skips staged proposals, emits accepted nodes only, and
decomposes interface hyperedges into deterministic structural edges.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import sys
from typing import Any

import links_validate


STRUCTURAL_EDGE_TYPES = {
    "supplier": "has-supplier",
    "customer": "has-customer",
    "subject": "has-subject",
}

OPEN_QUESTION_FILENAMES = {
    "08-drift-and-open-questions.md",
}


def is_compilable_status(card: links_validate.Card) -> bool:
    status = card.data.get("status")
    if card.data.get("type") == "decision":
        return status in {"accepted", "implemented"}
    return status == "accepted"


def read_text(root: Path, rel: str) -> str:
    path_part = rel.split(":", 1)[0]
    return (root / path_part).read_text(encoding="utf-8")


def extract_label(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            label = line[2:].strip()
            if label:
                return label
    return fallback


def validate_root(root: Path) -> tuple[int, str, dict[str, links_validate.Card]]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        exit_code = links_validate.main([str(root)])

    errors: list[str] = []
    cards = links_validate.collect_cards(str(root), str(root), errors)
    if errors and exit_code == 0:
        exit_code = 1
    return exit_code, buffer.getvalue().strip(), cards


def make_node(root: Path, card: links_validate.Card) -> dict[str, Any]:
    text = read_text(root, card.path)
    attrs = card.data.get("attrs") if isinstance(card.data.get("attrs"), dict) else {}
    return {
        "id": card.cid,
        "type": card.data.get("type"),
        "label": extract_label(text, card.cid),
        "status": card.data.get("status"),
        "source": card.data.get("source"),
        "owner": card.data.get("owner"),
        "last-reviewed": card.data.get("last-reviewed"),
        "next-audit": card.data.get("next-audit"),
        "attrs": attrs,
        "card": card.path.split(":", 1)[0],
    }


def make_edge(
    from_id: str,
    edge_type: str,
    to_id: str,
    attrs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": f"{from_id}::{edge_type}::{to_id}",
        "from": from_id,
        "to": to_id,
        "type": edge_type,
        "attrs": attrs or {},
    }


def authored_edges(
    cards: dict[str, links_validate.Card],
    accepted_ids: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    edges: list[dict[str, Any]] = []
    warnings: list[str] = []
    for card in cards.values():
        if card.cid not in accepted_ids:
            continue
        for relation, targets in card.links.items():
            for target in targets:
                if target not in accepted_ids:
                    warnings.append(
                        f"{card.path}: skipped authored edge {card.cid}::{relation}::{target} "
                        "because target is not an accepted node"
                    )
                    continue
                edges.append(make_edge(card.cid, relation, target, {"source": "authored"}))
    return edges, warnings


def interface_edges(
    cards: dict[str, links_validate.Card],
    accepted_ids: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    edges: list[dict[str, Any]] = []
    warnings: list[str] = []
    for card in cards.values():
        if card.cid not in accepted_ids or card.data.get("type") != "interface":
            continue
        attrs = card.data.get("attrs")
        if not isinstance(attrs, dict):
            continue
        participants = attrs.get("participants")
        if not isinstance(participants, dict):
            continue

        participant_ids: dict[str, list[str]] = {}
        for role, edge_type in STRUCTURAL_EDGE_TYPES.items():
            ids = participants.get(role)
            if not isinstance(ids, list):
                continue
            participant_ids[role] = []
            for target in ids:
                if target not in accepted_ids:
                    warnings.append(
                        f"{card.path}: skipped {edge_type} -> {target} "
                        "because participant is not an accepted node"
                    )
                    continue
                participant_ids[role].append(target)
                edges.append(
                    make_edge(
                        card.cid,
                        edge_type,
                        target,
                        {"source": "interface-decomposition", "interface": card.cid},
                    )
                )

        suppliers = participant_ids.get("supplier", [])
        customers = participant_ids.get("customer", [])
        subjects = participant_ids.get("subject", [])
        for supplier in suppliers:
            for customer in customers:
                for subject in subjects or [None]:
                    attrs_payload: dict[str, Any] = {
                        "source": "interface-decomposition",
                        "interface": card.cid,
                    }
                    if subject:
                        attrs_payload["subject"] = subject
                    edges.append(make_edge(supplier, "supplies-to", customer, attrs_payload))

    return edges, warnings


def collect_open_questions(root: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    skip_dirs = set(links_validate.SKIP_DIRS) | {links_validate.STAGED_DIR}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for filename in filenames:
            if filename in OPEN_QUESTION_FILENAMES or "open-question" in filename:
                path = Path(dirpath) / filename
                entries.append(
                    {
                        "file": str(path.relative_to(root)),
                        "text": path.read_text(encoding="utf-8"),
                    }
                )
    return sorted(entries, key=lambda item: item["file"])


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def compile_registry(root: Path, out_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    validator_exit, validator_output, cards = validate_root(root)
    if validator_exit != 0:
        raise ValueError(f"validation failed before registry build:\n{validator_output}")

    accepted_cards = {
        cid: card for cid, card in cards.items() if is_compilable_status(card)
    }
    accepted_ids = set(accepted_cards)

    nodes = [make_node(root, card) for card in accepted_cards.values()]
    authored, authored_warnings = authored_edges(cards, accepted_ids)
    generated, generated_warnings = interface_edges(cards, accepted_ids)
    edges = authored + generated

    nodes.sort(key=lambda node: node["id"])
    edges.sort(key=lambda edge: (edge["type"], edge["from"], edge["to"], edge["id"]))

    open_questions = collect_open_questions(root)
    manifest = {
        "generated-at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source-root": str(root),
        "validator-status": "pass",
        "validator-output": validator_output,
        "card-count": len(cards),
        "compiled-card-count": len(accepted_cards),
        "node-count": len(nodes),
        "edge-count": len(edges),
        "open-question-count": len(open_questions),
        "warnings": authored_warnings + generated_warnings,
        "outputs": {
            "nodes": "nodes.json",
            "edges": "edges.json",
            "manifest": "manifest.json",
            "open-questions": "open_questions.json" if open_questions else None,
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "nodes.json", nodes)
    write_json(out_dir / "edges.json", edges)
    write_json(out_dir / "manifest.json", manifest)
    if open_questions:
        write_json(out_dir / "open_questions.json", open_questions)

    return manifest, nodes, edges


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile ontology cards into registry JSON.")
    parser.add_argument("root", help="Ontology root to compile")
    parser.add_argument(
        "--out",
        default="registry",
        help="Output directory for generated registry JSON (default: registry)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    root = Path(args.root).resolve()
    out_dir = Path(args.out).resolve()

    try:
        manifest, _, _ = compile_registry(root, out_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Registry written to {out_dir}")
    print(f"Nodes: {manifest['node-count']}  |  edges: {manifest['edge-count']}")
    print(manifest["validator-output"])
    if manifest["warnings"]:
        print(f"Warnings: {len(manifest['warnings'])}")
        for warning in manifest["warnings"]:
            print(f"  WARNING: {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

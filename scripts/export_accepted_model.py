#!/usr/bin/env python3
"""Export the current accepted operational model without raw source payloads.

The operational store remains authoritative. This exporter produces a
deterministic, public-safe context snapshot for agents, the viewer, and Git
portability. It never copies evidence excerpts, locators, chat bodies, or
transcript payloads.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
for import_root in (SCRIPT_DIR, REPO_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from runtime.operational_store import OperationalStore  # noqa: E402


CARD_TYPES = {
    "business",
    "production-system",
    "role",
    "artifact",
    "tool",
    "metric",
    "state",
    "process",
    "interface",
    "decision",
    "term",
}
CARD_STATUSES = {"accepted", "candidate", "hypothesis", "conflict", "deprecated", "unknown"}
DECISION_STATUSES = {"proposed", "accepted", "implemented", "superseded", "retired"}
STATUS_RANK = {
    "unknown": 0,
    "hypothesis": 1,
    "proposed": 2,
    "candidate": 2,
    "conflict": 2,
    "accepted": 3,
    "implemented": 3,
    "superseded": 3,
    "retired": 3,
    "deprecated": 3,
}
PRIVATE_KEY_TOKENS = {
    "excerpt",
    "locator",
    "rawpayload",
    "rawtranscript",
    "transcriptbody",
    "messagebody",
    "chatbody",
    "replytext",
    "sourceref",
    "sourcemessageref",
    "messageref",
    "replytomessageref",
    "inboundmessageref",
}


class AcceptedModelExportError(ValueError):
    """Raised when applied state cannot be projected safely."""


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    _write_text_atomic(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _public_value(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _public_value(item)
            for key, item in value.items()
            if "".join(character for character in str(key).lower() if character.isalnum())
            not in PRIVATE_KEY_TOKENS
        }
    if isinstance(value, list):
        return [_public_value(item) for item in value]
    return value


def _iso_date(value: object) -> date:
    text = str(value or "").strip()
    if text:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
    return datetime.now(timezone.utc).date()


def _audit_date(reviewed: date, status: str) -> date:
    days = 30 if status in {"unknown", "hypothesis", "conflict", "proposed"} else 90
    return reviewed + timedelta(days=days)


def _card_status(card_type: str, item_status: object, candidate_status: object) -> str:
    item_value = str(item_status or "unknown")
    candidate_value = str(candidate_status or "unknown")
    if card_type == "decision":
        if item_value in DECISION_STATUSES:
            return item_value
        if item_value == "accepted":
            return "accepted"
        return candidate_value if candidate_value in DECISION_STATUSES else "proposed"
    if item_value in CARD_STATUSES:
        return item_value
    return candidate_value if candidate_value in CARD_STATUSES else "unknown"


def _card_type(candidate: dict[str, object] | None, item: dict[str, object]) -> str:
    candidate_type = str((candidate or {}).get("type") or "")
    if candidate_type in CARD_TYPES:
        return candidate_type
    kind = str(item.get("kind") or "")
    return kind if kind in CARD_TYPES else "term"


def _summary(candidate: dict[str, object] | None, item: dict[str, object]) -> str:
    value = str((candidate or {}).get("summary") or item.get("name") or item.get("id") or "")
    return " ".join(value.split())[:1000] or "Accepted model item."


def _candidate_metadata(store: OperationalStore) -> tuple[
    dict[str, dict[str, object]],
    list[dict[str, object]],
    list[str],
]:
    rows = store._connection.execute(  # package payload is the immutable reviewed source
        """
        SELECT package_id, module_id, payload_json, updated_at
          FROM model_change_packages
         WHERE status = 'applied'
         ORDER BY updated_at ASC, package_id ASC
        """
    ).fetchall()
    candidates: dict[str, dict[str, object]] = {}
    packages: list[dict[str, object]] = []
    processed_event_ids: list[str] = []
    for row in rows:
        package = json.loads(str(row["payload_json"]))
        if not isinstance(package, dict):
            continue
        package_id = str(row["package_id"])
        package_decision_ids: set[str] = set()
        projected_count = 0
        for change in package.get("changes") or []:
            if not isinstance(change, dict):
                continue
            accepted = change.get("acceptedItem")
            accepted_workflow = change.get("acceptedWorkflow")
            candidate = change.get("candidateCard")
            if isinstance(accepted, dict):
                item = accepted.get("item") if isinstance(accepted.get("item"), dict) else accepted
                item_id = str(item.get("id") or item.get("item_id") or "")
                decision_id = str(item.get("decision_id") or "")
                if decision_id:
                    package_decision_ids.add(decision_id)
                if item_id and isinstance(candidate, dict):
                    candidates[item_id] = dict(candidate)
                if item_id:
                    projected_count += 1
            if isinstance(accepted_workflow, dict):
                workflow = (
                    accepted_workflow.get("workflow")
                    if isinstance(accepted_workflow.get("workflow"), dict)
                    else accepted_workflow
                )
                workflow_id = str(workflow.get("workflow_id") or "")
                decision_id = str(workflow.get("decision_id") or "")
                if decision_id:
                    package_decision_ids.add(decision_id)
                if workflow_id and isinstance(candidate, dict):
                    candidates[workflow_id] = dict(candidate)
        for event_id in package.get("sourceEventIds") or []:
            value = str(event_id)
            if value and value not in processed_event_ids:
                processed_event_ids.append(value)
        packages.append(
            {
                "packageId": package_id,
                "moduleId": str(row["module_id"]),
                "ontologyRevision": str(package.get("ontologyRevision") or "unknown"),
                "decisionIds": sorted(package_decision_ids),
                "itemCount": projected_count,
                "appliedAt": str(row["updated_at"]),
            }
        )
    return candidates, packages, processed_event_ids


def _project_card(
    item: dict[str, object],
    candidate: dict[str, object] | None,
) -> dict[str, object]:
    item_id = str(item.get("id") or item.get("item_id") or "").strip()
    if not item_id:
        raise AcceptedModelExportError("accepted item has no id")
    card_type = _card_type(candidate, item)
    status = _card_status(card_type, item.get("status"), (candidate or {}).get("status"))
    reviewed = _iso_date(item.get("last_verified_at"))
    summary = _summary(candidate, item)
    links = _public_value((candidate or {}).get("links") or {})
    attrs = _public_value((candidate or {}).get("attrs") or {})
    if not isinstance(links, dict) or not all(
        isinstance(targets, list) and all(isinstance(target, str) for target in targets)
        for targets in links.values()
    ):
        raise AcceptedModelExportError(f"accepted item {item_id} has invalid projected links")
    if not isinstance(attrs, dict):
        raise AcceptedModelExportError(f"accepted item {item_id} has invalid projected attrs")
    return {
        "id": item_id,
        "type": card_type,
        "status": status,
        "source": str((candidate or {}).get("source") or item.get("source_id") or "unknown"),
        "owner": str((candidate or {}).get("owner") or "unknown"),
        "lastReviewed": reviewed.isoformat(),
        "nextAudit": _audit_date(reviewed, status).isoformat(),
        "volatility": "high" if status in {"unknown", "hypothesis", "conflict", "proposed"} else "medium",
        "evidence": [],
        "aliases": [],
        "attrs": attrs,
        "links": links,
        "title": summary[:180],
        "sections": [{"heading": "Summary", "body": summary}],
        "file": f"ontology/accepted-context.json#{item_id}",
    }


def _project_workflow(
    workflow: dict[str, object],
    candidate: dict[str, object] | None,
) -> dict[str, object]:
    item = {
        "id": workflow.get("workflow_id"),
        "kind": "process",
        "status": workflow.get("status"),
        "source_id": workflow.get("source_id"),
        "last_verified_at": workflow.get("last_verified_at"),
        "name": workflow.get("name"),
    }
    return _project_card(item, candidate)


def _sources(cards: list[dict[str, object]]) -> list[dict[str, object]]:
    statuses: dict[str, list[str]] = defaultdict(list)
    for card in cards:
        statuses[str(card.get("source") or "unknown")].append(str(card.get("status") or "unknown"))
    result: list[dict[str, object]] = []
    for source_id, source_statuses in sorted(statuses.items()):
        if source_id == "unknown":
            continue
        strongest = max(source_statuses, key=lambda item: STATUS_RANK.get(item, 0))
        trust = "candidate" if strongest == "proposed" else strongest
        if trust in {"implemented", "superseded", "retired"}:
            trust = "accepted"
        result.append(
            {
                "id": source_id,
                "trust": trust if trust in CARD_STATUSES else "unknown",
                "owner": "model-reviewers",
                "accessMode": "derived-reference",
                "readPolicy": "readOnly=true; piiExcluded=true; rawPayloadAccess=false",
                "meaning": "Source registered by an applied human-reviewed model package; raw content remains outside this export.",
            }
        )
    return result


def build_accepted_snapshot(store: OperationalStore, *, module: str | None = None) -> dict[str, object]:
    candidates, packages, processed_event_ids = _candidate_metadata(store)
    if not packages:
        raise AcceptedModelExportError("operational store has no applied model change package")
    cards = [
        _project_card(item, candidates.get(str(item.get("id") or item.get("item_id") or "")))
        for item in store.list_accepted_items()
    ]
    existing_ids = {str(card["id"]) for card in cards}
    for workflow in store.list_accepted_workflows():
        workflow_id = str(workflow.get("workflow_id") or "")
        if workflow_id and workflow_id not in existing_ids:
            cards.append(_project_workflow(workflow, candidates.get(workflow_id)))
    cards.sort(key=lambda card: (str(card["type"]), str(card["id"])))
    if not cards:
        raise AcceptedModelExportError("applied packages produced no current accepted model cards")
    revision_payload = {
        "cards": cards,
        "packages": packages,
        "processedEventIds": processed_event_ids,
    }
    revision = "store:sha256:" + hashlib.sha256(
        _json_text(revision_payload).encode("utf-8")
    ).hexdigest()
    as_of = max(str(card["lastReviewed"]) for card in cards)
    generated_at = max(
        str(package.get("appliedAt") or "") for package in packages
    ) or f"{as_of}T00:00:00Z"
    return {
        "module": module or str(packages[-1].get("moduleId") or "unknown"),
        "revision": revision,
        "ontologyRevision": revision,
        "asOf": as_of,
        "generatedAt": generated_at,
        "processedEventIds": processed_event_ids,
        "cards": cards,
        "sources": _sources(cards),
        "appliedPackages": packages,
    }


def _source_map(snapshot: dict[str, object]) -> str:
    lines = [
        "# Source Map",
        "",
        "Generated from the current applied model snapshot. Raw payloads remain outside this repository.",
        "",
        "| Source id | Trust | Owner | Access mode | Read policy | Meaning |",
        "|---|---|---|---|---|---|",
    ]
    for source in snapshot.get("sources") or []:
        assert isinstance(source, dict)
        lines.append(
            "| `{id}` | {trust} | {owner} | {accessMode} | {readPolicy} | {meaning} |".format(
                **source
            )
        )
    return "\n".join(lines) + "\n"


def _accepted_summary(snapshot: dict[str, object]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for card in snapshot.get("cards") or []:
        assert isinstance(card, dict)
        counts[str(card.get("status") or "unknown")] += 1
    status_text = ", ".join(f"{key}: {value}" for key, value in sorted(counts.items()))
    header = (
        "# Accepted Model Snapshot\n\n"
        f"- Revision: `{snapshot['revision']}`\n"
        f"- As of: `{snapshot['asOf']}`\n"
        f"- Cards: `{len(snapshot.get('cards') or [])}` ({status_text})\n"
        f"- Applied packages: `{len(snapshot.get('appliedPackages') or [])}`\n\n"
        "The complete machine-readable snapshot is `ontology/accepted-context.json`. "
        "It contains only projected model content; raw chats, transcripts, evidence excerpts, "
        "routing identifiers, and credentials are excluded.\n"
    )
    rows = ["", "## Cards", "", "| Card | Type | Status |", "|---|---|---|"]
    for card in snapshot.get("cards") or []:
        assert isinstance(card, dict)
        rows.append(f"| `{card.get('id')}` | {card.get('type')} | {card.get('status')} |")
    return header + "\n".join(rows) + "\n"


def _changelog(snapshot: dict[str, object]) -> str:
    lines = [
        "# Accepted Model Changelog",
        "",
        "| Package | Reviewed revision | Decision | Items |",
        "|---|---|---|---:|",
    ]
    for package in snapshot.get("appliedPackages") or []:
        assert isinstance(package, dict)
        decisions = ", ".join(str(item) for item in package.get("decisionIds") or []) or "unknown"
        lines.append(
            f"| `{package.get('packageId')}` | `{package.get('ontologyRevision')}` | "
            f"`{decisions}` | {package.get('itemCount', 0)} |"
        )
    return "\n".join(lines) + "\n"


def export_snapshot(
    store: OperationalStore,
    *,
    model_root: Path,
    module: str | None = None,
) -> dict[str, object]:
    snapshot = build_accepted_snapshot(store, module=module)
    _write_json_atomic(model_root / "ontology" / "accepted-context.json", snapshot)
    _write_text_atomic(model_root / "02-source-map.md", _source_map(snapshot))
    _write_text_atomic(model_root / "ACCEPTED_MODEL.md", _accepted_summary(snapshot))
    _write_text_atomic(model_root / "09-changelog.md", _changelog(snapshot))
    return snapshot


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export current accepted model from SQLite.")
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--module")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    store_path = args.store.resolve()
    if not store_path.is_file():
        print(json.dumps({"status": "error", "error": "operational store does not exist"}))
        return 2
    try:
        with OperationalStore.connect(store_path) as store:
            store.initialize()
            snapshot = export_snapshot(
                store,
                model_root=args.model_root.resolve(),
                module=args.module,
            )
    except (AcceptedModelExportError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    report = {
        "status": "exported",
        "revision": snapshot["revision"],
        "cardCount": len(snapshot["cards"]),
        "modelRoot": str(args.model_root.resolve()),
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(f"accepted model exported: {report['cardCount']} cards, {report['revision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

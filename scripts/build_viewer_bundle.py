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
        "attrs": attrs,
        "links": {rel: list(targets) for rel, targets in links.items()},
        "title": title or _scalar(data.get("id")),
        "sections": sections,
        "file": str(path.relative_to(root)),
    }


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


def _health(cards: list[dict], sources: list[dict], as_of: str | None) -> dict:
    counts: dict[str, int] = {}
    for card in cards:
        counts[card["status"]] = counts.get(card["status"], 0) + 1
    total = len(cards) or 1
    owned = sum(1 for c in cards if c["owner"].lower() not in UNKNOWN_OWNER)
    source_ids = {s["id"] for s in sources}
    sourced = sum(
        1
        for c in cards
        if c["source"] and (c["source"] in source_ids or c["source"] == "unknown")
    )
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
    edges = [
        {"from": c["id"], "to": target, "type": rel}
        for c in cards
        for rel, targets in c["links"].items()
        for target in targets
    ]
    sources = _read_source_map(root)
    return {
        "module": module,
        "companyModelLanguage": company_model_language,
        "packageVersion": package_version,
        "packageCommit": package_commit,
        "modelRevision": model_revision or revision,
        "sourceReadiness": source_readiness or empty_source_readiness(),
        "openHumanRequestCount": open_human_request_count,
        "validationStatus": validation_status,
        "revision": revision,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cards": cards,
        "edges": edges,
        "sources": sources,
        "openQuestions": _read_open_questions(root),
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
    parser.add_argument("--validation-status", default="not-run", help="Model validation status.")
    args = parser.parse_args(argv[1:])

    root = Path(args.root).resolve()
    module = args.module or root.name
    source_readiness = None
    if args.source_readiness_json:
        source_readiness = json.loads(Path(args.source_readiness_json).read_text(encoding="utf-8"))
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

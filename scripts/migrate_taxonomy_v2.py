#!/usr/bin/env python3
"""Rewrite v1 card frontmatter into data model v2 shape.

Data model v2 is specified in docs/specs/2026-07-02-data-model-v2.md,
section 6 ("Migration v1 -> v2"). This script applies that table
mechanically to frontmatter only: it never touches card ids (so existing
links keep resolving) and never touches the card body / prose below the
frontmatter block.

Migration table applied:

  concept, attrs.subtype: product|service  -> artifact, attrs.kind: <subtype>
  concept, attrs.subtype: metric           -> metric (formula/unit/direction/
                                               binding filled with "unknown"
                                               until a human enriches them)
  concept, attrs.subtype: role|position    -> role, attrs.kind: <subtype>
  concept, attrs.subtype: tool|system      -> tool, attrs.kind: <subtype>
  concept, attrs.subtype: regulation|rule|authority
                                            -> decision, attrs.norm-kind: regulated
                                               (a decision needs the 12 kinetic
                                               fields the spec requires; this
                                               script fills any missing one with
                                               "unknown" rather than inventing
                                               a value, and flags the card for
                                               review because a synthesized
                                               decision card is a judgment call
                                               a human should confirm)
  concept, attrs.subtype: state            -> left alone; flagged as
                                               "requires human review: possible
                                               duplicate of a state card" (the
                                               spec calls this a manual merge,
                                               not a mechanical one)
  concept, attrs.subtype: module           -> left alone; flagged as
                                               "requires human review: possible
                                               duplicate of a business card"
  concept, attrs.subtype: fact|other       -> left alone; flagged as
                                               "requires human review: term or
                                               artifact, a human decides"
  concept, any other/missing subtype       -> left alone; flagged as
                                               "requires human review: unknown
                                               v1 subtype, no v2 mapping"
  type: module                             -> type: business
  attrs.parent-module (a real id)          -> merged into links.part-of
  attrs.submodules (real ids)              -> each becomes a links.part-of
                                               entry on the child, so this
                                               script also has to touch the
                                               child cards named in
                                               submodules; if a listed child
                                               is not found in the ontology
                                               root, that name is reported
                                               and left untouched
  links.in-state                           -> links.lifecycle

Anything not in this table (production-system, interface, process, state,
decision cards that are not synthesized from a concept subtype, and any
concept subtype already covered above) is left byte-for-byte untouched.

Ids are never renamed, so every existing link in the ontology keeps
resolving after migration -- this is the whole point of doing the rewrite
in place rather than replacing cards.

Usage:
  python3 scripts/migrate_taxonomy_v2.py <ontology-root> [--dry-run]

--dry-run prints the migration plan (one line per card that would change,
plus the human-review queue) and writes nothing. Without --dry-run, the
script rewrites files in place and prints the same report afterward.
Running the script twice in a row is a no-op the second time: every
transformation checks the current type/subtype/links before touching
anything, so an already-migrated card has nothing left to match.

Exit codes: 0 when every card's frontmatter parsed cleanly (including
"nothing to do" -- no v1 fields matched the table), 1 if at least one card's
frontmatter could not be parsed. A parse failure on one card does not block
migrating the others; it is reported in the "Unresolved" section and the
migration still runs on every card that did parse.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import sys
from typing import Any

import links_validate


# concept attrs.subtype -> (new type, attrs.kind value or None)
SUBTYPE_TO_ARTIFACT = {"product": "product", "service": "service"}
SUBTYPE_TO_ROLE = {"role": "role", "position": "position"}
SUBTYPE_TO_TOOL = {"tool": "tool", "system": "system"}
SUBTYPE_TO_DECISION = {"regulation", "rule", "authority"}
SUBTYPE_REVIEW_QUEUE = {"fact", "other"}
SUBTYPE_MANUAL_MERGE = {"state", "module"}

DECISION_KINETIC_FIELDS = [
    "irreversible",
    "episode",
    "scope",
    "decision-owner",
    "transition-authority",
    "measurement-convention",
    "affected-workflows",
    "affected-kpis",
    "propagation-sla",
    "override-policy",
    "exception-path",
    "blast-radius",
]

FRONTMATTER_RE = links_validate.FRONTMATTER_RE


@dataclass
class MigrationEntry:
    path: str
    change: str
    detail: str = ""


@dataclass
class MigrationReport:
    changed: list[MigrationEntry] = field(default_factory=list)
    review_queue: list[MigrationEntry] = field(default_factory=list)
    unresolved: list[MigrationEntry] = field(default_factory=list)


def find_card_files(root: Path) -> list[Path]:
    skip_dirs = set(links_validate.SKIP_DIRS)
    paths: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip_dirs)
        for filename in sorted(filenames):
            if filename.endswith(".md"):
                paths.append(Path(dirpath) / filename)
    return paths


def parse_card(path: Path, root: Path, errors: list[str]) -> tuple[dict[str, Any], int, int] | None:
    """Return (frontmatter-data, block-start-offset, block-end-offset) or None
    if this file has no parseable frontmatter block. Offsets are character
    offsets into the raw file text, so the caller can splice a replacement
    block back in without disturbing the body.
    """
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    rel = str(path.relative_to(root))
    parsed = links_validate.parse_frontmatter_block(text, rel)
    if parsed is None:
        return None
    if parsed.errors:
        errors.append(f"{rel}: cannot migrate, frontmatter has parse errors: {parsed.errors}")
        return None
    if not links_validate.looks_like_card(parsed.data):
        return None
    return parsed.data, match.start(1), match.end(1)


def render_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if text == "" or text != text.strip():
        return f'"{text}"'
    return text


def render_value(value: Any, indent: int) -> list[str]:
    pad = " " * indent
    if isinstance(value, dict):
        if not value:
            return []
        lines = []
        for key, inner in value.items():
            lines.extend(render_entry(key, inner, indent))
        return lines
    if isinstance(value, list):
        if not value:
            return []
        lines = []
        for item in value:
            if isinstance(item, dict):
                sub = render_value(item, indent + 2)
                if not sub:
                    lines.append(f"{pad}- {{}}")
                else:
                    first, *rest = sub
                    lines.append(f"{pad}- {first.strip()}")
                    lines.extend(rest)
            elif isinstance(item, list):
                lines.append(f"{pad}- {render_inline_list(item)}")
            else:
                lines.append(f"{pad}- {render_scalar(item)}")
        return lines
    return [f"{pad}{render_scalar(value)}"]


def render_inline_list(items: list[Any]) -> str:
    return "[" + ", ".join(render_scalar(item) for item in items) + "]"


def render_entry(key: str, value: Any, indent: int) -> list[str]:
    pad = " " * indent
    if isinstance(value, dict):
        if not value:
            # The parser has no inline-empty-mapping syntax: `key: {}` reads
            # back as the literal string "{}", not an empty dict (same gap
            # documented in references/parser-subset.md's unsupported-YAML
            # list). Repo convention is to drop an empty block entirely
            # rather than write a placeholder (see references/templates.md,
            # "if a card has no links yet, drop the links block entirely
            # rather than writing an empty one") -- this applies the same
            # rule to attrs, which the migration can empty out (e.g. a
            # migrated business card with no more parent-module/submodules).
            return []
        return [f"{pad}{key}:"] + render_value(value, indent + 2)
    if isinstance(value, list):
        if not value:
            # `key: []` parses back fine as an empty list, but a downstream
            # consumer expecting a dict (links) or absence (attrs) is safer
            # served by omitting the key, matching the same drop-if-empty
            # convention as the dict case above.
            return []
        if all(not isinstance(item, (dict, list)) for item in value):
            return [f"{pad}{key}: {render_inline_list(value)}"]
        return [f"{pad}{key}:"] + render_value(value, indent + 2)
    return [f"{pad}{key}: {render_scalar(value)}"]


CARD_FIELD_ORDER = [
    "id",
    "type",
    "status",
    "source",
    "owner",
    "last-reviewed",
    "next-audit",
    "aliases",
    "evidence",
    "volatility",
    "attrs",
    "links",
]


def render_frontmatter(data: dict[str, Any]) -> str:
    ordered_keys = [key for key in CARD_FIELD_ORDER if key in data]
    ordered_keys += [key for key in data if key not in CARD_FIELD_ORDER]
    lines: list[str] = []
    for key in ordered_keys:
        lines.extend(render_entry(key, data[key], 0))
    return "\n".join(lines)


def migrate_concept(
    rel: str, data: dict[str, Any], report: MigrationReport
) -> bool:
    attrs = data.get("attrs")
    subtype = attrs.get("subtype") if isinstance(attrs, dict) else None
    if not isinstance(subtype, str):
        report.review_queue.append(
            MigrationEntry(rel, "requires human review", "concept has no attrs.subtype; no v2 mapping")
        )
        return False

    if subtype in SUBTYPE_TO_ARTIFACT:
        data["type"] = "artifact"
        data["attrs"] = {"kind": SUBTYPE_TO_ARTIFACT[subtype]}
        report.changed.append(
            MigrationEntry(rel, "concept -> artifact", f"attrs.kind: {SUBTYPE_TO_ARTIFACT[subtype]}")
        )
        return True

    if subtype == "metric":
        data["type"] = "metric"
        # attrs.direction has a closed enum (up-is-good | down-is-good |
        # target-band) with no "unknown" escape hatch in the v2 contract --
        # unlike formula/binding, which the spec explicitly allows to be
        # "unknown, but visible". Synthesizing a fake direction would assert
        # false knowledge, so it is left unset: the validator's existing
        # required-attrs check for metric already flags a missing direction,
        # which is the honest signal for the review queue below.
        data["attrs"] = {
            "formula": "unknown",
            "unit": "unknown",
            "binding": "unknown",
        }
        report.changed.append(
            MigrationEntry(
                rel,
                "concept -> metric",
                "attrs.formula/unit/binding set to unknown; attrs.direction left "
                "unset (no unknown value allowed) -- needs human enrichment",
            )
        )
        report.review_queue.append(
            MigrationEntry(rel, "requires human review", "metric contract fields default to unknown")
        )
        return True

    if subtype in SUBTYPE_TO_ROLE:
        data["type"] = "role"
        data["attrs"] = {"kind": SUBTYPE_TO_ROLE[subtype]}
        report.changed.append(
            MigrationEntry(rel, "concept -> role", f"attrs.kind: {SUBTYPE_TO_ROLE[subtype]}")
        )
        return True

    if subtype in SUBTYPE_TO_TOOL:
        data["type"] = "tool"
        data["attrs"] = {"kind": SUBTYPE_TO_TOOL[subtype]}
        report.changed.append(
            MigrationEntry(rel, "concept -> tool", f"attrs.kind: {SUBTYPE_TO_TOOL[subtype]}")
        )
        return True

    if subtype in SUBTYPE_TO_DECISION:
        data["type"] = "decision"
        data["status"] = "proposed"
        new_attrs: dict[str, Any] = {"norm-kind": "regulated"}
        for kinetic_field in DECISION_KINETIC_FIELDS:
            new_attrs[kinetic_field] = "unknown"
        data["attrs"] = new_attrs
        report.changed.append(
            MigrationEntry(
                rel,
                "concept -> decision",
                "attrs.norm-kind: regulated; 12 kinetic fields default to unknown",
            )
        )
        report.review_queue.append(
            MigrationEntry(
                rel,
                "requires human review",
                "synthesized decision card: kinetic fields need a human to fill them in",
            )
        )
        return True

    if subtype in SUBTYPE_MANUAL_MERGE:
        report.review_queue.append(
            MigrationEntry(
                rel,
                "requires human review",
                f"concept attrs.subtype: {subtype} is a possible duplicate of a "
                f"{'state' if subtype == 'state' else 'business'} card; manual merge, not mechanical",
            )
        )
        return False

    if subtype in SUBTYPE_REVIEW_QUEUE:
        report.review_queue.append(
            MigrationEntry(
                rel,
                "requires human review",
                f"concept attrs.subtype: {subtype} needs a human decision: term or artifact",
            )
        )
        return False

    report.review_queue.append(
        MigrationEntry(rel, "requires human review", f"concept attrs.subtype: {subtype} has no v2 mapping")
    )
    return False


def migrate_module_type(rel: str, data: dict[str, Any], report: MigrationReport) -> bool:
    if data.get("type") != "module":
        return False
    data["type"] = "business"
    # business has zero allowed attrs (containment moves entirely to
    # links.part-of; see docs/specs/2026-07-02-data-model-v2.md section 2.1).
    # migrate_parent_module_link/migrate_submodules_link (run right after
    # this in migrate_root) only clear parent-module/submodules when they
    # hold a real card id -- a placeholder value like "not applicable" is
    # not a link target, so those functions leave it alone, and the
    # placeholder would otherwise survive as a now-invalid attrs key on a
    # business card. Clear both unconditionally here instead of leaving
    # that gap.
    attrs = data.get("attrs")
    if isinstance(attrs, dict):
        for placeholder_key in ("parent-module", "submodules"):
            value = attrs.get(placeholder_key)
            if isinstance(value, str) and value.strip().lower() in {"unknown", "not applicable"}:
                attrs.pop(placeholder_key, None)
    report.changed.append(MigrationEntry(rel, "module -> business", "type only; id unchanged"))
    return True


def migrate_parent_module_link(rel: str, data: dict[str, Any], report: MigrationReport) -> bool:
    attrs = data.get("attrs")
    if not isinstance(attrs, dict):
        return False
    parent = attrs.get("parent-module")
    if not isinstance(parent, str) or not parent.strip():
        return False
    if parent.strip().lower() in {"unknown", "not applicable"}:
        return False

    links = data.get("links")
    if not isinstance(links, dict):
        links = {}
        data["links"] = links
    part_of = links.get("part-of")
    if not isinstance(part_of, list):
        part_of = []
    if parent not in part_of:
        part_of.append(parent)
    links["part-of"] = part_of
    attrs.pop("parent-module", None)
    report.changed.append(
        MigrationEntry(rel, "attrs.parent-module -> links.part-of", f"part-of: [{parent}]")
    )
    return True


def migrate_submodules_link(
    rel: str,
    data: dict[str, Any],
    all_cards: dict[str, tuple[Path, dict[str, Any], str]],
    report: MigrationReport,
) -> list[str]:
    """Submodules point *down* (parent -> children); part-of points *up*
    (child -> parent). So this direction of the migration edits the named
    child cards, not the card carrying attrs.submodules. Returns the list of
    child ids that were actually updated, so the caller knows which other
    cards in all_cards changed as a side effect of migrating this one.
    """
    attrs = data.get("attrs")
    if not isinstance(attrs, dict):
        return []
    submodules = attrs.get("submodules")
    if not isinstance(submodules, list) or not submodules:
        return []

    this_id = data.get("id")
    touched: list[str] = []
    for child_id in submodules:
        if not isinstance(child_id, str) or not child_id.strip():
            continue
        entry = all_cards.get(child_id)
        if entry is None:
            report.review_queue.append(
                MigrationEntry(
                    rel,
                    "requires human review",
                    f"attrs.submodules lists '{child_id}' but no card with that id was found",
                )
            )
            continue
        _child_path, child_data, child_rel = entry
        child_links = child_data.get("links")
        if not isinstance(child_links, dict):
            child_links = {}
            child_data["links"] = child_links
        part_of = child_links.get("part-of")
        if not isinstance(part_of, list):
            part_of = []
        if this_id not in part_of:
            part_of.append(this_id)
            child_links["part-of"] = part_of
            report.changed.append(
                MigrationEntry(
                    child_rel,
                    "attrs.submodules (parent) -> links.part-of (child)",
                    f"part-of: [{this_id}]",
                )
            )
            touched.append(child_id)

    attrs.pop("submodules", None)
    return touched


def migrate_in_state_link(rel: str, data: dict[str, Any], report: MigrationReport) -> bool:
    links = data.get("links")
    if not isinstance(links, dict):
        return False
    in_state = links.pop("in-state", None)
    if not in_state:
        return False
    lifecycle = links.get("lifecycle")
    if not isinstance(lifecycle, list):
        lifecycle = []
    for target in in_state:
        if target not in lifecycle:
            lifecycle.append(target)
    links["lifecycle"] = lifecycle
    report.changed.append(MigrationEntry(rel, "links.in-state -> links.lifecycle", str(lifecycle)))
    return True


RawCard = tuple[Path, dict[str, Any], str, int, int, str]


def migrate_root(root: Path) -> tuple[MigrationReport, dict[str, RawCard], set[str]]:
    """Parse every card once, apply every migration rule in memory, and
    return (report, id -> (path, data, rel, block_start, block_end,
    original_text) for every parsed card, set of ids that actually changed)
    so main() can decide whether to write.
    """
    report = MigrationReport()
    errors: list[str] = []

    raw_cards: dict[str, tuple[Path, dict[str, Any], str, int, int, str]] = {}
    for path in find_card_files(root):
        parsed = parse_card(path, root, errors)
        if parsed is None:
            continue
        data, start, end = parsed
        cid = data.get("id")
        if not isinstance(cid, str) or not cid:
            continue
        rel = str(path.relative_to(root))
        original_text = path.read_text(encoding="utf-8")
        raw_cards[cid] = (path, data, rel, start, end, original_text)

    for error in errors:
        report.unresolved.append(MigrationEntry("(parse)", "unreadable", error))

    all_cards_view = {cid: (entry[0], entry[1], entry[2]) for cid, entry in raw_cards.items()}

    changed_ids: set[str] = set()
    for cid, (_path, data, rel, _start, _end, _text) in raw_cards.items():
        ctype = data.get("type")
        before = dict(data)

        if ctype == "concept":
            if migrate_concept(rel, data, report):
                changed_ids.add(cid)
        if migrate_module_type(rel, data, report):
            changed_ids.add(cid)
        if migrate_parent_module_link(rel, data, report):
            changed_ids.add(cid)
        touched_children = migrate_submodules_link(rel, data, all_cards_view, report)
        changed_ids.update(touched_children)
        if migrate_in_state_link(rel, data, report):
            changed_ids.add(cid)

        if data != before:
            changed_ids.add(cid)

    return report, raw_cards, changed_ids


def write_migrated_card(path: Path, data: dict[str, Any], start: int, end: int, original_text: str) -> None:
    new_block = render_frontmatter(data)
    new_text = original_text[:start] + new_block + original_text[end:]
    path.write_text(new_text, encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rewrite v1 card frontmatter into data model v2 shape."
    )
    parser.add_argument("root", help="Ontology root to migrate")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the migration plan without writing any file",
    )
    return parser.parse_args(argv)


def print_report(report: MigrationReport, changed_count: int, dry_run: bool) -> None:
    verb = "would change" if dry_run else "changed"
    if changed_count == 0 and not report.review_queue and not report.unresolved:
        print("Nothing to do: no v1 fields matched the migration table.")
        return

    print(f"Cards {verb}: {changed_count}")
    for entry in report.changed:
        detail = f" ({entry.detail})" if entry.detail else ""
        print(f"  {entry.path}: {entry.change}{detail}")

    if report.review_queue:
        print(f"\nRequires human review: {len(report.review_queue)}")
        for entry in report.review_queue:
            print(f"  {entry.path}: {entry.detail}")

    if report.unresolved:
        print(f"\nUnresolved (could not parse): {len(report.unresolved)}")
        for entry in report.unresolved:
            print(f"  {entry.path}: {entry.detail}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"ERROR: {root} is not a directory", file=sys.stderr)
        return 1

    report, raw_cards, changed_ids = migrate_root(root)

    if not args.dry_run:
        for cid in changed_ids:
            entry = raw_cards.get(cid)
            if entry is None:
                continue
            path, data, _rel, start, end, original_text = entry
            write_migrated_card(path, data, start, end, original_text)

    print_report(report, len(changed_ids), args.dry_run)
    # A file that could not be parsed is reported but does not block
    # migrating every other card that did parse cleanly (see docstring: only
    # frontmatter is touched, files are otherwise independent). The exit
    # code still signals "not fully clean" so a caller scripting this can
    # tell the difference between a clean pass and one with a parse gap.
    return 1 if report.unresolved else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Validate business-ontology markdown cards with zero dependencies.

The accepted Markdown/Git export is the current validation surface; the target
operational source of truth is the canonical model store. This validator checks
the machine-readable contract that makes the export queryable: one frontmatter
shape, opaque ids, closed relation vocabulary, resolvable links, typed attrs,
registered source provenance, source trust floors, and the staged proposal gate.

Usage:
  python3 scripts/links_validate.py [ontology-root]
  python3 scripts/links_validate.py [ontology-root] --staged

Exit codes: 0 clean, 1 validation errors.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
import sys
from typing import Any


ALLOWED_LINKS = {
    "produces",
    "consumes",
    "supplies-to",
    "part-of",
    "owns",
    "measured-by",
    "source-of-truth",
    "in-state",
    "lifecycle",
    "influences",
    "governed-by",
}

# Data model v2 (docs/specs/2026-07-02-data-model-v2.md, section 6): relation
# names on the left validate for exactly one transitional version but emit a
# deprecation warning; author new cards with the value on the right.
DEPRECATED_LINK_ALIASES = {
    "in-state": "lifecycle",
}

SEMANTIC_LINK_RULES = {
    "in-state": "target must be type state",
    "lifecycle": "target must be type state",
    "measured-by": "target must be a metric concept",
    "source-of-truth": "source must be a state, metric, or artifact; target must be a tool",
    "part-of": "source and target must be structural business or production-system cards",
    "owns": "source must be a business; target must be a production-system or tool concept",
    "governed-by": "target must be a decision or rule/regulation/authority concept",
    "supplies-to": "target must be a role concept; concept sources must also be role concepts",
}

# Data model v2 (docs/specs/2026-07-02-data-model-v2.md, section 1): 11 closed
# types. `module` and `concept` are v1 aliases kept for one transitional
# version: `module` maps to `business` (DEPRECATED_TYPE_ALIASES), `concept`
# keeps its old attrs.subtype contract untouched (see ALLOWED_ATTRS).
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
    "module",
    "concept",
}

DEPRECATED_TYPE_ALIASES = {
    "module": "business",
}

CARD_STATUSES = {
    "accepted",
    "candidate",
    "hypothesis",
    "conflict",
    "deprecated",
    "unknown",
}

DECISION_STATUSES = {
    "proposed",
    "accepted",
    "implemented",
    "superseded",
    "retired",
}

STATUS_STRENGTH = {
    "unknown": 0,
    "hypothesis": 1,
    "candidate": 2,
    "conflict": 2,
    "accepted": 3,
    "deprecated": 3,
}

DECISION_STATUS_STRENGTH = {
    "proposed": 1,
    "accepted": 3,
    "implemented": 3,
    "superseded": 3,
    "retired": 3,
}

SOURCE_TRUST_STRENGTH = STATUS_STRENGTH

COMMON_KEYS = {
    "id",
    "type",
    "status",
    "source",
    "owner",
    "last-reviewed",
    "next-audit",
    "links",
    "attrs",
    # Data model v2 optional common fields (docs/specs/2026-07-02-data-model-v2.md,
    # section 0): old/jargon names for mining, evidence trail, audit cadence hint.
    "aliases",
    "evidence",
    "volatility",
}

VOLATILITY_VALUES = {"high", "medium", "low"}

REQUIRED_CARD_KEYS = {
    "id",
    "type",
    "status",
    "source",
    "owner",
    "last-reviewed",
    "next-audit",
}

# Data model v2 attrs contracts (docs/specs/2026-07-02-data-model-v2.md,
# section 2). Closed by type: a key outside this set is an error
# (validate_attrs). `concept` and `module` keep their v1 shape unchanged as
# one-version deprecated aliases (see DEPRECATED_TYPE_ALIASES).
ALLOWED_ATTRS = {
    "concept": {"subtype"},
    "module": {"parent-module", "submodules"},
    "business": set(),
    "production-system": {"business", "stages", "module"},
    "role": {"kind", "authority"},
    "artifact": {"kind", "influences"},
    "tool": {"kind", "access-mode"},
    "metric": {
        "formula",
        "unit",
        "direction",
        "target",
        "baseline",
        "refresh-cadence",
        "binding",
        "influences",
    },
    "state": {
        "entity",
        "states",
        "entry",
        "terminal",
        "transitions",
        "reason-codes",
        "influences",
    },
    "process": {"production-system", "entry-state", "exit-state", "steps"},
    "interface": {
        "contract",
        "participants",
        "outcome",
        "quality-criterion",
        "qualities",
        "slas",
        "acceptance",
    },
    "decision": {
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
        "norm-kind",
        "supersedes",
        "superseded-by",
        "valid-from",
        "valid-to",
    },
    "term": {"applies-to"},
}

# production-system carries a v1-compat `module` key (see ALLOWED_ATTRS above)
# purely so a card mid-migration can still resolve its old attrs.module
# pointer; it is not part of the v2 contract and is not required.
#
# Hard errors below are scoped to types with no v1 precedent to break: role,
# artifact, tool, metric, term are new in v2, and process had zero cards
# anywhere in the repo under v1 (see docs/specs/2026-07-02-data-model-v2.md,
# "Why this matters"), so requiring their v2 fields cannot fail a v1 card.
# production-system, state, interface, and decision keep the SAME type name
# across v1 and v2 (unlike module/concept, which are aliased type names) but
# their attrs contract tightened; a v1 card of one of these types is valid
# and predates fields the v2 contract newly asks for. Making those new
# fields hard-required would fail examples/acquisition-ontology without
# touching the v1 cards, which the migration is designed to avoid for
# exactly one transitional version. SOFT_REQUIRED_ATTRS (below) surfaces the
# same gap as a warning instead, so new v2 authoring still gets a visible
# nudge without retroactively breaking old cards.
REQUIRED_ATTRS = {
    "role": {"kind"},
    "artifact": {"kind"},
    "tool": {"kind"},
    "metric": {"formula", "unit", "direction", "binding"},
    "process": {"production-system", "steps"},
    "interface": {"participants", "quality-criterion", "outcome"},
    "decision": {
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
    },
    "term": {"applies-to"},
}

# Fields the v2 spec marks "да" (required) for a type that also existed in
# v1 with a looser contract. Missing => warning, not error; see the
# REQUIRED_ATTRS comment above for why these stay soft for one version.
SOFT_REQUIRED_ATTRS = {
    "production-system": {"business"},
    "state": {"states", "entry", "terminal", "transitions"},
    "interface": {"contract"},
    "decision": {"norm-kind"},
}

REQUIRED_INTERFACE_PARTICIPANTS = {"supplier", "customer", "subject"}
INTERFACE_CONTRACT_LEVELS = {"handoff", "contract"}
METRIC_DIRECTIONS = {"up-is-good", "down-is-good", "target-band"}
ROLE_KINDS = {"role", "position"}
ARTIFACT_KINDS = {"product", "service", "intermediate"}
TOOL_KINDS = {"system", "tool", "dashboard", "channel"}
DECISION_NORM_KINDS = {"decided", "regulated", "observed-practice"}

PROPOSAL_KEYS = {
    "proposal-id",
    "target",
    "diff",
    "basis",
    "source-locator",
    "confidence",
    "input",
    "originating-skill",
    "ttl",
    "validator-result",
}

REQUIRED_PROPOSAL_KEYS = set(PROPOSAL_KEYS)
PROPOSAL_CONFIDENCE = {"high", "medium", "low"}
PROPOSAL_INPUTS = {
    "owner-decision",
    "working-system",
    "regulation",
    "dashboard",
    "interview",
    "mined",
    "agent-inference",
}

STAGED_DIR = "staged"
SOURCE_MAP_FILE = "02-source-map.md"
SKIP_DIRS = {
    ".git",
    ".github",
    "node_modules",
    "registry",
    "scripts",
    "tests",
    "fixtures",
    "plans",
}

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
FENCED_BLOCK_RE = re.compile(r"```(?:markdown|md)?\s*\n(.*?)\n```", re.DOTALL)
KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

PII_PATTERNS = [
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


@dataclass
class ParsedFrontmatter:
    data: dict[str, Any]
    errors: list[str]
    body_start_line: int


@dataclass
class Card:
    cid: str
    path: str
    data: dict[str, Any]
    links: dict[str, list[str]]
    staged: bool


@dataclass
class SourceEntry:
    sid: str
    path: str
    trust: str
    owner: str
    access_mode: str
    read_policy: dict[str, bool]
    meaning: str


def count_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def clean_scalar(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def clean_table_cell(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] == "`":
        return value[1:-1].strip()
    return clean_scalar(value)


def parse_scalar(raw: str, path: str, line_no: int, errors: list[str]) -> Any:
    value = raw.strip()
    if value == "":
        return ""
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith("["):
        if not value.endswith("]"):
            errors.append(f"{path}:{line_no}: malformed inline list")
            return []
        inner = value[1:-1].strip()
        if not inner:
            return []
        items = []
        for item in inner.split(","):
            item = clean_scalar(item)
            if item:
                items.append(item)
        return items
    return clean_scalar(value)


def next_significant(lines: list[tuple[int, str]], index: int) -> tuple[int, str] | None:
    for pos in range(index, len(lines)):
        line_no, raw = lines[pos]
        if raw.strip() and not raw.lstrip().startswith("#"):
            return line_no, raw
    return None


def parse_list_item_mapping(
    lines: list[tuple[int, str]],
    index: int,
    item_indent: int,
    first_key_raw: str,
    path: str,
    errors: list[str],
) -> tuple[dict[str, Any], int]:
    """Parse a `- key: value` list item as a one-entry-per-line mapping.

    The first key/value pair lives on the `- ` line itself; any following
    lines indented to line up under that first key (item_indent + 2, the
    width of `- `) continue the same mapping. This lets attrs carry closed
    structures such as state.transitions or process.steps as a list of
    small maps, reusing parse_mapping's line-based walk rather than adding
    a second recursive-descent parser.
    """
    virtual_lines: list[tuple[int, str]] = []
    line_no, _ = lines[index]
    virtual_lines.append((line_no, " " * (item_indent + 2) + first_key_raw))
    index += 1

    member_indent = item_indent + 2
    while index < len(lines):
        next_line_no, raw = lines[index]
        if not raw.strip() or raw.lstrip().startswith("#"):
            index += 1
            continue
        current_indent = count_indent(raw)
        if current_indent < member_indent:
            break
        if current_indent == item_indent and raw[item_indent:].startswith("- "):
            break
        virtual_lines.append((next_line_no, raw))
        index += 1

    data, _ = parse_mapping(virtual_lines, 0, member_indent, path, errors)
    return data, index


def parse_list(
    lines: list[tuple[int, str]],
    index: int,
    indent: int,
    path: str,
    errors: list[str],
) -> tuple[list[Any], int]:
    items: list[Any] = []
    while index < len(lines):
        line_no, raw = lines[index]
        if not raw.strip() or raw.lstrip().startswith("#"):
            index += 1
            continue
        current_indent = count_indent(raw)
        if current_indent < indent:
            break
        if current_indent > indent:
            errors.append(f"{path}:{line_no}: unexpected indentation")
            index += 1
            continue
        stripped = raw[indent:]
        if not stripped.startswith("- "):
            break
        item = stripped[2:].strip()
        if item == "":
            errors.append(f"{path}:{line_no}: nested list items are not supported")
        elif KEY_RE.match(item):
            entry, index = parse_list_item_mapping(
                lines, index, indent, stripped[2:], path, errors
            )
            items.append(entry)
            continue
        else:
            items.append(parse_scalar(item, path, line_no, errors))
        index += 1
    return items, index


def parse_mapping(
    lines: list[tuple[int, str]],
    index: int,
    indent: int,
    path: str,
    errors: list[str],
) -> tuple[dict[str, Any], int]:
    data: dict[str, Any] = {}
    while index < len(lines):
        line_no, raw = lines[index]
        if not raw.strip() or raw.lstrip().startswith("#"):
            index += 1
            continue
        current_indent = count_indent(raw)
        if current_indent < indent:
            break
        if current_indent > indent:
            errors.append(f"{path}:{line_no}: unexpected indentation")
            index += 1
            continue

        stripped = raw[indent:]
        if stripped.startswith("- "):
            errors.append(f"{path}:{line_no}: list item where mapping key was expected")
            index += 1
            continue

        match = KEY_RE.match(stripped)
        if not match:
            errors.append(f"{path}:{line_no}: malformed mapping line")
            index += 1
            continue

        key, raw_value = match.group(1), match.group(2)
        if key in data:
            errors.append(f"{path}:{line_no}: duplicate key '{key}'")

        if raw_value.strip():
            data[key] = parse_scalar(raw_value, path, line_no, errors)
            index += 1
            continue

        lookahead = next_significant(lines, index + 1)
        if lookahead is None or count_indent(lookahead[1]) <= indent:
            data[key] = {}
            index += 1
            continue

        child_indent = count_indent(lookahead[1])
        if lookahead[1][child_indent:].startswith("- "):
            data[key], index = parse_list(lines, index + 1, child_indent, path, errors)
        else:
            data[key], index = parse_mapping(lines, index + 1, child_indent, path, errors)

    return data, index


def parse_frontmatter_block(text: str, path: str, start_line: int = 1) -> ParsedFrontmatter | None:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    block = match.group(1)
    lines = [(start_line + i, line.rstrip("\n")) for i, line in enumerate(block.splitlines())]
    errors: list[str] = []
    data, _ = parse_mapping(lines, 0, 0, path, errors)
    body_start_line = start_line + block.count("\n") + 2
    return ParsedFrontmatter(data=data, errors=errors, body_start_line=body_start_line)


def is_truthy_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def is_template_card(data: dict[str, Any]) -> bool:
    cid = data.get("id")
    return isinstance(cid, str) and cid.startswith("<")


def looks_like_card(data: dict[str, Any]) -> bool:
    return bool({"id", "type", "status", "links", "attrs"} & set(data))


def looks_like_proposal(data: dict[str, Any]) -> bool:
    return bool({"proposal-id", "target", "diff", "source-locator"} & set(data))


def normalize_links(value: Any, path: str, errors: list[str]) -> dict[str, list[str]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path}: links must be a mapping of relation -> [ids]")
        return {}

    normalized: dict[str, list[str]] = {}
    for relation, targets in value.items():
        if not isinstance(targets, list):
            errors.append(f"{path}: links.{relation} must be a list")
            continue
        clean_targets = []
        for target in targets:
            if not isinstance(target, str):
                errors.append(f"{path}: links.{relation} target must be a string id")
                continue
            if target.startswith("<"):
                continue
            clean_targets.append(target)
        normalized[relation] = clean_targets
    return normalized


def validate_attrs(
    path: str,
    data: dict[str, Any],
    errors: list[str],
    warnings: list[str] | None = None,
) -> None:
    if warnings is None:
        warnings = []
    ctype = data.get("type")
    attrs = data.get("attrs", {})
    if attrs == {}:
        attrs = {}
    if attrs and not isinstance(attrs, dict):
        errors.append(f"{path}: attrs must be a mapping")
        return
    if ctype not in CARD_TYPES:
        return

    allowed = ALLOWED_ATTRS.get(ctype, set())
    for key in attrs:
        if key not in allowed:
            errors.append(f"{path}: attrs.{key} is not allowed for type '{ctype}'")

    for key in REQUIRED_ATTRS.get(ctype, set()):
        if not is_truthy_value(attrs.get(key)):
            errors.append(f"{path}: missing required attrs.{key} for type '{ctype}'")

    for key in SOFT_REQUIRED_ATTRS.get(ctype, set()):
        if not is_truthy_value(attrs.get(key)):
            warnings.append(
                f"{path}: attrs.{key} is required by data model v2 for type '{ctype}' "
                "(warning for one transitional version; will become an error)"
            )

    if ctype == "interface":
        validate_interface_attrs(path, attrs, errors, warnings)

    if ctype == "decision":
        validate_decision_attrs(path, attrs, errors, warnings)

    if ctype == "role":
        kind = attrs.get("kind")
        if kind is not None and kind not in ROLE_KINDS:
            errors.append(f"{path}: attrs.kind must be one of {sorted(ROLE_KINDS)}")

    if ctype == "artifact":
        kind = attrs.get("kind")
        if kind is not None and kind not in ARTIFACT_KINDS:
            errors.append(f"{path}: attrs.kind must be one of {sorted(ARTIFACT_KINDS)}")

    if ctype == "tool":
        kind = attrs.get("kind")
        if kind is not None and kind not in TOOL_KINDS:
            errors.append(f"{path}: attrs.kind must be one of {sorted(TOOL_KINDS)}")

    if ctype == "metric":
        direction = attrs.get("direction")
        if direction is not None and direction not in METRIC_DIRECTIONS:
            errors.append(f"{path}: attrs.direction must be one of {sorted(METRIC_DIRECTIONS)}")

    if ctype == "state":
        validate_state_attrs(path, attrs, errors)

    if ctype == "process":
        steps = attrs.get("steps")
        if steps is not None and not isinstance(steps, list):
            errors.append(f"{path}: attrs.steps must be a list")
        elif isinstance(steps, list):
            if len(steps) > 30:
                errors.append(f"{path}: attrs.steps has {len(steps)} entries, budget is 30")
            for step in steps:
                if not isinstance(step, dict) or not is_truthy_value(step.get("role")):
                    errors.append(f"{path}: every attrs.steps entry needs a role")

    if ctype == "production-system":
        stages = attrs.get("stages")
        if stages is not None and not isinstance(stages, list):
            errors.append(f"{path}: attrs.stages must be a list")


def validate_interface_attrs(
    path: str, attrs: dict[str, Any], errors: list[str], warnings: list[str]
) -> None:
    participants = attrs.get("participants")
    if not isinstance(participants, dict):
        errors.append(f"{path}: attrs.participants must be a mapping")
    else:
        for role in REQUIRED_INTERFACE_PARTICIPANTS:
            ids = participants.get(role)
            if not isinstance(ids, list) or not ids:
                errors.append(f"{path}: attrs.participants.{role} must be a non-empty list")
                continue
            for participant_id in ids:
                if not isinstance(participant_id, str) or not participant_id:
                    errors.append(
                        f"{path}: attrs.participants.{role} contains a non-string id"
                    )
        for role in participants:
            if role not in REQUIRED_INTERFACE_PARTICIPANTS:
                errors.append(f"{path}: attrs.participants.{role} is not supported")

    contract = attrs.get("contract")
    if contract is not None and contract not in INTERFACE_CONTRACT_LEVELS:
        errors.append(f"{path}: attrs.contract must be one of {sorted(INTERFACE_CONTRACT_LEVELS)}")

    if contract == "contract":
        if not is_truthy_value(attrs.get("quality-criterion")):
            errors.append(
                f"{path}: attrs.quality-criterion is required when attrs.contract is 'contract'"
            )
        if not is_truthy_value(attrs.get("acceptance")):
            errors.append(
                f"{path}: attrs.acceptance is required when attrs.contract is 'contract'"
            )
    elif contract == "handoff" and is_truthy_value(attrs.get("slas")):
        warnings.append(
            f"{path}: attrs.contract is 'handoff' but attrs.slas is filled in "
            "(looks like this should be contract: contract)"
        )


def validate_decision_attrs(
    path: str, attrs: dict[str, Any], errors: list[str], warnings: list[str]
) -> None:
    if "irreversible" in attrs and not isinstance(attrs.get("irreversible"), bool):
        errors.append(f"{path}: attrs.irreversible must be true or false")

    # attrs.norm-kind presence is checked by SOFT_REQUIRED_ATTRS (warning, one
    # transitional version, since decision predates norm-kind in v1). Here we
    # only validate the value once it is present.
    norm_kind = attrs.get("norm-kind")
    if is_truthy_value(norm_kind) and norm_kind not in DECISION_NORM_KINDS:
        errors.append(f"{path}: attrs.norm-kind must be one of {sorted(DECISION_NORM_KINDS)}")
    elif norm_kind == "observed-practice":
        authority = attrs.get("transition-authority")
        if isinstance(authority, str) and authority.strip().lower() != "unknown":
            errors.append(
                f"{path}: attrs.norm-kind 'observed-practice' requires "
                "attrs.transition-authority: unknown (a practice has no author)"
            )


def validate_state_attrs(path: str, attrs: dict[str, Any], errors: list[str]) -> None:
    states = attrs.get("states")
    states_set = set(states) if isinstance(states, list) else set()
    if states is not None and not isinstance(states, list):
        errors.append(f"{path}: attrs.states must be a list")
    elif isinstance(states, list) and len(states) > 12:
        errors.append(f"{path}: attrs.states has {len(states)} entries, budget is 12")

    for bound_key in ("entry", "terminal"):
        bound = attrs.get(bound_key)
        if bound is None:
            continue
        if not isinstance(bound, list):
            errors.append(f"{path}: attrs.{bound_key} must be a list")
            continue
        for value in bound:
            if states_set and value not in states_set:
                errors.append(
                    f"{path}: attrs.{bound_key} value '{value}' is not in attrs.states"
                )

    terminal = attrs.get("terminal")
    terminal_set = set(terminal) if isinstance(terminal, list) else set()

    transitions = attrs.get("transitions")
    if transitions is not None and not isinstance(transitions, list):
        errors.append(f"{path}: attrs.transitions must be a list")
    elif isinstance(transitions, list):
        for transition in transitions:
            if not isinstance(transition, dict):
                errors.append(f"{path}: every attrs.transitions entry must be a mapping")
                continue
            for required_key in ("from", "to", "trigger"):
                if not is_truthy_value(transition.get(required_key)):
                    errors.append(
                        f"{path}: attrs.transitions entry is missing '{required_key}'"
                    )
            for endpoint_key in ("from", "to"):
                value = transition.get(endpoint_key)
                if states_set and value is not None and value not in states_set:
                    errors.append(
                        f"{path}: attrs.transitions.{endpoint_key} '{value}' is not in attrs.states"
                    )

    reason_codes = attrs.get("reason-codes")
    if reason_codes is not None and not isinstance(reason_codes, list):
        errors.append(f"{path}: attrs.reason-codes must be a list")
    elif isinstance(reason_codes, list):
        for entry in reason_codes:
            if not isinstance(entry, dict):
                errors.append(f"{path}: every attrs.reason-codes entry must be a mapping")
                continue
            on_value = entry.get("on")
            if not is_truthy_value(on_value):
                errors.append(f"{path}: attrs.reason-codes entry is missing 'on'")
            elif terminal_set and on_value not in terminal_set:
                errors.append(
                    f"{path}: attrs.reason-codes.on '{on_value}' is not in attrs.terminal"
                )


def validate_card_shape(
    path: str,
    data: dict[str, Any],
    errors: list[str],
    warnings: list[str] | None = None,
) -> dict[str, list[str]]:
    if warnings is None:
        warnings = []
    if is_template_card(data):
        return {}

    for key in data:
        if key not in COMMON_KEYS:
            errors.append(f"{path}: top-level key '{key}' is outside the card contract")

    for key in REQUIRED_CARD_KEYS:
        if not is_truthy_value(data.get(key)):
            errors.append(f"{path}: missing required field '{key}'")

    cid = data.get("id")
    if isinstance(cid, str) and cid:
        if not ID_RE.match(cid):
            errors.append(f"{path}: id '{cid}' must be a lowercase kebab-case slug")
        if "--" in cid:
            errors.append(
                f"{path}: node id '{cid}' contains '--' "
                "(looks derived from names; ids must be opaque and stable)"
            )

    ctype = data.get("type")
    if ctype not in CARD_TYPES:
        errors.append(f"{path}: type '{ctype}' is outside the closed card type set")
    elif ctype in DEPRECATED_TYPE_ALIASES:
        warnings.append(
            f"{path}: type '{ctype}' is deprecated; use "
            f"'{DEPRECATED_TYPE_ALIASES[ctype]}' (data model v2, one transitional version)"
        )

    status = data.get("status")
    if ctype == "decision":
        allowed_statuses = DECISION_STATUSES
        status_label = "decision lifecycle"
    else:
        allowed_statuses = CARD_STATUSES
        status_label = "knowledge status"
    if status is not None and status not in allowed_statuses:
        errors.append(f"{path}: status '{status}' is outside the {status_label} vocabulary")

    for key in ("source", "owner", "last-reviewed", "next-audit"):
        value = data.get(key)
        if isinstance(value, str) and not value.strip():
            errors.append(f"{path}: field '{key}' must be non-empty or explicit unknown")

    volatility = data.get("volatility")
    if volatility is not None and volatility not in VOLATILITY_VALUES:
        errors.append(f"{path}: volatility must be one of {sorted(VOLATILITY_VALUES)}")

    for list_key in ("aliases", "evidence"):
        value = data.get(list_key)
        if value is not None and not isinstance(value, list):
            errors.append(f"{path}: {list_key} must be a list")

    validate_attrs(path, data, errors, warnings)
    links = normalize_links(data.get("links"), path, errors)
    for relation in links:
        if relation in DEPRECATED_LINK_ALIASES:
            warnings.append(
                f"{path}: relation '{relation}' is deprecated; use "
                f"'{DEPRECATED_LINK_ALIASES[relation]}' (data model v2, one transitional version)"
            )
    return links


def validate_proposal_shape(path: str, data: dict[str, Any], errors: list[str]) -> None:
    for key in data:
        if key not in PROPOSAL_KEYS:
            errors.append(f"{path}: proposal key '{key}' is outside the staged contract")
    for key in REQUIRED_PROPOSAL_KEYS:
        if not is_truthy_value(data.get(key)):
            errors.append(f"{path}: missing required proposal field '{key}'")

    proposal_id = data.get("proposal-id")
    if isinstance(proposal_id, str):
        if not proposal_id.startswith("prop-") or not ID_RE.match(proposal_id):
            errors.append(f"{path}: proposal-id must be an opaque 'prop-' kebab-case id")

    target = data.get("target")
    if isinstance(target, str) and target != "new" and not ID_RE.match(target):
        errors.append(f"{path}: target must be 'new' or a card id")

    diff = data.get("diff")
    if not isinstance(diff, dict):
        errors.append(f"{path}: diff must contain was/now fields")
    else:
        for key in ("was", "now"):
            if not is_truthy_value(diff.get(key)):
                errors.append(f"{path}: diff.{key} must be present")

    confidence = data.get("confidence")
    if confidence and confidence not in PROPOSAL_CONFIDENCE:
        errors.append(f"{path}: confidence must be one of high, medium, low")

    input_class = data.get("input")
    if input_class and input_class not in PROPOSAL_INPUTS:
        errors.append(f"{path}: input must be one of the staged trust classes")


def candidate_blocks(text: str) -> list[tuple[int, str]]:
    blocks = []
    for match in FENCED_BLOCK_RE.finditer(text):
        block = match.group(1)
        if block.lstrip().startswith("---"):
            start_line = text[: match.start(1)].count("\n") + 1
            blocks.append((start_line, block))
    return blocks


def read_markdown(path: str, root: str, errors: list[str]) -> str | None:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except Exception as exc:
        errors.append(f"{os.path.relpath(path, root)}: unreadable ({exc})")
        return None


def normalize_table_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", clean_table_cell(value).lower()).strip("-")


def split_table_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def is_table_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def parse_read_policy(raw: str, path: str, line_no: int, errors: list[str]) -> dict[str, bool]:
    policy: dict[str, bool] = {}
    for item in re.split(r"[;,]", raw):
        if not item.strip():
            continue
        if "=" not in item:
            errors.append(f"{path}:{line_no}: read policy item '{item.strip()}' must use key=value")
            continue
        key, raw_value = item.split("=", 1)
        key = clean_table_cell(key)
        value = clean_table_cell(raw_value).lower()
        if value not in {"true", "false"}:
            errors.append(f"{path}:{line_no}: read policy {key} must be true or false")
            continue
        policy[key] = value == "true"

    required = {
        "readOnly": True,
        "piiExcluded": True,
        "rawPayloadAccess": False,
    }
    for key, expected in required.items():
        if key not in policy:
            errors.append(f"{path}:{line_no}: read policy missing {key}")
        elif policy[key] is not expected:
            expected_text = "true" if expected else "false"
            errors.append(f"{path}:{line_no}: read policy {key} must be {expected_text}")
    return policy


def parse_source_map(path: str, root: str, errors: list[str]) -> dict[str, SourceEntry]:
    text = read_markdown(path, root, errors)
    if text is None:
        return {}

    rel = os.path.relpath(path, root)
    entries: dict[str, SourceEntry] = {}
    lines = text.splitlines()
    header_indexes: dict[str, int] | None = None
    found_table = False

    for index, line in enumerate(lines):
        cells = split_table_row(line)
        if cells is None:
            continue
        headers = [normalize_table_header(cell) for cell in cells]
        if "source-id" in headers and (
            "trust" in headers or "trust-floor" in headers or "status" in headers
        ):
            header_indexes = {header: pos for pos, header in enumerate(headers)}
            found_table = True
            continue

        if header_indexes is None:
            continue
        if is_table_separator(cells):
            continue
        if len(cells) < len(header_indexes):
            continue

        line_no = index + 1
        sid = clean_table_cell(cells[header_indexes["source-id"]])
        trust_key = (
            "trust"
            if "trust" in header_indexes
            else "trust-floor"
            if "trust-floor" in header_indexes
            else "status"
        )
        trust = clean_table_cell(cells[header_indexes[trust_key]])
        owner = clean_table_cell(cells[header_indexes.get("owner", -1)]) if "owner" in header_indexes else "unknown"
        access_mode = (
            clean_table_cell(cells[header_indexes.get("access-mode", -1)])
            if "access-mode" in header_indexes
            else "unknown"
        )
        read_policy_raw = (
            clean_table_cell(cells[header_indexes.get("read-policy", -1)])
            if "read-policy" in header_indexes
            else ""
        )
        meaning = clean_table_cell(cells[header_indexes.get("meaning", -1)]) if "meaning" in header_indexes else ""

        if not sid:
            errors.append(f"{rel}:{line_no}: source id must be non-empty")
            continue
        if not ID_RE.match(sid):
            errors.append(f"{rel}:{line_no}: source id '{sid}' must be a lowercase kebab-case id")
        if trust not in SOURCE_TRUST_STRENGTH:
            errors.append(f"{rel}:{line_no}: source trust '{trust}' is outside the status vocabulary")
        if not owner:
            errors.append(f"{rel}:{line_no}: source owner must be non-empty or explicit unknown")
        if not access_mode:
            errors.append(f"{rel}:{line_no}: source access mode must be non-empty or explicit unknown")
        if not meaning:
            errors.append(f"{rel}:{line_no}: source meaning must be non-empty")
        policy = parse_read_policy(read_policy_raw, rel, line_no, errors)

        if sid in entries:
            errors.append(f"{rel}:{line_no}: duplicate source id '{sid}'")
            continue
        entries[sid] = SourceEntry(
            sid=sid,
            path=f"{rel}:{line_no}",
            trust=trust,
            owner=owner,
            access_mode=access_mode,
            read_policy=policy,
            meaning=meaning,
        )

    if not found_table:
        errors.append(
            f"{rel}: missing source-map table with Source id, Trust, Owner, "
            "Access mode, Read policy, and Meaning columns"
        )
    return entries


def collect_source_maps(root: str, errors: list[str]) -> dict[str, dict[str, SourceEntry]]:
    source_maps: dict[str, dict[str, SourceEntry]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if SOURCE_MAP_FILE not in filenames:
            continue
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            rel_dir = ""
        source_maps[rel_dir] = parse_source_map(os.path.join(dirpath, SOURCE_MAP_FILE), root, errors)
    return source_maps


def source_maps_for_card(card_path: str, source_maps: dict[str, dict[str, SourceEntry]]) -> dict[str, SourceEntry] | None:
    path_part = card_path.split(":", 1)[0]
    rel_dir = os.path.dirname(path_part)
    while True:
        if rel_dir in source_maps:
            return source_maps[rel_dir]
        if rel_dir in {"", "."}:
            return source_maps.get("")
        parent = os.path.dirname(rel_dir)
        if parent == rel_dir:
            return None
        rel_dir = parent


def status_strength(data: dict[str, Any]) -> int | None:
    status = data.get("status")
    if data.get("type") == "decision":
        return DECISION_STATUS_STRENGTH.get(status)
    return STATUS_STRENGTH.get(status)


def card_type(card: Card) -> str | None:
    value = card.data.get("type")
    return value if isinstance(value, str) else None


def card_subtype(card: Card) -> str | None:
    attrs = card.data.get("attrs")
    if not isinstance(attrs, dict):
        return None
    value = attrs.get("subtype")
    return value if isinstance(value, str) else None


def is_concept_subtype(card: Card, subtypes: set[str]) -> bool:
    return card_type(card) == "concept" and card_subtype(card) in subtypes


def is_metric_concept(card: Card) -> bool:
    return card_type(card) == "metric" or is_concept_subtype(card, {"metric"})


def is_role_concept(card: Card) -> bool:
    return card_type(card) == "role" or is_concept_subtype(card, {"role"})


def is_tool_or_system(card: Card) -> bool:
    return card_type(card) in {"tool", "production-system"} or is_concept_subtype(
        card,
        {"tool", "system"},
    )


def is_structural_card(card: Card) -> bool:
    return card_type(card) in {"business", "module", "production-system"}


def is_rule_authority(card: Card) -> bool:
    return card_type(card) == "decision" or is_concept_subtype(
        card,
        {"regulation", "rule", "authority"},
    )


def is_source_of_truth_subject(card: Card) -> bool:
    return card_type(card) in {"state", "metric", "artifact"} or is_concept_subtype(
        card, {"metric", "fact"}
    )


def is_business_card(card: Card) -> bool:
    return card_type(card) in {"business", "module"}


def is_influenceable(card: Card) -> bool:
    return card_type(card) in {"metric", "state", "artifact"}


def semantic_error(card: Card, relation: str, target: Card, message: str) -> str:
    return f"{card.path}: semantic link {relation} -> '{target.cid}' {message}"


def check_sources(
    cards: dict[str, Card],
    source_maps: dict[str, dict[str, SourceEntry]],
    errors: list[str],
) -> None:
    for card in cards.values():
        source = card.data.get("source")
        if not isinstance(source, str) or not source.strip():
            continue
        source = source.strip()
        card_strength = status_strength(card.data)
        if source == "unknown":
            if card_strength is not None and card_strength > STATUS_STRENGTH["candidate"]:
                errors.append(
                    f"{card.path}: source is unknown but status '{card.data.get('status')}' "
                    "is stronger than candidate"
                )
            continue

        source_map = source_maps_for_card(card.path, source_maps)
        if source_map is None:
            errors.append(
                f"{card.path}: source '{source}' cannot be checked because no "
                f"{SOURCE_MAP_FILE} applies to this card"
            )
            continue
        entry = source_map.get(source)
        if entry is None:
            errors.append(f"{card.path}: source '{source}' is not registered in {SOURCE_MAP_FILE}")
            continue
        if card_strength is None:
            continue
        source_strength = SOURCE_TRUST_STRENGTH.get(entry.trust)
        if source_strength is not None and card_strength > source_strength:
            errors.append(
                f"{card.path}: status '{card.data.get('status')}' exceeds source "
                f"trust floor '{entry.trust}' from {entry.path}"
            )


def collect_cards(
    root: str,
    sub_root: str,
    errors: list[str],
    warnings: list[str] | None = None,
) -> dict[str, Card]:
    if warnings is None:
        warnings = []
    cards: dict[str, Card] = {}
    is_staged = os.path.abspath(sub_root) != os.path.abspath(root)

    for dirpath, dirnames, filenames in os.walk(sub_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if not is_staged:
            dirnames[:] = [d for d in dirnames if d != STAGED_DIR]

        for filename in sorted(filenames):
            if not filename.endswith(".md"):
                continue
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, root)
            text = read_markdown(path, root, errors)
            if text is None:
                continue

            frontmatter = parse_frontmatter_block(text, rel)
            if frontmatter is None:
                continue
            errors.extend(frontmatter.errors)
            data = frontmatter.data

            if looks_like_proposal(data):
                if not is_staged:
                    errors.append(f"{rel}: staged proposal metadata is only allowed in staged/")
                    continue
                validate_proposal_shape(rel, data, errors)
                for start_line, block in candidate_blocks(text):
                    card_rel = f"{rel}:{start_line}"
                    card_fm = parse_frontmatter_block(block, card_rel, start_line)
                    if card_fm is None:
                        continue
                    errors.extend(card_fm.errors)
                    if looks_like_card(card_fm.data):
                        add_card(cards, card_rel, card_fm.data, is_staged, errors, warnings)
                continue

            if not looks_like_card(data):
                continue
            add_card(cards, rel, data, is_staged, errors, warnings)

    return cards


def add_card(
    cards: dict[str, Card],
    rel: str,
    data: dict[str, Any],
    is_staged: bool,
    errors: list[str],
    warnings: list[str] | None = None,
) -> None:
    if warnings is None:
        warnings = []
    if is_template_card(data):
        return
    links = validate_card_shape(rel, data, errors, warnings)
    cid = data.get("id")
    if not isinstance(cid, str) or not cid:
        return

    if cid in cards:
        errors.append(f"{rel}: duplicate id '{cid}' (also in {cards[cid].path})")
        return

    cards[cid] = Card(cid=cid, path=rel, data=data, links=links, staged=is_staged)


def check_links(cards: dict[str, Card], known_ids: set[str], errors: list[str]) -> None:
    for card in cards.values():
        for relation, targets in card.links.items():
            if relation not in ALLOWED_LINKS:
                errors.append(f"{card.path}: relation '{relation}' is outside the closed list")
            for target in targets:
                if target not in known_ids:
                    errors.append(
                        f"{card.path}: dangling link {relation} -> '{target}' "
                        "(no card with that id)"
                    )


def check_semantic_links(cards: dict[str, Card], errors: list[str]) -> None:
    for card in cards.values():
        for relation, targets in card.links.items():
            if relation not in ALLOWED_LINKS:
                continue
            for target_id in targets:
                target = cards.get(target_id)
                if target is None:
                    continue

                if relation in {"in-state", "lifecycle"}:
                    if card_type(target) != "state":
                        errors.append(
                            semantic_error(card, relation, target, "target must be type 'state'")
                        )
                elif relation == "measured-by":
                    if not is_metric_concept(target):
                        errors.append(
                            semantic_error(
                                card,
                                relation,
                                target,
                                "target must be a concept with attrs.subtype: metric",
                            )
                        )
                elif relation == "source-of-truth":
                    if not is_source_of_truth_subject(card):
                        errors.append(
                            f"{card.path}: semantic link {relation} from '{card.cid}' "
                            "must start at a state or a concept with attrs.subtype: metric/fact"
                        )
                    if not is_tool_or_system(target):
                        errors.append(
                            semantic_error(
                                card,
                                relation,
                                target,
                                "target must be a production-system or concept with "
                                "attrs.subtype: tool/system",
                            )
                        )
                elif relation == "part-of":
                    if not is_structural_card(card):
                        errors.append(
                            f"{card.path}: semantic link {relation} from '{card.cid}' "
                            "must start at a module or production-system"
                        )
                    if not is_structural_card(target):
                        errors.append(
                            semantic_error(
                                card,
                                relation,
                                target,
                                "target must be a module or production-system",
                            )
                        )
                elif relation == "owns":
                    if not is_business_card(card):
                        errors.append(
                            f"{card.path}: semantic link {relation} from '{card.cid}' "
                            "must start at a business"
                        )
                    if not is_tool_or_system(target):
                        errors.append(
                            semantic_error(
                                card,
                                relation,
                                target,
                                "target must be a production-system or concept with "
                                "attrs.subtype: tool/system",
                            )
                        )
                elif relation == "governed-by":
                    if not is_rule_authority(target):
                        errors.append(
                            semantic_error(
                                card,
                                relation,
                                target,
                                "target must be a decision or concept with attrs.subtype: "
                                "regulation/rule/authority",
                            )
                        )
                elif relation == "supplies-to":
                    if card_type(card) == "concept" and not is_role_concept(card):
                        errors.append(
                            f"{card.path}: semantic link {relation} from '{card.cid}' "
                            "must start at a role concept when authored from a concept"
                        )
                    if not is_role_concept(target):
                        errors.append(
                            semantic_error(
                                card,
                                relation,
                                target,
                                "target must be a concept with attrs.subtype: role",
                            )
                        )
                elif relation == "influences":
                    if not is_influenceable(card):
                        errors.append(
                            f"{card.path}: semantic link {relation} from '{card.cid}' "
                            "must start at a metric, state, or artifact"
                        )
                    if not is_influenceable(target):
                        errors.append(
                            semantic_error(
                                card,
                                relation,
                                target,
                                "target must be a metric, state, or artifact",
                            )
                        )


def check_interface_participant_links(cards: dict[str, Card], known_ids: set[str], errors: list[str]) -> None:
    for card in cards.values():
        if card.data.get("type") != "interface":
            continue
        attrs = card.data.get("attrs")
        if not isinstance(attrs, dict):
            continue
        participants = attrs.get("participants")
        if not isinstance(participants, dict):
            continue
        for role, ids in participants.items():
            if not isinstance(ids, list):
                continue
            for target in ids:
                if isinstance(target, str) and target not in known_ids:
                    errors.append(
                        f"{card.path}: dangling interface participant {role} -> '{target}' "
                        "(no card with that id)"
                    )


def check_owner_resolution(cards: dict[str, Card], warnings: list[str]) -> None:
    """Data model v2, section 2.3: every `owner:` field must resolve to a role
    card or the literal `unknown`. Warning, not error, so migration can land
    before every card's owner is re-pointed at a role id.
    """
    for card in cards.values():
        owner = card.data.get("owner")
        if not isinstance(owner, str):
            continue
        owner = owner.strip()
        if not owner or owner.lower() in {"unknown", "not applicable"}:
            continue
        target = cards.get(owner)
        if target is None or not is_role_concept(target):
            warnings.append(
                f"{card.path}: owner '{owner}' does not resolve to a role card or "
                "'unknown' (data model v2 requires owner: role-id|unknown)"
            )


def check_lifecycle_reciprocity(cards: dict[str, Card], errors: list[str]) -> None:
    """Data model v2, section 2.4: an artifact's `lifecycle` link must point at
    a state card whose `attrs.entity` points back at the same artifact.
    """
    for card in cards.values():
        if card_type(card) != "artifact":
            continue
        for target_id in card.links.get("lifecycle", []):
            target = cards.get(target_id)
            if target is None or card_type(target) != "state":
                continue
            attrs = target.data.get("attrs")
            entity = attrs.get("entity") if isinstance(attrs, dict) else None
            if entity != card.cid:
                errors.append(
                    f"{card.path}: lifecycle -> '{target_id}' but {target.path} "
                    f"attrs.entity is '{entity}', not '{card.cid}' (reciprocity broken)"
                )


def check_owns_part_of_duplicate(cards: dict[str, Card], warnings: list[str]) -> None:
    """Data model v2, section 3, relation #5: `owns` is forbidden between a pair
    that already has `part-of` the other way — the same containment fact
    would otherwise be authored twice under two different relations.

    Warning, not error, for one transitional version: v1's `owns` targeted a
    module's own production-system (module -> production-system) as a
    tool-surrogate pattern that legitimately coexisted with that
    production-system's `part-of` back to the module (see
    examples/acquisition-ontology/modules/acquisition.md and
    production-systems/ps-attraction.md). v2's `owns` narrows to
    business -> tool; hard-failing the old pattern would break a passing v1
    card without changing its content. Promote to an error once the v1
    module/production-system owns+part-of pattern has migrated away.
    """
    for card in cards.values():
        for owned_id in card.links.get("owns", []):
            owned = cards.get(owned_id)
            if owned is None:
                continue
            if card.cid in owned.links.get("part-of", []):
                warnings.append(
                    f"{card.path}: owns -> '{owned_id}' duplicates the fact already "
                    f"stated by {owned.path} part-of -> '{card.cid}' (duplicate fact; "
                    "warning for one transitional version)"
                )


def check_business_produces(cards: dict[str, Card], warnings: list[str]) -> None:
    """Data model v2, section 2.1: a business without `produces` is a
    long-standing audit pattern carried over from v1's module warning.
    """
    for card in cards.values():
        if not is_business_card(card):
            continue
        if not card.links.get("produces"):
            warnings.append(f"{card.path}: business '{card.cid}' has no links.produces")


def check_influences_attrs(cards: dict[str, Card], errors: list[str]) -> None:
    """Data model v2, section 3, relation #10: `links.influences` carries only
    target ids (the parser's flat string-list shape, see parse_list_item_mapping
    docstring for why edge attrs are not authored inline in `links`); polarity
    and delay ride in a parallel `attrs.influences: [{target, polarity, delay?}]`
    block, and evidence is mandatory for every influences claim. This is the
    documented parser-compromise from docs/specs/2026-07-02-data-model-v2.md
    section 7, item 2, and references/ai-ready.md.
    """
    for card in cards.values():
        targets = card.links.get("influences", [])
        if not targets:
            continue

        if not is_truthy_value(card.data.get("evidence")):
            errors.append(
                f"{card.path}: links.influences is present but evidence is empty "
                "(data model v2 requires evidence for every influences claim)"
            )

        attrs = card.data.get("attrs")
        entries = attrs.get("influences") if isinstance(attrs, dict) else None
        entries_by_target: dict[str, dict[str, Any]] = {}
        if not isinstance(entries, list) or not entries:
            errors.append(
                f"{card.path}: links.influences is present but attrs.influences "
                "is missing (data model v2 requires a parallel "
                "attrs.influences: [{target, polarity, delay?}] entry per target)"
            )
        else:
            for entry in entries:
                if not isinstance(entry, dict):
                    errors.append(f"{card.path}: every attrs.influences entry must be a mapping")
                    continue
                entry_target = entry.get("target")
                if not is_truthy_value(entry_target):
                    errors.append(f"{card.path}: attrs.influences entry is missing 'target'")
                    continue
                if not isinstance(entry_target, str):
                    continue
                entries_by_target[entry_target] = entry
                polarity = entry.get("polarity")
                if polarity not in {"+", "-"}:
                    errors.append(
                        f"{card.path}: attrs.influences target '{entry_target}' "
                        "polarity must be '+' or '-'"
                    )

        for target_id in targets:
            if target_id not in entries_by_target:
                errors.append(
                    f"{card.path}: links.influences -> '{target_id}' has no matching "
                    "attrs.influences entry (target/polarity)"
                )


def check_staged_gate(
    staged_cards: dict[str, Card],
    promoted_ids: set[str],
    errors: list[str],
) -> None:
    for card in staged_cards.values():
        for relation, targets in card.links.items():
            if relation != "part-of":
                continue
            for target in targets:
                if target in promoted_ids:
                    errors.append(
                        f"{card.path}: staged card is part-of promoted id '{target}' "
                        "(promote it first; staged proposals cannot graft into accepted model)"
                    )


def scan_pii(root: str, sub_root: str, errors: list[str]) -> None:
    for dirpath, dirnames, filenames in os.walk(sub_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in sorted(filenames):
            if not filename.endswith(".md"):
                continue
            path = os.path.join(dirpath, filename)
            try:
                with open(path, encoding="utf-8") as handle:
                    lines = handle.readlines()
            except Exception:
                continue
            rel = os.path.relpath(path, root)
            for line_no, line in enumerate(lines, start=1):
                for label, pattern in PII_PATTERNS:
                    if pattern.search(line):
                        errors.append(
                            f"{rel}:{line_no}: possible {label} in staged content "
                            "(redact before promotion)"
                        )
                        break


def parse_args(argv: list[str]) -> tuple[str, bool, list[str]]:
    include_staged = False
    positional = []
    errors = []
    for arg in argv:
        if arg == "--staged":
            include_staged = True
        elif arg.startswith("-"):
            errors.append(f"unknown option: {arg}")
        else:
            positional.append(arg)
    root = positional[0] if positional else "."
    return root, include_staged, errors


def main(argv: list[str] | None = None) -> int:
    root, include_staged, errors = parse_args(list(sys.argv[1:] if argv is None else argv))
    root = os.path.abspath(root)
    warnings: list[str] = []

    source_maps = collect_source_maps(root, errors)
    promoted = collect_cards(root, root, errors, warnings)
    promoted_ids = set(promoted)

    staged: dict[str, Card] = {}
    staged_root = os.path.join(root, STAGED_DIR)
    if include_staged and os.path.isdir(staged_root):
        staged = collect_cards(root, staged_root, errors, warnings)
        for cid, card in staged.items():
            if cid in promoted_ids:
                errors.append(
                    f"{card.path}: staged id '{cid}' duplicates promoted "
                    f"{promoted[cid].path}"
                )

    known_ids = set(promoted_ids)
    known_ids.update(staged)
    all_cards = dict(promoted)
    all_cards.update(staged)

    check_links(all_cards, known_ids, errors)
    check_semantic_links(all_cards, errors)
    check_interface_participant_links(all_cards, known_ids, errors)
    check_sources(all_cards, source_maps, errors)
    check_owner_resolution(all_cards, warnings)
    check_lifecycle_reciprocity(all_cards, errors)
    check_owns_part_of_duplicate(all_cards, warnings)
    check_business_produces(all_cards, warnings)
    check_influences_attrs(all_cards, errors)

    if include_staged and os.path.isdir(staged_root):
        check_staged_gate(staged, promoted_ids, errors)
        scan_pii(root, staged_root, errors)

    total = len(promoted) + len(staged)
    scope = "promoted+staged" if include_staged else "promoted"
    print(f"Cards: {total} ({scope})  |  errors: {len(errors)}")
    for error in errors:
        print("  ERROR:", error)
    for warning in warnings:
        print("  WARNING:", warning)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

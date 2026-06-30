#!/usr/bin/env python3
"""Lint human-facing chat examples for leaked technical markers.

The resident agent talks to people in a plain register: no machine ids, schema
field names, status codes, artifact names, relation tokens, or file/tool names.
Those belong in artifacts, not in conversation (see
`agent-os/COMMUNICATION_POLICY.md`).

This linter scans Markdown fenced code blocks whose info string contains the
word ``chat`` (for example ```` ```text chat ````) and fails if any forbidden
pattern appears inside one. It only inspects blocks explicitly marked as chat,
so artifact examples, schemas, and the glossary itself are never flagged.

Usage:
    python3 scripts/chat_register_lint.py <root>
    # exit 0 = clean, exit 1 = violations found
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


# Each entry: (human-readable label, compiled regex). Patterns target markers
# that must never reach a human-facing chat message.
FORBIDDEN = [
    ("machine id", re.compile(r"\b(?:mcpkg|srcevt|sysres|chg|rev|prop)-[a-z0-9]")),
    ("interface id", re.compile(r"\bif-[a-z0-9]+-[a-z0-9]")),
    (
        "schema field name",
        re.compile(
            r"\b(?:claimKind|evidenceGrade|sourceRisk|trustFloor|slaBand|"
            r"reviewEvidenceMode|sourceAdequacy|ontologyRevision|decisionImpact|"
            r"blastRadius|overallAction|highRiskReasons|affectedIds|"
            r"proposedAction|candidateCard|nextAudit)\b"
        ),
    ),
    (
        "status / artifact code",
        re.compile(
            r"(?:staged-proposal-ready|model-change package|review package|"
            r"source event|next-audit|last-reviewed)"
        ),
    ),
    (
        "relation token",
        re.compile(
            r"\b(?:supplies-to|source-of-truth|measured-by|in-state|part-of|"
            r"governed-by)\b"
        ),
    ),
]

_FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
MARKDOWN_NAMES = ("*.md", "*.md.tpl")


def _chat_blocks(text: str):
    """Yield (start_line, list_of_lines) for fenced blocks tagged as chat."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        match = _FENCE.match(lines[i])
        if not match:
            i += 1
            continue
        fence = match.group(2)[0]
        info = match.group(3).strip().lower()
        start = i + 1
        body: list[str] = []
        i += 1
        while i < len(lines):
            close = _FENCE.match(lines[i])
            if close and close.group(2)[0] == fence:
                break
            body.append(lines[i])
            i += 1
        i += 1
        if re.search(r"\bchat\b", info):
            yield start, body


def find_violations(root: Path) -> list[dict]:
    violations: list[dict] = []
    paths = sorted({path for pattern in MARKDOWN_NAMES for path in root.rglob(pattern)})
    for path in paths:
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for start, body in _chat_blocks(text):
            for offset, line in enumerate(body):
                for label, pattern in FORBIDDEN:
                    if pattern.search(line):
                        violations.append(
                            {
                                "file": str(path),
                                "line": start + offset + 1,
                                "kind": label,
                                "text": line.strip(),
                            }
                        )
    return violations


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(".")
    violations = find_violations(root)
    if not violations:
        print("chat-register lint: clean")
        return 0
    for v in violations:
        print(f"{v['file']}:{v['line']}: {v['kind']} in chat block -> {v['text']}")
    print(f"\nchat-register lint: {len(violations)} violation(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

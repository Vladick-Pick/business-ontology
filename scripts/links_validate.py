#!/usr/bin/env python3
"""links_validate.py - integrity check for ontology links (zero dependencies).

Why this exists
---------------
The markdown cards are the source of truth, and links between them carry the
real structure of the model (what produces what, who supplies whom, where a
fact lives). A link is only meaningful if its target actually exists and its
relation is one the contract recognises. A dangling link or an invented
relation is silent rot: queries, the registry graph, and any downstream
consumer (dashboard interpreter, financial overlay) will quietly read a broken
model. This script turns that rot into a visible failure you can fix before it
spreads, so "agent-queryable" stays a guarantee instead of a hope.

It supports manual discipline; it does not replace it. Run it before you commit
edits, and show the output - do not claim "checked" on your word alone.

What it checks (every card, promoted layer)
-------------------------------------------
  - each card has an `id` and a `status`;
  - `id` is unique and opaque (a node id must not contain `--`, which is the
    signature of a name-derived composite id that breaks on rename);
  - `status` is a value from the closed status vocabulary;
  - every relation in the `links` block is from the closed list of 9 relations;
  - every link target resolves to an existing card id (no dangling links).

The staged layer (--staged)
---------------------------
Staged cards are agent *proposals*. The core invariant of this toolkit is
"agent proposes, human commits": a proposal must never silently behave as if it
were already part of the committed model. With `--staged` this script:

  - loads accepted (promoted) cards AND staged cards into the known-id set, so
    a staged card may legitimately link forward to a promoted card (and to
    other staged cards) and still resolve;
  - rejects any staged card that claims to be `part-of` a promoted card. That
    edge would graft an unreviewed proposal directly into the committed
    structure - exactly the gate a human approval is supposed to hold;
  - scans staged content for PII / secret patterns. Incoming material is
    untrusted and sits at the trust floor; the repo must stay free of personal
    data and credentials, so we catch leaks at the staging boundary rather than
    after promotion.

Without `--staged`, the `staged/` directory is skipped entirely: the promoted
layer is validated on its own, and a half-finished proposal cannot fail the
gate that protects the committed model.

Usage
-----
  python3 scripts/links_validate.py [ontology-root]            # default: .
  python3 scripts/links_validate.py [ontology-root] --staged   # include staged

Exit codes: 0 - clean, 1 - errors found.
"""
import os
import re
import sys

# The closed list of 9 relations (kebab-case, English). A relation outside this
# set is a validation error, not a one-off invention: extending the list is a
# deliberate decision recorded in CHANGELOG, then added here first.
ALLOWED_LINKS = {
    "produces",
    "consumes",
    "supplies-to",
    "part-of",
    "owns",
    "measured-by",
    "source-of-truth",
    "in-state",
    "governed-by",
}

# The closed status vocabulary. Concept/module/etc. cards use the first set;
# decision cards use a dedicated lifecycle. We accept the union so a decision
# card's `status: proposed` is not flagged as unknown.
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
KNOWN_STATUSES = CARD_STATUSES | DECISION_STATUSES

# Directory name that holds staged proposals, relative to the ontology root.
STAGED_DIR = "staged"

# Directories never walked: VCS, deps, the derived machine layer, and tooling.
# The registry is generated from cards, so validating it would double-count ids.
SKIP_DIRS = {".git", "node_modules", "registry", "scripts"}

# --- Frontmatter parsing (minimal YAML-ish, no external deps) -----------------

# Leading frontmatter block delimited by --- ... ---.
FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
ID_RE = re.compile(r"^id:\s*(.+?)\s*$", re.MULTILINE)
STATUS_RE = re.compile(r"^status:\s*(.+?)\s*$", re.MULTILINE)
# The `links:` block: the header line, then the indented relation lines below it.
LINKS_BLOCK = re.compile(r"^links:\s*\n((?:[ \t]+.*\n?)*)", re.MULTILINE)
# One relation line inside the block, e.g. `  measured-by: [lead-quality]`.
LINK_LINE = re.compile(r"^[ \t]+([\w\-]+):\s*\[([^\]]*)\]\s*$")
# Tokenises ids inside the [...] list. Ids are opaque kebab-case slugs.
ID_TOKEN = re.compile(r"[\w\-]+")

# --- PII / secret patterns (staged scan) -------------------------------------
# Coarse, high-signal patterns. The point is to keep personal data and
# credentials out of the repo at the staging boundary, not to be a full DLP
# scanner. False positives are cheap to resolve (rephrase or redact); a leaked
# secret in git history is not.
PII_PATTERNS = [
    ("email address", re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")),
    # E.164-ish phone numbers: optional +, 10-15 digits, allowing spaces/dashes.
    ("phone number", re.compile(r"(?<!\w)\+?\d[\d\s\-]{8,}\d(?!\w)")),
    # Long digit runs that look like card / account numbers (13-19 digits).
    ("card/account number", re.compile(r"(?<!\d)\d{13,19}(?!\d)")),
    # Common secret-bearing key names with an assigned value.
    (
        "secret / credential",
        re.compile(
            r"(?i)\b(api[_\-]?key|secret|token|password|passwd|bearer|"
            r"private[_\-]?key)\b\s*[:=]\s*\S+"
        ),
    ),
]


def parse_card(text):
    """Parse one markdown file into a card dict, or None if it is not a card.

    A card is recognised by having frontmatter with at least an `id` or a
    `links` block. Files that merely have frontmatter (e.g. a SKILL.md with
    name/description) are not ontology cards and are skipped, so the validator
    stays scoped to the model and does not flag tooling docs.
    """
    m = FRONTMATTER.search(text)
    if not m:
        return None
    fm = m.group(1)

    idm = ID_RE.search(fm)
    cid = idm.group(1).strip() if idm else None

    statusm = STATUS_RE.search(fm)
    status = statusm.group(1).strip() if statusm else None

    links = []
    lb = LINKS_BLOCK.search(fm)
    if lb:
        for line in lb.group(1).splitlines():
            lm = LINK_LINE.match(line)
            if not lm:
                continue
            rel = lm.group(1)
            targets = ID_TOKEN.findall(lm.group(2))
            # Drop template placeholders such as <id> that survive tokenising.
            targets = [t for t in targets if not t.startswith("<")]
            links.append((rel, targets))

    # Frontmatter present but no id and no links: not an ontology card.
    if cid is None and not links:
        return None
    return {"id": cid, "status": status, "links": links}


def collect_cards(root, sub_root, errors):
    """Walk a tree and return {id: {file, status, links, staged}} of its cards.

    `sub_root` is the directory actually walked (root, or root/staged). `root`
    is used only to compute display-relative paths. Duplicate-id and bad-id
    checks run here so errors are reported once per card as it is discovered;
    `staged` marks where the card came from for layer-specific rules later.
    """
    cards = {}
    is_staged = os.path.abspath(sub_root) != os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(sub_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        # When walking the promoted layer, never descend into staged/.
        if not is_staged:
            dirnames[:] = [d for d in dirnames if d != STAGED_DIR]
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except Exception as exc:
                errors.append(f"{os.path.relpath(path, root)}: unreadable ({exc})")
                continue
            card = parse_card(text)
            if card is None:
                continue  # not an ontology card
            rel = os.path.relpath(path, root)

            cid = card["id"]
            if not cid:
                errors.append(f"{rel}: missing id field")
                continue
            if cid.startswith("<"):
                continue  # template stub, not a real card

            if "--" in cid:
                errors.append(
                    f"{rel}: node id '{cid}' contains '--' "
                    f"(looks derived from names; ids must be opaque and stable)"
                )

            status = card["status"]
            if status is None:
                errors.append(f"{rel}: missing status field")
            elif status not in KNOWN_STATUSES:
                errors.append(
                    f"{rel}: status '{status}' is outside the closed vocabulary "
                    f"({', '.join(sorted(KNOWN_STATUSES))})"
                )

            if cid in cards:
                errors.append(
                    f"{rel}: duplicate id '{cid}' (also in {cards[cid]['file']})"
                )
                continue

            cards[cid] = {
                "file": rel,
                "status": status,
                "links": card["links"],
                "staged": is_staged,
            }
    return cards


def check_links(cards, known, errors):
    """Verify every relation is allowed and every target resolves."""
    for info in cards.values():
        for rel, targets in info["links"]:
            if rel not in ALLOWED_LINKS:
                errors.append(
                    f"{info['file']}: relation '{rel}' is outside the closed list"
                )
            for t in targets:
                if t not in known:
                    errors.append(
                        f"{info['file']}: dangling link {rel} -> '{t}' "
                        f"(no card with that id)"
                    )


def check_staged_gate(staged_cards, promoted_ids, errors):
    """Enforce that a staged proposal cannot graft itself onto the committed model.

    A staged card claiming `part-of` a promoted card would insert an unreviewed
    proposal directly into the committed structure, bypassing the human commit
    gate. Forward links of other relation types are fine (a proposal naturally
    references the model it extends); only structural membership is gated.
    """
    for info in staged_cards.values():
        for rel, targets in info["links"]:
            if rel != "part-of":
                continue
            for t in targets:
                if t in promoted_ids:
                    errors.append(
                        f"{info['file']}: staged card is part-of promoted id '{t}' "
                        f"(staged must never be part of the accepted model; "
                        f"promote it first)"
                    )


def scan_pii(root, sub_root, errors):
    """Scan a tree's markdown for PII / secret patterns and report matches.

    Untrusted material enters through staging; keeping it free of personal data
    and credentials at this boundary protects the repo and its git history.
    """
    for dirpath, dirnames, filenames in os.walk(sub_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, encoding="utf-8") as fh:
                    lines = fh.readlines()
            except Exception:
                continue  # unreadable files are already reported by collect_cards
            rel = os.path.relpath(path, root)
            for lineno, line in enumerate(lines, start=1):
                for label, pat in PII_PATTERNS:
                    if pat.search(line):
                        errors.append(
                            f"{rel}:{lineno}: possible {label} in staged content "
                            f"(redact before promotion)"
                        )
                        break  # one finding per line is enough to flag it


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    include_staged = False
    positional = []
    for arg in argv:
        if arg == "--staged":
            include_staged = True
        elif arg.startswith("-"):
            print(f"unknown option: {arg}", file=sys.stderr)
            return 1
        else:
            positional.append(arg)
    root = positional[0] if positional else "."

    errors = []

    # Promoted layer: always validated, staged/ excluded.
    promoted = collect_cards(root, root, errors)
    promoted_ids = set(promoted)

    staged = {}
    staged_root = os.path.join(root, STAGED_DIR)
    if include_staged and os.path.isdir(staged_root):
        staged = collect_cards(root, staged_root, errors)
        # A staged id colliding with a promoted id is a duplicate across layers.
        for cid, info in staged.items():
            if cid in promoted_ids:
                errors.append(
                    f"{info['file']}: staged id '{cid}' duplicates promoted "
                    f"{promoted[cid]['file']}"
                )

    # Link integrity. Targets resolve against the layers in scope: promoted
    # alone by default, promoted + staged when staging is included (so a staged
    # card may link forward to the model it extends).
    known = set(promoted_ids)
    known.update(staged.keys())
    all_cards = dict(promoted)
    all_cards.update(staged)
    check_links(all_cards, known, errors)

    if include_staged and staged:
        check_staged_gate(staged, promoted_ids, errors)
        scan_pii(root, staged_root, errors)

    total = len(promoted) + len(staged)
    scope = "promoted+staged" if include_staged else "promoted"
    print(f"Cards: {total} ({scope})  |  errors: {len(errors)}")
    for e in errors:
        print("  ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

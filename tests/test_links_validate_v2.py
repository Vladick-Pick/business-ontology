"""Data model v2 contract tests for scripts/links_validate.py.

Covers the six behaviors named in plans/002-data-model-v2-schemas-and-validator.md
step 6: v2 types validate; the module alias warns, not errors; a metric with a
foreign attrs key errors; a broken influences authoring shape errors; and
reason-codes[].on outside terminal errors. The fourth named case in the plan
(owns+part-of on the same pair -> error) is implemented as a warning instead
-- see the test docstring below for why, and
docs/specs/2026-07-02-data-model-v2.md / scripts/links_validate.py's
check_owns_part_of_duplicate docstring for the full reasoning.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]

SOURCE_MAP = """# Source map

| Source id | Trust | Owner | Access mode | Read policy | Meaning |
|---|---|---|---|---|---|
| `fixture-source` | accepted | tester | fixture | readOnly=true; piiExcluded=true; rawPayloadAccess=false | v2 contract fixture. |
"""


def run_validator(root, *args):
    return subprocess.run(
        [sys.executable, "scripts/links_validate.py", str(root), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )


def write_card(root: Path, relpath: str, content: str) -> None:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class V2TypesAcceptedTests(unittest.TestCase):
    """Case 1: every v2 type validates cleanly with a minimal legal card."""

    def test_all_eleven_v2_types_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_card(root, "02-source-map.md", SOURCE_MAP)
            write_card(
                root,
                "business/biz-x.md",
                """---
id: biz-x
type: business
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
links:
  produces: [a-x]
---

# Business x
""",
            )
            write_card(
                root,
                "roles/r-x.md",
                """---
id: r-x
type: role
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  kind: role
---

# Role x
""",
            )
            write_card(
                root,
                "production-systems/ps-x.md",
                """---
id: ps-x
type: production-system
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  business: biz-x
---

# PS x
""",
            )
            write_card(
                root,
                "artifacts/a-x.md",
                """---
id: a-x
type: artifact
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  kind: intermediate
links:
  lifecycle: [st-x]
---

# Artifact x
""",
            )
            write_card(
                root,
                "tools/t-x.md",
                """---
id: t-x
type: tool
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  kind: system
---

# Tool x
""",
            )
            write_card(
                root,
                "metrics/m-x.md",
                """---
id: m-x
type: metric
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  formula: unknown
  unit: unknown
  direction: up-is-good
  binding: unknown
---

# Metric x
""",
            )
            write_card(
                root,
                "states/st-x.md",
                """---
id: st-x
type: state
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  entity: a-x
  states: [a, b]
  entry: [a]
  terminal: [b]
  transitions:
    - from: a
      to: b
      trigger: go
---

# State x
""",
            )
            write_card(
                root,
                "processes/p-x.md",
                """---
id: p-x
type: process
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  production-system: ps-x
  steps:
    - id: step-1
      role: r-x
      does: does something
---

# Process x
""",
            )
            write_card(
                root,
                "interfaces/if-x.md",
                """---
id: if-x
type: interface
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  contract: handoff
  participants:
    supplier: [r-x]
    customer: [r-x]
    subject: [a-x]
  outcome: something happened
  quality-criterion: fixture criterion
---

# Interface x
""",
            )
            write_card(
                root,
                "decisions/d-x.md",
                """---
id: d-x
type: decision
status: proposed
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  norm-kind: decided
  irreversible: false
  episode: fixture episode
  scope: fixture scope
  decision-owner: unknown
  transition-authority: unknown
  measurement-convention: not applicable
  affected-workflows: unknown
  affected-kpis: unknown
  propagation-sla: unknown
  override-policy: unknown
  exception-path: unknown
  blast-radius: unknown
---

# Decision x
""",
            )
            write_card(
                root,
                "terms/tm-x.md",
                """---
id: tm-x
type: term
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  applies-to: [a-x, biz-x]
---

# Term x
""",
            )

            result = run_validator(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("errors: 0", result.stdout)
        self.assertIn("Cards: 11", result.stdout)


class ModuleAliasWarnsTests(unittest.TestCase):
    """Case 2: type: module validates but emits a deprecation warning, not
    an error -- this is the mechanism that keeps examples/acquisition-ontology/
    passing without a forced rewrite for one transitional version.
    """

    def test_module_type_warns_not_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_card(root, "02-source-map.md", SOURCE_MAP)
            write_card(
                root,
                "modules/mod-x.md",
                """---
id: mod-x
type: module
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  parent-module: not applicable
  submodules: not applicable
---

# Module x
""",
            )

            result = run_validator(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("errors: 0", result.stdout)
        self.assertIn("WARNING: modules/mod-x.md: type 'module' is deprecated", result.stdout)


class MetricForeignAttrsKeyTests(unittest.TestCase):
    """Case 3: a metric card with an attrs key outside its closed contract
    (e.g. a state-only key like `states`) is a hard error.
    """

    def test_metric_with_foreign_attrs_key_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_card(root, "02-source-map.md", SOURCE_MAP)
            write_card(
                root,
                "metrics/m-bad.md",
                """---
id: m-bad
type: metric
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  formula: unknown
  unit: unknown
  direction: up-is-good
  binding: unknown
  states: [a, b]
---

# Bad metric
""",
            )

            result = run_validator(root)

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "attrs.states is not allowed for type 'metric'", result.stdout + result.stderr
        )


class OwnsPartOfDuplicateTests(unittest.TestCase):
    """Case 4 (plan's stated shape: owns+part-of on the same pair -> error).

    Implemented as a WARNING, not an error, for one transitional version.
    v1's `owns` targeted a module's own production-system as a
    tool-surrogate pattern (module -> production-system) that legitimately
    coexists with that production-system's `part-of` back to the module --
    see examples/acquisition-ontology/modules/acquisition.md and
    production-systems/ps-attraction.md, which authors exactly this pattern
    and is a Done-criteria fixture required to stay at 0 errors without
    being edited. v2's `owns` narrows to business -> tool; hard-failing the
    old pattern would break that passing v1 card. See
    check_owns_part_of_duplicate's docstring in scripts/links_validate.py
    for the full reasoning. This test asserts the actual (warning)
    behavior, not the plan's literal error framing.
    """

    def test_owns_and_part_of_same_pair_warns(self):
        """`owns` requires a business source and a tool/production-system
        target (is_tool_or_system); `part-of` requires structural endpoints
        (business/module/production-system) on both sides -- a tool is not
        a legal part-of endpoint. So the pair that actually exercises the
        owns+part-of duplicate-fact check without also tripping the
        part-of endpoint-type check is business owns production-system +
        production-system part-of business, mirroring the exact pattern in
        examples/acquisition-ontology/modules/acquisition.md (owns:
        [ps-attraction]) and production-systems/ps-attraction.md (part-of:
        [acquisition]) -- the v1 fixture this warning-not-error decision
        exists to keep passing.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_card(root, "02-source-map.md", SOURCE_MAP)
            write_card(
                root,
                "business/biz-x.md",
                """---
id: biz-x
type: business
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
links:
  owns: [ps-x]
---

# Business x
""",
            )
            write_card(
                root,
                "production-systems/ps-x.md",
                """---
id: ps-x
type: production-system
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  business: biz-x
links:
  part-of: [biz-x]
---

# PS x
""",
            )

            result = run_validator(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("errors: 0", result.stdout)
        self.assertIn("duplicate fact", result.stdout)
        self.assertIn("WARNING:", result.stdout)


class ReasonCodeOutsideTerminalTests(unittest.TestCase):
    """Case 5: reason-codes[].on must be one of attrs.terminal."""

    def test_reason_code_on_non_terminal_state_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_card(root, "02-source-map.md", SOURCE_MAP)
            write_card(
                root,
                "artifacts/a-x.md",
                """---
id: a-x
type: artifact
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  kind: intermediate
---

# Artifact x
""",
            )
            write_card(
                root,
                "states/st-x.md",
                """---
id: st-x
type: state
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  entity: a-x
  states: [a, b, c]
  entry: [a]
  terminal: [c]
  transitions:
    - from: a
      to: b
      trigger: go
    - from: b
      to: c
      trigger: finish
  reason-codes:
    - on: b
      codes:
        - code: not-terminal
          meaning: this state is not in terminal
---

# State x
""",
            )

            result = run_validator(root)

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "attrs.reason-codes.on 'b' is not in attrs.terminal", result.stdout + result.stderr
        )


class InfluencesFormatTests(unittest.TestCase):
    """Case 6: a broken influences authoring shape is an error. Covers all
    three failure modes the parallel-attrs compromise depends on: missing
    evidence, missing attrs.influences, and a bad polarity value.
    """

    def _base_cards(self, root: Path) -> None:
        write_card(root, "02-source-map.md", SOURCE_MAP)
        write_card(
            root,
            "metrics/m-two.md",
            """---
id: m-two
type: metric
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  formula: unknown
  unit: unknown
  direction: up-is-good
  binding: unknown
---

# Metric two
""",
        )

    def test_missing_evidence_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._base_cards(root)
            write_card(
                root,
                "metrics/m-one.md",
                """---
id: m-one
type: metric
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
attrs:
  formula: unknown
  unit: unknown
  direction: up-is-good
  binding: unknown
  influences:
    - target: m-two
      polarity: "+"
links:
  influences: [m-two]
---

# Metric one
""",
            )

            result = run_validator(root)

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "links.influences is present but evidence is empty", result.stdout + result.stderr
        )

    def test_missing_attrs_influences_block_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._base_cards(root)
            write_card(
                root,
                "metrics/m-one.md",
                """---
id: m-one
type: metric
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
evidence: [srcevt-fixture]
attrs:
  formula: unknown
  unit: unknown
  direction: up-is-good
  binding: unknown
links:
  influences: [m-two]
---

# Metric one
""",
            )

            result = run_validator(root)

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "links.influences is present but attrs.influences is missing",
            result.stdout + result.stderr,
        )

    def test_bad_polarity_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._base_cards(root)
            write_card(
                root,
                "metrics/m-one.md",
                """---
id: m-one
type: metric
status: candidate
source: fixture-source
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-09-30
evidence: [srcevt-fixture]
attrs:
  formula: unknown
  unit: unknown
  direction: up-is-good
  binding: unknown
  influences:
    - target: m-two
      polarity: up
links:
  influences: [m-two]
---

# Metric one
""",
            )

            result = run_validator(root)

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("polarity must be '+' or '-'", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

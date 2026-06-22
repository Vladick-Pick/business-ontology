import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "links_validate.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("links_validate", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_validator(path, *args):
    return subprocess.run(
        [sys.executable, "scripts/links_validate.py", str(path), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )


class ParserTests(unittest.TestCase):
    def test_parses_scalar_inline_list_block_list_and_nested_attrs(self):
        validator = load_validator()
        text = """---
id: if-example
type: interface
status: candidate
source: fixture
owner: tester
last-reviewed: 2026-06-22
next-audit: 2026-09-22
attrs:
  participants:
    supplier: [role-a]
    customer:
      - role-b
    subject:
      - output-c
  quality-criterion: accepted by customer
  outcome: output accepted
links:
  supplies-to: [role-b]
  governed-by:
    - d-rule
---

# Example
"""
        parsed = validator.parse_frontmatter_block(text, "fixture.md")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.errors, [])
        self.assertEqual(parsed.data["id"], "if-example")
        self.assertEqual(parsed.data["attrs"]["participants"]["supplier"], ["role-a"])
        self.assertEqual(parsed.data["attrs"]["participants"]["customer"], ["role-b"])
        self.assertEqual(parsed.data["links"]["supplies-to"], ["role-b"])
        self.assertEqual(parsed.data["links"]["governed-by"], ["d-rule"])

    def test_malformed_yaml_list_reports_an_error(self):
        validator = load_validator()
        text = """---
id: malformed
type: concept
status: accepted
source: fixture
owner: tester
last-reviewed: 2026-06-22
next-audit: 2026-09-22
links:
  measured-by:
    metric
---

# Malformed
"""
        parsed = validator.parse_frontmatter_block(text, "fixture.md")

        self.assertIsNotNone(parsed)
        self.assertTrue(
            any("malformed mapping line" in error for error in parsed.errors),
            parsed.errors,
        )

    def test_parses_source_map_table(self):
        validator = load_validator()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_map = root / "02-source-map.md"
            source_map.write_text(
                """# Source map

| Source id | Trust | Owner | Access mode | Read policy | Meaning |
|---|---|---|---|---|---|
| `fixture-source` | candidate | tester | fixture | readOnly=true; piiExcluded=true; rawPayloadAccess=false | Fixture source. |
""",
                encoding="utf-8",
            )
            errors = []
            entries = validator.parse_source_map(str(source_map), str(root), errors)

        self.assertEqual(errors, [])
        self.assertIn("fixture-source", entries)
        self.assertEqual(entries["fixture-source"].trust, "candidate")
        self.assertFalse(entries["fixture-source"].read_policy["rawPayloadAccess"])


class ValidatorIntegrationTests(unittest.TestCase):
    def test_valid_example_passes(self):
        result = run_validator("examples/acquisition-ontology")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("errors: 0", result.stdout)

    def test_repo_passes_promoted_and_staged_validation(self):
        promoted = run_validator(".")
        staged = run_validator(".", "--staged")

        self.assertEqual(promoted.returncode, 0, promoted.stdout + promoted.stderr)
        self.assertEqual(staged.returncode, 0, staged.stdout + staged.stderr)
        self.assertIn("errors: 0", promoted.stdout)
        self.assertIn("errors: 0", staged.stdout)


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_build(root, out_dir):
    # Avoid PIPE capture here: local shell/watch hooks can inherit pipes and
    # keep subprocess.run waiting for EOF after the child exits.
    with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w+") as stdout_file:
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w+") as stderr_file:
            result = subprocess.run(
                [sys.executable, "scripts/build_registry.py", str(root), "--out", str(out_dir)],
                cwd=REPO_ROOT,
                text=True,
                stdout=stdout_file,
                stderr=stderr_file,
                timeout=30,
            )
            stdout_file.seek(0)
            stderr_file.seek(0)
            return subprocess.CompletedProcess(
                args=result.args,
                returncode=result.returncode,
                stdout=stdout_file.read(),
                stderr=stderr_file.read(),
            )


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class BuildRegistryTests(unittest.TestCase):
    def test_builds_expected_nodes_edges_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "registry"
            result = run_build("examples/acquisition-ontology", out_dir)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            nodes = read_json(out_dir / "nodes.json")
            edges = read_json(out_dir / "edges.json")
            manifest = read_json(out_dir / "manifest.json")

        node_ids = {node["id"] for node in nodes}
        edge_ids = {edge["id"] for edge in edges}

        self.assertEqual(manifest["validator-status"], "pass")
        self.assertEqual(manifest["node-count"], 14)
        self.assertIn("qualified-lead", node_ids)
        self.assertIn("acquisition", node_ids)
        self.assertIn("if-attraction-sales", node_ids)
        self.assertIn("d-handoff-quality", node_ids)
        self.assertIn("ps-attraction::produces::qualified-lead", edge_ids)
        self.assertIn("if-attraction-sales::has-supplier::role-attraction-supplier", edge_ids)
        self.assertIn("if-attraction-sales::has-customer::role-sales-customer", edge_ids)
        self.assertIn("if-attraction-sales::has-subject::qualified-lead", edge_ids)
        self.assertIn("role-attraction-supplier::supplies-to::role-sales-customer", edge_ids)

    def test_interface_supplies_to_edge_carries_interface_attrs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "registry"
            result = run_build("examples/acquisition-ontology", out_dir)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            edges = read_json(out_dir / "edges.json")

        supply_edge = next(
            edge
            for edge in edges
            if edge["id"] == "role-attraction-supplier::supplies-to::role-sales-customer"
        )
        self.assertEqual(supply_edge["attrs"]["source"], "interface-decomposition")
        self.assertEqual(supply_edge["attrs"]["interface"], "if-attraction-sales")
        self.assertEqual(supply_edge["attrs"]["subject"], "qualified-lead")

    def test_decision_attrs_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "registry"
            result = run_build("examples/acquisition-ontology", out_dir)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            nodes = read_json(out_dir / "nodes.json")

        decision = next(node for node in nodes if node["id"] == "d-handoff-quality")
        self.assertFalse(decision["attrs"]["irreversible"])
        self.assertEqual(decision["attrs"]["decision-owner"], "revenue-lead")
        self.assertEqual(decision["attrs"]["affected-kpis"], ["lead-quality"])
        self.assertIn("sales queue", decision["attrs"]["blast-radius"])

    def test_staged_cards_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ontology"
            shutil.copytree(REPO_ROOT / "examples" / "acquisition-ontology", root)
            staged = root / "staged"
            staged.mkdir()
            (staged / "prop-staged-card.md").write_text(
                """---
proposal-id: prop-staged-card
target: new
diff:
  was: (none)
  now: staged-only card
basis: Test staged exclusion.
source-locator: test
confidence: medium
input: agent-inference
originating-skill: propose-change
ttl: 2026-07-22
validator-result: pass
---

# Staged card proposal

```markdown
---
id: staged-only
type: concept
status: candidate
source: fixture
owner: tester
last-reviewed: 2026-06-22
next-audit: 2026-09-22
attrs:
  subtype: other
---

# Staged only
```
""",
                encoding="utf-8",
            )
            out_dir = Path(tmp) / "registry"
            result = run_build(root, out_dir)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            nodes = read_json(out_dir / "nodes.json")

        self.assertNotIn("staged-only", {node["id"] for node in nodes})

    def test_refuses_invalid_input_before_emitting(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "registry"
            result = run_build("fixtures/invalid/dangling-link", out_dir)

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("validation failed", result.stderr)
            self.assertFalse((out_dir / "nodes.json").exists())


if __name__ == "__main__":
    unittest.main()

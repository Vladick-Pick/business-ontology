"""Tests for scripts/migrate_taxonomy_v2.py: --dry-run writes nothing, and
a real run is idempotent (a second run reports "nothing to do" and changes
zero bytes). Both are named cases in
plans/002-data-model-v2-schemas-and-validator.md step 6.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_SOURCE = REPO_ROOT / "examples" / "acquisition-ontology"


def run_migrate(root, *args):
    return subprocess.run(
        [sys.executable, "scripts/migrate_taxonomy_v2.py", str(root), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )


def snapshot_tree(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*.md")):
        files[str(path.relative_to(root))] = path.read_text(encoding="utf-8")
    return files


def write_legacy_module_card(root: Path) -> None:
    path = root / "modules" / "legacy-module.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "id: legacy-module\n"
        "type: module\n"
        "status: draft\n"
        "source: example-acquisition-source\n"
        "owner: unknown\n"
        "last-reviewed: 2026-07-02\n"
        "next-audit: 2026-09-30\n"
        "attrs:\n"
        "  parent-module: acquisition\n"
        "---\n\n"
        "# Legacy module\n",
        encoding="utf-8",
    )


class DryRunWritesNothingTests(unittest.TestCase):
    def test_dry_run_prints_a_plan_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "acquisition-ontology"
            shutil.copytree(FIXTURE_SOURCE, root)
            write_legacy_module_card(root)
            before = snapshot_tree(root)

            result = run_migrate(root, "--dry-run")

            after = snapshot_tree(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Cards would change:", result.stdout)
        self.assertIn("module -> business", result.stdout)
        self.assertEqual(before, after, "dry-run must not modify any file")

    def test_dry_run_on_a_directory_with_nothing_to_migrate_reports_nothing_to_do(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "empty-ontology"
            root.mkdir()
            (root / "02-source-map.md").write_text(
                "# Source map\n\n"
                "| Source id | Trust | Owner | Access mode | Read policy | Meaning |\n"
                "|---|---|---|---|---|---|\n"
                "| `fixture-source` | accepted | tester | fixture | "
                "readOnly=true; piiExcluded=true; rawPayloadAccess=false | Empty fixture. |\n",
                encoding="utf-8",
            )
            (root / "business" / "biz-x.md").parent.mkdir(parents=True, exist_ok=True)
            (root / "business" / "biz-x.md").write_text(
                "---\n"
                "id: biz-x\n"
                "type: business\n"
                "status: candidate\n"
                "source: fixture-source\n"
                "owner: unknown\n"
                "last-reviewed: 2026-07-02\n"
                "next-audit: 2026-09-30\n"
                "---\n\n"
                "# Business x\n",
                encoding="utf-8",
            )

            result = run_migrate(root, "--dry-run")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Nothing to do", result.stdout)


class IdempotencyTests(unittest.TestCase):
    def test_second_run_reports_nothing_to_do_and_changes_zero_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "acquisition-ontology"
            shutil.copytree(FIXTURE_SOURCE, root)
            write_legacy_module_card(root)

            first = run_migrate(root)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertIn("Cards changed:", first.stdout)

            after_first = snapshot_tree(root)

            second = run_migrate(root)
            after_second = snapshot_tree(root)

        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("Nothing to do", second.stdout)
        self.assertEqual(
            after_first, after_second, "a second migration run must change zero bytes"
        )

    def test_real_run_does_not_touch_the_repo_fixture(self):
        """Guard against a regression where main() resolves the wrong root:
        migrating a /tmp copy must never write back to the repo's own
        examples/acquisition-ontology/.
        """
        self.assertTrue(FIXTURE_SOURCE.is_dir())
        before_mtimes = {
            path: path.stat().st_mtime for path in FIXTURE_SOURCE.rglob("*.md")
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "acquisition-ontology"
            shutil.copytree(FIXTURE_SOURCE, root)
            run_migrate(root)

        after_mtimes = {
            path: path.stat().st_mtime for path in FIXTURE_SOURCE.rglob("*.md")
        }
        self.assertEqual(before_mtimes, after_mtimes)


if __name__ == "__main__":
    unittest.main()

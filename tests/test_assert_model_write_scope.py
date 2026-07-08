import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "assert_model_write_scope.py"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class AssertModelWriteScopeTests(unittest.TestCase):
    def run_script(self, args: list[str]) -> tuple[int, dict]:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args, "--json"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = json.loads(result.stdout)
        return result.returncode, payload

    def test_safe_scope_allows_staged_and_refuses_accepted_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "access.json"
            model = root / "model"
            write_json(
                config,
                {
                    "agent_id": "business-ontology-resident",
                    "access_modes": ["read-model", "write-staged", "open-review"],
                    "accepted_branch": "main",
                    "staged_branch_pattern": "staged/*",
                    "production_model_repo": False,
                    "generated_at": "2026-07-08T10:00:00Z",
                },
            )

            code, payload = self.run_script(["--access-config", str(config), "--model-root", str(model)])

            self.assertEqual(code, 0, payload)
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["checks"]["staged_write"], "passed")
            self.assertEqual(payload["checks"]["accepted_write"], "refused")
            self.assertEqual(payload["checks"]["generic_accepted_update"], "unavailable")
            self.assertTrue((model / "staged" / "scope-proof.md").is_file())
            self.assertFalse((model / "accepted" / "scope-proof.md").exists())
            self.assertFalse((model / "accepted" / "README.md").exists())
            self.assertFalse((model / "accepted").exists())

    def test_write_accepted_mode_is_unsafe_even_if_staged_write_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "access.json"
            write_json(
                config,
                {
                    "agent_id": "business-ontology-resident",
                    "access_modes": ["read-model", "write-staged", "write-accepted"],
                    "accepted_branch": "main",
                    "staged_branch_pattern": "staged/*",
                    "production_model_repo": False,
                    "generated_at": "2026-07-08T10:00:00Z",
                },
            )

            code, payload = self.run_script(["--access-config", str(config), "--model-root", str(root / "model")])

            self.assertEqual(code, 3, payload)
            self.assertEqual(payload["status"], "unsafe")
            self.assertIn("write-accepted", payload["reason"])

    def test_missing_staged_write_is_operational_failure_not_safety_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "access.json"
            write_json(
                config,
                {
                    "agent_id": "business-ontology-resident",
                    "access_modes": ["read-model", "open-review"],
                    "accepted_branch": "main",
                    "staged_branch_pattern": "staged/*",
                    "production_model_repo": False,
                    "generated_at": "2026-07-08T10:00:00Z",
                },
            )

            code, payload = self.run_script(["--access-config", str(config), "--model-root", str(root / "model")])

            self.assertEqual(code, 4, payload)
            self.assertEqual(payload["status"], "misconfigured")
            self.assertEqual(payload["checks"]["staged_write"], "denied")

    def test_incomplete_policy_shape_is_config_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "access.json"
            write_json(
                config,
                {
                    "agent_id": "business-ontology-resident",
                    "access_modes": ["read-model", "write-staged", "open-review"],
                    "accepted_branch": "main",
                    "staged_branch_pattern": "staged/*",
                    "generated_at": "2026-07-08T10:00:00Z",
                },
            )

            code, payload = self.run_script(["--access-config", str(config), "--model-root", str(root / "model")])

            self.assertEqual(code, 2, payload)
            self.assertEqual(payload["status"], "config-error")
            self.assertIn("production_model_repo", payload["reason"])


if __name__ == "__main__":
    unittest.main()

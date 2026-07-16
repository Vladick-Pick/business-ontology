import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts import migrate_workspace_v0_11_15 as migration


class WorkspaceV01115MigrationTests(unittest.TestCase):
    def make_workspace(self, root: Path, *, version: str = "0.11.15") -> Path:
        workspace = root / "workspace"
        (workspace / "agent-state").mkdir(parents=True)
        (workspace / "PACKAGE_VERSION.lock").write_text(
            json.dumps(
                {
                    "current_version": version,
                    "previous_version": "0.11.14",
                    "tag": f"v{version}",
                    "commit": "a" * 40,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (workspace / "runtime-config.json").write_text(
            json.dumps({"module_id": "interlab", "unrelated": {"keep": True}}) + "\n",
            encoding="utf-8",
        )
        (workspace / ".gitignore").write_text("/raw/\n", encoding="utf-8")
        return workspace

    def test_apply_creates_private_empty_policy_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))

            result = migration._apply(workspace)
            replay = migration._apply(workspace)

            config = json.loads((workspace / "runtime-config.json").read_text(encoding="utf-8"))
            policy_path = workspace / "agent-state" / "review-authority.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "migrated")
            self.assertEqual(replay["status"], "already-current")
            self.assertEqual(
                config["review_authority_policy_path"],
                "agent-state/review-authority.json",
            )
            self.assertTrue(config["unrelated"]["keep"])
            self.assertEqual(policy["businessId"], "interlab")
            self.assertEqual(policy["channels"], [])
            self.assertEqual(os.stat(policy_path).st_mode & 0o777, 0o600)
            self.assertIn(
                "/agent-state/review-authority.json",
                (workspace / ".gitignore").read_text(encoding="utf-8").splitlines(),
            )

    def test_existing_authority_policy_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            policy_path = workspace / "agent-state" / "review-authority.json"
            policy = {
                "policyVersion": 1,
                "businessId": "interlab",
                "channels": [
                    {
                        "channel": "telegram:group",
                        "aliases": [],
                        "reviewScopes": ["routine", "high-risk"],
                        "actors": ["telegram:reviewer-a"],
                    }
                ],
            }
            policy_path.write_text(json.dumps(policy) + "\n", encoding="utf-8")

            result = migration._apply(workspace)

            self.assertFalse(result["policy_created"])
            self.assertEqual(json.loads(policy_path.read_text(encoding="utf-8")), policy)
            self.assertEqual(os.stat(policy_path).st_mode & 0o777, 0o600)

    def test_rollback_restores_original_files_before_policy_is_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            original_config = (workspace / "runtime-config.json").read_text(encoding="utf-8")
            original_gitignore = (workspace / ".gitignore").read_text(encoding="utf-8")
            migration._apply(workspace)

            result = migration._rollback(workspace)

            self.assertEqual(result["status"], "rolled-back")
            self.assertEqual(
                (workspace / "runtime-config.json").read_text(encoding="utf-8"),
                original_config,
            )
            self.assertEqual(
                (workspace / ".gitignore").read_text(encoding="utf-8"),
                original_gitignore,
            )
            self.assertFalse((workspace / "agent-state" / "review-authority.json").exists())

    def test_rollback_refuses_to_overwrite_a_configured_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            migration._apply(workspace)
            policy_path = workspace / "agent-state" / "review-authority.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["channels"] = [
                {
                    "channel": "telegram:group",
                    "aliases": [],
                    "reviewScopes": ["routine"],
                    "actors": ["telegram:reviewer-a"],
                }
            ]
            policy_path.write_text(json.dumps(policy) + "\n", encoding="utf-8")
            migration._apply(workspace)

            with self.assertRaisesRegex(migration.MigrationError, "policy changed"):
                migration._rollback(workspace)


if __name__ == "__main__":
    unittest.main()

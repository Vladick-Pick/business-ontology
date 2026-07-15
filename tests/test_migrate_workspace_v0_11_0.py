import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import migrate_workspace_v0_11_0 as migration


class WorkspaceV011MigrationTests(unittest.TestCase):
    def make_workspace(self, root: Path) -> Path:
        workspace = root / "workspace"
        (workspace / "agent-state").mkdir(parents=True)
        (workspace / "live-proofs").mkdir()
        (workspace / "source-exports" / "telegram" / "run-1").mkdir(parents=True)
        (workspace / "source-material" / "meeting-transcripts" / "meeting-1").mkdir(
            parents=True
        )
        (workspace / "PACKAGE_VERSION.lock").write_text(
            json.dumps(
                {
                    "current_version": "0.11.0",
                    "previous_version": "0.10.6",
                    "tag": "v0.11.0",
                    "commit": "a" * 40,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (workspace / "runtime-config.example.json").write_text(
            json.dumps(
                {
                    "store_path": "agent-state/operational-store.sqlite",
                    "raw_source_policy": "external-or-redacted-source-events-only",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (workspace / "INTERACTION_CONTRACT.md").write_text(
            "# Legacy interaction contract\n\nDaily at 09:00.\n",
            encoding="utf-8",
        )
        (workspace / ".gitignore").write_text("secrets/\n", encoding="utf-8")
        for name in migration.BEHAVIOR_TEMPLATES:
            (workspace / name).write_text(f"legacy {name}\n", encoding="utf-8")

        telegram = workspace / "source-exports" / "telegram" / "run-1" / "messages.jsonl"
        meeting = (
            workspace
            / "source-material"
            / "meeting-transcripts"
            / "meeting-1"
            / "transcript.md"
        )
        telegram.write_text('{"text":"private telegram body"}\n', encoding="utf-8")
        meeting.write_text("private transcript body\n", encoding="utf-8")
        (workspace / "source-instances.json").write_text(
            json.dumps(
                {
                    "source_instances": [
                        {
                            "source_instance_id": "meeting-recorder",
                            "output_ref": str(meeting.relative_to(workspace)),
                        }
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (workspace / "live-proofs" / "proofs.json").write_text(
            json.dumps({"live_proofs": []}) + "\n",
            encoding="utf-8",
        )
        return workspace

    def test_apply_copies_raw_updates_behavior_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))

            result = migration._apply(
                workspace,
                "business-analyst-interlab",
                openclaw_bin=None,
                openclaw_node_bin_dir=None,
                apply_openclaw=False,
            )

            self.assertEqual(result["status"], "migrated")
            self.assertTrue(
                (workspace / "raw" / "telegram" / "run-1" / "messages.jsonl").is_file()
            )
            self.assertTrue(
                (workspace / "raw" / "meetings" / "meeting-1" / "transcript.md").is_file()
            )
            self.assertTrue(
                (workspace / "source-exports" / "telegram" / "run-1" / "messages.jsonl").is_file()
            )
            self.assertEqual(os.stat(workspace / "raw").st_mode & 0o777, 0o700)
            self.assertEqual(
                os.stat(workspace / "raw" / "telegram" / "run-1" / "messages.jsonl").st_mode
                & 0o777,
                0o600,
            )
            config = json.loads(
                (workspace / "runtime-config.example.json").read_text(encoding="utf-8")
            )
            self.assertEqual(config["raw_source_root"], "raw")
            self.assertIn("/raw/", (workspace / ".gitignore").read_text(encoding="utf-8"))
            self.assertIn(
                "one delivered question",
                (workspace / "COMMUNICATION_POLICY.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                migration.MANAGED_BEGIN,
                (workspace / "INTERACTION_CONTRACT.md").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                os.stat(workspace / "agent-state" / "managed-scheduling.json").st_mode
                & 0o777,
                0o600,
            )
            self.assertEqual(
                os.stat(
                    workspace
                    / "agent-state"
                    / "migrations"
                    / "v0.11.0"
                    / "backup"
                    / "manifest.json"
                ).st_mode
                & 0o777,
                0o600,
            )

            replay = migration._apply(
                workspace,
                "business-analyst-interlab",
                openclaw_bin=None,
                openclaw_node_bin_dir=None,
                apply_openclaw=False,
            )
            self.assertEqual(replay["status"], "already-current")
            self.assertFalse(replay["changed"])

    def test_rollback_restores_workspace_and_preserves_reconciled_raw_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            original_policy = (workspace / "COMMUNICATION_POLICY.md").read_text(encoding="utf-8")
            migration._apply(
                workspace,
                "business-analyst-interlab",
                openclaw_bin=None,
                openclaw_node_bin_dir=None,
                apply_openclaw=False,
            )

            result = migration._rollback(
                workspace,
                "business-analyst-interlab",
                openclaw_bin=None,
                openclaw_node_bin_dir=None,
                apply_openclaw=False,
            )

            self.assertEqual(result["status"], "rolled-back")
            self.assertEqual(
                (workspace / "COMMUNICATION_POLICY.md").read_text(encoding="utf-8"),
                original_policy,
            )
            restored_config = json.loads(
                (workspace / "runtime-config.example.json").read_text(encoding="utf-8")
            )
            self.assertNotIn("raw_source_root", restored_config)
            self.assertTrue(
                (workspace / "raw" / "telegram" / "run-1" / "messages.jsonl").is_file()
            )

    def test_already_migrated_workspace_can_activate_openclaw_later(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            migration._apply(
                workspace,
                "business-analyst-interlab",
                openclaw_bin=None,
                openclaw_node_bin_dir=None,
                apply_openclaw=False,
            )
            inventory = {
                "heartbeat_existed": False,
                "heartbeat": None,
                "plugin_installed": False,
                "plugin_allow": ["telegram"],
                "plugin_entry_existed": False,
                "plugin_entry": None,
                "managed_reminder_jobs": [],
            }
            with (
                mock.patch.object(migration, "_host_inventory", return_value=inventory),
                mock.patch.object(migration, "_activate_host") as activate,
                mock.patch.object(
                    migration,
                    "_postflight",
                    return_value={"status": "refreshed", "overall_status": "ok"},
                ),
            ):
                result = migration._apply(
                    workspace,
                    "business-analyst-interlab",
                    openclaw_bin="/opt/openclaw",
                    openclaw_node_bin_dir="/opt/node/bin",
                    apply_openclaw=True,
                )

            self.assertEqual(result["status"], "migrated")
            self.assertTrue(result["openclaw_host_applied"])
            activate.assert_called_once()
            manifest = json.loads(
                (workspace / "agent-state" / "migrations" / "v0.11.0" / "backup" / "manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["host"]["plugin_allow"], ["telegram"])

    def test_patch_package_is_compatible_with_workspace_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            (workspace / "PACKAGE_VERSION.lock").write_text(
                json.dumps(
                    {
                        "current_version": "0.11.2",
                        "previous_version": "0.11.1",
                        "tag": "v0.11.2",
                        "commit": "b" * 40,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            lock = migration._validate_source(workspace, dry_run=False)

            self.assertEqual(lock["current_version"], "0.11.2")

    def test_guard_activation_always_refreshes_package_copy_before_config(self):
        calls = []

        def record_mutation(_binary, _node_bin_dir, args):
            calls.append(args)

        with (
            mock.patch.object(migration, "_openclaw_mutate", side_effect=record_mutation),
            mock.patch.object(
                migration,
                "_plugin_config",
                return_value={"allow": [], "entries": {}},
            ),
        ):
            migration._merge_owner_chat_guard(
                "/opt/openclaw",
                "/opt/node/bin",
                "business-analyst-interlab",
            )

        self.assertEqual(calls[0][0:2], ["plugins", "install"])
        self.assertIn("--force", calls[0])
        self.assertEqual(calls[1][0:3], ["config", "set", "plugins.allow"])
        self.assertEqual(
            calls[2][0:3],
            ["config", "set", "plugins.entries.business-ontology-owner-chat-guard"],
        )
        configured_entry = json.loads(calls[2][3])
        self.assertTrue(configured_entry["hooks"]["allowConversationAccess"])
        self.assertTrue(configured_entry["hooks"]["allowPromptInjection"])


if __name__ == "__main__":
    unittest.main()

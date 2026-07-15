import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import migrate_workspace_v0_11_12 as migration


class WorkspaceV01112MigrationTests(unittest.TestCase):
    def make_workspace(self, root: Path) -> Path:
        workspace = root / "workspace"
        (workspace / "agent-state").mkdir(parents=True)
        (workspace / "PACKAGE_VERSION.lock").write_text(
            json.dumps(
                {
                    "current_version": "0.11.12",
                    "previous_version": "0.11.11",
                    "tag": "v0.11.12",
                    "commit": "a" * 40,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (workspace / "runtime-config.json").write_text(
            json.dumps({"viewer_output_path": "viewer", "unrelated": {"keep": True}}) + "\n",
            encoding="utf-8",
        )
        return workspace

    def test_apply_adds_workspace_only_target_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))

            result = migration._apply(
                workspace,
                "business-analyst-interlab",
                openclaw_bin=None,
                openclaw_node_bin_dir=None,
                apply_openclaw=False,
            )
            replay = migration._apply(
                workspace,
                "business-analyst-interlab",
                openclaw_bin=None,
                openclaw_node_bin_dir=None,
                apply_openclaw=False,
            )

            config = json.loads((workspace / "runtime-config.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "migrated")
            self.assertEqual(config["viewer_publication"]["mode"], "workspace-only")
            self.assertTrue(config["unrelated"]["keep"])
            self.assertEqual(replay["status"], "already-current")
            self.assertFalse(replay["changed"])

    def test_host_activation_merges_sites_deny_without_losing_existing_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            before = {
                "agent_index": 3,
                "tools_existed": True,
                "tools": {"allow": ["read"], "deny": ["dangerous.*"]},
            }
            with (
                mock.patch.object(migration, "_agent_inventory", return_value=before),
                mock.patch.object(migration, "_activate_host") as activate,
            ):
                result = migration._apply(
                    workspace,
                    "business-analyst-interlab",
                    openclaw_bin="/opt/openclaw",
                    openclaw_node_bin_dir="/opt/node/bin",
                    apply_openclaw=True,
                )

            activate.assert_called_once_with(
                "/opt/openclaw",
                "/opt/node/bin",
                "business-analyst-interlab",
            )
            manifest = json.loads(
                (
                    workspace
                    / "agent-state"
                    / "migrations"
                    / "v0.11.12"
                    / "backup"
                    / "manifest.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["host"]["tools"]["allow"], ["read"])
            self.assertEqual(result["sites_tools_denied"], list(migration.SITES_DENY))

    def test_activate_host_sets_exact_agent_tools_path_and_merges_deny(self):
        inventory_before = {
            "agent_index": 2,
            "tools_existed": True,
            "tools": {"allow": ["read"], "deny": ["dangerous.*"]},
        }
        inventory_after = {
            "agent_index": 2,
            "tools_existed": True,
            "tools": {
                "allow": ["read"],
                "deny": ["dangerous.*", *migration.SITES_DENY],
            },
        }
        calls = []
        with (
            mock.patch.object(
                migration,
                "_agent_inventory",
                side_effect=[inventory_before, inventory_before, inventory_after],
            ),
            mock.patch.object(
                migration,
                "_openclaw_mutate",
                side_effect=lambda _binary, _node, args: calls.append(args),
            ),
        ):
            migration._activate_host("openclaw", None, "business-analyst-interlab")

        self.assertEqual(calls[0][0:3], ["config", "set", "agents.list[2].tools"])
        written = json.loads(calls[0][3])
        self.assertEqual(written["allow"], ["read"])
        self.assertEqual(
            written["deny"],
            ["dangerous.*", "sites.*", "codex_apps.sites.*"],
        )

    def test_rollback_restores_runtime_config_and_original_host_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            original = (workspace / "runtime-config.json").read_text(encoding="utf-8")
            inventory = {
                "agent_index": 1,
                "tools_existed": False,
                "tools": None,
            }
            with (
                mock.patch.object(migration, "_agent_inventory", return_value=inventory),
                mock.patch.object(migration, "_activate_host"),
            ):
                migration._apply(
                    workspace,
                    "business-analyst-interlab",
                    openclaw_bin="openclaw",
                    openclaw_node_bin_dir=None,
                    apply_openclaw=True,
                )

            with mock.patch.object(migration, "_restore_host") as restore:
                result = migration._rollback(
                    workspace,
                    "business-analyst-interlab",
                    openclaw_bin="openclaw",
                    openclaw_node_bin_dir=None,
                    apply_openclaw=True,
                )

            self.assertEqual((workspace / "runtime-config.json").read_text(encoding="utf-8"), original)
            restore.assert_called_once()
            self.assertEqual(result["status"], "rolled-back")


if __name__ == "__main__":
    unittest.main()

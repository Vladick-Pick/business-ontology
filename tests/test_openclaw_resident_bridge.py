import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts.install_openclaw_resident_bridge import (
    BridgeInstallError,
    install_bridge,
    rollback_bridge,
)


class OpenClawResidentBridgeTests(unittest.TestCase):
    agent_id = "business-analyst-interlab"

    def make_workspace(self, root: Path) -> Path:
        workspace = root / "workspace"
        (workspace / "agent-state").mkdir(parents=True)
        (workspace / "AGENTS.md").write_text(
            "# Custom Interlab agent\n\nKeep this contour-specific policy.\n",
            encoding="utf-8",
        )
        declaration = f"business-ontology:{self.agent_id}:owner-reminder"
        (workspace / "agent-state" / "managed-scheduling.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "managed_by": "business-ontology",
                    "agent_id": self.agent_id,
                    "heartbeat": {
                        "every": "2h",
                        "target": "none",
                        "directPolicy": "block",
                        "isolatedSession": True,
                        "lightContext": True,
                    },
                    "owner_reminder": {
                        "configured": False,
                        "requires_owner_confirmation": True,
                        "job_name": declaration,
                        "declaration_key": declaration,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return workspace

    def test_install_preserves_custom_agents_and_is_idempotent_without_cron_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            original_agents = (workspace / "AGENTS.md").read_text(encoding="utf-8")

            result = install_bridge(workspace, self.agent_id)

            self.assertEqual(result["status"], "installed")
            self.assertFalse(result["cron_mutated"])
            agents = (workspace / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn(original_agents.strip(), agents)
            self.assertIn("resident-self-service-v1", agents)
            self.assertIn("Do not hand this work", agents)
            bridge = (
                workspace / "skills" / "business-ontology-resident" / "SKILL.md"
            ).read_text(encoding="utf-8")
            self.assertIn("name: business-ontology-resident", bridge)
            self.assertIn(
                f"$HOME/.openclaw/agents/{self.agent_id}/agent/package/current",
                bridge,
            )
            scheduling = json.loads(
                (workspace / "agent-state" / "managed-scheduling.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                scheduling["owner_reminder"]["setup_status"], "needs-owner-question"
            )
            self.assertEqual(
                os.stat(workspace / "agent-state" / "managed-scheduling.json").st_mode
                & 0o777,
                0o600,
            )

            replay = install_bridge(workspace, self.agent_id)
            self.assertEqual(replay["status"], "already-current")
            self.assertFalse(replay["changed"])
            self.assertFalse(replay["cron_mutated"])

    def test_rollback_restores_original_files_and_removes_new_bridge(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            original_agents = (workspace / "AGENTS.md").read_bytes()
            original_scheduling = (
                workspace / "agent-state" / "managed-scheduling.json"
            ).read_bytes()
            install_bridge(workspace, self.agent_id)

            result = rollback_bridge(workspace, self.agent_id)

            self.assertEqual(result["status"], "rolled-back")
            self.assertFalse(result["cron_mutated"])
            self.assertEqual((workspace / "AGENTS.md").read_bytes(), original_agents)
            self.assertEqual(
                (workspace / "agent-state" / "managed-scheduling.json").read_bytes(),
                original_scheduling,
            )
            self.assertFalse(
                (workspace / "skills" / "business-ontology-resident" / "SKILL.md").exists()
            )

    def test_non_package_skill_collision_fails_without_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            bridge = workspace / "skills" / "business-ontology-resident" / "SKILL.md"
            bridge.parent.mkdir(parents=True)
            bridge.write_text("---\nname: someone-elses-skill\n---\n", encoding="utf-8")
            original_agents = (workspace / "AGENTS.md").read_bytes()

            with self.assertRaises(BridgeInstallError):
                install_bridge(workspace, self.agent_id)

            self.assertEqual((workspace / "AGENTS.md").read_bytes(), original_agents)
            self.assertEqual(
                bridge.read_text(encoding="utf-8"),
                "---\nname: someone-elses-skill\n---\n",
            )


if __name__ == "__main__":
    unittest.main()

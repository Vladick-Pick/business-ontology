import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from runtime.operational_store import OperationalStore
from scripts.owner_reminder import NO_REPLY, render_reminder
from scripts.system_heartbeat import EXPECTED_HEARTBEAT, _managed_cron_matches, build_snapshot


class ResidentSchedulingTests(unittest.TestCase):
    agent_id = "business-analyst-interlab"

    def make_workspace(self, root: Path, *, reminder_configured: bool = True) -> Path:
        workspace = root / "workspace"
        (workspace / "agent-state").mkdir(parents=True)
        (workspace / "runtime-config.example.json").write_text(
            json.dumps({"store_path": "agent-state/operational-store.sqlite"}) + "\n",
            encoding="utf-8",
        )
        (workspace / "source-instances.json").write_text(
            json.dumps({"source_instances": []}) + "\n",
            encoding="utf-8",
        )
        (workspace / "PACKAGE_VERSION.lock").write_text(
            json.dumps(
                {
                    "current_version": "0.11.0",
                    "tag": "v0.11.0",
                    "commit": "a" * 40,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (workspace / "workspace-state.json").write_text(
            json.dumps(
                {
                    "agent_identity": {
                        "package_name": "business-ontology",
                        "package_version": "0.11.0",
                    },
                    "workspace": {"workspace_id": "workspace-interlab"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        declaration = f"business-ontology:{self.agent_id}:owner-reminder"
        reminder = {
            "configured": reminder_configured,
            "requires_owner_confirmation": not reminder_configured,
            "job_name": declaration,
            "declaration_key": declaration,
            "cadence": "daily" if reminder_configured else None,
            "cron": "0 9 * * *" if reminder_configured else None,
            "timezone": "Europe/Moscow" if reminder_configured else None,
            "channel": "telegram" if reminder_configured else None,
            "delivery_target": "owner-chat" if reminder_configured else None,
            "quiet_window": "22:00-09:00" if reminder_configured else None,
            "account_id": None,
            "language": "ru" if reminder_configured else "pending-owner-selection",
            "confirmation_ref": "owner-message-1" if reminder_configured else None,
            "confirmed_at": "2026-07-15T06:00:00Z" if reminder_configured else None,
        }
        (workspace / "agent-state" / "managed-scheduling.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "managed_by": "business-ontology",
                    "agent_id": self.agent_id,
                    "heartbeat": EXPECTED_HEARTBEAT,
                    "owner_reminder": reminder,
                    "owner_chat_guard": {
                        "plugin_id": "business-ontology-owner-chat-guard",
                        "enabled": True,
                        "allow_conversation_access": True,
                        "agent_id": self.agent_id,
                        "required_hooks": [
                            "before_agent_run",
                            "before_agent_finalize",
                            "message_sending",
                        ],
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (workspace / "agent-state" / "system-health.json").write_text(
            json.dumps({"overall_status": "ok"}) + "\n",
            encoding="utf-8",
        )
        store = OperationalStore.connect(workspace / "agent-state" / "operational-store.sqlite")
        store.initialize()
        store.close()
        return workspace

    def test_reminder_returns_one_plain_current_question_and_obeys_quiet_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            with OperationalStore.connect(
                workspace / "agent-state" / "operational-store.sqlite"
            ) as store:
                store.record_human_request(
                    {
                        "requestId": "hreq-private-id",
                        "kind": "setup",
                        "owner": "owner",
                        "channel": "telegram",
                        "messageRef": "message-1",
                        "prompt": "Во сколько присылать ежедневное напоминание?",
                        "recommendedAnswer": "В 09:00 по Москве.",
                        "askedAt": "2026-07-15T06:00:00Z",
                    }
                )

            message = render_reminder(
                workspace,
                self.agent_id,
                datetime(2026, 7, 15, 7, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(message.count("?"), 1)
            self.assertIn("Рекомендация:", message)
            self.assertIn("Последствие:", message)
            self.assertNotIn("hreq-private-id", message)
            self.assertEqual(
                render_reminder(
                    workspace,
                    self.agent_id,
                    datetime(2026, 7, 15, 21, 0, tzinfo=timezone.utc),
                ),
                NO_REPLY,
            )

    def test_reminder_is_silent_without_confirmed_schedule_or_actionable_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unconfigured = self.make_workspace(root / "unconfigured", reminder_configured=False)
            configured = self.make_workspace(root / "configured", reminder_configured=True)

            now = datetime(2026, 7, 15, 7, 0, tzinfo=timezone.utc)
            self.assertEqual(render_reminder(unconfigured, self.agent_id, now), NO_REPLY)
            self.assertEqual(render_reminder(configured, self.agent_id, now), NO_REPLY)

    def test_two_heartbeat_snapshots_never_allow_external_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp), reminder_configured=False)

            first = build_snapshot(
                workspace,
                self.agent_id,
                checked_at="2026-07-15T08:00:00Z",
                openclaw_bin=None,
                openclaw_node_bin_dir=None,
                skip_openclaw_probe=True,
            )
            second = build_snapshot(
                workspace,
                self.agent_id,
                checked_at="2026-07-15T10:00:00Z",
                openclaw_bin=None,
                openclaw_node_bin_dir=None,
                skip_openclaw_probe=True,
            )

            self.assertFalse(first["external_delivery_allowed"])
            self.assertFalse(second["external_delivery_allowed"])
            self.assertEqual(first["heartbeat_delivery"], {"target": "none", "direct_policy": "block"})
            self.assertNotEqual(first["checked_at"], second["checked_at"])

    def test_managed_cron_match_checks_agent_schedule_delivery_and_declaration(self):
        declaration = f"business-ontology:{self.agent_id}:owner-reminder"
        reminder = {
            "declaration_key": declaration,
            "cron": "0 9 * * *",
            "timezone": "Europe/Moscow",
            "channel": "telegram",
            "delivery_target": "owner-chat",
        }
        job = {
            "name": declaration,
            "declarationKey": declaration,
            "enabled": True,
            "agentId": self.agent_id,
            "schedule": {"kind": "cron", "expr": "0 9 * * *", "tz": "Europe/Moscow"},
            "sessionTarget": "isolated",
            "delivery": {"mode": "announce", "channel": "telegram", "to": "owner-chat"},
        }

        self.assertEqual(_managed_cron_matches([job], reminder, self.agent_id), (True, "ok"))
        job["agentId"] = "another-agent"
        healthy, reason = _managed_cron_matches([job], reminder, self.agent_id)
        self.assertFalse(healthy)
        self.assertIn("agent", reason)


if __name__ == "__main__":
    unittest.main()

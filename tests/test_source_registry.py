import json
from pathlib import Path
import tempfile
import unittest

from scripts import source_registry


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class SourceRegistryTests(unittest.TestCase):
    def test_upserts_source_instance_without_raw_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            record = source_registry.upsert_source_instance(
                workspace,
                {
                    "source_instance_id": "tg-main-history",
                    "owner_agent": "business-analyst",
                    "kind": "telegram-mtproto-history",
                    "runtime_adapter": "scripts/tg_run_daily_ingest.py",
                    "config_ref": "config/tg.toml",
                    "cursor_ref": "source-cursors/tg.json",
                    "output_ref": "source-events/tg-main-history",
                    "scheduler_ref": "manual",
                    "status": "configured",
                    "last_live_proof_id": "",
                },
            )

            self.assertEqual(record["source_instance_id"], "tg-main-history")
            registry = load_json(workspace / "source-instances.json")
            self.assertEqual(len(registry["source_instances"]), 1)
            blob = json.dumps(registry)
            self.assertNotIn("raw", blob.lower())
            self.assertNotIn("message text", blob.lower())

    def test_live_proof_updates_instance_status_and_keeps_refs_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source_registry.upsert_source_instance(
                workspace,
                {
                    "source_instance_id": "meeting-skribby",
                    "owner_agent": "business-analyst",
                    "kind": "meeting-recorder",
                    "runtime_adapter": "scripts/run_meeting_recording_live_proof.py",
                    "config_ref": "env:MEETING_RECORDING_SERVICE_URL",
                    "cursor_ref": "",
                    "output_ref": "live-proofs/meeting-recording",
                    "scheduler_ref": "manual",
                    "status": "configured",
                    "last_live_proof_id": "",
                },
            )

            proof = source_registry.record_live_proof(
                workspace,
                {
                    "live_proof_id": "proof-meeting-001",
                    "source_instance_id": "meeting-skribby",
                    "capability": "meeting-recording-transcript",
                    "mode": "fixture",
                    "input_ref": "packet:mtgpk-001",
                    "output_artifacts": ["live-proofs/meeting-recording/proof.md"],
                    "evidence_hash": "sha256:abc",
                    "status": "passed",
                },
            )

            self.assertEqual(proof["status"], "passed")
            registry = load_json(workspace / "source-instances.json")
            instance = registry["source_instances"][0]
            self.assertEqual(instance["status"], "live-proven")
            self.assertEqual(instance["last_live_proof_id"], "proof-meeting-001")
            ledger = load_json(workspace / "live-proofs" / "proofs.json")
            self.assertEqual(ledger["live_proofs"][0]["output_artifacts"], ["live-proofs/meeting-recording/proof.md"])

    def test_ready_instances_are_scoped_to_owner_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            for owner in ["main", "business-analyst"]:
                source_registry.upsert_source_instance(
                    workspace,
                    {
                        "source_instance_id": f"tg-{owner}",
                        "owner_agent": owner,
                        "kind": "telegram-mtproto-history",
                        "runtime_adapter": "scripts/tg_run_daily_ingest.py",
                        "config_ref": "config/tg.toml",
                        "cursor_ref": "source-cursors/tg.json",
                        "output_ref": "source-events/tg",
                        "scheduler_ref": "cron",
                        "status": "live-proven",
                        "last_live_proof_id": "proof",
                    },
                )

            ready = source_registry.ready_source_instances(workspace, owner_agent="business-analyst")

            self.assertEqual([item["source_instance_id"] for item in ready], ["tg-business-analyst"])

    def test_live_proof_requires_existing_source_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            with self.assertRaisesRegex(ValueError, "unknown source instance"):
                source_registry.record_live_proof(
                    workspace,
                    {
                        "live_proof_id": "proof-orphan",
                        "source_instance_id": "missing-source",
                        "capability": "telegram-history-mtproto-daily-packet",
                        "mode": "fixture",
                        "input_ref": "mtproto-run:run-1",
                        "output_artifacts": ["packet.json"],
                        "evidence_hash": "sha256:" + "a" * 64,
                        "status": "passed",
                    },
                )
            self.assertFalse((workspace / "live-proofs" / "proofs.json").exists())

    def test_configured_upsert_preserves_existing_live_proof_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source_registry.upsert_source_instance(
                workspace,
                {
                    "source_instance_id": "tg-main-history",
                    "owner_agent": "business-analyst",
                    "kind": "telegram-mtproto-history",
                    "runtime_adapter": "scripts/tg_run_daily_ingest.py",
                    "config_ref": "config/tg.toml",
                    "cursor_ref": "source-cursors/tg.json",
                    "output_ref": "source-events/tg",
                    "scheduler_ref": "cron",
                    "status": "live-proven",
                    "last_live_proof_id": "proof-old",
                },
            )

            source_registry.upsert_source_instance(
                workspace,
                {
                    "source_instance_id": "tg-main-history",
                    "owner_agent": "business-analyst",
                    "kind": "telegram-mtproto-history",
                    "runtime_adapter": "scripts/tg_run_daily_ingest.py",
                    "config_ref": "config/tg.toml",
                    "cursor_ref": "source-cursors/tg.json",
                    "output_ref": "source-events/tg",
                    "scheduler_ref": "cron",
                    "status": "configured",
                    "last_live_proof_id": "",
                },
            )

            [instance] = load_json(workspace / "source-instances.json")["source_instances"]
            self.assertEqual(instance["status"], "live-proven")
            self.assertEqual(instance["last_live_proof_id"], "proof-old")


if __name__ == "__main__":
    unittest.main()

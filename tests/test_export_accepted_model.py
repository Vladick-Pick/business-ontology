import json
from pathlib import Path
import tempfile
import unittest

from runtime.operational_store import OperationalStore
from scripts.export_accepted_model import build_accepted_snapshot, export_snapshot


class AcceptedModelExportTests(unittest.TestCase):
    def make_applied_store(self, root: Path) -> OperationalStore:
        store = OperationalStore.connect(root / "operational.sqlite")
        store.initialize()
        package = {
            "packageId": "mcpkg-export-accepted-001",
            "moduleId": "interlab",
            "modelPackId": "mp-interlab",
            "modelPackVersion": "1",
            "ontologyRevision": "store:before",
            "compiler": {"name": "test", "version": "1", "mode": "synthetic-fixture"},
            "sourceEventIds": ["srcevt-export-001"],
            "generatedAt": "2026-07-16T09:00:00Z",
            "summary": "Private-safe accepted model test.",
            "changes": [
                {
                    "changeId": "chg-export-offer",
                    "kind": "new-object",
                    "confidence": "medium",
                    "risk": "medium",
                    "claimKind": "owner-claim",
                    "evidenceGrade": "claim",
                    "sourceRisk": ["no-known-risk"],
                    "affectedIds": ["artifact-offer"],
                    "evidence": [
                        {
                            "sourceEventId": "srcevt-export-001",
                            "locator": "telegram:private:42",
                            "excerpt": "PRIVATE RAW EVIDENCE MUST NOT BE EXPORTED",
                        }
                    ],
                    "proposedAction": "prepare-staged-proposal",
                    "candidateCard": {
                        "id": "artifact-offer",
                        "type": "artifact",
                        "status": "candidate",
                        "source": "src-owner-confirmation",
                        "owner": "role-model-owner",
                        "summary": "Offer used by the sales contour.",
                        "links": {},
                        "attrs": {
                            "kind": "intermediate",
                            "raw_payload": "PRIVATE ATTRIBUTE MUST NOT BE EXPORTED",
                            "sourceMessageRef": "telegram:-10042:114",
                        },
                    },
                    "acceptedItem": {
                        "item": {
                            "id": "artifact-offer",
                            "kind": "artifact",
                            "status": "accepted",
                            "name": "Offer",
                            "source_id": "src-owner-confirmation",
                            "evidence_id": "evd-export-001",
                            "decision_id": "hdec-export-accepted-001",
                            "valid_from": "2026-07-16T09:05:00Z",
                            "valid_to": None,
                            "supersedes": [],
                            "superseded_by": [],
                            "last_verified_at": "2026-07-16T09:05:00Z",
                            "confidence": "high",
                        }
                    },
                }
            ],
            "review": {
                "overallAction": "human-review",
                "owner": "role-model-owner",
                "reason": "Model change requires review.",
            },
            "safety": {
                "noPii": True,
                "noSecrets": True,
                "noRawPayload": True,
                "noAcceptedMutation": True,
            },
        }
        store.record_model_change_package(package)
        store.record_human_decision(
            "hdec-export-accepted-001",
            {
                "packageId": package["packageId"],
                "actor": "telegram:reviewer",
                "decision": "approved",
                "reason": "Approved exact revision.",
                "decidedAt": "2026-07-16T09:05:00Z",
            },
        )
        store.apply_approved_model_change(package)
        return store

    def test_snapshot_is_current_deterministic_and_excludes_raw_source_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.make_applied_store(root) as store:
                first = build_accepted_snapshot(store)
                second = build_accepted_snapshot(store)

            self.assertEqual(first, second)
            self.assertEqual(first["module"], "interlab")
            self.assertEqual(len(first["cards"]), 1)
            self.assertEqual(first["cards"][0]["status"], "accepted")
            serialized = json.dumps(first, ensure_ascii=False)
            self.assertNotIn("PRIVATE RAW EVIDENCE", serialized)
            self.assertNotIn("telegram:private:42", serialized)
            self.assertNotIn("PRIVATE ATTRIBUTE", serialized)
            self.assertNotIn("raw_payload", serialized)
            self.assertNotIn("sourceMessageRef", serialized)
            self.assertNotIn("telegram:-10042:114", serialized)

    def test_export_writes_agent_viewer_and_git_portability_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_root = root / "model"
            with self.make_applied_store(root) as store:
                snapshot = export_snapshot(store, model_root=model_root)

            context = json.loads(
                (model_root / "ontology" / "accepted-context.json").read_text(encoding="utf-8")
            )
            self.assertEqual(context["revision"], snapshot["revision"])
            self.assertIn("artifact-offer", (model_root / "ACCEPTED_MODEL.md").read_text())
            self.assertIn("src-owner-confirmation", (model_root / "02-source-map.md").read_text())
            self.assertIn("mcpkg-export-accepted-001", (model_root / "09-changelog.md").read_text())


if __name__ == "__main__":
    unittest.main()

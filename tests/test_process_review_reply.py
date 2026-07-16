import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from runtime.operational_store import OperationalStore
from scripts.process_review_reply import process_review_reply, reconcile_package


class ProcessReviewReplyTests(unittest.TestCase):
    channel = "telegram:-10042"
    actor = "telegram:101"
    request_id = "hreq-review-atomic-001"
    package_id = "mcpkg-review-atomic-001"
    decision_id = "hdec-review-atomic-001"

    def make_workspace(self, root: Path) -> tuple[Path, dict[str, object]]:
        workspace = root / "workspace"
        (workspace / "agent-state").mkdir(parents=True)
        (workspace / "model").mkdir()
        (workspace / "runtime-config.example.json").write_text(
            json.dumps(
                {
                    "module_id": "interlab",
                    "store_path": "agent-state/operational-store.sqlite",
                    "accepted_context_path": "ontology/accepted-context.json",
                    "review_authority_policy_path": "agent-state/review-authority.json",
                    "viewer_output_path": "viewer",
                    "viewer_publication": {
                        "mode": "static-url",
                        "public_url": "https://model.example.test/",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (workspace / "agent-state" / "review-authority.json").write_text(
            json.dumps(
                {
                    "policyVersion": 1,
                    "businessId": "interlab",
                    "channels": [
                        {
                            "channel": self.channel,
                            "aliases": ["telegram:dm-owner"],
                            "reviewScopes": ["routine", "high-risk"],
                            "actors": [self.actor, "telegram:202"],
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        package = {
            "packageId": self.package_id,
            "moduleId": "interlab",
            "modelPackId": "mp-interlab",
            "modelPackVersion": "1",
            "ontologyRevision": "bootstrap-empty",
            "compiler": {"name": "test", "version": "1", "mode": "fixture"},
            "sourceEventIds": ["srcevt-review-001"],
            "generatedAt": "2026-07-16T06:00:00Z",
            "summary": "One reviewed business definition.",
            "changes": [
                {
                    "changeId": "chg-review-artifact",
                    "kind": "new-object",
                    "confidence": "high",
                    "risk": "medium",
                    "claimKind": "owner-claim",
                    "evidenceGrade": "claim",
                    "sourceRisk": ["no-known-risk"],
                    "affectedIds": ["artifact-current-model"],
                    "evidence": [
                        {
                            "sourceEventId": "srcevt-review-001",
                            "locator": "telegram:private:42",
                            "excerpt": "PRIVATE RAW REPLY MUST NOT BE EXPORTED",
                        }
                    ],
                    "proposedAction": "prepare-staged-proposal",
                    "candidateCard": {
                        "id": "artifact-current-model",
                        "type": "artifact",
                        "status": "candidate",
                        "source": "src-owner-review",
                        "owner": "role-model-owner",
                        "summary": "Current model publication.",
                        "attrs": {"kind": "output"},
                        "links": {},
                    },
                    "acceptedItem": {
                        "item": {
                            "id": "artifact-current-model",
                            "kind": "artifact",
                            "status": "accepted",
                            "name": "Current model publication",
                            "source_id": "src-owner-review",
                            "evidence_id": "evd-review-001",
                            "decision_id": self.decision_id,
                            "valid_from": "2026-07-16T06:05:00Z",
                            "valid_to": None,
                            "supersedes": [],
                            "superseded_by": [],
                            "last_verified_at": "2026-07-16T06:05:00Z",
                            "confidence": "high",
                        }
                    },
                }
            ],
            "review": {
                "overallAction": "human-review",
                "owner": "role-model-owner",
                "reason": "The accepted model needs human approval.",
            },
            "safety": {
                "noPii": True,
                "noSecrets": True,
                "noRawPayload": True,
                "noAcceptedMutation": True,
            },
        }
        store_path = workspace / "agent-state" / "operational-store.sqlite"
        with OperationalStore.connect(store_path) as store:
            store.initialize()
            store.record_model_change_package(package)
            store.record_human_request(
                {
                    "requestId": self.request_id,
                    "kind": "review",
                    "status": "open",
                    "owner": "role-model-owner",
                    "channel": self.channel,
                    "messageRef": f"{self.channel}:114",
                    "prompt": "Применить эту ревизию к актуальной модели?",
                    "recommendedAnswer": "Применить эту ревизию.",
                    "blocks": ["accepted-model"],
                    "sourceRef": self.package_id,
                    "packageId": self.package_id,
                    "askedAt": "2026-07-16T06:01:00Z",
                }
            )
        return workspace, package

    @staticmethod
    def published(*_args, **_kwargs):
        return True, {"status": "published"}

    def test_exact_authorized_yes_applies_exports_closes_and_never_persists_raw_reply(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, _ = self.make_workspace(Path(tmp))
            private_reply = "Да"
            with patch("scripts.process_review_reply._publish", side_effect=self.published):
                result = process_review_reply(
                    workspace=workspace,
                    package_root=Path(tmp),
                    channel=self.channel,
                    actor=self.actor,
                    reply_to_message_ref=f"{self.channel}:114",
                    inbound_message_ref=f"{self.channel}:115",
                    reply_text=private_reply,
                    received_at="2026-07-16T06:05:00Z",
                )

            self.assertEqual(result["status"], "applied-and-published")
            self.assertEqual(result["cardCount"], 1)
            self.assertIn("https://model.example.test/", result["rendering"])
            with OperationalStore.connect(
                workspace / "agent-state" / "operational-store.sqlite"
            ) as store:
                self.assertEqual(store.table_count("accepted_items"), 1)
                self.assertEqual(store.get_human_request(self.request_id)["status"], "answered")
                self.assertEqual(
                    store.get_human_request(self.request_id)["decisionId"], self.decision_id
                )
            serialized_workspace = "\n".join(
                path.read_text(encoding="utf-8", errors="ignore")
                for path in workspace.rglob("*")
                if path.is_file() and path.suffix != ".sqlite"
            )
            self.assertNotIn("PRIVATE RAW REPLY", serialized_workspace)
            self.assertEqual(
                json.loads(
                    (workspace / "runtime-config.example.json").read_text(encoding="utf-8")
                )["accepted_context_path"],
                "model/ontology/accepted-context.json",
            )

    def test_unauthorized_exact_reply_is_handled_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, _ = self.make_workspace(Path(tmp))
            result = process_review_reply(
                workspace=workspace,
                package_root=Path(tmp),
                channel=self.channel,
                actor="telegram:unauthorized",
                reply_to_message_ref=f"{self.channel}:114",
                inbound_message_ref=f"{self.channel}:115",
                reply_text="Да",
            )

            self.assertEqual(result["status"], "authorization-required")
            with OperationalStore.connect(
                workspace / "agent-state" / "operational-store.sqlite"
            ) as store:
                self.assertEqual(store.table_count("accepted_items"), 0)
                self.assertEqual(store.table_count("human_decisions"), 0)
                self.assertEqual(store.get_human_request(self.request_id)["status"], "open")

    def test_export_failure_keeps_applied_truth_and_does_not_request_reapproval(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, _ = self.make_workspace(Path(tmp))
            with patch(
                "scripts.process_review_reply.export_snapshot",
                side_effect=OSError("derived export unavailable"),
            ):
                result = process_review_reply(
                    workspace=workspace,
                    package_root=Path(tmp),
                    channel=self.channel,
                    actor=self.actor,
                    reply_to_message_ref=f"{self.channel}:114",
                    inbound_message_ref=f"{self.channel}:115",
                    reply_text="Применить",
                    received_at="2026-07-16T06:05:00Z",
                )

            self.assertEqual(result["status"], "applied-publication-pending")
            self.assertEqual(result["publication"]["reportStatus"], "accepted-export-pending")
            self.assertIn("Повторное решение не нужно", result["rendering"])
            with OperationalStore.connect(
                workspace / "agent-state" / "operational-store.sqlite"
            ) as store:
                self.assertEqual(store.table_count("accepted_items"), 1)
                self.assertEqual(store._package_status(self.package_id), "applied")
                self.assertEqual(store.get_human_request(self.request_id)["status"], "answered")

    def test_reply_with_edits_falls_through_to_agent_without_partial_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, _ = self.make_workspace(Path(tmp))
            result = process_review_reply(
                workspace=workspace,
                package_root=Path(tmp),
                channel=self.channel,
                actor=self.actor,
                reply_to_message_ref=f"{self.channel}:114",
                inbound_message_ref=f"{self.channel}:115",
                reply_text="Да, но измени владельца",
            )

            self.assertFalse(result["handled"])
            self.assertEqual(result["status"], "review-content-requires-agent")
            with OperationalStore.connect(
                workspace / "agent-state" / "operational-store.sqlite"
            ) as store:
                self.assertEqual(store.table_count("accepted_items"), 0)
                self.assertEqual(store.table_count("human_decisions"), 0)

    def test_reconcile_applies_existing_approval_without_reapproval(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, package = self.make_workspace(Path(tmp))
            with OperationalStore.connect(
                workspace / "agent-state" / "operational-store.sqlite"
            ) as store:
                store.record_human_decision(
                    self.decision_id,
                    {
                        "packageId": self.package_id,
                        "actor": self.actor,
                        "decision": "approved",
                        "reason": "Approved exact revision.",
                        "decidedAt": "2026-07-16T06:05:00Z",
                    },
                )
            with patch("scripts.process_review_reply._publish", side_effect=self.published):
                result = reconcile_package(
                    workspace=workspace,
                    package_root=Path(tmp),
                    package_id=self.package_id,
                )

            self.assertEqual(result["status"], "applied-and-published")
            self.assertEqual(result["cardCount"], 1)
            with OperationalStore.connect(
                workspace / "agent-state" / "operational-store.sqlite"
            ) as store:
                self.assertEqual(store.table_count("accepted_items"), 1)
                self.assertEqual(store.get_human_request(self.request_id)["status"], "answered")
                self.assertEqual(store.get_model_change_package(package["packageId"]), package)


if __name__ == "__main__":
    unittest.main()

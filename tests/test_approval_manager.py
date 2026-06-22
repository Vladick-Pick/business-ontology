import copy
import json
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PACK_PATH = REPO_ROOT / "examples" / "model-packs" / "acquisition.model-pack.json"
PACKAGE_DIR = REPO_ROOT / "evals" / "fixtures" / "model-change-packages"
SCHEMA_PATH = REPO_ROOT / "schemas" / "review-package.schema.json"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class ApprovalManagerTests(unittest.TestCase):
    def setUp(self):
        from runtime.approval_manager import (
            ApprovalManagerRefusal,
            prepare_review_package,
            record_review_decision,
        )

        self.ApprovalManagerRefusal = ApprovalManagerRefusal
        self.prepare_review_package = prepare_review_package
        self.record_review_decision = record_review_decision
        self.model_pack = load_json(MODEL_PACK_PATH)

    def package(self, filename):
        return load_json(PACKAGE_DIR / filename)

    def test_schema_is_strict_object_contract(self):
        schema = load_json(SCHEMA_PATH)

        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema.get("additionalProperties", True))
        self.assertEqual(
            set(schema["required"]),
            {
                "reviewId",
                "packageId",
                "moduleId",
                "status",
                "owner",
                "risk",
                "summary",
                "changes",
                "requiredActions",
                "decisions",
                "audit",
                "safety",
            },
        )
        self.assertEqual(
            set(schema["properties"]["status"]["enum"]),
            {
                "pending",
                "approved",
                "rejected",
                "needs-info",
                "superseded",
                "staged-proposal-ready",
            },
        )
        self.assertEqual(
            schema["allOf"][0]["then"]["properties"]["requiredActions"]["items"]["not"]
            ["properties"]["action"]["const"],
            "prepare-staged-proposal",
        )
        self.assertEqual(
            schema["allOf"][0]["if"]["properties"]["status"]["not"]["const"],
            "staged-proposal-ready",
        )
        self.assertEqual(
            schema["allOf"][1]["then"]["properties"]["requiredActions"]["contains"]
            ["properties"]["action"]["const"],
            "prepare-staged-proposal",
        )
        self.assertEqual(
            schema["allOf"][1]["if"]["properties"]["status"]["const"],
            "staged-proposal-ready",
        )
        self.assertEqual(
            schema["properties"]["changes"]["items"]["properties"]["evidence"]["minItems"],
            1,
        )

    def test_low_risk_package_becomes_pending_review_with_owner(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["changes"][0]["risk"] = "low"
        package["review"]["owner"] = "role:acquisition-owner"

        review = self.prepare_review_package(package, self.model_pack)

        self.assertEqual(review["status"], "pending")
        self.assertEqual(review["owner"], "role:acquisition-owner")
        self.assertEqual(review["risk"], "low")
        self.assertIn("human-review", {action["action"] for action in review["requiredActions"]})
        self.assertNotIn("prepare-staged-proposal", {action["action"] for action in review["requiredActions"]})
        self.assertIs(review["safety"]["noAcceptedMutation"], True)

    def test_high_risk_field_routes_to_explicit_owner(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["review"]["owner"] = "role:ontology-reviewer"
        package["changes"][0]["risk"] = "high"
        package["changes"][0]["candidateCard"]["type"] = "decision"
        package["changes"][0]["candidateCard"]["attrs"] = {
            "measurement-convention": "Overrides are excluded from conversion rate.",
        }

        review = self.prepare_review_package(package, self.model_pack)

        self.assertEqual(review["status"], "pending")
        self.assertEqual(review["owner"], "role:analytics-owner")
        self.assertEqual(review["risk"], "high")
        self.assertIn(
            "candidate touches high-risk field measurement-convention",
            review["changes"][0]["highRiskReasons"],
        )

    def test_unknown_owner_results_in_needs_info(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["review"] = {
            "overallAction": "needs-owner",
            "owner": "unknown",
            "reason": "Compiler could not route this package to an owner.",
        }

        review = self.prepare_review_package(package, self.model_pack)

        self.assertEqual(review["status"], "needs-info")
        self.assertEqual(review["owner"], "unknown")
        self.assertIn("needs-owner", {action["action"] for action in review["requiredActions"]})

    def test_missing_evidence_is_refused_before_review_package(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["changes"][0]["evidence"] = []

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.prepare_review_package(package, self.model_pack)

    def test_unsafe_package_safety_flag_is_refused_before_review_package(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["safety"]["noPii"] = False

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.prepare_review_package(package, self.model_pack)

    def test_sensitive_package_summary_is_refused_before_review_package(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["summary"] = "Contact alice@example.com to approve this package."

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.prepare_review_package(package, self.model_pack)

    def test_sensitive_review_reason_is_refused_before_review_package(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["review"]["reason"] = "Contact alice@example.com to approve this package."

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.prepare_review_package(package, self.model_pack)

    def test_sensitive_evidence_excerpt_is_refused_before_review_package(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["changes"][0]["evidence"][0]["excerpt"] = "api_key=abcdef should not appear."

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.prepare_review_package(package, self.model_pack)

    def test_malformed_evidence_item_is_refused_before_review_package(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["changes"][0]["evidence"] = [{}]

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.prepare_review_package(package, self.model_pack)

    def test_mixed_non_object_evidence_is_refused_before_review_package(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["changes"][0]["evidence"].append("bad-item")

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.prepare_review_package(package, self.model_pack)

    def test_evidence_with_extra_fields_is_refused_before_review_package(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["changes"][0]["evidence"][0]["rawPayload"] = "not allowed"

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.prepare_review_package(package, self.model_pack)

    def test_non_object_change_is_refused_before_review_package(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["changes"].append("bad-change")

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.prepare_review_package(package, self.model_pack)

    def test_invalid_change_action_is_refused_before_review_package(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["changes"][0]["proposedAction"] = "promote"

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.prepare_review_package(package, self.model_pack)

    def test_invalid_affected_id_is_refused_before_review_package(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["changes"][0]["affectedIds"].append(42)

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.prepare_review_package(package, self.model_pack)

    def test_invalid_package_review_action_is_refused(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["review"]["overallAction"] = "auto-promote"

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.prepare_review_package(package, self.model_pack)

    def test_high_risk_without_matching_review_owner_needs_info(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["changes"][0]["risk"] = "high"
        package["changes"][0].pop("candidateCard")

        review = self.prepare_review_package(package, self.model_pack)

        self.assertEqual(review["status"], "needs-info")
        self.assertEqual(review["owner"], "unknown")
        self.assertIn("needs-owner", {action["action"] for action in review["requiredActions"]})

    def test_multi_owner_high_risk_routes_to_escalation_owner(self):
        package = self.package("dashboard-metric-concern.synthetic.json")
        package["changes"][0]["candidateCard"] = {
            "links": {"source-of-truth": ["crm"]}
        }

        review = self.prepare_review_package(package, self.model_pack)

        self.assertEqual(review["status"], "pending")
        self.assertEqual(review["owner"], "role:operations-lead")

    def test_propagation_sla_routes_as_high_risk_authority_change(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["review"]["owner"] = "role:ontology-reviewer"
        package["changes"][0]["risk"] = "high"
        package["changes"][0]["candidateCard"]["type"] = "decision"
        package["changes"][0]["candidateCard"]["attrs"] = {
            "propagation-sla": "Dashboard and sales workflow updates must land within one business day.",
        }

        review = self.prepare_review_package(package, self.model_pack)

        self.assertEqual(review["status"], "pending")
        self.assertEqual(review["owner"], "role:acquisition-owner")
        self.assertIn(
            "candidate touches high-risk field propagation-sla",
            review["changes"][0]["highRiskReasons"],
        )

    def test_wrong_owner_cannot_approve_review(self):
        package = self.package("dashboard-metric-concern.synthetic.json")
        review = self.prepare_review_package(package, self.model_pack)

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.record_review_decision(
                review,
                {
                    "decision": "approve",
                    "actor": "role:random-reviewer",
                    "reason": "Trying to approve outside routed ownership.",
                    "decidedAt": "2026-06-22T12:00:00Z",
                },
            )

    def test_sensitive_decision_reason_is_refused_before_recording(self):
        package = self.package("dashboard-metric-concern.synthetic.json")
        review = self.prepare_review_package(package, self.model_pack)

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.record_review_decision(
                review,
                {
                    "decision": "approve",
                    "actor": "role:analytics-owner",
                    "reason": "Approve after checking alice@example.com.",
                    "decidedAt": "2026-06-22T12:00:00Z",
                },
            )

    def test_malformed_existing_audit_is_refused_before_decision(self):
        package = self.package("transcript-handoff.synthetic.json")
        review = self.prepare_review_package(package, self.model_pack)
        review["audit"].append("bad-audit-event")

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.record_review_decision(
                review,
                {
                    "decision": "reject",
                    "actor": "role:acquisition-owner",
                    "reason": "Malformed prior audit should be refused.",
                    "decidedAt": "2026-06-22T12:00:00Z",
                },
            )

    def test_tampered_review_package_missing_changes_is_refused_before_decision(self):
        package = self.package("transcript-handoff.synthetic.json")
        review = self.prepare_review_package(package, self.model_pack)
        del review["changes"]

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.record_review_decision(
                review,
                {
                    "decision": "reject",
                    "actor": "role:acquisition-owner",
                    "reason": "Tampered review package should not be decidable.",
                    "decidedAt": "2026-06-22T12:00:00Z",
                },
            )

    def test_tampered_pending_review_package_cannot_request_staged_proposal(self):
        package = self.package("transcript-handoff.synthetic.json")
        review = self.prepare_review_package(package, self.model_pack)
        review["requiredActions"].append(
            {
                "action": "prepare-staged-proposal",
                "changeId": review["packageId"],
                "reason": "This action is only valid after approval.",
            }
        )

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.record_review_decision(
                review,
                {
                    "decision": "approve",
                    "actor": "role:acquisition-owner",
                    "reason": "Tampered review package should not be decidable.",
                    "decidedAt": "2026-06-22T12:00:00Z",
                },
            )

    def test_terminal_review_cannot_be_decided_again(self):
        package = self.package("transcript-handoff.synthetic.json")
        review = self.prepare_review_package(package, self.model_pack)
        rejected = self.record_review_decision(
            review,
            {
                "decision": "reject",
                "actor": "role:acquisition-owner",
                "reason": "The owner rejects this package.",
                "decidedAt": "2026-06-22T12:00:00Z",
            },
        )

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.record_review_decision(
                rejected,
                {
                    "decision": "approve",
                    "actor": "role:acquisition-owner",
                    "reason": "Trying to reverse a terminal review item.",
                    "decidedAt": "2026-06-22T12:10:00Z",
                },
            )

    def test_package_model_pack_mismatch_is_refused(self):
        package = self.package("transcript-handoff.synthetic.json")
        package["modelPackId"] = "mp-other-module"

        with self.assertRaises(self.ApprovalManagerRefusal):
            self.prepare_review_package(package, self.model_pack)

    def test_approved_review_becomes_staged_proposal_ready_without_accepted_mutation(self):
        package = self.package("dashboard-metric-concern.synthetic.json")
        original_package = copy.deepcopy(package)
        review = self.prepare_review_package(package, self.model_pack)

        decided = self.record_review_decision(
            review,
            {
                "decision": "approve",
                "actor": "role:analytics-owner",
                "reason": "Metric owner confirms this should become a staged proposal.",
                "decidedAt": "2026-06-22T12:00:00Z",
            },
        )

        self.assertEqual(decided["status"], "staged-proposal-ready")
        self.assertEqual(decided["decisions"][0]["decision"], "approved")
        self.assertEqual(decided["requiredActions"][0]["action"], "prepare-staged-proposal")
        self.assertIs(decided["safety"]["noAcceptedMutation"], True)
        self.assertIs(decided["safety"]["noAutoPromotion"], True)
        self.assertIs(decided["safety"]["noCommit"], True)
        self.assertEqual(package, original_package)

    def test_rejected_review_records_reason_and_audit_event(self):
        package = self.package("transcript-handoff.synthetic.json")
        review = self.prepare_review_package(package, self.model_pack)

        decided = self.record_review_decision(
            review,
            {
                "decision": "reject",
                "actor": "role:acquisition-owner",
                "reason": "The transcript duplicated an existing accepted handoff.",
                "decidedAt": "2026-06-22T12:30:00Z",
            },
        )

        self.assertEqual(decided["status"], "rejected")
        self.assertEqual(decided["decisions"][0]["reason"], "The transcript duplicated an existing accepted handoff.")
        self.assertEqual(decided["audit"][-1]["result"], "rejected")
        self.assertEqual(decided["requiredActions"], [])


if __name__ == "__main__":
    unittest.main()

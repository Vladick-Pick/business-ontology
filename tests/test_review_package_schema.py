import json
from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "review-package.schema.json"
RESIDENT_RUNS_DIR = REPO_ROOT / "evals" / "fixtures" / "resident-runs"
CLAIM_KINDS = {
    "observed-fact",
    "owner-claim",
    "regulation",
    "dashboard-reading",
    "agent-inference",
    "human-decision",
    "unknown",
}
EVIDENCE_GRADES = {
    "measured",
    "instance",
    "external",
    "claim",
    "inference",
    "hypothesis",
    "framing",
    "unknown",
}
SOURCE_RISKS = {
    "no-known-risk",
    "stale-document",
    "partial-export",
    "manual-memory",
    "formula-unknown",
    "conflicting-source",
    "raw-source-unavailable",
    "owner-unknown",
    "auto-transcription-risk",
    "speaker-attribution-uncertain",
    "meeting-scope-unconfirmed",
    "provider-transcript-unverified",
    "unknown",
}
REVIEW_EVIDENCE_MODES = {
    "document-review-only",
    "source-locator-checked",
    "owner-confirmed",
    "live-runtime-checked",
    "not-checked",
}
SOURCE_ADEQUACY = {
    "sufficient",
    "partial",
    "conflicting",
    "stale",
    "missing-owner",
    "insufficient",
}
SLA_BANDS = {"high-risk-48h", "definition-interface-7d", "normal", "needs-owner"}


class ReviewPackageSchemaTests(unittest.TestCase):
    def load_schema(self):
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def fixture_paths(self):
        return sorted(RESIDENT_RUNS_DIR.glob("*/reviews/*.json"))

    def source_event_ids(self):
        ids = set()
        for path in RESIDENT_RUNS_DIR.glob("*/source-event.json"):
            event = json.loads(path.read_text(encoding="utf-8"))
            ids.add(event["eventId"])
        return ids

    def test_schema_is_strict_object_contract(self):
        schema = self.load_schema()

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
                "decisionImpact",
                "reviewEvidenceMode",
                "sourceAdequacy",
                "slaBand",
                "changes",
                "requiredActions",
                "decisions",
                "audit",
                "safety",
            },
        )
        self.assertIn("allOf", schema)

    def test_schema_locks_decision_impact_and_reality_review_fields(self):
        schema = self.load_schema()
        decision_impact = schema["properties"]["decisionImpact"]

        self.assertFalse(decision_impact["additionalProperties"])
        self.assertEqual(
            set(decision_impact["required"]),
            {
                "affectedWorkflows",
                "affectedMetrics",
                "affectedInterfaces",
                "affectedOwners",
                "decisionUse",
                "blastRadius",
            },
        )
        for field in ["affectedWorkflows", "affectedMetrics", "affectedInterfaces", "affectedOwners"]:
            self.assertEqual(decision_impact["properties"][field]["type"], "array")
            self.assertTrue(decision_impact["properties"][field]["uniqueItems"])
        self.assertEqual(
            set(schema["properties"]["reviewEvidenceMode"]["enum"]),
            REVIEW_EVIDENCE_MODES,
        )
        self.assertEqual(set(schema["properties"]["sourceAdequacy"]["enum"]), SOURCE_ADEQUACY)
        self.assertEqual(set(schema["properties"]["slaBand"]["enum"]), SLA_BANDS)

    def test_captured_review_packages_have_required_shape_and_safe_flags(self):
        schema = self.load_schema()
        change_schema = schema["properties"]["changes"]["items"]
        required = set(schema["required"])
        change_required = set(change_schema["required"])
        allowed_statuses = set(schema["properties"]["status"]["enum"])
        allowed_risks = set(schema["properties"]["risk"]["enum"])
        allowed_kinds = set(change_schema["properties"]["kind"]["enum"])
        allowed_confidences = set(change_schema["properties"]["confidence"]["enum"])
        allowed_actions = set(change_schema["properties"]["proposedAction"]["enum"])
        self.assertEqual(set(change_schema["properties"]["claimKind"]["enum"]), CLAIM_KINDS)
        self.assertEqual(set(change_schema["properties"]["evidenceGrade"]["enum"]), EVIDENCE_GRADES)
        self.assertEqual(
            set(change_schema["properties"]["sourceRisk"]["items"]["enum"]),
            SOURCE_RISKS,
        )
        self.assertTrue(change_schema["properties"]["sourceRisk"]["uniqueItems"])
        self.assertEqual(change_schema["properties"]["sourceRisk"]["minItems"], 1)
        self.assertEqual(
            change_schema["properties"]["sourceRisk"]["allOf"][0]["not"]["allOf"][0]["contains"]["const"],
            "unknown",
        )
        self.assertEqual(
            change_schema["properties"]["sourceRisk"]["allOf"][0]["not"]["allOf"][1]["minItems"],
            2,
        )
        self.assertEqual(
            change_schema["properties"]["sourceRisk"]["allOf"][1]["not"]["allOf"][0]["contains"]["const"],
            "no-known-risk",
        )
        self.assertEqual(
            change_schema["properties"]["sourceRisk"]["allOf"][1]["not"]["allOf"][1]["minItems"],
            2,
        )
        self.assertTrue(
            any(
                rule.get("if", {}).get("properties", {}).get("claimKind", {}).get("const")
                == "agent-inference"
                and set(
                    rule.get("then", {})
                    .get("properties", {})
                    .get("evidenceGrade", {})
                    .get("enum", [])
                )
                == {"inference", "hypothesis"}
                for rule in change_schema["allOf"]
            )
        )
        self.assertTrue(
            any(
                rule.get("if", {}).get("properties", {}).get("kind", {}).get("const")
                == "system-analysis-result"
                and set(rule.get("then", {}).get("required", []))
                >= {"systemAnalysisResultId", "systemAnalysisClassification"}
                for rule in change_schema["allOf"]
            )
        )
        self.assertTrue(
            any(
                rule.get("if", {}).get("properties", {}).get("proposedAction", {}).get("const")
                == "review-system-analysis-result"
                and set(rule.get("then", {}).get("required", []))
                >= {"systemAnalysisResultId", "systemAnalysisClassification"}
                for rule in change_schema["allOf"]
            )
        )
        source_event_ids = self.source_event_ids()
        fixtures = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in self.fixture_paths()
        ]

        self.assertGreaterEqual(len(fixtures), 4)
        for fixture in fixtures:
            self.assertEqual(required - set(fixture), set(), fixture.get("reviewId"))
            self.assertRegex(fixture["reviewId"], r"^rev-[a-z0-9][a-z0-9-]*$")
            self.assertRegex(fixture["packageId"], r"^mcpkg-[a-z0-9][a-z0-9-]*$")
            self.assertRegex(fixture["moduleId"], r"^[a-z0-9][a-z0-9-]*$")
            self.assertIn(fixture["status"], allowed_statuses)
            self.assertIn(fixture["risk"], allowed_risks)
            self.assertLessEqual(len(fixture["summary"]), 1000)
            self.assertIn(fixture["reviewEvidenceMode"], REVIEW_EVIDENCE_MODES)
            self.assertIn(fixture["sourceAdequacy"], SOURCE_ADEQUACY)
            self.assertIn(fixture["slaBand"], SLA_BANDS)
            self.assertEqual(
                set(fixture["decisionImpact"]),
                {
                    "affectedWorkflows",
                    "affectedMetrics",
                    "affectedInterfaces",
                    "affectedOwners",
                    "decisionUse",
                    "blastRadius",
                },
                fixture["reviewId"],
            )
            for field in ["affectedWorkflows", "affectedMetrics", "affectedInterfaces", "affectedOwners"]:
                self.assertEqual(len(fixture["decisionImpact"][field]), len(set(fixture["decisionImpact"][field])))
            self.assertTrue(fixture["decisionImpact"]["decisionUse"].strip(), fixture["reviewId"])
            self.assertTrue(fixture["decisionImpact"]["blastRadius"].strip(), fixture["reviewId"])

            for flag in ["noAcceptedMutation", "noAutoPromotion", "noCommit", "noSourceWriteback"]:
                self.assertIs(fixture["safety"][flag], True, fixture["reviewId"])

            for change in fixture["changes"]:
                self.assertEqual(change_required - set(change), set(), change.get("changeId"))
                self.assertRegex(change["changeId"], r"^chg-[a-z0-9][a-z0-9-]*$")
                self.assertIn(change["kind"], allowed_kinds)
                self.assertIn(change["confidence"], allowed_confidences)
                self.assertIn(change["risk"], allowed_risks)
                self.assertIn(change["claimKind"], CLAIM_KINDS)
                self.assertIn(change["evidenceGrade"], EVIDENCE_GRADES)
                self.assertTrue(set(change["sourceRisk"]) <= SOURCE_RISKS)
                self.assertGreaterEqual(len(change["sourceRisk"]), 1)
                self.assertEqual(len(change["sourceRisk"]), len(set(change["sourceRisk"])))
                self.assertIn(change["proposedAction"], allowed_actions)
                self.assertEqual(len(change["affectedIds"]), len(set(change["affectedIds"])))
                for evidence in change["evidence"]:
                    self.assertIn(evidence["sourceEventId"], source_event_ids, change["changeId"])
                    self.assertLessEqual(len(evidence["excerpt"]), 280, change["changeId"])

    def test_staged_ready_review_requires_routed_owner_approval(self):
        for path in self.fixture_paths():
            fixture = json.loads(path.read_text(encoding="utf-8"))
            if fixture["status"] != "staged-proposal-ready":
                continue
            approved = [
                decision for decision in fixture["decisions"]
                if decision.get("decision") == "approved"
                and decision.get("actor") == fixture["owner"]
                and decision.get("resultingStatus") == "staged-proposal-ready"
            ]
            self.assertTrue(approved, path.name)

    def test_captured_review_packages_do_not_contain_private_payload_markers(self):
        forbidden_terms = [
            "password",
            "credential",
            "api key",
            "secret key",
            "bearer ",
            "private message body",
            "raw transcript",
            "raw payload",
        ]
        email_like = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+")
        phone_like = re.compile(r"(?:\+?\d[\s-]?){10,}")

        for path in self.fixture_paths():
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            for term in forbidden_terms:
                self.assertNotIn(term, lowered, path.name)
            self.assertIsNone(email_like.search(text), path.name)
            self.assertIsNone(phone_like.search(text), path.name)


if __name__ == "__main__":
    unittest.main()

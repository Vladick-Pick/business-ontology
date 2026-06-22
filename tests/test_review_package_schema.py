import json
from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "review-package.schema.json"
RESIDENT_RUNS_DIR = REPO_ROOT / "evals" / "fixtures" / "resident-runs"


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
                "changes",
                "requiredActions",
                "decisions",
                "audit",
                "safety",
            },
        )
        self.assertIn("allOf", schema)

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

            for flag in ["noAcceptedMutation", "noAutoPromotion", "noCommit", "noSourceWriteback"]:
                self.assertIs(fixture["safety"][flag], True, fixture["reviewId"])

            for change in fixture["changes"]:
                self.assertEqual(change_required - set(change), set(), change.get("changeId"))
                self.assertRegex(change["changeId"], r"^chg-[a-z0-9][a-z0-9-]*$")
                self.assertIn(change["kind"], allowed_kinds)
                self.assertIn(change["confidence"], allowed_confidences)
                self.assertIn(change["risk"], allowed_risks)
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

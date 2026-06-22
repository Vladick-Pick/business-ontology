import json
from pathlib import Path
import re
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import links_validate  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "schemas" / "model-change-package.schema.json"
MODEL_PACK_PATH = REPO_ROOT / "examples" / "model-packs" / "acquisition.model-pack.json"
SOURCE_EVENT_DIR = REPO_ROOT / "evals" / "fixtures" / "source-events"
FIXTURE_DIR = REPO_ROOT / "evals" / "fixtures" / "model-change-packages"
RESIDENT_RUNS_DIR = REPO_ROOT / "evals" / "fixtures" / "resident-runs"


def walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from walk_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from walk_strings(item)


class ModelChangePackageSchemaTests(unittest.TestCase):
    def load_schema(self):
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def load_model_pack(self):
        return json.loads(MODEL_PACK_PATH.read_text(encoding="utf-8"))

    def fixture_paths(self):
        return sorted(FIXTURE_DIR.glob("*.json"))

    def captured_fixture_paths(self):
        return sorted(RESIDENT_RUNS_DIR.glob("*/packages/*.json"))

    def load_fixtures(self):
        return [json.loads(path.read_text(encoding="utf-8")) for path in self.fixture_paths()]

    def source_events_by_id(self):
        events = {}
        for path in SOURCE_EVENT_DIR.glob("*.json"):
            event = json.loads(path.read_text(encoding="utf-8"))
            events[event["eventId"]] = event
        for path in RESIDENT_RUNS_DIR.glob("*/source-event.json"):
            event = json.loads(path.read_text(encoding="utf-8"))
            events[event["eventId"]] = event
        return events

    def source_event_ids(self):
        return set(self.source_events_by_id())

    def accepted_cards(self):
        errors = []
        cards = links_validate.collect_cards(str(REPO_ROOT), str(REPO_ROOT), errors)
        self.assertEqual(errors, [])
        return cards

    def test_schema_is_strict_object_contract(self):
        schema = self.load_schema()

        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema.get("additionalProperties", True))

        expected_required = {
            "packageId",
            "moduleId",
            "modelPackId",
            "modelPackVersion",
            "ontologyRevision",
            "compiler",
            "sourceEventIds",
            "generatedAt",
            "summary",
            "changes",
            "review",
            "safety",
        }
        self.assertEqual(set(schema["required"]), expected_required)

    def test_schema_locks_nested_contracts(self):
        schema = self.load_schema()
        change_schema = schema["properties"]["changes"]["items"]
        evidence_schema = change_schema["properties"]["evidence"]["items"]
        compiler_schema = schema["properties"]["compiler"]
        review_schema = schema["properties"]["review"]
        safety_schema = schema["properties"]["safety"]

        self.assertFalse(change_schema["additionalProperties"])
        self.assertFalse(evidence_schema["additionalProperties"])
        self.assertFalse(compiler_schema["additionalProperties"])
        self.assertFalse(review_schema["additionalProperties"])
        self.assertFalse(safety_schema["additionalProperties"])
        self.assertTrue(schema["properties"]["sourceEventIds"]["uniqueItems"])
        self.assertTrue(change_schema["properties"]["affectedIds"]["uniqueItems"])
        self.assertEqual(
            set(compiler_schema["properties"]["mode"]["enum"]),
            {"synthetic-fixture", "manual-review", "automated"},
        )

        expected_kinds = {
            "new-object",
            "new-definition",
            "new-decision",
            "new-agreement",
            "drift",
            "conflict",
            "source-of-truth-change",
            "dashboard-metric-concern",
            "stale-area",
            "no-op",
        }
        self.assertEqual(set(change_schema["properties"]["kind"]["enum"]), expected_kinds)
        self.assertEqual(
            set(change_schema["properties"]["proposedAction"]["enum"]),
            {
                "prepare-staged-proposal",
                "open-drift-review",
                "open-conflict-review",
                "review-source-of-truth",
                "review-dashboard-metric",
                "needs-info",
                "record-no-op",
            },
        )
        self.assertEqual(
            set(review_schema["properties"]["overallAction"]["enum"]),
            {"human-review", "needs-owner", "no-review-needed"},
        )
        for flag in ["noPii", "noSecrets", "noRawPayload", "noAcceptedMutation"]:
            self.assertTrue(safety_schema["properties"][flag]["const"])

    def test_candidate_card_contract_is_structured_and_non_accepted(self):
        schema = self.load_schema()
        change_properties = schema["properties"]["changes"]["items"]["properties"]
        candidate_schema = change_properties["candidateCard"]

        self.assertNotIn("candidateCardMarkdown", change_properties)
        self.assertFalse(candidate_schema["additionalProperties"])
        self.assertEqual(
            set(candidate_schema["properties"]["type"]["enum"]),
            links_validate.CARD_TYPES,
        )
        self.assertEqual(
            set(candidate_schema["properties"]["status"]["enum"]),
            {"candidate", "hypothesis", "conflict", "unknown", "proposed"},
        )
        self.assertNotIn("accepted", candidate_schema["properties"]["status"]["enum"])
        self.assertEqual(
            candidate_schema["allOf"][0]["if"]["properties"]["type"]["const"],
            "decision",
        )
        self.assertEqual(
            set(candidate_schema["allOf"][0]["then"]["properties"]["status"]["enum"]),
            {"proposed"},
        )
        decision_attrs = candidate_schema["allOf"][0]["then"]["properties"]["attrs"]
        self.assertFalse(decision_attrs["additionalProperties"])
        self.assertEqual(set(decision_attrs["required"]), links_validate.REQUIRED_ATTRS["decision"])
        self.assertEqual(
            set(candidate_schema["allOf"][1]["if"]["properties"]["type"]["enum"]),
            links_validate.CARD_TYPES - {"decision"},
        )
        self.assertEqual(
            set(candidate_schema["allOf"][1]["then"]["properties"]["status"]["enum"]),
            {"candidate", "hypothesis", "conflict", "unknown"},
        )
        self.assertEqual(
            candidate_schema["allOf"][2]["if"]["properties"]["type"]["const"],
            "interface",
        )
        interface_attrs = candidate_schema["allOf"][2]["then"]["properties"]["attrs"]
        participants = interface_attrs["properties"]["participants"]
        self.assertFalse(interface_attrs["additionalProperties"])
        self.assertEqual(set(interface_attrs["required"]), links_validate.REQUIRED_ATTRS["interface"])
        self.assertEqual(
            set(participants["required"]),
            links_validate.REQUIRED_INTERFACE_PARTICIPANTS,
        )
        self.assertFalse(participants["additionalProperties"])
        self.assertFalse(candidate_schema["properties"]["links"]["additionalProperties"])
        self.assertEqual(
            set(candidate_schema["properties"]["links"]["properties"]),
            links_validate.ALLOWED_LINKS,
        )
        self.assertIn("attrs", candidate_schema["properties"])

    def test_fixtures_have_required_shape_and_safe_flags(self):
        schema = self.load_schema()
        required = set(schema["required"])
        change_required = set(schema["properties"]["changes"]["items"]["required"])
        allowed_kinds = set(schema["properties"]["changes"]["items"]["properties"]["kind"]["enum"])
        allowed_actions = set(
            schema["properties"]["changes"]["items"]["properties"]["proposedAction"]["enum"]
        )
        source_event_ids = self.source_event_ids()
        model_pack = self.load_model_pack()

        fixtures = self.load_fixtures()
        self.assertGreaterEqual(len(fixtures), 3)
        for fixture in fixtures:
            self.assertEqual(required - set(fixture), set(), fixture.get("packageId"))
            self.assertRegex(fixture["packageId"], r"^mcpkg-[a-z0-9][a-z0-9-]*$")
            self.assertEqual(fixture["modelPackId"], model_pack["modelPackId"])
            self.assertEqual(fixture["modelPackVersion"], model_pack["version"])
            self.assertRegex(fixture["ontologyRevision"], r"^(git|registry|gbrain):")
            self.assertEqual(fixture["compiler"]["mode"], "synthetic-fixture")
            self.assertEqual(len(fixture["sourceEventIds"]), len(set(fixture["sourceEventIds"])))
            self.assertTrue(set(fixture["sourceEventIds"]) <= source_event_ids)

            self.assertIs(fixture["safety"]["noPii"], True)
            self.assertIs(fixture["safety"]["noSecrets"], True)
            self.assertIs(fixture["safety"]["noRawPayload"], True)
            self.assertIs(fixture["safety"]["noAcceptedMutation"], True)

            for change in fixture["changes"]:
                self.assertEqual(change_required - set(change), set(), change.get("changeId"))
                self.assertIn(change["kind"], allowed_kinds)
                self.assertIn(change["proposedAction"], allowed_actions)
                self.assertEqual(len(change["affectedIds"]), len(set(change["affectedIds"])))
                for evidence in change["evidence"]:
                    self.assertIn(evidence["sourceEventId"], source_event_ids)
                    self.assertLessEqual(len(evidence["excerpt"]), 280)

    def test_captured_resident_packages_have_required_shape_and_safe_flags(self):
        schema = self.load_schema()
        required = set(schema["required"])
        change_schema = schema["properties"]["changes"]["items"]
        change_required = set(change_schema["required"])
        allowed_kinds = set(change_schema["properties"]["kind"]["enum"])
        allowed_confidences = set(change_schema["properties"]["confidence"]["enum"])
        allowed_risks = set(change_schema["properties"]["risk"]["enum"])
        allowed_actions = set(change_schema["properties"]["proposedAction"]["enum"])
        source_event_ids = self.source_event_ids()
        fixtures = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in self.captured_fixture_paths()
        ]

        self.assertGreaterEqual(len(fixtures), 4)
        for fixture in fixtures:
            self.assertEqual(required - set(fixture), set(), fixture.get("packageId"))
            self.assertRegex(fixture["packageId"], r"^mcpkg-[a-z0-9][a-z0-9-]*$")
            self.assertRegex(fixture["moduleId"], r"^[a-z0-9][a-z0-9-]*$")
            self.assertRegex(fixture["modelPackId"], r"^mp-[a-z0-9][a-z0-9-]*$")
            self.assertRegex(fixture["ontologyRevision"], r"^(git|registry|gbrain):")
            self.assertLessEqual(len(fixture["summary"]), 1000)
            self.assertEqual(len(fixture["sourceEventIds"]), len(set(fixture["sourceEventIds"])))
            self.assertTrue(set(fixture["sourceEventIds"]) <= source_event_ids, fixture["packageId"])

            for flag in ["noPii", "noSecrets", "noRawPayload", "noAcceptedMutation"]:
                self.assertIs(fixture["safety"][flag], True, fixture["packageId"])

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
                drift = change.get("drift")
                if drift is not None:
                    self.assertEqual(set(drift), {"was", "now", "reason"})
                    self.assertTrue(all(isinstance(drift[key], str) and drift[key] for key in drift))

    def test_fixtures_reference_model_pack_source_authority(self):
        source_events = self.source_events_by_id()
        source_kinds = {
            rule["sourceKind"]
            for rule in self.load_model_pack()["sourceAuthority"]
        }

        for fixture in self.load_fixtures():
            for event_id in fixture["sourceEventIds"]:
                self.assertIn(source_events[event_id]["sourceKind"], source_kinds, fixture["packageId"])
            for change in fixture["changes"]:
                for evidence in change["evidence"]:
                    source_kind = source_events[evidence["sourceEventId"]]["sourceKind"]
                    self.assertIn(source_kind, source_kinds, change["changeId"])

    def test_fixtures_resolve_ontology_references(self):
        accepted_ids = set(self.accepted_cards())

        for fixture in self.load_fixtures():
            for change in fixture["changes"]:
                for affected_id in change["affectedIds"]:
                    if affected_id != "unknown":
                        self.assertIn(affected_id, accepted_ids, change["changeId"])

                candidate = change.get("candidateCard")
                if not candidate:
                    continue
                candidate_frontmatter = {
                    key: value for key, value in candidate.items() if key != "summary"
                }
                candidate_frontmatter.update({
                    "last-reviewed": "unknown",
                    "next-audit": "unknown",
                })
                errors = []
                links_validate.validate_card_shape(candidate["id"], candidate_frontmatter, errors)
                self.assertEqual(errors, [])
                self.assertNotEqual(candidate["status"], "accepted")
                for relation, targets in candidate.get("links", {}).items():
                    self.assertIn(relation, links_validate.ALLOWED_LINKS)
                    for target in targets:
                        self.assertIn(target, accepted_ids, candidate["id"])
                for participant_ids in candidate.get("attrs", {}).get("participants", {}).values():
                    for participant_id in participant_ids:
                        self.assertIn(participant_id, accepted_ids, candidate["id"])

    def test_noop_fixture_is_explicitly_non_reviewable(self):
        fixtures = {fixture["packageId"]: fixture for fixture in self.load_fixtures()}
        noop = fixtures["mcpkg-noop-duplicate-source-001"]

        self.assertEqual(noop["review"]["overallAction"], "no-review-needed")
        self.assertEqual(noop["changes"][0]["kind"], "no-op")
        self.assertEqual(noop["changes"][0]["proposedAction"], "record-no-op")

    def test_fixtures_do_not_contain_private_payload_markers(self):
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
        phone_like = re.compile(r"(?:\\+?\\d[\\s-]?){10,}")

        for path in self.fixture_paths() + self.captured_fixture_paths():
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            for term in forbidden_terms:
                self.assertNotIn(term, lowered, path.name)
            self.assertIsNone(email_like.search(text), path.name)
            self.assertIsNone(phone_like.search(text), path.name)


if __name__ == "__main__":
    unittest.main()

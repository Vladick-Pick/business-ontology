import json
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import links_validate  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "schemas" / "model-pack.schema.json"
FIXTURE_PATH = REPO_ROOT / "examples" / "model-packs" / "acquisition.model-pack.json"


def walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from walk_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from walk_strings(item)


class ModelPackSchemaTests(unittest.TestCase):
    def load_schema(self):
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def load_fixture(self):
        return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_schema_is_strict_object_contract(self):
        schema = self.load_schema()

        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema.get("additionalProperties", True))

        expected_required = {
            "modelPackId",
            "moduleId",
            "version",
            "companyModelLanguage",
            "owners",
            "objectTypes",
            "relationPolicy",
            "sourceAuthority",
            "highRiskFields",
            "reviewOwners",
            "digestPolicy",
            "businessArchitecture",
            "compilerHints",
            "competencyQuestions",
        }
        self.assertEqual(set(schema["required"]), expected_required)

    def test_schema_locks_competency_question_contract_without_global_count(self):
        schema = self.load_schema()
        questions = schema["properties"]["competencyQuestions"]
        question = questions["items"]

        self.assertEqual(questions["type"], "array")
        self.assertNotIn("minItems", questions)
        self.assertFalse(question["additionalProperties"])
        self.assertEqual(
            set(question["required"]),
            {
                "questionId",
                "scopeId",
                "question",
                "decisionUse",
                "answerStatus",
                "answeredByIds",
                "missingFields",
                "owner",
                "lastReviewedAt",
            },
        )
        self.assertEqual(
            set(question["properties"]["answerStatus"]["enum"]),
            {"answered", "partially-answered", "unanswered", "blocked"},
        )
        self.assertTrue(question["properties"]["answeredByIds"]["uniqueItems"])
        self.assertTrue(question["properties"]["missingFields"]["uniqueItems"])

    def test_fixture_has_required_shape_and_no_blank_strings(self):
        fixture = self.load_fixture()
        required = set(self.load_schema()["required"])

        self.assertEqual(required - set(fixture), set())
        self.assertRegex(fixture["modelPackId"], r"^mp-[a-z0-9][a-z0-9-]*$")
        self.assertEqual(fixture["moduleId"], "acquisition")

        blank_strings = [value for value in walk_strings(fixture) if not value.strip()]
        self.assertEqual(blank_strings, [])

    def test_acquisition_fixture_has_decision_useful_competency_questions(self):
        fixture = self.load_fixture()
        questions = fixture["competencyQuestions"]

        self.assertGreaterEqual(len(questions), 5)
        self.assertLessEqual(len(questions), 15)
        self.assertEqual(len({item["questionId"] for item in questions}), len(questions))
        required_scope_terms = {
            "metric": False,
            "source of truth": False,
            "workflow": False,
            "state": False,
            "owner": False,
        }

        for item in questions:
            self.assertRegex(item["questionId"], r"^cq-[a-z0-9][a-z0-9-]*$")
            self.assertRegex(item["scopeId"], r"^[a-z0-9][a-z0-9-]*$")
            self.assertIn(item["answerStatus"], {"answered", "partially-answered", "unanswered", "blocked"})
            self.assertEqual(len(item["answeredByIds"]), len(set(item["answeredByIds"])))
            self.assertEqual(len(item["missingFields"]), len(set(item["missingFields"])))
            self.assertTrue(item["owner"])
            self.assertTrue(item["lastReviewedAt"])
            self.assertTrue(item["question"].endswith("?"), item["questionId"])
            self.assertGreaterEqual(len(item["decisionUse"].split()), 4, item["questionId"])

            lowered = f"{item['question']} {item['decisionUse']}".lower()
            for term in required_scope_terms:
                if term in lowered:
                    required_scope_terms[term] = True

        self.assertTrue(all(required_scope_terms.values()), required_scope_terms)

    def test_fixture_names_expected_high_risk_fields(self):
        fixture = self.load_fixture()
        high_risk = set(fixture["highRiskFields"])

        expected = {
            "decision-owner",
            "transition-authority",
            "measurement-convention",
            "affected-kpis",
            "propagation-sla",
            "override-policy",
            "exception-path",
            "blast-radius",
            "source-of-truth",
        }
        self.assertEqual(high_risk, expected)

    def test_business_architecture_pilot_connects_value_to_workflow(self):
        fixture = self.load_fixture()
        architecture = fixture["businessArchitecture"]

        for key in [
            "valueStreams",
            "valueStages",
            "capabilities",
            "stakeholders",
            "valueItems",
            "businessObjects",
        ]:
            self.assertEqual(len(architecture[key]), 1, key)

        relations = architecture["relations"]
        relation_types = {relation["relation"] for relation in relations}
        self.assertEqual(
            relation_types,
            {
                "stakeholder-triggers-value-stream",
                "value-stream-contains-value-stage",
                "capability-enables-value-stage",
                "value-stage-delivers-value-item",
                "workflow-realizes-value-stage",
                "business-object-changes-state-in-workflow",
            },
        )
        self.assertIn(
            {
                "relation": "workflow-realizes-value-stage",
                "fromId": "wf-lead-ready-to-meeting-booked",
                "toId": "vst-sales-ready-handoff",
            },
            relations,
        )
        self.assertIn(
            {
                "relation": "business-object-changes-state-in-workflow",
                "fromId": "bo-prospective-participant",
                "toId": "wf-lead-ready-to-meeting-booked",
            },
            relations,
        )

    def test_fixture_stays_inside_locked_card_contract(self):
        schema = self.load_schema()
        fixture = self.load_fixture()

        card_type_enum = set(
            schema["properties"]["objectTypes"]["items"]["properties"]["cardTypes"]["items"]["enum"]
        )
        relation_enum = set(
            schema["properties"]["relationPolicy"]["properties"]["allowedRelations"]["items"]["enum"]
        )
        status_enum = set(
            schema["properties"]["sourceAuthority"]["items"]["properties"]["maxStatus"]["enum"]
        )

        v2_card_types = links_validate.CARD_TYPES - set(links_validate.DEPRECATED_TYPE_ALIASES)
        v2_relations = links_validate.ALLOWED_LINKS - set(links_validate.DEPRECATED_LINK_ALIASES)

        self.assertEqual(card_type_enum, v2_card_types)
        self.assertEqual(relation_enum, v2_relations)
        self.assertEqual(status_enum, links_validate.CARD_STATUSES)

        for object_type in fixture["objectTypes"]:
            self.assertTrue(set(object_type["cardTypes"]) <= v2_card_types)
        self.assertEqual(set(fixture["relationPolicy"]["allowedRelations"]), v2_relations)
        for source_rule in fixture["sourceAuthority"]:
            self.assertIn(source_rule["maxStatus"], links_validate.CARD_STATUSES)

    def test_compiler_hints_do_not_claim_governance_authority(self):
        fixture = self.load_fixture()
        hint_keys = set(fixture["compilerHints"])

        forbidden_keys = {
            "systemPrompt",
            "developerPrompt",
            "overrideInstructions",
            "acceptedStatusOverride",
            "autoPromote",
        }
        self.assertEqual(hint_keys & forbidden_keys, set())

        joined_hints = "\n".join(walk_strings(fixture["compilerHints"])).lower()
        self.assertNotIn("mark accepted", joined_hints)
        self.assertNotIn("auto-promote", joined_hints)


if __name__ == "__main__":
    unittest.main()

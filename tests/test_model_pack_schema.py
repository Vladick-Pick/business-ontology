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
            "owners",
            "objectTypes",
            "relationPolicy",
            "sourceAuthority",
            "highRiskFields",
            "reviewOwners",
            "digestPolicy",
            "compilerHints",
        }
        self.assertEqual(set(schema["required"]), expected_required)

    def test_fixture_has_required_shape_and_no_blank_strings(self):
        fixture = self.load_fixture()
        required = set(self.load_schema()["required"])

        self.assertEqual(required - set(fixture), set())
        self.assertRegex(fixture["modelPackId"], r"^mp-[a-z0-9][a-z0-9-]*$")
        self.assertEqual(fixture["moduleId"], "acquisition")

        blank_strings = [value for value in walk_strings(fixture) if not value.strip()]
        self.assertEqual(blank_strings, [])

    def test_fixture_names_expected_high_risk_fields(self):
        fixture = self.load_fixture()
        high_risk = set(fixture["highRiskFields"])

        expected = {
            "decision-owner",
            "transition-authority",
            "measurement-convention",
            "affected-kpis",
            "override-policy",
            "exception-path",
            "blast-radius",
            "source-of-truth",
        }
        self.assertEqual(high_risk, expected)

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

        self.assertEqual(card_type_enum, links_validate.CARD_TYPES)
        self.assertEqual(relation_enum, links_validate.ALLOWED_LINKS)
        self.assertEqual(status_enum, links_validate.CARD_STATUSES)

        for object_type in fixture["objectTypes"]:
            self.assertTrue(set(object_type["cardTypes"]) <= links_validate.CARD_TYPES)
        self.assertEqual(set(fixture["relationPolicy"]["allowedRelations"]), links_validate.ALLOWED_LINKS)
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

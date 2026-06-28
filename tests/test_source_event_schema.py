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

SCHEMA_PATH = REPO_ROOT / "schemas" / "source-event.schema.json"
SOURCE_MAP_SCHEMA_PATH = REPO_ROOT / "schemas" / "source-map-entry.schema.json"
FIXTURE_DIR = REPO_ROOT / "evals" / "fixtures" / "source-events"
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


class SourceEventSchemaTests(unittest.TestCase):
    def load_schema(self):
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def load_source_map_schema(self):
        return json.loads(SOURCE_MAP_SCHEMA_PATH.read_text(encoding="utf-8"))

    def fixture_paths(self):
        return sorted(FIXTURE_DIR.glob("*.json")) + sorted(
            RESIDENT_RUNS_DIR.glob("*/source-event.json")
        )

    def load_fixtures(self):
        return [json.loads(path.read_text(encoding="utf-8")) for path in self.fixture_paths()]

    def test_schema_is_strict_object_contract(self):
        schema = self.load_schema()

        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema.get("additionalProperties", True))

        expected_required = {
            "eventId",
            "sourceId",
            "sourceKind",
            "observedAt",
            "connector",
            "authority",
            "trustFloor",
            "redaction",
            "evidence",
            "contentSummary",
            "hash",
        }
        self.assertEqual(set(schema["required"]), expected_required)

    def test_schema_locks_nested_contracts(self):
        schema = self.load_schema()
        source_map_schema = self.load_source_map_schema()

        self.assertFalse(schema["properties"]["connector"]["additionalProperties"])
        self.assertFalse(schema["properties"]["authority"]["additionalProperties"])
        self.assertFalse(schema["properties"]["redaction"]["additionalProperties"])
        self.assertFalse(schema["properties"]["evidence"]["items"]["additionalProperties"])

        self.assertEqual(
            set(schema["properties"]["connector"]["properties"]["mode"]["enum"]),
            {"manual-export", "api-read", "file-drop"},
        )
        self.assertTrue(schema["properties"]["connector"]["properties"]["readOnly"]["const"])
        self.assertTrue(schema["properties"]["redaction"]["properties"]["piiExcluded"]["const"])
        self.assertFalse(schema["properties"]["redaction"]["properties"]["rawPayloadIncluded"]["const"])
        self.assertEqual(
            set(schema["properties"]["evidence"]["items"]["properties"]["segmentType"]["enum"]),
            {"time-range", "line-range", "cell-range", "record-class", "section", "widget"},
        )

        source_event_trust = set(schema["properties"]["trustFloor"]["enum"])
        source_map_trust = set(source_map_schema["properties"]["trust"]["enum"])
        self.assertEqual(source_map_trust, links_validate.CARD_STATUSES)
        self.assertEqual(source_event_trust, source_map_trust - {"accepted"})

    def test_source_kind_vocabulary_is_connector_neutral(self):
        schema = self.load_schema()
        source_kinds = set(schema["properties"]["sourceKind"]["enum"])

        self.assertEqual(
            source_kinds,
            {
                "human-session",
                "telegram-export",
                "meeting-transcript",
                "dashboard-snapshot",
                "crm-export",
                "document",
                "manual-drop",
                "google-drive",
                "calendar-event",
            },
        )
        self.assertNotIn("zoom-transcript", source_kinds)
        self.assertNotIn("fireflies-transcript", source_kinds)

    def test_source_kind_documentation_uses_schema_terms(self):
        allowed = set(self.load_schema()["properties"]["sourceKind"]["enum"])
        paths = [
            REPO_ROOT / "specs" / "SOURCE-SPEC.md",
            REPO_ROOT / "adapters" / "openclaw" / "source-setup" / "telegram.md",
            REPO_ROOT / "adapters" / "openclaw" / "source-setup" / "dashboard.md",
            REPO_ROOT / "adapters" / "openclaw" / "source-setup" / "google-drive.md",
            REPO_ROOT / "adapters" / "openclaw" / "source-setup" / "transcripts.md",
        ]
        forbidden = {
            "telegram-chat",
            "telegram-channel",
            "google-drive-folder",
            "dashboard",
            "manual-material",
            "zoom-transcript",
            "fireflies-transcript",
        } - allowed

        for path in paths:
            text = path.read_text(encoding="utf-8")
            for kind in forbidden:
                self.assertNotIn(f"`{kind}`", text, f"{path}: {kind}")

    def test_all_synthetic_fixtures_parse_and_have_required_fields(self):
        schema = self.load_schema()
        required = set(schema["required"])
        source_kinds = set(schema["properties"]["sourceKind"]["enum"])
        fixtures = self.load_fixtures()

        self.assertGreaterEqual(len(fixtures), 4)
        for fixture in fixtures:
            self.assertEqual(required - set(fixture), set(), fixture.get("eventId"))
            self.assertRegex(fixture["eventId"], r"^srcevt-[a-z0-9][a-z0-9-]*$")
            self.assertIn(fixture["sourceKind"], source_kinds)
            self.assertRegex(fixture["hash"], r"^sha256:[a-f0-9]{64}$")
            self.assertGreaterEqual(len(fixture["evidence"]), 1)

    def test_redaction_policy_is_safe_for_all_fixtures(self):
        for fixture in self.load_fixtures():
            redaction = fixture["redaction"]
            connector = fixture["connector"]

            self.assertIs(redaction["piiExcluded"], True, fixture["eventId"])
            self.assertIs(redaction["rawPayloadIncluded"], False, fixture["eventId"])
            self.assertIs(connector["readOnly"], True, fixture["eventId"])

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
        phone_like = re.compile(r"(?:\+?\d[\s-]?){10,}")

        for path in self.fixture_paths():
            text = path.read_text(encoding="utf-8")
            text_without_hashes = re.sub(r"sha256:[a-f0-9]{64}", "", text)
            lowered = text_without_hashes.lower()
            for term in forbidden_terms:
                self.assertNotIn(term, lowered, path.name)
            self.assertIsNone(email_like.search(text_without_hashes), path.name)
            self.assertIsNone(phone_like.search(text_without_hashes), path.name)

    def test_content_summary_and_evidence_are_distilled(self):
        for fixture in self.load_fixtures():
            self.assertLessEqual(len(fixture["contentSummary"]), 1000, fixture["eventId"])
            for evidence in fixture["evidence"]:
                self.assertLessEqual(len(evidence["excerpt"]), 280, fixture["eventId"])
                self.assertNotIn("@", evidence["excerpt"], fixture["eventId"])


if __name__ == "__main__":
    unittest.main()

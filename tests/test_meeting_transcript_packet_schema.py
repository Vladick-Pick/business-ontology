import json
from pathlib import Path
import unittest

from runtime.meeting_transcript_capture import validate_meeting_transcript_packet


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "meeting-transcript-packet.schema.json"
FIXTURE_DIR = REPO_ROOT / "evals" / "fixtures" / "meeting-transcript-packets"


class MeetingTranscriptPacketSchemaTests(unittest.TestCase):
    def test_schema_locks_runtime_packet_contract(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema.get("additionalProperties", True))
        self.assertEqual(
            set(schema["required"]),
            {
                "packetId",
                "jobId",
                "provider",
                "providerBotId",
                "businessId",
                "sourceId",
                "chatRef",
                "requestedBy",
                "observedAt",
                "transcriptPath",
                "summaryPath",
                "transcriptHash",
                "participants",
                "segments",
            },
        )
        self.assertEqual(schema["properties"]["provider"]["const"], "skribby")
        self.assertEqual(schema["properties"]["transcriptPath"]["const"], "transcript.md")
        self.assertEqual(schema["properties"]["summaryPath"]["const"], "summary.md")
        self.assertEqual(schema["properties"]["segments"]["minItems"], 1)
        self.assertIn("segmentId", schema["properties"]["segments"]["items"]["required"])

    def test_eval_packet_fixtures_validate_against_runtime_contract(self):
        fixture_paths = [
            FIXTURE_DIR / "skribby.finished.json",
            FIXTURE_DIR / "decision-and-fixation.json",
            FIXTURE_DIR / "noise-only.json",
        ]

        for path in fixture_paths:
            with self.subTest(path=path.name):
                packet = json.loads(path.read_text(encoding="utf-8"))
                validate_meeting_transcript_packet(packet)


if __name__ == "__main__":
    unittest.main()

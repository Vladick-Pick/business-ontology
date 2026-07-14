import json
from pathlib import Path
import stat
import tempfile
import unittest


class MeetingTranscriptCaptureTests(unittest.TestCase):
    def job(self):
        return {
            "job_id": "mtgrec-20260706-abcdef12",
            "provider": "skribby",
            "bot_id": "bot_123",
            "business_id": "biz-acquisition",
            "source_id": "src-meeting-skribby",
            "chat_ref": "-100123/77",
            "requested_by": "owner",
        }

    def bot_payload(self):
        return {
            "id": "bot_123",
            "finished_at": "2026-07-06T12:30:00Z",
            "participants": [{"name": "Owner"}, {"name": "Analyst"}],
            "transcript": [
                {
                    "start": 0,
                    "end": 4.2,
                    "speaker": 1,
                    "speaker_name": "Owner",
                    "confidence": 0.91,
                    "transcript": "The CRM remains the source of truth for acquisition handoff.",
                },
                {
                    "start": 5,
                    "end": 9,
                    "speaker": 2,
                    "speaker_name": "Analyst",
                    "confidence": 0.88,
                    "transcript": "Changing that owner requires review.",
                },
            ],
        }

    def test_capture_writes_full_transcript_summary_stub_and_packet_under_raw_meetings(self):
        from runtime.meeting_transcript_capture import capture_finished_bot

        with tempfile.TemporaryDirectory() as tmp:
            result = capture_finished_bot(
                self.job(),
                self.bot_payload(),
                Path(tmp),
                packet_id_factory=lambda: "mtgpk-20260706-abcdef12",
                observed_at="2026-07-06T12:31:00Z",
            )
            packet = json.loads(result.packet_path.read_text(encoding="utf-8"))
            transcript = result.transcript_path.read_text(encoding="utf-8")
            summary = result.summary_path.read_text(encoding="utf-8")

            self.assertEqual(
                result.packet_path,
                Path(tmp) / "meetings" / "mtgrec-20260706-abcdef12" / "packet.json",
            )
            self.assertEqual(stat.S_IMODE(Path(tmp).stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(result.packet_path.parent.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(result.packet_path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(result.transcript_path.stat().st_mode), 0o600)

        self.assertEqual(result.transcript_hash, packet["transcriptHash"])
        self.assertIn("The CRM remains the source of truth", transcript)
        self.assertIn("Changing that owner requires review", transcript)
        self.assertIn("pending meeting-transcript-ingest", summary)
        self.assertEqual(packet["packetId"], "mtgpk-20260706-abcdef12")
        self.assertEqual(packet["jobId"], "mtgrec-20260706-abcdef12")
        self.assertEqual(packet["provider"], "skribby")
        self.assertEqual(packet["providerBotId"], "bot_123")
        self.assertEqual(packet["businessId"], "biz-acquisition")
        self.assertEqual(packet["sourceId"], "src-meeting-skribby")
        self.assertEqual(packet["chatRef"], "-100123/77")
        self.assertEqual(packet["transcriptPath"], "transcript.md")
        self.assertEqual(packet["summaryPath"], "summary.md")
        self.assertEqual(packet["participants"], [{"name": "Owner", "source": "skribby"}, {"name": "Analyst", "source": "skribby"}])
        self.assertEqual(packet["segments"][0]["segmentId"], "seg-00001")
        self.assertEqual(packet["segments"][0]["speakerName"], "Owner")
        self.assertTrue(packet["transcriptHash"].startswith("sha256:"))

    def test_capture_expands_skribby_utterances_into_addressable_segments(self):
        from runtime.meeting_transcript_capture import capture_finished_bot

        payload = {
            "id": "bot_123",
            "finished_at": "2026-07-06T12:30:00Z",
            "participants": [{"name": "Owner"}],
            "transcript": [
                {
                    "start": 0,
                    "end": 30,
                    "transcript": "Large merged block.",
                    "utterances": [
                        {
                            "start": 1,
                            "end": 3,
                            "speaker": "owner",
                            "speaker_name": "Owner",
                            "confidence": 0.93,
                            "transcript": "CRM remains source of truth.",
                        },
                        {
                            "start": 4,
                            "end": 7,
                            "speaker": "analyst",
                            "speaker_name": "Analyst",
                            "confidence": 0.87,
                            "transcript": "Changing it needs owner review.",
                        },
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            result = capture_finished_bot(self.job(), payload, Path(tmp))
            packet = json.loads(result.packet_path.read_text(encoding="utf-8"))
            transcript = result.transcript_path.read_text(encoding="utf-8")

        self.assertEqual([segment["segmentId"] for segment in packet["segments"]], ["seg-00001", "seg-00002"])
        self.assertEqual(packet["segments"][0]["text"], "CRM remains source of truth.")
        self.assertEqual(packet["segments"][1]["text"], "Changing it needs owner review.")
        self.assertIn("[seg-00001] [1 - 3] Owner: CRM remains source of truth.", transcript)
        self.assertIn("[seg-00002] [4 - 7] Analyst: Changing it needs owner review.", transcript)

    def test_capture_refuses_empty_transcript_without_packet(self):
        from runtime.meeting_transcript_capture import EmptyTranscriptError, capture_finished_bot

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(EmptyTranscriptError):
                capture_finished_bot(self.job(), {"id": "bot_123", "transcript": []}, Path(tmp))
            packet_path = (
                Path(tmp)
                / "meetings"
                / "mtgrec-20260706-abcdef12"
                / "packet.json"
            )

        self.assertFalse(packet_path.exists())

    def test_capture_rejects_job_id_that_would_escape_raw_root(self):
        from runtime.meeting_transcript_capture import capture_finished_bot

        job = self.job()
        job["job_id"] = "../../../source-events"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            with self.assertRaisesRegex(ValueError, "job_id has invalid format"):
                capture_finished_bot(job, self.bot_payload(), root / "raw")

            self.assertFalse((root / "source-events").exists())

    def test_existing_summary_is_not_overwritten(self):
        from runtime.meeting_transcript_capture import capture_finished_bot

        with tempfile.TemporaryDirectory() as tmp:
            summary_path = (
                Path(tmp)
                / "meetings"
                / "mtgrec-20260706-abcdef12"
                / "summary.md"
            )
            summary_path.parent.mkdir(parents=True)
            summary_path.write_text("human edited summary\n", encoding="utf-8")

            capture_finished_bot(self.job(), self.bot_payload(), Path(tmp))

            self.assertEqual(summary_path.read_text(encoding="utf-8"), "human edited summary\n")

    def test_packet_validator_rejects_schema_shape_mismatch(self):
        from runtime.meeting_transcript_capture import validate_meeting_transcript_packet

        packet = {
            "packetId": "mtgpk-20260706-abcdef12",
            "jobId": "mtgrec-20260706-abcdef12",
            "provider": "skribby",
            "providerBotId": "bot_123",
            "businessId": "biz-acquisition",
            "sourceId": "src-meeting-skribby",
            "chatRef": "-100123/77",
            "requestedBy": "owner",
            "observedAt": "2026-07-06T12:31:00Z",
            "transcriptPath": "raw-transcript.txt",
            "summaryPath": "summary.md",
            "transcriptHash": "sha256:" + "a" * 64,
            "participants": [{"name": "Owner", "source": "skribby"}],
            "segments": [
                {
                    "segmentId": "seg-00001",
                    "start": 0,
                    "end": 1,
                    "speaker": "1",
                    "speakerName": "Owner",
                    "confidence": 0.9,
                    "text": "Decision.",
                }
            ],
        }

        with self.assertRaises(ValueError):
            validate_meeting_transcript_packet(packet)

    def test_packet_validator_rejects_empty_required_string_fields(self):
        from runtime.meeting_transcript_capture import validate_meeting_transcript_packet

        packet = {
            "packetId": "mtgpk-20260706-abcdef12",
            "jobId": "mtgrec-20260706-abcdef12",
            "provider": "skribby",
            "providerBotId": "bot_123",
            "businessId": "",
            "sourceId": "src-meeting-skribby",
            "chatRef": "dm-owner",
            "requestedBy": "owner",
            "observedAt": "2026-07-06T12:31:00Z",
            "transcriptPath": "transcript.md",
            "summaryPath": "summary.md",
            "transcriptHash": "sha256:" + "a" * 64,
            "participants": [{"name": "Owner", "source": "skribby"}],
            "segments": [
                {
                    "segmentId": "seg-00001",
                    "start": 0,
                    "end": 1,
                    "speaker": "1",
                    "speakerName": "Owner",
                    "confidence": 0.9,
                    "text": "Decision.",
                }
            ],
        }

        with self.assertRaises(ValueError):
            validate_meeting_transcript_packet(packet)


if __name__ == "__main__":
    unittest.main()

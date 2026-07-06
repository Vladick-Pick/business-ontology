from pathlib import Path
import sqlite3
import tempfile
import unittest


class MeetingRecordingStoreTests(unittest.TestCase):
    def make_store(self, tmp):
        from runtime.meeting_recording_store import MeetingRecordingStore

        store = MeetingRecordingStore.connect(Path(tmp) / "state" / "recordings.sqlite3")
        store.initialize()
        self.addCleanup(store.close)
        return store

    def requested_job(self, job_id="mtgrec-20260706-abcdef12"):
        return {
            "job_id": job_id,
            "provider": "skribby",
            "meeting_url_hash": "sha256:" + "a" * 64,
            "meeting_url_display": "https://zoom.us/j/123456789?pwd=[redacted]",
            "service": "zoom",
            "business_id": "biz-acquisition",
            "source_id": "src-meeting-skribby",
            "chat_ref": "-100123/77",
            "requested_by": "owner",
            "webhook_nonce_hash": "sha256:" + "b" * 64,
            "provider_payload": {"request": "redacted"},
        }

    def test_initialize_creates_recording_jobs_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            self.assertEqual(store.table_count("meeting_recording_jobs"), 0)

    def test_create_requested_job_persists_without_raw_meeting_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            store.create_requested_job(self.requested_job())
            job = store.get_job("mtgrec-20260706-abcdef12")

        self.assertEqual(job["status"], "requested")
        self.assertEqual(job["meeting_url_display"], "https://zoom.us/j/123456789?pwd=[redacted]")
        self.assertNotIn("raw-secret", str(job))

    def test_transition_requested_to_bot_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            store.create_requested_job(self.requested_job())

            store.mark_bot_created(
                "mtgrec-20260706-abcdef12",
                bot_id="bot_123",
                provider_payload={"id": "bot_123", "meeting_url": "https://zoom.us/j/123?pwd=[redacted]"},
            )
            job = store.get_job("mtgrec-20260706-abcdef12")

        self.assertEqual(job["status"], "bot_created")
        self.assertEqual(job["bot_id"], "bot_123")

    def test_finished_webhook_records_receive_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            store.create_requested_job(self.requested_job())
            store.mark_bot_created("mtgrec-20260706-abcdef12", bot_id="bot_123", provider_payload={})

            store.mark_finished_received(
                "mtgrec-20260706-abcdef12",
                webhook_payload={"type": "status_update", "data": {"new_status": "finished"}},
            )
            job = store.get_job("mtgrec-20260706-abcdef12")

        self.assertEqual(job["status"], "finished_received")
        self.assertEqual(job["completion_source"], "webhook")
        self.assertRegex(job["webhook_received_at"], r"^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_recovery_records_provider_finished_without_webhook_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            store.create_requested_job(self.requested_job())
            store.mark_bot_created("mtgrec-20260706-abcdef12", bot_id="bot_123", provider_payload={})

            store.mark_transcript_recovered(
                "mtgrec-20260706-abcdef12",
                provider_payload={"id": "bot_123", "status": "finished"},
                provider_finished_at="2026-07-06T12:50:56Z",
            )
            job = store.get_job("mtgrec-20260706-abcdef12")

        self.assertEqual(job["status"], "transcript_fetched")
        self.assertEqual(job["completion_source"], "recovery")
        self.assertEqual(job["provider_finished_at"], "2026-07-06T12:50:56Z")
        self.assertIsNone(job["webhook_received_at"])

    def test_mark_wakeup_delivered_clears_pending_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            store.create_requested_job(self.requested_job())
            store.mark_bot_created("mtgrec-20260706-abcdef12", bot_id="bot_123", provider_payload={})
            store.mark_finished_received(
                "mtgrec-20260706-abcdef12",
                webhook_payload={"type": "status_update", "data": {"new_status": "finished"}},
            )
            store.mark_transcript_fetched(
                "mtgrec-20260706-abcdef12",
                provider_payload={"id": "bot_123"},
            )
            store.mark_packet_ready(
                "mtgrec-20260706-abcdef12",
                packet_path="/tmp/packet.json",
                transcript_hash="sha256:" + "c" * 64,
                wakeup_pending=True,
            )

            store.mark_wakeup_delivered("mtgrec-20260706-abcdef12")
            job = store.get_job("mtgrec-20260706-abcdef12")

        self.assertEqual(job["status"], "packet_ready")
        self.assertEqual(job["wakeup_pending"], 0)

    def test_transition_requested_to_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            store.create_requested_job(self.requested_job())

            store.mark_failed(
                "mtgrec-20260706-abcdef12",
                error_code="provider-error",
                error_message="Skribby request failed",
            )
            job = store.get_job("mtgrec-20260706-abcdef12")

        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error_code"], "provider-error")
        self.assertEqual(job["error_message"], "Skribby request failed")

    def test_invalid_state_transition_raises_value_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            store.create_requested_job(self.requested_job())
            store.mark_bot_created("mtgrec-20260706-abcdef12", bot_id="bot_123", provider_payload={})

            with self.assertRaises(ValueError):
                store.mark_bot_created("mtgrec-20260706-abcdef12", bot_id="bot_456", provider_payload={})

    def test_duplicate_job_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            store.create_requested_job(self.requested_job())

            with self.assertRaises(sqlite3.IntegrityError):
                store.create_requested_job(self.requested_job())

    def test_table_count_rejects_non_identifier_table_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            with self.assertRaises(ValueError):
                store.table_count("meeting_recording_jobs; DROP TABLE meeting_recording_jobs")


if __name__ == "__main__":
    unittest.main()

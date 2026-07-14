import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import URLError
from unittest import mock


class FakeSkribbyClient:
    def __init__(self, bot_payload=None):
        self.create_payloads = []
        self.fetch_bot_ids = []
        self.bot_payload = bot_payload or {
            "id": "bot_123",
            "finished_at": "2026-07-06T12:30:00Z",
            "participants": [{"name": "Owner"}],
            "transcript": [
                {
                    "start": 0,
                    "end": 3,
                    "speaker": 1,
                    "speaker_name": "Owner",
                    "confidence": 0.9,
                    "transcript": "The CRM remains source of truth.",
                }
            ],
        }

    def create_bot(self, payload):
        self.create_payloads.append(payload)
        return {"id": "bot_123", "status": "scheduled"}

    def fetch_bot(self, bot_id):
        self.fetch_bot_ids.append(bot_id)
        return self.bot_payload


class FlakyFetchSkribbyClient(FakeSkribbyClient):
    def __init__(self):
        super().__init__()
        self.fail_next_fetch = True

    def fetch_bot(self, bot_id):
        self.fetch_bot_ids.append(bot_id)
        if self.fail_next_fetch:
            self.fail_next_fetch = False
            raise RuntimeError("temporary provider failure")
        return self.bot_payload


class MeetingRecordingWebhookTests(unittest.TestCase):
    def make_runtime_and_app(self, tmp, client=None, wakeup_url=None, wakeup_token=None):
        from runtime.meeting_recording_service import (
            MeetingRecordingConfig,
            MeetingRecordingRuntime,
            build_app,
        )
        from runtime.meeting_recording_store import MeetingRecordingStore

        store = MeetingRecordingStore.connect(Path(tmp) / "recordings.sqlite3")
        store.initialize()
        self.addCleanup(store.close)
        client = client or FakeSkribbyClient()
        runtime = MeetingRecordingRuntime(
            MeetingRecordingConfig(
                public_base_url="https://recorder.example",
                raw_source_root=Path(tmp) / "workspace" / "raw",
                openclaw_wakeup_url=wakeup_url,
                openclaw_hooks_token=wakeup_token,
            ),
            store=store,
            skribby_client=client,
            id_factory=lambda: "mtgrec-20260706-abcdef12",
        )
        runtime.order_recording(
            {
                "meeting_url": "https://zoom.us/j/123456789",
                "business_id": "biz-acquisition",
                "source_id": "src-meeting-skribby",
                "chat_ref": "-100123/77",
                "requested_by": "owner",
            }
        )
        self.webhook_nonce = client.create_payloads[0]["custom_metadata"]["webhook_nonce"]
        return runtime, build_app(runtime)

    def webhook(
        self,
        *,
        status="finished",
        job_id="mtgrec-20260706-abcdef12",
        bot_id="bot_123",
        webhook_nonce=None,
    ):
        return {
            "bot_id": bot_id,
            "type": "status_update",
            "data": {"new_status": status},
            "custom_metadata": {
                "job_id": job_id,
                "webhook_nonce": self.webhook_nonce if webhook_nonce is None else webhook_nonce,
            },
        }

    def post_webhook(self, app, payload):
        return app.handle_post_skribby(
            json.dumps(payload).encode("utf-8"),
            {"content-type": "application/json"},
        )

    def test_non_finished_webhook_is_accepted_without_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeSkribbyClient()
            runtime, app = self.make_runtime_and_app(tmp, client)

            status, _, body = self.post_webhook(app, self.webhook(status="recording"))
            job = runtime.store.get_job("mtgrec-20260706-abcdef12")

        self.assertEqual(status, 202)
        self.assertEqual(json.loads(body.decode("utf-8"))["status"], "ignored")
        self.assertEqual(client.fetch_bot_ids, [])
        self.assertEqual(job["status"], "bot_created")
        self.assertNotIn(self.webhook_nonce, json.dumps(job, sort_keys=True))

    def test_finished_webhook_fetches_bot_captures_packet_and_marks_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeSkribbyClient()
            runtime, app = self.make_runtime_and_app(tmp, client)

            status, _, body = self.post_webhook(app, self.webhook())
            response = json.loads(body.decode("utf-8"))
            job = runtime.store.get_job("mtgrec-20260706-abcdef12")
            packet_exists = Path(job["packet_path"]).is_file()
            packet_path = Path(job["packet_path"])

        self.assertEqual(status, 200)
        self.assertEqual(client.fetch_bot_ids, ["bot_123"])
        self.assertEqual(job["status"], "packet_ready")
        self.assertEqual(job["wakeup_pending"], 1)
        self.assertRegex(job["webhook_received_at"], r"^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertTrue(packet_exists)
        self.assertEqual(
            packet_path,
            Path(tmp) / "workspace" / "raw" / "meetings" / "mtgrec-20260706-abcdef12" / "packet.json",
        )
        self.assertTrue(response["packet_path"].endswith("packet.json"))
        self.assertTrue(job["transcript_hash"].startswith("sha256:"))
        self.assertNotIn("The CRM remains source of truth.", json.dumps(job, sort_keys=True))

    def test_duplicate_finished_webhook_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeSkribbyClient()
            runtime, app = self.make_runtime_and_app(tmp, client)

            first_status, _, _ = self.post_webhook(app, self.webhook())
            second_status, _, body = self.post_webhook(app, self.webhook())

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(client.fetch_bot_ids, ["bot_123"])
        self.assertEqual(json.loads(body.decode("utf-8"))["status"], "packet_ready")

    def test_finished_webhook_retry_recovers_after_fetch_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FlakyFetchSkribbyClient()
            runtime, app = self.make_runtime_and_app(tmp, client)

            first_status, _, _ = self.post_webhook(app, self.webhook())
            first_job = runtime.store.get_job("mtgrec-20260706-abcdef12")
            second_status, _, body = self.post_webhook(app, self.webhook())
            second_job = runtime.store.get_job("mtgrec-20260706-abcdef12")

        self.assertEqual(first_status, 502)
        self.assertEqual(first_job["status"], "finished_received")
        self.assertEqual(second_status, 200)
        self.assertEqual(second_job["status"], "packet_ready")
        self.assertEqual(client.fetch_bot_ids, ["bot_123", "bot_123"])
        self.assertEqual(json.loads(body.decode("utf-8"))["status"], "packet_ready")

    def test_bot_mismatch_returns_409_without_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeSkribbyClient()
            runtime, app = self.make_runtime_and_app(tmp, client)

            status, _, body = self.post_webhook(app, self.webhook(bot_id="bot_other"))
            job = runtime.store.get_job("mtgrec-20260706-abcdef12")

        self.assertEqual(status, 409)
        self.assertIn("bot mismatch", body.decode("utf-8"))
        self.assertEqual(client.fetch_bot_ids, [])
        self.assertEqual(job["status"], "bot_created")

    def test_webhook_missing_or_wrong_nonce_returns_401_without_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeSkribbyClient()
            runtime, app = self.make_runtime_and_app(tmp, client)

            missing = self.webhook()
            del missing["custom_metadata"]["webhook_nonce"]
            missing_status, _, _ = self.post_webhook(app, missing)
            wrong_status, _, body = self.post_webhook(app, self.webhook(webhook_nonce="wrong"))
            job = runtime.store.get_job("mtgrec-20260706-abcdef12")

        self.assertEqual(missing_status, 401)
        self.assertEqual(wrong_status, 401)
        self.assertIn("webhook authentication failed", body.decode("utf-8"))
        self.assertEqual(client.fetch_bot_ids, [])
        self.assertEqual(job["status"], "bot_created")

    def test_unknown_job_returns_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, app = self.make_runtime_and_app(tmp)

            status, _, body = self.post_webhook(app, self.webhook(job_id="mtgrec-unknown"))

        self.assertEqual(status, 404)
        self.assertIn("unknown job", body.decode("utf-8"))

    def test_empty_transcript_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeSkribbyClient(bot_payload={"id": "bot_123", "transcript": []})
            runtime, app = self.make_runtime_and_app(tmp, client)

            status, _, body = self.post_webhook(app, self.webhook())
            job = runtime.store.get_job("mtgrec-20260706-abcdef12")

        self.assertEqual(status, 422)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error_code"], "empty-transcript")
        self.assertNotIn("packet_path", json.loads(body.decode("utf-8")))

    def test_wakeup_failure_keeps_packet_ready_with_pending_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeSkribbyClient()
            runtime, app = self.make_runtime_and_app(
                tmp,
                client,
                wakeup_url="https://openclaw.example/hooks/meeting-process",
                wakeup_token="hook-token",
            )

            with mock.patch("urllib.request.urlopen", side_effect=URLError("connection refused")):
                status, _, body = self.post_webhook(app, self.webhook())
            job = runtime.store.get_job("mtgrec-20260706-abcdef12")

        self.assertEqual(status, 200)
        self.assertEqual(job["status"], "packet_ready")
        self.assertEqual(job["wakeup_pending"], 1)
        self.assertTrue(json.loads(body.decode("utf-8"))["wakeup_pending"])


if __name__ == "__main__":
    unittest.main()

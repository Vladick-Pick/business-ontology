import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


class FakeSkribbyClient:
    def __init__(self, response=None, error=None):
        self.response = response or {"id": "bot_123", "status": "scheduled"}
        self.error = error
        self.payloads = []

    def create_bot(self, payload):
        self.payloads.append(payload)
        if self.error:
            raise self.error
        return self.response


class MeetingRecordingServiceTests(unittest.TestCase):
    def make_runtime(self, tmp, client=None):
        from runtime.meeting_recording_service import MeetingRecordingConfig, MeetingRecordingRuntime
        from runtime.meeting_recording_store import MeetingRecordingStore

        store = MeetingRecordingStore.connect(Path(tmp) / "recordings.sqlite3")
        store.initialize()
        self.addCleanup(store.close)
        return MeetingRecordingRuntime(
            MeetingRecordingConfig(
                public_base_url="https://recorder.example",
                bot_name="Ontology Agent recorder",
                transcription_model="whisper",
                default_stop_options={"waiting_room_timeout": 900},
            ),
            store=store,
            skribby_client=client or FakeSkribbyClient(),
            id_factory=lambda: "mtgrec-20260706-abcdef12",
        )

    def valid_request(self, meeting_url="https://zoom.us/j/123456789?pwd=raw-secret"):
        return {
            "meeting_url": meeting_url,
            "business_id": "biz-acquisition",
            "source_id": "src-meeting-skribby",
            "chat_ref": "-100123/77",
            "requested_by": "owner",
            "agent_mentioned": True,
            "return_channel": "telegram:-100123",
        }

    def test_order_recording_creates_job_and_sends_skribby_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeSkribbyClient()
            runtime = self.make_runtime(tmp, client)

            result = runtime.order_recording(self.valid_request())
            job = runtime.store.get_job("mtgrec-20260706-abcdef12")

        self.assertEqual(
            result,
            {
                "job_id": "mtgrec-20260706-abcdef12",
                "provider": "skribby",
                "bot_id": "bot_123",
                "status": "bot_created",
            },
        )
        self.assertEqual(job["status"], "bot_created")
        self.assertEqual(job["service"], "zoom")
        self.assertNotIn("raw-secret", json.dumps(job, sort_keys=True))
        payload = client.payloads[0]
        self.assertEqual(payload["meeting_url"], "https://zoom.us/j/123456789?pwd=raw-secret")
        self.assertEqual(payload["webhook_url"], "https://recorder.example/webhooks/skribby")
        self.assertEqual(payload["custom_metadata"]["job_id"], "mtgrec-20260706-abcdef12")
        self.assertEqual(payload["custom_metadata"]["business_id"], "biz-acquisition")
        self.assertEqual(payload["custom_metadata"]["source_id"], "src-meeting-skribby")
        self.assertEqual(payload["custom_metadata"]["chat_ref"], "-100123/77")

    def test_order_recording_supports_zoom_gmeet_and_teams(self):
        from runtime.meeting_recording_service import infer_meeting_service

        self.assertEqual(infer_meeting_service("https://zoom.us/j/123"), "zoom")
        self.assertEqual(infer_meeting_service("https://zoom.com/j/123"), "zoom")
        self.assertEqual(infer_meeting_service("https://meet.google.com/abc-defg-hij"), "gmeet")
        self.assertEqual(infer_meeting_service("https://teams.microsoft.com/l/meetup-join/abc"), "teams")

    def test_order_recording_rejects_missing_required_field(self):
        from runtime.meeting_recording_service import ValidationError

        with tempfile.TemporaryDirectory() as tmp:
            runtime = self.make_runtime(tmp)
            request = self.valid_request()
            del request["business_id"]

            with self.assertRaises(ValidationError) as raised:
                runtime.order_recording(request)

        self.assertIn("business_id", str(raised.exception))

    def test_order_recording_rejects_unsupported_url(self):
        from runtime.meeting_recording_service import ValidationError

        with tempfile.TemporaryDirectory() as tmp:
            runtime = self.make_runtime(tmp)

            with self.assertRaises(ValidationError):
                runtime.order_recording(self.valid_request("https://example.com/room"))

    def test_provider_error_marks_job_failed_without_secret_or_raw_url(self):
        from runtime.skribby_client import SkribbyHTTPError
        from runtime.meeting_recording_service import ProviderCreateError

        with tempfile.TemporaryDirectory() as tmp:
            runtime = self.make_runtime(tmp, FakeSkribbyClient(error=SkribbyHTTPError(401)))

            with self.assertRaises(ProviderCreateError) as raised:
                runtime.order_recording(self.valid_request())
            job = runtime.store.get_job("mtgrec-20260706-abcdef12")

        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error_code"], "provider-create-failed")
        self.assertNotIn("raw-secret", str(raised.exception))
        self.assertNotIn("raw-secret", json.dumps(job, sort_keys=True))

    def test_stored_job_redacts_all_meeting_url_query_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self.make_runtime(tmp)

            runtime.order_recording(self.valid_request("https://zoom.us/j/123456789?foo=raw-secret"))
            job = runtime.store.get_job("mtgrec-20260706-abcdef12")

        self.assertEqual(job["meeting_url_display"], "https://zoom.us/j/123456789?foo=[redacted]")
        self.assertNotIn("raw-secret", json.dumps(job, sort_keys=True))

    def test_post_recordings_http_handler_returns_json(self):
        from runtime.meeting_recording_service import build_app

        with tempfile.TemporaryDirectory() as tmp:
            runtime = self.make_runtime(tmp)
            app = build_app(runtime)

            status, headers, body = app.handle_post_recordings(
                json.dumps(self.valid_request()).encode("utf-8"),
                {"content-type": "application/json"},
            )

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(json.loads(body.decode("utf-8"))["status"], "bot_created")

    def test_post_recordings_rejects_non_json_request(self):
        from runtime.meeting_recording_service import build_app

        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(self.make_runtime(tmp))

            status, _, body = app.handle_post_recordings(b"{}", {"content-type": "text/plain"})

        self.assertEqual(status, 415)
        self.assertIn("application/json", body.decode("utf-8"))

    def test_http_handler_never_echoes_secret_query_token(self):
        from runtime.meeting_recording_service import build_app

        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(self.make_runtime(tmp))
            payload = self.valid_request("https://example.com/room?token=raw-secret")

            status, _, body = app.handle_post_recordings(
                json.dumps(payload).encode("utf-8"),
                {"content-type": "application/json"},
            )

        self.assertEqual(status, 400)
        self.assertNotIn("raw-secret", body.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()

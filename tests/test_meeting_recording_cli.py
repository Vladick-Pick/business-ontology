import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from urllib.error import HTTPError, URLError
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "meeting_recording_cli.py"


def load_script():
    spec = importlib.util.spec_from_file_location("meeting_recording_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class MeetingRecordingCliTests(unittest.TestCase):
    def test_order_posts_recording_request_and_prints_response(self):
        script = load_script()
        stdout = io.StringIO()
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse(
                {
                    "job_id": "mtgrec-20260706-abcdef12",
                    "provider": "skribby",
                    "bot_id": "bot_123",
                    "status": "bot_created",
                }
            )

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen), redirect_stdout(stdout):
            code = script.main(
                [
                    "order",
                    "--service-url",
                    "https://recorder.example",
                    "--meeting-url",
                    "https://zoom.us/j/123456789",
                    "--business-id",
                    "biz-acquisition",
                    "--source-id",
                    "src-meeting-skribby",
                    "--chat-ref",
                    "-100123/77",
                    "--requested-by",
                    "owner",
                    "--agent-mentioned",
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(captured["url"], "https://recorder.example/recordings")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["body"]["chat_ref"], "-100123/77")
        self.assertTrue(captured["body"]["agent_mentioned"])
        self.assertEqual(captured["timeout"], 30)
        self.assertEqual(json.loads(stdout.getvalue())["bot_id"], "bot_123")

    def test_order_rejected_by_runtime_returns_exit_3_without_secret(self):
        script = load_script()
        stderr = io.StringIO()
        response = io.BytesIO(b'{"error":"unsupported meeting URL"}')
        error = HTTPError("https://recorder.example/recordings", 400, "Bad Request", {}, response)

        with mock.patch("urllib.request.urlopen", side_effect=error), redirect_stderr(stderr):
            code = script.main(
                [
                    "order",
                    "--service-url",
                    "https://recorder.example",
                    "--meeting-url",
                    "https://example.com/room?token=raw-secret",
                    "--business-id",
                    "biz-acquisition",
                    "--source-id",
                    "src-meeting-skribby",
                    "--chat-ref",
                    "dm/1",
                    "--requested-by",
                    "owner",
                ]
            )

        self.assertEqual(code, 3)
        self.assertIn("unsupported meeting URL", stderr.getvalue())
        self.assertNotIn("raw-secret", stderr.getvalue())

    def test_order_rejected_by_runtime_redacts_secret_from_error_body(self):
        script = load_script()
        stderr = io.StringIO()
        response = io.BytesIO(b'{"error":"bad https://example.com?token=raw-secret"}')
        error = HTTPError("https://recorder.example/recordings", 400, "Bad Request", {}, response)

        with mock.patch("urllib.request.urlopen", side_effect=error), redirect_stderr(stderr):
            code = script.main(
                [
                    "order",
                    "--service-url",
                    "https://recorder.example",
                    "--meeting-url",
                    "https://example.com/room?token=raw-secret",
                    "--business-id",
                    "biz-acquisition",
                    "--source-id",
                    "src-meeting-skribby",
                    "--chat-ref",
                    "dm/1",
                    "--requested-by",
                    "owner",
                ]
            )

        self.assertEqual(code, 3)
        self.assertNotIn("raw-secret", stderr.getvalue())
        self.assertIn("[redacted]", stderr.getvalue())

    def test_order_unreachable_runtime_returns_exit_4(self):
        script = load_script()
        stderr = io.StringIO()

        with mock.patch("urllib.request.urlopen", side_effect=URLError("connection refused")), redirect_stderr(stderr):
            code = script.main(
                [
                    "order",
                    "--service-url",
                    "https://recorder.example",
                    "--meeting-url",
                    "https://zoom.us/j/123456789",
                    "--business-id",
                    "biz-acquisition",
                    "--source-id",
                    "src-meeting-skribby",
                    "--chat-ref",
                    "dm/1",
                    "--requested-by",
                    "owner",
                ]
            )

        self.assertEqual(code, 4)
        self.assertIn("unreachable", stderr.getvalue())

    def test_recover_fetches_provider_and_marks_packet_ready_without_webhook_timestamp(self):
        from runtime.meeting_recording_service import hash_meeting_url, hash_secret, sanitize_url
        from runtime.meeting_recording_store import MeetingRecordingStore

        script = load_script()
        stdout = io.StringIO()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "recordings.sqlite3"
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "runtime-config.json").write_text(
                json.dumps({"raw_source_root": "raw"}),
                encoding="utf-8",
            )
            with MeetingRecordingStore.connect(db_path) as store:
                store.initialize()
                store.create_requested_job(
                    {
                        "job_id": "mtgrec-20260706-recover",
                        "provider": "skribby",
                        "meeting_url_hash": hash_meeting_url("https://zoom.us/j/123?pwd=secret"),
                        "meeting_url_display": sanitize_url("https://zoom.us/j/123?pwd=secret"),
                        "service": "zoom",
                        "business_id": "biz-acquisition",
                        "source_id": "src-meeting-skribby",
                        "chat_ref": "dm-owner",
                        "requested_by": "owner",
                        "webhook_nonce_hash": hash_secret("nonce"),
                        "provider_payload": {},
                    }
                )
                store.mark_bot_created("mtgrec-20260706-recover", bot_id="bot_123", provider_payload={})

            bot_payload = {
                "id": "bot_123",
                "status": "finished",
                "finished_at": "2026-07-06T12:50:56Z",
                "participants": [{"name": "Owner"}],
                "transcript": [
                    {
                        "start": 0,
                        "end": 10,
                        "utterances": [
                            {
                                "start": 1,
                                "end": 2,
                                "speaker": "owner",
                                "speaker_name": "Owner",
                                "confidence": 0.9,
                                "transcript": "CRM remains source of truth.",
                            }
                        ],
                    }
                ],
            }

            with mock.patch.dict("os.environ", {"SKRIBBY_API_KEY": "sk_test_secret"}, clear=True), mock.patch(
                "runtime.skribby_client.SkribbyClient.fetch_bot",
                return_value=bot_payload,
            ), redirect_stdout(stdout):
                code = script.main(
                    [
                        "recover",
                        "--db",
                        str(db_path),
                        "--workspace",
                        str(workspace),
                        "--job-id",
                        "mtgrec-20260706-recover",
                    ]
                )

            result = json.loads(stdout.getvalue())
            with MeetingRecordingStore.connect(db_path) as store:
                store.initialize()
                job = store.get_job("mtgrec-20260706-recover")
                packet_exists = Path(job["packet_path"]).is_file()
                packet_path = Path(job["packet_path"])

        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "packet_ready")
        self.assertEqual(result["completion_source"], "recovery")
        self.assertEqual(result["segments_count"], 1)
        self.assertEqual(job["completion_source"], "recovery")
        self.assertEqual(job["provider_finished_at"], "2026-07-06T12:50:56Z")
        self.assertIsNone(job["webhook_received_at"])
        self.assertTrue(packet_exists)
        self.assertEqual(
            packet_path,
            (workspace / "raw" / "meetings" / "mtgrec-20260706-recover" / "packet.json").resolve(),
        )

    def test_retry_wakeup_posts_packet_to_openclaw_hook_and_clears_pending(self):
        from runtime.meeting_recording_store import MeetingRecordingStore

        script = load_script()
        stdout = io.StringIO()
        captured = {}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "recordings.sqlite3"
            packet_path = root / "packet.json"
            packet_path.write_text("{}", encoding="utf-8")
            with MeetingRecordingStore.connect(db_path) as store:
                store.initialize()
                store.create_requested_job(self._requested_job("mtgrec-20260706-wakeup"))
                store.mark_bot_created("mtgrec-20260706-wakeup", bot_id="bot_123", provider_payload={})
                store.mark_finished_received(
                    "mtgrec-20260706-wakeup",
                    webhook_payload={"type": "status_update", "data": {"new_status": "finished"}},
                )
                store.mark_transcript_fetched(
                    "mtgrec-20260706-wakeup",
                    provider_payload={"id": "bot_123"},
                )
                store.mark_packet_ready(
                    "mtgrec-20260706-wakeup",
                    packet_path=str(packet_path),
                    transcript_hash="sha256:" + "d" * 64,
                    wakeup_pending=True,
                )

            def fake_urlopen(request, timeout):
                captured["url"] = request.full_url
                captured["headers"] = dict(request.header_items())
                captured["body"] = json.loads(request.data.decode("utf-8"))
                return FakeResponse({"ok": True})

            with mock.patch.dict(
                "os.environ",
                {
                    "OPENCLAW_MEETING_PROCESS_HOOK_URL": "https://openclaw.example/hooks/meeting-process",
                    "OPENCLAW_HOOKS_TOKEN": "hook-token",
                },
                clear=True,
            ), mock.patch("urllib.request.urlopen", side_effect=fake_urlopen), redirect_stdout(stdout):
                code = script.main(
                    [
                        "retry-wakeup",
                        "--db",
                        str(db_path),
                        "--job-id",
                        "mtgrec-20260706-wakeup",
                    ]
                )

            result = json.loads(stdout.getvalue())
            with MeetingRecordingStore.connect(db_path) as store:
                store.initialize()
                job = store.get_job("mtgrec-20260706-wakeup")

        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "wakeup_delivered")
        self.assertEqual(job["wakeup_pending"], 0)
        self.assertEqual(captured["url"], "https://openclaw.example/hooks/meeting-process")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer hook-token")
        self.assertIn(str(packet_path), captured["body"]["message"])

    def _requested_job(self, job_id):
        return {
            "job_id": job_id,
            "provider": "skribby",
            "meeting_url_hash": "sha256:" + "a" * 64,
            "meeting_url_display": "https://zoom.us/j/123?pwd=[redacted]",
            "service": "zoom",
            "business_id": "biz-acquisition",
            "source_id": "src-meeting-skribby",
            "chat_ref": "dm-owner",
            "requested_by": "owner",
            "webhook_nonce_hash": "sha256:" + "b" * 64,
            "provider_payload": {},
        }


if __name__ == "__main__":
    unittest.main()

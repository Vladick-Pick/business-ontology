import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "skribby_order_bot.py"


def load_script():
    spec = importlib.util.spec_from_file_location("skribby_order_bot", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SkribbyOrderBotTests(unittest.TestCase):
    def test_dry_run_prints_payload_with_metadata_without_http(self):
        script = load_script()
        stdout = io.StringIO()

        with redirect_stdout(stdout), mock.patch("urllib.request.urlopen") as urlopen:
            code = script.main(
                [
                    "--meeting-url",
                    "https://zoom.us/j/123456789",
                    "--bot-name",
                    "Ontology Agent recorder",
                    "--webhook-url",
                    "https://gateway.example/hooks/skribby",
                    "--business-id",
                    "biz-acquisition",
                    "--chat-id",
                    "-100123",
                    "--source-id",
                    "tg-group-acquisition",
                    "--telegram-message-ref",
                    "-100123/77",
                    "--dry-run",
                ]
            )

        self.assertEqual(code, 0)
        urlopen.assert_not_called()
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["meeting_url"], "https://zoom.us/j/123456789")
        self.assertEqual(payload["service"], "zoom")
        self.assertEqual(payload["transcription_model"], "whisper")
        self.assertEqual(payload["webhook_url"], "https://gateway.example/hooks/skribby")
        self.assertEqual(
            payload["custom_metadata"],
            {
                "business_id": "biz-acquisition",
                "chat_id": "-100123",
                "source_id": "tg-group-acquisition",
                "telegram_message_ref": "-100123/77",
            },
        )

    def test_dry_run_redacts_webhook_query_token(self):
        script = load_script()
        stdout = io.StringIO()

        with redirect_stdout(stdout), mock.patch("urllib.request.urlopen") as urlopen:
            code = script.main(
                [
                    "--meeting-url",
                    "https://zoom.us/j/123456789",
                    "--bot-name",
                    "Ontology Agent recorder",
                    "--webhook-url",
                    (
                        "https://gateway.example/hooks/skribby?"
                        "token=secret-token&access_token=access-secret&api_key=api-secret&chat=123"
                    ),
                    "--dry-run",
                ]
            )

        self.assertEqual(code, 0)
        urlopen.assert_not_called()
        payload = json.loads(stdout.getvalue())
        self.assertEqual(
            payload["webhook_url"],
            (
                "https://gateway.example/hooks/skribby?"
                "token=%5Bredacted%5D&access_token=%5Bredacted%5D&api_key=%5Bredacted%5D&chat=123"
            ),
        )
        self.assertNotIn("secret-token", stdout.getvalue())
        self.assertNotIn("access-secret", stdout.getvalue())
        self.assertNotIn("api-secret", stdout.getvalue())

    def test_service_detection_supports_zoom_meet_and_teams(self):
        script = load_script()

        self.assertEqual(script.infer_service("https://zoom.us/j/123456789"), "zoom")
        self.assertEqual(script.infer_service("https://meet.google.com/abc-defg-hij"), "gmeet")
        self.assertEqual(script.infer_service("https://teams.microsoft.com/l/meetup-join/abc"), "teams")

    def test_live_order_refuses_legacy_path_without_network(self):
        script = load_script()
        stderr = io.StringIO()

        with mock.patch.dict("os.environ", {"SKRIBBY_API_KEY": "test-secret-value"}, clear=True), redirect_stderr(
            stderr
        ), mock.patch(
            "urllib.request.urlopen"
        ) as urlopen:
            code = script.main(
                [
                    "--meeting-url",
                    "https://meet.google.com/abc-defg-hij",
                    "--bot-name",
                    "Ontology Agent recorder",
                    "--webhook-url",
                    "https://gateway.example/hooks/skribby",
                ]
            )

        self.assertEqual(code, 2)
        urlopen.assert_not_called()
        self.assertIn("meeting_recording_cli.py", stderr.getvalue())
        self.assertNotIn("test-secret-value", stderr.getvalue())

    def test_unknown_meeting_url_requires_service_override(self):
        script = load_script()
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            code = script.main(
                [
                    "--meeting-url",
                    "https://example.com/meeting/123",
                    "--bot-name",
                    "Ontology Agent recorder",
                    "--webhook-url",
                    "https://gateway.example/hooks/skribby",
                    "--dry-run",
                ]
            )

        self.assertEqual(code, 2)
        self.assertIn("--service", stderr.getvalue())

    def test_live_order_with_service_override_still_refuses_legacy_path(self):
        script = load_script()
        stderr = io.StringIO()

        with mock.patch.dict("os.environ", {"SKRIBBY_API_KEY": "test-secret-value"}, clear=True), mock.patch(
            "urllib.request.urlopen"
        ) as urlopen, redirect_stderr(stderr):
            code = script.main(
                [
                    "--meeting-url",
                    "https://meet.google.com/abc-defg-hij",
                    "--bot-name",
                    "Ontology Agent recorder",
                    "--webhook-url",
                    "https://gateway.example/hooks/skribby",
                    "--service",
                    "gmeet",
                ]
            )

        self.assertEqual(code, 2)
        urlopen.assert_not_called()
        self.assertIn("dry-run only", stderr.getvalue())
        self.assertNotIn("test-secret-value", stderr.getvalue())

    def test_non_default_api_url_requires_explicit_override(self):
        script = load_script()
        stderr = io.StringIO()

        with mock.patch.dict("os.environ", {"SKRIBBY_API_KEY": "test-secret-value"}, clear=True), mock.patch(
            "urllib.request.urlopen"
        ) as urlopen, redirect_stderr(stderr):
            code = script.main(
                [
                    "--meeting-url",
                    "https://meet.google.com/abc-defg-hij",
                    "--bot-name",
                    "Ontology Agent recorder",
                    "--webhook-url",
                    "https://gateway.example/hooks/skribby",
                    "--service",
                    "gmeet",
                    "--api-url",
                    "https://example.invalid/api/v1/bot",
                ]
            )

        self.assertEqual(code, 2)
        urlopen.assert_not_called()
        self.assertIn("--allow-non-default-api-url", stderr.getvalue())

    def test_help_exits_zero(self):
        script = load_script()
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as raised:
            script.main(["--help"])

        self.assertEqual(raised.exception.code, 0)

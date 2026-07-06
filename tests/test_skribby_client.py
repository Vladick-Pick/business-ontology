import io
import json
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")


class SkribbyClientTests(unittest.TestCase):
    def test_create_bot_posts_expected_payload_and_headers(self):
        from runtime.skribby_client import DEFAULT_API_URL, SkribbyClient

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse({"id": "bot_123", "status": "scheduled"})

        client = SkribbyClient(api_key="sk_test_secret", timeout=17)
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.create_bot(
                {
                    "meeting_url": "https://zoom.us/j/123456789",
                    "service": "zoom",
                    "bot_name": "Ontology Agent recorder",
                    "webhook_url": "https://hooks.example/webhooks/skribby",
                    "custom_metadata": {"job_id": "mtgrec-20260706-abcdef12"},
                }
            )

        self.assertEqual(result["id"], "bot_123")
        self.assertEqual(captured["url"], DEFAULT_API_URL)
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer sk_test_secret")
        self.assertEqual(captured["headers"]["Content-type"], "application/json")
        self.assertEqual(captured["body"]["webhook_url"], "https://hooks.example/webhooks/skribby")
        self.assertEqual(captured["body"]["custom_metadata"]["job_id"], "mtgrec-20260706-abcdef12")
        self.assertEqual(captured["timeout"], 17)

    def test_create_bot_http_error_does_not_leak_key_or_body(self):
        from runtime.skribby_client import SkribbyClient, SkribbyHTTPError

        response = io.BytesIO(b'{"message":"bad key sk_test_secret"}')
        error = HTTPError(
            url="https://platform.skribby.io/api/v1/bot",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=response,
        )

        client = SkribbyClient(api_key="sk_test_secret")
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(SkribbyHTTPError) as raised:
                client.create_bot({"meeting_url": "https://zoom.us/j/123456789"})

        self.assertEqual(raised.exception.status, 401)
        self.assertNotIn("sk_test_secret", str(raised.exception))
        self.assertNotIn("bad key", str(raised.exception))

    def test_create_bot_malformed_json_raises_typed_error_without_secret(self):
        from runtime.skribby_client import SkribbyClient, SkribbyResponseError

        client = SkribbyClient(api_key="sk_test_secret")
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse(b"not-json")):
            with self.assertRaises(SkribbyResponseError) as raised:
                client.create_bot({"meeting_url": "https://zoom.us/j/123456789"})

        self.assertNotIn("sk_test_secret", str(raised.exception))
        self.assertIn("invalid JSON", str(raised.exception))

    def test_create_bot_transport_error_is_typed(self):
        from runtime.skribby_client import SkribbyClient, SkribbyTransportError

        client = SkribbyClient(api_key="sk_test_secret")
        with mock.patch("urllib.request.urlopen", side_effect=URLError("connection refused")):
            with self.assertRaises(SkribbyTransportError) as raised:
                client.create_bot({"meeting_url": "https://zoom.us/j/123456789"})

        self.assertNotIn("sk_test_secret", str(raised.exception))
        self.assertIn("Skribby request could not be completed", str(raised.exception))

    def test_fetch_bot_uses_get_bot_endpoint(self):
        from runtime.skribby_client import SkribbyClient

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return FakeResponse({"id": "bot_123", "transcript": []})

        client = SkribbyClient(api_key="sk_test_secret", timeout=11)
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.fetch_bot("bot_123")

        self.assertEqual(result["id"], "bot_123")
        self.assertEqual(captured["url"], "https://platform.skribby.io/api/v1/bot/bot_123")
        self.assertEqual(captured["method"], "GET")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer sk_test_secret")
        self.assertEqual(captured["timeout"], 11)


if __name__ == "__main__":
    unittest.main()

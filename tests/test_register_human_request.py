import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from runtime.operational_store import OperationalStore
from scripts.register_human_request import register_human_request


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "register_human_request.py"


class RegisterHumanRequestTests(unittest.TestCase):
    def request(self, suffix: str, *, channel: str = "telegram:dm-owner") -> dict[str, object]:
        return {
            "requestId": f"hreq-{suffix}",
            "kind": "review",
            "owner": "owner",
            "channel": channel,
            "messageRef": "",
            "prompt": f"Private question {suffix}",
            "recommendedAnswer": "Accept this one recommendation.",
            "askedAt": "2026-07-16T09:00:00Z",
        }

    def test_registration_precedes_delivery_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "operational.sqlite3"
            with OperationalStore.connect(store_path) as store:
                store.initialize()
                request = self.request("one")
                result = register_human_request(store, request)
                replay = register_human_request(store, request)
                store.bind_human_request_message_ref(
                    "hreq-one",
                    message_ref="telegram:dm-owner:42",
                )
                post_binding_replay = register_human_request(store, request)

                self.assertEqual(result["status"], "registered")
                self.assertEqual(replay["status"], "already-registered")
                self.assertEqual(post_binding_replay["status"], "already-registered")
                self.assertFalse(post_binding_replay["provisional"])
                recorded = store.get_human_request("hreq-one")
                self.assertEqual(recorded["messageRef"], "telegram:dm-owner:42")

    def test_second_current_question_in_same_channel_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "operational.sqlite3"
            with OperationalStore.connect(store_path) as store:
                store.initialize()
                register_human_request(store, self.request("one"))

                with self.assertRaisesRegex(ValueError, "current delivered question"):
                    register_human_request(store, self.request("two"))

                self.assertIsNone(store.get_human_request("hreq-two"))

    def test_closed_request_and_mismatched_provisional_ref_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "operational.sqlite3"
            with OperationalStore.connect(store_path) as store:
                store.initialize()
                request = self.request("closed")
                register_human_request(store, request)
                store.cancel_human_request("hreq-closed", reason="No longer current.")
                with self.assertRaisesRegex(ValueError, "already closed"):
                    register_human_request(store, request)

                mismatched = self.request("mismatch", channel="telegram:other")
                mismatched["messageRef"] = "pending:hreq-someone-else"
                with self.assertRaisesRegex(ValueError, "must match requestId"):
                    register_human_request(store, mismatched)

    def test_cli_never_echoes_private_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "operational.sqlite3"
            with OperationalStore.connect(store_path) as store:
                store.initialize()
            private_prompt = "Confidential wording that must not appear in stdout."
            request = self.request("private")
            request["prompt"] = private_prompt

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--store", str(store_path)],
                cwd=REPO_ROOT,
                input=json.dumps(request),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(private_prompt, result.stdout)
            self.assertEqual(json.loads(result.stdout)["status"], "registered")


if __name__ == "__main__":
    unittest.main()

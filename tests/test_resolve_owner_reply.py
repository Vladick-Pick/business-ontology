import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from runtime.operational_store import OperationalStore
from scripts.resolve_owner_reply import resolve_owner_reply


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "resolve_owner_reply.py"


class ResolveOwnerReplyTests(unittest.TestCase):
    def make_store(self, tmp: str) -> OperationalStore:
        store = OperationalStore.connect(Path(tmp) / "operational.sqlite3")
        store.initialize()
        return store

    def record_request(
        self,
        store: OperationalStore,
        suffix: str,
        *,
        kind: str = "clarification",
        message_ref: str | None = None,
        owner: str = "owner",
    ) -> None:
        store.record_human_request(
            {
                "requestId": f"hreq-{suffix}",
                "kind": kind,
                "owner": owner,
                "channel": "telegram:dm-owner",
                "messageRef": message_ref or f"telegram-message-{suffix}",
                "prompt": f"Choose the action for {suffix}?",
                "recommendedAnswer": "Use the current documented action.",
                "askedAt": f"2026-07-15T09:0{suffix[-1]}:00Z",
            }
        )

    @staticmethod
    def decision_count(store: OperationalStore) -> int:
        row = store._connection.execute("SELECT COUNT(*) AS count FROM human_decisions").fetchone()
        return int(row["count"])

    def test_blanket_reply_with_three_open_requests_changes_nothing_and_creates_one_clarification(self):
        with tempfile.TemporaryDirectory() as tmp, self.make_store(tmp) as store:
            self.record_request(store, "open-1", kind="setup")
            self.record_request(store, "open-2", kind="review")
            self.record_request(store, "open-3", kind="migration")

            result = resolve_owner_reply(
                store,
                channel="telegram:dm-owner",
                actor="owner",
                reply_to_message_ref="",
                reply_text="Всё ок",
                inbound_message_ref="telegram-inbound-100",
                received_at="2026-07-15T10:00:00Z",
                language="ru",
            )

            self.assertEqual(result["answeredRequestIds"], [])
            self.assertEqual(result["reviewDecisionIds"], [])
            self.assertEqual(result["clarificationCount"], 1)
            self.assertIn("Рекомендация:", result["clarification"]["rendering"])
            self.assertIn("Последствие:", result["clarification"]["rendering"])
            self.assertEqual(self.decision_count(store), 0)
            for suffix in ("open-1", "open-2", "open-3"):
                self.assertEqual(store.get_human_request(f"hreq-{suffix}")["status"], "open")
            clarifications = store.list_open_human_requests(kind="clarification")
            self.assertEqual(len(clarifications), 1)
            created_id = result["clarification"]["requestId"]

            replay = resolve_owner_reply(
                store,
                channel="telegram:dm-owner",
                actor="owner",
                reply_to_message_ref="",
                reply_text="Всё ок",
                inbound_message_ref="telegram-inbound-100",
                received_at="2026-07-15T10:00:00Z",
                language="ru",
            )
            self.assertEqual(replay["clarification"]["requestId"], created_id)
            self.assertFalse(replay["clarificationCreated"])
            self.assertEqual(len(store.list_open_human_requests()), 4)

    def test_exact_reply_answers_exactly_one_non_review_request(self):
        with tempfile.TemporaryDirectory() as tmp, self.make_store(tmp) as store:
            for suffix in ("open-1", "open-2", "open-3"):
                self.record_request(store, suffix, kind="setup")

            result = resolve_owner_reply(
                store,
                channel="telegram:dm-owner",
                actor="owner",
                reply_to_message_ref="telegram-message-open-2",
                reply_text="Всё ок",
                inbound_message_ref="telegram-inbound-101",
                received_at="2026-07-15T10:01:00Z",
            )

            self.assertEqual(result["answeredRequestIds"], ["hreq-open-2"])
            self.assertEqual(result["reviewDecisionIds"], [])
            self.assertEqual(store.get_human_request("hreq-open-1")["status"], "open")
            self.assertEqual(store.get_human_request("hreq-open-2")["status"], "answered")
            self.assertEqual(store.get_human_request("hreq-open-3")["status"], "open")
            self.assertEqual(self.decision_count(store), 0)

    def test_duplicate_message_ref_and_wrong_actor_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp, self.make_store(tmp) as store:
            self.record_request(store, "open-1", message_ref="duplicate-ref")
            self.record_request(store, "open-2", message_ref="duplicate-ref")

            duplicate = resolve_owner_reply(
                store,
                channel="telegram:dm-owner",
                actor="owner",
                reply_to_message_ref="duplicate-ref",
                reply_text="Choose the current action.",
                inbound_message_ref="telegram-inbound-102",
            )
            self.assertEqual(duplicate["status"], "clarification-required")
            self.assertEqual(duplicate["answeredRequestIds"], [])

            self.record_request(store, "open-3", message_ref="unique-ref")
            wrong_actor = resolve_owner_reply(
                store,
                channel="telegram:dm-owner",
                actor="someone-else",
                reply_to_message_ref="unique-ref",
                reply_text="Choose the current action.",
                inbound_message_ref="telegram-inbound-103",
            )
            self.assertEqual(wrong_actor["reason"], "actor-not-authorized")
            self.assertEqual(store.get_human_request("hreq-open-3")["status"], "open")

    def test_review_ack_never_records_a_decision_or_answers_the_request(self):
        with tempfile.TemporaryDirectory() as tmp, self.make_store(tmp) as store:
            self.record_request(store, "open-1", kind="review")

            ack = resolve_owner_reply(
                store,
                channel="telegram:dm-owner",
                actor="owner",
                reply_to_message_ref="telegram-message-open-1",
                reply_text="Everything is fine",
                inbound_message_ref="telegram-inbound-104",
            )
            self.assertEqual(ack["status"], "clarification-required")
            self.assertEqual(ack["reason"], "review-action-not-explicit")
            self.assertEqual(store.get_human_request("hreq-open-1")["status"], "open")
            self.assertEqual(self.decision_count(store), 0)

            explicit = resolve_owner_reply(
                store,
                channel="telegram:dm-owner",
                actor="owner",
                reply_to_message_ref="telegram-message-open-1",
                reply_text="Accept the lead handoff rule.",
                inbound_message_ref="telegram-inbound-105",
            )
            self.assertEqual(explicit["status"], "review-validation-required")
            self.assertEqual(explicit["answeredRequestIds"], [])
            self.assertEqual(store.get_human_request("hreq-open-1")["status"], "open")
            self.assertEqual(self.decision_count(store), 0)

    def test_high_risk_non_review_ack_requires_an_explicit_action_and_object(self):
        with tempfile.TemporaryDirectory() as tmp, self.make_store(tmp) as store:
            self.record_request(store, "open-1", kind="source-access")

            ack = resolve_owner_reply(
                store,
                channel="telegram:dm-owner",
                actor="owner",
                reply_to_message_ref="telegram-message-open-1",
                reply_text="Всё ок",
                inbound_message_ref="telegram-inbound-107",
                language="ru",
            )
            self.assertEqual(ack["reason"], "high-risk-action-not-explicit")
            self.assertEqual(store.get_human_request("hreq-open-1")["status"], "open")

            explicit = resolve_owner_reply(
                store,
                channel="telegram:dm-owner",
                actor="owner",
                reply_to_message_ref="telegram-message-open-1",
                reply_text="Разрешаю подключить Google Drive только на чтение.",
                inbound_message_ref="telegram-inbound-108",
                language="ru",
            )
            self.assertEqual(explicit["answeredRequestIds"], ["hreq-open-1"])
            self.assertEqual(store.get_human_request("hreq-open-1")["status"], "answered")

    def test_cli_reads_private_reply_from_stdin_and_does_not_echo_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.make_store(tmp) as store:
                self.record_request(store, "open-1", kind="setup")
                store_path = Path(tmp) / "operational.sqlite3"

            private_reply = "Use the private repository; do not echo this sentence."
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--store",
                    str(store_path),
                    "--channel",
                    "telegram:dm-owner",
                    "--actor",
                    "owner",
                    "--reply-to-message-ref",
                    "telegram-message-open-1",
                    "--inbound-message-ref",
                    "telegram-inbound-106",
                ],
                cwd=REPO_ROOT,
                input=private_reply,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["answeredRequestIds"], ["hreq-open-1"])
            self.assertNotIn(private_reply, result.stdout)
            with OperationalStore.connect(store_path) as store:
                row = store._connection.execute(
                    "SELECT payload_json, answer_summary FROM human_requests WHERE request_id = ?",
                    ("hreq-open-1",),
                ).fetchone()
                self.assertNotIn(private_reply, str(row["payload_json"]))
                self.assertNotIn(private_reply, str(row["answer_summary"]))


if __name__ == "__main__":
    unittest.main()

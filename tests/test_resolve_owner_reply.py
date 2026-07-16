import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from runtime.operational_store import OperationalStore
from scripts.resolve_owner_reply import anchor_forwarded_question, resolve_owner_reply


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
        channel: str = "telegram:dm-owner",
        prompt: str | None = None,
    ) -> None:
        store.record_human_request(
            {
                "requestId": f"hreq-{suffix}",
                "kind": kind,
                "owner": owner,
                "channel": channel,
                "messageRef": message_ref or f"telegram-message-{suffix}",
                "prompt": prompt or f"Choose the action for {suffix}?",
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

    def test_reply_to_generated_clarification_can_be_correlated_and_closed(self):
        with tempfile.TemporaryDirectory() as tmp, self.make_store(tmp) as store:
            self.record_request(store, "open-1", kind="setup")
            self.record_request(store, "open-2", kind="review")
            clarification = resolve_owner_reply(
                store,
                channel="telegram:dm-owner",
                actor="owner",
                reply_to_message_ref="",
                reply_text="Да",
                inbound_message_ref="telegram-inbound-clarify-1",
            )

            result = resolve_owner_reply(
                store,
                channel="telegram:dm-owner",
                actor="owner",
                reply_to_message_ref="telegram-message-clarification",
                reply_text="I am answering the setup question.",
                inbound_message_ref="telegram-inbound-clarify-2",
            )

            clarification_id = clarification["clarification"]["requestId"]
            self.assertEqual(result["status"], "answered")
            self.assertEqual(result["answeredRequestIds"], [clarification_id])
            self.assertEqual(store.get_human_request(clarification_id)["status"], "answered")
            self.assertEqual(store.get_human_request("hreq-open-1")["status"], "open")
            self.assertEqual(store.get_human_request("hreq-open-2")["status"], "open")

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
            self.assertEqual(wrong_actor["status"], "authorization-required")
            self.assertEqual(wrong_actor["reason"], "actor-not-authorized")
            self.assertEqual(wrong_actor["clarificationCount"], 0)
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
            self.assertEqual(ack["status"], "review-validation-required")
            self.assertEqual(ack["reason"], "referenced-recommendation-confirmed")
            self.assertTrue(ack["recommendationConfirmed"])
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

    def test_authorized_group_actor_can_confirm_one_exact_review_request(self):
        policy = {
            "policyVersion": 1,
            "businessId": "interlab",
            "channels": [
                {
                    "channel": "telegram:group-systematization",
                    "aliases": ["telegram:-1000000000001"],
                    "reviewScopes": ["routine", "high-risk"],
                    "actors": ["telegram:reviewer-a"],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp, self.make_store(tmp) as store:
            self.record_request(
                store,
                "group-review",
                kind="review",
                owner="owner",
                channel="telegram:group-systematization",
            )

            result = resolve_owner_reply(
                store,
                channel="telegram:-1000000000001",
                actor="telegram:reviewer-a",
                reply_to_message_ref="telegram-message-group-review",
                reply_text="Да",
                inbound_message_ref="telegram-inbound-200",
                language="ru",
                authority_policy=policy,
            )

            self.assertEqual(result["status"], "review-validation-required")
            self.assertEqual(result["correlation"], "exact-message-ref")
            self.assertTrue(result["recommendationConfirmed"])
            self.assertEqual(store.get_human_request("hreq-group-review")["status"], "open")
            self.assertEqual(self.decision_count(store), 0)

    def test_policy_applies_to_routed_owner_in_a_review_channel(self):
        policy = {
            "policyVersion": 1,
            "businessId": "interlab",
            "channels": [
                {
                    "channel": "telegram:group-systematization",
                    "aliases": [],
                    "reviewScopes": ["routine"],
                    "actors": ["telegram:reviewer-a"],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp, self.make_store(tmp) as store:
            self.record_request(
                store,
                "owner-not-granted",
                kind="review",
                owner="owner",
                channel="telegram:group-systematization",
            )

            result = resolve_owner_reply(
                store,
                channel="telegram:group-systematization",
                actor="owner",
                reply_to_message_ref="telegram-message-owner-not-granted",
                reply_text="Да",
                authority_policy=policy,
            )

            self.assertEqual(result["status"], "authorization-required")
            self.assertEqual(result["clarificationCount"], 0)

    def test_provisional_question_binds_actual_reply_reference_before_validation(self):
        with tempfile.TemporaryDirectory() as tmp, self.make_store(tmp) as store:
            self.record_request(
                store,
                "pending-review",
                kind="review",
                message_ref="pending:hreq-pending-review",
            )

            result = resolve_owner_reply(
                store,
                channel="telegram:dm-owner",
                actor="owner",
                reply_to_message_ref="telegram:dm-owner:139",
                reply_text="Да да",
                inbound_message_ref="telegram:dm-owner:140",
                language="ru",
            )

            self.assertEqual(result["status"], "review-validation-required")
            self.assertEqual(result["correlation"], "provisional-message-ref")
            self.assertTrue(result["recommendationConfirmed"])
            self.assertEqual(
                store.get_human_request("hreq-pending-review")["messageRef"],
                "telegram:dm-owner:139",
            )

    def test_message_without_native_reply_matches_only_single_current_question(self):
        with tempfile.TemporaryDirectory() as tmp, self.make_store(tmp) as store:
            self.record_request(store, "single-review", kind="review")

            result = resolve_owner_reply(
                store,
                channel="telegram:dm-owner",
                actor="owner",
                reply_to_message_ref="",
                reply_text="Ок",
                inbound_message_ref="telegram-inbound-201",
                language="ru",
            )

            self.assertEqual(result["status"], "review-validation-required")
            self.assertEqual(result["correlation"], "single-current-question")
            self.assertTrue(result["recommendationConfirmed"])

    def test_forwarded_group_question_anchors_owner_dm_reply_without_raw_retention(self):
        policy = {
            "policyVersion": 1,
            "businessId": "interlab",
            "channels": [
                {
                    "channel": "telegram:dm-owner",
                    "aliases": [],
                    "reviewScopes": ["routine", "high-risk"],
                    "actors": ["owner"],
                },
                {
                    "channel": "telegram:group-systematization",
                    "aliases": [],
                    "reviewScopes": ["routine", "high-risk"],
                    "actors": ["telegram:reviewer-a"],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp, self.make_store(tmp) as store:
            prompt = "Should the four product claims use this exact classification?"
            self.record_request(
                store,
                "forwarded-review",
                kind="review",
                owner="owner",
                channel="telegram:group-systematization",
                prompt=prompt,
            )
            private_suffix = "PRIVATE FORWARDED SUFFIX MUST NOT PERSIST"

            anchored = anchor_forwarded_question(
                store,
                channel="telegram:dm-owner",
                actor="owner",
                inbound_message_ref="telegram:dm-owner:200",
                forwarded_body=f"{prompt}\n\n{private_suffix}",
                language="ru",
                authority_policy=policy,
            )
            resolved = resolve_owner_reply(
                store,
                channel="telegram:dm-owner",
                actor="owner",
                reply_to_message_ref="telegram:dm-owner:200",
                reply_text="Да",
                inbound_message_ref="telegram:dm-owner:201",
                language="ru",
                authority_policy=policy,
            )
            resolved_without_ref = resolve_owner_reply(
                store,
                channel="telegram:dm-owner",
                actor="owner",
                reply_to_message_ref="",
                reply_text="Да",
                inbound_message_ref="telegram:dm-owner:202",
                language="ru",
                authority_policy=policy,
            )

            self.assertEqual(anchored["status"], "context-anchored")
            self.assertEqual(anchored["answeredRequestIds"], [])
            self.assertEqual(resolved["status"], "review-validation-required")
            self.assertEqual(resolved["correlation"], "exact-message-ref")
            self.assertTrue(resolved["recommendationConfirmed"])
            self.assertEqual(resolved_without_ref["status"], "review-validation-required")
            self.assertEqual(
                resolved_without_ref["correlation"],
                "single-current-question",
            )
            self.assertEqual(self.decision_count(store), 0)
            refs = store.list_human_request_context_refs(
                request_id="hreq-forwarded-review"
            )
            self.assertEqual(refs[0]["messageRef"], "telegram:dm-owner:200")
            self.assertNotIn(private_suffix.encode(), (Path(tmp) / "operational.sqlite3").read_bytes())

    def test_forwarded_question_anchor_requires_one_match_and_inbound_authority(self):
        policy = {
            "policyVersion": 1,
            "businessId": "interlab",
            "channels": [
                {
                    "channel": "telegram:dm-owner",
                    "aliases": [],
                    "reviewScopes": ["routine"],
                    "actors": ["owner"],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp, self.make_store(tmp) as store:
            prompt = "Should this exact forwarded model question be accepted?"
            for suffix in ("forward-a", "forward-b"):
                self.record_request(
                    store,
                    suffix,
                    kind="review",
                    owner="owner",
                    channel="telegram:group-systematization",
                    prompt=prompt,
                )

            ambiguous = anchor_forwarded_question(
                store,
                channel="telegram:dm-owner",
                actor="owner",
                inbound_message_ref="telegram:dm-owner:300",
                forwarded_body=prompt,
                authority_policy=policy,
            )
            store.cancel_human_request("hreq-forward-b", reason="Remove duplicate test request.")
            unauthorized = anchor_forwarded_question(
                store,
                channel="telegram:dm-owner",
                actor="other-actor",
                inbound_message_ref="telegram:dm-owner:301",
                forwarded_body=prompt,
                authority_policy=policy,
            )

            self.assertEqual(ambiguous["status"], "context-not-matched")
            self.assertEqual(ambiguous["reason"], "multiple-forwarded-question-matches")
            self.assertEqual(unauthorized["status"], "authorization-required")
            self.assertEqual(store.list_human_request_context_refs(), [])

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

    def test_cli_anchors_a_forward_and_initializes_an_existing_store(self):
        policy = {
            "policyVersion": 1,
            "businessId": "interlab",
            "channels": [
                {
                    "channel": "telegram:dm-owner",
                    "aliases": [],
                    "reviewScopes": ["routine"],
                    "actors": ["owner"],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "operational.sqlite3"
            policy_path = Path(tmp) / "review-authority.json"
            prompt = "Should this forwarded question use the proposed classification?"
            with self.make_store(tmp) as store:
                self.record_request(
                    store,
                    "cli-forward",
                    kind="review",
                    channel="telegram:group-systematization",
                    prompt=prompt,
                )
                store._connection.execute("DROP TABLE human_request_context_refs")
                store._connection.commit()
            policy_path.write_text(json.dumps(policy), encoding="utf-8")

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
                    "--inbound-message-ref",
                    "telegram:dm-owner:400",
                    "--authority-policy",
                    str(policy_path),
                    "--forwarded-context-only",
                ],
                cwd=REPO_ROOT,
                input=prompt,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "context-anchored")
            self.assertNotIn(prompt, result.stdout)
            with OperationalStore.connect(store_path) as store:
                refs = store.list_human_request_context_refs()
                self.assertEqual(len(refs), 1)
                self.assertEqual(refs[0]["requestId"], "hreq-cli-forward")


if __name__ == "__main__":
    unittest.main()

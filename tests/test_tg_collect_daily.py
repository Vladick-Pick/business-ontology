import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = REPO_ROOT / "scripts" / "tg_collect_daily.py"


def load_collector():
    spec = importlib.util.spec_from_file_location("tg_collect_daily", COLLECTOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class TelegramDailyCollectorTests(unittest.TestCase):
    def test_telegram_desktop_export_moves_cursor_and_writes_packet(self):
        collector = load_collector()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export = {
                "id": -1001001,
                "name": "Systematization Acquisition",
                "messages": [
                    {
                        "id": 1,
                        "date": "2026-07-04T10:00:00",
                        "from": "Alice Example",
                        "from_id": "user123",
                        "text": "Partner review moved before sales handoff.",
                        "phone": "+1 555 101 2020",
                    }
                ],
            }
            write_json(root / "exports" / "acquisition" / "result.json", export)
            write_json(
                root / "chat-map.json",
                {
                    "-1001001": {
                        "business": "biz-acquisition",
                        "source_id": "tg-group-acquisition",
                        "chat_slug": "acquisition",
                    }
                },
            )

            result = collector.collect_daily(
                exports_dir=root / "exports",
                cursors_file=root / "cursors.json",
                out_dir=root / "out",
                chat_map_path=root / "chat-map.json",
                tz="UTC",
                backfill_days=36500,
                no_wake=True,
                run_id="run-001",
            )

            self.assertEqual(result["message_count"], 1)
            run_dir = root / "out" / "run-001"
            self.assertTrue((run_dir / "run_manifest.json").is_file())
            self.assertTrue((run_dir / "chats" / "acquisition" / "chat_manifest.json").is_file())
            packet = read_json(run_dir / "interpretation_packet.json")
            message = packet["messages"][0]
            self.assertEqual(message["chat"]["business"], "biz-acquisition")
            self.assertEqual(message["chat"]["source_id"], "tg-group-acquisition")
            self.assertEqual(message["sender"]["slug"], "alice-example")
            self.assertNotIn("phone", json.dumps(packet).lower())
            self.assertNotIn("email", json.dumps(packet).lower())
            cursor = read_json(root / "cursors.json")
            self.assertEqual(cursor["-1001001"]["last_id"], 1)

    def test_second_run_without_new_messages_is_noop(self):
        collector = load_collector()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "exports" / "acquisition" / "result.json",
                {
                    "id": -1001001,
                    "name": "Systematization Acquisition",
                    "messages": [
                        {
                            "id": 1,
                            "date": "2026-07-04T10:00:00",
                            "from": "Alice Example",
                            "text": "First message.",
                        }
                    ],
                },
            )
            write_json(root / "chat-map.json", {"-1001001": "biz-acquisition"})

            collector.collect_daily(
                root / "exports",
                root / "cursors.json",
                root / "out",
                root / "chat-map.json",
                run_id="run-001",
                no_wake=True,
            )
            second = collector.collect_daily(
                root / "exports",
                root / "cursors.json",
                root / "out",
                root / "chat-map.json",
                run_id="run-002",
                no_wake=True,
            )

            self.assertEqual(second["message_count"], 0)
            packet = read_json(root / "out" / "run-002" / "interpretation_packet.json")
            self.assertEqual(packet["messages"], [])

    def test_cursor_does_not_replay_older_messages_with_larger_ids(self):
        collector = load_collector()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "exports" / "acquisition" / "result.json",
                {
                    "id": -1001001,
                    "name": "Systematization Acquisition",
                    "messages": [
                        {
                            "id": 100,
                            "date": "2026-07-04T10:00:00",
                            "from": "Alice Example",
                            "text": "Cursor anchor.",
                        },
                        {
                            "id": 200,
                            "date": "2026-07-04T09:00:00",
                            "from": "Alice Example",
                            "text": "Older export row must not replay.",
                        },
                    ],
                },
            )
            write_json(root / "chat-map.json", {"-1001001": "biz-acquisition"})
            write_json(
                root / "cursors.json",
                {"-1001001": {"last_ts": "2026-07-04T10:00:00Z", "last_id": 100}},
            )

            result = collector.collect_daily(
                root / "exports",
                root / "cursors.json",
                root / "out",
                root / "chat-map.json",
                run_id="run-older-id",
                no_wake=True,
            )

            self.assertEqual(result["message_count"], 0)
            packet = read_json(root / "out" / "run-older-id" / "interpretation_packet.json")
            self.assertEqual(packet["messages"], [])

    def test_jsonl_export_is_supported(self):
        collector = load_collector()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lines = [
                {
                    "chat_id": "sales-chat",
                    "chat_slug": "sales",
                    "message_id": 7,
                    "ts": "2026-07-04T12:00:00Z",
                    "sender": {"name": "Bob Sales", "email": "bob@example.invalid"},
                    "text": "Sales accepts after profile completeness is visible.",
                    "reply_to": 6,
                    "attachments": [{"path": "files/spec.pdf"}],
                }
            ]
            jsonl = root / "exports" / "sales.jsonl"
            jsonl.parent.mkdir(parents=True)
            jsonl.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
            write_json(root / "chat-map.json", {"sales-chat": {"business": "biz-sales"}})

            result = collector.collect_daily(
                root / "exports",
                root / "cursors.json",
                root / "out",
                root / "chat-map.json",
                run_id="run-jsonl",
                no_wake=True,
            )

            self.assertEqual(result["message_count"], 1)
            packet = read_json(root / "out" / "run-jsonl" / "interpretation_packet.json")
            message = packet["messages"][0]
            self.assertEqual(message["chat"]["chat_slug"], "sales")
            self.assertEqual(message["reply_to"], 6)
            self.assertEqual(message["attachments"][0]["path"], "files/spec.pdf")
            self.assertNotIn("bob@example.invalid", json.dumps(packet))

    def test_unmapped_new_chat_is_collected_with_unknown_business(self):
        collector = load_collector()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jsonl = root / "exports" / "new-chat.jsonl"
            jsonl.parent.mkdir(parents=True)
            jsonl.write_text(
                json.dumps(
                    {
                        "chat_id": "new-chat",
                        "chat_slug": "new-chat",
                        "message_id": 1,
                        "ts": "2026-07-04T13:00:00Z",
                        "sender": "New Sender",
                        "text": "New business chat appeared.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            write_json(root / "chat-map.json", {})

            result = collector.collect_daily(
                root / "exports",
                root / "cursors.json",
                root / "out",
                root / "chat-map.json",
                run_id="run-new",
                no_wake=True,
            )

            self.assertEqual(result["chat_count"], 1)
            packet = read_json(root / "out" / "run-new" / "interpretation_packet.json")
            self.assertEqual(packet["messages"][0]["chat"]["business"], "unknown")

    def test_no_wake_does_not_call_http(self):
        collector = load_collector()
        with tempfile.TemporaryDirectory() as tmp, mock.patch("urllib.request.urlopen") as urlopen:
            root = Path(tmp)
            write_json(
                root / "exports" / "acquisition" / "result.json",
                {
                    "id": -1001001,
                    "name": "Systematization Acquisition",
                    "messages": [
                        {
                            "id": 1,
                            "date": "2026-07-04T10:00:00",
                            "from": "Alice Example",
                            "text": "Message.",
                        }
                    ],
                },
            )
            write_json(root / "chat-map.json", {"-1001001": "biz-acquisition"})

            collector.collect_daily(
                root / "exports",
                root / "cursors.json",
                root / "out",
                root / "chat-map.json",
                run_id="run-001",
                no_wake=True,
            )

            urlopen.assert_not_called()

    def test_help_exits_zero(self):
        collector = load_collector()
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as raised:
            collector.main(["--help"])

        self.assertEqual(raised.exception.code, 0)


if __name__ == "__main__":
    unittest.main()

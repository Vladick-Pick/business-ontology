import importlib.util
import contextlib
import io
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORTER = REPO_ROOT / "scripts" / "tg_mtproto_export.py"
COLLECTOR = REPO_ROOT / "scripts" / "tg_collect_daily.py"
DAILY_INGEST = REPO_ROOT / "scripts" / "tg_run_daily_ingest.py"


def load_exporter():
    spec = importlib.util.spec_from_file_location("tg_mtproto_export", EXPORTER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_collector():
    spec = importlib.util.spec_from_file_location("tg_collect_daily", COLLECTOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_daily_ingest():
    spec = importlib.util.spec_from_file_location("tg_run_daily_ingest", DAILY_INGEST)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_mtproto_config(root: Path) -> Path:
    config_dir = root / "source-setup"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "telegram-mtproto.toml"
    config_path.write_text(
        """
[telegram]
api_id_env = "TEST_TELEGRAM_API_ID"
api_hash_env = "TEST_TELEGRAM_API_HASH"
folder_title = "Daily Review"

[runtime]
timezone = "UTC"
backfill_days = 1
download_media = true

[storage]
exports_dir = "exports"
cursor_file = "mtproto-cursors.json"
""".lstrip(),
        encoding="utf-8",
    )
    return config_path


def write_chat_map(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "-1001001": {
                    "business": "biz-acquisition",
                    "source_id": "tg-group-acquisition",
                    "chat_slug": "acquisition",
                },
                "-1002002": {
                    "business": "biz-sales",
                    "source_id": "tg-group-sales",
                    "chat_slug": "sales",
                },
            }
        ),
        encoding="utf-8",
    )


@contextlib.contextmanager
def telegram_env():
    old_id = os.environ.get("TEST_TELEGRAM_API_ID")
    old_hash = os.environ.get("TEST_TELEGRAM_API_HASH")
    os.environ["TEST_TELEGRAM_API_ID"] = "456"
    os.environ["TEST_TELEGRAM_API_HASH"] = "secret-hash"
    try:
        yield
    finally:
        if old_id is None:
            os.environ.pop("TEST_TELEGRAM_API_ID", None)
        else:
            os.environ["TEST_TELEGRAM_API_ID"] = old_id
        if old_hash is None:
            os.environ.pop("TEST_TELEGRAM_API_HASH", None)
        else:
            os.environ["TEST_TELEGRAM_API_HASH"] = old_hash


@dataclass
class FakeEntity:
    id: int
    title: str | None = None
    username: str | None = None
    megagroup: bool = False


@dataclass
class FakeDialog:
    entity: FakeEntity
    name: str
    id: int
    input_entity: object | None = None
    is_group: bool = False
    is_channel: bool = False
    is_user: bool = False


@dataclass
class FakeInputPeerUser:
    user_id: int


@dataclass
class FakeInputPeerChannel:
    channel_id: int


@dataclass
class FakeInputPeerSelf:
    pass


@dataclass
class FakeFilter:
    pinned_peers: list[object]
    include_peers: list[object]
    exclude_peers: list[object]
    groups: bool = False
    broadcasts: bool = False
    bots: bool = False
    contacts: bool = False
    non_contacts: bool = False


@dataclass
class FakeSender:
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


@dataclass
class FakeFile:
    name: str | None = None
    ext: str | None = None
    mime_type: str | None = None
    size: int | None = None
    id: int | None = None


@dataclass
class FakeMessage:
    id: int
    date: datetime
    text: str = ""
    sender: FakeSender | None = None
    file: FakeFile | None = None
    reply_to_msg_id: int | None = None


class FakeTelegramGateway:
    def __init__(self, *, fail_chat_id=None):
        self.fail_chat_id = fail_chat_id
        self.chats = [
            {"id": -1001001, "title": "Systematization Acquisition", "slug": "acquisition", "entity": object()},
            {"id": -1002002, "title": "Systematization Sales", "slug": "sales", "entity": object()},
        ]
        self.messages = {
            "-1001001": [
                FakeMessage(
                    id=11,
                    date=datetime(2026, 7, 4, 8, 0, tzinfo=timezone.utc),
                    text="Old message.",
                    sender=FakeSender(id=1, username="alice"),
                ),
                FakeMessage(
                    id=12,
                    date=datetime(2026, 7, 5, 8, 0, tzinfo=timezone.utc),
                    text="Partner review moved before sales handoff.",
                    sender=FakeSender(id=2, first_name="Bob", last_name="Sales"),
                    file=FakeFile(name="handoff.pdf", ext=".pdf", mime_type="application/pdf", size=42, id=501),
                    reply_to_msg_id=10,
                ),
            ],
            "-1002002": [
                FakeMessage(
                    id=3,
                    date=datetime(2026, 7, 5, 9, 0, tzinfo=timezone.utc),
                    text="Sales accepts after profile completeness is visible.",
                    sender=FakeSender(id=3, username="carol"),
                )
            ],
        }
        self.iter_calls = []
        self.downloads = []

    def list_folder_chats(self, folder_title):
        self.folder_title = folder_title
        return self.chats

    def iter_new_messages(self, chat_ref, *, after_message_id, after_date, limit):
        self.iter_calls.append((chat_ref["id"], after_message_id, after_date, limit))
        if self.fail_chat_id == chat_ref["id"]:
            raise RuntimeError("forced chat failure")
        rows = self.messages[str(chat_ref["id"])]
        if after_message_id is not None:
            rows = [row for row in rows if row.id > after_message_id]
        elif after_date is not None:
            rows = [row for row in rows if row.date > after_date]
        return rows[:limit] if limit else rows

    def download_media(self, message, target_dir):
        if message.file is None:
            return None
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{message.id}.bin"
        path.write_bytes(b"payload")
        self.downloads.append(str(path))
        return str(path)


class FakeGatewayContext:
    def __init__(self, settings):
        self.gateway = FakeTelegramGateway(fail_chat_id=-1002002)

    def __enter__(self):
        return self.gateway

    def __exit__(self, exc_type, exc, tb):
        return None


class MtprotoExportTests(unittest.TestCase):
    def config(self, module, root):
        return module.MtprotoExportConfig(
            telegram=module.TelegramSettings(
                api_id=123,
                api_hash="hash",
                session_path=root / "telegram.session",
                folder_title="Daily Review",
            ),
            runtime=module.RuntimeSettings(
                timezone="UTC",
                backfill_days=1,
                max_messages_per_chat=None,
                download_media=True,
            ),
            storage=module.StorageSettings(
                exports_dir=root / "exports",
                cursor_file=root / "mtproto-cursors.json",
            ),
        )

    def test_select_dialogs_for_native_folder_uses_included_peers_and_excludes_self(self):
        module = load_exporter()
        target = FakeDialog(
            entity=FakeEntity(id=42, title="Target", megagroup=True),
            name="Target",
            id=-10042,
            input_entity=FakeInputPeerChannel(channel_id=42),
            is_group=True,
        )
        other = FakeDialog(
            entity=FakeEntity(id=99, title="Other", megagroup=True),
            name="Other",
            id=-10099,
            input_entity=FakeInputPeerChannel(channel_id=99),
            is_group=True,
        )
        self_dialog = FakeDialog(
            entity=FakeEntity(id=1, title="Saved"),
            name="Saved",
            id=1,
            input_entity=FakeInputPeerSelf(),
            is_user=True,
        )
        folder = FakeFilter(
            pinned_peers=[FakeInputPeerChannel(channel_id=42)],
            include_peers=[],
            exclude_peers=[],
        )

        selected = module.select_dialogs_for_filter([self_dialog, target, other], folder)
        refs = [module.chat_ref_from_dialog(dialog) for dialog in selected]

        self.assertEqual(selected, [target])
        self.assertEqual(refs[0]["id"], -10042)
        self.assertEqual(refs[0]["slug"], "target")

    def test_run_export_writes_jsonl_manifest_and_cursor(self):
        module = load_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.config(module, root)
            gateway = FakeTelegramGateway()

            manifest = module.run_export(
                config,
                telegram=gateway,
                now=datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc),
                run_id="run-001",
            )

            self.assertEqual(manifest["source_mode"], "mtproto-session")
            self.assertEqual(manifest["folder_title"], "Daily Review")
            self.assertEqual(manifest["chat_count"], 2)
            self.assertEqual(manifest["total_messages"], 2)
            self.assertEqual(manifest["failed_chats"], [])
            self.assertTrue((root / "exports" / "run-001" / "mtproto_run_manifest.json").is_file())
            packet_rows = [
                json.loads(line)
                for line in (root / "exports" / "run-001" / "acquisition.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(packet_rows), 1)
            message = packet_rows[0]
            self.assertEqual(message["chat_id"], "-1001001")
            self.assertEqual(message["chat_slug"], "acquisition")
            self.assertEqual(message["message_id"], 12)
            self.assertEqual(message["sender"]["name"], "Bob Sales")
            self.assertEqual(message["reply_to"], 10)
            self.assertEqual(message["attachments"][0]["mime_type"], "application/pdf")
            self.assertTrue(message["attachments"][0]["path"].endswith("12.bin"))
            cursors = read_json(root / "mtproto-cursors.json")
            self.assertEqual(cursors["-1001001"]["last_id"], 12)
            self.assertEqual(cursors["-1002002"]["last_id"], 3)

    def test_mtproto_export_folder_is_consumed_by_daily_packet_collector(self):
        module = load_exporter()
        collector = load_collector()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.config(module, root)
            gateway = FakeTelegramGateway()
            module.run_export(
                config,
                telegram=gateway,
                now=datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc),
                run_id="run-bridge",
            )
            write_chat_map(root / "chat-map.json")

            result = collector.collect_daily(
                exports_dir=root / "exports",
                cursors_file=root / "packet-cursors.json",
                out_dir=root / "packet-runs",
                chat_map_path=root / "chat-map.json",
                tz="UTC",
                backfill_days=7,
                no_wake=True,
                run_id="packet-001",
            )

            self.assertEqual(result["message_count"], 2)
            packet = read_json(root / "packet-runs" / "packet-001" / "interpretation_packet.json")
            self.assertEqual(packet["messages"][0]["chat"]["business"], "biz-acquisition")
            self.assertEqual(packet["messages"][0]["text"], "Partner review moved before sales handoff.")
            self.assertEqual(packet["messages"][1]["chat"]["business"], "biz-sales")

    def test_run_export_uses_cursor_and_does_not_commit_cursor_on_partial_failure(self):
        module = load_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.config(module, root)
            config.storage.cursor_file.write_text(
                json.dumps(
                    {
                        "-1001001": {"last_id": 11, "last_ts": "2026-07-04T08:00:00Z"},
                        "-1002002": {"last_id": 2, "last_ts": "2026-07-04T09:00:00Z"},
                    }
                ),
                encoding="utf-8",
            )
            gateway = FakeTelegramGateway(fail_chat_id=-1002002)

            manifest = module.run_export(
                config,
                telegram=gateway,
                now=datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc),
                run_id="run-002",
            )

            self.assertEqual(manifest["total_messages"], 1)
            self.assertEqual(manifest["failed_chats"][0]["chat_id"], "-1002002")
            self.assertFalse(manifest["cursor_committed"])
            self.assertEqual(gateway.iter_calls[0][1], 11)
            cursors = read_json(root / "mtproto-cursors.json")
            self.assertEqual(cursors["-1001001"]["last_id"], 11)
            self.assertEqual(cursors["-1002002"]["last_id"], 2)

    def test_run_export_can_commit_successful_cursors_when_partial_is_explicitly_allowed(self):
        module = load_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.config(module, root)
            config.storage.cursor_file.write_text(
                json.dumps(
                    {
                        "-1001001": {"last_id": 11, "last_ts": "2026-07-04T08:00:00Z"},
                        "-1002002": {"last_id": 2, "last_ts": "2026-07-04T09:00:00Z"},
                    }
                ),
                encoding="utf-8",
            )
            gateway = FakeTelegramGateway(fail_chat_id=-1002002)

            manifest = module.run_export(
                config,
                telegram=gateway,
                now=datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc),
                run_id="run-002",
                allow_partial=True,
            )

            self.assertTrue(manifest["cursor_committed"])
            cursors = read_json(root / "mtproto-cursors.json")
            self.assertEqual(cursors["-1001001"]["last_id"], 12)
            self.assertEqual(cursors["-1002002"]["last_id"], 2)

    def test_load_config_prefers_env_names_for_telegram_credentials(self):
        module = load_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = write_mtproto_config(root)
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    "timezone = \"UTC\"\nbackfill_days = 1\ndownload_media = true",
                    "timezone = \"Europe/Istanbul\"\nbackfill_days = 2\nmax_messages_per_chat = 50\ndownload_media = false",
                ),
                encoding="utf-8",
            )
            with telegram_env():
                config = module.load_config(config_path)

            self.assertEqual(config.telegram.api_id, 456)
            self.assertEqual(config.telegram.api_hash, "secret-hash")
            self.assertEqual(config.telegram.folder_title, "Daily Review")
            self.assertEqual(config.runtime.timezone, "Europe/Istanbul")
            self.assertEqual(config.runtime.backfill_days, 2)
            self.assertEqual(config.runtime.max_messages_per_chat, 50)
            self.assertFalse(config.runtime.download_media)
            self.assertEqual(config.telegram.session_path, root / "secrets" / "telegram" / "telegram-user.session")
            self.assertEqual(config.storage.exports_dir, root / "source-setup" / "exports")
            self.assertEqual(config.storage.cursor_file, root / "source-setup" / "mtproto-cursors.json")

    def test_load_config_rejects_literal_telegram_credentials(self):
        module = load_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = write_mtproto_config(root)
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    'api_id_env = "TEST_TELEGRAM_API_ID"',
                    'api_id = "456"',
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "api_id must be provided through api_id_env"):
                module.load_config(config_path)

    def test_export_cli_fails_by_default_when_a_selected_chat_fails(self):
        module = load_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = write_mtproto_config(root)
            module.TelethonGateway = FakeGatewayContext

            with telegram_env(), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                exit_code = module.main(
                    [
                        "--config",
                        str(config_path),
                        "--run-id",
                        "run-partial",
                        "--now",
                        "2026-07-05T12:00:00+00:00",
                        "--json",
                    ]
                )

            self.assertEqual(exit_code, 2)
            self.assertFalse((root / "exports" / "run-partial" / "sales.jsonl").exists())

    def test_export_cli_allows_partial_only_when_explicit(self):
        module = load_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = write_mtproto_config(root)
            module.TelethonGateway = FakeGatewayContext

            with telegram_env(), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                exit_code = module.main(
                    [
                        "--config",
                        str(config_path),
                        "--run-id",
                        "run-partial",
                        "--now",
                        "2026-07-05T12:00:00+00:00",
                        "--allow-partial",
                    ]
                )

            self.assertEqual(exit_code, 0)

    def test_daily_ingest_wrapper_consumes_only_the_current_mtproto_run(self):
        wrapper = load_daily_ingest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = write_mtproto_config(root)
            write_chat_map(root / "chat-map.json")
            old_dir = root / "source-setup" / "exports" / "old-run"
            old_dir.mkdir(parents=True)
            old_message = {
                "chat_id": "-1001001",
                "chat_slug": "acquisition",
                "message_id": 99,
                "ts": "2026-07-05T11:00:00Z",
                "sender": {"id": 9, "username": "old"},
                "text": "Historical run that must not be replayed.",
            }
            (old_dir / "acquisition.jsonl").write_text(json.dumps(old_message) + "\n", encoding="utf-8")

            with telegram_env():
                result = wrapper.run_daily_ingest(
                    mtproto_config=config_path,
                    packet_cursors_file=root / "packet-cursors.json",
                    packet_out_dir=root / "packet-runs",
                    chat_map=root / "chat-map.json",
                    tz="UTC",
                    backfill_days=7,
                    no_wake=True,
                    run_id="current-run",
                    now=datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc),
                    telegram=FakeTelegramGateway(),
                )

            self.assertEqual(result["packet"]["message_count"], 2)
            packet = read_json(root / "packet-runs" / "current-run" / "interpretation_packet.json")
            texts = [message["text"] for message in packet["messages"]]
            self.assertNotIn("Historical run that must not be replayed.", texts)

    def test_telegram_dependency_and_boundary_are_documented(self):
        requirements = (REPO_ROOT / "requirements-telegram.txt").read_text(encoding="utf-8")
        install = (REPO_ROOT / "deployment" / "INSTALL.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        package = (REPO_ROOT / "agent-package.yaml").read_text(encoding="utf-8")

        self.assertIn("telethon", requirements)
        self.assertIn("requirements-telegram.txt", install)
        self.assertIn("tg_run_daily_ingest.py", readme)
        self.assertIn("local Telegram MTProto folder exporter", package)
        self.assertNotIn("live Telegram account " + "export connector", package)
        telegram_scan = (REPO_ROOT / "adapters" / "openclaw" / "source-setup" / "telegram-scan.md").read_text(encoding="utf-8")
        self.assertIn("omits `session_path`", telegram_scan)
        self.assertIn("<workspace>/secrets/telegram/telegram-user.session", telegram_scan)
        self.assertNotIn("TELEGRAM_SESSION_PATH", telegram_scan)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Run the installed OpenClaw-style business analyst E2E proof."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from package_update_common import utc_timestamp, write_json_atomic  # noqa: E402
from runtime.resident_loop import run_once as run_resident_loop_once  # noqa: E402
from scripts.source_registry import record_live_proof, sha256_file_ref, upsert_source_instance  # noqa: E402


def read_package_version() -> str:
    for line in (REPO_ROOT / "agent-package.yaml").read_text(encoding="utf-8").splitlines():
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip().strip('"')
    raise RuntimeError("agent-package.yaml does not declare version")


PACKAGE_VERSION = read_package_version()
PACKAGE_TAG = f"v{PACKAGE_VERSION}"
REPORT_JSON = "INSTALLED_AGENT_E2E_REPORT.json"
REPORT_MD = "INSTALLED_AGENT_E2E_REPORT.md"
SENSITIVE_KEY_FRAGMENTS = (
    "token",
    "secret",
    "password",
    "api_key",
    "api-key",
    "apikey",
    "authorization",
    "bearer",
)


@dataclass
class FixtureMessage:
    id: int
    date: datetime
    text: str = ""
    sender: Any | None = None
    file: Any | None = None
    reply_to_msg_id: int | None = None


@dataclass
class FixtureSender:
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


@dataclass
class FixtureFile:
    name: str | None = None
    ext: str | None = None
    mime_type: str | None = None
    size: int | None = None
    id: int | None = None


class FixtureTelegramGateway:
    def __init__(self) -> None:
        self.chats = [
            {"id": -1001001, "title": "Acquisition", "slug": "acquisition", "entity": object()},
            {"id": -1002002, "title": "Sales", "slug": "sales", "entity": object()},
        ]
        self.messages = {
            "-1001001": [
                FixtureMessage(
                    id=12,
                    date=datetime(2026, 7, 5, 8, 0, tzinfo=timezone.utc),
                    text="Partner review moved before sales handoff.",
                    sender=FixtureSender(id=2, first_name="Owner"),
                    file=FixtureFile(name="handoff.pdf", ext=".pdf", mime_type="application/pdf", size=42, id=501),
                    reply_to_msg_id=10,
                ),
            ],
            "-1002002": [
                FixtureMessage(
                    id=3,
                    date=datetime(2026, 7, 5, 9, 0, tzinfo=timezone.utc),
                    text="Sales accepts after profile completeness is visible.",
                    sender=FixtureSender(id=3, username="sales"),
                )
            ],
        }

    def list_folder_chats(self, folder_title: str) -> list[dict[str, Any]]:
        self.folder_title = folder_title
        return self.chats

    def iter_new_messages(self, chat_ref: dict[str, Any], *, after_message_id, after_date, limit):
        rows = self.messages[str(chat_ref["id"])]
        if after_message_id is not None:
            rows = [row for row in rows if row.id > after_message_id]
        elif after_date is not None:
            rows = [row for row in rows if row.date > after_date]
        return rows[:limit] if limit else rows

    def download_media(self, message: FixtureMessage, target_dir: Path) -> str | None:
        if message.file is None:
            return None
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{message.id}.bin"
        path.write_bytes(b"fixture-payload")
        return str(path)


class FixtureHostAdapter:
    def __init__(self) -> None:
        self.events: list[dict[str, str]] = []

    def direct_message(self, text: str) -> None:
        self.events.append({"kind": "direct-message", "summary": text})

    def group_mention(self, text: str) -> None:
        self.events.append({"kind": "group-mention", "summary": text})

    def owner_answer(self, text: str) -> None:
        self.events.append({"kind": "owner-answer", "summary": text})

    def report(self) -> dict[str, object]:
        return {"events": self.events, "event_count": len(self.events)}


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 900,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git(command: list[str], *, cwd: Path) -> str:
    result = run(["git", *command], cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git failed")
    return result.stdout.strip()


def copy_current_package_source(target: Path) -> None:
    def ignore(_: str, names: list[str]) -> set[str]:
        ignored = {
            ".git",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".DS_Store",
        }
        return {name for name in names if name in ignored or name.endswith(".pyc")}

    shutil.copytree(REPO_ROOT, target, ignore=ignore)


def prepare_local_release_repo(work_dir: Path) -> tuple[Path, str]:
    source = work_dir / "package-source"
    bare = work_dir / "package-release.git"
    copy_current_package_source(source)
    git(["init"], cwd=source)
    git(["add", "."], cwd=source)
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Business Ontology E2E",
            "GIT_AUTHOR_EMAIL": "business-ontology-e2e@example.invalid",
            "GIT_COMMITTER_NAME": "Business Ontology E2E",
            "GIT_COMMITTER_EMAIL": "business-ontology-e2e@example.invalid",
        }
    )
    commit = run(["git", "commit", "-m", "fixture package release"], cwd=source, env=env)
    if commit.returncode != 0:
        raise RuntimeError(commit.stderr.strip() or commit.stdout.strip() or "git commit failed")
    git(["tag", PACKAGE_TAG], cwd=source)
    git(["clone", "--bare", str(source), str(bare)], cwd=work_dir)
    return bare, git(["rev-parse", "HEAD"], cwd=source)


def bootstrap_workspace(install_root: Path, model_root: Path) -> Path:
    workspace = install_root / "workspace"
    result = run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "bootstrap_openclaw_workspace.py"),
            "--workspace",
            str(workspace),
            "--module",
            "Acquisition",
            "--agent-name",
            "Business Ontology Resident",
            "--ontology-repo-url",
            str(model_root),
            "--company-model-language",
            "ru",
        ],
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "workspace bootstrap failed")
    return workspace


def write_old_install_lock(workspace: Path, remote: Path) -> None:
    write_json(
        workspace / "PACKAGE_VERSION.lock",
        {
            "commit": "old-fixture-commit",
            "current_version": "0.9.0",
            "installed_at": "2026-07-01T00:00:00Z",
            "previous_commit": "",
            "previous_version": "",
            "remote_url": str(remote),
            "tag": "v0.9.0",
        },
    )


def prepare_model_repo(work_dir: Path, package_commit: str) -> Path:
    model_root = work_dir / "accepted-model"
    shutil.copytree(REPO_ROOT / "examples" / "acquisition-ontology", model_root)
    (model_root / "scripts").mkdir()
    shutil.copy2(
        REPO_ROOT / "templates" / "model-repo" / "scripts" / "validate_model_repo.py.tpl",
        model_root / "scripts" / "validate_model_repo.py",
    )
    write_json(
        model_root / "PACKAGE_CONTRACT.lock",
        {
            "package_name": "business-ontology",
            "package_version": PACKAGE_VERSION,
            "package_commit": package_commit,
            "validator": "scripts/links_validate.py",
            "validator_contract": "data-model-v2-hard-gate",
        },
    )
    git(["init"], cwd=model_root)
    git(["add", "."], cwd=model_root)
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Business Ontology E2E",
            "GIT_AUTHOR_EMAIL": "business-ontology-e2e@example.invalid",
            "GIT_COMMITTER_NAME": "Business Ontology E2E",
            "GIT_COMMITTER_EMAIL": "business-ontology-e2e@example.invalid",
        }
    )
    result = run(["git", "commit", "-m", "fixture accepted model"], cwd=model_root, env=env)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "model git commit failed")
    return model_root


def apply_update(install_root: Path, model_root: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("BUSINESS_ONTOLOGY_PACKAGE_SELF_TEST_TIMEOUT", "180")
    result = run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "apply_package_update.py"),
            "--install-root",
            str(install_root),
            "--to",
            PACKAGE_TAG,
            "--model-repo",
            str(model_root),
        ],
        cwd=REPO_ROOT,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or result.stderr.strip() or "package update failed")
    return json.loads(result.stdout)


def verify_installed_package(install_root: Path) -> dict[str, Any]:
    verifier = install_root / "package" / "current" / "scripts" / "verify_installed_package.py"
    result = run([sys.executable, str(verifier), "--install-root", str(install_root)])
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or result.stderr.strip() or "installed package verification failed")
    return json.loads(result.stdout)


def write_mtproto_fixture_config(workspace: Path) -> tuple[Path, Path]:
    config_dir = workspace / "source-setup"
    config_dir.mkdir(parents=True, exist_ok=True)
    config = config_dir / "telegram-mtproto.fixture.toml"
    config.write_text(
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
    chat_map = config_dir / "telegram-chat-map.fixture.json"
    write_json(
        chat_map,
        {
            "-1001001": {"business": "biz-acquisition", "source_id": "tg-group-acquisition", "chat_slug": "acquisition"},
            "-1002002": {"business": "biz-sales", "source_id": "tg-group-sales", "chat_slug": "sales"},
        },
    )
    return config, chat_map


def run_telegram_fixture(workspace: Path) -> dict[str, Any]:
    from scripts.tg_run_daily_ingest import run_daily_ingest

    config, chat_map = write_mtproto_fixture_config(workspace)
    old_id = os.environ.get("TEST_TELEGRAM_API_ID")
    old_hash = os.environ.get("TEST_TELEGRAM_API_HASH")
    os.environ["TEST_TELEGRAM_API_ID"] = "456"
    os.environ["TEST_TELEGRAM_API_HASH"] = "fixture-secret-not-persisted"
    try:
        return run_daily_ingest(
            mtproto_config=config,
            packet_cursors_file=workspace / "agent-state" / "telegram-packet-cursors.json",
            packet_out_dir=workspace / "source-material" / "telegram-daily-packets",
            chat_map=chat_map,
            tz="UTC",
            backfill_days=1,
            no_wake=True,
            run_id="fixture-telegram-run",
            now=datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc),
            telegram=FixtureTelegramGateway(),
            workspace=workspace,
            source_instance_id="telegram-mtproto-history",
            owner_agent="business-ontology-resident",
            scheduler_ref="fixture:daily-scan",
        )
    finally:
        if old_id is None:
            os.environ.pop("TEST_TELEGRAM_API_ID", None)
        else:
            os.environ["TEST_TELEGRAM_API_ID"] = old_id
        if old_hash is None:
            os.environ.pop("TEST_TELEGRAM_API_HASH", None)
        else:
            os.environ["TEST_TELEGRAM_API_HASH"] = old_hash


def run_meeting_fixture(workspace: Path) -> dict[str, Any]:
    packet_dir = workspace / "source-material" / "meeting-transcripts" / "fixture-meeting"
    packet_dir.mkdir(parents=True, exist_ok=True)
    packet = {
        "packet_id": "mtg-packet-fixture-001",
        "source_id": "meeting-fixture",
        "business_id": "biz-acquisition",
        "meeting_url_hash": "sha256:" + "a" * 64,
        "transcript_hash": "sha256:" + "b" * 64,
        "segments": [
            {
                "speaker": "Owner",
                "start_ms": 0,
                "end_ms": 12000,
                "text": "Qualification handoff needs owner review before sales accepts it.",
            }
        ],
        "redaction": {"rawPayloadIncluded": False, "piiExcluded": True},
    }
    packet_path = packet_dir / "meeting-transcript-packet.json"
    write_json(packet_path, packet)
    instance = upsert_source_instance(
        workspace,
        {
            "source_instance_id": "meeting-recording",
            "owner_agent": "business-ontology-resident",
            "kind": "meeting-recorder",
            "runtime_adapter": "scripts/meeting_recording_cli.py",
            "config_ref": "env:SKRIBBY_API_KEY; env:MEETING_RECORDING_PUBLIC_BASE_URL",
            "cursor_ref": "meeting-recording-store:fixture",
            "output_ref": "source-material/meeting-transcripts",
            "scheduler_ref": "host-delivered-message",
            "status": "configured",
            "last_live_proof_id": "",
        },
    )
    proof = record_live_proof(
        workspace,
        {
            "live_proof_id": "proof-meeting-recording-fixture",
            "source_instance_id": "meeting-recording",
            "capability": "meeting-recording-transcript-packet",
            "mode": "fixture",
            "input_ref": "host-message:zoom-link-fixture",
            "output_artifacts": [str(packet_path)],
            "evidence_hash": sha256_file_ref(packet_path),
            "status": "passed",
        },
    )
    return {"source_instance": instance, "live_proof": proof, "packet_path": str(packet_path)}


def write_source_event_fixture(workspace: Path) -> Path:
    source_dir = workspace / "source-events"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_event = read_json(REPO_ROOT / "evals" / "fixtures" / "source-events" / "telegram-export.synthetic.json")
    path = source_dir / "srcevt-telegram-handoff-001.json"
    write_json(path, source_event)
    return path


def run_resident_loop(workspace: Path, model_revision: str) -> dict[str, Any]:
    source_event_path = write_source_event_fixture(workspace)
    config = {
        "model_pack_path": str(workspace / "model-packs" / "acquisition.model-pack.json"),
        "source_event_dir": str(source_event_path.parent),
        "package_output_dir": str(workspace / "model-change-packages"),
        "state_path": str(workspace / "agent-state" / "resident-loop-ledger.json"),
        "trace_path": str(workspace / "traces" / "events.jsonl"),
        "artifact_root": str(workspace),
        "state_root": str(workspace / "agent-state"),
        "store_path": str(workspace / "agent-state" / "operational-store.sqlite"),
        "digest_path": str(workspace / "digests" / "daily-digest.md"),
        "ontology_revision": model_revision,
        "generated_at": "2026-07-08T00:00:00Z",
        "digest_threshold": 1,
        "write_digest": True,
    }
    return run_resident_loop_once(config)


def run_write_gate(workspace: Path) -> dict[str, Any]:
    result = run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "assert_model_write_scope.py"),
            "--access-config",
            str(workspace / "model-access-policy.json"),
            "--model-root",
            str(workspace / ".operator" / "model-scope-proof"),
            "--json",
        ],
        cwd=REPO_ROOT,
    )
    payload = json.loads(result.stdout) if result.stdout.strip().startswith("{") else {"status": "failed"}
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or result.stderr.strip() or "accepted write gate failed")
    return payload


def publish_viewer(install_root: Path, workspace: Path, model_root: Path) -> dict[str, Any]:
    publisher = install_root / "package" / "current" / "scripts" / "publish_viewer.py"
    result = run(
        [
            sys.executable,
            str(publisher),
            str(model_root),
            "--workspace",
            str(workspace),
            "--out-dir",
            str(workspace / "viewer"),
            "--module",
            "acquisition",
            "--as-of",
            "2026-12-01",
            "--json",
        ],
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or result.stderr.strip() or "viewer publish failed")
    return json.loads(result.stdout)


def human_request_summary(workspace: Path) -> dict[str, Any]:
    db = workspace / "agent-state" / "operational-store.sqlite"
    if not db.exists():
        return {"open_count": 0, "requests": []}
    with sqlite3.connect(str(db)) as connection:
        rows = connection.execute(
            "select request_id, kind, status, package_id from human_requests order by request_id"
        ).fetchall()
    requests = [
        {"request_id": row[0], "kind": row[1], "status": row[2], "package_id": row[3]}
        for row in rows
    ]
    return {
        "open_count": sum(1 for row in requests if row["status"] == "open"),
        "requests": requests,
    }


def final_status(checks: list[dict[str, str]]) -> str:
    if any(check["status"] == "failed" for check in checks):
        return "failed"
    if any(check["status"] == "blocked" for check in checks):
        return "blocked"
    return "passed"


def append_check(checks: list[dict[str, str]], name: str, status: str, **extra: str) -> None:
    checks.append({"name": name, "status": status, **extra})


def run_fixture(work_dir: Path) -> tuple[int, dict[str, Any]]:
    started_at = utc_timestamp()
    checks: list[dict[str, str]] = []
    host = FixtureHostAdapter()
    install_root = work_dir / "install-root"
    install_root.mkdir(parents=True, exist_ok=True)

    try:
        remote, package_commit = prepare_local_release_repo(work_dir)
        append_check(checks, "local_package_release", "passed", path=str(remote))
        model_root = prepare_model_repo(work_dir, package_commit)
        append_check(checks, "model_repo_support_contract", "passed", path=str(model_root / "PACKAGE_CONTRACT.lock"))
        workspace = bootstrap_workspace(install_root, model_root)
        append_check(checks, "workspace_bootstrap", "passed", path=str(workspace / "workspace-state.json"))
        write_old_install_lock(workspace, remote)

        update = apply_update(install_root, model_root)
        update_proof = verify_installed_package(install_root)
        append_check(checks, "package_update", "passed", path=str(update.get("install_report", "")))
        append_check(checks, "installed_package_verify", "passed", path=str(update_proof.get("install_report", "")))

        host.direct_message("Owner selected ru as company model language.")
        host.group_mention("@business-ontology please record this Zoom link for the fixture meeting.")
        host.owner_answer("Review the generated package before acceptance.")

        telegram = run_telegram_fixture(workspace)
        append_check(checks, "telegram_mtproto_fixture", "passed", path=str(telegram["packet"]["interpretation_packet_path"]))
        meeting = run_meeting_fixture(workspace)
        append_check(checks, "meeting_recording_fixture", "passed", path=str(meeting["packet_path"]))

        resident = run_resident_loop(workspace, model_revision=git(["rev-parse", "--short", "HEAD"], cwd=model_root))
        if resident["packages_written"] < 1:
            raise RuntimeError("resident loop did not write a model-change package")
        package_path = Path(str(resident["package_paths"][0]))
        append_check(checks, "resident_loop_model_change", "passed", path=str(package_path))

        write_gate = run_write_gate(workspace)
        append_check(checks, "accepted_write_gate", "passed")

        viewer = publish_viewer(install_root, workspace, model_root)
        append_check(checks, "official_viewer_publish", "passed", path=str(workspace / "viewer" / "VIEWER_PUBLISH_REPORT.json"))

        source_registry = read_json(workspace / "source-instances.json")
        live_proofs = read_json(workspace / "live-proofs" / "proofs.json")
        requests = human_request_summary(workspace)
        report = {
            "kind": "installedAgentE2EReport",
            "mode": "fixture",
            "status": final_status(checks),
            "started_at": started_at,
            "finished_at": utc_timestamp(),
            "work_dir": str(work_dir),
            "install_root": str(install_root),
            "package_update_proof_path": str(update_proof.get("install_report", "")),
            "workspace_state_path": str(workspace / "workspace-state.json"),
            "selected_model_language": read_json(workspace / "workspace-state.json")["company_model"]["company_model_language"],
            "source_instances_path": str(workspace / "source-instances.json"),
            "source_instances": source_registry["source_instances"],
            "live_proof_ledger_path": str(workspace / "live-proofs" / "proofs.json"),
            "live_proofs": live_proofs["live_proofs"],
            "human_requests": requests,
            "model_change_package_path": str(package_path),
            "accepted_write_gate_result": write_gate,
            "viewer_publish_report_path": str(workspace / "viewer" / "VIEWER_PUBLISH_REPORT.json"),
            "viewer_publish_report": viewer,
            "host_simulation": host.report(),
            "checks": checks,
        }
        return 0, report
    except Exception as exc:
        append_check(checks, "fixture_e2e", "failed")
        return 1, {
            "kind": "installedAgentE2EReport",
            "mode": "fixture",
            "status": "failed",
            "started_at": started_at,
            "finished_at": utc_timestamp(),
            "work_dir": str(work_dir),
            "failure_reason": str(exc),
            "checks": checks,
        }


def run_live(work_dir: Path, live_proof_file: Path | None) -> tuple[int, dict[str, Any]]:
    started_at = utc_timestamp()
    checks: list[dict[str, str]] = []
    if os.environ.get("BUSINESS_ONTOLOGY_E2E_LIVE") != "1":
        append_check(checks, "live_authorization", "blocked", reason="BUSINESS_ONTOLOGY_E2E_LIVE=1 is required")
        return 0, live_report(work_dir, started_at, checks, "blocked")

    workspace_env = os.environ.get("OPENCLAW_WORKSPACE", "")
    if not workspace_env:
        append_check(checks, "openclaw_workspace", "blocked", reason="OPENCLAW_WORKSPACE is not set")
        return 0, live_report(work_dir, started_at, checks, "blocked")
    workspace = Path(workspace_env)
    if not workspace.exists():
        append_check(checks, "openclaw_workspace", "blocked", reason="OPENCLAW_WORKSPACE does not exist")
        return 0, live_report(work_dir, started_at, checks, "blocked")
    append_check(checks, "openclaw_workspace", "passed", path=str(workspace))

    if live_proof_file is None or not live_proof_file.exists():
        append_check(
            checks,
            "host_agent_interaction",
            "blocked",
            reason="provide --live-proof-file with redacted host-agent evidence",
        )
        return 0, live_report(work_dir, started_at, checks, "blocked", workspace=workspace)

    proof = read_json(live_proof_file)
    if proof.get("accepted_model_write_attempted") is True:
        append_check(checks, "accepted_write_safety", "failed", reason="live proof attempted accepted model write")
        return 1, live_report(work_dir, started_at, checks, "failed", workspace=workspace, live_proof=proof)
    append_check(checks, "host_agent_interaction", "passed", path=str(live_proof_file))
    return 0, live_report(work_dir, started_at, checks, "passed", workspace=workspace, live_proof=proof)


def live_report(
    work_dir: Path,
    started_at: str,
    checks: list[dict[str, str]],
    status: str,
    *,
    workspace: Path | None = None,
    live_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "kind": "installedAgentE2EReport",
        "mode": "live",
        "status": status,
        "started_at": started_at,
        "finished_at": utc_timestamp(),
        "work_dir": str(work_dir),
        "checks": checks,
    }
    if workspace is not None:
        report["workspace_state_path"] = str(workspace / "workspace-state.json")
        report["source_instances_path"] = str(workspace / "source-instances.json")
        report["live_proof_ledger_path"] = str(workspace / "live-proofs" / "proofs.json")
    if live_proof is not None:
        report["live_proof"] = redact_live_proof(live_proof)
    return report


def redact_live_proof(proof: dict[str, Any]) -> dict[str, Any]:
    value = redact_sensitive_values(proof)
    if not isinstance(value, dict):
        raise TypeError("live proof must be a JSON object")
    return value


def redact_sensitive_values(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, child in value.items():
            if any(fragment in str(key).lower() for fragment in SENSITIVE_KEY_FRAGMENTS):
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_sensitive_values(child)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_values(item) for item in value]
    return value


def write_reports(work_dir: Path, report: dict[str, Any]) -> Path:
    report_path = work_dir / REPORT_JSON
    write_json_atomic(report_path, report)
    lines = [
        "# Installed Agent E2E Report",
        "",
        f"- mode: {report.get('mode')}",
        f"- status: {report.get('status')}",
        f"- selected model language: {report.get('selected_model_language', '')}",
        f"- package update proof: {report.get('package_update_proof_path', '')}",
        f"- viewer publish report: {report.get('viewer_publish_report_path', '')}",
        "",
        "## Checks",
    ]
    for check in report.get("checks", []):
        if isinstance(check, dict):
            detail = check.get("path") or check.get("reason") or ""
            lines.append(f"- {check.get('status')} - {check.get('name')} {detail}".rstrip())
    if report.get("failure_reason"):
        lines.extend(["", "## Failure", str(report["failure_reason"])])
    md_path = work_dir / REPORT_MD
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report_path


def default_work_dir(mode: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"business-ontology-{mode}-e2e-"))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run installed-agent E2E proof.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture-only", action="store_true", help="Run offline fixture E2E.")
    mode.add_argument("--live", action="store_true", help="Write live E2E proof or blocked report.")
    parser.add_argument("--work-dir", type=Path, help="Directory for reports and fixture install.")
    parser.add_argument("--live-proof-file", type=Path, help="Redacted live host-agent proof JSON.")
    parser.add_argument("--json", action="store_true", help="Print report JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    work_dir = (args.work_dir or default_work_dir("live" if args.live else "fixture")).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    if args.live:
        code, report = run_live(work_dir, args.live_proof_file)
    else:
        code, report = run_fixture(work_dir)
    report_path = write_reports(work_dir, report)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(report_path)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Migrate one v0.10.6 workspace to the v0.11.0 behavior contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
from typing import Any

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from package_update_common import (  # noqa: E402
    UpdateLock,
    UpdateLockBusy,
    utc_timestamp,
    write_json_atomic,
)


SOURCE_VERSION = "0.10.6"
TARGET_VERSION = "0.11.0"
COMPATIBLE_PACKAGE_VERSIONS = {"0.11.0", "0.11.1", "0.11.2", "0.11.3", "0.11.4"}
MIGRATION_ID = "workspace-v0.11.0"
PLUGIN_ID = "business-ontology-owner-chat-guard"
BEHAVIOR_TEMPLATES = {
    "COMMUNICATION_POLICY.md": "COMMUNICATION_POLICY.md.tpl",
    "REVIEW_PROTOCOL.md": "REVIEW_PROTOCOL.md.tpl",
    "SOUL.md": "SOUL.md.tpl",
    "TOOLS.md": "TOOLS.md.tpl",
}
EXPECTED_HEARTBEAT: dict[str, object] = {
    "every": "2h",
    "target": "none",
    "directPolicy": "block",
    "isolatedSession": True,
    "lightContext": True,
}
MANAGED_BEGIN = "<!-- BEGIN BUSINESS-ONTOLOGY MANAGED: scheduling-v0.11.0 -->"
MANAGED_END = "<!-- END BUSINESS-ONTOLOGY MANAGED: scheduling-v0.11.0 -->"


class MigrationError(RuntimeError):
    """A safe migration precondition or verification failed."""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MigrationError(f"required file is missing: {path.name}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrationError(f"required JSON is invalid: {path.name}") from exc
    if not isinstance(payload, dict):
        raise MigrationError(f"required JSON is not an object: {path.name}")
    return payload


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(content.rstrip() + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _migration_root(workspace: Path) -> Path:
    return workspace / "agent-state" / "migrations" / "v0.11.0"


def _result_path(workspace: Path) -> Path:
    return _migration_root(workspace) / "result.json"


def _backup_root(workspace: Path) -> Path:
    return _migration_root(workspace) / "backup"


def _runtime_config_path(workspace: Path) -> Path:
    for name in ("runtime-config.json", "runtime-config.example.json"):
        path = workspace / name
        if path.is_file():
            return path
    raise MigrationError("runtime config is missing")


def _meeting_databases(workspace: Path) -> list[Path]:
    candidates = [
        workspace / "meeting-recordings.sqlite3",
        workspace / "agent-state" / "meeting-recordings.sqlite3",
    ]
    config_path = _runtime_config_path(workspace)
    config = _read_object(config_path)
    for key in ("meeting_recording_db", "meeting_recording_db_path"):
        value = config.get(key)
        if isinstance(value, str) and value:
            path = Path(value)
            resolved = path.resolve() if path.is_absolute() else (workspace / path).resolve()
            try:
                resolved.relative_to(workspace.resolve())
            except ValueError as exc:
                raise MigrationError(f"{key} escapes workspace") from exc
            candidates.append(resolved)
    return sorted({path for path in candidates if path.is_file()})


def _validate_source(workspace: Path, *, dry_run: bool) -> dict[str, Any]:
    if not workspace.is_dir():
        raise MigrationError("workspace does not exist")
    lock = _read_object(workspace / "PACKAGE_VERSION.lock")
    current = str(lock.get("current_version") or "")
    previous = str(lock.get("previous_version") or "")
    supported = current == SOURCE_VERSION or (
        current in COMPATIBLE_PACKAGE_VERSIONS
        and previous in ({"", SOURCE_VERSION} | COMPATIBLE_PACKAGE_VERSIONS)
    )
    if not supported:
        raise MigrationError(
            f"unsupported package transition: current={current or 'missing'} previous={previous or 'missing'}"
        )
    if not dry_run and current not in COMPATIBLE_PACKAGE_VERSIONS:
        raise MigrationError(
            "install a package compatible with the v0.11.0 workspace migration "
            "before applying it"
        )
    if not (workspace / "INTERACTION_CONTRACT.md").is_file():
        raise MigrationError("INTERACTION_CONTRACT.md is missing")
    _runtime_config_path(workspace)
    return lock


def _managed_block(agent_id: str) -> str:
    return f"""{MANAGED_BEGIN}
## v0.11.0 scheduling boundary

- Silent system heartbeat: every 2h, target none, direct messages blocked,
  isolated session, and HEARTBEAT.md-only context.
- Owner reminder: one deterministic command cron named
  `business-ontology:{agent_id}:owner-reminder`.
- Reminder creation requires explicit owner confirmation of cadence/time, IANA
  timezone, channel, delivery target, and quiet window.
- The reminder re-reads current open requests and health. An unchanged request
  returns in the next cadence window. OpenClaw owns delivery and retry state.
- Only the exact package-owned reminder declaration may be reconciled. Source,
  drift, Bitrix, and other agents' jobs are outside this migration.
{MANAGED_END}"""


def _patch_interaction_contract(text: str, agent_id: str) -> str:
    block = _managed_block(agent_id)
    if MANAGED_BEGIN not in text:
        return text.rstrip() + "\n\n" + block + "\n"
    before, remainder = text.split(MANAGED_BEGIN, 1)
    if MANAGED_END not in remainder:
        raise MigrationError("interaction contract has an incomplete managed scheduling block")
    _, after = remainder.split(MANAGED_END, 1)
    return before.rstrip() + "\n\n" + block + after


def _heartbeat_template(agent_id: str) -> str:
    template = (REPO_ROOT / "templates" / "workspace" / "HEARTBEAT.md.tpl").read_text(
        encoding="utf-8"
    )
    return template.replace("{{AGENT_ID}}", agent_id).rstrip() + "\n"


def _agent_name(workspace: Path, agent_id: str) -> str:
    soul = workspace / "SOUL.md"
    if soul.is_file():
        match = re.search(r"^Identity:\s*(.+?)\.\s*$", soul.read_text(encoding="utf-8"), re.MULTILINE)
        if match:
            return match.group(1).strip()
    return agent_id


def _behavior_content(workspace: Path, agent_id: str) -> dict[Path, str]:
    values = {"AGENT_NAME": _agent_name(workspace, agent_id), "AGENT_ID": agent_id}
    rendered: dict[Path, str] = {}
    for target_name, template_name in BEHAVIOR_TEMPLATES.items():
        text = (REPO_ROOT / "templates" / "workspace" / template_name).read_text(encoding="utf-8")
        for key, value in values.items():
            text = text.replace("{{" + key + "}}", value)
        rendered[workspace / target_name] = text.rstrip() + "\n"
    return rendered


def _default_scheduling(agent_id: str, generated_at: str) -> dict[str, object]:
    declaration = f"business-ontology:{agent_id}:owner-reminder"
    return {
        "schema_version": 1,
        "managed_by": "business-ontology",
        "agent_id": agent_id,
        "heartbeat": dict(EXPECTED_HEARTBEAT),
        "owner_reminder": {
            "configured": False,
            "requires_owner_confirmation": True,
            "job_name": declaration,
            "declaration_key": declaration,
            "cadence": None,
            "cron": None,
            "timezone": None,
            "channel": None,
            "delivery_target": None,
            "quiet_window": None,
            "account_id": None,
            "language": "pending-owner-selection",
            "confirmation_ref": None,
            "confirmed_at": None,
        },
        "owner_chat_guard": {
            "plugin_id": PLUGIN_ID,
            "enabled": True,
            "allow_conversation_access": True,
            "agent_id": agent_id,
            "required_hooks": ["before_agent_finalize", "message_sending"],
        },
        "openclaw": {
            "launcher": None,
            "node_bin_dir": None,
            "verified": False,
        },
        "generated_at": generated_at,
    }


def _migrated_scheduling(workspace: Path, agent_id: str, generated_at: str) -> dict[str, object]:
    path = workspace / "agent-state" / "managed-scheduling.json"
    if not path.is_file():
        return _default_scheduling(agent_id, generated_at)
    existing = _read_object(path)
    reminder = existing.get("owner_reminder")
    if not isinstance(reminder, dict):
        reminder = {}
    declaration = f"business-ontology:{agent_id}:owner-reminder"
    migrated = _default_scheduling(agent_id, generated_at)
    migrated_reminder = migrated["owner_reminder"]
    assert isinstance(migrated_reminder, dict)
    for key in (
        "configured",
        "requires_owner_confirmation",
        "cadence",
        "cron",
        "timezone",
        "channel",
        "delivery_target",
        "quiet_window",
        "account_id",
        "language",
        "confirmation_ref",
        "confirmed_at",
    ):
        if key in reminder:
            migrated_reminder[key] = reminder[key]
    migrated_reminder["job_name"] = declaration
    migrated_reminder["declaration_key"] = declaration
    if migrated_reminder.get("configured") is not True:
        migrated_reminder["configured"] = False
        migrated_reminder["requires_owner_confirmation"] = True
    openclaw = existing.get("openclaw")
    if isinstance(openclaw, dict):
        migrated["openclaw"] = {
            "launcher": openclaw.get("launcher"),
            "node_bin_dir": openclaw.get("node_bin_dir"),
            "verified": openclaw.get("verified") is True,
        }
    return migrated


def _ensure_gitignore(text: str) -> str:
    rules = {line.strip() for line in text.splitlines()}
    if "raw/" in rules or "/raw/" in rules:
        return text.rstrip() + "\n"
    return text.rstrip() + ("\n" if text else "") + "/raw/\n"


def _raw_roots(workspace: Path) -> list[tuple[Path, Path]]:
    telegram_root = workspace / "source-exports" / "telegram"
    if not telegram_root.is_dir():
        telegram_root = workspace / "source-exports"
    roots: list[tuple[Path, Path]] = []
    if telegram_root.is_dir():
        roots.append((telegram_root, workspace / "raw" / "telegram"))
    meetings_root = workspace / "source-material" / "meeting-transcripts"
    if meetings_root.is_dir():
        roots.append((meetings_root, workspace / "raw" / "meetings"))
    return roots


def _raw_copy_plan(workspace: Path) -> list[tuple[Path, Path]]:
    plan: list[tuple[Path, Path]] = []
    for source_root, target_root in _raw_roots(workspace):
        for source in sorted(path for path in source_root.rglob("*") if path.is_file()):
            relative = source.relative_to(source_root)
            if len(relative.parts) == 1:
                relative = Path(f"legacy-v{SOURCE_VERSION}") / relative
            plan.append((source, target_root / relative))
    return plan


def _path_mapping(workspace: Path, plan: list[tuple[Path, Path]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for source, target in plan:
        source_relative = source.relative_to(workspace)
        target_relative = target.relative_to(workspace)
        mapping[str(source)] = str(target)
        mapping[str(source_relative)] = str(target_relative)
        mapping[f"./{source_relative}"] = f"./{target_relative}"
    for source_root, target_root in _raw_roots(workspace):
        source_relative = source_root.relative_to(workspace)
        target_relative = target_root.relative_to(workspace)
        mapping[str(source_root)] = str(target_root)
        mapping[str(source_relative)] = str(target_relative)
        mapping[f"./{source_relative}"] = f"./{target_relative}"
    return mapping


def _rewrite_values(value: object, mapping: dict[str, str]) -> tuple[object, int]:
    if isinstance(value, str):
        replacement = mapping.get(value)
        return (replacement, 1) if replacement is not None else (value, 0)
    if isinstance(value, list):
        rewritten: list[object] = []
        count = 0
        for item in value:
            new_item, changed = _rewrite_values(item, mapping)
            rewritten.append(new_item)
            count += changed
        return rewritten, count
    if isinstance(value, dict):
        rewritten_object: dict[str, object] = {}
        count = 0
        for key, item in value.items():
            new_item, changed = _rewrite_values(item, mapping)
            rewritten_object[str(key)] = new_item
            count += changed
        return rewritten_object, count
    return value, 0


def _copy_raw(plan: list[tuple[Path, Path]]) -> dict[str, object]:
    source_hashes = {str(source): _sha256(source) for source, _ in plan}
    for source, target in plan:
        if target.exists() and _sha256(target) != source_hashes[str(source)]:
            raise MigrationError(f"raw target collision: {target.name}")
    copied = 0
    for source, target in plan:
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied += 1
        if _sha256(target) != source_hashes[str(source)]:
            raise MigrationError(f"raw reconciliation failed: {target.name}")
        os.chmod(target, 0o600)
        raw_root = next((parent for parent in target.parents if parent.name == "raw"), None)
        if raw_root is None:
            raise MigrationError("raw target is outside the configured raw root")
        current = target.parent
        while True:
            os.chmod(current, 0o700)
            if current == raw_root:
                break
            current = current.parent
    return {
        "legacy_file_count": len(plan),
        "copied_file_count": copied,
        "reconciled_file_count": len(plan),
        "source_hashes_digest": hashlib.sha256(
            "\n".join(sorted(source_hashes.values())).encode("utf-8")
        ).hexdigest(),
        "legacy_originals_preserved": True,
    }


def _backup_paths(workspace: Path) -> list[Path]:
    paths = [
        workspace / "INTERACTION_CONTRACT.md",
        workspace / "HEARTBEAT.md",
        workspace / ".gitignore",
        _runtime_config_path(workspace),
        workspace / "agent-state" / "managed-scheduling.json",
        workspace / "agent-state" / "system-health.json",
        workspace / "source-instances.json",
        workspace / "live-proofs" / "proofs.json",
        workspace / "PACKAGE_INSTALL_REPORT.json",
    ]
    paths.extend(workspace / name for name in BEHAVIOR_TEMPLATES)
    paths.extend(_meeting_databases(workspace))
    return sorted(set(paths))


def _create_backup(workspace: Path, paths: list[Path], host: dict[str, object] | None) -> Path:
    root = _backup_root(workspace)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        manifest = _read_object(manifest_path)
        if host is not None and not isinstance(manifest.get("host"), dict):
            manifest["host"] = host
            manifest["host_captured_at"] = utc_timestamp()
            write_json_atomic(manifest_path, manifest)
        os.chmod(manifest_path, 0o600)
        return manifest_path
    files_root = root / "files"
    files_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(files_root, 0o700)
    records: list[dict[str, object]] = []
    for path in paths:
        relative = path.relative_to(workspace)
        exists = path.is_file()
        record: dict[str, object] = {"path": str(relative), "existed": exists}
        if exists:
            destination = files_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            os.chmod(destination, 0o600)
            parent = destination.parent
            while True:
                os.chmod(parent, 0o700)
                if parent == root:
                    break
                parent = parent.parent
            record["sha256"] = _sha256(path)
            record["mode"] = path.stat().st_mode & 0o777
        records.append(record)
    write_json_atomic(
        manifest_path,
        {
            "migration_id": MIGRATION_ID,
            "source_version": SOURCE_VERSION,
            "target_version": TARGET_VERSION,
            "created_at": utc_timestamp(),
            "files": records,
            "host": host,
            "raw_bodies_included": False,
        },
    )
    os.chmod(manifest_path, 0o600)
    return manifest_path


def _restore_backup(workspace: Path) -> dict[str, object]:
    root = _backup_root(workspace)
    manifest = _read_object(root / "manifest.json")
    records = manifest.get("files")
    if not isinstance(records, list):
        raise MigrationError("backup manifest has no file inventory")
    restored = 0
    removed = 0
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise MigrationError("backup manifest file record is invalid")
        target = workspace / str(record["path"])
        if record.get("existed") is True:
            source = root / "files" / str(record["path"])
            if not source.is_file() or _sha256(source) != record.get("sha256"):
                raise MigrationError(f"backup verification failed: {record['path']}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            mode = record.get("mode")
            if isinstance(mode, int):
                os.chmod(target, mode)
            restored += 1
        elif target.exists():
            target.unlink()
            removed += 1
    return {"restored_files": restored, "removed_created_files": removed}


def _rewrite_json_file(path: Path, mapping: dict[str, str]) -> int:
    if not path.is_file():
        return 0
    payload = _read_object(path)
    rewritten, count = _rewrite_values(payload, mapping)
    if count:
        assert isinstance(rewritten, dict)
        write_json_atomic(path, rewritten)
    return count


def _rewrite_meeting_database(path: Path, mapping: dict[str, str]) -> int:
    connection = sqlite3.connect(path)
    try:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meeting_recording_jobs'"
        ).fetchone()
        if table is None:
            return 0
        rows = connection.execute(
            "SELECT job_id, packet_path FROM meeting_recording_jobs WHERE packet_path IS NOT NULL"
        ).fetchall()
        changed = 0
        with connection:
            for job_id, packet_path in rows:
                replacement = mapping.get(str(packet_path))
                if replacement is not None and replacement != packet_path:
                    connection.execute(
                        "UPDATE meeting_recording_jobs SET packet_path = ? WHERE job_id = ?",
                        (replacement, job_id),
                    )
                    changed += 1
        return changed
    finally:
        connection.close()


def _openclaw_json(binary: str, node_bin_dir: str | None, args: list[str]) -> object:
    try:
        result = subprocess.run(
            [binary, *args],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
            env=_openclaw_env(node_bin_dir),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MigrationError(f"OpenClaw command failed: {type(exc).__name__}") from exc
    if result.returncode != 0:
        raise MigrationError(f"OpenClaw command failed with exit {result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MigrationError("OpenClaw returned invalid JSON") from exc


def _agents(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        payload = payload.get("agents", payload.get("data", []))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _objects(payload: object, key: str) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        payload = payload.get(key, payload.get("data", []))
        if isinstance(payload, dict):
            payload = payload.get(key, [])
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _openclaw_env(node_bin_dir: str | None) -> dict[str, str]:
    environment = os.environ.copy()
    if node_bin_dir:
        environment["PATH"] = f"{node_bin_dir}{os.pathsep}{environment.get('PATH', '')}"
    return environment


def _openclaw_mutate(binary: str, node_bin_dir: str | None, args: list[str]) -> None:
    result = subprocess.run(
        [binary, *args],
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
        env=_openclaw_env(node_bin_dir),
    )
    if result.returncode != 0:
        raise MigrationError(f"OpenClaw mutation failed with exit {result.returncode}: {args[0]}")


def _plugin_config(binary: str, node_bin_dir: str | None) -> dict[str, Any]:
    payload = _openclaw_json(binary, node_bin_dir, ["config", "get", "plugins", "--json"])
    return payload if isinstance(payload, dict) else {}


def _plugin_is_installed(binary: str, node_bin_dir: str | None) -> bool:
    payload = _openclaw_json(binary, node_bin_dir, ["plugins", "list", "--json"])
    return any(plugin.get("id") == PLUGIN_ID for plugin in _objects(payload, "plugins"))


def _cron_jobs(binary: str, node_bin_dir: str | None) -> list[dict[str, Any]]:
    payload = _openclaw_json(binary, node_bin_dir, ["cron", "list", "--all", "--json"])
    return _objects(payload, "jobs")


def _declaration(job: dict[str, Any]) -> str:
    return str(job.get("declarationKey") or job.get("declaration_key") or "")


def _managed_jobs(jobs: list[dict[str, Any]], declaration: str) -> list[dict[str, Any]]:
    return [
        job
        for job in jobs
        if _declaration(job) == declaration or str(job.get("name") or "") == declaration
    ]


def _host_inventory(binary: str, node_bin_dir: str | None, agent_id: str) -> dict[str, object]:
    agents = _agents(
        _openclaw_json(binary, node_bin_dir, ["config", "get", "agents.list", "--json"])
    )
    matches = [(index, agent) for index, agent in enumerate(agents) if agent.get("id") == agent_id]
    if len(matches) != 1:
        raise MigrationError("OpenClaw must contain exactly one matching agent id")
    index, agent = matches[0]
    heartbeat = agent.get("heartbeat")
    plugins = _plugin_config(binary, node_bin_dir)
    allow = plugins.get("allow") if isinstance(plugins.get("allow"), list) else []
    entries = plugins.get("entries") if isinstance(plugins.get("entries"), dict) else {}
    declaration = f"business-ontology:{agent_id}:owner-reminder"
    return {
        "agent_index": index,
        "heartbeat_existed": isinstance(heartbeat, dict),
        "heartbeat": heartbeat if isinstance(heartbeat, dict) else None,
        "plugin_installed": _plugin_is_installed(binary, node_bin_dir),
        "plugin_allow": list(allow),
        "plugin_entry_existed": PLUGIN_ID in entries,
        "plugin_entry": entries.get(PLUGIN_ID),
        "managed_reminder_jobs": _managed_jobs(_cron_jobs(binary, node_bin_dir), declaration),
    }


def _verify_owner_chat_guard(binary: str, node_bin_dir: str | None, agent_id: str) -> None:
    if not _plugin_is_installed(binary, node_bin_dir):
        raise MigrationError("owner chat guard is not installed")
    plugins = _plugin_config(binary, node_bin_dir)
    allow = plugins.get("allow") if isinstance(plugins.get("allow"), list) else []
    entries = plugins.get("entries") if isinstance(plugins.get("entries"), dict) else {}
    entry = entries.get(PLUGIN_ID) if isinstance(entries.get(PLUGIN_ID), dict) else {}
    hooks = entry.get("hooks") if isinstance(entry.get("hooks"), dict) else {}
    config = entry.get("config") if isinstance(entry.get("config"), dict) else {}
    checks = {
        "allow": PLUGIN_ID in allow,
        "enabled": entry.get("enabled") is True,
        "conversation-access": hooks.get("allowConversationAccess") is True,
        "agent-filter": agent_id in (config.get("agentIds") or []),
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise MigrationError("owner chat guard config postflight failed: " + ",".join(failed))
    inspected = _openclaw_json(
        binary,
        node_bin_dir,
        ["plugins", "inspect", PLUGIN_ID, "--runtime", "--json"],
    )
    serialized = json.dumps(inspected, sort_keys=True)
    for hook in ("before_agent_finalize", "message_sending"):
        if hook not in serialized:
            raise MigrationError(f"owner chat guard runtime inspection is missing {hook}")


def _merge_owner_chat_guard(
    binary: str,
    node_bin_dir: str | None,
    agent_id: str,
) -> None:
    source = REPO_ROOT / "adapters" / "openclaw" / "plugins" / "owner-chat-guard"
    # Always refresh the installed copy so a package update cannot leave an
    # older guard active. Without agentIds the plugin is inert, which makes the
    # install-before-configure sequence safe on a clean host.
    _openclaw_mutate(
        binary,
        node_bin_dir,
        ["plugins", "install", str(source), "--force"],
    )
    plugins = _plugin_config(binary, node_bin_dir)
    allow = plugins.get("allow") if isinstance(plugins.get("allow"), list) else []
    merged_allow = list(dict.fromkeys([*(str(item) for item in allow), PLUGIN_ID]))
    entries = plugins.get("entries") if isinstance(plugins.get("entries"), dict) else {}
    existing = entries.get(PLUGIN_ID) if isinstance(entries.get(PLUGIN_ID), dict) else {}
    existing_hooks = existing.get("hooks") if isinstance(existing.get("hooks"), dict) else {}
    existing_config = existing.get("config") if isinstance(existing.get("config"), dict) else {}
    existing_agent_ids = (
        existing_config.get("agentIds") if isinstance(existing_config.get("agentIds"), list) else []
    )
    entry = dict(existing)
    entry["enabled"] = True
    entry["hooks"] = {**existing_hooks, "allowConversationAccess": True}
    entry["config"] = {
        **existing_config,
        "agentIds": list(dict.fromkeys([*(str(item) for item in existing_agent_ids), agent_id])),
    }
    _openclaw_mutate(
        binary,
        node_bin_dir,
        ["config", "set", "plugins.allow", json.dumps(merged_allow), "--strict-json"],
    )
    _openclaw_mutate(
        binary,
        node_bin_dir,
        [
            "config",
            "set",
            f"plugins.entries.{PLUGIN_ID}",
            json.dumps(entry, sort_keys=True),
            "--strict-json",
        ],
    )


def _reminder_args(
    workspace: Path,
    agent_id: str,
    reminder: dict[str, Any],
) -> list[str]:
    declaration = f"business-ontology:{agent_id}:owner-reminder"
    required = (
        "cron",
        "timezone",
        "channel",
        "delivery_target",
        "quiet_window",
        "language",
        "confirmation_ref",
        "confirmed_at",
    )
    if any(not reminder.get(key) for key in required):
        raise MigrationError("configured owner reminder is missing required owner-confirmed fields")
    installed_package_root = Path.home() / ".openclaw" / "agents" / agent_id / "agent" / "package" / "current"
    command_argv = [
        "python3",
        str(installed_package_root / "scripts" / "owner_reminder.py"),
        "--workspace",
        str(workspace),
        "--agent-id",
        agent_id,
    ]
    args = ["cron", "add"]
    args.extend(
        [
            "--name",
            declaration,
            "--declaration-key",
            declaration,
            "--agent",
            agent_id,
            "--cron",
            str(reminder["cron"]),
            "--tz",
            str(reminder["timezone"]),
            "--session",
            "isolated",
            "--command-argv",
            json.dumps(command_argv),
            "--command-cwd",
            str(workspace),
            "--announce",
            "--channel",
            str(reminder["channel"]),
            "--to",
            str(reminder["delivery_target"]),
        ]
    )
    if reminder.get("account_id"):
        args.extend(["--account", str(reminder["account_id"])])
    return args


def _reconcile_owner_reminder(
    binary: str,
    node_bin_dir: str | None,
    workspace: Path,
    agent_id: str,
    scheduling: dict[str, object],
) -> None:
    reminder = scheduling.get("owner_reminder")
    if not isinstance(reminder, dict):
        raise MigrationError("managed scheduling has no owner reminder contract")
    declaration = f"business-ontology:{agent_id}:owner-reminder"
    matches = _managed_jobs(_cron_jobs(binary, node_bin_dir), declaration)
    if any(_declaration(job) != declaration for job in matches):
        raise MigrationError("legacy reminder name conflicts with the managed declaration key")
    if reminder.get("configured") is not True:
        if matches:
            raise MigrationError("owner reminder exists without an owner-confirmed schedule")
        return
    _openclaw_mutate(
        binary,
        node_bin_dir,
        _reminder_args(workspace, agent_id, reminder),
    )


def _job_id(job: dict[str, Any]) -> str:
    return str(job.get("id") or job.get("jobId") or "")


def _remove_managed_reminders(
    binary: str,
    node_bin_dir: str | None,
    agent_id: str,
    previous_jobs: object,
) -> None:
    if not isinstance(previous_jobs, list) or any(not isinstance(item, dict) for item in previous_jobs):
        raise MigrationError("backup managed reminder inventory is invalid")
    if previous_jobs:
        raise MigrationError("v0.10.6 backup unexpectedly contains a v0.11 managed reminder")
    declaration = f"business-ontology:{agent_id}:owner-reminder"
    for job in _managed_jobs(_cron_jobs(binary, node_bin_dir), declaration):
        identifier = _job_id(job)
        if not identifier:
            raise MigrationError("current managed reminder has no removable id")
        _openclaw_mutate(binary, node_bin_dir, ["cron", "remove", identifier])


def _restore_owner_chat_guard(
    binary: str,
    node_bin_dir: str | None,
    host: dict[str, object],
) -> None:
    old_allow = host.get("plugin_allow")
    if not isinstance(old_allow, list):
        raise MigrationError("backup plugin allow inventory is invalid")
    _openclaw_mutate(
        binary,
        node_bin_dir,
        ["config", "set", "plugins.allow", json.dumps(old_allow), "--strict-json"],
    )
    if host.get("plugin_entry_existed") is True:
        entry = host.get("plugin_entry")
        if not isinstance(entry, dict):
            raise MigrationError("backup plugin entry inventory is invalid")
        _openclaw_mutate(
            binary,
            node_bin_dir,
            [
                "config",
                "set",
                f"plugins.entries.{PLUGIN_ID}",
                json.dumps(entry, sort_keys=True),
                "--strict-json",
            ],
        )
    else:
        _openclaw_mutate(binary, node_bin_dir, ["config", "unset", f"plugins.entries.{PLUGIN_ID}"])
    if host.get("plugin_installed") is not True:
        _openclaw_mutate(binary, node_bin_dir, ["plugins", "uninstall", PLUGIN_ID, "--force"])


def _set_host_heartbeat(
    binary: str,
    node_bin_dir: str | None,
    agent_id: str,
    heartbeat: dict[str, object] | None,
) -> None:
    agents = _agents(
        _openclaw_json(binary, node_bin_dir, ["config", "get", "agents.list", "--json"])
    )
    indexes = [index for index, agent in enumerate(agents) if agent.get("id") == agent_id]
    if len(indexes) != 1:
        raise MigrationError("OpenClaw agent index changed or is ambiguous")
    path = f"agents.list[{indexes[0]}].heartbeat"
    if heartbeat is None:
        _openclaw_mutate(binary, node_bin_dir, ["config", "unset", path])
    else:
        _openclaw_mutate(
            binary,
            node_bin_dir,
            ["config", "set", path, json.dumps(heartbeat, sort_keys=True), "--strict-json"],
        )


def _verify_host_heartbeat(binary: str, node_bin_dir: str | None, agent_id: str) -> None:
    agents = _agents(
        _openclaw_json(binary, node_bin_dir, ["config", "get", "agents.list", "--json"])
    )
    matches = [agent for agent in agents if agent.get("id") == agent_id]
    heartbeat = matches[0].get("heartbeat") if len(matches) == 1 else None
    if not isinstance(heartbeat, dict) or any(
        heartbeat.get(key) != value for key, value in EXPECTED_HEARTBEAT.items()
    ):
        raise MigrationError("OpenClaw heartbeat postflight failed")


def _activate_host(
    binary: str,
    node_bin_dir: str | None,
    workspace: Path,
    agent_id: str,
    scheduling: dict[str, object],
    host_inventory: dict[str, object],
) -> None:
    # Reconcile the declaration first so an unconfirmed pre-existing reminder
    # fails before any other host mutation.
    _reconcile_owner_reminder(binary, node_bin_dir, workspace, agent_id, scheduling)
    heartbeat = host_inventory.get("heartbeat")
    merged_heartbeat = dict(heartbeat) if isinstance(heartbeat, dict) else {}
    merged_heartbeat.update(EXPECTED_HEARTBEAT)
    _set_host_heartbeat(binary, node_bin_dir, agent_id, merged_heartbeat)
    _merge_owner_chat_guard(
        binary,
        node_bin_dir,
        agent_id,
    )
    _verify_host_heartbeat(binary, node_bin_dir, agent_id)
    _verify_owner_chat_guard(binary, node_bin_dir, agent_id)


def _restore_host(binary: str, node_bin_dir: str | None, agent_id: str, workspace: Path) -> None:
    manifest = _read_object(_backup_root(workspace) / "manifest.json")
    host = manifest.get("host")
    if not isinstance(host, dict):
        raise MigrationError("backup has no OpenClaw host inventory")
    _remove_managed_reminders(
        binary,
        node_bin_dir,
        agent_id,
        host.get("managed_reminder_jobs"),
    )
    _restore_owner_chat_guard(binary, node_bin_dir, host)
    heartbeat = host.get("heartbeat") if host.get("heartbeat_existed") is True else None
    _set_host_heartbeat(
        binary,
        node_bin_dir,
        agent_id,
        heartbeat if isinstance(heartbeat, dict) else None,
    )


def _already_current(workspace: Path, agent_id: str, plan: list[tuple[Path, Path]]) -> bool:
    result_path = _result_path(workspace)
    if not result_path.is_file():
        return False
    result = _read_object(result_path)
    if result.get("status") != "migrated" or result.get("agent_id") != agent_id:
        return False
    heartbeat_path = workspace / "HEARTBEAT.md"
    if not heartbeat_path.is_file() or _heartbeat_template(agent_id) != heartbeat_path.read_text(encoding="utf-8"):
        return False
    for path, content in _behavior_content(workspace, agent_id).items():
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            return False
    if MANAGED_BEGIN not in (workspace / "INTERACTION_CONTRACT.md").read_text(encoding="utf-8"):
        return False
    scheduling = _read_object(workspace / "agent-state" / "managed-scheduling.json")
    heartbeat = scheduling.get("heartbeat")
    if not isinstance(heartbeat, dict) or any(
        heartbeat.get(key) != value for key, value in EXPECTED_HEARTBEAT.items()
    ):
        return False
    declaration = f"business-ontology:{agent_id}:owner-reminder"
    reminder = scheduling.get("owner_reminder")
    guard = scheduling.get("owner_chat_guard")
    if not isinstance(reminder, dict) or any(
        reminder.get(key) != declaration for key in ("job_name", "declaration_key")
    ):
        return False
    if not isinstance(guard, dict) or any(
        (
            guard.get("plugin_id") != PLUGIN_ID,
            guard.get("enabled") is not True,
            guard.get("allow_conversation_access") is not True,
            guard.get("agent_id") != agent_id,
        )
    ):
        return False
    config = _read_object(_runtime_config_path(workspace))
    if config.get("raw_source_root") != "raw" or config.get("raw_source_policy") != "private-configured-raw-root-only":
        return False
    for directory in (workspace / "raw", workspace / "raw" / "telegram", workspace / "raw" / "meetings"):
        if not directory.is_dir() or directory.stat().st_mode & 0o777 != 0o700:
            return False
    return all(target.is_file() and _sha256(source) == _sha256(target) for source, target in plan)


def _postflight(
    workspace: Path,
    agent_id: str,
    *,
    openclaw_bin: str | None,
    openclaw_node_bin_dir: str | None,
    host_applied: bool,
) -> dict[str, object]:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "system_heartbeat.py"),
        "--workspace",
        str(workspace),
        "--agent-id",
        agent_id,
    ]
    if openclaw_bin:
        command.extend(["--openclaw-bin", openclaw_bin])
    if openclaw_node_bin_dir:
        command.extend(["--openclaw-node-bin-dir", openclaw_node_bin_dir])
    if not host_applied:
        command.append("--skip-openclaw-probe")
    result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=60)
    if result.returncode != 0:
        raise MigrationError("system heartbeat postflight failed")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MigrationError("system heartbeat postflight returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise MigrationError("system heartbeat postflight returned a non-object")
    if host_applied and payload.get("overall_status") != "ok":
        raise MigrationError("strict installed-agent postflight is degraded")
    return payload


def _dry_run_payload(
    workspace: Path,
    agent_id: str,
    source_lock: dict[str, Any],
    raw_plan: list[tuple[Path, Path]],
    *,
    apply_openclaw: bool,
) -> dict[str, object]:
    return {
        "status": "dry-run",
        "migration_id": MIGRATION_ID,
        "agent_id": agent_id,
        "source_version": str(source_lock.get("current_version") or ""),
        "target_version": TARGET_VERSION,
        "workspace_changes": [
            "interaction managed block",
            "HEARTBEAT.md",
            "managed scheduling state",
            "system health snapshot",
            "private raw root and Git exclusion",
            "raw locator references",
            "package install report migration result",
        ],
        "raw_copy_file_count": len(raw_plan),
        "raw_originals_will_be_preserved": True,
        "heartbeat": dict(EXPECTED_HEARTBEAT),
        "owner_reminder": "owner-confirmation-required-before-cron",
        "openclaw_apply_requested": apply_openclaw,
        "delivery_target_in_output": False,
    }


def _apply(
    workspace: Path,
    agent_id: str,
    *,
    openclaw_bin: str | None,
    openclaw_node_bin_dir: str | None,
    apply_openclaw: bool,
) -> dict[str, object]:
    raw_plan = _raw_copy_plan(workspace)
    workspace_current = _already_current(workspace, agent_id, raw_plan)
    if workspace_current and not apply_openclaw:
        return {
            "status": "already-current",
            "migration_id": MIGRATION_ID,
            "agent_id": agent_id,
            "target_version": TARGET_VERSION,
            "changed": False,
        }

    timestamp = utc_timestamp()
    if apply_openclaw and not openclaw_bin:
        raise MigrationError("--apply-openclaw requires a verified --openclaw-bin launcher")
    host_inventory = (
        _host_inventory(openclaw_bin, openclaw_node_bin_dir, agent_id)
        if apply_openclaw and openclaw_bin
        else None
    )
    backup_manifest = _create_backup(workspace, _backup_paths(workspace), host_inventory)
    mapping = _path_mapping(workspace, raw_plan)
    for path, content in _behavior_content(workspace, agent_id).items():
        _write_text_atomic(path, content)
    interaction_path = workspace / "INTERACTION_CONTRACT.md"
    interaction = interaction_path.read_text(encoding="utf-8")
    _write_text_atomic(interaction_path, _patch_interaction_contract(interaction, agent_id))
    _write_text_atomic(workspace / "HEARTBEAT.md", _heartbeat_template(agent_id))
    scheduling = _migrated_scheduling(workspace, agent_id, timestamp)
    if apply_openclaw:
        scheduling["openclaw"] = {
            "launcher": openclaw_bin,
            "node_bin_dir": openclaw_node_bin_dir,
            "verified": True,
        }
    write_json_atomic(workspace / "agent-state" / "managed-scheduling.json", scheduling)
    os.chmod(workspace / "agent-state" / "managed-scheduling.json", 0o600)
    gitignore_path = workspace / ".gitignore"
    gitignore = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    _write_text_atomic(gitignore_path, _ensure_gitignore(gitignore))
    for directory in (workspace / "raw", workspace / "raw" / "telegram", workspace / "raw" / "meetings"):
        directory.mkdir(parents=True, exist_ok=True)
        os.chmod(directory, 0o700)

    config_path = _runtime_config_path(workspace)
    config = _read_object(config_path)
    config["raw_source_root"] = "raw"
    config["raw_source_policy"] = "private-configured-raw-root-only"
    write_json_atomic(config_path, config)
    raw_result = _copy_raw(raw_plan)
    locator_changes = 0
    for path in (workspace / "source-instances.json", workspace / "live-proofs" / "proofs.json"):
        locator_changes += _rewrite_json_file(path, mapping)
    for database in _meeting_databases(workspace):
        locator_changes += _rewrite_meeting_database(database, mapping)

    if apply_openclaw:
        assert openclaw_bin is not None
        assert host_inventory is not None
        _activate_host(
            openclaw_bin,
            openclaw_node_bin_dir,
            workspace,
            agent_id,
            scheduling,
            host_inventory,
        )

    postflight = _postflight(
        workspace,
        agent_id,
        openclaw_bin=openclaw_bin,
        openclaw_node_bin_dir=openclaw_node_bin_dir,
        host_applied=apply_openclaw,
    )
    result_payload: dict[str, object] = {
        "status": "migrated",
        "migration_id": MIGRATION_ID,
        "agent_id": agent_id,
        "source_version": SOURCE_VERSION,
        "target_version": TARGET_VERSION,
        "migrated_at": timestamp,
        "backup_manifest": str(backup_manifest.relative_to(workspace)),
        "raw": raw_result,
        "locator_updates": locator_changes,
        "heartbeat": dict(EXPECTED_HEARTBEAT),
        "openclaw_host_applied": apply_openclaw,
        "host_activation_required": not apply_openclaw,
        "owner_reminder": (
            "configured" if scheduling["owner_reminder"]["configured"] is True
            else "owner-confirmation-required-before-cron"
        ),
        "postflight": postflight,
        "delivery_target_in_output": False,
    }
    install_report_path = workspace / "PACKAGE_INSTALL_REPORT.json"
    install_report = _read_object(install_report_path) if install_report_path.is_file() else {}
    install_report["workspace_migration"] = {
        key: result_payload[key]
        for key in (
            "status",
            "migration_id",
            "agent_id",
            "source_version",
            "target_version",
            "migrated_at",
            "backup_manifest",
            "openclaw_host_applied",
            "host_activation_required",
            "owner_reminder",
        )
    }
    write_json_atomic(install_report_path, install_report)
    write_json_atomic(_result_path(workspace), result_payload)
    return result_payload


def _rollback(
    workspace: Path,
    agent_id: str,
    *,
    openclaw_bin: str | None,
    openclaw_node_bin_dir: str | None,
    apply_openclaw: bool,
) -> dict[str, object]:
    result_path = _result_path(workspace)
    if result_path.is_file() and _read_object(result_path).get("status") == "rolled-back":
        return {
            "status": "already-rolled-back",
            "migration_id": MIGRATION_ID,
            "agent_id": agent_id,
            "changed": False,
        }
    restored = _restore_backup(workspace)
    if apply_openclaw:
        if not openclaw_bin:
            raise MigrationError("--apply-openclaw rollback requires --openclaw-bin")
        _restore_host(openclaw_bin, openclaw_node_bin_dir, agent_id, workspace)
    payload: dict[str, object] = {
        "status": "rolled-back",
        "migration_id": MIGRATION_ID,
        "agent_id": agent_id,
        "target_version": TARGET_VERSION,
        "rolled_back_at": utc_timestamp(),
        "workspace": restored,
        "openclaw_host_restored": apply_openclaw,
        "raw_copies_preserved": True,
        "package_pointer_rollback_required": True,
    }
    write_json_atomic(result_path, payload)
    return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--agent-id", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--rollback", action="store_true")
    parser.add_argument(
        "--apply-openclaw",
        action="store_true",
        help="Install and verify the package-owned heartbeat, chat guard, and confirmed reminder on OpenClaw.",
    )
    parser.add_argument("--openclaw-bin")
    parser.add_argument("--openclaw-node-bin-dir")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    workspace = args.workspace.resolve()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", args.agent_id):
        print(json.dumps({"status": "error", "reason": "invalid-agent-id"}, sort_keys=True))
        return 2
    try:
        source_lock = _validate_source(workspace, dry_run=args.dry_run or args.rollback)
        if args.dry_run:
            payload = _dry_run_payload(
                workspace,
                args.agent_id,
                source_lock,
                _raw_copy_plan(workspace),
                apply_openclaw=args.apply_openclaw,
            )
        else:
            lock_path = workspace / "agent-state" / ".workspace-migration-v0.11.0.lock"
            with UpdateLock(lock_path):
                if args.rollback:
                    payload = _rollback(
                        workspace,
                        args.agent_id,
                        openclaw_bin=args.openclaw_bin,
                        openclaw_node_bin_dir=args.openclaw_node_bin_dir,
                        apply_openclaw=args.apply_openclaw,
                    )
                else:
                    payload = _apply(
                        workspace,
                        args.agent_id,
                        openclaw_bin=args.openclaw_bin,
                        openclaw_node_bin_dir=args.openclaw_node_bin_dir,
                        apply_openclaw=args.apply_openclaw,
                    )
    except (MigrationError, UpdateLockBusy) as exc:
        print(
            json.dumps(
                {"status": "error", "migration_id": MIGRATION_ID, "reason": str(exc)},
                sort_keys=True,
            )
        )
        return 3
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

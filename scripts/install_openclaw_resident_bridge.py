#!/usr/bin/env python3
"""Install the package bridge and resident-owned reminder contract in one workspace."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
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


MIGRATION_ID = "resident-self-service-v1"
MANAGED_BEGIN = "<!-- BEGIN BUSINESS-ONTOLOGY MANAGED: resident-self-service-v1 -->"
MANAGED_END = "<!-- END BUSINESS-ONTOLOGY MANAGED: resident-self-service-v1 -->"
BRIDGE_RELATIVE = Path("skills/business-ontology-resident/SKILL.md")
STATE_RELATIVE = Path("agent-state/managed-scheduling.json")
AGENTS_RELATIVE = Path("AGENTS.md")
MANAGED_FILES = (AGENTS_RELATIVE, STATE_RELATIVE, BRIDGE_RELATIVE)
UNCONFIGURED_STATUSES = {"needs-owner-question", "awaiting-owner", "deferred"}


class BridgeInstallError(RuntimeError):
    """The workspace cannot be changed without violating the bridge contract."""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BridgeInstallError(f"required file is missing: {path.name}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise BridgeInstallError(f"required JSON is invalid: {path.name}") from exc
    if not isinstance(payload, dict):
        raise BridgeInstallError(f"required JSON is not an object: {path.name}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_text_atomic(path: Path, content: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(content.rstrip() + "\n", encoding="utf-8")
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def _render(text: str, agent_id: str) -> str:
    return text.replace("{{AGENT_ID}}", agent_id).rstrip() + "\n"


def _managed_block(agent_id: str) -> str:
    template = (REPO_ROOT / "templates/workspace/AGENTS.md.tpl").read_text(encoding="utf-8")
    if MANAGED_BEGIN not in template or MANAGED_END not in template:
        raise BridgeInstallError("workspace AGENTS template has no complete managed runtime block")
    before_end = template.split(MANAGED_END, 1)[0]
    block = before_end.rsplit(MANAGED_BEGIN, 1)[1]
    return _render(f"{MANAGED_BEGIN}{block}{MANAGED_END}", agent_id)


def _bridge_content(agent_id: str) -> str:
    template = (
        REPO_ROOT
        / "templates/workspace/skills/business-ontology-resident/SKILL.md.tpl"
    ).read_text(encoding="utf-8")
    return _render(template, agent_id)


def _patch_managed_block(text: str, block: str) -> str:
    has_begin = MANAGED_BEGIN in text
    has_end = MANAGED_END in text
    if has_begin != has_end:
        raise BridgeInstallError("AGENTS.md has an incomplete managed runtime block")
    if not has_begin:
        return text.rstrip() + "\n\n" + block
    before, remainder = text.split(MANAGED_BEGIN, 1)
    _, after = remainder.split(MANAGED_END, 1)
    return before.rstrip() + "\n\n" + block.rstrip() + after.rstrip() + "\n"


def _next_scheduling(scheduling: dict[str, Any], agent_id: str) -> dict[str, Any]:
    if scheduling.get("agent_id") != agent_id:
        raise BridgeInstallError("managed scheduling belongs to another agent")
    reminder = scheduling.get("owner_reminder")
    if not isinstance(reminder, dict):
        raise BridgeInstallError("managed scheduling has no owner reminder object")
    next_scheduling = json.loads(json.dumps(scheduling))
    next_reminder = next_scheduling["owner_reminder"]
    if next_reminder.get("configured") is True:
        next_reminder["requires_owner_confirmation"] = False
        next_reminder["setup_status"] = "configured"
    else:
        next_reminder["configured"] = False
        next_reminder["requires_owner_confirmation"] = True
        if next_reminder.get("setup_status") not in UNCONFIGURED_STATUSES:
            next_reminder["setup_status"] = "needs-owner-question"
    return next_scheduling


def _migration_root(workspace: Path) -> Path:
    return workspace / "agent-state" / "migrations" / MIGRATION_ID


def _backup(workspace: Path) -> Path:
    root = _migration_root(workspace) / "backup"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        return manifest_path
    records: list[dict[str, object]] = []
    files_root = root / "files"
    files_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    for relative in MANAGED_FILES:
        source = workspace / relative
        record: dict[str, object] = {"path": str(relative), "existed": source.is_file()}
        if source.is_file():
            destination = files_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            os.chmod(destination, 0o600)
            record["mode"] = source.stat().st_mode & 0o777
            record["sha256"] = _sha256(source)
        records.append(record)
    write_json_atomic(
        manifest_path,
        {
            "migration_id": MIGRATION_ID,
            "created_at": utc_timestamp(),
            "files": records,
            "cron_mutation": False,
            "delivery_target_included": False,
        },
    )
    os.chmod(manifest_path, 0o600)
    return manifest_path


def _is_current(workspace: Path, agent_id: str) -> bool:
    agents_path = workspace / AGENTS_RELATIVE
    bridge_path = workspace / BRIDGE_RELATIVE
    state_path = workspace / STATE_RELATIVE
    if not all(path.is_file() for path in (agents_path, bridge_path, state_path)):
        return False
    expected_block = _managed_block(agent_id).strip()
    if expected_block not in agents_path.read_text(encoding="utf-8"):
        return False
    if bridge_path.read_text(encoding="utf-8") != _bridge_content(agent_id):
        return False
    try:
        scheduling = _read_object(state_path)
        return scheduling == _next_scheduling(scheduling, agent_id)
    except BridgeInstallError:
        return False


def install_bridge(workspace: Path, agent_id: str, *, dry_run: bool = False) -> dict[str, object]:
    if not workspace.is_dir():
        raise BridgeInstallError("workspace does not exist")
    agents_path = workspace / AGENTS_RELATIVE
    state_path = workspace / STATE_RELATIVE
    bridge_path = workspace / BRIDGE_RELATIVE
    if not agents_path.is_file():
        raise BridgeInstallError("AGENTS.md is missing")
    scheduling = _read_object(state_path)
    next_scheduling = _next_scheduling(scheduling, agent_id)
    if bridge_path.exists() and "managed-by: business-ontology" not in bridge_path.read_text(
        encoding="utf-8"
    ):
        raise BridgeInstallError("workspace skill name collides with a non-package skill")
    if _is_current(workspace, agent_id):
        return {
            "status": "already-current",
            "migration_id": MIGRATION_ID,
            "agent_id": agent_id,
            "changed": False,
            "cron_mutated": False,
        }
    if dry_run:
        return {
            "status": "dry-run",
            "migration_id": MIGRATION_ID,
            "agent_id": agent_id,
            "changes": [str(path) for path in MANAGED_FILES],
            "resident_agent_owns_reminder_setup": True,
            "cron_mutated": False,
        }
    manifest = _backup(workspace)
    agents_mode = agents_path.stat().st_mode & 0o777
    patched_agents = _patch_managed_block(
        agents_path.read_text(encoding="utf-8"), _managed_block(agent_id)
    )
    _write_text_atomic(agents_path, patched_agents, agents_mode)
    _write_text_atomic(bridge_path, _bridge_content(agent_id), 0o644)
    write_json_atomic(state_path, next_scheduling)
    os.chmod(state_path, 0o600)
    result = {
        "status": "installed",
        "migration_id": MIGRATION_ID,
        "agent_id": agent_id,
        "installed_at": utc_timestamp(),
        "backup_manifest": str(manifest.relative_to(workspace)),
        "resident_agent_owns_reminder_setup": True,
        "setup_status": next_scheduling["owner_reminder"]["setup_status"],
        "cron_mutated": False,
    }
    write_json_atomic(_migration_root(workspace) / "result.json", result)
    os.chmod(_migration_root(workspace) / "result.json", 0o600)
    return result


def rollback_bridge(workspace: Path, agent_id: str) -> dict[str, object]:
    manifest_path = _migration_root(workspace) / "backup" / "manifest.json"
    manifest = _read_object(manifest_path)
    if manifest.get("migration_id") != MIGRATION_ID:
        raise BridgeInstallError("bridge backup belongs to another migration")
    records = manifest.get("files")
    if not isinstance(records, list):
        raise BridgeInstallError("bridge backup file inventory is invalid")
    files_root = manifest_path.parent / "files"
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise BridgeInstallError("bridge backup entry is invalid")
        relative = Path(record["path"])
        if relative not in MANAGED_FILES:
            raise BridgeInstallError("bridge backup contains an unexpected path")
        target = workspace / relative
        if record.get("existed") is True:
            source = files_root / relative
            if not source.is_file():
                raise BridgeInstallError("bridge backup file is missing")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            os.chmod(target, int(record.get("mode") or 0o600))
        else:
            target.unlink(missing_ok=True)
    result = {
        "status": "rolled-back",
        "migration_id": MIGRATION_ID,
        "agent_id": agent_id,
        "rolled_back_at": utc_timestamp(),
        "cron_mutated": False,
    }
    write_json_atomic(_migration_root(workspace) / "result.json", result)
    os.chmod(_migration_root(workspace) / "result.json", 0o600)
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--agent-id", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--rollback", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    workspace = args.workspace.resolve()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", args.agent_id):
        print(json.dumps({"status": "error", "reason": "invalid-agent-id"}, sort_keys=True))
        return 2
    try:
        lock = workspace / "agent-state" / f".{MIGRATION_ID}.lock"
        with UpdateLock(lock):
            payload = (
                rollback_bridge(workspace, args.agent_id)
                if args.rollback
                else install_bridge(workspace, args.agent_id, dry_run=args.dry_run)
            )
    except UpdateLockBusy as exc:
        print(json.dumps({"status": "locked", "pid": exc.pid}, sort_keys=True))
        return 5
    except (BridgeInstallError, OSError) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

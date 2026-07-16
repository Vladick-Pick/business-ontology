#!/usr/bin/env python3
"""Migrate an installed workspace to the v0.11.12 viewer publication boundary."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from package_update_common import (  # noqa: E402
    UpdateLock,
    UpdateLockBusy,
    utc_timestamp,
    write_json_atomic,
)


MIGRATION_ID = "workspace-v0.11.12"
TARGET_VERSION = "0.11.12"
SUPPORTED_SOURCE_VERSIONS = {
    "0.11.11",
    TARGET_VERSION,
    "0.11.13",
    "0.11.14",
    "0.11.15",
    "0.11.16",
}
APPLY_PACKAGE_VERSIONS = {
    TARGET_VERSION,
    "0.11.13",
    "0.11.14",
    "0.11.15",
    "0.11.16",
}
SITES_DENY = ("sites.*", "codex_apps.sites.*")


class MigrationError(RuntimeError):
    """A safe migration precondition or postflight failed."""


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


def _runtime_config_path(workspace: Path) -> Path:
    for name in ("runtime-config.json", "runtime-config.example.json"):
        path = workspace / name
        if path.is_file():
            return path
    raise MigrationError("runtime config is missing")


def _migration_root(workspace: Path) -> Path:
    return workspace / "agent-state" / "migrations" / "v0.11.12"


def _backup_root(workspace: Path) -> Path:
    return _migration_root(workspace) / "backup"


def _result_path(workspace: Path) -> Path:
    return _migration_root(workspace) / "result.json"


def _openclaw_env(node_bin_dir: str | None) -> dict[str, str]:
    environment = os.environ.copy()
    if node_bin_dir:
        environment["PATH"] = f"{node_bin_dir}{os.pathsep}{environment.get('PATH', '')}"
    return environment


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
        raise MigrationError(f"OpenClaw mutation failed with exit {result.returncode}")


def _agents(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        payload = payload.get("agents", payload.get("data", []))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _agent_inventory(binary: str, node_bin_dir: str | None, agent_id: str) -> dict[str, Any]:
    agents = _agents(
        _openclaw_json(binary, node_bin_dir, ["config", "get", "agents.list", "--json"])
    )
    matches = [(index, agent) for index, agent in enumerate(agents) if agent.get("id") == agent_id]
    if len(matches) != 1:
        raise MigrationError("OpenClaw must contain exactly one matching agent id")
    index, agent = matches[0]
    tools = agent.get("tools")
    if tools is not None and not isinstance(tools, dict):
        raise MigrationError("OpenClaw agent tools config is not an object")
    return {
        "agent_index": index,
        "tools_existed": isinstance(tools, dict),
        "tools": tools if isinstance(tools, dict) else None,
    }


def _set_agent_tools(
    binary: str,
    node_bin_dir: str | None,
    agent_id: str,
    tools: dict[str, Any] | None,
) -> None:
    inventory = _agent_inventory(binary, node_bin_dir, agent_id)
    path = f"agents.list[{inventory['agent_index']}].tools"
    if tools is None:
        _openclaw_mutate(binary, node_bin_dir, ["config", "unset", path])
    else:
        _openclaw_mutate(
            binary,
            node_bin_dir,
            ["config", "set", path, json.dumps(tools, sort_keys=True), "--strict-json"],
        )


def _activate_host(binary: str, node_bin_dir: str | None, agent_id: str) -> None:
    inventory = _agent_inventory(binary, node_bin_dir, agent_id)
    previous = inventory.get("tools")
    tools = dict(previous) if isinstance(previous, dict) else {}
    existing_deny = tools.get("deny")
    if existing_deny is not None and not isinstance(existing_deny, list):
        raise MigrationError("OpenClaw agent tools.deny is not a list")
    tools["deny"] = list(
        dict.fromkeys([*(str(item) for item in (existing_deny or [])), *SITES_DENY])
    )
    _set_agent_tools(binary, node_bin_dir, agent_id, tools)
    current = _agent_inventory(binary, node_bin_dir, agent_id).get("tools")
    current_deny = current.get("deny") if isinstance(current, dict) else None
    if not isinstance(current_deny, list) or not set(SITES_DENY) <= set(current_deny):
        raise MigrationError("OpenClaw Sites deny postflight failed")


def _restore_host(
    binary: str,
    node_bin_dir: str | None,
    agent_id: str,
    host: dict[str, Any],
) -> None:
    if host.get("tools_existed") is True:
        tools = host.get("tools")
        if not isinstance(tools, dict):
            raise MigrationError("backup OpenClaw tools inventory is invalid")
        _set_agent_tools(binary, node_bin_dir, agent_id, tools)
    else:
        _set_agent_tools(binary, node_bin_dir, agent_id, None)


def _validate(workspace: Path, *, dry_run_or_rollback: bool) -> dict[str, Any]:
    if not workspace.is_dir():
        raise MigrationError("workspace does not exist")
    lock = _read_object(workspace / "PACKAGE_VERSION.lock")
    current = str(lock.get("current_version") or "")
    if current not in SUPPORTED_SOURCE_VERSIONS:
        raise MigrationError(f"unsupported package version: {current or 'missing'}")
    if not dry_run_or_rollback and current not in APPLY_PACKAGE_VERSIONS:
        raise MigrationError("install a v0.11.12-compatible package before applying this migration")
    _runtime_config_path(workspace)
    return lock


def _ensure_backup(
    workspace: Path,
    *,
    host: dict[str, Any] | None,
) -> dict[str, Any]:
    backup = _backup_root(workspace)
    backup.mkdir(parents=True, exist_ok=True)
    manifest_path = backup / "manifest.json"
    if manifest_path.exists():
        manifest = _read_object(manifest_path)
    else:
        config_path = _runtime_config_path(workspace)
        backup_config = backup / config_path.name
        shutil.copy2(config_path, backup_config)
        manifest = {
            "migration_id": MIGRATION_ID,
            "created_at": utc_timestamp(),
            "runtime_config_name": config_path.name,
            "runtime_config_backup": backup_config.name,
            "host": None,
        }
    if host is not None:
        previous_host = manifest.get("host")
        if previous_host is not None and previous_host != host:
            raise MigrationError("backup already contains a different OpenClaw host inventory")
        manifest["host"] = host
    write_json_atomic(manifest_path, manifest)
    return manifest


def _apply(
    workspace: Path,
    agent_id: str,
    *,
    openclaw_bin: str | None,
    openclaw_node_bin_dir: str | None,
    apply_openclaw: bool,
) -> dict[str, Any]:
    if apply_openclaw and not openclaw_bin:
        raise MigrationError("--apply-openclaw requires --openclaw-bin")
    config_path = _runtime_config_path(workspace)
    config = _read_object(config_path)
    current_host = (
        _agent_inventory(openclaw_bin, openclaw_node_bin_dir, agent_id)
        if apply_openclaw and openclaw_bin
        else None
    )
    manifest_path = _backup_root(workspace) / "manifest.json"
    existing_manifest = _read_object(manifest_path) if manifest_path.exists() else {}
    backup_host = current_host if existing_manifest.get("host") is None else None
    _ensure_backup(workspace, host=backup_host)

    created_publication = "viewer_publication" not in config
    if created_publication:
        config["viewer_publication"] = {
            "mode": "workspace-only",
            "public_url": "",
        }
        write_json_atomic(config_path, config)
    else:
        publication = config.get("viewer_publication")
        if not isinstance(publication, dict) or not publication.get("mode"):
            raise MigrationError("existing viewer_publication config is invalid")

    host_changed = False
    if apply_openclaw:
        assert openclaw_bin is not None
        current_tools = current_host.get("tools") if isinstance(current_host, dict) else None
        current_deny = current_tools.get("deny") if isinstance(current_tools, dict) else None
        host_changed = not isinstance(current_deny, list) or not set(SITES_DENY) <= set(current_deny)
        if host_changed:
            _activate_host(openclaw_bin, openclaw_node_bin_dir, agent_id)

    payload = {
        "status": "migrated" if created_publication or host_changed else "already-current",
        "migration_id": MIGRATION_ID,
        "changed": created_publication or host_changed,
        "viewer_publication_created": created_publication,
        "openclaw_host_applied": apply_openclaw,
        "sites_tools_denied": list(SITES_DENY) if apply_openclaw else [],
        "completed_at": utc_timestamp(),
    }
    write_json_atomic(_result_path(workspace), payload)
    return payload


def _rollback(
    workspace: Path,
    agent_id: str,
    *,
    openclaw_bin: str | None,
    openclaw_node_bin_dir: str | None,
    apply_openclaw: bool,
) -> dict[str, Any]:
    manifest = _read_object(_backup_root(workspace) / "manifest.json")
    host = manifest.get("host")
    if host is not None and not apply_openclaw:
        raise MigrationError("rollback must use --apply-openclaw to restore host tools")
    if apply_openclaw:
        if not openclaw_bin or not isinstance(host, dict):
            raise MigrationError("rollback has no usable OpenClaw host backup")
        _restore_host(openclaw_bin, openclaw_node_bin_dir, agent_id, host)

    config_name = str(manifest.get("runtime_config_name") or "")
    backup_name = str(manifest.get("runtime_config_backup") or "")
    if not config_name or not backup_name:
        raise MigrationError("runtime config backup manifest is incomplete")
    source = _backup_root(workspace) / backup_name
    destination = workspace / config_name
    shutil.copy2(source, destination)
    payload = {
        "status": "rolled-back",
        "migration_id": MIGRATION_ID,
        "openclaw_host_restored": apply_openclaw,
        "completed_at": utc_timestamp(),
    }
    write_json_atomic(_result_path(workspace), payload)
    return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--agent-id", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--rollback", action="store_true")
    parser.add_argument("--apply-openclaw", action="store_true")
    parser.add_argument("--openclaw-bin")
    parser.add_argument("--openclaw-node-bin-dir")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    workspace = args.workspace.resolve()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", args.agent_id):
        print(json.dumps({"status": "error", "reason": "invalid-agent-id"}))
        return 2
    try:
        lock = _validate(workspace, dry_run_or_rollback=args.dry_run or args.rollback)
        if args.dry_run:
            config = _read_object(_runtime_config_path(workspace))
            payload = {
                "status": "dry-run",
                "migration_id": MIGRATION_ID,
                "package_version": lock.get("current_version"),
                "viewer_publication_would_be_created": "viewer_publication" not in config,
                "openclaw_host_would_be_updated": args.apply_openclaw,
                "sites_tools_to_deny": list(SITES_DENY),
            }
        else:
            lock_path = workspace / "agent-state" / ".workspace-migration-v0.11.12.lock"
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
        print(json.dumps({"status": "error", "migration_id": MIGRATION_ID, "reason": str(exc)}))
        return 3
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

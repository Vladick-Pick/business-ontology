#!/usr/bin/env python3
"""Migrate one installed workspace to private review authority state."""
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
for import_root in (SCRIPT_DIR, REPO_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from package_update_common import (  # noqa: E402
    UpdateLock,
    UpdateLockBusy,
    utc_timestamp,
    write_json_atomic,
)
from runtime.review_authority import validate_review_authority  # noqa: E402


MIGRATION_ID = "workspace-v0.11.15"
TARGET_VERSION = "0.11.15"
SUPPORTED_SOURCE_VERSIONS = {"0.11.14", TARGET_VERSION, "0.11.16"}
APPLY_PACKAGE_VERSIONS = {TARGET_VERSION, "0.11.16"}
DEFAULT_POLICY_PATH = "agent-state/review-authority.json"


class MigrationError(RuntimeError):
    """A migration precondition, postflight, or rollback guard failed."""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        raise MigrationError(f"required JSON is invalid or missing: {path.name}") from exc
    if not isinstance(payload, dict):
        raise MigrationError(f"required JSON is not an object: {path.name}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime_config_path(workspace: Path) -> Path:
    for name in ("runtime-config.json", "runtime-config.example.json"):
        path = workspace / name
        if path.is_file():
            return path
    raise MigrationError("runtime config is missing")


def _policy_path(workspace: Path, config: dict[str, Any]) -> tuple[Path, str]:
    configured = config.get("review_authority_policy_path")
    if configured is not None and not isinstance(configured, str):
        raise MigrationError("review authority policy path must be a string")
    raw_path = str(configured or DEFAULT_POLICY_PATH).strip()
    relative = Path(raw_path)
    if relative.is_absolute():
        raise MigrationError("review authority policy path must be workspace-relative")
    resolved = (workspace / relative).resolve()
    try:
        normalized = resolved.relative_to(workspace.resolve()).as_posix()
    except ValueError as exc:
        raise MigrationError("review authority policy path escapes workspace") from exc
    if resolved == workspace.resolve() or (resolved.exists() and not resolved.is_file()):
        raise MigrationError("review authority policy path must point to a file")
    return resolved, normalized


def _migration_root(workspace: Path) -> Path:
    return workspace / "agent-state" / "migrations" / "v0.11.15"


def _backup_root(workspace: Path) -> Path:
    return _migration_root(workspace) / "backup"


def _result_path(workspace: Path) -> Path:
    return _migration_root(workspace) / "result.json"


def _write_text_atomic(path: Path, content: str, *, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(content, encoding="utf-8")
    if mode is not None:
        os.chmod(temporary, mode)
    os.replace(temporary, path)


def _validate(workspace: Path, *, dry_run_or_rollback: bool) -> dict[str, Any]:
    if not workspace.is_dir():
        raise MigrationError("workspace does not exist")
    lock = _read_object(workspace / "PACKAGE_VERSION.lock")
    current = str(lock.get("current_version") or "")
    if current not in SUPPORTED_SOURCE_VERSIONS:
        raise MigrationError(f"unsupported package version: {current or 'missing'}")
    if not dry_run_or_rollback and current not in APPLY_PACKAGE_VERSIONS:
        raise MigrationError("install v0.11.15 or newer before applying this migration")
    _runtime_config_path(workspace)
    return lock


def _ensure_backup(workspace: Path, config: dict[str, Any]) -> dict[str, Any]:
    backup = _backup_root(workspace)
    backup.mkdir(parents=True, exist_ok=True)
    os.chmod(backup, 0o700)
    manifest_path = backup / "manifest.json"
    if manifest_path.is_file():
        return _read_object(manifest_path)

    config_path = _runtime_config_path(workspace)
    policy_path, policy_relative = _policy_path(workspace, config)
    gitignore = workspace / ".gitignore"
    shutil.copy2(config_path, backup / config_path.name)
    if gitignore.is_file():
        shutil.copy2(gitignore, backup / "gitignore")
    if policy_path.is_file():
        shutil.copy2(policy_path, backup / "review-authority.json")
        os.chmod(backup / "review-authority.json", 0o600)
    manifest = {
        "migration_id": MIGRATION_ID,
        "created_at": utc_timestamp(),
        "runtime_config_name": config_path.name,
        "gitignore_existed": gitignore.is_file(),
        "policy_existed": policy_path.is_file(),
        "policy_relative_path": policy_relative,
        "policy_mode": (policy_path.stat().st_mode & 0o777) if policy_path.is_file() else None,
    }
    write_json_atomic(manifest_path, manifest)
    os.chmod(manifest_path, 0o600)
    return manifest


def _gitignore_with_rule(existing: str, relative_path: str) -> str:
    rule = f"/{relative_path}"
    if rule in existing.splitlines():
        return existing
    separator = "" if not existing or existing.endswith("\n") else "\n"
    return f"{existing}{separator}{rule}\n"


def _apply(workspace: Path) -> dict[str, Any]:
    config_path = _runtime_config_path(workspace)
    config = _read_object(config_path)
    module_id = str(config.get("module_id") or "").strip()
    if re.fullmatch(r"[a-z0-9][a-z0-9-]*", module_id) is None:
        raise MigrationError("runtime config module_id is invalid")
    existing_policy_path, _ = _policy_path(workspace, config)
    if existing_policy_path.is_file():
        existing_policy = validate_review_authority(_read_object(existing_policy_path))
        if existing_policy["businessId"] != module_id:
            raise MigrationError("review authority businessId does not match module_id")
    manifest = _ensure_backup(workspace, config)

    configured_policy_path = config.get("review_authority_policy_path")
    config_changed = not isinstance(configured_policy_path, str) or not configured_policy_path.strip()
    config["review_authority_policy_path"] = (
        configured_policy_path.strip()
        if isinstance(configured_policy_path, str) and configured_policy_path.strip()
        else DEFAULT_POLICY_PATH
    )
    policy_path, policy_relative = _policy_path(workspace, config)
    if config_changed:
        write_json_atomic(config_path, config)

    policy_created = not policy_path.exists()
    if policy_created:
        empty_policy = validate_review_authority(
            {"policyVersion": 1, "businessId": module_id, "channels": []}
        )
        _write_text_atomic(
            policy_path,
            json.dumps(empty_policy, indent=2, sort_keys=True) + "\n",
            mode=0o600,
        )
    else:
        os.chmod(policy_path, 0o600)

    gitignore = workspace / ".gitignore"
    existing_gitignore = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    updated_gitignore = _gitignore_with_rule(existing_gitignore, policy_relative)
    gitignore_changed = updated_gitignore != existing_gitignore
    if gitignore_changed:
        _write_text_atomic(gitignore, updated_gitignore)

    postflight_hashes = {
        "runtime_config": _sha256(config_path),
        "gitignore": _sha256(gitignore),
        "policy": _sha256(policy_path),
    }
    if "postflight_hashes" not in manifest:
        manifest["postflight_hashes"] = postflight_hashes
        manifest_path = _backup_root(workspace) / "manifest.json"
        write_json_atomic(manifest_path, manifest)
        os.chmod(manifest_path, 0o600)

    payload = {
        "status": (
            "migrated"
            if config_changed or policy_created or gitignore_changed
            else "already-current"
        ),
        "migration_id": MIGRATION_ID,
        "changed": config_changed or policy_created or gitignore_changed,
        "policy_created": policy_created,
        "policy_mode": "0600",
        "completed_at": utc_timestamp(),
        "postflight_hashes": postflight_hashes,
    }
    write_json_atomic(_result_path(workspace), payload)
    return payload


def _rollback(workspace: Path) -> dict[str, Any]:
    manifest = _read_object(_backup_root(workspace) / "manifest.json")
    hashes = manifest.get("postflight_hashes")
    if not isinstance(hashes, dict):
        raise MigrationError("migration result has no rollback hashes")

    config_name = str(manifest.get("runtime_config_name") or "")
    if config_name not in {"runtime-config.json", "runtime-config.example.json"}:
        raise MigrationError("runtime config backup manifest is invalid")
    config_path = workspace / config_name
    policy_relative = str(manifest.get("policy_relative_path") or "")
    policy_path, normalized_policy_relative = _policy_path(
        workspace,
        {"review_authority_policy_path": policy_relative},
    )
    if normalized_policy_relative != policy_relative:
        raise MigrationError("review authority backup path is invalid")
    gitignore = workspace / ".gitignore"
    current = {
        "runtime_config": config_path,
        "gitignore": gitignore,
        "policy": policy_path,
    }
    for name, path in current.items():
        if not path.is_file() or _sha256(path) != hashes.get(name):
            raise MigrationError(f"rollback refused because {name} changed after migration")

    shutil.copy2(_backup_root(workspace) / config_path.name, config_path)
    if manifest.get("gitignore_existed") is True:
        shutil.copy2(_backup_root(workspace) / "gitignore", gitignore)
    else:
        gitignore.unlink()
    if manifest.get("policy_existed") is True:
        shutil.copy2(_backup_root(workspace) / "review-authority.json", policy_path)
        mode = manifest.get("policy_mode")
        os.chmod(policy_path, int(mode) if isinstance(mode, int) else 0o600)
    else:
        policy_path.unlink()

    payload = {
        "status": "rolled-back",
        "migration_id": MIGRATION_ID,
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    workspace = args.workspace.resolve()
    if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", args.agent_id) is None:
        print(json.dumps({"status": "error", "reason": "invalid-agent-id"}))
        return 2
    try:
        lock = _validate(workspace, dry_run_or_rollback=args.dry_run or args.rollback)
        if args.dry_run:
            config = _read_object(_runtime_config_path(workspace))
            policy_path, policy_relative = _policy_path(workspace, config)
            payload = {
                "status": "dry-run",
                "migration_id": MIGRATION_ID,
                "package_version": lock.get("current_version"),
                "config_would_change": "review_authority_policy_path" not in config,
                "policy_would_be_created": not policy_path.exists(),
                "gitignore_rule": f"/{policy_relative}",
            }
        else:
            lock_path = workspace / "agent-state" / ".workspace-migration-v0.11.15.lock"
            with UpdateLock(lock_path):
                payload = _rollback(workspace) if args.rollback else _apply(workspace)
    except (MigrationError, UpdateLockBusy, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "migration_id": MIGRATION_ID, "reason": str(exc)}))
        return 3
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

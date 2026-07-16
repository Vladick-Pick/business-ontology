#!/usr/bin/env python3
"""Write one validated workspace-local review authority policy from stdin."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.review_authority import validate_review_authority  # noqa: E402


MAX_POLICY_CHARS = 65_536


def _read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"required JSON is invalid or missing: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"required JSON is not an object: {path.name}")
    return payload


def _runtime_config(workspace: Path) -> dict[str, Any]:
    for name in ("runtime-config.json", "runtime-config.example.json"):
        path = workspace / name
        if path.is_file():
            return _read_object(path)
    raise ValueError("runtime config is missing")


def _policy_path(workspace: Path, config: dict[str, Any]) -> Path:
    raw_path = str(config.get("review_authority_policy_path") or "").strip()
    if not raw_path:
        raise ValueError("runtime config has no review_authority_policy_path")
    configured = Path(raw_path)
    if configured.is_absolute():
        raise ValueError("review authority policy path must be workspace-relative")
    resolved = (workspace / configured).resolve()
    try:
        resolved.relative_to(workspace.resolve())
    except ValueError as exc:
        raise ValueError("review authority policy path escapes workspace") from exc
    if resolved == workspace.resolve() or (resolved.exists() and not resolved.is_file()):
        raise ValueError("review authority policy path must point to a file")
    return resolved


def _read_policy_stdin() -> dict[str, object]:
    raw = sys.stdin.read(MAX_POLICY_CHARS + 1)
    if len(raw) > MAX_POLICY_CHARS:
        raise ValueError("review authority policy exceeds safe input limit")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("review authority policy is not valid JSON") from exc
    return validate_review_authority(payload)


def _write_private_json(path: Path, payload: dict[str, object]) -> bool:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path.is_file() and path.read_text(encoding="utf-8") == rendered:
        os.chmod(path, 0o600)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(rendered, encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    return True


def configure(workspace: Path, policy: dict[str, object]) -> dict[str, object]:
    if not workspace.is_dir():
        raise ValueError("workspace does not exist")
    policy = validate_review_authority(policy)
    config = _runtime_config(workspace)
    module_id = str(config.get("module_id") or "").strip()
    if not module_id:
        raise ValueError("runtime config module_id is missing")
    if policy["businessId"] != module_id:
        raise ValueError("review authority businessId does not match workspace module_id")
    path = _policy_path(workspace, config)
    changed = _write_private_json(path, policy)
    channels = policy["channels"]
    assert isinstance(channels, list)
    actor_grants = 0
    for channel in channels:
        assert isinstance(channel, dict)
        actors = channel["actors"]
        assert isinstance(actors, list)
        actor_grants += len(actors)
    return {
        "status": "configured" if changed else "already-current",
        "channelCount": len(channels),
        "actorGrantCount": actor_grants,
        "mode": "0600",
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        policy = _read_policy_stdin()
        result = configure(args.workspace.resolve(), policy)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

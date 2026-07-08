#!/usr/bin/env python3
"""Verify that installed model access can stage proposals but cannot write accepted truth."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any


EXIT_PASS = 0
EXIT_CONFIG_ERROR = 2
EXIT_UNSAFE = 3
EXIT_MISCONFIGURED = 4
EXIT_PRODUCTION_REFUSED = 5

ALLOWED_ACCESS_MODES = {"read-model", "write-staged", "open-review", "write-accepted"}
HUMAN_ONLY_MODE = "write-accepted"
REQUIRED_STRING_FIELDS = ["agent_id", "accepted_branch", "staged_branch_pattern", "generated_at"]


class ScopeDenied(PermissionError):
    pass


class AccessControlledModelRepo:
    def __init__(self, root: Path, access_modes: set[str]) -> None:
        self.root = root
        self.access_modes = access_modes

    def write_staged(self) -> Path:
        self._require("write-staged")
        path = self.root / "staged" / "scope-proof.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Scope proof\n\nStaged write is allowed.\n", encoding="utf-8")
        return path

    def write_accepted(self) -> Path:
        self._require(HUMAN_ONLY_MODE)
        path = self.root / "accepted" / "scope-proof.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Scope proof\n\nAccepted write should be human-only.\n", encoding="utf-8")
        return path

    def generic_accepted_update(self) -> str:
        if HUMAN_ONLY_MODE in self.access_modes:
            return "available"
        return "unavailable"

    def _require(self, mode: str) -> None:
        if mode not in self.access_modes:
            raise ScopeDenied(f"missing access mode: {mode}")


def load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("access config must be a JSON object")
    for field in REQUIRED_STRING_FIELDS:
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if not isinstance(payload.get("production_model_repo"), bool):
        raise ValueError("production_model_repo must be a boolean")
    modes = payload.get("access_modes")
    if not isinstance(modes, list) or not all(isinstance(item, str) for item in modes):
        raise ValueError("access_modes must be a list of strings")
    if len(modes) != len(set(modes)):
        raise ValueError("access_modes must not contain duplicates")
    unknown = sorted(set(modes) - ALLOWED_ACCESS_MODES)
    if unknown:
        raise ValueError("unknown access mode(s): " + ", ".join(unknown))
    return payload


def verify_scope(access_config: dict[str, Any], model_root: Path) -> tuple[int, dict[str, Any]]:
    access_modes = set(access_config["access_modes"])
    report: dict[str, Any] = {
        "status": "unknown",
        "agent_id": str(access_config.get("agent_id") or ""),
        "accepted_branch": str(access_config.get("accepted_branch") or ""),
        "staged_branch_pattern": str(access_config.get("staged_branch_pattern") or ""),
        "access_modes": sorted(access_modes),
        "checks": {
            "staged_write": "not-run",
            "accepted_write": "not-run",
            "generic_accepted_update": "not-run",
        },
    }

    if access_config.get("production_model_repo") is True:
        report["status"] = "refused"
        report["reason"] = "refusing to probe a production model repository"
        return EXIT_PRODUCTION_REFUSED, report

    if HUMAN_ONLY_MODE in access_modes:
        report["status"] = "unsafe"
        report["reason"] = "agent access includes human-only mode: write-accepted"
        return EXIT_UNSAFE, report

    repo = AccessControlledModelRepo(model_root, access_modes)
    try:
        staged_path = repo.write_staged()
    except ScopeDenied:
        report["status"] = "misconfigured"
        report["reason"] = "agent cannot write staged proposals"
        report["checks"]["staged_write"] = "denied"
        return EXIT_MISCONFIGURED, report
    report["checks"]["staged_write"] = "passed"
    report["staged_write_path"] = str(staged_path)

    try:
        accepted_path = repo.write_accepted()
    except ScopeDenied:
        report["checks"]["accepted_write"] = "refused"
    else:
        report["status"] = "unsafe"
        report["reason"] = f"direct accepted write succeeded: {accepted_path}"
        report["checks"]["accepted_write"] = "succeeded"
        return EXIT_UNSAFE, report

    generic = repo.generic_accepted_update()
    report["checks"]["generic_accepted_update"] = generic
    if generic != "unavailable":
        report["status"] = "unsafe"
        report["reason"] = "generic accepted update path is available to the agent"
        return EXIT_UNSAFE, report

    report["status"] = "pass"
    report["reason"] = "staged write is available and accepted writes are refused"
    return EXIT_PASS, report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assert model repository write-scope separation.")
    parser.add_argument("--access-config", type=Path, required=True)
    parser.add_argument("--model-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = load_config(args.access_config)
    except Exception as exc:
        payload = {"status": "config-error", "reason": str(exc)}
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else payload["reason"])
        return EXIT_CONFIG_ERROR

    if args.model_root is not None:
        code, payload = verify_scope(config, args.model_root)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            code, payload = verify_scope(config, Path(tmp) / "model")

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"{payload['status']}: {payload.get('reason', '')}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

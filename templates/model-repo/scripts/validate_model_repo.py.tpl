#!/usr/bin/env python3
"""Validate this model repository with the pinned business-ontology package."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


EXPECTED_PACKAGE_NAME = "business-ontology"
STRICT_CONTRACT = "data-model-v2-hard-gate"
EXPECTED_VALIDATOR = "scripts/links_validate.py"
LOCK_NAME = "PACKAGE_CONTRACT.lock"
COPIED_VALIDATOR = Path("scripts") / "links_validate.py"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def package_version(package: Path) -> str:
    version_file = package / "VERSION.txt"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    manifest = package / "agent-package.yaml"
    if manifest.exists():
        match = re.search(r'(?m)^version:\s*["\']?v?([^"\'\s]+)', manifest.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    raise RuntimeError(f"package version not found in {package}")


def package_commit(package: Path) -> str:
    metadata = package / ".package-release.json"
    if metadata.exists():
        commit = read_json(metadata).get("commit")
        if isinstance(commit, str) and commit:
            return commit
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=package,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    raise RuntimeError(f"package commit not found in {package}")


def default_package_path(model_root: Path) -> Path:
    env_path = os.environ.get("BUSINESS_ONTOLOGY_PACKAGE")
    if env_path:
        return Path(env_path)
    return model_root.parent / "package" / "current"


def verify_contract(model_root: Path, package: Path) -> dict[str, Any]:
    lock_path = model_root / LOCK_NAME
    if not lock_path.exists():
        raise RuntimeError(f"{LOCK_NAME} is missing; install model repo support files from the package template")
    lock = read_json(lock_path)
    copied_validator = model_root / COPIED_VALIDATOR
    if copied_validator.exists():
        raise RuntimeError(f"{COPIED_VALIDATOR} is unsupported; use scripts/validate_model_repo.py wrapper instead")
    if lock.get("package_name") != EXPECTED_PACKAGE_NAME:
        raise RuntimeError(f"package_name mismatch in {LOCK_NAME}")
    if lock.get("validator_contract") != STRICT_CONTRACT:
        raise RuntimeError(f"validator_contract must be {STRICT_CONTRACT}")
    if lock.get("package_version") != package_version(package):
        raise RuntimeError(f"package_version mismatch in {LOCK_NAME}")
    if lock.get("package_commit") != package_commit(package):
        raise RuntimeError(f"package_commit mismatch in {LOCK_NAME}")
    validator = lock.get("validator")
    if validator != EXPECTED_VALIDATOR:
        raise RuntimeError(f"validator must be {EXPECTED_VALIDATOR}")
    validator_path = (package / EXPECTED_VALIDATOR).resolve()
    if package.resolve() not in validator_path.parents:
        raise RuntimeError(f"package validator path escapes package: {validator_path}")
    if not validator_path.exists():
        raise RuntimeError(f"package validator missing: {validator_path}")
    return lock


def parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Validate this model repo with the pinned package validator.")
    parser.add_argument("--package", type=Path, help="Installed package path. Defaults to env or ../package/current.")
    return parser.parse_known_args(argv)


def main(argv: list[str] | None = None) -> int:
    args, passthrough = parse_args(list(sys.argv[1:] if argv is None else argv))
    model_root = Path(__file__).resolve().parents[1]
    package = (args.package or default_package_path(model_root)).resolve()
    try:
        lock = verify_contract(model_root, package)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    command = [sys.executable, str(package / EXPECTED_VALIDATOR), str(model_root), *passthrough]
    if lock.get("validator_contract") == STRICT_CONTRACT and "--strict-transitional" not in passthrough:
        command.append("--strict-transitional")
    return subprocess.run(command, cwd=package, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

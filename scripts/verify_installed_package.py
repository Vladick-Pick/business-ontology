#!/usr/bin/env python3
"""Verify that an installed package update has a usable proof report."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from apply_package_update import (  # noqa: E402
    current_link,
    forbidden_release_residue,
    install_report_path,
    lock_path,
    release_head,
    source_tree_hash,
)
from check_package_updates import normalize_tag  # noqa: E402
from package_update_common import read_json_file  # noqa: E402


EXIT_CODES = {
    "ok": 0,
    "manual-or-unproven-install": 6,
    "dirty-release-tree": 7,
    "self-test-missing": 8,
    "model-validation-missing": 9,
    "reanchor-missing": 10,
    "model-support-contract-missing": 11,
}


def relative_install_path(install_root: Path, path: Path) -> str:
    return str(path.relative_to(install_root))


def current_release(install_root: Path) -> Path | None:
    current = current_link(install_root)
    if not current.is_symlink():
        return None
    return (current.parent / os.readlink(current)).resolve()


def payload(status: str, **extra: object) -> tuple[int, dict[str, object]]:
    return EXIT_CODES[status], {"status": status, **extra}


def verify_install(install_root: Path) -> tuple[int, dict[str, object]]:
    install_root = install_root.resolve()
    report_file = install_report_path(install_root)
    lock_file = lock_path(install_root)
    release = current_release(install_root)
    if release is None or not release.exists():
        return payload("manual-or-unproven-install", reason="current symlink is missing or invalid")
    if not report_file.exists():
        return payload("manual-or-unproven-install", reason="install report is missing")
    if report_file.stat().st_mtime_ns < current_link(install_root).lstat().st_mtime_ns:
        return payload("manual-or-unproven-install", reason="install report is older than current symlink")

    lock = read_json_file(lock_file)
    report = read_json_file(report_file)
    tag = normalize_tag(lock.get("tag") or lock.get("current_version"))
    commit = str(lock.get("commit") or "")
    release_rel = relative_install_path(install_root, release)

    expected_fields = {
        "current_symlink": relative_install_path(install_root, current_link(install_root)),
        "package_commit": commit,
        "package_tag": tag,
        "release_dir": release_rel,
    }
    mismatched = [key for key, expected in expected_fields.items() if report.get(key) != expected]
    if mismatched:
        return payload("manual-or-unproven-install", mismatched_fields=mismatched)
    if report.get("status") not in {"installed", "rolled-back"}:
        return payload("manual-or-unproven-install", mismatched_fields=["status"])

    residue = forbidden_release_residue(release)
    if residue:
        return payload("dirty-release-tree", residue=residue)

    try:
        actual_commit = release_head(release)
    except Exception as exc:
        return payload("manual-or-unproven-install", reason=str(exc))
    if actual_commit != commit:
        return payload("manual-or-unproven-install", reason="release commit mismatch")

    if report.get("source_tree_hash") != source_tree_hash(release):
        return payload("manual-or-unproven-install", reason="source tree hash mismatch")

    self_test = report.get("self_test")
    if not isinstance(self_test, dict) or self_test.get("status") != "passed":
        return payload("self-test-missing")

    model_validation = report.get("model_validation")
    valid_model_statuses = {"passed"}
    if report.get("status") == "rolled-back":
        valid_model_statuses.add("not_required_for_rollback")
    if not isinstance(model_validation, dict) or model_validation.get("status") not in valid_model_statuses:
        return payload("model-validation-missing")

    model_support_contract = report.get("model_support_contract")
    valid_support_statuses = {
        "current",
        "drift",
        "invalid",
        "missing",
        "skipped",
        "unsupported-copied-validator",
    }
    if report.get("status") == "rolled-back":
        valid_support_statuses.add("not_required_for_rollback")
    if (
        not isinstance(model_support_contract, dict)
        or model_support_contract.get("status") not in valid_support_statuses
    ):
        return payload("model-support-contract-missing")

    reanchor = report.get("reanchor")
    if not isinstance(reanchor, dict) or reanchor.get("status") not in {"required", "done", "not_supported"}:
        return payload("reanchor-missing")

    return payload("ok", package_tag=tag, package_commit=commit, install_report=str(report_file))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify installed business-ontology package proof.")
    parser.add_argument("--install-root", required=True, type=Path, help="Installed agent root.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        exit_code, result = verify_install(args.install_root)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

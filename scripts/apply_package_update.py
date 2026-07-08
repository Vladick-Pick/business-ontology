#!/usr/bin/env python3
"""Apply or roll back an installed package release."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from package_update_common import (  # noqa: E402
    UpdateLock,
    UpdateLockBusy,
    read_json_file,
    sanitize_remote_url,
    utc_timestamp,
    write_json_atomic,
)
from check_package_updates import ensure_bare_cache, normalize_tag, run_git  # noqa: E402

RELEASE_METADATA_NAME = ".package-release.json"
INSTALL_REPORT_NAME = "PACKAGE_INSTALL_REPORT.json"
FORBIDDEN_RELEASE_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
MODEL_CONTRACT_LOCK_NAME = "PACKAGE_CONTRACT.lock"
MODEL_VALIDATOR_CONTRACT = "data-model-v2-hard-gate"
PACKAGE_NAME = "business-ontology"
READINESS_LEDGER_DEFAULTS: dict[str, dict[str, object]] = {
    "source-instances.json": {"source_instances": []},
    "live-proofs/proofs.json": {"live_proofs": []},
}


def bounded_process_output(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    lines = [
        line.strip()
        for line in ((result.stdout or "") + "\n" + (result.stderr or "")).splitlines()
        if line.strip()
    ]
    return {
        "lines": [line[:240] for line in lines[:8]],
        "line_count": len(lines),
        "truncated": len(lines) > 8,
    }


def version_from_tag(tag: str) -> str:
    return normalize_tag(tag).removeprefix("v")


def version_tuple(value: str) -> tuple[int, int, int] | None:
    parts = value.removeprefix("v").split(".")
    if len(parts) < 3:
        return None
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def release_requires_strict_transitional_validation(release: Path) -> bool:
    version = version_tuple(release.name)
    return version is not None and version >= (0, 10, 0)


def lock_path(install_root: Path) -> Path:
    return install_root / "workspace" / "PACKAGE_VERSION.lock"


def install_report_path(install_root: Path) -> Path:
    return install_root / "workspace" / INSTALL_REPORT_NAME


def package_dir(install_root: Path) -> Path:
    return install_root / "package"


def releases_dir(install_root: Path) -> Path:
    return package_dir(install_root) / "releases"


def current_link(install_root: Path) -> Path:
    return package_dir(install_root) / "current"


def update_lock_path(install_root: Path) -> Path:
    return package_dir(install_root) / ".update.lock"


def release_dir(install_root: Path, tag: str) -> Path:
    return releases_dir(install_root) / normalize_tag(tag)


def release_metadata_path(path: Path) -> Path:
    return path / RELEASE_METADATA_NAME


def installed_workspace(root: Path) -> Path:
    workspace = root / "workspace"
    if workspace.exists():
        return workspace
    return root


def read_release_metadata(path: Path) -> dict[str, object]:
    metadata = release_metadata_path(path)
    if not metadata.exists():
        return {}
    return read_json_file(metadata)


def read_workspace_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    data = read_json_file(path)
    return data if isinstance(data, dict) else {}


def infer_workspace_state(install_root: Path, tag: str, sha: str) -> dict[str, object]:
    workspace = installed_workspace(install_root)
    runtime_config = read_workspace_json(workspace / "runtime-config.example.json")
    manifest = read_workspace_json(workspace / "agent-state" / "bootstrap-manifest.json")
    now = utc_timestamp()
    model_language = str(
        runtime_config.get("company_model_language")
        or manifest.get("companyModelLanguage")
        or "pending-owner-selection"
    )
    language_source = str(
        runtime_config.get("company_model_language_source")
        or ("pending-owner-onboarding" if model_language == "pending-owner-selection" else "owner-onboarding")
    )
    language_decided_at = None if model_language == "pending-owner-selection" else now
    created_at = str(runtime_config.get("generated_at") or manifest.get("generatedAt") or now)
    return {
        "agent_identity": {
            "package_name": PACKAGE_NAME,
            "package_version": version_from_tag(tag),
            "package_commit": sha,
        },
        "company_model": {
            "model_repo": str(runtime_config.get("accepted_model_repository") or manifest.get("ontologyRepoUrl") or "ask-human"),
            "model_repo_revision": str(runtime_config.get("ontology_revision") or "pending-human-owned-repo"),
            "company_model_language": model_language,
            "language_source": language_source,
            "language_decided_at": language_decided_at,
        },
        "workspace": {
            "workspace_id": str(runtime_config.get("module_id") or manifest.get("moduleId") or "company-baseline"),
            "created_at": created_at,
            "updated_at": now,
        },
    }


def refreshed_workspace_state(install_root: Path, tag: str, sha: str) -> dict[str, object]:
    workspace = installed_workspace(install_root)
    defaults = infer_workspace_state(install_root, tag, sha)
    existing = read_workspace_json(workspace / "workspace-state.json")
    if not existing:
        return defaults
    state = dict(existing)
    company_model = existing.get("company_model")
    workspace_state = existing.get("workspace")
    state["agent_identity"] = defaults["agent_identity"]
    state["company_model"] = company_model if isinstance(company_model, dict) else defaults["company_model"]
    if isinstance(workspace_state, dict):
        state["workspace"] = {**defaults["workspace"], **workspace_state, "updated_at": utc_timestamp()}
    else:
        state["workspace"] = defaults["workspace"]
    return state


def workspace_readiness_status(install_root: Path) -> dict[str, object]:
    workspace = installed_workspace(install_root)
    missing: list[str] = []
    invalid: list[str] = []
    for relative in ["workspace-state.json", *READINESS_LEDGER_DEFAULTS.keys()]:
        path = workspace / relative
        if not path.exists():
            missing.append(relative)
            continue
        try:
            data = read_json_file(path)
        except Exception:
            invalid.append(relative)
            continue
        if relative == "source-instances.json" and not isinstance(data.get("source_instances"), list):
            invalid.append(relative)
        elif relative == "live-proofs/proofs.json" and not isinstance(data.get("live_proofs"), list):
            invalid.append(relative)
        elif relative == "workspace-state.json":
            if not isinstance(data.get("agent_identity"), dict) or not isinstance(data.get("company_model"), dict):
                invalid.append(relative)
    status = "ready" if not missing and not invalid else "missing-or-invalid"
    return {
        "invalid": invalid,
        "missing": missing,
        "status": status,
    }


def ensure_workspace_readiness_ledgers(install_root: Path, tag: str, sha: str) -> dict[str, object]:
    workspace = installed_workspace(install_root)
    created: list[str] = []
    updated: list[str] = []
    workspace_state = workspace / "workspace-state.json"
    if workspace_state.exists():
        updated.append("workspace-state.json")
    else:
        created.append("workspace-state.json")
    write_json_atomic(workspace_state, refreshed_workspace_state(install_root, tag, sha))
    for relative, payload in READINESS_LEDGER_DEFAULTS.items():
        path = workspace / relative
        if not path.exists():
            write_json_atomic(path, payload)
            created.append(relative)
    status = workspace_readiness_status(install_root)
    return {
        **status,
        "created": created,
        "updated": updated,
    }


def write_release_metadata(path: Path, tag: str, commit: str) -> None:
    write_json_atomic(
        release_metadata_path(path),
        {
            "commit": commit,
            "tag": normalize_tag(tag),
        },
    )


def release_head(path: Path) -> str:
    metadata = read_release_metadata(path)
    commit = metadata.get("commit")
    if isinstance(commit, str) and commit:
        return commit
    return run_git(["rev-parse", "HEAD"], cwd=path)


def release_package_version(release: Path) -> str:
    version_file = release / "VERSION.txt"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    manifest = release / "agent-package.yaml"
    if manifest.exists():
        match = re.search(r'(?m)^version:\s*["\']?v?([^"\'\s]+)', manifest.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    return version_from_tag(release.name)


def remote_from_lock(lock: dict[str, object]) -> str:
    remote = str(lock.get("remote_url") or "")
    if not remote:
        raise RuntimeError("remote_url is missing from PACKAGE_VERSION.lock")
    return remote


def resolve_tag(cache_dir: Path, tag: str) -> str:
    try:
        return run_git(["rev-list", "-n", "1", normalize_tag(tag)], cwd=cache_dir)
    except RuntimeError as exc:
        raise RuntimeError(f"release tag not found: {tag}") from exc


def materialize_release(install_root: Path, cache_dir: Path, tag: str, expected_sha: str) -> tuple[Path, bool]:
    tag = normalize_tag(tag)
    target = release_dir(install_root, tag)
    if target.exists():
        actual_sha = release_head(target)
        if actual_sha != expected_sha:
            raise RuntimeError(f"{target} exists at {actual_sha}, expected {expected_sha}")
        return target, False
    target.parent.mkdir(parents=True, exist_ok=True)
    run_git(["clone", str(cache_dir), str(target)])
    run_git(["checkout", "--detach", tag], cwd=target)
    actual_sha = release_head(target)
    if actual_sha != expected_sha:
        shutil.rmtree(target)
        raise RuntimeError(f"{target} checked out {actual_sha}, expected {expected_sha}")
    write_release_metadata(target, tag, actual_sha)
    clean_release_tree(target)
    return target, True


def run_self_test(path: Path) -> dict[str, object]:
    self_test = path / "scripts" / "package_self_test.py"
    if self_test.exists():
        timeout = os.environ.get("BUSINESS_ONTOLOGY_PACKAGE_SELF_TEST_TIMEOUT", "300")
        command = [sys.executable, str(self_test), "--suite-timeout", timeout]
        env = os.environ.copy()
        env["BUSINESS_ONTOLOGY_UPDATE_SELF_TEST"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            command,
            cwd=path,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        return {
            "command": " ".join(command),
            "exit_code": result.returncode,
            "output": bounded_process_output(result),
            "status": "passed" if result.returncode == 0 else "failed",
        }
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    unit = subprocess.run(command, cwd=path, env=env, check=False)
    if unit.returncode != 0:
        return {
            "command": " ".join(command),
            "exit_code": unit.returncode,
            "status": "failed",
        }
    eval_command = [sys.executable, "scripts/run_evals.py", "--fixture-only"]
    evals = subprocess.run(eval_command, cwd=path, env=env, check=False)
    return {
        "command": " && ".join((" ".join(command), " ".join(eval_command))),
        "exit_code": evals.returncode,
        "status": "passed" if evals.returncode == 0 else "failed",
    }


def copy_model_tree(model_repo: Path, destination: Path) -> Path:
    model_copy = destination / "model-copy"
    shutil.copytree(model_repo, model_copy, ignore=shutil.ignore_patterns(".git"))
    return model_copy


def validate_model_copy(release: Path, model_repo: Path) -> tuple[bool, int]:
    validator = release / "scripts" / "links_validate.py"
    if not validator.exists():
        return True, 0
    with tempfile.TemporaryDirectory() as tmp:
        model_copy = copy_model_tree(model_repo, Path(tmp))
        args = [sys.executable, str(validator), str(model_copy)]
        if release_requires_strict_transitional_validation(release):
            args.append("--strict-transitional")
        result = subprocess.run(
            args,
            cwd=release,
            text=True,
            capture_output=True,
            check=False,
        )
    if result.returncode == 0:
        return True, 0
    return False, max(1, parse_error_count(result.stdout + "\n" + result.stderr))


def model_validation_report(release: Path, model_repo: Path | None) -> tuple[bool, dict[str, object]]:
    if model_repo is None:
        return True, {"status": "skipped", "used_copy": False}
    ok, errors = validate_model_copy(release, model_repo)
    return ok, {
        "errors": errors,
        "status": "passed" if ok else "failed",
        "used_copy": True,
    }


def expected_model_support_contract(release: Path) -> dict[str, object]:
    return {
        "package_commit": release_head(release),
        "package_name": PACKAGE_NAME,
        "package_version": release_package_version(release),
        "validator": "scripts/links_validate.py",
        "validator_contract": MODEL_VALIDATOR_CONTRACT,
    }


def model_support_contract_report(release: Path, model_repo: Path | None) -> dict[str, object]:
    if model_repo is None:
        return {"status": "skipped", "review_required": False}

    expected = expected_model_support_contract(release)
    lock_path = model_repo / MODEL_CONTRACT_LOCK_NAME
    copied_validator = model_repo / "scripts" / "links_validate.py"
    report: dict[str, object] = {
        "expected": expected,
        "lock_path": str(lock_path),
        "review_required": False,
    }

    if copied_validator.exists():
        report.update(
            {
                "copied_validator": str(copied_validator),
                "reason": "model repo contains a copied validator; use the thin wrapper instead",
                "review_required": True,
                "status": "unsupported-copied-validator",
            }
        )
        return report

    if not lock_path.exists():
        report.update(
            {
                "reason": f"{MODEL_CONTRACT_LOCK_NAME} is missing",
                "review_required": True,
                "status": "missing",
            }
        )
        return report

    try:
        actual = read_json_file(lock_path)
    except Exception as exc:
        report.update(
            {
                "reason": f"{MODEL_CONTRACT_LOCK_NAME} is not readable JSON: {exc}",
                "review_required": True,
                "status": "invalid",
            }
        )
        return report
    mismatched = sorted(key for key, expected_value in expected.items() if actual.get(key) != expected_value)
    report["actual"] = actual
    if mismatched:
        report.update(
            {
                "mismatched_fields": mismatched,
                "reason": "model repo support contract does not match installed package",
                "review_required": True,
                "status": "drift",
            }
        )
        return report

    report["status"] = "current"
    return report


def parse_error_count(output: str) -> int:
    for token in ("errors", "Errors", "ERRORS"):
        marker = f"{token}:"
        if marker in output:
            tail = output.split(marker, 1)[1].strip().split(maxsplit=1)[0]
            if tail.isdigit():
                return int(tail)
    return 1


def clean_release_tree(release: Path) -> None:
    for path in sorted(release.rglob("*"), key=lambda candidate: len(candidate.parts), reverse=True):
        if path.name not in FORBIDDEN_RELEASE_DIRS:
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)


def forbidden_release_residue(release: Path) -> list[str]:
    residue: list[str] = []
    for path in sorted(release.rglob("*")):
        if any(part in FORBIDDEN_RELEASE_DIRS for part in path.relative_to(release).parts):
            residue.append(str(path.relative_to(release)))
    return residue


def source_tree_hash(release: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(release.rglob("*")):
        relative = path.relative_to(release)
        if path.name == RELEASE_METADATA_NAME:
            continue
        if any(part in FORBIDDEN_RELEASE_DIRS for part in relative.parts):
            continue
        digest.update(str(relative).encode("utf-8"))
        if path.is_symlink():
            digest.update(b"\0symlink\0")
            digest.update(os.readlink(path).encode("utf-8"))
        elif path.is_file():
            digest.update(b"\0file\0")
            digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
        elif path.is_dir():
            digest.update(b"\0dir\0")
    return digest.hexdigest()


def relative_install_path(install_root: Path, path: Path) -> str:
    return str(path.relative_to(install_root))


def write_install_report(
    install_root: Path,
    *,
    tag: str,
    sha: str,
    release: Path,
    remote: str,
    old_lock: dict[str, object],
    self_test: dict[str, object],
    model_validation: dict[str, object],
    model_support_contract: dict[str, object],
    workspace_readiness: dict[str, object],
    started_at: str,
    status: str = "installed",
) -> Path:
    previous_tag = normalize_tag(old_lock.get("tag") or old_lock.get("current_version"))
    report = {
        "current_symlink": relative_install_path(install_root, current_link(install_root)),
        "finished_at": utc_timestamp(),
        "lock_file": relative_install_path(install_root, lock_path(install_root)),
        "model_validation": model_validation,
        "model_support_contract": model_support_contract,
        "package_commit": sha,
        "package_tag": normalize_tag(tag),
        "reanchor": {"status": "required"},
        "release_dir": relative_install_path(install_root, release),
        "rollback": {
            "available_offline": release_dir(install_root, previous_tag).exists(),
            "previous_commit": old_lock.get("commit"),
            "previous_tag": previous_tag,
        },
        "self_test": self_test,
        "source_tree_hash": source_tree_hash(release),
        "source_url": sanitize_remote_url(remote),
        "started_at": started_at,
        "status": status,
        "updater_package_commit": old_lock.get("commit"),
        "updater_script": "scripts/apply_package_update.py",
        "workspace_readiness": workspace_readiness,
    }
    path = install_report_path(install_root)
    write_json_atomic(path, report)
    return path


def atomic_flip(install_root: Path, tag: str) -> None:
    current = current_link(install_root)
    tmp = current.with_name(f".current.tmp-{os.getpid()}")
    tmp.unlink(missing_ok=True)
    os.symlink(str(Path("releases") / normalize_tag(tag)), tmp)
    os.replace(tmp, current)


def running_release_dir(install_root: Path) -> Path | None:
    try:
        script_path = Path(__file__).resolve()
    except OSError:
        return None
    releases = releases_dir(install_root).resolve()
    for parent in script_path.parents:
        if parent.parent == releases:
            return parent
    return None


def prune_releases(install_root: Path, keep_tags: set[str]) -> None:
    running = running_release_dir(install_root)
    for path in releases_dir(install_root).iterdir():
        if not path.is_dir():
            continue
        if path.name in keep_tags:
            continue
        if running is not None and path.resolve() == running:
            continue
        shutil.rmtree(path)


def update_lock_for_apply(lock_file: Path, old_lock: dict[str, object], tag: str, sha: str, remote: str) -> None:
    payload = {
        "commit": sha,
        "current_version": version_from_tag(tag),
        "installed_at": utc_timestamp(),
        "previous_commit": old_lock.get("commit"),
        "previous_version": old_lock.get("current_version") or version_from_tag(str(old_lock.get("tag"))),
        "remote_url": sanitize_remote_url(remote),
        "tag": normalize_tag(tag),
    }
    write_json_atomic(lock_file, payload)


def update_lock_for_rollback(lock_file: Path, old_lock: dict[str, object]) -> dict[str, object]:
    previous_version = str(old_lock.get("previous_version") or "")
    previous_commit = str(old_lock.get("previous_commit") or "")
    if not previous_version or not previous_commit:
        raise RuntimeError("previous release is missing from PACKAGE_VERSION.lock")
    payload = {
        "commit": previous_commit,
        "current_version": previous_version,
        "installed_at": utc_timestamp(),
        "previous_commit": old_lock.get("commit"),
        "previous_version": old_lock.get("current_version"),
        "remote_url": sanitize_remote_url(str(old_lock.get("remote_url") or "")),
        "tag": normalize_tag(previous_version),
    }
    write_json_atomic(lock_file, payload)
    return payload


def apply_update(install_root: Path, tag: str, model_repo: Path | None, dry_run: bool) -> tuple[int, dict[str, object]]:
    tag = normalize_tag(tag)
    lock_file = lock_path(install_root)
    old_lock = read_json_file(lock_file)
    remote = remote_from_lock(old_lock)
    if dry_run:
        return 0, {"status": "dry-run", "to": tag, "current": old_lock.get("tag")}

    started_at = utc_timestamp()
    cache_dir = package_dir(install_root) / ".cache.git"
    ensure_bare_cache(cache_dir, remote)
    sha = resolve_tag(cache_dir, tag)
    release, fresh = materialize_release(install_root, cache_dir, tag, sha)
    self_test = run_self_test(release)
    if self_test["status"] != "passed":
        if fresh:
            shutil.rmtree(release)
        return 4, {"status": "self-test-failed", "tag": tag, "self_test": self_test}
    model_ok, validation = model_validation_report(release, model_repo)
    support_contract = model_support_contract_report(release, model_repo)
    if not model_ok:
        return 3, {
            "status": "migration-required",
            "errors": validation["errors"],
            "model_support_contract": support_contract,
            "tag": tag,
        }
    atomic_flip(install_root, tag)
    update_lock_for_apply(lock_file, old_lock, tag, sha, remote)
    readiness = ensure_workspace_readiness_ledgers(install_root, tag, sha)
    previous_tag = normalize_tag(old_lock.get("tag") or old_lock.get("current_version"))
    clean_release_tree(release)
    report = write_install_report(
        install_root,
        tag=tag,
        sha=sha,
        release=release,
        remote=remote,
        old_lock=old_lock,
        self_test=self_test,
        model_validation=validation,
        model_support_contract=support_contract,
        workspace_readiness=readiness,
        started_at=started_at,
    )
    prune_releases(install_root, {tag, previous_tag})
    return 0, {"status": "updated", "tag": tag, "commit": sha, "install_report": str(report)}


def rollback_update(install_root: Path) -> tuple[int, dict[str, object]]:
    started_at = utc_timestamp()
    lock_file = lock_path(install_root)
    old_lock = read_json_file(lock_file)
    previous_version = str(old_lock.get("previous_version") or "")
    previous_commit = str(old_lock.get("previous_commit") or "")
    if not previous_version or not previous_commit:
        raise RuntimeError("previous release is missing from PACKAGE_VERSION.lock")
    previous_tag = normalize_tag(previous_version)
    previous_release = release_dir(install_root, previous_tag)
    if not previous_release.exists():
        raise RuntimeError(f"previous release directory is missing: {previous_release}")
    actual_sha = release_head(previous_release)
    if actual_sha != previous_commit:
        raise RuntimeError(f"previous release sha mismatch: {actual_sha} != {previous_commit}")
    write_release_metadata(previous_release, previous_tag, actual_sha)
    self_test = run_self_test(previous_release)
    if self_test["status"] != "passed":
        return 4, {"status": "self-test-failed", "tag": previous_tag, "self_test": self_test}
    atomic_flip(install_root, previous_tag)
    payload = update_lock_for_rollback(lock_file, old_lock)
    readiness = ensure_workspace_readiness_ledgers(install_root, previous_tag, previous_commit)
    clean_release_tree(previous_release)
    report = write_install_report(
        install_root,
        tag=previous_tag,
        sha=previous_commit,
        release=previous_release,
        remote=str(old_lock.get("remote_url") or ""),
        old_lock=old_lock,
        self_test=self_test,
        model_validation={"status": "not_required_for_rollback", "used_copy": False},
        model_support_contract={"status": "not_required_for_rollback", "review_required": False},
        workspace_readiness=readiness,
        started_at=started_at,
        status="rolled-back",
    )
    return 0, {"status": "rolled-back", "tag": payload["tag"], "commit": payload["commit"], "install_report": str(report)}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply or roll back a business-ontology package release.")
    parser.add_argument("--install-root", required=True, type=Path, help="Installed agent root.")
    parser.add_argument("--to", help="Release tag to install, e.g. v0.10.0.")
    parser.add_argument("--model-repo", type=Path, help="Accepted model repository for read-only validation copy.")
    parser.add_argument("--rollback", action="store_true", help="Roll back to previous release from the lock file.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned action without writing.")
    parser.add_argument("--force-unlock", action="store_true", help="Remove a stale update lock before starting.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    install_root = args.install_root.resolve()
    if not args.rollback and not args.to:
        print("--to is required unless --rollback is used", file=sys.stderr)
        return 2
    try:
        with UpdateLock(update_lock_path(install_root), force_unlock=args.force_unlock):
            if args.rollback:
                exit_code, payload = rollback_update(install_root)
            else:
                exit_code, payload = apply_update(install_root, args.to, args.model_repo, args.dry_run)
    except UpdateLockBusy as exc:
        print(json.dumps({"status": "locked", "pid": exc.pid, "lock": str(exc.path)}, sort_keys=True))
        return 5
    except Exception as exc:
        print(sanitize_remote_url(str(exc)), file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

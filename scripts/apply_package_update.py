#!/usr/bin/env python3
"""Apply or roll back an installed package release."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

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


def version_from_tag(tag: str) -> str:
    return normalize_tag(tag).removeprefix("v")


def lock_path(install_root: Path) -> Path:
    return install_root / "workspace" / "PACKAGE_VERSION.lock"


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


def release_head(path: Path) -> str:
    return run_git(["rev-parse", "HEAD"], cwd=path)


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
    return target, True


def run_self_test(path: Path) -> int:
    self_test = path / "scripts" / "package_self_test.py"
    if self_test.exists():
        return subprocess.run([sys.executable, str(self_test)], cwd=path, check=False).returncode
    unit = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"], cwd=path, check=False)
    if unit.returncode != 0:
        return unit.returncode
    return subprocess.run([sys.executable, "scripts/run_evals.py", "--fixture-only"], cwd=path, check=False).returncode


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
        result = subprocess.run(
            [sys.executable, str(validator), str(model_copy)],
            cwd=release,
            text=True,
            capture_output=True,
            check=False,
        )
    if result.returncode == 0:
        return True, 0
    return False, max(1, parse_error_count(result.stdout + "\n" + result.stderr))


def parse_error_count(output: str) -> int:
    for token in ("errors", "Errors", "ERRORS"):
        marker = f"{token}:"
        if marker in output:
            tail = output.split(marker, 1)[1].strip().split(maxsplit=1)[0]
            if tail.isdigit():
                return int(tail)
    return 1


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

    cache_dir = package_dir(install_root) / ".cache.git"
    ensure_bare_cache(cache_dir, remote)
    sha = resolve_tag(cache_dir, tag)
    release, fresh = materialize_release(install_root, cache_dir, tag, sha)
    try:
        if run_self_test(release) != 0:
            if fresh:
                shutil.rmtree(release)
            return 4, {"status": "self-test-failed", "tag": tag}
        if model_repo is not None:
            ok, errors = validate_model_copy(release, model_repo)
            if not ok:
                return 3, {"status": "migration-required", "errors": errors, "tag": tag}
        atomic_flip(install_root, tag)
        update_lock_for_apply(lock_file, old_lock, tag, sha, remote)
        previous_tag = normalize_tag(old_lock.get("tag") or old_lock.get("current_version"))
        prune_releases(install_root, {tag, previous_tag})
        return 0, {"status": "updated", "tag": tag, "commit": sha}
    finally:
        pass


def rollback_update(install_root: Path) -> tuple[int, dict[str, object]]:
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
    atomic_flip(install_root, previous_tag)
    payload = update_lock_for_rollback(lock_file, old_lock)
    return 0, {"status": "rolled-back", "tag": payload["tag"], "commit": payload["commit"]}


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

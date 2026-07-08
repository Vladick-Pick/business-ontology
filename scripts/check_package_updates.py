#!/usr/bin/env python3
"""Check package release tags against an installed PACKAGE_VERSION.lock."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from package_update_common import (  # noqa: E402
    UpdateLock,
    UpdateLockBusy,
    read_json_file,
    sanitize_remote_url,
)


SEMVER_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def semver_key(tag: str) -> tuple[int, int, int]:
    match = SEMVER_TAG_RE.match(tag)
    if not match:
        raise ValueError(f"not a release semver tag: {tag}")
    return tuple(int(part) for part in match.groups())


def normalize_tag(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "v0.0.0"
    return text if text.startswith("v") else f"v{text}"


def install_root_for_lock(lock_path: Path) -> Path:
    return lock_path.resolve().parent.parent


def run_git(args: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = sanitize_remote_url(result.stderr.strip() or result.stdout.strip())
        raise RuntimeError(message or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def ensure_bare_cache(cache_dir: Path, remote_url: str) -> None:
    safe_remote = sanitize_remote_url(remote_url)
    if not cache_dir.exists():
        cache_dir.parent.mkdir(parents=True, exist_ok=True)
        run_git(["clone", "--bare", safe_remote, str(cache_dir)])
    else:
        run_git(["remote", "set-url", "origin", safe_remote], cwd=cache_dir)
    run_git(["fetch", "--tags", "--prune", "origin"], cwd=cache_dir)


def release_tags(cache_dir: Path) -> list[str]:
    tags = run_git(["tag", "--list"], cwd=cache_dir).splitlines()
    return sorted((tag for tag in tags if SEMVER_TAG_RE.match(tag)), key=semver_key)


def changelog_for_tag(cache_dir: Path, tag: str) -> str:
    try:
        changelog = run_git(["show", f"{tag}:CHANGELOG.md"], cwd=cache_dir)
    except RuntimeError:
        return ""
    version = re.escape(tag.removeprefix("v"))
    heading = re.compile(rf"^##\s+\[?v?{version}\b.*$", re.MULTILINE)
    match = heading.search(changelog)
    if not match:
        return ""
    next_heading = re.search(r"^##\s+", changelog[match.end() :], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(changelog)
    return changelog[match.start() : end].strip()


def check_updates(lock_path: Path, remote_override: str | None = None) -> tuple[dict[str, object], int]:
    lock = read_json_file(lock_path)
    install_root = install_root_for_lock(lock_path)
    remote = str(remote_override or lock.get("remote_url") or "")
    if not remote:
        raise RuntimeError("remote_url is missing from PACKAGE_VERSION.lock")
    cache_dir = install_root / "package" / ".cache.git"
    update_lock = install_root / "package" / ".update.lock"

    with UpdateLock(update_lock):
        ensure_bare_cache(cache_dir, remote)

    current = normalize_tag(lock.get("tag") or lock.get("current_version"))
    tags = release_tags(cache_dir)
    latest = tags[-1] if tags else current
    newer = [tag for tag in tags if semver_key(tag) > semver_key(current)]
    payload = {
        "current": current,
        "latest": latest,
        "newer": newer,
        "changelog_excerpt": changelog_for_tag(cache_dir, latest) if newer else "",
        "remote": sanitize_remote_url(remote),
    }
    return payload, 10 if newer else 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check for newer business-ontology package release tags.")
    parser.add_argument("--lock", required=True, type=Path, help="Path to workspace/PACKAGE_VERSION.lock.")
    parser.add_argument("--remote", help="Override remote URL for this check.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        payload, exit_code = check_updates(args.lock, args.remote)
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

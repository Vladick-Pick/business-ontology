#!/usr/bin/env python3
"""Publish the official read-only model viewer with validation proof."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_viewer_bundle import build_bundle, empty_source_readiness  # noqa: E402
from package_update_common import utc_timestamp, write_json_atomic  # noqa: E402


VALIDATION_FAILED = 3
CUSTOM_VIEWER_REJECTED = 4
CONFIG_INVALID = 5


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def run_command(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )


def package_version(package_root: Path) -> str:
    version_file = package_root / "VERSION.txt"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    manifest = package_root / "agent-package.yaml"
    if not manifest.exists():
        return "unknown"
    match = re.search(r'^version:\s*"?([^"\n]+)"?\s*$', manifest.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1).strip() if match else "unknown"


def git_revision(path: Path) -> str:
    result = run_command(["git", "-C", str(path), "rev-parse", "--short", "HEAD"])
    if result.returncode != 0:
        return "local-export"
    return result.stdout.strip() or "local-export"


def git_commit(path: Path) -> str:
    metadata = path / ".package-release.json"
    if metadata.exists():
        data = load_json(metadata)
        commit = data.get("commit")
        if isinstance(commit, str) and commit:
            return commit
    result = run_command(["git", "-C", str(path), "rev-parse", "HEAD"])
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_runtime_config(workspace: Path) -> dict[str, Any]:
    for name in ["runtime-config.json", "runtime-config.example.json"]:
        data = load_json(workspace / name)
        if data:
            return data
    return {}


def workspace_child(workspace: Path, value: object, default: str) -> Path:
    relative = Path(str(value or default))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"workspace config path must be relative and stay inside workspace: {relative}")
    return workspace / relative


def company_model_language(workspace: Path, config: dict[str, Any]) -> str:
    state = load_json(workspace / "workspace-state.json")
    company_model = state.get("company_model") if isinstance(state.get("company_model"), dict) else {}
    value = company_model.get("company_model_language") or config.get("company_model_language")
    return str(value or "pending-owner-selection")


def source_readiness_from_workspace(workspace: Path, config: dict[str, Any]) -> dict[str, Any]:
    path = workspace_child(workspace, config.get("source_instances_path"), "source-instances.json")
    data = load_json(path)
    instances = data.get("source_instances")
    if not isinstance(instances, list):
        return empty_source_readiness()

    buckets = {
        "configured": [],
        "source-connected": [],
        "live-proven": [],
        "scheduled": [],
        "failed": [],
    }
    last_proofs: dict[str, str] = {}
    for item in instances:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "configured")
        source_id = str(item.get("source_instance_id") or "")
        if status not in buckets:
            status = "configured"
        if source_id:
            buckets[status].append(source_id)
        proof_id = str(item.get("last_live_proof_id") or "")
        if source_id and proof_id:
            last_proofs[source_id] = proof_id

    return {
        "configuredCount": len(buckets["configured"]),
        "sourceConnectedCount": len(buckets["source-connected"]),
        "liveProvenCount": len(buckets["live-proven"]),
        "scheduledCount": len(buckets["scheduled"]),
        "failedCount": len(buckets["failed"]),
        "sourceInstanceIdsByStatus": buckets,
        "lastProofIdsBySource": last_proofs,
    }


def source_readiness_report(readiness: dict[str, Any]) -> dict[str, Any]:
    return {
        "configured": int(readiness.get("configuredCount") or 0),
        "source_connected": int(readiness.get("sourceConnectedCount") or 0),
        "live_proven": int(readiness.get("liveProvenCount") or 0),
        "scheduled": int(readiness.get("scheduledCount") or 0),
        "failed": int(readiness.get("failedCount") or 0),
        "source_instance_ids_by_status": readiness.get("sourceInstanceIdsByStatus") or {},
        "last_proof_ids_by_source": readiness.get("lastProofIdsBySource") or {},
    }


def open_human_request_count(workspace: Path, config: dict[str, Any]) -> int:
    store_path_value = config.get("store_path")
    if isinstance(store_path_value, str) and store_path_value:
        store_path = workspace_child(workspace, store_path_value, "agent-state/operational-store.sqlite")
        count = open_human_request_count_from_sqlite(store_path)
        if count is not None:
            return count

    json_path = workspace / "human-requests.json"
    data = load_json(json_path)
    requests = data.get("human_requests")
    if isinstance(requests, list):
        return sum(1 for item in requests if isinstance(item, dict) and item.get("status") == "open")

    requests_dir = workspace / "human-requests"
    if not requests_dir.exists():
        return 0
    count = 0
    for path in sorted(requests_dir.glob("*.json")):
        data = load_json(path)
        if data.get("status") == "open":
            count += 1
    return count


def open_human_request_count_from_sqlite(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        with sqlite3.connect(str(path)) as connection:
            has_table = connection.execute(
                "select name from sqlite_master where type='table' and name='human_requests'"
            ).fetchone()
            if not has_table:
                return None
            row = connection.execute(
                "select count(*) from human_requests where status = 'open'"
            ).fetchone()
            return int(row[0]) if row else 0
    except sqlite3.Error:
        return None


def bounded_output_summary(stdout: str, stderr: str) -> dict[str, Any]:
    lines = [line.strip() for line in (stdout + "\n" + stderr).splitlines() if line.strip()]
    visible = [line[:240] for line in lines[:8]]
    return {
        "lines": visible,
        "line_count": len(lines),
        "truncated": len(lines) > len(visible),
    }


def validate_model(package_root: Path, model_root: Path) -> tuple[bool, dict[str, Any]]:
    wrapper = model_root / "scripts" / "validate_model_repo.py"
    if wrapper.exists():
        command = [sys.executable, str(wrapper), "--package", str(package_root)]
        validator = "model-repo-wrapper"
    else:
        command = [
            sys.executable,
            str(package_root / "scripts" / "links_validate.py"),
            str(model_root),
            "--strict-transitional",
        ]
        validator = "package-links-validator"
    result = run_command(command)
    validation = {
        "status": "passed" if result.returncode == 0 else "failed",
        "validator": validator,
        "command": command,
        "exit_code": result.returncode,
        "output": bounded_output_summary(result.stdout, result.stderr),
    }
    return result.returncode == 0, validation


def ensure_official_viewer(package_root: Path, out_dir: Path, *, allow_overwrite_custom: bool) -> tuple[str, str]:
    source = package_root / "viewer" / "index.html"
    destination = out_dir / "index.html"
    source_text = source.read_text(encoding="utf-8")
    source_hash = sha256_text(source_text)

    if destination.exists():
        existing_hash = sha256_file(destination)
        if existing_hash != source_hash and not allow_overwrite_custom:
            raise RuntimeError("custom-viewer-rejected")

    return source_text, source_hash


def publish(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    package_root = Path(args.package_root).resolve()
    model_root = Path(args.model_root).resolve()
    workspace = Path(args.workspace).resolve()
    out_dir = Path(args.out_dir).resolve()

    valid, validation = validate_model(package_root, model_root)
    if not valid:
        return VALIDATION_FAILED, {"status": "validation-failed", "validation": validation}

    try:
        viewer_text, viewer_asset_hash = ensure_official_viewer(
            package_root,
            out_dir,
            allow_overwrite_custom=args.allow_overwrite_custom,
        )
    except RuntimeError as exc:
        if str(exc) == "custom-viewer-rejected":
            return CUSTOM_VIEWER_REJECTED, {"status": "custom-viewer-rejected"}
        raise

    try:
        config = load_runtime_config(workspace)
        language = company_model_language(workspace, config)
        readiness = source_readiness_from_workspace(workspace, config)
        open_request_count = open_human_request_count(workspace, config)
    except ValueError as exc:
        return CONFIG_INVALID, {"status": "config-invalid", "reason": str(exc)}
    revision = args.revision or git_revision(model_root)
    module = args.module or str(config.get("module_id") or model_root.name)
    version = package_version(package_root)
    commit = git_commit(package_root)

    bundle = build_bundle(
        model_root,
        module,
        revision,
        args.as_of,
        company_model_language=language,
        package_version=version,
        package_commit=commit,
        model_revision=revision,
        source_readiness=readiness,
        open_human_request_count=open_request_count,
        validation_status="passed",
    )
    bundle_text = json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    bundle_hash = sha256_text(bundle_text)

    report = {
        "status": "published",
        "package_version": version,
        "package_commit": commit,
        "model_revision": revision,
        "company_model_language": language,
        "source_readiness": source_readiness_report(readiness),
        "open_human_request_count": open_request_count,
        "validation": validation,
        "viewer_asset_hash": viewer_asset_hash,
        "bundle_hash": bundle_hash,
        "published_at": utc_timestamp(),
        "viewer_index": "index.html",
        "bundle": "ontology.json",
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(viewer_text, encoding="utf-8")
    (out_dir / "ontology.json").write_text(bundle_text, encoding="utf-8")
    write_json_atomic(out_dir / "VIEWER_PUBLISH_REPORT.json", report)

    return 0, report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Publish the official company model viewer.")
    parser.add_argument("model_root", help="Accepted model repository/export root.")
    parser.add_argument("--workspace", required=True, help="Installed workspace root.")
    parser.add_argument("--out-dir", required=True, help="Published viewer directory.")
    parser.add_argument("--package-root", default=str(SCRIPT_DIR.parent), help="Package root.")
    parser.add_argument("--module", default=None, help="Module id. Defaults to runtime config or model folder.")
    parser.add_argument("--revision", default=None, help="Model revision. Defaults to model git HEAD or local-export.")
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD for stale audit counts.")
    parser.add_argument(
        "--allow-overwrite-custom",
        action="store_true",
        help="Explicit operator/test override to replace a non-official published HTML file.",
    )
    parser.add_argument("--json", action="store_true", help="Print the full publish report as JSON.")
    args = parser.parse_args(argv[1:])

    code, payload = publish(args)
    if args.json or code != 0:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "viewer published: "
            f"{payload['viewer_index']} + {payload['bundle']} -> {Path(args.out_dir).resolve()}"
        )
        print(f"publish report: {Path(args.out_dir).resolve() / 'VIEWER_PUBLISH_REPORT.json'}")
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

#!/usr/bin/env python3
"""Publish the official read-only model viewer with validation proof."""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_viewer_bundle import (  # noqa: E402
    HUMAN_REQUEST_LIMIT,
    accepted_context_cards,
    accepted_context_sources,
    build_bundle,
    empty_source_readiness,
)
from package_update_common import utc_timestamp, write_json_atomic  # noqa: E402
from viewer_privacy import privacy_report  # noqa: E402
from viewer_reachability import apply_reachability, load_reachability  # noqa: E402


VALIDATION_FAILED = 3
CUSTOM_VIEWER_REJECTED = 4
CONFIG_INVALID = 5
PUBLICATION_VERIFICATION_FAILED = 6
PRIVACY_FAILED = 7
PUBLICATION_MODES = {"workspace-only", "static-url", "tailscale-funnel"}
WORKING_PACKAGE_LIMIT = 50
NON_WORKING_PACKAGE_STATUSES = (
    "applied",
    "rejected",
    "superseded",
    "no-op",
    "no-review-needed",
)
PUBLIC_FETCH_LIMIT = 8 * 1024 * 1024


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


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def viewer_publication_config(config: dict[str, Any]) -> dict[str, str]:
    value = config.get("viewer_publication")
    if value is None:
        return {"mode": "workspace-only", "public_url": ""}
    if not isinstance(value, dict):
        raise ValueError("viewer_publication must be an object")
    mode = str(value.get("mode") or "workspace-only")
    if mode not in PUBLICATION_MODES:
        raise ValueError(f"viewer_publication.mode must be one of {sorted(PUBLICATION_MODES)}")
    public_url = str(value.get("public_url") or "")
    if mode == "workspace-only":
        if public_url:
            raise ValueError("workspace-only viewer publication must not declare public_url")
        return {"mode": mode, "public_url": ""}
    if not public_url:
        raise ValueError(f"{mode} viewer publication requires public_url")
    parsed = urlsplit(public_url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("viewer public_url must be a credential-free HTTPS directory URL")
    normalized = public_url.rstrip("/") + "/"
    return {"mode": mode, "public_url": normalized}


def workspace_child(workspace: Path, value: object, default: str) -> Path:
    relative = Path(str(value or default))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"workspace config path must be relative and stay inside workspace: {relative}")
    return workspace / relative


def accepted_context_snapshot(
    workspace: Path,
    model_root: Path,
    config: dict[str, Any],
) -> tuple[dict[str, Any], Path | None]:
    configured = workspace_child(
        workspace,
        config.get("accepted_context_path"),
        "model/ontology/accepted-context.json",
    )
    candidates = [configured, model_root / "ontology" / "accepted-context.json"]
    for path in candidates:
        if path.exists():
            payload = load_json(path)
            if payload:
                return payload, path
    return {}, None


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


def _human_request_from_json(data: dict[str, Any]) -> dict[str, Any]:
    return data if isinstance(data, dict) else {}


def _parse_blocks_json(value: object) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        blocks = data.get("blocks")
    else:
        blocks = data
    if not isinstance(blocks, list):
        return []
    return [str(item) for item in blocks if str(item)]


def _sqlite_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error:
        return set()


def _sqlite_open_status_clause(columns: set[str]) -> str:
    if "status" not in columns:
        return "1 = 0"
    return "status IN ('open', 'deferred')"


def _sqlite_human_request_rows(path: Path, *, limit: int = HUMAN_REQUEST_LIMIT) -> tuple[list[dict[str, Any]], int] | None:
    if not path.exists():
        return None
    try:
        with closing(sqlite3.connect(str(path))) as connection:
            connection.row_factory = sqlite3.Row
            has_table = connection.execute(
                "select name from sqlite_master where type='table' and name='human_requests'"
            ).fetchone()
            if not has_table:
                return None
            columns = _sqlite_columns(connection, "human_requests")
            if "request_id" not in columns or "status" not in columns:
                return None
            count_row = connection.execute(
                f"select count(*) from human_requests where {_sqlite_open_status_clause(columns)}"
            ).fetchone()
            count = int(count_row[0]) if count_row else 0
            wanted = [
                "request_id",
                "kind",
                "status",
                "owner",
                "channel",
                "message_ref",
                "prompt",
                "recommended_answer",
                "blocks_json",
                "source_ref",
                "package_id",
                "asked_at",
                "due_at",
            ]
            selected = [name for name in wanted if name in columns]
            if not selected:
                return [], count
            if {"due_at", "asked_at"} <= columns:
                order_by = "ORDER BY COALESCE(NULLIF(due_at, ''), asked_at) ASC, asked_at ASC, request_id ASC"
            elif "asked_at" in columns:
                order_by = "ORDER BY asked_at ASC, request_id ASC"
            else:
                order_by = "ORDER BY request_id ASC"
            rows = connection.execute(
                f"""
                SELECT {", ".join(selected)}
                  FROM human_requests
                 WHERE {_sqlite_open_status_clause(columns)}
                 {order_by}
                 LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
            requests: list[dict[str, Any]] = []
            for row in rows:
                item = {key: row[key] for key in row.keys()}
                request = {
                    "requestId": str(item.get("request_id") or ""),
                    "kind": str(item.get("kind") or "clarification"),
                    "status": str(item.get("status") or "open"),
                    "owner": str(item.get("owner") or "unknown"),
                    "channel": str(item.get("channel") or "unknown"),
                    "messageRef": str(item.get("message_ref") or ""),
                    "prompt": str(item.get("prompt") or item.get("request_id") or ""),
                    "recommendedAnswer": str(item.get("recommended_answer") or ""),
                    "blocks": _parse_blocks_json(item.get("blocks_json")),
                    "sourceRef": str(item.get("source_ref") or ""),
                    "packageId": str(item.get("package_id") or ""),
                    "askedAt": str(item.get("asked_at") or ""),
                    "dueAt": str(item.get("due_at") or ""),
                }
                requests.append(request)
            return requests, count
    except sqlite3.Error:
        return None


def _open_status(value: object) -> bool:
    return str(value or "") in {"open", "deferred"}


def open_human_request_snapshot(workspace: Path, config: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    store_path_value = config.get("store_path")
    if isinstance(store_path_value, str) and store_path_value:
        store_path = workspace_child(workspace, store_path_value, "agent-state/operational-store.sqlite")
        snapshot = _sqlite_human_request_rows(store_path)
        if snapshot is not None:
            return snapshot

    json_path = workspace / "human-requests.json"
    data = load_json(json_path)
    requests = data.get("human_requests")
    if isinstance(requests, list):
        open_requests = [
            _human_request_from_json(item)
            for item in requests
            if isinstance(item, dict) and _open_status(item.get("status"))
        ]
        return open_requests[:HUMAN_REQUEST_LIMIT], len(open_requests)

    requests_dir = workspace / "human-requests"
    if not requests_dir.exists():
        return [], 0
    open_requests = []
    for path in sorted(requests_dir.glob("*.json")):
        data = load_json(path)
        if _open_status(data.get("status")):
            open_requests.append(data)
    return open_requests[:HUMAN_REQUEST_LIMIT], len(open_requests)


def _sqlite_working_packages(path: Path, *, limit: int = WORKING_PACKAGE_LIMIT) -> list[dict[str, Any]] | None:
    if not path.exists():
        return None
    try:
        with closing(sqlite3.connect(str(path))) as connection:
            connection.row_factory = sqlite3.Row
            has_table = connection.execute(
                "select name from sqlite_master where type='table' and name='model_change_packages'"
            ).fetchone()
            if not has_table:
                return None
            columns = _sqlite_columns(connection, "model_change_packages")
            required = {"package_id", "status", "payload_json"}
            if not required <= columns:
                return None
            optional = [
                name
                for name in ("module_id", "risk", "review_action", "created_at", "updated_at")
                if name in columns
            ]
            selected = ["package_id", "status", "payload_json", *optional]
            order_by = "updated_at DESC, package_id ASC" if "updated_at" in columns else "package_id ASC"
            hidden_statuses = ", ".join("?" for _ in NON_WORKING_PACKAGE_STATUSES)
            rows = connection.execute(
                f"""
                SELECT {", ".join(selected)}
                  FROM model_change_packages
                 WHERE status NOT IN ({hidden_statuses})
                 ORDER BY {order_by}
                 LIMIT ?
                """,
                (*NON_WORKING_PACKAGE_STATUSES, max(1, int(limit))),
            ).fetchall()
            packages: list[dict[str, Any]] = []
            for row in rows:
                try:
                    payload = json.loads(str(row["payload_json"]))
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                package = dict(payload)
                package["packageId"] = str(row["package_id"] or package.get("packageId") or "")
                package["status"] = str(row["status"] or "pending")
                if "risk" in row.keys():
                    package["risk"] = str(row["risk"] or package.get("risk") or "unknown")
                if "review_action" in row.keys():
                    package["reviewAction"] = str(row["review_action"] or "unknown")
                if "created_at" in row.keys():
                    package["created_at"] = str(row["created_at"] or "")
                if "updated_at" in row.keys():
                    package["updated_at"] = str(row["updated_at"] or "")
                packages.append(package)
            return packages
    except sqlite3.Error:
        return None


def working_package_snapshot(workspace: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    store_value = config.get("store_path")
    if isinstance(store_value, str) and store_value:
        store_path = workspace_child(workspace, store_value, "agent-state/operational-store.sqlite")
        packages = _sqlite_working_packages(store_path)
        if packages is not None:
            return packages

    package_dir = workspace_child(workspace, config.get("package_output_dir"), "model-change-packages")
    if not package_dir.exists():
        return []
    packages = []
    for path in sorted(package_dir.glob("*.json"), reverse=True):
        data = load_json(path)
        if not data.get("packageId") or not isinstance(data.get("changes"), list):
            continue
        package = dict(data)
        package["status"] = str(package.get("status") or "pending")
        if package["status"] in NON_WORKING_PACKAGE_STATUSES:
            continue
        packages.append(package)
        if len(packages) >= WORKING_PACKAGE_LIMIT:
            break
    return packages


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
        previous_report = load_json(out_dir / "VIEWER_PUBLISH_REPORT.json")
        previous_official_hash = str(previous_report.get("viewer_asset_hash") or "")
        is_previous_official = previous_official_hash == existing_hash
        if existing_hash != source_hash and not allow_overwrite_custom and not is_previous_official:
            raise RuntimeError("custom-viewer-rejected")

    return source_text, source_hash


def _fetch_public_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "Cache-Control": "no-cache, no-store, max-age=0",
            "Pragma": "no-cache",
            "User-Agent": "business-ontology-viewer-verifier/1",
        },
    )
    with urlopen(request, timeout=12) as response:
        payload = response.read(PUBLIC_FETCH_LIMIT + 1)
    if len(payload) > PUBLIC_FETCH_LIMIT:
        raise ValueError("public viewer response exceeds the verification limit")
    return payload.decode("utf-8")


def verify_publication(public_url: str, report: dict[str, Any]) -> dict[str, str]:
    local_privacy = report.get("privacy")
    if not isinstance(local_privacy, dict) or local_privacy.get("status") != "passed":
        raise ValueError("local publish report has no passed privacy proof")
    last_error = "unknown"
    for attempt in range(3):
        try:
            remote_index = _fetch_public_text(public_url)
            remote_report_text = _fetch_public_text(urljoin(public_url, "VIEWER_PUBLISH_REPORT.json"))
            remote_report = json.loads(remote_report_text)
            if not isinstance(remote_report, dict) or remote_report.get("status") != "published":
                raise ValueError("public publish report is not published")
            bundle_name = str(remote_report.get("bundle") or "ontology.json")
            if Path(bundle_name).name != bundle_name:
                raise ValueError("public publish report bundle path is invalid")
            remote_bundle = _fetch_public_text(urljoin(public_url, bundle_name))
            checks = {
                "viewer_asset_hash": sha256_text(remote_index) == report["viewer_asset_hash"],
                "bundle_hash": sha256_text(remote_bundle) == report["bundle_hash"],
                "package_version": remote_report.get("package_version") == report["package_version"],
                "package_commit": remote_report.get("package_commit") == report["package_commit"],
                "model_revision": remote_report.get("model_revision") == report["model_revision"],
                "bundle_name": bundle_name == report["bundle"],
                "privacy": isinstance(remote_report.get("privacy"), dict)
                and remote_report["privacy"].get("status") == "passed"
                and remote_report["privacy"].get("policy") == local_privacy.get("policy"),
            }
            failed = sorted(name for name, passed in checks.items() if not passed)
            if failed:
                raise ValueError("public viewer mismatch: " + ",".join(failed))
            return {
                "status": "verified",
                "infrastructure_status": "verified",
                "public_url": public_url,
                "verified_at": utc_timestamp(),
            }
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {str(exc)[:240]}"
            if attempt < 2:
                time.sleep(0.25)
    raise ValueError(last_error)


def _prune_versioned_bundles(out_dir: Path, keep: set[str]) -> None:
    for path in out_dir.glob("ontology.*.json"):
        if path.name not in keep:
            path.unlink(missing_ok=True)


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
        open_requests, open_request_count = open_human_request_snapshot(workspace, config)
        working_packages = working_package_snapshot(workspace, config)
        publication = viewer_publication_config(config)
        accepted_context, accepted_context_path = accepted_context_snapshot(
            workspace,
            model_root,
            config,
        )
        accepted_cards = accepted_context_cards(accepted_context)
        accepted_sources = accepted_context_sources(accepted_context)
    except ValueError as exc:
        return CONFIG_INVALID, {"status": "config-invalid", "reason": str(exc)}
    validation = dict(validation)
    validation["accepted_context"] = {
        "status": "passed",
        "path": str(accepted_context_path) if accepted_context_path else "not-configured",
        "card_count": len(accepted_cards),
    }
    revision = args.revision or str(accepted_context.get("revision") or "") or git_revision(model_root)
    module = args.module or str(
        accepted_context.get("module") or config.get("module_id") or model_root.name
    )
    as_of = args.as_of or str(accepted_context.get("asOf") or "") or None
    version = package_version(package_root)
    commit = git_commit(package_root)

    bundle = build_bundle(
        model_root,
        module,
        revision,
        as_of,
        company_model_language=language,
        package_version=version,
        package_commit=commit,
        model_revision=revision,
        source_readiness=readiness,
        open_human_request_count=open_request_count,
        open_human_requests=open_requests,
        working_packages=working_packages,
        accepted_cards=accepted_cards if accepted_context_path else None,
        accepted_sources=accepted_sources if accepted_context_path else None,
        validation_status="passed",
    )
    viewer_diagnostics = bundle.get("viewerDiagnostics")
    if isinstance(viewer_diagnostics, list) and viewer_diagnostics:
        validation = dict(validation)
        validation["viewer_projection_diagnostics"] = viewer_diagnostics
        return VALIDATION_FAILED, {"status": "viewer-projection-invalid", "validation": validation}

    privacy = privacy_report(bundle)
    if privacy["status"] != "passed":
        return PRIVACY_FAILED, {"status": "viewer-privacy-invalid", "privacy": privacy}

    bundle_text = json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    bundle_hash = sha256_text(bundle_text)
    bundle_filename = f"ontology.{bundle_hash.removeprefix('sha256:')[:16]}.json"
    working_model = bundle.get("workingModel") if isinstance(bundle.get("workingModel"), dict) else {}

    report = {
        "status": "published",
        "package_version": version,
        "package_commit": commit,
        "model_revision": revision,
        "company_model_language": language,
        "source_readiness": source_readiness_report(readiness),
        "open_human_request_count": open_request_count,
        "accepted_model": {
            "card_count": len(accepted_cards),
            "context_path": str(accepted_context_path) if accepted_context_path else "",
        },
        "working_model": {
            "package_count": int(working_model.get("packageCount") or 0),
            "change_count": int(working_model.get("changeCount") or 0),
            "card_count": int(working_model.get("cardCount") or 0),
            "truth_boundary": "working-layer-not-accepted",
        },
        "validation": validation,
        "privacy": privacy,
        "viewer_asset_hash": viewer_asset_hash,
        "bundle_hash": bundle_hash,
        "published_at": utc_timestamp(),
        "viewer_index": "index.html",
        "bundle": bundle_filename,
        "publication": {
            "mode": publication["mode"],
            "public_url": publication["public_url"],
            "status": "workspace-only" if publication["mode"] == "workspace-only" else "configured",
            "infrastructure_status": (
                "workspace-only" if publication["mode"] == "workspace-only" else "configured"
            ),
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write_text_atomic(out_dir / bundle_filename, bundle_text)
    write_text_atomic(out_dir / "ontology.json", bundle_text)
    write_text_atomic(out_dir / "index.html", viewer_text)
    write_json_atomic(out_dir / "VIEWER_PUBLISH_REPORT.json", report)
    _prune_versioned_bundles(
        out_dir,
        {bundle_filename},
    )

    if publication["mode"] != "workspace-only" and not args.skip_public_verification:
        try:
            proof = verify_publication(publication["public_url"], report)
        except ValueError as exc:
            report["publication"] = {
                **report["publication"],
                "status": "verification-failed",
                "infrastructure_status": "verification-failed",
                "reason": str(exc),
                "verified_at": utc_timestamp(),
            }
            write_json_atomic(out_dir / "VIEWER_PUBLISH_REPORT.json", report)
            return PUBLICATION_VERIFICATION_FAILED, {
                "status": "publication-verification-failed",
                "publication": report["publication"],
                "publish_report": report,
            }
        report["publication"] = apply_reachability(
            {**report["publication"], **proof},
            load_reachability(out_dir, publication["public_url"]),
        )
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
    parser.add_argument(
        "--skip-public-verification",
        action="store_true",
        help="Publish locally without checking a configured public URL. Never use before sharing the URL.",
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

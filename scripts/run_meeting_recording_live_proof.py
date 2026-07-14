#!/usr/bin/env python3
"""Run and verify a real meeting-recording live proof.

This script proves the deployed product path without becoming a second runtime:
it calls the meeting-recording runtime, waits for the local job store to show
the webhook-created packet, validates packet files, and optionally validates
the agent-produced source events, model-change packages, and digest/review
handoff. It never polls Skribby.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
import urllib.request


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.meeting_recording_service import (  # noqa: E402
    ValidationError,
    hash_meeting_url,
    resolve_meeting_raw_source_root,
    sanitize_url,
)
from runtime.meeting_recording_store import MeetingRecordingStore  # noqa: E402
from runtime.meeting_transcript_capture import validate_meeting_transcript_packet  # noqa: E402
from runtime.source_event_contract import validate_source_event_contract  # noqa: E402
from scripts.source_registry import record_live_proof, sha256_file_ref, upsert_source_instance  # noqa: E402


class ProofError(RuntimeError):
    pass


@dataclass
class PacketCheck:
    packet_path: Path
    packet_id: str
    source_id: str
    transcript_hash: str


@dataclass
class AgentArtifactCheck:
    source_event_paths: list[Path]
    model_change_package_paths: list[Path]
    digest_or_review_handoff_path: Path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    proof_root = args.proof_root or _default_proof_root(args.workspace)
    started_at = _now()
    proof_dir = proof_root / _proof_stamp()
    proof_dir.mkdir(parents=True, exist_ok=True)
    return_code = 1

    report: dict[str, Any] = {
        "package_version": _package_version(),
        "git_commit": _git_commit(),
        "service_public_base_url": _safe_url(args.public_base_url),
        "service_url": _safe_url(args.service_url),
        "started_at": started_at,
        "finished_at": "",
        "job_id": args.job_id or "",
        "provider": "skribby",
        "bot_id": "",
        "completion_source": "",
        "provider_finished_at": "",
        "webhook_received_at": "",
        "wakeup_pending": "",
        "transcript_hash": "",
        "packet_path": "",
        "source_event_path": "",
        "model_change_package_path": "",
        "digest_or_review_handoff_path": "",
        "result": "fail",
        "maturity": "setup-only",
        "failure_reason": "",
        "checks": [],
    }
    if args.meeting_url:
        report["meeting_url_display"] = sanitize_url(args.meeting_url)
        report["meeting_url_hash"] = hash_meeting_url(args.meeting_url)

    try:
        if args.preflight:
            result = run_preflight(args, report)
            report.update(result)
            return_code = 0 if result.get("result") == "pass" else 1
        else:
            result = run_live_proof(args, report)
            report.update(result)
            report["result"] = "pass"
            report["failure_reason"] = ""
            return_code = 0
    except ProofError as exc:
        report["failure_reason"] = str(exc)
        return_code = 1
    finally:
        report["finished_at"] = _now()
        proof_path = write_proof_report(proof_dir, report)
        try:
            record_source_live_proof(args, report, proof_path)
        except Exception as exc:
            report["result"] = "fail"
            report["maturity"] = "setup-only"
            report["failure_reason"] = f"source registry update failed: {exc}"
            proof_path = write_proof_report(proof_dir, report)
            return_code = 1
        print(proof_path)
    return return_code


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a real meeting recording live proof.")
    parser.add_argument("--service-url", default=os.environ.get("MEETING_RECORDING_SERVICE_URL", ""))
    parser.add_argument("--public-base-url", default=os.environ.get("MEETING_RECORDING_PUBLIC_BASE_URL", ""))
    parser.add_argument("--db", type=Path, default=_env_path("MEETING_RECORDING_DB"))
    parser.add_argument("--workspace", type=Path, default=_env_path("OPENCLAW_WORKSPACE"))
    parser.add_argument("--meeting-url", default=os.environ.get("REAL_ZOOM_URL", ""))
    parser.add_argument("--business-id", default=os.environ.get("TEST_BUSINESS_ID", ""))
    parser.add_argument("--source-id", default=os.environ.get("TEST_SOURCE_ID", ""))
    parser.add_argument("--chat-ref", default=os.environ.get("TEST_CHAT_REF", ""))
    parser.add_argument("--requested-by", default=os.environ.get("TEST_REQUESTED_BY", ""))
    parser.add_argument("--job-id", default="")
    parser.add_argument("--source-events-dir", type=Path)
    parser.add_argument("--model-change-packages-dir", type=Path)
    parser.add_argument("--digest-or-review-handoff-path", type=Path)
    parser.add_argument("--proof-root", type=Path)
    parser.add_argument("--source-instance-id", default="meeting-recording")
    parser.add_argument("--owner-agent", default="business-ontology-resident")
    parser.add_argument("--timeout-seconds", type=float, default=3600)
    parser.add_argument("--poll-interval-seconds", type=float, default=10)
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Check live-proof inputs and runtime health without ordering a bot.",
    )
    parser.add_argument(
        "--packet-only",
        action="store_true",
        help="Stop at packet validation and mark maturity as source-connected, not live-proven.",
    )
    args = parser.parse_args(argv)

    if args.preflight:
        return args
    if args.db is None:
        parser.error("--db or MEETING_RECORDING_DB is required")
    if args.workspace is None:
        parser.error("--workspace or OPENCLAW_WORKSPACE is required")
    if not args.job_id:
        for field, value in {
            "--service-url or MEETING_RECORDING_SERVICE_URL": args.service_url,
            "--meeting-url or REAL_ZOOM_URL": args.meeting_url,
            "--business-id or TEST_BUSINESS_ID": args.business_id,
            "--source-id or TEST_SOURCE_ID": args.source_id,
            "--chat-ref or TEST_CHAT_REF": args.chat_ref,
            "--requested-by or TEST_REQUESTED_BY": args.requested_by,
        }.items():
            if not str(value).strip():
                parser.error(f"{field} is required unless --job-id is used")
    if args.timeout_seconds < 0:
        parser.error("--timeout-seconds must be >= 0")
    if args.poll_interval_seconds <= 0:
        parser.error("--poll-interval-seconds must be > 0")
    return args


def record_source_live_proof(args: argparse.Namespace, report: dict[str, Any], proof_path: Path) -> None:
    if args.preflight or args.workspace is None:
        return
    source_instance_id = str(args.source_instance_id or "meeting-recording")
    upsert_source_instance(
        args.workspace,
        {
            "source_instance_id": source_instance_id,
            "owner_agent": str(args.owner_agent or "business-ontology-resident"),
            "kind": "meeting-recorder",
            "runtime_adapter": "scripts/run_meeting_recording_live_proof.py",
            "config_ref": "env:MEETING_RECORDING_SERVICE_URL; env:MEETING_RECORDING_PUBLIC_BASE_URL",
            "cursor_ref": f"meeting-recording-store:{args.db}" if args.db else "",
            "output_ref": "runtime-config:raw_source_root#meetings",
            "scheduler_ref": "host-delivered-message",
            "status": "configured",
            "last_live_proof_id": "",
        },
    )
    job_id = str(report.get("job_id") or args.job_id or proof_path.parent.name)
    record_live_proof(
        args.workspace,
        {
            "live_proof_id": f"proof-{source_instance_id}-{job_id}",
            "source_instance_id": source_instance_id,
            "capability": "meeting-recording-transcript",
            "mode": "live",
            "input_ref": f"meeting-job:{job_id}",
            "output_artifacts": _proof_artifacts(report, proof_path),
            "evidence_hash": sha256_file_ref(proof_path),
            "status": _proof_status_for_registry(report),
        },
    )


def _proof_status_for_registry(report: dict[str, Any]) -> str:
    if report.get("result") != "pass":
        return "failed"
    if report.get("maturity") == "live-proven":
        return "passed"
    if report.get("maturity") == "source-connected":
        return "source-connected"
    return "setup-only"


def _proof_artifacts(report: dict[str, Any], proof_path: Path) -> list[str]:
    artifacts = [str(proof_path)]
    for key in [
        "packet_path",
        "source_event_path",
        "model_change_package_path",
        "digest_or_review_handoff_path",
    ]:
        value = str(report.get(key) or "").strip()
        if value:
            artifacts.extend(part.strip() for part in value.split(",") if part.strip())
    return artifacts


def run_preflight(args: argparse.Namespace, report: dict[str, Any]) -> dict[str, Any]:
    missing = preflight_missing_inputs(args)
    checks = list(report.get("checks", []))
    if missing:
        checks.append("preflight_inputs: fail")
        return {
            "result": "fail",
            "maturity": "setup-only",
            "failure_reason": "missing required live proof inputs: " + ", ".join(missing),
            "checks": checks,
            "missing_inputs": missing,
        }

    checks.append("preflight_inputs: pass")
    try:
        _health_check(args.service_url)
    except ProofError as exc:
        checks.append("service_health: fail")
        return {
            "result": "fail",
            "maturity": "setup-only",
            "failure_reason": str(exc),
            "checks": checks,
        }
    checks.append("service_health: pass")
    try:
        _public_health_check(args.public_base_url)
    except ProofError as exc:
        checks.append("public_health: fail")
        return {
            "result": "fail",
            "maturity": "setup-only",
            "failure_reason": str(exc),
            "checks": checks,
        }
    checks.append("public_health: pass")
    return {
        "result": "pass",
        "maturity": "setup-only",
        "failure_reason": "",
        "checks": checks,
    }


def preflight_missing_inputs(args: argparse.Namespace) -> list[str]:
    required: list[tuple[str, Any]] = [
        ("SKRIBBY_API_KEY", os.environ.get("SKRIBBY_API_KEY")),
        ("MEETING_RECORDING_DB", args.db),
        ("MEETING_RECORDING_PUBLIC_BASE_URL", args.public_base_url),
        ("MEETING_RECORDING_SERVICE_URL", args.service_url),
        ("OPENCLAW_WORKSPACE", args.workspace),
        ("REAL_ZOOM_URL", args.meeting_url),
        ("TEST_BUSINESS_ID", args.business_id),
        ("TEST_SOURCE_ID", args.source_id),
        ("TEST_CHAT_REF", args.chat_ref),
        ("TEST_REQUESTED_BY", args.requested_by),
    ]
    if not args.packet_only:
        required.extend(
            [
                ("OPENCLAW_MEETING_PROCESS_HOOK_URL", os.environ.get("OPENCLAW_MEETING_PROCESS_HOOK_URL")),
                ("OPENCLAW_HOOKS_TOKEN", os.environ.get("OPENCLAW_HOOKS_TOKEN")),
                ("MEETING_SOURCE_EVENTS_PATH", args.source_events_dir or os.environ.get("MEETING_SOURCE_EVENTS_PATH")),
                (
                    "MEETING_MODEL_CHANGE_PACKAGES_PATH",
                    args.model_change_packages_dir or os.environ.get("MEETING_MODEL_CHANGE_PACKAGES_PATH"),
                ),
                (
                    "MEETING_DIGEST_OR_REVIEW_PATH",
                    args.digest_or_review_handoff_path or os.environ.get("MEETING_DIGEST_OR_REVIEW_PATH"),
                ),
            ]
        )
    return [name for name, value in required if not str(value or "").strip()]


def run_live_proof(args: argparse.Namespace, report: dict[str, Any]) -> dict[str, Any]:
    job_id = args.job_id.strip()
    if not job_id:
        _health_check(args.service_url)
        report["checks"].append("service_health: pass")
        _public_health_check(args.public_base_url)
        report["checks"].append("public_health: pass")
        order = order_recording(args)
        job_id = str(order.get("job_id") or "")
        if not job_id:
            raise ProofError("recording runtime response did not include job_id")
        report["job_id"] = job_id
        report["bot_id"] = str(order.get("bot_id") or "")
        report["checks"].append("recording_ordered: pass")

    job = wait_for_packet(
        db_path=args.db,
        job_id=job_id,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
    )
    report["job_id"] = job_id
    report["bot_id"] = str(job.get("bot_id") or report.get("bot_id") or "")
    report["completion_source"] = str(job.get("completion_source") or "")
    report["provider_finished_at"] = str(job.get("provider_finished_at") or "")
    report["webhook_received_at"] = str(job.get("webhook_received_at") or "")
    report["wakeup_pending"] = str(int(job.get("wakeup_pending") or 0))

    packet_check = validate_packet_from_job(job, args.workspace)
    report["packet_path"] = str(packet_check.packet_path)
    report["packet_id"] = packet_check.packet_id
    report["transcript_hash"] = packet_check.transcript_hash
    report["checks"].append("packet_validated: pass")

    if args.packet_only:
        return {
            "maturity": _packet_only_maturity(job),
            "source_event_path": "",
            "model_change_package_path": "",
            "digest_or_review_handoff_path": "",
        }
    if job.get("completion_source") != "webhook":
        raise ProofError("full live proof requires webhook completion_source")
    if not str(job.get("webhook_received_at") or "").strip():
        raise ProofError("full live proof requires webhook_received_at")
    if int(job.get("wakeup_pending") or 0):
        raise ProofError("OpenClaw wakeup is still pending; meeting recording is not live-proven")

    artifact_check = validate_agent_artifacts(
        args.source_events_dir,
        args.model_change_packages_dir,
        args.digest_or_review_handoff_path,
        packet_check,
    )
    report["checks"].append("agent_artifacts_validated: pass")
    return {
        "maturity": "live-proven",
        "source_event_path": _join_paths(artifact_check.source_event_paths),
        "model_change_package_path": _join_paths(artifact_check.model_change_package_paths),
        "digest_or_review_handoff_path": str(artifact_check.digest_or_review_handoff_path),
    }


def order_recording(args: argparse.Namespace) -> dict[str, Any]:
    payload = {
        "meeting_url": args.meeting_url,
        "business_id": args.business_id,
        "source_id": args.source_id,
        "chat_ref": args.chat_ref,
        "requested_by": args.requested_by,
        "agent_mentioned": True,
    }
    return _post_json(_join_url(args.service_url, "/recordings"), payload)


def wait_for_packet(
    *,
    db_path: Path,
    job_id: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_status = "not-found"
    while True:
        try:
            with MeetingRecordingStore.connect(db_path) as store:
                store.initialize()
                job = store.get_job(job_id)
        except KeyError:
            job = None
        if job:
            last_status = str(job.get("status") or "")
            if last_status == "packet_ready":
                return job
            if last_status == "failed":
                raise ProofError(
                    "recording job failed: "
                    + str(job.get("error_code") or "unknown")
                    + " "
                    + str(job.get("error_message") or "")
                )
        if time.monotonic() >= deadline:
            raise ProofError(f"recording job did not reach packet_ready; last status: {last_status}")
        time.sleep(poll_interval_seconds)


def validate_packet_from_job(job: dict[str, Any], workspace: Path) -> PacketCheck:
    packet_value = str(job.get("packet_path") or "")
    if not packet_value:
        raise ProofError("packet_ready job has no packet_path")
    packet_path = _resolve_workspace_path(packet_value, workspace)
    if not packet_path.is_file():
        raise ProofError(f"packet_path is not a file: {packet_path}")
    try:
        raw_source_root = resolve_meeting_raw_source_root(workspace)
    except ValidationError as exc:
        raise ProofError(f"raw_source_root configuration invalid: {exc}") from exc
    job_id = str(job.get("job_id") or "")
    expected_packet_path = raw_source_root / "meetings" / job_id / "packet.json"
    if not job_id or packet_path.resolve() != expected_packet_path.resolve():
        raise ProofError("packet_path is outside configured raw_source_root/meetings/<job_id>")
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProofError(f"packet is not valid JSON: {exc}") from exc
    if not isinstance(packet, dict):
        raise ProofError("packet JSON must be an object")
    try:
        validate_meeting_transcript_packet(packet)
    except Exception as exc:
        raise ProofError(f"packet contract invalid: {exc}") from exc

    transcript_path = packet_path.parent / str(packet["transcriptPath"])
    summary_path = packet_path.parent / str(packet["summaryPath"])
    if not transcript_path.is_file():
        raise ProofError(f"transcript file missing: {transcript_path}")
    if not summary_path.is_file():
        raise ProofError(f"summary file missing: {summary_path}")
    transcript_hash = "sha256:" + hashlib.sha256(transcript_path.read_bytes()).hexdigest()
    if transcript_hash != packet["transcriptHash"]:
        raise ProofError("transcript hash does not match packet transcriptHash")
    if job.get("transcript_hash") and job["transcript_hash"] != transcript_hash:
        raise ProofError("job transcript_hash does not match packet transcriptHash")
    return PacketCheck(
        packet_path=packet_path,
        packet_id=str(packet["packetId"]),
        source_id=str(packet["sourceId"]),
        transcript_hash=transcript_hash,
    )


def validate_agent_artifacts(
    source_events_dir: Path | None,
    model_change_packages_dir: Path | None,
    digest_or_review_handoff_path: Path | None,
    packet_check: PacketCheck,
) -> AgentArtifactCheck:
    if source_events_dir is None or model_change_packages_dir is None or digest_or_review_handoff_path is None:
        raise ProofError(
            "full live proof requires --source-events-dir, --model-change-packages-dir, "
            "and --digest-or-review-handoff-path; use --packet-only only for source-connected proof"
        )
    source_event_paths = _json_files(source_events_dir)
    if not source_event_paths:
        raise ProofError(f"no source event JSON files found in {source_events_dir}")
    meeting_event_ids: set[str] = set()
    matching_source_event_paths: list[Path] = []
    packet_ref = f"packet:{packet_check.packet_id}"
    mismatched_meeting_events: list[Path] = []
    for path in source_event_paths:
        event = _read_json_object(path, "source event")
        try:
            validate_source_event_contract(event)
        except Exception as exc:
            raise ProofError(f"{path}: invalid source event: {exc}") from exc
        if event.get("sourceKind") == "meeting-transcript":
            if (
                event.get("sourceId") == packet_check.source_id
                and _source_event_references_packet(event, packet_check.packet_id)
            ):
                meeting_event_ids.add(str(event.get("eventId")))
                matching_source_event_paths.append(path)
            else:
                mismatched_meeting_events.append(path)
    if not meeting_event_ids:
        if mismatched_meeting_events:
            raise ProofError(
                f"{mismatched_meeting_events[0]} does not reference packet {packet_check.packet_id}"
            )
        raise ProofError("no meeting-transcript source events found")

    run_evals = _load_run_evals()
    package_paths = _json_files(model_change_packages_dir)
    if not package_paths:
        raise ProofError(f"no model-change package JSON files found in {model_change_packages_dir}")
    package_event_refs: set[str] = set()
    matching_package_paths: list[Path] = []
    matching_package_ids: set[str] = set()
    for path in package_paths:
        errors = run_evals.check_model_change_package(path.parent, {"path": path.name})
        if errors:
            raise ProofError("; ".join(errors))
        package = _read_json_object(path, "model-change package")
        current_refs = {str(item) for item in package.get("sourceEventIds", [])}
        package_event_refs.update(current_refs)
        if meeting_event_ids & current_refs:
            _require_package_packet_locator(package, meeting_event_ids, packet_check.packet_id, path)
            matching_package_paths.append(path)
            matching_package_ids.add(str(package.get("packageId") or ""))
    if not (meeting_event_ids & package_event_refs):
        raise ProofError("no model-change package references the meeting-transcript source event")

    if not digest_or_review_handoff_path.is_file():
        raise ProofError(f"digest/review handoff path is not a file: {digest_or_review_handoff_path}")
    if digest_or_review_handoff_path.suffix.lower() == ".json":
        errors = run_evals.check_review_package(
            digest_or_review_handoff_path.parent,
            {"path": digest_or_review_handoff_path.name},
        )
    else:
        errors = run_evals.check_digest_artifact(
            digest_or_review_handoff_path.parent,
            {"path": digest_or_review_handoff_path.name},
        )
    if errors:
        raise ProofError("; ".join(errors))
    _require_handoff_linkage(
        digest_or_review_handoff_path,
        packet_ref=packet_ref,
        event_ids=meeting_event_ids,
        package_ids=matching_package_ids,
    )
    return AgentArtifactCheck(
        source_event_paths=matching_source_event_paths,
        model_change_package_paths=matching_package_paths,
        digest_or_review_handoff_path=digest_or_review_handoff_path,
    )


def write_proof_report(proof_dir: Path, report: dict[str, Any]) -> Path:
    proof_path = proof_dir / "proof.md"
    lines = [
        "# Meeting Recording Live Proof",
        "",
        f"- package version: {report.get('package_version', '')}",
        f"- git commit: {report.get('git_commit', '')}",
        f"- service public base URL: {report.get('service_public_base_url', '')}",
        f"- job_id: {report.get('job_id', '')}",
        f"- provider: {report.get('provider', 'skribby')}",
        f"- bot_id: {report.get('bot_id', '')}",
        f"- started_at: {report.get('started_at', '')}",
        f"- finished_at: {report.get('finished_at', '')}",
        f"- completion_source: {report.get('completion_source', '')}",
        f"- provider_finished_at: {report.get('provider_finished_at', '')}",
        f"- webhook_received_at: {report.get('webhook_received_at', '')}",
        f"- wakeup_pending: {report.get('wakeup_pending', '')}",
        f"- transcript_hash: {report.get('transcript_hash', '')}",
        f"- packet_path: {report.get('packet_path', '')}",
        f"- packet_id: {report.get('packet_id', '')}",
        f"- source_event_path: {report.get('source_event_path', '')}",
        f"- model_change_package_path: {report.get('model_change_package_path', '')}",
        f"- digest_or_review_handoff_path: {report.get('digest_or_review_handoff_path', '')}",
        f"- result: {report.get('result', 'fail')}",
        f"- maturity: {report.get('maturity', 'setup-only')}",
        f"- failure_reason: {report.get('failure_reason', '')}",
    ]
    if report.get("meeting_url_hash"):
        lines.extend(
            [
                f"- meeting_url_display: {report.get('meeting_url_display', '')}",
                f"- meeting_url_hash: {report.get('meeting_url_hash', '')}",
            ]
        )
    checks = report.get("checks", [])
    if isinstance(checks, list) and checks:
        lines.extend(["", "## Checks", ""])
        lines.extend(f"- {item}" for item in checks)
    missing_inputs = report.get("missing_inputs")
    if isinstance(missing_inputs, list) and missing_inputs:
        lines.extend(["", "## Missing Inputs", ""])
        lines.extend(f"- {item}" for item in missing_inputs if isinstance(item, str))
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Proof report is redacted and must stay outside the model repository.",
            "- `source-connected` is not `live-proven`; full proof requires agent artifacts.",
        ]
    )
    proof_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return proof_path


def _health_check(service_url: str) -> None:
    result = _get_json(_join_url(service_url, "/health"))
    if result.get("status") != "ok":
        raise ProofError("meeting recording runtime health check did not return status=ok")


def _public_health_check(public_base_url: str) -> None:
    try:
        result = _get_json(_join_url(public_base_url, "/health"))
    except ProofError as exc:
        raise ProofError(f"public endpoint health check failed: {exc}") from exc
    if result.get("status") != "ok":
        raise ProofError("public endpoint health check failed: status is not ok")


def _packet_only_maturity(job: dict[str, Any]) -> str:
    if job.get("completion_source") == "webhook" and job.get("webhook_received_at"):
        return "source-connected"
    if job.get("completion_source") == "recovery":
        return "provider-recovered"
    return "setup-only"


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _open_json(request)


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")
    return _open_json(request)


def _open_json(request: urllib.request.Request) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = getattr(response, "status", 200)
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        raise ProofError(f"runtime request failed with HTTP {exc.code}") from exc
    except (OSError, URLError) as exc:
        raise ProofError("meeting recording runtime is unreachable") from exc
    if status < 200 or status >= 300:
        raise ProofError(f"runtime request failed with HTTP {status}")
    try:
        payload = json.loads(body)
    except Exception as exc:
        raise ProofError("runtime returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ProofError("runtime returned non-object JSON")
    return payload


def _load_run_evals() -> Any:
    path = REPO_ROOT / "scripts" / "run_evals.py"
    spec = importlib.util.spec_from_file_location("run_evals_live_proof", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _json_files(root: Path) -> list[Path]:
    if root.is_file() and root.suffix.lower() == ".json":
        return [root]
    if not root.is_dir():
        raise ProofError(f"artifact path is not a directory: {root}")
    return sorted(path for path in root.rglob("*.json") if path.is_file())


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProofError(f"{path}: cannot read {label} JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProofError(f"{path}: {label} must be a JSON object")
    return payload


def _source_event_references_packet(event: dict[str, Any], packet_id: str) -> bool:
    packet_ref = f"packet:{packet_id}"
    provenance = event.get("provenanceActivity")
    locators: list[str] = []
    if isinstance(provenance, dict):
        locators.append(str(provenance.get("sourceLocator") or ""))
    evidence = event.get("evidence")
    if isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, dict):
                locators.append(str(item.get("locator") or ""))
    return any(_locator_references_packet(locator, packet_ref) for locator in locators)


def _require_package_packet_locator(
    package: dict[str, Any],
    meeting_event_ids: set[str],
    packet_id: str,
    path: Path,
) -> None:
    packet_ref = f"packet:{packet_id}"
    for change in package.get("changes", []):
        if not isinstance(change, dict):
            continue
        for evidence in change.get("evidence", []):
            if not isinstance(evidence, dict):
                continue
            if str(evidence.get("sourceEventId") or "") not in meeting_event_ids:
                continue
            if _locator_references_packet(str(evidence.get("locator") or ""), packet_ref):
                return
    raise ProofError(f"{path}: no evidence locator references packet {packet_id}")


def _require_handoff_linkage(
    path: Path,
    *,
    packet_ref: str,
    event_ids: set[str],
    package_ids: set[str],
) -> None:
    text = path.read_text(encoding="utf-8")
    needles = {packet_ref, *event_ids, *{item for item in package_ids if item}}
    if not any(needle and needle in text for needle in needles):
        raise ProofError(f"{path}: digest/review handoff does not reference current packet, event, or package")


def _locator_references_packet(locator: str, packet_ref: str) -> bool:
    return locator == packet_ref or locator.startswith(packet_ref + "#")


def _resolve_workspace_path(value: str, workspace: Path) -> Path:
    path = Path(value)
    if path.is_absolute() or path.exists():
        return path
    return workspace / path


def _join_url(base: str, path: str) -> str:
    if not base:
        raise ProofError("service URL is required")
    return base.rstrip("/") + "/" + path.lstrip("/")


def _safe_url(value: str) -> str:
    if not value:
        return ""
    parsed = urlparse(value)
    return urlunparse(parsed._replace(query="", fragment=""))


def _join_paths(paths: list[Path]) -> str:
    return ", ".join(str(path) for path in paths)


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value) if value else None


def _default_proof_root(workspace: Path | None) -> Path:
    if workspace is not None:
        return workspace / "live-proofs" / "meeting-recording"
    return Path(os.environ.get("TMPDIR") or "/tmp") / "meeting-recording-live-proof"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _proof_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _package_version() -> str:
    try:
        text = (REPO_ROOT / "agent-package.yaml").read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("version:"):
                return line.split(":", 1)[1].strip().strip('"')
        return ""
    except Exception:
        return ""


def _git_commit() -> str:
    git_dir = _git_dir()
    if git_dir is None:
        return ""
    head = git_dir / "HEAD"
    try:
        value = head.read_text(encoding="utf-8").strip()
        if value.startswith("ref:"):
            ref = value.split(":", 1)[1].strip()
            ref_path = git_dir / ref
            if ref_path.is_file():
                return ref_path.read_text(encoding="utf-8").strip()
        return value
    except Exception:
        return ""


def _git_dir() -> Path | None:
    dot_git = REPO_ROOT / ".git"
    if dot_git.is_dir():
        return dot_git
    if not dot_git.is_file():
        return None
    try:
        text = dot_git.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    if not text.startswith("gitdir:"):
        return None
    value = text.split(":", 1)[1].strip()
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


if __name__ == "__main__":
    raise SystemExit(main())

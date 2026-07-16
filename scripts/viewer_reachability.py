#!/usr/bin/env python3
"""Gate viewer-link delivery on explicit owner reachability feedback."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from package_update_common import utc_timestamp, write_json_atomic  # noqa: E402


SHARE_BLOCKED = 3
INVALID_STATE = 4
STATE_FILENAME = "VIEWER_REACHABILITY.json"
REPORT_FILENAME = "VIEWER_PUBLISH_REPORT.json"
REACHABILITY_STATUSES = {
    "unconfirmed",
    "awaiting-owner",
    "confirmed",
    "unreachable",
}
REASON_CODES = {
    "owner-confirmed",
    "owner-reported-unreachable",
    "connection-failed",
    "certificate-error",
    "http-error",
    "content-mismatch",
}


class ViewerReachabilityError(ValueError):
    """Raised when viewer reachability state cannot be used safely."""


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ViewerReachabilityError(f"invalid JSON file: {path.name}") from exc
    if not isinstance(value, dict):
        raise ViewerReachabilityError(f"JSON file must contain an object: {path.name}")
    return value


def normalize_public_url(value: object) -> str:
    public_url = str(value or "")
    parsed = urlsplit(public_url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ViewerReachabilityError(
            "viewer public_url must be a credential-free HTTPS directory URL"
        )
    return public_url.rstrip("/") + "/"


def viewer_dir_from_workspace(workspace: Path) -> tuple[Path, dict[str, Any]]:
    workspace = workspace.resolve()
    config: dict[str, Any] = {}
    for name in ("runtime-config.json", "runtime-config.example.json"):
        candidate = workspace / name
        if candidate.is_file():
            config = load_json(candidate)
            break
    if not config:
        raise ViewerReachabilityError("workspace runtime config is missing")
    relative = Path(str(config.get("viewer_output_path") or "viewer"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ViewerReachabilityError("viewer_output_path must stay inside the workspace")
    return (workspace / relative).resolve(), config


def _default_state(public_url: str) -> dict[str, Any]:
    return {
        "public_url": public_url,
        "status": "unconfirmed",
    }


def load_reachability(viewer_dir: Path, public_url: str) -> dict[str, Any]:
    public_url = normalize_public_url(public_url)
    value = load_json(viewer_dir / STATE_FILENAME)
    if not value:
        return _default_state(public_url)
    try:
        state_url = normalize_public_url(value.get("public_url"))
    except ViewerReachabilityError:
        return _default_state(public_url)
    if state_url != public_url:
        return _default_state(public_url)
    status = str(value.get("status") or "")
    if status not in REACHABILITY_STATUSES:
        raise ViewerReachabilityError("viewer reachability status is invalid")
    state = _default_state(public_url)
    state["status"] = status
    for key in ("first_shared_at", "recorded_at", "reason_code"):
        item = value.get(key)
        if isinstance(item, str) and item:
            state[key] = item
    return state


def owner_reachability_projection(state: dict[str, Any]) -> dict[str, str]:
    projection = {"status": str(state.get("status") or "unconfirmed")}
    for key in ("first_shared_at", "recorded_at", "reason_code"):
        value = state.get(key)
        if isinstance(value, str) and value:
            projection[key] = value
    return projection


def infrastructure_status(publication: dict[str, Any]) -> str:
    explicit = str(publication.get("infrastructure_status") or "")
    if explicit:
        return explicit
    legacy = str(publication.get("status") or "")
    if legacy in {"verified", "owner-unreachable"}:
        return "verified"
    return legacy


def apply_reachability(
    publication: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    updated = dict(publication)
    infra_status = infrastructure_status(updated)
    if infra_status:
        updated["infrastructure_status"] = infra_status
    updated["owner_reachability"] = owner_reachability_projection(state)
    status = str(state.get("status") or "unconfirmed")
    if infra_status == "verified" and status == "unreachable":
        updated["status"] = "owner-unreachable"
    elif infra_status == "verified":
        updated["status"] = "verified"
    return updated


def _report_context(workspace: Path) -> tuple[Path, dict[str, Any], dict[str, Any], str]:
    viewer_dir, config = viewer_dir_from_workspace(workspace)
    report = load_json(viewer_dir / REPORT_FILENAME)
    if report.get("status") != "published":
        raise ViewerReachabilityError("official viewer publish report is not published")
    privacy = report.get("privacy")
    if not isinstance(privacy, dict) or privacy.get("status") != "passed":
        raise ViewerReachabilityError("official viewer has no passed privacy proof")
    publication = report.get("publication")
    if not isinstance(publication, dict):
        raise ViewerReachabilityError("viewer publication proof is missing")
    public_url = normalize_public_url(publication.get("public_url"))
    configured = config.get("viewer_publication")
    if not isinstance(configured, dict):
        raise ViewerReachabilityError("viewer publication target is missing from runtime config")
    configured_url = normalize_public_url(configured.get("public_url"))
    if configured_url != public_url:
        raise ViewerReachabilityError("viewer publication report does not match runtime config")
    if infrastructure_status(publication) != "verified":
        raise ViewerReachabilityError("viewer publication has no verified infrastructure proof")
    return viewer_dir, report, publication, public_url


def _write_state_and_report(
    viewer_dir: Path,
    report: dict[str, Any],
    publication: dict[str, Any],
    state: dict[str, Any],
) -> None:
    write_json_atomic(viewer_dir / STATE_FILENAME, state)
    updated_report = dict(report)
    updated_report["publication"] = apply_reachability(publication, state)
    write_json_atomic(viewer_dir / REPORT_FILENAME, updated_report)


def claim_link(workspace: Path) -> dict[str, Any]:
    viewer_dir, report, publication, public_url = _report_context(workspace)
    state = load_reachability(viewer_dir, public_url)
    status = str(state["status"])
    if status == "unconfirmed":
        now = utc_timestamp()
        state = {
            **state,
            "status": "awaiting-owner",
            "first_shared_at": now,
        }
        _write_state_and_report(viewer_dir, report, publication, state)
        return {
            "shareable": True,
            "public_url": public_url,
            "owner_reachability": "awaiting-owner",
            "requires_owner_confirmation": True,
        }
    if status == "confirmed":
        return {
            "shareable": True,
            "public_url": public_url,
            "owner_reachability": "confirmed",
            "requires_owner_confirmation": False,
        }
    reason = (
        "awaiting-owner-confirmation"
        if status == "awaiting-owner"
        else "owner-reported-unreachable"
    )
    return {
        "shareable": False,
        "public_url": "",
        "owner_reachability": status,
        "reason": reason,
    }


def record_feedback(
    workspace: Path,
    *,
    status: str,
    reason_code: str | None = None,
) -> dict[str, Any]:
    if status not in {"confirmed", "unreachable"}:
        raise ViewerReachabilityError("owner feedback status must be confirmed or unreachable")
    if status == "confirmed":
        reason = "owner-confirmed"
    else:
        reason = reason_code or "owner-reported-unreachable"
    if reason not in REASON_CODES:
        raise ViewerReachabilityError("owner feedback reason code is invalid")
    viewer_dir, report, publication, public_url = _report_context(workspace)
    previous = load_reachability(viewer_dir, public_url)
    now = utc_timestamp()
    state = {
        "public_url": public_url,
        "status": status,
        "recorded_at": now,
        "reason_code": reason,
    }
    if isinstance(previous.get("first_shared_at"), str):
        state["first_shared_at"] = previous["first_shared_at"]
    _write_state_and_report(viewer_dir, report, publication, state)
    return {
        "recorded": True,
        "owner_reachability": status,
        "reason_code": reason,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Gate model-viewer link delivery on explicit owner reachability."
    )
    parser.add_argument("--workspace", required=True, help="Installed workspace root.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("claim", help="Claim the URL for one owner-facing delivery.")
    record = subparsers.add_parser("record", help="Record explicit owner feedback.")
    record.add_argument("--status", choices=("confirmed", "unreachable"), required=True)
    record.add_argument("--reason", choices=tuple(sorted(REASON_CODES)), default=None)
    args = parser.parse_args(argv[1:])
    workspace = Path(args.workspace)
    try:
        if args.command == "claim":
            result = claim_link(workspace)
            code = 0 if result["shareable"] else SHARE_BLOCKED
        elif args.command == "record":
            result = record_feedback(
                workspace,
                status=args.status,
                reason_code=args.reason,
            )
            code = 0
    except ViewerReachabilityError as exc:
        result = {"status": "invalid", "reason": str(exc)}
        code = INVALID_STATE
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

#!/usr/bin/env python3
"""Refresh the silent resident-agent system-health snapshot."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
for import_root in (SCRIPT_DIR, REPO_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from package_update_common import utc_timestamp, write_json_atomic  # noqa: E402
from runtime.operational_store import OperationalStore  # noqa: E402


EXPECTED_HEARTBEAT: dict[str, object] = {
    "every": "2h",
    "target": "none",
    "directPolicy": "block",
    "isolatedSession": True,
    "lightContext": True,
}
PLUGIN_ID = "business-ontology-owner-chat-guard"
REQUIRED_PLUGIN_HOOKS = (
    "before_agent_run",
    "before_agent_finalize",
    "message_sending",
)


def _read_object(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.is_file():
        return None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "invalid"
    if not isinstance(payload, dict):
        return None, "invalid"
    return payload, "ok"


def _workspace_path(workspace: Path, value: object, fallback: str) -> Path:
    candidate = Path(str(value or fallback))
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (workspace / candidate).resolve()
    try:
        resolved.relative_to(workspace.resolve())
    except ValueError as exc:
        raise ValueError(f"configured path escapes workspace: {candidate}") from exc
    return resolved


def _runtime_config(workspace: Path) -> tuple[dict[str, Any], str, Path | None]:
    for name in ("runtime-config.json", "runtime-config.example.json"):
        path = workspace / name
        payload, status = _read_object(path)
        if payload is not None:
            return payload, status, path
        if status == "invalid":
            return {}, status, path
    return {}, "missing", None


def _request_summary(request: dict[str, object]) -> dict[str, object]:
    return {
        "request_id": str(request.get("requestId") or ""),
        "kind": str(request.get("kind") or ""),
        "status": str(request.get("status") or ""),
        "asked_at": str(request.get("askedAt") or ""),
        "due_at": str(request.get("dueAt") or ""),
    }


def _open_requests(workspace: Path, config: dict[str, Any]) -> dict[str, object]:
    try:
        store_path = _workspace_path(
            workspace,
            config.get("store_path"),
            "agent-state/operational-store.sqlite",
        )
    except ValueError as exc:
        return {"status": "invalid-config", "reason": str(exc), "count": None, "items": []}
    if not store_path.is_file():
        return {"status": "missing-store", "count": None, "items": []}
    try:
        with OperationalStore.open_readonly(store_path) as store:
            requests = store.list_open_human_requests(limit=50)
    except Exception as exc:  # SQLite schema and I/O errors are runtime health facts.
        return {
            "status": "read-failed",
            "reason": type(exc).__name__,
            "count": None,
            "items": [],
        }
    return {
        "status": "ok",
        "count": len(requests),
        "items": [_request_summary(request) for request in requests],
    }


def _source_state(workspace: Path) -> dict[str, object]:
    payload, status = _read_object(workspace / "source-instances.json")
    if payload is None:
        return {"status": status, "count": None, "by_status": {}}
    instances = payload.get("source_instances")
    if not isinstance(instances, list):
        return {"status": "invalid", "count": None, "by_status": {}}
    counts: dict[str, int] = {}
    for instance in instances:
        if not isinstance(instance, dict):
            continue
        state = str(instance.get("status") or "unknown")
        counts[state] = counts.get(state, 0) + 1
    return {"status": "ok", "count": len(instances), "by_status": dict(sorted(counts.items()))}


def _package_proof(workspace: Path) -> dict[str, object]:
    payload, status = _read_object(workspace / "PACKAGE_VERSION.lock")
    if payload is None:
        return {"status": status}
    required = ("current_version", "tag", "commit")
    if any(not str(payload.get(key) or "").strip() for key in required):
        return {"status": "invalid"}
    return {
        "status": "ok",
        "version": str(payload["current_version"]),
        "tag": str(payload["tag"]),
        "commit": str(payload["commit"]),
    }


def _workspace_proof(workspace: Path, agent_id: str) -> dict[str, object]:
    payload, status = _read_object(workspace / "workspace-state.json")
    if payload is None:
        return {"status": status}
    identity = payload.get("agent_identity")
    workspace_state = payload.get("workspace")
    if not isinstance(identity, dict) or not isinstance(workspace_state, dict):
        return {"status": "invalid"}
    return {
        "status": "ok",
        "agent_id": agent_id,
        "workspace_id": str(workspace_state.get("workspace_id") or ""),
        "package_name": str(identity.get("package_name") or ""),
        "package_version": str(identity.get("package_version") or ""),
    }


def _scheduling_state(workspace: Path, agent_id: str) -> tuple[dict[str, object], dict[str, Any] | None]:
    payload, status = _read_object(workspace / "agent-state" / "managed-scheduling.json")
    if payload is None:
        return {"status": status, "heartbeat_matches": False}, None
    heartbeat = payload.get("heartbeat")
    reminder = payload.get("owner_reminder")
    guard = payload.get("owner_chat_guard")
    matches = (
        payload.get("managed_by") == "business-ontology"
        and payload.get("agent_id") == agent_id
        and isinstance(heartbeat, dict)
        and all(heartbeat.get(key) == value for key, value in EXPECTED_HEARTBEAT.items())
    )
    reminder_configured = bool(isinstance(reminder, dict) and reminder.get("configured") is True)
    job_name = str(reminder.get("job_name") or "") if isinstance(reminder, dict) else ""
    declaration_key = (
        str(reminder.get("declaration_key") or "") if isinstance(reminder, dict) else ""
    )
    expected_job_name = f"business-ontology:{agent_id}:owner-reminder"
    reminder_fields = (
        "cadence",
        "cron",
        "timezone",
        "channel",
        "delivery_target",
        "quiet_window",
        "language",
        "confirmation_ref",
        "confirmed_at",
    )
    reminder_complete = not reminder_configured or (
        isinstance(reminder, dict) and all(reminder.get(key) for key in reminder_fields)
    )
    guard_matches = (
        isinstance(guard, dict)
        and guard.get("plugin_id") == PLUGIN_ID
        and guard.get("enabled") is True
        and guard.get("allow_conversation_access") is True
        and guard.get("agent_id") == agent_id
        and set(guard.get("required_hooks") or []) == set(REQUIRED_PLUGIN_HOOKS)
    )
    scheduling_ok = (
        matches
        and job_name == expected_job_name
        and declaration_key == expected_job_name
        and reminder_complete
        and guard_matches
    )
    return (
        {
            "status": "ok" if scheduling_ok else "invalid",
            "heartbeat_matches": matches,
            "owner_reminder_configured": reminder_configured,
            "owner_reminder_job_name_matches": job_name == expected_job_name,
            "owner_reminder_declaration_matches": declaration_key == expected_job_name,
            "owner_reminder_fields_complete": reminder_complete,
            "owner_chat_guard_contract_matches": guard_matches,
        },
        payload,
    )


def _extract_list(payload: object, key: str) -> list[dict[str, Any]]:
    value = payload
    if isinstance(payload, dict):
        value = payload.get(key, payload.get("data", []))
        if isinstance(value, dict):
            value = value.get(key, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _extract_object(payload: object, key: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    value: object = payload
    for wrapper in ("data", "value"):
        candidate = value.get(wrapper) if isinstance(value, dict) else None
        if isinstance(candidate, dict):
            value = candidate
    if isinstance(value, dict) and isinstance(value.get(key), dict):
        value = value[key]
    return value if isinstance(value, dict) else {}


def _run_openclaw(
    binary: str,
    args: list[str],
    *,
    node_bin_dir: str | None,
) -> tuple[object | None, str]:
    environment = os.environ.copy()
    if node_bin_dir:
        environment["PATH"] = f"{node_bin_dir}{os.pathsep}{environment.get('PATH', '')}"
    try:
        result = subprocess.run(
            [binary, *args],
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, type(exc).__name__
    if result.returncode != 0:
        return None, f"exit-{result.returncode}"
    try:
        return json.loads(result.stdout), "ok"
    except json.JSONDecodeError:
        return None, "invalid-json"


def _openclaw_probe(
    binary: str,
    node_bin_dir: str | None,
    agent_id: str,
    scheduling: dict[str, object],
    managed: dict[str, Any] | None,
    *,
    skip: bool,
) -> dict[str, object]:
    if skip:
        return {
            "status": "not-verified",
            "heartbeat_matches": False,
            "managed_cron_healthy": None,
            "owner_chat_guard_healthy": None,
        }

    if not binary:
        return {
            "status": "unavailable",
            "reason": "launcher-not-configured",
            "heartbeat_matches": False,
            "managed_cron_healthy": None,
            "owner_chat_guard_healthy": None,
        }
    agent_payload, agent_status = _run_openclaw(
        binary,
        ["config", "get", "agents.list", "--json"],
        node_bin_dir=node_bin_dir,
    )
    if agent_payload is None:
        return {
            "status": "unavailable",
            "reason": agent_status,
            "heartbeat_matches": False,
            "managed_cron_healthy": None,
            "owner_chat_guard_healthy": None,
        }
    agents = _extract_list(agent_payload, "agents")
    agent = next((item for item in agents if item.get("id") == agent_id), None)
    heartbeat = agent.get("heartbeat") if isinstance(agent, dict) else None
    heartbeat_matches = isinstance(heartbeat, dict) and all(
        heartbeat.get(key) == value for key, value in EXPECTED_HEARTBEAT.items()
    )

    reminder_configured = bool(scheduling.get("owner_reminder_configured"))
    reminder = managed.get("owner_reminder") if isinstance(managed, dict) else None
    declaration = (
        str(reminder.get("declaration_key") or "") if isinstance(reminder, dict) else ""
    )
    cron_payload, cron_status = _run_openclaw(
        binary,
        ["cron", "list", "--all", "--json"],
        node_bin_dir=node_bin_dir,
    )
    if cron_payload is None:
        cron_reason = cron_status
        cron_healthy = False
    else:
        jobs = _extract_list(cron_payload, "jobs")
        matches = [
            job
            for job in jobs
            if _first(job, "declarationKey", "declaration_key") == declaration
            or str(job.get("name") or "") == declaration
        ]
        if reminder_configured:
            cron_healthy, cron_reason = _managed_cron_matches(matches, reminder, agent_id)
        else:
            cron_healthy = len(matches) == 0
            cron_reason = "not-configured" if cron_healthy else "unexpected-managed-job"

    plugin_config_payload, plugin_config_status = _run_openclaw(
        binary,
        ["config", "get", "plugins", "--json"],
        node_bin_dir=node_bin_dir,
    )
    inspected_payload, inspect_status = _run_openclaw(
        binary,
        ["plugins", "inspect", PLUGIN_ID, "--runtime", "--json"],
        node_bin_dir=node_bin_dir,
    )
    plugin_healthy = False
    plugin_reason = plugin_config_status if plugin_config_payload is None else inspect_status
    if plugin_config_payload is not None and inspected_payload is not None:
        plugins = _extract_object(plugin_config_payload, "plugins")
        allow = plugins.get("allow") if isinstance(plugins.get("allow"), list) else []
        entries = plugins.get("entries") if isinstance(plugins.get("entries"), dict) else {}
        entry = entries.get(PLUGIN_ID) if isinstance(entries.get(PLUGIN_ID), dict) else {}
        hooks = entry.get("hooks") if isinstance(entry.get("hooks"), dict) else {}
        config = entry.get("config") if isinstance(entry.get("config"), dict) else {}
        serialized = json.dumps(inspected_payload, sort_keys=True)
        plugin_checks = {
            "allow": PLUGIN_ID in allow,
            "enabled": entry.get("enabled") is True,
            "conversation_access": hooks.get("allowConversationAccess") is True,
            "agent_filter": agent_id in (config.get("agentIds") or []),
            "runtime_hooks": all(hook in serialized for hook in REQUIRED_PLUGIN_HOOKS),
        }
        failed_plugin_checks = sorted(
            name for name, passed in plugin_checks.items() if not passed
        )
        plugin_healthy = not failed_plugin_checks
        plugin_reason = (
            "ok"
            if plugin_healthy
            else "mismatch:" + ",".join(failed_plugin_checks)
        )

    status = "ok" if heartbeat_matches and cron_healthy and plugin_healthy else "invalid"
    return {
        "status": status,
        "heartbeat_matches": heartbeat_matches,
        "managed_cron_healthy": cron_healthy,
        "managed_cron_reason": cron_reason,
        "owner_chat_guard_healthy": plugin_healthy,
        "owner_chat_guard_reason": plugin_reason,
    }


def _first(mapping: dict[str, Any], *keys: str) -> object:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _managed_cron_matches(
    jobs: list[dict[str, Any]],
    reminder: object,
    agent_id: str,
) -> tuple[bool, str]:
    if len(jobs) != 1 or not isinstance(reminder, dict):
        return False, "missing-or-duplicate"
    job = jobs[0]
    schedule = job.get("schedule") if isinstance(job.get("schedule"), dict) else {}
    delivery = job.get("delivery") if isinstance(job.get("delivery"), dict) else {}
    checks = {
        "enabled": job.get("enabled", True) is not False,
        "agent": _first(job, "agentId", "agent_id", "agent") == agent_id,
        "declaration": _first(job, "declarationKey", "declaration_key")
        == reminder.get("declaration_key"),
        "cron": (_first(schedule, "expr", "cron") or _first(job, "cron"))
        == reminder.get("cron"),
        "timezone": (_first(schedule, "tz", "timezone") or _first(job, "tz", "timezone"))
        == reminder.get("timezone"),
        "session": _first(job, "sessionTarget", "session") == "isolated",
        "delivery_mode": (_first(delivery, "mode") or _first(job, "deliveryMode"))
        == "announce",
        "delivery_channel": (_first(delivery, "channel") or _first(job, "channel"))
        == reminder.get("channel"),
        "delivery_target": (_first(delivery, "to", "target") or _first(job, "to"))
        == reminder.get("delivery_target"),
    }
    expected_account = reminder.get("account_id")
    if expected_account:
        checks["delivery_account"] = (
            _first(delivery, "accountId", "account_id") or _first(job, "accountId", "account_id")
        ) == expected_account
    failed = sorted(name for name, passed in checks.items() if not passed)
    return (not failed, "ok" if not failed else "mismatch:" + ",".join(failed))


def build_snapshot(
    workspace: Path,
    agent_id: str,
    *,
    checked_at: str,
    openclaw_bin: str | None,
    openclaw_node_bin_dir: str | None,
    skip_openclaw_probe: bool,
) -> dict[str, object]:
    config, config_status, config_path = _runtime_config(workspace)
    scheduling, managed = _scheduling_state(workspace, agent_id)
    managed_openclaw = managed.get("openclaw") if isinstance(managed, dict) else None
    launcher = openclaw_bin
    node_bin_dir = openclaw_node_bin_dir
    if isinstance(managed_openclaw, dict):
        launcher = launcher or str(managed_openclaw.get("launcher") or "")
        node_bin_dir = node_bin_dir or str(managed_openclaw.get("node_bin_dir") or "") or None
    snapshot: dict[str, object] = {
        "schema_version": 1,
        "agent_id": agent_id,
        "checked_at": checked_at,
        "external_delivery_allowed": False,
        "heartbeat_delivery": {"target": "none", "direct_policy": "block"},
        "runtime_config": {
            "status": config_status,
            "file": config_path.name if config_path is not None else None,
        },
        "sources": _source_state(workspace),
        "open_requests": _open_requests(workspace, config),
        "package": _package_proof(workspace),
        "workspace": _workspace_proof(workspace, agent_id),
        "managed_scheduling": scheduling,
        "openclaw": _openclaw_probe(
            launcher or "",
            node_bin_dir,
            agent_id,
            scheduling,
            managed,
            skip=skip_openclaw_probe,
        ),
    }
    required_statuses = [
        config_status,
        str(snapshot["sources"].get("status")),
        str(snapshot["open_requests"].get("status")),
        str(snapshot["package"].get("status")),
        str(snapshot["workspace"].get("status")),
        str(snapshot["managed_scheduling"].get("status")),
        str(snapshot["openclaw"].get("status")),
    ]
    snapshot["overall_status"] = "ok" if all(status == "ok" for status in required_statuses) else "degraded"
    return snapshot


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the silent system-health snapshot.")
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--openclaw-bin")
    parser.add_argument("--openclaw-node-bin-dir")
    parser.add_argument("--skip-openclaw-probe", action="store_true")
    parser.add_argument("--now", help="Deterministic UTC timestamp for tests.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(json.dumps({"status": "error", "reason": "workspace-not-found"}, sort_keys=True))
        return 2
    snapshot = build_snapshot(
        workspace,
        args.agent_id,
        checked_at=args.now or utc_timestamp(),
        openclaw_bin=args.openclaw_bin,
        openclaw_node_bin_dir=args.openclaw_node_bin_dir,
        skip_openclaw_probe=args.skip_openclaw_probe,
    )
    output_path = workspace / "agent-state" / "system-health.json"
    write_json_atomic(output_path, snapshot)
    output_path.chmod(0o600)
    print(
        json.dumps(
            {
                "status": "refreshed",
                "overall_status": snapshot["overall_status"],
                "open_request_count": snapshot["open_requests"].get("count"),
                "external_delivery_allowed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

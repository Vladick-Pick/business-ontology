#!/usr/bin/env python3
"""Configure one explicit publication target for the official workspace viewer.

The viewer stays in the agent workspace. Tailscale publication uses a package-
owned localhost service and one non-colliding Funnel reverse-proxy path; it
does not create a website, repository, provider account, or domain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from package_update_common import write_json_atomic  # noqa: E402
from publish_viewer import (  # noqa: E402
    load_json,
    verify_publication,
    viewer_publication_config,
    write_text_atomic,
)


UNIT_MARKER = "# Managed by business-ontology viewer publication"
DEFAULT_PORT_BASE = 18000
DEFAULT_PORT_SPAN = 10000


class PublicationConfigurationError(RuntimeError):
    """The target cannot be configured without guessing or overwriting state."""


def runtime_config_path(workspace: Path) -> Path:
    for name in ("runtime-config.json", "runtime-config.example.json"):
        path = workspace / name
        if path.is_file():
            return path
    raise PublicationConfigurationError("workspace runtime config is missing")


def normalize_route_path(value: str) -> str:
    route = "/" + value.strip().strip("/")
    if route == "/" or not re.fullmatch(r"/[A-Za-z0-9._~/-]+", route):
        raise PublicationConfigurationError("tailscale route must be a non-root URL path")
    if any(part in {".", ".."} for part in route.split("/")):
        raise PublicationConfigurationError("tailscale route must not contain dot segments")
    return route.rstrip("/")


def normalize_agent_id(value: str) -> str:
    agent_id = value.strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", agent_id):
        raise PublicationConfigurationError("tailscale-funnel requires a valid --agent-id")
    return agent_id


def default_local_port(agent_id: str) -> int:
    digest = hashlib.sha256(agent_id.encode("utf-8")).digest()
    return DEFAULT_PORT_BASE + int.from_bytes(digest[:4], "big") % DEFAULT_PORT_SPAN


def _run_json(binary: str, args: list[str]) -> object:
    try:
        result = subprocess.run(
            [binary, *args],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PublicationConfigurationError(
            f"tailscale command failed: {type(exc).__name__}"
        ) from exc
    if result.returncode != 0:
        raise PublicationConfigurationError(
            f"tailscale command failed with exit {result.returncode}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PublicationConfigurationError("tailscale returned invalid JSON") from exc


def _run_mutation(binary: str, args: list[str]) -> None:
    try:
        result = subprocess.run(
            [binary, *args],
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PublicationConfigurationError(
            f"tailscale mutation failed: {type(exc).__name__}"
        ) from exc
    if result.returncode != 0:
        reason = (result.stderr or result.stdout).strip().splitlines()
        detail = reason[0][:200] if reason else f"exit {result.returncode}"
        raise PublicationConfigurationError(f"tailscale mutation failed: {detail}")


def _run_systemctl(binary: str, args: list[str], *, required: bool = True) -> bool:
    try:
        result = subprocess.run(
            [binary, "--user", *args],
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        if required:
            raise PublicationConfigurationError(
                f"viewer service command failed: {type(exc).__name__}"
            ) from exc
        return False
    if result.returncode != 0 and required:
        raise PublicationConfigurationError(
            f"viewer service command failed with exit {result.returncode}: {args[0]}"
        )
    return result.returncode == 0


def tailscale_dns_name(binary: str) -> str:
    payload = _run_json(binary, ["status", "--json"])
    current = payload.get("Self") if isinstance(payload, dict) else None
    dns_name = current.get("DNSName") if isinstance(current, dict) else None
    name = str(dns_name or "").rstrip(".")
    if not name or not re.fullmatch(r"[A-Za-z0-9.-]+", name):
        raise PublicationConfigurationError("tailscale status has no usable Self.DNSName")
    return name


def _matching_handlers(value: object, route: str) -> list[object]:
    matches: list[object] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).rstrip("/") == route:
                matches.append(child)
            matches.extend(_matching_handlers(child, route))
    elif isinstance(value, list):
        for child in value:
            matches.extend(_matching_handlers(child, route))
    return matches


def assert_route_available(status: object, route: str, expected_target: str) -> bool:
    handlers = _matching_handlers(status, route)
    if not handlers:
        return False
    if all(expected_target in json.dumps(handler, sort_keys=True) for handler in handlers):
        return True
    raise PublicationConfigurationError(
        f"tailscale route {route} already exists and is not owned by this viewer"
    )


def _published_report(viewer_dir: Path) -> dict[str, Any]:
    report = load_json(viewer_dir / "VIEWER_PUBLISH_REPORT.json")
    privacy = report.get("privacy") if isinstance(report, dict) else None
    if report.get("status") != "published":
        raise PublicationConfigurationError(
            "publish the official viewer before configuring a public target"
        )
    if not isinstance(privacy, dict) or privacy.get("status") != "passed":
        raise PublicationConfigurationError(
            "public target requires a viewer publish report with passed privacy proof"
        )
    return report


def _verified_existing_report(
    viewer_dir: Path,
    public_url: str,
    report: dict[str, Any] | None = None,
) -> dict[str, str]:
    current = report or _published_report(viewer_dir)
    try:
        return verify_publication(public_url, current)
    except ValueError as exc:
        raise PublicationConfigurationError(
            f"public viewer verification failed: {exc}"
        ) from exc


def _systemd_quote(value: object) -> str:
    text = str(value)
    if "\n" in text or "\r" in text or "\x00" in text:
        raise PublicationConfigurationError("viewer service argument contains invalid control data")
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def _service_name(agent_id: str) -> str:
    return f"business-ontology-viewer-{agent_id}.service"


def _service_unit(
    *,
    agent_id: str,
    viewer_dir: Path,
    server_script: Path,
    python_bin: str,
    port: int,
) -> str:
    command = " ".join(
        _systemd_quote(value)
        for value in (
            python_bin,
            server_script,
            "--viewer-dir",
            viewer_dir,
            "--host",
            "127.0.0.1",
            "--port",
            port,
        )
    )
    return f"""{UNIT_MARKER}
[Unit]
Description=Business Ontology viewer for {agent_id}
After=network.target

[Service]
Type=simple
ExecStart={command}
Restart=on-failure
RestartSec=2
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
UMask=0077

[Install]
WantedBy=default.target
"""


def _restore_service(
    *,
    systemctl_bin: str,
    service_name: str,
    unit_path: Path,
    previous: str | None,
    was_enabled: bool,
    was_active: bool,
) -> None:
    _run_systemctl(systemctl_bin, ["disable", "--now", service_name], required=False)
    if previous is None:
        unit_path.unlink(missing_ok=True)
    else:
        write_text_atomic(unit_path, previous)
    _run_systemctl(systemctl_bin, ["daemon-reload"], required=False)
    if previous is not None and was_enabled:
        _run_systemctl(systemctl_bin, ["enable", service_name], required=False)
    if previous is not None and was_active:
        _run_systemctl(systemctl_bin, ["start", service_name], required=False)


def _install_service(
    *,
    agent_id: str,
    viewer_dir: Path,
    server_script: Path,
    python_bin: str,
    port: int,
    systemctl_bin: str,
    user_unit_dir: Path,
) -> dict[str, Any]:
    if not server_script.is_file():
        raise PublicationConfigurationError("package viewer server script is missing")
    service_name = _service_name(agent_id)
    unit_path = user_unit_dir / service_name
    previous = unit_path.read_text(encoding="utf-8") if unit_path.is_file() else None
    if previous is not None and not previous.startswith(UNIT_MARKER + "\n"):
        raise PublicationConfigurationError(
            f"viewer service name collision: {service_name}"
        )
    was_enabled = _run_systemctl(systemctl_bin, ["is-enabled", "--quiet", service_name], required=False)
    was_active = _run_systemctl(systemctl_bin, ["is-active", "--quiet", service_name], required=False)
    desired = _service_unit(
        agent_id=agent_id,
        viewer_dir=viewer_dir,
        server_script=server_script,
        python_bin=python_bin,
        port=port,
    )
    user_unit_dir.mkdir(parents=True, exist_ok=True)
    try:
        if desired != previous:
            write_text_atomic(unit_path, desired)
        _run_systemctl(systemctl_bin, ["daemon-reload"])
        _run_systemctl(systemctl_bin, ["enable", "--now", service_name])
        _run_systemctl(systemctl_bin, ["restart", service_name])
        _run_systemctl(systemctl_bin, ["is-active", "--quiet", service_name])
    except PublicationConfigurationError:
        _restore_service(
            systemctl_bin=systemctl_bin,
            service_name=service_name,
            unit_path=unit_path,
            previous=previous,
            was_enabled=was_enabled,
            was_active=was_active,
        )
        raise
    return {
        "name": service_name,
        "unit_path": unit_path,
        "previous": previous,
        "was_enabled": was_enabled,
        "was_active": was_active,
    }


def _record_verified_publication(
    viewer_dir: Path,
    target: dict[str, Any],
    proof: dict[str, str],
) -> dict[str, Any]:
    report = _published_report(viewer_dir)
    report["publication"] = {
        "mode": target["mode"],
        "public_url": target["public_url"],
        **proof,
    }
    write_json_atomic(viewer_dir / "VIEWER_PUBLISH_REPORT.json", report)
    return report


def configure(
    workspace: Path,
    *,
    mode: str,
    public_url: str | None,
    route_path: str | None,
    tailscale_bin: str,
    apply: bool,
    agent_id: str | None = None,
    local_port: int | None = None,
    systemctl_bin: str = "systemctl",
    user_unit_dir: Path | None = None,
    python_bin: str = sys.executable,
    server_script: Path | None = None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    config_path = runtime_config_path(workspace)
    config = load_json(config_path)
    viewer_value = config.get("viewer_output_path") or "viewer"
    viewer_relative = Path(str(viewer_value))
    if viewer_relative.is_absolute() or ".." in viewer_relative.parts:
        raise PublicationConfigurationError("viewer_output_path must stay inside the workspace")
    viewer_dir = (workspace / viewer_relative).resolve()

    target: dict[str, Any]
    route = ""
    route_already_bound = False
    backend_url = ""
    resolved_agent_id = ""
    resolved_port = 0
    service_name = ""
    resolved_server_script = (server_script or (SCRIPT_DIR / "serve_viewer.py")).absolute()
    if mode == "workspace-only":
        if public_url or route_path or agent_id or local_port:
            raise PublicationConfigurationError(
                "workspace-only mode does not accept a public URL, route, agent id, or port"
            )
        target = {"mode": mode, "public_url": ""}
    elif mode == "static-url":
        if agent_id or local_port:
            raise PublicationConfigurationError("static-url does not accept an agent id or local port")
        target = {"mode": mode, "public_url": str(public_url or "")}
        try:
            target = viewer_publication_config({"viewer_publication": target})
        except ValueError as exc:
            raise PublicationConfigurationError(str(exc)) from exc
    elif mode == "tailscale-funnel":
        if public_url:
            raise PublicationConfigurationError(
                "tailscale-funnel derives the public URL; do not pass --public-url"
            )
        if not route_path:
            raise PublicationConfigurationError("tailscale-funnel requires --path")
        resolved_agent_id = normalize_agent_id(agent_id or "")
        resolved_port = local_port or default_local_port(resolved_agent_id)
        if not 1024 <= resolved_port <= 65535:
            raise PublicationConfigurationError("viewer local port must be between 1024 and 65535")
        route = normalize_route_path(route_path)
        dns_name = tailscale_dns_name(tailscale_bin)
        public_url = f"https://{dns_name}{route}/"
        backend_url = f"http://127.0.0.1:{resolved_port}"
        status = _run_json(tailscale_bin, ["funnel", "status", "--json"])
        route_already_bound = assert_route_available(status, route, backend_url)
        service_name = _service_name(resolved_agent_id)
        target = {
            "mode": mode,
            "public_url": public_url,
            "path": route,
            "local_port": resolved_port,
            "service": service_name,
        }
    else:
        raise PublicationConfigurationError(f"unsupported publication mode: {mode}")

    current_target = config.get("viewer_publication")
    comparable_current = {
        key: current_target.get(key)
        for key in target
        if isinstance(current_target, dict)
    }
    changed = comparable_current != target
    result: dict[str, Any] = {
        "status": "planned" if not apply else "configured",
        "workspace": str(workspace),
        "viewer_dir": str(viewer_dir),
        "target": target,
        "changed": changed,
    }
    if not apply:
        return result

    if mode == "workspace-only":
        if changed:
            updated = dict(config)
            updated["viewer_publication"] = target
            write_json_atomic(config_path, updated)
        result["verification"] = {"status": "workspace-only"}
        return result

    report = _published_report(viewer_dir)
    if mode == "static-url":
        proof = _verified_existing_report(viewer_dir, str(target["public_url"]), report)
        if changed:
            updated = dict(config)
            updated["viewer_publication"] = target
            write_json_atomic(config_path, updated)
        result["verification"] = proof
        return result

    unit_dir = (user_unit_dir or (Path.home() / ".config" / "systemd" / "user")).expanduser()
    service_state: dict[str, Any] | None = None
    route_added = False
    original_config = dict(config)
    original_report = dict(report)
    try:
        service_state = _install_service(
            agent_id=resolved_agent_id,
            viewer_dir=viewer_dir,
            server_script=resolved_server_script,
            python_bin=python_bin,
            port=resolved_port,
            systemctl_bin=systemctl_bin,
            user_unit_dir=unit_dir,
        )
        _verified_existing_report(viewer_dir, backend_url + "/", report)
        if not route_already_bound:
            _run_mutation(
                tailscale_bin,
                ["funnel", "--bg", "--yes", "--set-path", route, backend_url],
            )
            route_added = True
        updated = dict(config)
        updated["viewer_publication"] = target
        write_json_atomic(config_path, updated)
        configured_report = dict(report)
        configured_report["publication"] = {
            "mode": target["mode"],
            "public_url": target["public_url"],
            "status": "configured",
        }
        write_json_atomic(viewer_dir / "VIEWER_PUBLISH_REPORT.json", configured_report)
        proof = _verified_existing_report(
            viewer_dir,
            str(target["public_url"]),
            configured_report,
        )
        _record_verified_publication(viewer_dir, target, proof)
    except (OSError, PublicationConfigurationError) as exc:
        write_json_atomic(config_path, original_config)
        write_json_atomic(viewer_dir / "VIEWER_PUBLISH_REPORT.json", original_report)
        if route_added:
            try:
                _run_mutation(
                    tailscale_bin,
                    ["funnel", "--bg", "--yes", "--set-path", route, "off"],
                )
            except PublicationConfigurationError:
                pass
        if service_state is not None:
            _restore_service(
                systemctl_bin=systemctl_bin,
                service_name=str(service_state["name"]),
                unit_path=service_state["unit_path"],
                previous=service_state["previous"],
                was_enabled=bool(service_state["was_enabled"]),
                was_active=bool(service_state["was_active"]),
            )
        if isinstance(exc, PublicationConfigurationError):
            raise
        raise PublicationConfigurationError(
            f"viewer publication configuration failed: {type(exc).__name__}"
        ) from exc

    result["target"] = target
    result["verification"] = proof
    result["service"] = {
        "name": service_name,
        "status": "active",
        "local_url": backend_url + "/",
    }
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Bind the official workspace viewer to one explicit publication target."
    )
    parser.add_argument("--workspace", required=True)
    parser.add_argument(
        "--mode",
        required=True,
        choices=("workspace-only", "static-url", "tailscale-funnel"),
    )
    parser.add_argument("--public-url")
    parser.add_argument("--path", dest="route_path")
    parser.add_argument("--agent-id")
    parser.add_argument("--port", dest="local_port", type=int)
    parser.add_argument("--tailscale-bin", default="tailscale")
    parser.add_argument("--systemctl-bin", default="systemctl")
    parser.add_argument("--user-unit-dir", type=Path)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--server-script", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv[1:])
    default_server_script = (Path(argv[0]).absolute().parent / "serve_viewer.py")
    try:
        result = configure(
            Path(args.workspace),
            mode=args.mode,
            public_url=args.public_url,
            route_path=args.route_path,
            tailscale_bin=args.tailscale_bin,
            apply=args.apply,
            agent_id=args.agent_id,
            local_port=args.local_port,
            systemctl_bin=args.systemctl_bin,
            user_unit_dir=args.user_unit_dir,
            python_bin=args.python_bin,
            server_script=args.server_script or default_server_script,
        )
    except PublicationConfigurationError as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

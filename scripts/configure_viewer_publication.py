#!/usr/bin/env python3
"""Configure one explicit publication target for the official workspace viewer.

The viewer is always generated in the agent workspace. This script only binds
that directory to a declared delivery capability; it never creates a website,
repository, provider account, or domain.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
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
)


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


def assert_route_available(status: object, route: str, viewer_dir: Path) -> bool:
    handlers = _matching_handlers(status, route)
    if not handlers:
        return False
    expected = str(viewer_dir.resolve())
    if all(expected in json.dumps(handler, sort_keys=True) for handler in handlers):
        return True
    raise PublicationConfigurationError(
        f"tailscale route {route} already exists and is not owned by this viewer"
    )


def _verified_existing_report(viewer_dir: Path, public_url: str) -> dict[str, str]:
    report_path = viewer_dir / "VIEWER_PUBLISH_REPORT.json"
    report = load_json(report_path)
    if report.get("status") != "published":
        raise PublicationConfigurationError(
            "publish the official viewer before configuring a public target"
        )
    try:
        return verify_publication(public_url, report)
    except ValueError as exc:
        raise PublicationConfigurationError(
            f"public viewer verification failed: {exc}"
        ) from exc


def configure(
    workspace: Path,
    *,
    mode: str,
    public_url: str | None,
    route_path: str | None,
    tailscale_bin: str,
    apply: bool,
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
    if mode == "workspace-only":
        if public_url or route_path:
            raise PublicationConfigurationError(
                "workspace-only mode does not accept a public URL or route"
            )
        target = {"mode": mode, "public_url": ""}
    elif mode == "static-url":
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
        route = normalize_route_path(route_path)
        dns_name = tailscale_dns_name(tailscale_bin)
        public_url = f"https://{dns_name}{route}/"
        status = _run_json(tailscale_bin, ["serve", "status", "--json"])
        route_already_bound = assert_route_available(status, route, viewer_dir)
        target = {
            "mode": mode,
            "public_url": public_url,
            "path": route,
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

    if mode == "tailscale-funnel" and not route_already_bound:
        _run_mutation(
            tailscale_bin,
            ["funnel", "--bg", "--yes", "--set-path", route, str(viewer_dir)],
        )

    proof: dict[str, str] | None = None
    if mode != "workspace-only":
        proof = _verified_existing_report(viewer_dir, str(target["public_url"]))

    if changed:
        updated = dict(config)
        updated["viewer_publication"] = target
        write_json_atomic(config_path, updated)
        result["target"] = updated["viewer_publication"]
    elif isinstance(current_target, dict):
        result["target"] = current_target
    result["verification"] = proof or {"status": "workspace-only"}
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
    parser.add_argument("--tailscale-bin", default="tailscale")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv[1:])
    try:
        result = configure(
            Path(args.workspace),
            mode=args.mode,
            public_url=args.public_url,
            route_path=args.route_path,
            tailscale_bin=args.tailscale_bin,
            apply=args.apply,
        )
    except PublicationConfigurationError as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

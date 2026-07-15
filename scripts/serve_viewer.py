#!/usr/bin/env python3
"""Serve only the current privacy-checked viewer files on localhost."""
from __future__ import annotations

import argparse
import hashlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any
from urllib.parse import unquote, urlsplit


VERSIONED_BUNDLE_RE = re.compile(r"ontology\.[0-9a-f]{16}\.json")
CONTENT_TYPES = {
    "index.html": "text/html; charset=utf-8",
    "VIEWER_PUBLISH_REPORT.json": "application/json; charset=utf-8",
}


class ViewerUnavailable(RuntimeError):
    """The viewer has no current privacy-checked publication."""


def _viewer_file(viewer_dir: Path, filename: str) -> Path:
    target = (viewer_dir / filename).resolve()
    if target.parent != viewer_dir or not target.is_file():
        raise ViewerUnavailable("viewer file unavailable")
    return target


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_report(viewer_dir: Path) -> dict[str, Any]:
    try:
        report_path = _viewer_file(viewer_dir, "VIEWER_PUBLISH_REPORT.json")
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ViewerUnavailable) as exc:
        raise ViewerUnavailable("publish report unavailable") from exc
    privacy = payload.get("privacy") if isinstance(payload, dict) else None
    bundle = str(payload.get("bundle") or "") if isinstance(payload, dict) else ""
    if (
        not isinstance(payload, dict)
        or payload.get("status") != "published"
        or not isinstance(privacy, dict)
        or privacy.get("status") != "passed"
        or not VERSIONED_BUNDLE_RE.fullmatch(bundle)
    ):
        raise ViewerUnavailable("viewer has no privacy-checked publication")
    try:
        if _sha256(_viewer_file(viewer_dir, bundle)) != payload.get("bundle_hash"):
            raise ViewerUnavailable("viewer bundle hash mismatch")
        if _sha256(_viewer_file(viewer_dir, "index.html")) != payload.get("viewer_asset_hash"):
            raise ViewerUnavailable("viewer asset hash mismatch")
    except OSError as exc:
        raise ViewerUnavailable("viewer hash proof unavailable") from exc
    return payload


def _allowed_filename(viewer_dir: Path, request_path: str) -> str:
    report = _load_report(viewer_dir)
    normalized = unquote(urlsplit(request_path).path).lstrip("/")
    filename = normalized or "index.html"
    allowed = {
        "index.html",
        "VIEWER_PUBLISH_REPORT.json",
        str(report["bundle"]),
    }
    if filename not in allowed:
        raise FileNotFoundError(filename)
    target = (viewer_dir / filename).resolve()
    if target.parent != viewer_dir or not target.is_file():
        raise FileNotFoundError(filename)
    return filename


def handler_for(viewer_dir: Path) -> type[BaseHTTPRequestHandler]:
    root = viewer_dir.resolve()

    class ViewerHandler(BaseHTTPRequestHandler):
        server_version = "BusinessOntologyViewer/1"

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _send(self, *, body: bool) -> None:
            try:
                filename = _allowed_filename(root, self.path)
            except ViewerUnavailable:
                self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, "viewer unavailable")
                return
            except FileNotFoundError:
                self.send_error(HTTPStatus.NOT_FOUND, "not found")
                return

            target = root / filename
            self.send_response(HTTPStatus.OK)
            self.send_header(
                "Content-Type",
                CONTENT_TYPES.get(filename, "application/json; charset=utf-8"),
            )
            self.send_header("Content-Length", str(target.stat().st_size))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            if body:
                with target.open("rb") as source:
                    shutil.copyfileobj(source, self.wfile)

        def do_GET(self) -> None:  # noqa: N802
            self._send(body=True)

        def do_HEAD(self) -> None:  # noqa: N802
            self._send(body=False)

    return ViewerHandler


def create_server(viewer_dir: Path, host: str, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), handler_for(viewer_dir))
    server.daemon_threads = True
    return server


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--viewer-dir", required=True, type=Path)
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "::1"))
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args(argv[1:])
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    viewer_dir = args.viewer_dir.resolve()
    if not viewer_dir.is_dir():
        parser.error("--viewer-dir must exist")
    with create_server(viewer_dir, args.host, args.port) as server:
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

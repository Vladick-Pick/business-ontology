#!/usr/bin/env python3
"""Run the meeting recording HTTP runtime."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.meeting_recording_service import (  # noqa: E402
    ValidationError,
    build_app,
    build_runtime_from_env,
    run_http_server,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the meeting recording runtime service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.workspace:
            import os

            os.environ["MEETING_RECORDING_WORKSPACE"] = str(args.workspace)
        runtime = build_runtime_from_env(args.db)
    except ValidationError as exc:
        print(f"meeting recording service configuration error: {exc}", file=sys.stderr)
        return 2

    print(f"meeting recording service listening on {args.host}:{args.port}", file=sys.stderr)
    run_http_server(args.host, args.port, build_app(runtime))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

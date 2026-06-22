#!/usr/bin/env python3
"""Run the in-process resident loop once from a JSON config file."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.resident_loop import run_once  # noqa: E402


class ResidentLoopArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        if "--once" in message:
            message = (
                f"{message}\n"
                "Continuous scheduling is not implemented in this repository; rerun with --once."
            )
        super().error(message)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = ResidentLoopArgumentParser(description="Run the reference resident loop.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--once",
        action="store_true",
        required=True,
        help="Run one scan/compile/review-queue pass.",
    )
    return parser.parse_args(argv)


def load_config(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"cannot read runtime config from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("runtime config must be a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        summary = run_once(load_config(args.config))
    except Exception as exc:
        print(f"resident loop failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

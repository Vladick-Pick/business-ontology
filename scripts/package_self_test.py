#!/usr/bin/env python3
"""Offline, bounded self-test contract for an installed package release.

This script is safe for package update apply:
- offline: it runs local unit tests and fixture evals only;
- bounded: each suite has a timeout and the total default budget is one minute;
- no live connectors: it does not call Telegram, Skribby, OpenClaw, OAuth, or
  other deployed services.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_suite(command: list[str], *, timeout: int) -> int:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(command, cwd=REPO_ROOT, env=env, timeout=timeout, check=False)
    return result.returncode


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the offline package self-test suite.")
    parser.add_argument("--suite-timeout", type=int, default=30, help="Per-suite timeout in seconds.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    commands = [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
        [sys.executable, "scripts/run_evals.py", "--fixture-only"],
    ]
    for command in commands:
        try:
            exit_code = run_suite(command, timeout=args.suite_timeout)
        except subprocess.TimeoutExpired:
            print(f"self-test timeout: {' '.join(command)}", file=sys.stderr)
            return 1
        if exit_code != 0:
            return exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run an extraction agent over golden cases, then score its packages."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_extraction_benchmark  # noqa: E402


@dataclass
class AgentProofResult:
    returncode: int
    errors: list[str]
    manifest: dict[str, Any]
    benchmark: run_extraction_benchmark.BenchmarkResult


def run_agent_proof(
    golden_dir: Path | str,
    packages_dir: Path | str,
    *,
    agent_command: list[str],
    agent: str,
    cli: str,
    model: str,
    prompt_hash: str,
    min_f1: float = 0.8,
) -> AgentProofResult:
    golden_dir = Path(golden_dir)
    packages_dir = Path(packages_dir)
    packages_dir.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    started_at = _utc_now()
    manifest_cases: list[dict[str, str]] = []

    if not agent_command:
        errors.append("agent command is required")

    for case_dir in _case_dirs(golden_dir):
        case_id = case_dir.name
        source_event_path = case_dir / "source-event.json"
        accepted_context_path = case_dir / "accepted-context" / "context.json"
        output_dir = packages_dir / case_id
        _prepare_output_dir(output_dir)

        if agent_command:
            env = _agent_env(
                case_id=case_id,
                source_event_path=source_event_path,
                accepted_context_path=accepted_context_path,
                output_dir=output_dir,
            )
            completed = subprocess.run(
                agent_command,
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                errors.append(f"{case_id}: agent command exited {completed.returncode}")

        package_paths = _package_paths(output_dir)
        if len(package_paths) != 1:
            errors.append(f"{case_id}: expected exactly one package JSON; found {len(package_paths)}")
            continue
        manifest_cases.append(
            {
                "case_id": case_id,
                "source_event_hash": _file_hash(source_event_path),
                "package_path": str(package_paths[0].relative_to(packages_dir)),
            }
        )

    manifest = {
        "agent": agent,
        "cli": cli,
        "model": model,
        "prompt_hash": prompt_hash,
        "started_at": started_at,
        "finished_at": _utc_now(),
        "cases": manifest_cases,
    }
    _write_json(packages_dir / "run_manifest.json", manifest)
    benchmark = run_extraction_benchmark.run_benchmark(
        golden_dir,
        packages_dir,
        min_f1=min_f1,
    )
    return AgentProofResult(
        returncode=0 if not errors and benchmark.passed else 1,
        errors=errors + benchmark.errors,
        manifest=manifest,
        benchmark=benchmark,
    )


def _case_dirs(golden_dir: Path) -> list[Path]:
    if not golden_dir.is_dir():
        return []
    return sorted(path for path in golden_dir.iterdir() if path.is_dir())


def _agent_env(
    *,
    case_id: str,
    source_event_path: Path,
    accepted_context_path: Path,
    output_dir: Path,
) -> dict[str, str]:
    env = dict(os.environ)
    pythonpath = env.get("PYTHONPATH")
    env.update(
        {
            "BO_CASE_ID": case_id,
            "BO_SOURCE_EVENT": str(source_event_path),
            "BO_ACCEPTED_CONTEXT": str(accepted_context_path),
            "BO_OUTPUT_DIR": str(output_dir),
            "BO_EXTRACTION_SKILL": str(REPO_ROOT / "skills" / "extract-from-input" / "SKILL.md"),
            "PYTHONPATH": str(REPO_ROOT)
            if not pythonpath
            else f"{REPO_ROOT}{os.pathsep}{pythonpath}",
        }
    )
    return env


def _package_paths(output_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in output_dir.glob("*.json")
        if path.name not in {"run_manifest.json", "scorecard.json"}
    )


def _prepare_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in output_dir.glob("*.json"):
        path.unlink()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _file_hash(path: Path) -> str:
    return "sha256:" + sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run an extraction agent command once per golden case, write "
            "run_manifest.json, then score produced model-change packages."
        )
    )
    parser.add_argument("--golden", type=Path, default=Path("evals/golden"))
    parser.add_argument("--packages", type=Path, required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--cli", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt-hash", required=True)
    parser.add_argument("--min-f1", type=float, default=0.8)
    parser.add_argument(
        "--agent-command",
        nargs=argparse.REMAINDER,
        required=True,
        help=(
            "Command to run for each case. It receives BO_CASE_ID, "
            "BO_SOURCE_EVENT, BO_ACCEPTED_CONTEXT, BO_OUTPUT_DIR, and "
            "BO_EXTRACTION_SKILL in the environment."
        ),
    )
    args = parser.parse_args(argv)

    result = run_agent_proof(
        args.golden,
        args.packages,
        agent_command=args.agent_command,
        agent=args.agent,
        cli=args.cli,
        model=args.model,
        prompt_hash=args.prompt_hash,
        min_f1=args.min_f1,
    )
    print(run_extraction_benchmark._format_table(result.benchmark.metrics))
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"- {error}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

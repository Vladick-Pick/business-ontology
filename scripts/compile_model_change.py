#!/usr/bin/env python3
"""Compile one source event into a model-change package JSON artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.model_compiler import CompilerRefusal, compile_model_change  # noqa: E402


def load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CompilerRefusal(f"cannot read JSON from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CompilerRefusal(f"{path} must contain a JSON object")
    return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile a normalized source event into a model-change package.",
    )
    parser.add_argument("--model-pack", required=True, type=Path)
    parser.add_argument("--source-event", required=True, type=Path)
    parser.add_argument("--accepted-context", type=Path)
    parser.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        accepted_context = load_json(args.accepted_context) if args.accepted_context else None
        package = compile_model_change(
            model_pack=load_json(args.model_pack),
            source_event=load_json(args.source_event),
            accepted_context=accepted_context,
        )
    except CompilerRefusal as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(package, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

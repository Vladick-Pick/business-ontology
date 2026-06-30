#!/usr/bin/env python3
"""Generate a reviewable draft ontology JSON artifact from source events."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.draft_generator import generate_draft_ontology  # noqa: E402


def load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-pack", required=True, type=Path)
    parser.add_argument("--source-event", required=True, type=Path, action="append")
    parser.add_argument("--accepted-context", type=Path)
    parser.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        draft = generate_draft_ontology(
            model_pack=load_json(args.model_pack),
            source_events=[load_json(path) for path in args.source_event],
            accepted_context=load_json(args.accepted_context) if args.accepted_context else None,
        )
    except Exception as exc:
        print(f"draft generation failed: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(draft, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 2 if draft["status"] == "refused" else 0


if __name__ == "__main__":
    raise SystemExit(main())

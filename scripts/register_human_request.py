#!/usr/bin/env python3
"""Register one human question before delivery without logging its text."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
for import_root in (SCRIPT_DIR, REPO_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from runtime.operational_store import OperationalStore  # noqa: E402
from runtime.review_authority import (  # noqa: E402
    channels_equivalent,
    load_review_authority,
)


MAX_REQUEST_CHARS = 65_536


def _read_request() -> dict[str, Any]:
    raw = sys.stdin.read(MAX_REQUEST_CHARS + 1)
    if len(raw) > MAX_REQUEST_CHARS:
        raise ValueError("human request exceeds safe input limit")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("human request is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("human request must be a JSON object")
    return payload


def register_human_request(
    store: OperationalStore,
    request: dict[str, Any],
    *,
    authority_policy: dict[str, object] | None = None,
) -> dict[str, object]:
    request_id = str(request.get("requestId") or "").strip()
    channel = str(request.get("channel") or "").strip()
    if re.fullmatch(r"hreq-[a-z0-9][a-z0-9-]*", request_id) is None or not channel:
        raise ValueError("human request requires requestId and channel")

    prepared = dict(request)
    message_ref = str(prepared.get("messageRef") or "").strip()
    if not message_ref:
        message_ref = f"pending:{request_id}"
        prepared["messageRef"] = message_ref
    elif message_ref.startswith("pending:") and message_ref != f"pending:{request_id}":
        raise ValueError("provisional messageRef must match requestId")

    existing = store.get_human_request(request_id)
    if existing is not None:
        if existing.get("status") not in {"open", "deferred"}:
            raise ValueError("human request is already closed")
        existing_ref = str(existing.get("messageRef") or "")
        if message_ref.startswith("pending:") and existing_ref and not existing_ref.startswith(
            "pending:"
        ):
            prepared["messageRef"] = existing_ref
            message_ref = existing_ref
        store.record_human_request(prepared)
        return {
            "status": "already-registered",
            "requestId": request_id,
            "provisional": message_ref.startswith("pending:"),
        }

    current = [
        item
        for item in store.list_open_human_requests(limit=10_000)
        if str(item.get("messageRef") or "")
        and channels_equivalent(
            authority_policy,
            str(item.get("channel") or ""),
            channel,
        )
    ]
    if current:
        raise ValueError("channel already has a current delivered question")

    store.record_human_request(prepared)
    return {
        "status": "registered",
        "requestId": request_id,
        "provisional": message_ref.startswith("pending:"),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--authority-policy", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        request = _read_request()
        store_path = args.store.resolve()
        if not store_path.is_file():
            raise ValueError("operational store does not exist")
        authority_policy = (
            load_review_authority(args.authority_policy.resolve())
            if args.authority_policy is not None
            else None
        )
        with OperationalStore.connect(store_path) as store:
            store.initialize()
            result = register_human_request(
                store,
                request,
                authority_policy=authority_policy,
            )
    except (sqlite3.IntegrityError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

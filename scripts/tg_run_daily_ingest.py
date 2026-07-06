#!/usr/bin/env python3
"""Run one Telegram MTProto export and build a packet from that exact run."""
from __future__ import annotations

import argparse
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent


class PartialTelegramExportError(RuntimeError):
    def __init__(self, manifest: dict[str, Any]) -> None:
        super().__init__("Telegram export has failed chats")
        self.manifest = manifest


def run_daily_ingest(
    *,
    mtproto_config: Path,
    packet_cursors_file: Path,
    packet_out_dir: Path,
    chat_map: Path,
    tz: str,
    backfill_days: int,
    no_wake: bool,
    run_id: str | None = None,
    now: datetime | None = None,
    wake_url: str = "http://127.0.0.1:3000/hooks/wake",
    allow_partial: bool = False,
    telegram: Any | None = None,
) -> dict[str, Any]:
    exporter = _load_sibling_module("tg_mtproto_export", "tg_mtproto_export.py")
    collector = _load_sibling_module("tg_collect_daily", "tg_collect_daily.py")
    config = exporter.load_config(mtproto_config)

    if telegram is None:
        with exporter.TelethonGateway(config.telegram) as gateway:
            mtproto_manifest = exporter.run_export(
                config,
                telegram=gateway,
                now=now,
                run_id=run_id,
                allow_partial=allow_partial,
            )
    else:
        mtproto_manifest = exporter.run_export(
            config,
            telegram=telegram,
            now=now,
            run_id=run_id,
            allow_partial=allow_partial,
        )

    if mtproto_manifest.get("failed_chats") and not allow_partial:
        raise PartialTelegramExportError(mtproto_manifest)

    packet_manifest = collector.collect_daily(
        exports_dir=Path(mtproto_manifest["run_dir"]),
        cursors_file=packet_cursors_file,
        out_dir=packet_out_dir,
        chat_map_path=chat_map,
        tz=tz,
        backfill_days=backfill_days,
        no_wake=no_wake,
        run_id=str(mtproto_manifest["run_id"]),
        wake_url=wake_url,
    )
    return {"mtproto": mtproto_manifest, "packet": packet_manifest}


def _load_sibling_module(name: str, filename: str) -> Any:
    module_path = SCRIPT_DIR / filename
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Cannot load {module_path}")
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Telegram MTProto export and packet collection once.")
    parser.add_argument("--mtproto-config", type=Path, required=True)
    parser.add_argument("--packet-cursors-file", type=Path, required=True)
    parser.add_argument("--packet-out-dir", type=Path, required=True)
    parser.add_argument("--chat-map", type=Path, required=True)
    parser.add_argument("--tz", default="UTC")
    parser.add_argument("--backfill-days", type=int, default=30)
    parser.add_argument("--run-id")
    parser.add_argument("--now", help="ISO timestamp for deterministic tests or backfills.")
    parser.add_argument("--wake-url", default="http://127.0.0.1:3000/hooks/wake")
    parser.add_argument("--no-wake", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    now = datetime.fromisoformat(args.now) if args.now else None
    try:
        result = run_daily_ingest(
            mtproto_config=args.mtproto_config,
            packet_cursors_file=args.packet_cursors_file,
            packet_out_dir=args.packet_out_dir,
            chat_map=args.chat_map,
            tz=args.tz,
            backfill_days=args.backfill_days,
            no_wake=args.no_wake,
            run_id=args.run_id,
            now=now,
            wake_url=args.wake_url,
            allow_partial=args.allow_partial,
        )
    except PartialTelegramExportError as exc:
        if args.json:
            print(json.dumps({"error": "partial-telegram-export", "mtproto": exc.manifest}, indent=2, sort_keys=True))
        print(
            f"Telegram export failed for {len(exc.manifest['failed_chats'])} chat(s); packet collection skipped.",
            file=sys.stderr,
        )
        return 2

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(result["packet"]["out_dir"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""SQLite store for meeting recorder jobs."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Any


class MeetingRecordingStore:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection
        self._connection.row_factory = sqlite3.Row

    @classmethod
    def connect(cls, path: Path) -> "MeetingRecordingStore":
        path.parent.mkdir(parents=True, exist_ok=True)
        return cls(sqlite3.connect(path))

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "MeetingRecordingStore":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def initialize(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS meeting_recording_jobs (
                job_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                meeting_url_hash TEXT NOT NULL,
                meeting_url_display TEXT NOT NULL,
                service TEXT NOT NULL,
                business_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                chat_ref TEXT NOT NULL,
                requested_by TEXT NOT NULL,
                webhook_nonce_hash TEXT NOT NULL DEFAULT '',
                bot_id TEXT,
                status TEXT NOT NULL,
                error_code TEXT,
                error_message TEXT,
                packet_path TEXT,
                transcript_hash TEXT,
                wakeup_pending INTEGER NOT NULL DEFAULT 0,
                completion_source TEXT NOT NULL DEFAULT '',
                provider_finished_at TEXT,
                webhook_received_at TEXT,
                webhook_payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                provider_payload_json TEXT NOT NULL
            )
            """
        )
        self._ensure_columns()
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_meeting_recording_jobs_status
                ON meeting_recording_jobs(status, updated_at, job_id)
            """
        )
        self._connection.commit()

    def _ensure_columns(self) -> None:
        columns = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(meeting_recording_jobs)").fetchall()
        }
        additions = {
            "packet_path": "TEXT",
            "transcript_hash": "TEXT",
            "wakeup_pending": "INTEGER NOT NULL DEFAULT 0",
            "completion_source": "TEXT NOT NULL DEFAULT ''",
            "provider_finished_at": "TEXT",
            "webhook_received_at": "TEXT",
            "webhook_payload_json": "TEXT NOT NULL DEFAULT '{}'",
            "webhook_nonce_hash": "TEXT NOT NULL DEFAULT ''",
        }
        for name, definition in additions.items():
            if name not in columns:
                self._connection.execute(f"ALTER TABLE meeting_recording_jobs ADD COLUMN {name} {definition}")

    def create_requested_job(self, job: dict[str, Any]) -> None:
        now = _now()
        payload = json.dumps(job.get("provider_payload", {}), sort_keys=True)
        self._connection.execute(
            """
            INSERT INTO meeting_recording_jobs (
                job_id, provider, meeting_url_hash, meeting_url_display,
                service, business_id, source_id, chat_ref, requested_by,
                webhook_nonce_hash, bot_id, status, error_code, error_message, created_at,
                updated_at, provider_payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 'requested', NULL, NULL, ?, ?, ?)
            """,
            (
                job["job_id"],
                job["provider"],
                job["meeting_url_hash"],
                job["meeting_url_display"],
                job["service"],
                job["business_id"],
                job["source_id"],
                job["chat_ref"],
                job["requested_by"],
                job["webhook_nonce_hash"],
                now,
                now,
                payload,
            ),
        )
        self._connection.commit()

    def mark_bot_created(self, job_id: str, *, bot_id: str, provider_payload: dict[str, Any]) -> None:
        self._transition(
            job_id,
            allowed_from={"requested"},
            status="bot_created",
            bot_id=bot_id,
            provider_payload=provider_payload,
            error_code=None,
            error_message=None,
        )

    def mark_failed(self, job_id: str, *, error_code: str, error_message: str) -> None:
        self._transition(
            job_id,
            allowed_from={"requested", "bot_created", "finished_received", "transcript_fetched"},
            status="failed",
            bot_id=None,
            provider_payload=None,
            error_code=error_code,
            error_message=error_message,
        )

    def mark_finished_received(self, job_id: str, *, webhook_payload: dict[str, Any]) -> None:
        current = self.get_job(job_id)
        if current["status"] not in {"bot_created"}:
            raise ValueError(f"invalid transition from {current['status']} to finished_received")
        now = _now()
        self._connection.execute(
            """
            UPDATE meeting_recording_jobs
               SET status = 'finished_received',
                   completion_source = 'webhook',
                   webhook_received_at = ?,
                   webhook_payload_json = ?,
                   updated_at = ?
             WHERE job_id = ?
            """,
            (now, json.dumps(webhook_payload, sort_keys=True), now, job_id),
        )
        self._connection.commit()

    def mark_transcript_fetched(
        self,
        job_id: str,
        *,
        provider_payload: dict[str, Any],
        provider_finished_at: str | None = None,
    ) -> None:
        self._transition(
            job_id,
            allowed_from={"finished_received"},
            status="transcript_fetched",
            bot_id=None,
            provider_payload=provider_payload,
            error_code=None,
            error_message=None,
            completion_source=None,
            provider_finished_at=provider_finished_at or _payload_finished_at(provider_payload),
        )

    def mark_transcript_recovered(
        self,
        job_id: str,
        *,
        provider_payload: dict[str, Any],
        provider_finished_at: str | None = None,
    ) -> None:
        self._transition(
            job_id,
            allowed_from={"bot_created", "finished_received"},
            status="transcript_fetched",
            bot_id=None,
            provider_payload=provider_payload,
            error_code=None,
            error_message=None,
            completion_source="recovery",
            provider_finished_at=provider_finished_at or _payload_finished_at(provider_payload),
        )

    def mark_packet_ready(
        self,
        job_id: str,
        *,
        packet_path: str,
        transcript_hash: str,
        wakeup_pending: bool,
    ) -> None:
        current = self.get_job(job_id)
        if current["status"] != "transcript_fetched":
            raise ValueError(f"invalid transition from {current['status']} to packet_ready")
        self._connection.execute(
            """
            UPDATE meeting_recording_jobs
               SET status = 'packet_ready',
                   packet_path = ?,
                   transcript_hash = ?,
                   wakeup_pending = ?,
                   updated_at = ?
             WHERE job_id = ?
            """,
            (packet_path, transcript_hash, 1 if wakeup_pending else 0, _now(), job_id),
        )
        self._connection.commit()

    def mark_wakeup_delivered(self, job_id: str) -> None:
        current = self.get_job(job_id)
        if current["status"] != "packet_ready":
            raise ValueError(f"invalid transition from {current['status']} to wakeup delivered")
        self._connection.execute(
            """
            UPDATE meeting_recording_jobs
               SET wakeup_pending = 0,
                   updated_at = ?
             WHERE job_id = ?
            """,
            (_now(), job_id),
        )
        self._connection.commit()

    def get_job(self, job_id: str) -> dict[str, Any]:
        row = self._connection.execute(
            "SELECT * FROM meeting_recording_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise KeyError(job_id)
        return self._row_to_dict(row)

    def table_count(self, table: str) -> int:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
            raise ValueError("table name must be a SQLite identifier")
        row = self._connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
        return int(row["count"])

    def _transition(
        self,
        job_id: str,
        *,
        allowed_from: set[str],
        status: str,
        bot_id: str | None,
        provider_payload: dict[str, Any] | None,
        error_code: str | None,
        error_message: str | None,
        completion_source: str | None = None,
        provider_finished_at: str | None = None,
    ) -> None:
        current = self.get_job(job_id)
        if current["status"] not in allowed_from:
            raise ValueError(f"invalid transition from {current['status']} to {status}")
        next_bot_id = bot_id if bot_id is not None else current.get("bot_id")
        next_payload = (
            provider_payload
            if provider_payload is not None
            else current.get("provider_payload", {})
        )
        self._connection.execute(
            """
            UPDATE meeting_recording_jobs
               SET status = ?,
                   bot_id = ?,
                   error_code = ?,
                   error_message = ?,
                   completion_source = ?,
                   provider_finished_at = ?,
                   updated_at = ?,
                   provider_payload_json = ?
             WHERE job_id = ?
            """,
            (
                status,
                next_bot_id,
                error_code,
                error_message,
                completion_source if completion_source is not None else current.get("completion_source", ""),
                provider_finished_at if provider_finished_at is not None else current.get("provider_finished_at"),
                _now(),
                json.dumps(next_payload, sort_keys=True),
                job_id,
            ),
        )
        self._connection.commit()

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["provider_payload"] = json.loads(result.pop("provider_payload_json"))
        result["webhook_payload"] = json.loads(result.pop("webhook_payload_json"))
        return result


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _payload_finished_at(payload: dict[str, Any]) -> str | None:
    value = payload.get("finished_at") if isinstance(payload, dict) else None
    return str(value) if value else None

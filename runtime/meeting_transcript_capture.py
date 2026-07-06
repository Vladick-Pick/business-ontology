#!/usr/bin/env python3
"""Capture finished meeting transcripts into private workspace packets."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any


HASH_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
PACKET_ID_RE = re.compile(r"^mtgpk-[a-z0-9][a-z0-9-]*$")
JOB_ID_RE = re.compile(r"^mtgrec-[a-z0-9][a-z0-9-]*$")


class EmptyTranscriptError(ValueError):
    pass


@dataclass
class CaptureResult:
    packet_path: Path
    transcript_path: Path
    summary_path: Path
    transcript_hash: str


def capture_finished_bot(
    job: dict[str, Any],
    bot_payload: dict[str, Any],
    workspace_root: Path,
    *,
    packet_id_factory: Any | None = None,
    observed_at: str | None = None,
) -> CaptureResult:
    segments = _segments(bot_payload.get("transcript"))
    if not segments:
        raise EmptyTranscriptError("Skribby bot response did not contain transcript segments")

    job_id = str(job["job_id"])
    capture_dir = Path(workspace_root) / "source-material" / "meeting-transcripts" / job_id
    capture_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = capture_dir / "transcript.md"
    summary_path = capture_dir / "summary.md"
    packet_path = capture_dir / "packet.json"

    transcript_text = _transcript_markdown(job, segments)
    transcript_path.write_text(transcript_text, encoding="utf-8")
    transcript_hash = "sha256:" + hashlib.sha256(transcript_text.encode("utf-8")).hexdigest()
    if not summary_path.exists():
        summary_path.write_text(_summary_stub(), encoding="utf-8")

    packet = {
        "packetId": packet_id_factory() if packet_id_factory else _packet_id(job_id),
        "jobId": job_id,
        "provider": "skribby",
        "providerBotId": str(job.get("bot_id") or bot_payload.get("id") or ""),
        "businessId": str(job["business_id"]),
        "sourceId": str(job["source_id"]),
        "chatRef": str(job["chat_ref"]),
        "requestedBy": str(job["requested_by"]),
        "observedAt": observed_at or str(bot_payload.get("finished_at") or _now()),
        "transcriptPath": "transcript.md",
        "summaryPath": "summary.md",
        "transcriptHash": transcript_hash,
        "participants": _participants(bot_payload.get("participants")),
        "segments": segments,
    }
    validate_meeting_transcript_packet(packet)
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return CaptureResult(
        packet_path=packet_path,
        transcript_path=transcript_path,
        summary_path=summary_path,
        transcript_hash=transcript_hash,
    )


def validate_meeting_transcript_packet(packet: dict[str, Any]) -> None:
    required = {
        "packetId",
        "jobId",
        "provider",
        "providerBotId",
        "businessId",
        "sourceId",
        "chatRef",
        "requestedBy",
        "observedAt",
        "transcriptPath",
        "summaryPath",
        "transcriptHash",
        "participants",
        "segments",
    }
    missing = sorted(required - set(packet))
    if missing:
        raise ValueError(f"meeting transcript packet missing field: {missing[0]}")
    extra = sorted(set(packet) - required)
    if extra:
        raise ValueError(f"meeting transcript packet unexpected field: {extra[0]}")
    if packet["provider"] != "skribby":
        raise ValueError("meeting transcript packet provider must be skribby")
    for field in (
        "providerBotId",
        "businessId",
        "sourceId",
        "chatRef",
        "requestedBy",
        "observedAt",
    ):
        if not str(packet[field]).strip():
            raise ValueError(f"meeting transcript packet {field} must be non-empty")
    if not PACKET_ID_RE.match(str(packet["packetId"])):
        raise ValueError("meeting transcript packet packetId has invalid format")
    if not JOB_ID_RE.match(str(packet["jobId"])):
        raise ValueError("meeting transcript packet jobId has invalid format")
    if packet["transcriptPath"] != "transcript.md":
        raise ValueError("meeting transcript packet transcriptPath must be transcript.md")
    if packet["summaryPath"] != "summary.md":
        raise ValueError("meeting transcript packet summaryPath must be summary.md")
    if not HASH_RE.match(str(packet["transcriptHash"])):
        raise ValueError("meeting transcript packet transcriptHash must be sha256:<64 hex>")
    _validate_participants(packet["participants"])
    if not isinstance(packet["segments"], list) or not packet["segments"]:
        raise ValueError("meeting transcript packet segments must be non-empty")
    for index, segment in enumerate(packet["segments"]):
        _validate_segment(segment, index)


def _validate_participants(value: Any) -> None:
    if not isinstance(value, list):
        raise ValueError("meeting transcript packet participants must be an array")
    for index, participant in enumerate(value):
        if not isinstance(participant, dict):
            raise ValueError(f"meeting transcript packet participants[{index}] must be an object")
        if set(participant) != {"name", "source"}:
            raise ValueError(f"meeting transcript packet participants[{index}] has invalid fields")
        if not str(participant.get("name") or "").strip():
            raise ValueError(f"meeting transcript packet participants[{index}] missing name")
        if participant.get("source") != "skribby":
            raise ValueError(f"meeting transcript packet participants[{index}] source must be skribby")


def _validate_segment(value: Any, index: int) -> None:
    required = {"segmentId", "start", "end", "speaker", "speakerName", "confidence", "text"}
    if not isinstance(value, dict):
        raise ValueError(f"meeting transcript packet segments[{index}] must be an object")
    if set(value) != required:
        raise ValueError(f"meeting transcript packet segments[{index}] has invalid fields")
    if not re.fullmatch(r"seg-\d{5}", str(value["segmentId"])):
        raise ValueError(f"meeting transcript packet segments[{index}].segmentId has invalid format")
    for key in ("start", "end", "confidence"):
        if not isinstance(value[key], (int, float)):
            raise ValueError(f"meeting transcript packet segments[{index}].{key} must be numeric")
    for key in ("speaker", "speakerName", "text"):
        if not isinstance(value[key], str) or (key != "speaker" and not value[key].strip()):
            raise ValueError(f"meeting transcript packet segments[{index}].{key} must be text")


def _segments(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    segments: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        utterances = item.get("utterances")
        if isinstance(utterances, list) and utterances:
            for utterance in utterances:
                segment = _segment_from_item(utterance, parent=item)
                if segment:
                    segments.append(segment)
            continue
        segment = _segment_from_item(item)
        if segment:
            segments.append(segment)
    for index, segment in enumerate(segments, start=1):
        segment["segmentId"] = f"seg-{index:05d}"
    return segments


def _segment_from_item(item: Any, *, parent: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    text = str(item.get("transcript") or "").strip()
    if not text:
        return None
    parent = parent or {}
    confidence = item.get("confidence", parent.get("confidence", 0))
    if not isinstance(confidence, (int, float)):
        confidence = 0
    speaker_name = (
        item.get("speaker_name")
        or item.get("speakerName")
        or parent.get("speaker_name")
        or parent.get("speakerName")
        or "unknown"
    )
    return {
        "start": _number(item.get("start", parent.get("start", 0))),
        "end": _number(item.get("end", parent.get("end", 0))),
        "speaker": str(item.get("speaker", parent.get("speaker", "")) or ""),
        "speakerName": str(speaker_name),
        "confidence": confidence,
        "text": text,
    }


def _number(value: Any) -> int | float:
    return value if isinstance(value, (int, float)) else 0


def _participants(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    participants: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict) and item.get("name"):
            participants.append({"name": str(item["name"]), "source": "skribby"})
    return participants


def _transcript_markdown(job: dict[str, Any], segments: list[dict[str, Any]]) -> str:
    lines = [
        "# Meeting Transcript",
        "",
        f"- job_id: {job['job_id']}",
        "- provider: skribby",
        f"- bot_id: {job.get('bot_id') or 'unknown'}",
        f"- business_id: {job['business_id']}",
        f"- source_id: {job['source_id']}",
        "",
        "## Transcript",
        "",
    ]
    for segment in segments:
        lines.append(
            f"[{segment['segmentId']}] [{segment['start']} - {segment['end']}] "
            f"{segment['speakerName']}: {segment['text']}"
        )
    lines.append("")
    return "\n".join(lines)


def _summary_stub() -> str:
    return """---
type: meeting_summary
packet: "packet.json"
transcript: "transcript.md"
source_kind: "meeting-transcript"
status: "pending-ingest"
---

# Meeting Summary

> pending meeting-transcript-ingest
"""


def _packet_id(job_id: str) -> str:
    return "mtgpk-" + job_id.removeprefix("mtgrec-")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

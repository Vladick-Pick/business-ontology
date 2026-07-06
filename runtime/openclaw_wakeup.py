#!/usr/bin/env python3
"""OpenClaw wakeup adapter for ready meeting transcript packets."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import urllib.request


@dataclass
class WakeupResult:
    attempted: bool
    pending: bool


def wake_meeting_transcript(
    packet_path: Path,
    *,
    hook_url: str | None,
    token: str | None,
    timeout: int = 10,
) -> WakeupResult:
    if not hook_url or not token:
        return WakeupResult(attempted=False, pending=True)
    body = json.dumps(
        {
            "message": f"process meeting transcript {packet_path}",
            "mode": "now",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        hook_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
    except Exception:
        return WakeupResult(attempted=True, pending=True)
    return WakeupResult(attempted=True, pending=False)

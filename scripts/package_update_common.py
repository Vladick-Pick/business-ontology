"""Shared helpers for package update scripts."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


class UpdateLockBusy(RuntimeError):
    """Raised when another live package update process holds the lock."""

    def __init__(self, path: Path, pid: int | None):
        self.path = path
        self.pid = pid
        detail = f" held by pid {pid}" if pid is not None else ""
        super().__init__(f"{path} is locked{detail}")


def sanitize_remote_url(remote_url: str) -> str:
    """Return a remote URL safe for lock files and logs."""
    if not remote_url:
        return remote_url
    parsed = urlsplit(remote_url)
    if parsed.scheme and "@" in parsed.netloc:
        host = parsed.netloc.rsplit("@", 1)[1]
        return urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))
    return remote_url


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json_file(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def pid_is_live(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class UpdateLock:
    """Exclusive filesystem lock for check/apply package update scripts."""

    def __init__(self, path: Path, *, force_unlock: bool = False):
        self.path = path
        self.force_unlock = force_unlock
        self.acquired = False

    def __enter__(self) -> "UpdateLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.force_unlock and self.path.exists():
            self.path.unlink()
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                pid = self._locked_pid()
                if pid is not None and pid_is_live(pid):
                    raise UpdateLockBusy(self.path, pid)
                self.path.unlink(missing_ok=True)
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"pid": os.getpid(), "timestamp": utc_timestamp()}, handle, sort_keys=True)
                handle.write("\n")
            self.acquired = True
            return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False

    def _locked_pid(self) -> int | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return None
        pid = data.get("pid")
        return pid if isinstance(pid, int) else None


def utc_timestamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

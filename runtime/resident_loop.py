#!/usr/bin/env python3
"""In-process resident loop for normalized source events.

This is a reference loop, not a daemon, scheduler, live connector, OAuth
adapter, or networked MCP server. It scans already-normalized source-event JSON
files, calls the deterministic model compiler, queues model-change packages for
review, records idempotency state, and emits redacted trace events.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from runtime.model_compiler import CompilerRefusal, compile_model_change
from runtime.operational_store import OperationalStore


DEFAULT_ONTOLOGY_REVISION = "runtime:resident-loop"
DEFAULT_DIGEST_NAME = "digest-resident-loop.md"
DEFAULT_SUMMARY_PACKAGE_LIMIT = 20
DEFAULT_DIGEST_PACKAGE_LIMIT = 20
REPO_ROOT = Path(__file__).resolve().parents[1]
ID_RE = re.compile(r"[^a-z0-9]+")
FORBIDDEN_WRITE_PARTS = {
    "adapters",
    "agent-os",
    "deployment",
    "skills",
    "concepts",
    "decisions",
    "interfaces",
    "modules",
    "processes",
    "production-systems",
    "references",
    "registry",
    "schemas",
    "specs",
    "staged",
    "states",
    "templates",
}
FORBIDDEN_WRITE_FILES = {
    "02-source-map.md",
    "AGENTS.md",
    "BOOTSTRAP.md",
    "BUSINESS-ONTOLOGY-RESIDENT.md",
    "CLAUDE.md",
    "README.md",
    "SKILL.md",
    "agent-package.yaml",
}


@dataclass(frozen=True)
class ResidentLoopConfig:
    model_pack_path: Path
    source_event_dir: Path
    package_output_dir: Path
    state_path: Path
    trace_path: Path
    artifact_root: Path
    state_root: Path
    store_path: Path | None = None
    accepted_context_path: Path | None = None
    ontology_revision: str = DEFAULT_ONTOLOGY_REVISION
    generated_at: str = ""
    digest_path: Path | None = None
    digest_threshold: int = 1
    summary_package_limit: int = DEFAULT_SUMMARY_PACKAGE_LIMIT
    digest_package_limit: int = DEFAULT_DIGEST_PACKAGE_LIMIT
    write_digest: bool = True


def run_once(config: dict[str, object]) -> dict[str, object]:
    """Run one resident-loop pass and return a bounded summary."""

    runtime_config = _normalize_config(config)
    store = _connect_store(runtime_config)
    run_started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    run_id = f"run-resident-loop-{_slug(run_started_at)}"
    if store is not None:
        store.record_run(
            {
                "runId": run_id,
                "status": "running",
                "startedAt": run_started_at,
                "summary": {"status": "running"},
            }
        )
    model_pack = _load_json_object(runtime_config.model_pack_path)
    accepted_context = _accepted_context(runtime_config)
    ledger = _load_ledger(runtime_config.state_path)

    events_seen = 0
    skipped = 0
    refused = 0
    package_paths: list[str] = []
    package_payloads: list[dict[str, object]] = []

    for source_path in _source_event_paths(runtime_config.source_event_dir):
        events_seen += 1
        try:
            source_event = _load_json_object(source_path)
            event_id = _required_str(source_event, "eventId")
            event_hash = _required_str(source_event, "hash")
        except ValueError as exc:
            event_hash = _file_hash(source_path)
            event_id = f"invalid-source-event-{_slug(source_path.stem)}-{event_hash[7:19]}"
            if _event_already_handled(ledger, event_id, event_hash, store):
                skipped += 1
                _trace(
                    runtime_config,
                    actor="agent",
                    event_type="tool_call",
                    name="resident_loop_skip_duplicate",
                    scope="source:read",
                    path=_display_path(runtime_config, source_path),
                    summary=f"Skipped already-refused malformed source event {source_path.name}.",
                    result="skipped",
                )
                continue
            refused += 1
            _record_refusal(ledger, event_id, event_hash)
            _trace(
                runtime_config,
                actor="agent",
                event_type="refusal",
                name="source_event_intake",
                scope="source:read",
                path=_display_path(runtime_config, source_path),
                summary=f"Refused malformed source event {source_path.name}: {exc}",
                result="refused",
            )
            continue

        if _event_already_handled(ledger, event_id, event_hash, store):
            skipped += 1
            _trace(
                runtime_config,
                actor="agent",
                event_type="tool_call",
                name="resident_loop_skip_duplicate",
                scope="source:read",
                path=_display_path(runtime_config, source_path),
                summary=f"Skipped already-handled source event {event_id}.",
                result="skipped",
            )
            continue

        _trace(
            runtime_config,
            actor="agent",
            event_type="resource_read",
            name="source_event",
            scope="source:read",
            path=_display_path(runtime_config, source_path),
            summary=f"Read redacted source event {event_id}.",
            result="pass",
        )

        try:
            package = compile_model_change(
                model_pack=model_pack,
                source_event=source_event,
                accepted_context={
                    **accepted_context,
                    "processedEventIds": _merged_strings(
                        accepted_context.get("processedEventIds"),
                        _ledger_strings(ledger, "processedEventIds"),
                    ),
                    "processedHashes": _merged_strings(
                        accepted_context.get("processedHashes"),
                        _ledger_strings(ledger, "processedHashes"),
                    ),
                },
            )
        except CompilerRefusal as exc:
            refused += 1
            _record_refusal(ledger, event_id, event_hash)
            _trace(
                runtime_config,
                actor="agent",
                event_type="refusal",
                name="compile_model_change",
                scope="ontology:admin-review",
                path=_display_path(runtime_config, source_path),
                summary=f"Refused source event {event_id}: {exc}",
                result="refused",
            )
            continue

        package_id = _required_str(package, "packageId")
        package_path = runtime_config.package_output_dir / f"{package_id}.json"
        if store is not None:
            store.record_source_event(source_event)
            store.record_model_change_package(package)
        _write_json(package_path, package)
        package_payloads.append(package)
        if len(package_paths) < runtime_config.summary_package_limit:
            package_paths.append(_display_path(runtime_config, package_path))
        _record_processed(ledger, event_id, event_hash, package_id, package_path, runtime_config)
        _trace(
            runtime_config,
            actor="agent",
            event_type="artifact_write",
            name="model_change_package",
            scope="ontology:admin-review",
            path=_display_path(runtime_config, package_path),
            summary=f"Queued model-change package {package_id}; no accepted files changed.",
            result="queued-for-review"
            if _review_action(package) != "no-review-needed"
            else "pass",
        )

    digest = _write_digest(runtime_config, package_payloads, refused)
    _write_json(runtime_config.state_path, ledger)

    summary = {
        "status": "ok",
        "run_id": run_id,
        "events_seen": events_seen,
        "packages_written": len(package_payloads),
        "events_skipped": skipped,
        "events_refused": refused,
        "package_paths": package_paths,
        "package_paths_total": len(package_payloads),
        "package_paths_truncated": max(0, len(package_payloads) - len(package_paths)),
        "state_path": _display_path(runtime_config, runtime_config.state_path),
        "trace_path": _display_path(runtime_config, runtime_config.trace_path),
        "digest": digest,
    }
    if runtime_config.store_path is not None:
        summary["store_path"] = _display_path(runtime_config, runtime_config.store_path)
    if store is not None:
        store.record_run(
            {
                "runId": run_id,
                "status": "succeeded",
                "startedAt": run_started_at,
                "finishedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "summary": summary,
            }
        )
        store.close()
    return summary


def _normalize_config(config: dict[str, object]) -> ResidentLoopConfig:
    if not isinstance(config, dict):
        raise ValueError("runtime config must be a JSON-like object")

    package_output_dir = _required_path(config, "package_output_dir", "packageOutputDir")
    state_path = _required_path(config, "state_path", "statePath")
    artifact_root = _optional_path(config, "artifact_root", "artifactRoot") or package_output_dir.parent
    state_root = _optional_path(config, "state_root", "stateRoot") or state_path.parent
    digest_path = _optional_path(config, "digest_path", "digestPath") or (
        artifact_root / "digests" / DEFAULT_DIGEST_NAME
    )
    runtime_config = ResidentLoopConfig(
        model_pack_path=_required_path(config, "model_pack_path", "modelPackPath"),
        source_event_dir=_required_path(config, "source_event_dir", "sourceEventDir"),
        package_output_dir=package_output_dir,
        state_path=state_path,
        trace_path=_required_path(config, "trace_path", "tracePath"),
        artifact_root=artifact_root,
        state_root=state_root,
        store_path=_optional_path(config, "store_path", "storePath"),
        accepted_context_path=_optional_path(
            config,
            "accepted_context_path",
            "acceptedContextPath",
        ),
        ontology_revision=str(
            _value(config, "ontology_revision", "ontologyRevision", default=DEFAULT_ONTOLOGY_REVISION)
        ),
        generated_at=str(_value(config, "generated_at", "generatedAt", default="")),
        digest_path=digest_path,
        digest_threshold=_positive_int(config, "digest_threshold", "digestThreshold", default=1),
        summary_package_limit=_positive_int(
            config,
            "summary_package_limit",
            "summaryPackageLimit",
            default=DEFAULT_SUMMARY_PACKAGE_LIMIT,
        ),
        digest_package_limit=_positive_int(
            config,
            "digest_package_limit",
            "digestPackageLimit",
            default=DEFAULT_DIGEST_PACKAGE_LIMIT,
        ),
        write_digest=bool(_value(config, "write_digest", "writeDigest", default=True)),
    )
    _validate_write_boundaries(runtime_config)
    return runtime_config


def _accepted_context(config: ResidentLoopConfig) -> dict[str, object]:
    context: dict[str, object] = {
        "ontologyRevision": config.ontology_revision,
    }
    if config.generated_at:
        context["generatedAt"] = config.generated_at
    if config.accepted_context_path is not None and config.accepted_context_path.exists():
        context.update(_load_json_object(config.accepted_context_path))
    return context


def _source_event_paths(source_event_dir: Path) -> list[Path]:
    if not source_event_dir.is_dir():
        raise ValueError(f"source_event_dir is not a directory: {source_event_dir}")
    return sorted(path for path in source_event_dir.glob("*.json") if path.is_file())


def _load_ledger(path: Path) -> dict[str, object]:
    if not path.exists():
        return {
            "processedEventIds": [],
            "processedHashes": [],
            "refusedEventIds": [],
            "refusedHashes": [],
            "packages": [],
        }
    ledger = _load_json_object(path)
    for key in ("processedEventIds", "processedHashes", "refusedEventIds", "refusedHashes"):
        ledger[key] = sorted(set(_string_list(ledger.get(key))))
    packages = ledger.get("packages")
    if not isinstance(packages, list):
        ledger["packages"] = []
    return ledger


def _connect_store(config: ResidentLoopConfig) -> OperationalStore | None:
    if config.store_path is None:
        return None
    store = OperationalStore.connect(config.store_path)
    store.initialize()
    return store


def _event_already_handled(
    ledger: dict[str, object],
    event_id: str,
    event_hash: str,
    store: OperationalStore | None = None,
) -> bool:
    if store is not None and store.source_event_seen(event_id, event_hash):
        return True
    return (
        event_id in _ledger_strings(ledger, "processedEventIds")
        or event_hash in _ledger_strings(ledger, "processedHashes")
        or event_id in _ledger_strings(ledger, "refusedEventIds")
        or event_hash in _ledger_strings(ledger, "refusedHashes")
    )


def _record_processed(
    ledger: dict[str, object],
    event_id: str,
    event_hash: str,
    package_id: str,
    package_path: Path,
    config: ResidentLoopConfig,
) -> None:
    _append_unique(ledger, "processedEventIds", event_id)
    _append_unique(ledger, "processedHashes", event_hash)
    packages = ledger.get("packages")
    if not isinstance(packages, list):
        packages = []
        ledger["packages"] = packages
    packages.append(
        {
            "packageId": package_id,
            "path": _display_path(config, package_path),
            "sourceEventIds": [event_id],
        }
    )


def _record_refusal(ledger: dict[str, object], event_id: str, event_hash: str) -> None:
    _append_unique(ledger, "refusedEventIds", event_id)
    _append_unique(ledger, "refusedHashes", event_hash)


def _write_digest(
    config: ResidentLoopConfig,
    packages: list[dict[str, object]],
    refused: int,
) -> dict[str, object]:
    if not config.write_digest:
        return {"status": "disabled", "path": "", "review_package_count": 0}

    reviewable = [package for package in packages if _review_action(package) != "no-review-needed"]
    if len(reviewable) < config.digest_threshold:
        _trace(
            config,
            actor="agent",
            event_type="digest",
            name="resident_digest",
            scope="ontology:admin-review",
            summary=(
                f"Digest skipped: {len(reviewable)} review package(s) below "
                f"threshold {config.digest_threshold}."
            ),
            result="skipped",
        )
        return {
            "status": "skipped",
            "path": "",
            "review_package_count": len(reviewable),
            "threshold": config.digest_threshold,
        }

    digest_path = config.digest_path or config.artifact_root / "digests" / DEFAULT_DIGEST_NAME
    lines = [
        "# Resident runtime digest",
        "",
        f"Review packages: {len(reviewable)}",
        f"Refused source events: {refused}",
        "",
    ]
    digest_packages = reviewable[: config.digest_package_limit]
    for package in digest_packages:
        lines.append(
            "- "
            + _required_str(package, "packageId")
            + " - "
            + _review_action(package)
            + " - "
            + _bounded_summary(str(package.get("summary", "")))
        )
    truncated = max(0, len(reviewable) - len(digest_packages))
    if truncated:
        lines.append(f"- ... {truncated} more package(s) omitted from this bounded digest.")
    digest_path.parent.mkdir(parents=True, exist_ok=True)
    digest_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    _trace(
        config,
        actor="agent",
        event_type="digest",
        name="resident_digest",
        scope="ontology:admin-review",
        path=_display_path(config, digest_path),
        summary=f"Prepared resident-loop digest with {len(reviewable)} review package(s).",
        result="pass",
    )
    return {
        "status": "written",
        "path": _display_path(config, digest_path),
        "review_package_count": len(reviewable),
        "entries_written": len(digest_packages),
        "entries_truncated": truncated,
        "threshold": config.digest_threshold,
    }


def _trace(config: ResidentLoopConfig, **event: object) -> None:
    payload: dict[str, object] = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "actor": str(event.get("actor", "agent")),
        "event_type": str(event.get("event_type", "tool_call")),
        "name": str(event.get("name", "unknown")),
        "scope": str(event.get("scope", "ontology:admin-review")),
        "summary": _bounded_summary(str(event.get("summary", ""))),
        "result": str(event.get("result", "pass")),
    }
    path = event.get("path")
    if isinstance(path, str) and path:
        payload["path"] = path
    config.trace_path.parent.mkdir(parents=True, exist_ok=True)
    with config.trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"cannot read JSON object from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _validate_write_boundaries(config: ResidentLoopConfig) -> None:
    write_targets = [
        ("packageOutputDir", config.package_output_dir, config.artifact_root),
        ("tracePath", config.trace_path, config.artifact_root),
        ("statePath", config.state_path, config.state_root),
    ]
    if config.store_path is not None:
        write_targets.append(("storePath", config.store_path, config.state_root))
    if config.digest_path is not None:
        write_targets.append(("digestPath", config.digest_path, config.artifact_root))
    for label, root in (("artifactRoot", config.artifact_root), ("stateRoot", config.state_root)):
        if _is_project_root(root):
            raise ValueError(f"{label} must not be the repository root")
        if _is_forbidden_write_target(root):
            raise ValueError(f"{label} points at a forbidden ontology path: {root}")
    for label, target, root in write_targets:
        if not _is_within(target, root):
            raise ValueError(f"{label} must stay within its configured write root")
        if _is_forbidden_write_target(target):
            raise ValueError(f"{label} points at a forbidden ontology path: {target}")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _is_project_root(path: Path) -> bool:
    resolved = path.resolve()
    return resolved == REPO_ROOT.resolve() or (
        (resolved / "AGENTS.md").exists() and (resolved / "README.md").exists()
    )


def _is_forbidden_write_target(path: Path) -> bool:
    resolved = path.resolve()
    candidates = [resolved]
    for root in (REPO_ROOT.resolve(), Path.cwd().resolve()):
        try:
            rel = resolved.relative_to(root)
        except ValueError:
            continue
        parts = set(rel.parts)
        if parts & FORBIDDEN_WRITE_PARTS:
            return True
        if rel.name in FORBIDDEN_WRITE_FILES:
            return True
    for candidate in candidates:
        if candidate.name in FORBIDDEN_WRITE_FILES or candidate.name in FORBIDDEN_WRITE_PARTS:
            return True
    return False


def _review_action(package: dict[str, object]) -> str:
    review = package.get("review")
    if isinstance(review, dict) and isinstance(review.get("overallAction"), str):
        return str(review["overallAction"])
    return "human-review"


def _display_path(config: ResidentLoopConfig, path: Path) -> str:
    resolved = path.resolve()
    for root in (config.artifact_root.resolve(), Path.cwd().resolve()):
        try:
            return str(resolved.relative_to(root))
        except ValueError:
            continue
    return path.name


def _required_path(config: dict[str, object], *names: str) -> Path:
    value = _value(config, *names)
    if not isinstance(value, str) or not value:
        raise ValueError(f"runtime config requires one of: {', '.join(names)}")
    return Path(value)


def _optional_path(config: dict[str, object], *names: str) -> Path | None:
    value = _value(config, *names, default="")
    if value in {"", None}:
        return None
    if not isinstance(value, str):
        raise ValueError(f"runtime config path must be a string: {', '.join(names)}")
    return Path(value)


def _value(config: dict[str, object], *names: str, default: object = None) -> object:
    for name in names:
        if name in config:
            return config[name]
    return default


def _positive_int(config: dict[str, object], *names: str, default: int) -> int:
    raw_value = _value(config, *names, default=default)
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{names[0]} must be an integer") from exc
    return max(1, value)


def _required_str(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing required string field {key!r}")
    return value


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _ledger_strings(ledger: dict[str, object], key: str) -> list[str]:
    return _string_list(ledger.get(key))


def _merged_strings(first: object, second: object) -> list[str]:
    return sorted(set(_string_list(first)) | set(_string_list(second)))


def _append_unique(ledger: dict[str, object], key: str, value: str) -> None:
    values = _ledger_strings(ledger, key)
    if value not in values:
        values.append(value)
    ledger[key] = values


def _bounded_summary(value: str) -> str:
    value = " ".join(value.split())
    if len(value) > 280:
        return value[:277].rstrip() + "..."
    return value


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _slug(value: str) -> str:
    slug = ID_RE.sub("-", value.lower()).strip("-")
    return slug or "unknown"

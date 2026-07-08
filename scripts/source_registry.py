"""Workspace source instance registry and live-proof ledger."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any
import hashlib

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from package_update_common import utc_timestamp, write_json_atomic


SOURCE_REGISTRY_NAME = "source-instances.json"
LIVE_PROOF_LEDGER = "live-proofs/proofs.json"
LIVE_PROVEN_STATUSES = {"live-proven", "scheduled"}
PROOF_BACKED_STATUSES = {"source-connected", *LIVE_PROVEN_STATUSES}


def registry_path(workspace: Path) -> Path:
    return workspace / SOURCE_REGISTRY_NAME


def proof_ledger_path(workspace: Path) -> Path:
    return workspace / LIVE_PROOF_LEDGER


def sha256_file_ref(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load_source_registry(workspace: Path) -> dict[str, Any]:
    path = registry_path(workspace)
    if not path.exists():
        return {"source_instances": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    instances = data.get("source_instances")
    if not isinstance(instances, list):
        return {"source_instances": []}
    return {"source_instances": instances}


def load_live_proofs(workspace: Path) -> dict[str, Any]:
    path = proof_ledger_path(workspace)
    if not path.exists():
        return {"live_proofs": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    proofs = data.get("live_proofs")
    if not isinstance(proofs, list):
        return {"live_proofs": []}
    return {"live_proofs": proofs}


def upsert_source_instance(workspace: Path, record: dict[str, Any]) -> dict[str, Any]:
    registry = load_source_registry(workspace)
    now = utc_timestamp()
    normalized = _source_instance_record(record, now=now)
    replaced = False
    next_instances = []
    for item in registry["source_instances"]:
        if item.get("source_instance_id") == normalized["source_instance_id"]:
            normalized["created_at"] = item.get("created_at") or normalized["created_at"]
            if not normalized["last_live_proof_id"] and item.get("last_live_proof_id"):
                normalized["last_live_proof_id"] = str(item["last_live_proof_id"])
            if normalized["status"] == "configured" and item.get("status") in PROOF_BACKED_STATUSES:
                normalized["status"] = str(item["status"])
            next_instances.append(normalized)
            replaced = True
        else:
            next_instances.append(item)
    if not replaced:
        next_instances.append(normalized)
    next_instances.sort(key=lambda item: str(item.get("source_instance_id") or ""))
    write_json_atomic(registry_path(workspace), {"source_instances": next_instances})
    return normalized


def record_live_proof(workspace: Path, proof: dict[str, Any]) -> dict[str, Any]:
    registry = load_source_registry(workspace)
    source_instance_id = str(proof.get("source_instance_id") or "")
    if not any(item.get("source_instance_id") == source_instance_id for item in registry["source_instances"]):
        raise ValueError(f"live proof references unknown source instance: {source_instance_id}")
    ledger = load_live_proofs(workspace)
    now = utc_timestamp()
    normalized = _live_proof_record(proof, now=now)
    replaced = False
    next_proofs = []
    for item in ledger["live_proofs"]:
        if item.get("live_proof_id") == normalized["live_proof_id"]:
            normalized["created_at"] = item.get("created_at") or normalized["created_at"]
            next_proofs.append(normalized)
            replaced = True
        else:
            next_proofs.append(item)
    if not replaced:
        next_proofs.append(normalized)
    next_proofs.sort(key=lambda item: str(item.get("live_proof_id") or ""))
    write_json_atomic(proof_ledger_path(workspace), {"live_proofs": next_proofs})
    _update_instance_after_proof(workspace, normalized, now=now)
    return normalized


def ready_source_instances(workspace: Path, *, owner_agent: str) -> list[dict[str, Any]]:
    registry = load_source_registry(workspace)
    return [
        item
        for item in registry["source_instances"]
        if item.get("owner_agent") == owner_agent and item.get("status") in LIVE_PROVEN_STATUSES
    ]


def _source_instance_record(record: dict[str, Any], *, now: str) -> dict[str, Any]:
    required = [
        "source_instance_id",
        "owner_agent",
        "kind",
        "runtime_adapter",
        "config_ref",
        "cursor_ref",
        "output_ref",
        "scheduler_ref",
        "status",
        "last_live_proof_id",
    ]
    missing = [key for key in required if key not in record]
    if missing:
        raise ValueError("source instance missing required field(s): " + ", ".join(missing))
    return {
        **{key: str(record.get(key) or "") for key in required},
        "created_at": str(record.get("created_at") or now),
        "updated_at": now,
    }


def _live_proof_record(proof: dict[str, Any], *, now: str) -> dict[str, Any]:
    required = [
        "live_proof_id",
        "source_instance_id",
        "capability",
        "mode",
        "input_ref",
        "output_artifacts",
        "evidence_hash",
        "status",
    ]
    missing = [key for key in required if key not in proof]
    if missing:
        raise ValueError("live proof missing required field(s): " + ", ".join(missing))
    artifacts = proof.get("output_artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("output_artifacts must be a list")
    return {
        "live_proof_id": str(proof.get("live_proof_id") or ""),
        "source_instance_id": str(proof.get("source_instance_id") or ""),
        "capability": str(proof.get("capability") or ""),
        "mode": str(proof.get("mode") or ""),
        "input_ref": str(proof.get("input_ref") or ""),
        "output_artifacts": [str(item) for item in artifacts],
        "evidence_hash": str(proof.get("evidence_hash") or ""),
        "status": str(proof.get("status") or ""),
        "created_at": str(proof.get("created_at") or now),
        "updated_at": now,
    }


def _update_instance_after_proof(workspace: Path, proof: dict[str, Any], *, now: str) -> None:
    registry = load_source_registry(workspace)
    next_instances = []
    for item in registry["source_instances"]:
        if item.get("source_instance_id") == proof["source_instance_id"]:
            updated = dict(item)
            updated["last_live_proof_id"] = proof["live_proof_id"]
            updated["updated_at"] = now
            if proof.get("status") == "passed":
                updated["status"] = "live-proven"
            elif proof.get("status") == "source-connected":
                updated["status"] = "source-connected"
            elif proof.get("status") == "failed":
                updated["status"] = "failed"
            next_instances.append(updated)
        else:
            next_instances.append(item)
    write_json_atomic(registry_path(workspace), {"source_instances": next_instances})

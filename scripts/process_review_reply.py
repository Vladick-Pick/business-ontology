#!/usr/bin/env python3
"""Apply one authorized review reply and refresh the accepted model.

Raw reply text is accepted only on stdin, used for deterministic intent checks,
and never stored or returned. Human authority, exact reply correlation, package
identity, accepted-state mutation, request closure, export, and publication are
separate fail-closed gates.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
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
    is_review_authorized,
    load_review_authority,
)
from export_accepted_model import export_snapshot  # noqa: E402
from resolve_owner_reply import (  # noqa: E402
    MAX_REPLY_CHARS,
    _open_match,
    resolve_owner_reply,
)


APPROVAL_RE = re.compile(
    r"\b(?:accept|accepted|approve|approved|apply|confirm|confirmed|"
    r"принять|принимаю|принял|приняла|одобрить|одобряю|одобрено|"
    r"применить|применяй|подтвердить|подтверждаю|подтверждено)\b",
    re.IGNORECASE,
)
REJECTION_RE = re.compile(
    r"\b(?:reject|rejected|decline|отклонить|отклоняю|не принимать|не применяй)\b",
    re.IGNORECASE,
)
EDIT_MARKER_RE = re.compile(
    r"\b(?:except|but|edit|change|revise|кроме|но|исправ|измен|доработ|за исключением)\b",
    re.IGNORECASE,
)
GENERIC_APPROVAL_RE = re.compile(
    r"^\s*(?:yes|ok|okay|done|да|ага|ок|окей|хорошо|всё ок|все ок)\s*[.!]*\s*$",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _runtime_config(workspace: Path) -> tuple[dict[str, Any], Path]:
    for name in ("runtime-config.json", "runtime-config.example.json"):
        path = workspace / name
        payload = _load_json(path)
        if payload:
            return payload, path
    raise ValueError("workspace runtime config is missing")


def _workspace_path(workspace: Path, value: object, default: str) -> Path:
    relative = Path(str(value or default))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"workspace path must stay relative: {relative}")
    return workspace / relative


def _expected_decision_id(package: dict[str, object]) -> str:
    ids: set[str] = set()

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "decision_id" and isinstance(item, str) and item.strip():
                    ids.add(item.strip())
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    for change in package.get("changes") or []:
        if isinstance(change, dict):
            visit(change.get("acceptedItem"))
            visit(change.get("acceptedWorkflow"))
    if len(ids) != 1:
        raise ValueError("review package must bind accepted payloads to exactly one decision id")
    return next(iter(ids))


def _risk_scope(package: dict[str, object]) -> str:
    for change in package.get("changes") or []:
        if isinstance(change, dict) and change.get("risk") == "high":
            return "high-risk"
    return "routine"


def _approval_intent(reply_text: str, recommended_answer: str, recommendation_confirmed: bool) -> bool:
    text = reply_text.strip()
    if EDIT_MARKER_RE.search(text) or REJECTION_RE.search(text):
        return False
    if APPROVAL_RE.search(text):
        return True
    if recommendation_confirmed or GENERIC_APPROVAL_RE.fullmatch(text):
        return bool(APPROVAL_RE.search(recommended_answer))
    return False


def _decision_payload(
    *,
    package: dict[str, object],
    actor: str,
    channel: str,
    scope: str,
    inbound_message_ref: str,
    decided_at: str,
) -> dict[str, object]:
    affected_ids: list[str] = []
    for change in package.get("changes") or []:
        if not isinstance(change, dict):
            continue
        for item in change.get("affectedIds") or []:
            value = str(item)
            if value and value not in affected_ids:
                affected_ids.append(value)
    return {
        "packageId": str(package.get("packageId") or ""),
        "actor": actor,
        "decision": "approved",
        "reason": "Authorized reviewer approved the exact referenced model revision.",
        "decidedAt": decided_at,
        "channel": channel,
        "authorityScope": scope,
        "sourceMessageRef": inbound_message_ref,
        "ontologyRevision": str(package.get("ontologyRevision") or "unknown"),
        "affectedIds": affected_ids,
    }


def _current_revision(workspace: Path, config: dict[str, Any], package: dict[str, object]) -> str:
    context_path = _workspace_path(
        workspace,
        config.get("accepted_context_path"),
        "model/ontology/accepted-context.json",
    )
    context = _load_json(context_path)
    cards = context.get("cards")
    if isinstance(cards, list) and cards:
        return str(context.get("revision") or config.get("ontology_revision") or "")
    return str(package.get("ontologyRevision") or "")


def _publication_rendering(
    *,
    applied_count: int,
    public_url: str,
    published: bool,
) -> str:
    if published:
        suffix = f"\nАктуальная модель: {public_url}" if public_url else ""
        return (
            f"Принял. Решение применено: в актуальной модели {applied_count} карточек. "
            f"Запрос по этой ревизии закрыт.{suffix}"
        )
    return (
        f"Решение принято и {applied_count} карточек записаны в актуальную модель, "
        "но публичное представление пока не подтвердило обновление. Повторное решение не нужно."
    )


def _publish(
    *,
    workspace: Path,
    model_root: Path,
    package_root: Path,
    config: dict[str, Any],
    revision: str,
) -> tuple[bool, dict[str, Any]]:
    out_dir = _workspace_path(
        workspace,
        config.get("viewer_output_path"),
        "viewer",
    )
    command = [
        sys.executable,
        str(package_root / "scripts" / "publish_viewer.py"),
        str(model_root),
        "--workspace",
        str(workspace),
        "--out-dir",
        str(out_dir),
        "--package-root",
        str(package_root),
        "--revision",
        revision,
        "--json",
    ]
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=45)
    except Exception:
        return False, {"status": "execution-failed"}
    try:
        report = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        report = {}
    if not isinstance(report, dict):
        report = {}
    return result.returncode == 0, report


def _public_url(config: dict[str, Any]) -> str:
    publication = config.get("viewer_publication")
    if not isinstance(publication, dict):
        return ""
    return str(publication.get("public_url") or "").rstrip("/") + (
        "/" if publication.get("public_url") else ""
    )


def _accepted_card_count(store: OperationalStore) -> int:
    item_ids = {
        str(item.get("id") or item.get("item_id") or "")
        for item in store.list_accepted_items()
    }
    workflow_ids = {
        str(workflow.get("workflow_id") or "")
        for workflow in store.list_accepted_workflows()
    }
    return len({item_id for item_id in item_ids | workflow_ids if item_id})


def _applied_projection_pending(
    *,
    package_id: str,
    decision_id: str,
    revision: str,
    card_count: int,
    applied: dict[str, list[str]],
    config: dict[str, Any],
    report_status: str,
) -> dict[str, Any]:
    return {
        "handled": True,
        "status": "applied-publication-pending",
        "packageId": package_id,
        "decisionId": decision_id,
        "revision": revision,
        "cardCount": card_count,
        "applied": applied,
        "publication": {
            "status": "pending",
            "publicUrl": _public_url(config),
            "reportStatus": report_status,
        },
        "rendering": _publication_rendering(
            applied_count=card_count,
            public_url=_public_url(config),
            published=False,
        ),
    }


def process_review_reply(
    *,
    workspace: Path,
    package_root: Path,
    channel: str,
    actor: str,
    reply_to_message_ref: str,
    inbound_message_ref: str,
    reply_text: str,
    received_at: str | None = None,
    language: str = "ru",
) -> dict[str, Any]:
    config, config_path = _runtime_config(workspace)
    store_path = _workspace_path(
        workspace,
        config.get("store_path"),
        "agent-state/operational-store.sqlite",
    )
    authority_path = _workspace_path(
        workspace,
        config.get("review_authority_policy_path"),
        "agent-state/review-authority.json",
    )
    authority = load_review_authority(authority_path)
    timestamp = received_at or _now()

    with OperationalStore.connect(store_path) as store:
        store.initialize()
        match, _ = _open_match(
            store,
            channel=channel,
            reply_to_message_ref=reply_to_message_ref,
            authority_policy=authority,
        )
        if match is None or match.get("kind") != "review":
            return {"handled": False, "status": "not-applicable"}
        resolution = resolve_owner_reply(
            store,
            channel=channel,
            actor=actor,
            reply_to_message_ref=reply_to_message_ref,
            reply_text=reply_text,
            inbound_message_ref=inbound_message_ref,
            received_at=timestamp,
            language=language,
            authority_policy=authority,
        )
        if resolution.get("status") == "authorization-required":
            return {
                "handled": True,
                "status": "authorization-required",
                "rendering": resolution.get("rendering"),
            }
        if resolution.get("status") != "review-validation-required":
            return {"handled": False, "status": str(resolution.get("status") or "not-applicable")}

        request_id = str(resolution.get("matchedRequestId") or "")
        request = store.get_human_request(request_id)
        if request is None:
            raise ValueError("matched review request disappeared")
        package_id = str(request.get("packageId") or "")
        package = store.get_model_change_package(package_id)
        if package is None:
            raise ValueError("matched review package is missing")
        if not _approval_intent(
            reply_text,
            str(request.get("recommendedAnswer") or ""),
            bool(resolution.get("recommendationConfirmed")),
        ):
            return {"handled": False, "status": "review-content-requires-agent"}

        scope = _risk_scope(package)
        if authority.get("businessId") != package.get("moduleId") or not is_review_authorized(
            authority,
            actor=actor,
            channel=channel,
            scope=scope,
        ):
            return {
                "handled": True,
                "status": "authorization-required",
                "rendering": "У этого участника нет права принять эту ревизию в данном чате. Модель не изменена.",
            }
        decision_id = _expected_decision_id(package)
        decision = _decision_payload(
            package=package,
            actor=actor,
            channel=channel,
            scope=scope,
            inbound_message_ref=inbound_message_ref,
            decided_at=timestamp,
        )
        applied = store.record_approved_decision_and_apply(
            request_id=request_id,
            decision_id=decision_id,
            decision=decision,
            package=package,
            current_revision=_current_revision(workspace, config, package),
        )
        model_root = workspace / "model"
        card_count = _accepted_card_count(store)
        try:
            snapshot = export_snapshot(
                store,
                model_root=model_root,
                module=str(package.get("moduleId") or config.get("module_id") or "unknown"),
            )
        except Exception:
            return _applied_projection_pending(
                package_id=package_id,
                decision_id=decision_id,
                revision=str(config.get("ontology_revision") or package.get("ontologyRevision") or ""),
                card_count=card_count,
                applied=applied,
                config=config,
                report_status="accepted-export-pending",
            )

    config["accepted_context_path"] = "model/ontology/accepted-context.json"
    config["ontology_revision"] = snapshot["revision"]
    try:
        _write_json_atomic(config_path, config)
    except Exception:
        return _applied_projection_pending(
            package_id=package_id,
            decision_id=decision_id,
            revision=str(snapshot["revision"]),
            card_count=len(snapshot["cards"]),
            applied=applied,
            config=config,
            report_status="runtime-config-write-pending",
        )
    published, publish_report = _publish(
        workspace=workspace,
        model_root=model_root,
        package_root=package_root,
        config=config,
        revision=str(snapshot["revision"]),
    )
    return {
        "handled": True,
        "status": "applied-and-published" if published else "applied-publication-pending",
        "packageId": package_id,
        "decisionId": decision_id,
        "revision": snapshot["revision"],
        "cardCount": len(snapshot["cards"]),
        "applied": applied,
        "publication": {
            "status": "published" if published else "pending",
            "publicUrl": _public_url(config),
            "reportStatus": str(publish_report.get("status") or "unknown"),
        },
        "rendering": _publication_rendering(
            applied_count=len(snapshot["cards"]),
            public_url=_public_url(config),
            published=published,
        ),
    }


def reconcile_package(
    *,
    workspace: Path,
    package_root: Path,
    package_id: str,
) -> dict[str, Any]:
    config, config_path = _runtime_config(workspace)
    store_path = _workspace_path(
        workspace,
        config.get("store_path"),
        "agent-state/operational-store.sqlite",
    )
    with OperationalStore.connect(store_path) as store:
        store.initialize()
        package = store.get_model_change_package(package_id)
        if package is None:
            raise ValueError(f"model change package {package_id} is missing")
        decision_id = _expected_decision_id(package)
        with store._connection:
            applied = store.apply_approved_model_change(
                package,
                decision_id=decision_id,
                current_revision=_current_revision(workspace, config, package),
                _transaction=True,
            )
            for request in store.list_open_human_requests(kind="review", limit=10_000):
                if request.get("packageId") == package_id:
                    store.mark_human_request_answered(
                        str(request["requestId"]),
                        answer_summary="Previously recorded approval was reconciled into the accepted model.",
                        decision_id=decision_id,
                        _transaction=True,
                    )
        card_count = _accepted_card_count(store)
        try:
            snapshot = export_snapshot(
                store,
                model_root=workspace / "model",
                module=str(package.get("moduleId") or config.get("module_id") or "unknown"),
            )
        except Exception:
            return _applied_projection_pending(
                package_id=package_id,
                decision_id=decision_id,
                revision=str(config.get("ontology_revision") or package.get("ontologyRevision") or ""),
                card_count=card_count,
                applied=applied,
                config=config,
                report_status="accepted-export-pending",
            )
    config["accepted_context_path"] = "model/ontology/accepted-context.json"
    config["ontology_revision"] = snapshot["revision"]
    try:
        _write_json_atomic(config_path, config)
    except Exception:
        return _applied_projection_pending(
            package_id=package_id,
            decision_id=decision_id,
            revision=str(snapshot["revision"]),
            card_count=card_count,
            applied=applied,
            config=config,
            report_status="runtime-config-write-pending",
        )
    published, report = _publish(
        workspace=workspace,
        model_root=workspace / "model",
        package_root=package_root,
        config=config,
        revision=str(snapshot["revision"]),
    )
    return {
        "handled": True,
        "status": "applied-and-published" if published else "applied-publication-pending",
        "packageId": package_id,
        "decisionId": decision_id,
        "revision": snapshot["revision"],
        "cardCount": len(snapshot["cards"]),
        "applied": applied,
        "publication": {
            "status": "published" if published else "pending",
            "publicUrl": _public_url(config),
            "reportStatus": str(report.get("status") or "unknown"),
        },
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process one exact model-review reply.")
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--package-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--channel")
    parser.add_argument("--actor")
    parser.add_argument("--reply-to-message-ref", default="")
    parser.add_argument("--inbound-message-ref", default="")
    parser.add_argument("--received-at")
    parser.add_argument("--language", choices=("en", "ru"), default="ru")
    parser.add_argument("--reconcile-package")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    workspace = args.workspace.resolve()
    package_root = args.package_root.resolve()
    try:
        if args.reconcile_package:
            result = reconcile_package(
                workspace=workspace,
                package_root=package_root,
                package_id=args.reconcile_package,
            )
        else:
            if not args.channel or not args.actor:
                raise ValueError("--channel and --actor are required for an inbound reply")
            reply_text = sys.stdin.read(MAX_REPLY_CHARS + 1)
            if len(reply_text) > MAX_REPLY_CHARS:
                raise ValueError("reply exceeds safe input limit")
            inbound_ref = args.inbound_message_ref or (
                "inbound:sha256:"
                + hashlib.sha256(
                    "\0".join(
                        (
                            args.channel,
                            args.actor,
                            args.reply_to_message_ref,
                            args.received_at or "",
                        )
                    ).encode("utf-8")
                ).hexdigest()[:24]
            )
            result = process_review_reply(
                workspace=workspace,
                package_root=package_root,
                channel=args.channel,
                actor=args.actor,
                reply_to_message_ref=args.reply_to_message_ref,
                inbound_message_ref=inbound_ref,
                reply_text=reply_text,
                received_at=args.received_at,
                language=args.language,
            )
    except (ValueError, OSError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"handled": True, "status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Small in-process reference runtime for the business-ontology harness.

This is not a production resident agent and not a networked MCP server. It is a
dependency-free executable baseline for the contract in specs/BUSINESS-ONTOLOGY-RESIDENT.md and
references/mcp-boundary.md: read accepted resources, stage proposals, validate
before review, enforce scope checks, and emit redacted trace events.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_registry  # noqa: E402
import links_validate  # noqa: E402
from runtime.context_projection import (  # noqa: E402
    build_configuration_canvas,
    build_data_binding_projection,
    build_instance_graph_projection,
)
from runtime.draft_generator import generate_draft_ontology  # noqa: E402
from runtime.operational_store import OperationalStore  # noqa: E402


TRACE_EVENT_TYPES = {
    "resource_read",
    "tool_call",
    "artifact_write",
    "validation",
    "approval",
    "refusal",
    "digest",
}
PROPOSAL_ID_PATTERN = re.compile(r"^prop-[a-z0-9][a-z0-9-]*$")


@dataclass
class RuntimeConfig:
    module_id: str
    ontology_root: Path
    trace_path: Path
    scopes: set[str] = field(default_factory=set)
    store_path: Path | None = None


@dataclass
class PermissionDecision:
    decision: str
    tool: str
    required_scope: str
    reason: str


class BusinessOntologyRuntime:
    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.root = Path(config.ontology_root).resolve()
        self.trace_path = Path(config.trace_path).resolve()

    def list_resource_templates(self) -> dict[str, Any]:
        return {
            "resourceTemplates": [
                {
                    "uriTemplate": "ontology://{module_id}/model/current",
                    "name": "current-model",
                    "title": "Current accepted model",
                    "description": "Read the current accepted model projection with revision metadata.",
                    "mimeType": "application/json",
                },
                {
                    "uriTemplate": "ontology://{module_id}/model/entities",
                    "name": "model-entities",
                    "title": "Accepted model entities",
                    "description": "Read accepted entity projections.",
                    "mimeType": "application/json",
                },
                {
                    "uriTemplate": "ontology://{module_id}/model/relations",
                    "name": "model-relations",
                    "title": "Accepted model relations",
                    "description": "Read accepted authored and generated relation projections.",
                    "mimeType": "application/json",
                },
                {
                    "uriTemplate": "ontology://{module_id}/model/decisions",
                    "name": "model-decisions",
                    "title": "Accepted model decisions",
                    "description": "Read accepted decision projections.",
                    "mimeType": "application/json",
                },
                {
                    "uriTemplate": "ontology://{module_id}/model/drift",
                    "name": "model-drift",
                    "title": "Accepted drift and open questions",
                    "description": "Read accepted drift and open-question projection.",
                    "mimeType": "application/json",
                },
                {
                    "uriTemplate": "ontology://{module_id}/model/canvas",
                    "name": "model-canvas",
                    "title": "Configuration canvas projection",
                    "description": "Read an accepted model canvas projection for visual ontology clients.",
                    "mimeType": "application/json",
                },
                {
                    "uriTemplate": "ontology://{module_id}/model/bindings",
                    "name": "model-bindings",
                    "title": "Data binding projection",
                    "description": "Read accepted data bindings between model items and source locators.",
                    "mimeType": "application/json",
                },
                {
                    "uriTemplate": "ontology://{module_id}/model/instance-graph",
                    "name": "model-instance-graph",
                    "title": "Accepted instance graph",
                    "description": "Read a bounded accepted instance graph projection.",
                    "mimeType": "application/json",
                },
                {
                    "uriTemplate": "ontology://{module_id}/cards/{id}",
                    "name": "accepted-card",
                    "title": "Accepted ontology card",
                    "description": "Read one accepted card by stable id.",
                    "mimeType": "text/markdown",
                },
                {
                    "uriTemplate": "ontology://{module_id}/review/packages",
                    "name": "pending-review-packages",
                    "title": "Pending review packages",
                    "description": "Read bounded review queue summaries. Reference runtime does not implement a package store.",
                    "mimeType": "application/json",
                },
                {
                    "uriTemplate": "ontology://{module_id}/review/packages/{package_id}",
                    "name": "review-package",
                    "title": "Review package",
                    "description": "Read one reviewable package when a package store backs the runtime.",
                    "mimeType": "application/json",
                },
                {
                    "uriTemplate": "ontology://{module_id}/sources/events/{event_id}",
                    "name": "source-event",
                    "title": "Redacted source event",
                    "description": "Read source-event metadata and evidence locators, not raw payloads.",
                    "mimeType": "application/json",
                },
                {
                    "uriTemplate": "ontology://{module_id}/sources",
                    "name": "source-map",
                    "title": "Source map",
                    "description": "Read registered sources, trust floors, and read policies.",
                    "mimeType": "application/json",
                },
            ]
        }

    def list_resources(self) -> dict[str, Any]:
        return {
            "resources": [
                {
                    "uri": f"ontology://{self.config.module_id}/model/current",
                    "name": "current-model",
                    "title": "Current accepted model",
                    "description": "Accepted model projection with revision metadata.",
                    "mimeType": "application/json",
                },
                {
                    "uri": f"ontology://{self.config.module_id}/sources",
                    "name": "source-map",
                    "title": "Source map",
                    "description": "Registered ontology sources and read policies.",
                    "mimeType": "application/json",
                },
                {
                    "uri": f"ontology://{self.config.module_id}/model/canvas",
                    "name": "model-canvas",
                    "title": "Configuration canvas projection",
                    "description": "Accepted model canvas projection.",
                    "mimeType": "application/json",
                },
                {
                    "uri": f"ontology://{self.config.module_id}/model/bindings",
                    "name": "model-bindings",
                    "title": "Data binding projection",
                    "description": "Accepted data binding projection.",
                    "mimeType": "application/json",
                },
            ]
        }

    def list_tools(self) -> dict[str, Any]:
        return {
            "tools": [
                {
                    "name": "propose_change",
                    "title": "Propose ontology change",
                    "description": "Create or update one staged proposal; never mutates accepted cards.",
                    "inputSchema": self._propose_input_schema(),
                    "outputSchema": self._propose_output_schema(),
                },
                {
                    "name": "validate_proposal",
                    "title": "Validate staged proposals",
                    "description": "Run the ontology validator against promoted plus staged proposals.",
                    "inputSchema": self._validate_input_schema(),
                    "outputSchema": self._validate_output_schema(),
                },
                {
                    "name": "prepare_promote_digest",
                    "title": "Prepare promotion digest",
                    "description": "Prepare a human review packet after validation; never promotes.",
                    "inputSchema": self._digest_input_schema(),
                    "outputSchema": self._digest_output_schema(),
                },
                {
                    "name": "generate_draft_ontology",
                    "title": "Generate draft ontology",
                    "description": "Compile redacted source events into reviewable draft packages and binding suggestions.",
                    "inputSchema": self._draft_input_schema(),
                    "outputSchema": self._draft_output_schema(),
                },
            ]
        }

    def read_resource(self, uri: str) -> dict[str, Any]:
        module_id, path = self._parse_uri(uri)
        if module_id != self.config.module_id:
            self._trace(
                actor="agent",
                event_type="refusal",
                name="resources/read",
                scope="ontology:read",
                uri=uri,
                summary="Refused resource read for unknown module.",
                result="refused",
            )
            return {"contents": [], "status": "refused", "refusal_reason": "unknown module_id"}
        permission = self._require_scope("resources/read", "ontology:read")
        if permission.decision != "allow":
            return self._refusal_result("resources/read", permission.reason, uri=uri)

        if path.startswith("cards/"):
            card_id = path.split("/", 1)[1]
            text, rel_path = self._read_card(card_id)
            self._trace(
                actor="agent",
                event_type="resource_read",
                name="accepted-card",
                scope="ontology:read",
                uri=uri,
                path=rel_path,
                summary=f"Read accepted card {card_id}.",
                result="pass",
            )
            return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": text}]}

        if path == "sources":
            payload = self._source_map_payload()
            self._trace(
                actor="agent",
                event_type="resource_read",
                name="source-map",
                scope="ontology:read",
                uri=uri,
                summary="Read source map without credential values.",
                result="pass",
            )
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(payload, indent=2, sort_keys=True),
                    }
                ]
            }

        if path in {"model/current", "manifest"}:
            registry = self._compile_registry_payload()
            revision = self._local_revision(registry)
            payload = {
                "moduleId": self.config.module_id,
                "source": "accepted-export",
                "revision": revision,
                "stale": False,
                "manifest": registry["manifest"],
            }
            self._trace(
                actor="agent",
                event_type="resource_read",
                name="current-model",
                scope="ontology:read",
                uri=uri,
                summary="Read accepted model projection.",
                result="pass",
            )
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(payload, indent=2, sort_keys=True),
                    }
                ]
            }

        if path in {
            "model/entities",
            "model/relations",
            "model/decisions",
            "model/drift",
            "registry/nodes",
            "registry/edges",
        }:
            registry = self._compile_registry_payload()
            revision = self._local_revision(registry)
            key = {
                "model/entities": "nodes",
                "model/relations": "edges",
                "model/decisions": "decisions",
                "model/drift": "drift",
                "registry/nodes": "nodes",
                "registry/edges": "edges",
            }[path]
            if key == "decisions":
                payload: Any = [node for node in registry["nodes"] if node.get("type") == "decision"]
            elif key == "drift":
                payload = {
                    "moduleId": self.config.module_id,
                    "revision": revision,
                    "stale": False,
                    "items": registry["open_questions"],
                }
            else:
                payload = registry[key]
            self._trace(
                actor="agent",
                event_type="resource_read",
                name=key,
                scope="ontology:read",
                uri=uri,
                summary=f"Read compiled registry {key}.",
                result="pass",
            )
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(payload, indent=2, sort_keys=True),
                    }
                ]
            }

        if path in {"model/canvas", "model/bindings", "model/instance-graph"}:
            return self._read_store_projection(path, uri)

        if path == "review/packages" or path.startswith("review/packages/"):
            permission = self._require_scope("resources/read", "ontology:admin-review")
            if permission.decision != "allow":
                return self._refusal_result(
                    "resources/read",
                    permission.reason,
                    uri=uri,
                    scope="ontology:admin-review",
                )
            if self.config.store_path is None:
                return self._refusal_result(
                    "resources/read",
                    "reference runtime has no package store configured",
                    uri=uri,
                    scope="ontology:admin-review",
                )
            with self._open_store() as store:
                if path == "review/packages":
                    payload: Any = store.list_pending_packages()
                else:
                    package_id = path.rsplit("/", 1)[1]
                    payload = store.get_model_change_package(package_id)
                    if payload is None:
                        return self._refusal_result(
                            "resources/read",
                            f"unknown package_id {package_id!r}",
                            uri=uri,
                            scope="ontology:admin-review",
                        )
            self._trace(
                actor="agent",
                event_type="resource_read",
                name="review-packages",
                scope="ontology:admin-review",
                uri=uri,
                summary="Read store-backed review package resource.",
                result="pass",
            )
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(payload, indent=2, sort_keys=True),
                    }
                ]
            }

        if path.startswith("sources/events/"):
            permission = self._require_scope("resources/read", "ontology:admin-review")
            if permission.decision != "allow":
                return self._refusal_result(
                    "resources/read",
                    permission.reason,
                    uri=uri,
                    scope="ontology:admin-review",
                )
            if self.config.store_path is None:
                return self._refusal_result(
                    "resources/read",
                    "reference runtime has no source-event store configured",
                    uri=uri,
                    scope="ontology:admin-review",
                )
            event_id = path.rsplit("/", 1)[1]
            with self._open_store() as store:
                payload = store.get_source_event(event_id)
            if payload is None:
                return self._refusal_result(
                    "resources/read",
                    f"unknown source event {event_id!r}",
                    uri=uri,
                    scope="ontology:admin-review",
                )
            self._trace(
                actor="agent",
                event_type="resource_read",
                name="source-event",
                scope="ontology:admin-review",
                uri=uri,
                summary="Read redacted source event metadata from store.",
                result="pass",
            )
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(payload, indent=2, sort_keys=True),
                    }
                ]
            }

        return self._refusal_result("resources/read", "resource is not exposed", uri=uri)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "propose_change":
            return self._propose_change(arguments)
        if name == "validate_proposal":
            return self._validate_proposal(arguments)
        if name == "prepare_promote_digest":
            return self._prepare_promote_digest(arguments)
        if name == "generate_draft_ontology":
            return self._generate_draft_ontology(arguments)
        return self._refusal_result(name, f"tool {name!r} is not exposed by reference runtime")

    def _propose_change(self, arguments: dict[str, Any]) -> dict[str, Any]:
        permission = self._require_scope("propose_change", "ontology:propose")
        if permission.decision != "allow":
            return self._refusal_result("propose_change", permission.reason)
        module_error = self._module_error(arguments)
        if module_error:
            return self._refusal_result("propose_change", module_error)

        candidate = str(arguments.get("candidate_card_markdown", ""))
        sensitive = self._sensitive_findings(candidate)
        if sensitive:
            return self._refusal_result(
                "propose_change",
                "candidate card contains sensitive content: " + ", ".join(sensitive),
            )
        source_id = str(arguments.get("source_id", "")).strip()
        source_error = self._source_policy_error(source_id)
        if source_error:
            return self._refusal_result("propose_change", source_error)

        proposal_id = str(arguments.get("proposal_id") or self._generated_proposal_id())
        if not PROPOSAL_ID_PATTERN.match(proposal_id):
            return self._refusal_result(
                "propose_change",
                "proposal_id must match ^prop-[a-z0-9][a-z0-9-]*$",
            )
        proposal_text = self._format_proposal(proposal_id, arguments, candidate)
        sensitive = self._sensitive_findings(proposal_text)
        if sensitive:
            return self._refusal_result(
                "propose_change",
                "proposal contains sensitive content: " + ", ".join(sensitive),
            )
        staged_root = (self.root / "staged").resolve()
        proposal_path = (staged_root / f"{proposal_id}.md").resolve()
        try:
            proposal_path.relative_to(staged_root)
        except ValueError:
            return self._refusal_result("propose_change", "proposal_id resolves outside staged")
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text(proposal_text, encoding="utf-8")

        validator = self._run_validator(include_staged=True)
        proposal_path.write_text(
            proposal_text.replace("validator-result: pending", f"validator-result: {validator['status']}"),
            encoding="utf-8",
        )
        result_status = "proposed" if validator["status"] == "pass" else "refused"
        rel_path = str(proposal_path.relative_to(self.root))
        self._trace(
            actor="agent",
            event_type="validation",
            name="links_validate",
            scope="ontology:propose",
            path=rel_path,
            summary="Validated staged proposal before review.",
            result=validator["status"],
        )
        self._trace(
            actor="agent",
            event_type="artifact_write",
            name="propose_change",
            scope="ontology:propose",
            path=rel_path,
            summary="Prepared staged proposal; no accepted files changed.",
            result="proposal-ready" if validator["status"] == "pass" else "fail",
        )
        return {
            "status": result_status,
            "proposal_id": proposal_id,
            "proposal_path": rel_path,
            "validator": validator,
            "affected_ids": self._extract_candidate_ids(candidate),
            "audit_event_id": self._event_id("propose_change"),
            "refusal_reason": "" if result_status == "proposed" else "validator failed",
        }

    def _validate_proposal(self, arguments: dict[str, Any]) -> dict[str, Any]:
        permission = self._require_scope("validate_proposal", "ontology:propose")
        if permission.decision != "allow":
            return self._refusal_result("validate_proposal", permission.reason)
        module_error = self._module_error(arguments)
        if module_error:
            return self._refusal_result("validate_proposal", module_error)
        validator = self._run_validator(include_staged=True)
        self._trace(
            actor="agent",
            event_type="validation",
            name="links_validate",
            scope="ontology:propose",
            summary="Validated promoted plus staged ontology.",
            result=validator["status"],
        )
        return {
            "status": validator["status"],
            "validator_errors": validator["errors"],
            "warnings": validator["warnings"],
            "sensitive_content_findings": [],
            "affected_ids": [],
            "audit_event_id": self._event_id("validate_proposal"),
            "refusal_reason": "",
        }

    def _prepare_promote_digest(self, arguments: dict[str, Any]) -> dict[str, Any]:
        permission = self._require_scope("prepare_promote_digest", "ontology:admin-review")
        if permission.decision != "allow":
            return self._refusal_result("prepare_promote_digest", permission.reason)
        module_error = self._module_error(arguments)
        if module_error:
            return self._refusal_result("prepare_promote_digest", module_error)
        validator = self._run_validator(include_staged=True)
        staged_files = sorted((self.root / "staged").glob("*.md")) if (self.root / "staged").exists() else []
        digest_text = "\n".join(
            [
                "# Promotion review digest",
                "",
                f"Validator: {validator['status']}",
                f"Staged proposals: {len(staged_files)}",
                *(f"- {path.name}" for path in staged_files),
            ]
        )
        digest_path = ""
        if arguments.get("write_digest", True):
            digest_file = self.root / "staged" / "digest-reference-runtime.md"
            digest_file.parent.mkdir(parents=True, exist_ok=True)
            digest_file.write_text(digest_text + "\n", encoding="utf-8")
            digest_path = str(digest_file.relative_to(self.root))
        self._trace(
            actor="agent",
            event_type="tool_call",
            name="prepare_promote_digest",
            scope="ontology:admin-review",
            path=digest_path,
            summary="Prepared human review digest after validation; no promotion.",
            result="proposal-ready" if validator["status"] == "pass" else "blocked",
        )
        return {
            "status": "proposal-ready" if validator["status"] == "pass" else "blocked",
            "digest_path": digest_path,
            "digest_text": digest_text,
            "validator_status": validator["status"],
            "validator_errors": validator["errors"],
            "affected_ids": [],
            "high_risk_fields": [],
            "audit_event_id": self._event_id("prepare_promote_digest"),
            "refusal_reason": "",
        }

    def _generate_draft_ontology(self, arguments: dict[str, Any]) -> dict[str, Any]:
        permission = self._require_scope("generate_draft_ontology", "ontology:admin-review")
        if permission.decision != "allow":
            return self._draft_refusal(permission.reason)
        module_error = self._module_error(arguments)
        if module_error:
            return self._draft_refusal(module_error)
        sensitive = self._sensitive_findings(json.dumps(arguments, sort_keys=True, default=str))
        if sensitive:
            return self._draft_refusal(
                "draft input contains sensitive content: " + ", ".join(sorted(set(sensitive)))
            )
        model_pack = arguments.get("model_pack")
        source_events = arguments.get("source_events")
        accepted_context = arguments.get("accepted_context")
        if not isinstance(model_pack, dict):
            return self._draft_refusal("model_pack must be an object")
        if not isinstance(source_events, list) or not all(isinstance(item, dict) for item in source_events):
            return self._draft_refusal("source_events must be an array of objects")
        if accepted_context is not None and not isinstance(accepted_context, dict):
            return self._draft_refusal("accepted_context must be an object")
        try:
            draft = generate_draft_ontology(
                model_pack=model_pack,
                source_events=source_events,
                accepted_context=accepted_context,
            )
        except ValueError as exc:
            return self._draft_refusal(str(exc))
        self._trace(
            actor="agent",
            event_type="tool_call",
            name="generate_draft_ontology",
            scope="ontology:admin-review",
            summary="Generated reviewable draft ontology; no accepted model mutation.",
            result=str(draft["status"]),
        )
        return {
            "status": draft["status"],
            "draft": draft,
            "audit_event_id": self._event_id("generate_draft_ontology"),
            "refusal_reason": "",
        }

    def _draft_refusal(self, reason: str) -> dict[str, Any]:
        result = self._refusal_result(
            "generate_draft_ontology",
            reason,
            scope="ontology:admin-review",
        )
        result["draft"] = {}
        return result

    def _parse_uri(self, uri: str) -> tuple[str, str]:
        prefix = "ontology://"
        if not uri.startswith(prefix):
            return "", ""
        rest = uri[len(prefix) :]
        module_id, _, path = rest.partition("/")
        return module_id, path

    def _read_card(self, card_id: str) -> tuple[str, str]:
        errors: list[str] = []
        cards = links_validate.collect_cards(str(self.root), str(self.root), errors)
        card = cards.get(card_id)
        if card is None:
            raise KeyError(f"unknown accepted card id: {card_id}")
        rel_path = card.path.split(":", 1)[0]
        return (self.root / rel_path).read_text(encoding="utf-8"), rel_path

    def _source_map_payload(self) -> list[dict[str, Any]]:
        errors: list[str] = []
        path = self.root / links_validate.SOURCE_MAP_FILE
        entries = links_validate.parse_source_map(str(path), str(self.root), errors)
        return [
            {
                "id": entry.sid,
                "trust": entry.trust,
                "owner": entry.owner,
                "access_mode": entry.access_mode,
                "read_policy": entry.read_policy,
                "meaning": entry.meaning,
            }
            for entry in entries.values()
        ]

    def _compile_registry_payload(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            manifest, nodes, edges = build_registry.compile_registry(self.root, out_dir)
            open_questions_path = out_dir / "open_questions.json"
            open_questions = (
                json.loads(open_questions_path.read_text(encoding="utf-8"))
                if open_questions_path.exists()
                else []
            )
        return {
            "manifest": manifest,
            "nodes": nodes,
            "edges": edges,
            "open_questions": open_questions,
        }

    def _local_revision(self, registry: dict[str, Any]) -> str:
        manifest = {
            key: value
            for key, value in registry["manifest"].items()
            if key not in {"generated-at", "source-root"}
        }
        payload = {
            "manifest": manifest,
            "nodes": registry["nodes"],
            "edges": registry["edges"],
            "open_questions": registry["open_questions"],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return f"accepted-export:sha256:{hashlib.sha256(encoded).hexdigest()}"

    def _read_store_projection(self, path: str, uri: str) -> dict[str, Any]:
        if self.config.store_path is None:
            return self._refusal_result(
                "resources/read",
                "reference runtime has no operational store configured",
                uri=uri,
            )
        with self._open_store() as store:
            revision = self._store_revision()
            bindings = store.list_data_bindings()
            if path == "model/bindings":
                payload = build_data_binding_projection(
                    module_id=self.config.module_id,
                    revision=revision,
                    bindings=bindings,
                )
                resource_name = "model-bindings"
            elif path == "model/instance-graph":
                graph = store.query_instance_graph(limit=50)
                payload = build_instance_graph_projection(
                    module_id=self.config.module_id,
                    revision=revision,
                    instances=graph["instances"],
                    relations=graph["relations"],
                    limit=50,
                )
                resource_name = "model-instance-graph"
            else:
                include_review = "ontology:admin-review" in self.config.scopes
                graph = store.query_instance_graph(limit=50)
                instance_graph = build_instance_graph_projection(
                    module_id=self.config.module_id,
                    revision=revision,
                    instances=graph["instances"],
                    relations=graph["relations"],
                    limit=50,
                )
                payload = build_configuration_canvas(
                    module_id=self.config.module_id,
                    revision=revision,
                    items=store.list_accepted_items(),
                    workflows=store.list_accepted_workflows(),
                    data_bindings=bindings,
                    instance_graph=instance_graph,
                    pending_packages=store.list_pending_packages() if include_review else [],
                    open_questions=store.list_open_questions() if include_review else [],
                )
                resource_name = "model-canvas"
        self._trace(
            actor="agent",
            event_type="resource_read",
            name=resource_name,
            scope="ontology:read",
            uri=uri,
            summary="Read store-backed ontology projection.",
            result="pass",
        )
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(payload, indent=2, sort_keys=True),
                }
            ]
        }

    def _open_store(self) -> OperationalStore:
        if self.config.store_path is None:
            raise ValueError("store_path is not configured")
        store = OperationalStore.connect(Path(self.config.store_path))
        store.initialize()
        return store

    def _store_revision(self) -> str:
        path = str(self.config.store_path or "")
        encoded = f"{path}:{Path(path).stat().st_mtime_ns if path and Path(path).exists() else 0}"
        return f"operational-store:sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"

    def _run_validator(self, include_staged: bool = False) -> dict[str, Any]:
        argv = [str(self.root)]
        if include_staged:
            argv.append("--staged")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = links_validate.main(argv)
        output = buffer.getvalue().strip()
        errors = [
            line.strip()
            for line in output.splitlines()
            if line.strip().startswith("ERROR:")
        ]
        return {
            "ran": True,
            "status": "pass" if code == 0 else "fail",
            "errors": errors,
            "warnings": [],
            "output": output,
        }

    def _source_policy_error(self, source_id: str) -> str:
        entries = self._source_map_payload()
        entry = next((item for item in entries if item["id"] == source_id), None)
        if entry is None:
            return f"source id {source_id!r} is not registered"
        policy = entry["read_policy"]
        if not policy.get("readOnly") or not policy.get("piiExcluded") or policy.get("rawPayloadAccess"):
            return f"source id {source_id!r} has unsafe read policy"
        return ""

    def _require_scope(self, tool: str, scope: str) -> PermissionDecision:
        if scope not in self.config.scopes:
            return PermissionDecision(
                decision="deny",
                tool=tool,
                required_scope=scope,
                reason=f"missing required scope {scope}",
            )
        return PermissionDecision(decision="allow", tool=tool, required_scope=scope, reason="allowed")

    def _module_error(self, arguments: dict[str, Any]) -> str:
        module_id = arguments.get("module_id")
        if module_id != self.config.module_id:
            return f"unknown module_id {module_id!r}"
        return ""

    def _sensitive_findings(self, text: str) -> list[str]:
        findings = []
        for label, pattern in links_validate.PII_PATTERNS:
            if pattern.search(text):
                findings.append(label)
        forbidden_terms = ["raw_payload", "hidden_reasoning", "credential_value", "secret_value"]
        for term in forbidden_terms:
            if term in text:
                findings.append(term)
        return findings

    def _format_proposal(self, proposal_id: str, arguments: dict[str, Any], candidate: str) -> str:
        diff = arguments.get("diff") if isinstance(arguments.get("diff"), dict) else {}
        ttl = arguments.get("ttl") or (date.today() + timedelta(days=30)).isoformat()
        lines = [
            "---",
            f"proposal-id: {proposal_id}",
            f"target: {arguments.get('target', 'new')}",
            "diff:",
            f"  was: {diff.get('was', '(none)')}",
            f"  now: {diff.get('now', 'unknown')}",
            f"basis: {arguments.get('basis', 'unknown')}",
            f"source-locator: {arguments.get('source_locator', arguments.get('source-locator', 'unknown'))}",
            f"confidence: {arguments.get('confidence', 'medium')}",
            f"input: {arguments.get('input', 'agent-inference')}",
            f"originating-skill: {arguments.get('originating_skill', 'reference-runtime')}",
            f"ttl: {ttl}",
            "validator-result: pending",
            "---",
            "",
            f"# {proposal_id}",
            "",
            "Reference runtime staged this proposal. A human must review and promote it.",
            "",
            "```markdown",
            candidate.strip(),
            "```",
            "",
        ]
        return "\n".join(lines)

    def _extract_candidate_ids(self, candidate: str) -> list[str]:
        parsed = links_validate.parse_frontmatter_block(candidate, "<candidate>")
        if parsed and isinstance(parsed.data.get("id"), str):
            return [parsed.data["id"]]
        return []

    def _generated_proposal_id(self) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"prop-runtime-{stamp}"

    def _refusal_result(
        self,
        name: str,
        reason: str,
        uri: str = "",
        path: str = "",
        scope: str = "",
    ) -> dict[str, Any]:
        self._trace(
            actor="agent",
            event_type="refusal",
            name=name,
            scope=scope or ("ontology:read" if name == "resources/read" else "ontology:propose"),
            uri=uri,
            path=path,
            summary=reason,
            result="refused",
        )
        return {
            "status": "refused",
            "refusal_reason": reason,
            "audit_event_id": self._event_id(name),
        }

    def _trace(self, **event: Any) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "actor": event.get("actor", "agent"),
            "event_type": event.get("event_type", "tool_call"),
            "name": event.get("name", "unknown"),
            "scope": event.get("scope", "ontology:read"),
            "summary": event.get("summary", ""),
            "result": event.get("result", "pass"),
        }
        if "path" in event and event["path"]:
            payload["path"] = event["path"]
        if "uri" in event and event["uri"]:
            payload["uri"] = event["uri"]
        if payload["event_type"] not in TRACE_EVENT_TYPES:
            payload["event_type"] = "tool_call"
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def _event_id(self, name: str) -> str:
        normalized = "".join(ch if ch.isalnum() else "-" for ch in name).strip("-")
        return f"evt-{normalized}"

    @staticmethod
    def _propose_input_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "module_id": {"type": "string"},
                "proposal_id": {"type": "string", "pattern": "^prop-[a-z0-9][a-z0-9-]*$"},
                "target": {"type": "string"},
                "diff": {"type": "object"},
                "basis": {"type": "string"},
                "source_id": {"type": "string"},
                "source_locator": {"type": "string"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "input": {
                    "type": "string",
                    "enum": [
                        "owner-decision",
                        "working-system",
                        "regulation",
                        "dashboard",
                        "interview",
                        "mined",
                        "agent-inference",
                    ],
                },
                "originating_skill": {"type": "string"},
                "candidate_card_markdown": {"type": "string"},
                "ttl": {"type": "string"},
            },
            "required": [
                "module_id",
                "target",
                "diff",
                "basis",
                "source_id",
                "source_locator",
                "confidence",
                "input",
                "originating_skill",
                "candidate_card_markdown",
            ],
        }

    @staticmethod
    def _propose_output_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "status": {"type": "string", "enum": ["proposed", "refused"]},
                "proposal_id": {"type": "string"},
                "proposal_path": {"type": "string"},
                "validator": {"type": "object"},
                "affected_ids": {"type": "array", "items": {"type": "string"}},
                "audit_event_id": {"type": "string"},
                "refusal_reason": {"type": "string"},
            },
            "required": ["status", "validator", "affected_ids", "audit_event_id"],
        }

    @staticmethod
    def _validate_input_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "module_id": {"type": "string"},
                "proposal_id": {"type": "string"},
                "proposal_path": {"type": "string"},
            },
            "required": ["module_id"],
        }

    @staticmethod
    def _validate_output_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "status": {"type": "string", "enum": ["pass", "fail", "refused"]},
                "validator_errors": {"type": "array", "items": {"type": "string"}},
                "warnings": {"type": "array", "items": {"type": "string"}},
                "sensitive_content_findings": {"type": "array", "items": {"type": "string"}},
                "affected_ids": {"type": "array", "items": {"type": "string"}},
                "audit_event_id": {"type": "string"},
                "refusal_reason": {"type": "string"},
            },
            "required": ["status", "validator_errors", "warnings", "audit_event_id"],
        }

    @staticmethod
    def _digest_input_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "module_id": {"type": "string"},
                "proposal_ids": {"type": "array", "items": {"type": "string"}},
                "write_digest": {"type": "boolean"},
            },
            "required": ["module_id"],
        }

    @staticmethod
    def _digest_output_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "status": {"type": "string", "enum": ["proposal-ready", "blocked", "refused"]},
                "digest_path": {"type": "string"},
                "digest_text": {"type": "string"},
                "validator_status": {"type": "string", "enum": ["pass", "fail", "not-run"]},
                "validator_errors": {"type": "array", "items": {"type": "string"}},
                "affected_ids": {"type": "array", "items": {"type": "string"}},
                "high_risk_fields": {"type": "array", "items": {"type": "string"}},
                "audit_event_id": {"type": "string"},
                "refusal_reason": {"type": "string"},
            },
            "required": [
                "status",
                "validator_status",
                "validator_errors",
                "affected_ids",
                "high_risk_fields",
                "audit_event_id",
            ],
        }

    @staticmethod
    def _draft_input_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "module_id": {"type": "string"},
                "model_pack": {"type": "object"},
                "source_events": {"type": "array", "items": {"type": "object"}},
                "accepted_context": {"type": "object"},
            },
            "required": ["module_id", "model_pack", "source_events"],
        }

    @staticmethod
    def _draft_output_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "status": {"type": "string", "enum": ["drafted", "partial", "refused", "empty"]},
                "draft": {"type": "object"},
                "audit_event_id": {"type": "string"},
                "refusal_reason": {"type": "string"},
            },
            "required": ["status", "draft", "audit_event_id", "refusal_reason"],
        }

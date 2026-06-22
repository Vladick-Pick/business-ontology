#!/usr/bin/env python3
"""Small in-process reference runtime for the business-ontology harness.

This is not a production resident agent and not a networked MCP server. It is a
dependency-free executable baseline for the contract in AGENT-SPEC.md and
references/mcp-boundary.md: read accepted resources, stage proposals, validate
before review, enforce scope checks, and emit redacted trace events.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_registry  # noqa: E402
import links_validate  # noqa: E402


TRACE_EVENT_TYPES = {
    "resource_read",
    "tool_call",
    "artifact_write",
    "validation",
    "approval",
    "refusal",
    "digest",
}


@dataclass
class RuntimeConfig:
    module_id: str
    ontology_root: Path
    trace_path: Path
    scopes: set[str] = field(default_factory=set)


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
                    "uriTemplate": "ontology://{module_id}/manifest",
                    "name": "registry-manifest",
                    "title": "Registry manifest",
                    "description": "Read the compiled registry manifest.",
                    "mimeType": "application/json",
                },
                {
                    "uriTemplate": "ontology://{module_id}/registry/nodes",
                    "name": "registry-nodes",
                    "title": "Registry nodes",
                    "description": "Read accepted compiled ontology nodes.",
                    "mimeType": "application/json",
                },
                {
                    "uriTemplate": "ontology://{module_id}/registry/edges",
                    "name": "registry-edges",
                    "title": "Registry edges",
                    "description": "Read accepted authored and generated ontology edges.",
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
                    "uri": f"ontology://{self.config.module_id}/manifest",
                    "name": "registry-manifest",
                    "title": "Registry manifest",
                    "description": "Compiled accepted ontology registry manifest.",
                    "mimeType": "application/json",
                },
                {
                    "uri": f"ontology://{self.config.module_id}/sources",
                    "name": "source-map",
                    "title": "Source map",
                    "description": "Registered ontology sources and read policies.",
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

        if path in {"manifest", "registry/nodes", "registry/edges"}:
            registry = self._compile_registry_payload()
            key = {
                "manifest": "manifest",
                "registry/nodes": "nodes",
                "registry/edges": "edges",
            }[path]
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
                        "text": json.dumps(registry[key], indent=2, sort_keys=True),
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
        proposal_path = self.root / "staged" / f"{proposal_id}.md"
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_text = self._format_proposal(proposal_id, arguments, candidate)
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
            manifest, nodes, edges = build_registry.compile_registry(self.root, Path(tmp))
        return {"manifest": manifest, "nodes": nodes, "edges": edges}

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

    def _refusal_result(self, name: str, reason: str, uri: str = "", path: str = "") -> dict[str, Any]:
        self._trace(
            actor="agent",
            event_type="refusal",
            name=name,
            scope="ontology:read" if name == "resources/read" else "ontology:propose",
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
                "proposal_id": {"type": "string"},
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

# MCP boundary: read resources and gated proposal tools

This is a boundary spec, not a production MCP server. It describes how a future
MCP server should expose the business ontology without weakening the repository
trust model. The repository also ships `runtime/reference_runtime.py`, an
in-process reference harness that uses these resource/tool shapes for local tests
and captured traces; it is not OAuth, deployment, or a network listener.

The rule is simple: accepted ontology is exposed as read-only resources; every
write-like action is an approval-gated proposal. There is no direct mutation of
accepted cards, no source writeback, no schema mutation, and no auto-promotion.

## Protocol grounding

MCP resources are contextual data identified by URIs. A client discovers
resources with `resources/list`, discovers parameterized resources with
`resources/templates/list`, and reads contents with `resources/read`. A future
server should expose registry JSON and selected accepted card/source content as
resources, not as mutation tools.

MCP tools are discovered with `tools/list` and executed with `tools/call`. Tool
definitions expose `name`, `description`, `inputSchema`, and, when structured
results are useful, `outputSchema`. The schemas below are documentation-grade
contracts for a future server's `tools/list` response and are mirrored by the
local reference runtime. They are not, by themselves, production deployment code.

If the server uses OAuth, clients request tokens for the canonical MCP server
URI using the OAuth resource parameter and request only the needed scopes. Scope
design here is intentionally split between read, proposal, and admin-review
capabilities:

- `ontology:read` - read accepted ontology resources.
- `ontology:propose` - call tools that create or validate staged proposals.
- `ontology:admin-review` - prepare promotion review artifacts; still no
  auto-promotion.

Auth is not implemented in this repository. These names are a contract for
future implementation, not a runtime guarantee today.

## Resource contracts

Use `module_id` as the ontology/module namespace from deployment config. Resource
templates should be discoverable through `resources/templates/list`; concrete
resources may also appear in `resources/list` when the server has a bounded
module catalog.

All resources below require `ontology:read`, are read by `resources/read`, and
serve accepted ontology state only. Staged proposals are excluded unless the URI
explicitly says review/staged and requires `ontology:admin-review`.

| URI template | Name | mimeType | Source | Staged included | Stale/failure behavior |
|---|---|---|---|---|---|
| `ontology://{module_id}/manifest` | `registry-manifest` | `application/json` | `registry/manifest.json` emitted by `scripts/build_registry.py`. | No | If validation fails, return the last known good manifest with `_meta.stale: true` and validator errors, or refuse the fresh read with a validation error. |
| `ontology://{module_id}/registry/nodes` | `registry-nodes` | `application/json` | Accepted compiled nodes from `registry/nodes.json`. | No | Same stale/refusal behavior as manifest; never serve hand-edited registry JSON as fresh. |
| `ontology://{module_id}/registry/edges` | `registry-edges` | `application/json` | Authored business edges plus compiler-generated interface edges from `registry/edges.json`. | No | Same stale/refusal behavior as manifest. |
| `ontology://{module_id}/cards/{id}` | `accepted-card` | `text/markdown` | Accepted card matching `id`, including frontmatter and body. | No | Unknown `id` returns not found; failed validation should not invent a card. |
| `ontology://{module_id}/open-questions` | `open-questions` | `application/json` | `08-drift-and-open-questions.md` normalized by the registry compiler, or `registry/open_questions.json` when present. | No | If normalization fails, return the source file with `_meta.partial: true` or refuse with parser errors. |
| `ontology://{module_id}/sources` | `source-map` | `application/json` | Parsed `02-source-map.md` source ids, trust floors, owners, access modes, read policies, and locators. | No | Credential values are always omitted; unsafe source policies are surfaced as validation errors. |

Resource objects returned from `resources/list` should use the MCP resource
fields `uri`, `name`, optional `title`, optional `description`, and `mimeType`.
Parameterized entries returned from `resources/templates/list` should use
`uriTemplate`, `name`, optional `title`, optional `description`, and `mimeType`.

Example resource template entry:

```json
{
  "uriTemplate": "ontology://{module_id}/cards/{id}",
  "name": "accepted-card",
  "title": "Accepted ontology card",
  "description": "Read one accepted business-ontology card by stable id.",
  "mimeType": "text/markdown"
}
```

## Tool contracts

Tools may prepare proposals and review packets. They must not mutate the
accepted model directly. Every successful tool call emits a trace event shaped
like the `events.jsonl` schema in `evals/README.md`; refusals emit a `refusal`
event with the same redaction rules.

### Shared refusal cases

Every tool must refuse when any of these are true:

- unknown `module_id`;
- missing required scope;
- source id is unregistered or its read policy is unsafe
  (`readOnly=false`, `piiExcluded=false`, or `rawPayloadAccess=true`);
- input, candidate card, diff, or output contains PII, a secret, a credential
  value, hidden reasoning, or raw source payload;
- request attempts to mutate accepted cards, registry JSON, `AGENTS.md`,
  `AGENT-SPEC.md`, `references/`, source systems, or credentials;
- request attempts to mutate relation list, status list, frontmatter schema, or
  `attrs` contract;
- request asks the tool to promote, merge, commit, push to accepted, or bypass
  human review.

### `propose_change`

Creates a staged proposal using the single proposal shape documented in
`staged/README.md` and `agent-skills/propose-change/SKILL.md`.

Required scope: `ontology:propose`.

Allowed side effects:

- create or update files only under `staged/`;
- run validation against promoted plus staged cards;
- emit one redacted trace event.

Forbidden side effects:

- direct accepted-card mutation;
- registry JSON hand editing;
- source writeback;
- credential read/export;
- self-promotion to `accepted` or `implemented`.

`inputSchema`:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "module_id": {"type": "string"},
    "proposal_id": {"type": "string", "pattern": "^prop-[a-z0-9][a-z0-9-]*$"},
    "generate_proposal_id": {"type": "boolean", "default": true},
    "target": {"type": "string", "description": "Existing card id or 'new'."},
    "diff": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "was": {"type": "string"},
        "now": {"type": "string"}
      },
      "required": ["was", "now"]
    },
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
        "agent-inference"
      ]
    },
    "originating_skill": {"type": "string"},
    "candidate_card_markdown": {"type": "string"},
    "dry_run": {"type": "boolean", "default": false}
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
    "candidate_card_markdown"
  ]
}
```

`outputSchema`:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "status": {"type": "string", "enum": ["proposed", "refused"]},
    "proposal_id": {"type": "string"},
    "proposal_path": {"type": "string"},
    "validator": {
      "type": "object",
      "properties": {
        "ran": {"type": "boolean"},
        "status": {"type": "string", "enum": ["pass", "fail", "not-run"]},
        "errors": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}}
      },
      "required": ["ran", "status", "errors", "warnings"]
    },
    "affected_ids": {"type": "array", "items": {"type": "string"}},
    "audit_event_id": {"type": "string"},
    "refusal_reason": {"type": "string"}
  },
  "required": ["status", "validator", "affected_ids", "audit_event_id"]
}
```

Audit event:

```json
{
  "actor": "agent",
  "event_type": "tool_call",
  "name": "propose_change",
  "scope": "ontology:propose",
  "path": "staged/<proposal-id>.md",
  "summary": "Prepared staged proposal and validator result.",
  "result": "proposed"
}
```

Timeout/result-size guidance: finish within the deployment's normal tool-call
timeout; cap returned markdown excerpts to the staged proposal path, affected
ids, and validation output. Do not echo full raw source payloads.

### `validate_proposal`

Validates a staged proposal without promoting it.

Required scope: `ontology:propose`.

Allowed side effects:

- read accepted cards and staged proposals;
- run `scripts/links_validate.py <ontology-root> --staged`;
- emit one redacted trace event.

Forbidden side effects:

- editing cards or proposals;
- creating repair files;
- promotion, commit, merge, or registry JSON writes.

`inputSchema`:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "module_id": {"type": "string"},
    "proposal_id": {"type": "string"},
    "proposal_path": {"type": "string"}
  },
  "required": ["module_id"]
}
```

At least one of `proposal_id` or `proposal_path` must be supplied by the
implementation.

`outputSchema`:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "status": {"type": "string", "enum": ["pass", "fail", "refused"]},
    "validator_errors": {"type": "array", "items": {"type": "string"}},
    "warnings": {"type": "array", "items": {"type": "string"}},
    "sensitive_content_findings": {"type": "array", "items": {"type": "string"}},
    "affected_ids": {"type": "array", "items": {"type": "string"}},
    "audit_event_id": {"type": "string"},
    "refusal_reason": {"type": "string"}
  },
  "required": [
    "status",
    "validator_errors",
    "warnings",
    "sensitive_content_findings",
    "audit_event_id"
  ]
}
```

Audit event:

```json
{
  "actor": "agent",
  "event_type": "validation",
  "name": "links_validate",
  "scope": "ontology:read",
  "path": "staged/<proposal-id>.md",
  "summary": "Validated staged proposal without promotion.",
  "result": "pass"
}
```

Timeout/result-size guidance: return bounded validator output; if validator
output is large, include counts plus first errors and link the staged proposal
path.

### `prepare_promote_digest`

Builds a human review packet for staged proposals.

Required scope: `ontology:admin-review`.

Allowed side effects:

- read accepted cards and staged proposals;
- run validation before producing a review-ready digest;
- write a digest artifact under `staged/` if the deployment uses file-backed
  review packets;
- emit one redacted trace event.

Forbidden side effects:

- promotion, commit, merge, push, or accepted-card mutation;
- status flipping to `accepted` or `implemented`;
- hiding high-risk kinetic fields;
- source writeback or credential read/export.

`inputSchema`:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "module_id": {"type": "string"},
    "proposal_ids": {"type": "array", "items": {"type": "string"}},
    "batch_selector": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "since": {"type": "string"},
        "include_all_staged": {"type": "boolean", "default": false},
        "risk_minimum": {"type": "string", "enum": ["low", "medium", "high"]}
      }
    },
    "group_by": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["risk", "originating_skill", "source_id", "owner", "target_type"]
      }
    },
    "write_digest": {"type": "boolean", "default": true}
  },
  "required": ["module_id"]
}
```

`outputSchema`:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "status": {"type": "string", "enum": ["proposal-ready", "blocked", "refused"]},
    "digest_path": {"type": "string"},
    "digest_text": {"type": "string"},
    "validator_status": {"type": "string", "enum": ["pass", "fail", "not-run"]},
    "validator_errors": {"type": "array", "items": {"type": "string"}},
    "affected_ids": {"type": "array", "items": {"type": "string"}},
    "high_risk_fields": {"type": "array", "items": {"type": "string"}},
    "audit_event_id": {"type": "string"},
    "refusal_reason": {"type": "string"}
  },
  "required": [
    "status",
    "validator_status",
    "validator_errors",
    "affected_ids",
    "high_risk_fields",
    "audit_event_id"
  ]
}
```

Audit event:

```json
{
  "actor": "agent",
  "event_type": "tool_call",
  "name": "prepare_promote_digest",
  "scope": "ontology:admin-review",
  "path": "staged/digest-<date>.md",
  "summary": "Prepared human review digest after validation; no promotion.",
  "result": "proposal-ready"
}
```

Timeout/result-size guidance: group and summarize proposals; do not return large
raw card bodies unless the client explicitly reads the staged proposal files.
Digest output must stay redacted and should name affected ids, risk groups, and
validator status.

## Explicitly out of scope

These capabilities must not exist in this boundary:

- `promote_all`;
- direct accepted-model mutation;
- source writeback;
- raw payload export;
- credential value read/export;
- relation-list, status-list, or frontmatter schema mutation;
- registry JSON hand-editing.

If a future implementation needs any of these, it is a new design decision and a
separate security review. It is not an extension of this boundary.

## Runtime expectations

- Registry resources are served from compiler output produced by
  `scripts/build_registry.py`, not from hand-authored JSON.
- The compiler must run validation before writing registry output. If validation
  fails, resources should either expose the last known good registry with a
  stale marker, or refuse to serve a fresh registry with the validator errors.
- Staged proposals are not truth. They can be reviewed, but read-only ontology
  resources answer from accepted cards and compiled accepted registry only.
- Tool responses must not include secrets, PII, raw source payloads, credential
  values, or hidden reasoning.
- Tool calls must emit redacted audit events compatible with the trace schema in
  `evals/README.md`.

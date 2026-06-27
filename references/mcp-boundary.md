# MCP boundary: read resources and gated proposal tools

This is a boundary spec, not a production MCP server. It describes how a future
MCP server should expose the business ontology without weakening the repository
trust model. The repository also ships `runtime/reference_runtime.py`, an
in-process reference harness that uses these resource/tool shapes for local tests
and captured traces; it is not OAuth, deployment, or a network listener.

GBrain may be used as an optional backing store, index, search layer, sync
target, and MCP access implementation. It is not the canonical model store
defined in [canonical-model-store.md](canonical-model-store.md), not the
semantic compiler, and not the approval manager. The storage-specific boundary
is defined in [gbrain-integration.md](gbrain-integration.md).

The rule is simple: accepted model projections are exposed as read-only
resources; every write-like action is an approval-gated proposal. There is no
direct mutation of the canonical model store, accepted cards, source systems,
schemas, or auto-promotion.

## Protocol grounding

MCP resources are contextual data identified by URIs. A client discovers
resources with `resources/list`, discovers parameterized resources with
`resources/templates/list`, and reads contents with `resources/read`. A future
server should expose registry JSON and selected accepted card/source content as
resources, not as mutation tools.

MCP tools are discovered with `tools/list` and executed with `tools/call`. Tool
definitions expose `name`, `description`, `inputSchema`, and, when structured
results are useful, `outputSchema`. The proposal/review schemas below are
documentation-grade contracts for a future server's `tools/list` response and
the core proposal tools are mirrored by the local reference runtime. Future
GBrain-backed package listing and review tools remain documentation-grade until
implemented explicitly. They are not, by themselves, production deployment code.

If the server uses OAuth, clients request tokens for the canonical MCP server
URI using the OAuth resource parameter and request only the needed scopes. Scope
design here is intentionally split between read, proposal, and admin-review
capabilities:

- `ontology:read` - read accepted model resources.
- `ontology:propose` - call tools that create or validate staged proposals.
- `ontology:admin-review` - read review resources and prepare review artifacts;
  still no auto-promotion.

Auth is not implemented in this repository. These names are a contract for
future implementation, not a runtime guarantee today.

## Resource contracts

Use `module_id` as the ontology/module namespace from deployment config. Resource
templates should be discoverable through `resources/templates/list`; concrete
resources may also appear in `resources/list` when the server has a bounded
module catalog.

The public MCP URI space should stay storage-neutral even when GBrain backs the
server. Callers read `ontology://...` resources; the implementation may sync
from or cache into `gbrain://...` namespaces behind that boundary.

Accepted-state resources below require `ontology:read`, are read by
`resources/read`, and serve accepted model projections only. Staged proposals
and model-change packages are excluded from accepted-state resources. The target
accepted-state contract is the canonical model store in
[canonical-model-store.md](canonical-model-store.md). Until accepted-state
storage is wired, these projections come from the accepted Markdown/Git export
and compiled registry.

| URI template | Name | mimeType | Source | Staged included | Stale/failure behavior |
|---|---|---|---|---|---|
| `ontology://{module_id}/model/current` | `current-model` | `application/json` | Canonical model store projection with revision metadata; until full accepted-state storage exists, the compiled accepted Markdown/Git export. | No | If validation fails, return the last known good projection with `_meta.stale: true` and validator errors, or refuse the fresh read with a validation error. |
| `ontology://{module_id}/model/entities` | `model-entities` | `application/json` | Accepted entity/node projections from the canonical store or compiled registry. | No | Same stale/refusal behavior as current model; never serve hand-edited registry JSON as fresh. |
| `ontology://{module_id}/model/relations` | `model-relations` | `application/json` | Accepted relation projections from the canonical store or compiled registry. | No | Same stale/refusal behavior as current model. |
| `ontology://{module_id}/model/decisions` | `model-decisions` | `application/json` | Accepted decision projections, including status and supersession metadata when present. | No | Same stale/refusal behavior as current model. |
| `ontology://{module_id}/model/drift` | `model-drift` | `application/json` | Accepted drift/open-question projection normalized from the canonical store, registry output, or `08-drift-and-open-questions.md`. | No | If normalization fails, return `_meta.partial: true` or refuse with parser errors. |
| `ontology://{module_id}/cards/{id}` | `accepted-card` | `text/markdown` | Accepted card matching `id`, including frontmatter and body. | No | Unknown `id` returns not found; failed validation should not invent a card. |
| `ontology://{module_id}/sources` | `source-map` | `application/json` | Parsed `02-source-map.md` source ids, trust floors, owners, access modes, read policies, and locators. | No | Credential values are always omitted; unsafe source policies are surfaced as validation errors. |

Review resources are separate from accepted model resources. They are
read-only resources, but they require `ontology:admin-review` because they expose
pending review state rather than accepted truth.

| URI template | Name | mimeType | Source | Staged included | Stale/failure behavior |
|---|---|---|---|---|---|
| `ontology://{module_id}/review/packages/{package_id}` | `review-package` | `application/json` | Reviewable package emitted by the semantic compiler contract in `model-change-package.md`, optionally indexed in GBrain. | Review artifact only | Unknown `package_id` returns not found; packages compiled against stale ontology revisions must be marked stale or refused until rebuilt. |
| `ontology://{module_id}/review/packages` | `pending-review-packages` | `application/json` | Bounded list of package summaries from the review queue or GBrain package index. "Pending" means queue membership, not a package status. | Review artifact only | Return bounded summaries, not raw source payloads; unsafe packages must be refused or quarantined. |
| `ontology://{module_id}/review/digests/{digest_id}` | `review-digest` | `text/markdown` | Redacted weekly or review digest prepared for human attention. | Review artifact only | Stale digests must show their source revision/package ids; do not present them as current accepted state. |
| `ontology://{module_id}/sources/events/{event_id}` | `source-event` | `application/json` | Redacted source-event metadata, hashes, connector id, source kind, and evidence locators. | Review-scoped evidence only | Raw payloads, private messages, transcripts, secrets, and credential values are omitted; unsafe events are refused or quarantined. |

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

Future GBrain-backed tools may list or prepare model-change package review
packets. They are still approval-gated MCP tools, not mutation privileges over
the canonical model store or accepted export.

### Shared refusal cases

Every tool must refuse when any of these are true:

- unknown `module_id`;
- missing required scope;
- source id is unregistered or its read policy is unsafe
  (`readOnly=false`, `piiExcluded=false`, or `rawPayloadAccess=true`);
- input, candidate card, diff, or output contains PII, a secret, a credential
  value, hidden reasoning, or raw source payload;
- request attempts to mutate accepted cards, registry JSON, `AGENTS.md`,
  `specs/BUSINESS-ONTOLOGY-RESIDENT.md`, `references/`, source systems, or credentials;
- request attempts to mutate relation list, status list, frontmatter schema, or
  `attrs` contract;
- request asks the tool to promote, merge, commit, push to accepted, or bypass
  human review.

### `propose_change`

Creates a staged proposal using the single proposal shape documented in
`staged/README.md` and `skills/propose-change/SKILL.md`.

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

### Optional package review tools

These tools are documentation-grade contracts for a future GBrain-backed MCP
server. They are not implemented by `runtime/reference_runtime.py` yet.

#### `list_pending_model_packages`

Lists model-change package summaries for human review. "Pending" in the tool
name means membership in a review queue, not a new package lifecycle status.

Required scope: `ontology:admin-review`.

Allowed side effects:

- read package metadata from the review queue or GBrain package index;
- emit one redacted trace event.

Forbidden side effects:

- accepted-card mutation;
- staged proposal creation;
- package approval or rejection;
- promotion, commit, merge, or push;
- raw source payload export.

`inputSchema`:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "module_id": {"type": "string"},
    "package_review_action": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["human-review", "needs-owner", "no-review-needed"]
      }
    },
    "risk_minimum": {"type": "string", "enum": ["low", "medium", "high"]},
    "limit": {"type": "integer", "minimum": 1, "maximum": 100}
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
    "status": {"type": "string", "enum": ["ok", "refused"]},
    "packages": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "package_id": {"type": "string"},
          "summary": {"type": "string"},
          "risk": {"type": "string", "enum": ["low", "medium", "high"]},
          "review_action": {
            "type": "string",
            "enum": ["human-review", "needs-owner", "no-review-needed"]
          },
          "affected_ids": {"type": "array", "items": {"type": "string"}},
          "ontology_revision": {"type": "string"},
          "stale": {"type": "boolean"}
        },
        "required": [
          "package_id",
          "summary",
          "risk",
          "review_action",
          "affected_ids",
          "ontology_revision",
          "stale"
        ]
      }
    },
    "audit_event_id": {"type": "string"},
    "refusal_reason": {"type": "string"}
  },
  "required": ["status", "packages", "audit_event_id"]
}
```

Timeout/result-size guidance: default to a small deployment-defined limit, cap
`limit` at 100, and return summaries plus ids only. Large package bodies,
candidate cards, raw source payloads, and long evidence excerpts should be read
through specific review resources or refused when unsafe.

#### `prepare_review_package`

Builds a bounded human review packet from one or more model-change packages.
When the packet is represented as structured JSON, it should follow
`schemas/review-package.schema.json` and the lifecycle in
`references/review-ux.md`.

Required scope: `ontology:admin-review`.

Allowed side effects:

- read package metadata, accepted context, and redacted evidence locators;
- write a review packet under the deployment's review/staged area if configured;
- emit one redacted trace event.

Forbidden side effects:

- accepting or rejecting the package;
- creating a staged proposal without explicit review decision;
- promotion, commit, merge, or push;
- accepted-card mutation;
- raw source payload export.

`inputSchema`:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "module_id": {"type": "string"},
    "package_ids": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 1
    },
    "write_packet": {"type": "boolean", "default": true}
  },
  "required": ["module_id", "package_ids"]
}
```

`outputSchema`:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "status": {"type": "string", "enum": ["review-ready", "blocked", "refused"]},
    "packet_path": {"type": "string"},
    "packet_text": {"type": "string"},
    "review_package": {"$ref": "schemas/review-package.schema.json"},
    "package_ids": {"type": "array", "items": {"type": "string"}},
    "affected_ids": {"type": "array", "items": {"type": "string"}},
    "stale_package_ids": {"type": "array", "items": {"type": "string"}},
    "audit_event_id": {"type": "string"},
    "refusal_reason": {"type": "string"}
  },
  "required": [
    "status",
    "package_ids",
    "affected_ids",
    "stale_package_ids",
    "audit_event_id"
  ],
  "allOf": [
    {
      "if": {
        "properties": {"status": {"const": "review-ready"}},
        "required": ["status"]
      },
      "then": {
        "anyOf": [
          {"required": ["review_package"]},
          {"required": ["packet_path"]}
        ]
      }
    }
  ]
}
```

Timeout/result-size guidance: keep the returned packet bounded to the package
ids, affected ids, stale-package markers, review action, and short redacted
evidence excerpts. If a packet would exceed the result limit, write it as a
review artifact and return `packet_path`; do not stream raw source payloads or
full package archives into the tool result.

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
- GBrain, when present, is a derived backing implementation for search, sync,
  storage, and access. It must preserve source revisions and stale markers
  rather than becoming a second truth store.
- The compiler must run validation before writing registry output. If validation
  fails, resources should either expose the last known good registry with a
  stale marker, or refuse to serve a fresh registry with the validator errors.
- Staged proposals are not truth. They can be reviewed, but read-only ontology
  resources answer from canonical model projections. Until accepted-state
  storage is wired, they answer from accepted cards and the compiled accepted
  registry.
- Model-change packages are review artifacts. They can be listed and prepared
  for review, but they must not be included in accepted answers as if they were
  true.
- Tool responses must not include secrets, PII, raw source payloads, credential
  values, or hidden reasoning.
- Tool calls must emit redacted audit events compatible with the trace schema in
  `evals/README.md`.

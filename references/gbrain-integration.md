# GBrain integration

This reference defines where GBrain fits in the resident business analyst
architecture. It is a boundary contract, not an implementation guide for a
specific GBrain API.

GBrain is storage/index/search/sync/access infrastructure. It is not the
canonical model store defined in
[canonical-model-store.md](canonical-model-store.md), not the semantic compiler,
and not the human approval gate.

## Role

GBrain makes accepted model projections and the review queue easier for agents
to discover, search, traverse, and reuse through MCP or a comparable access
layer.

Its useful jobs are:

- store bounded projections of the accepted model, source-event metadata,
  model-change packages, registry output, and digests;
- index ids, links, evidence locators, package review actions, owners, and review
  routing fields;
- serve read-only resources to agents that need context;
- sync derived views from the canonical model store, Markdown/Git export, and
  review artifacts;
- expose query access without requiring every agent to parse the repository
  directly.

## Non-role

GBrain must not decide what the company model says.

It must not:

- become the canonical model store;
- compile raw source material into model-change packages;
- mine facts directly into accepted cards;
- approve, reject, or promote proposals;
- mutate accepted model state, accepted exports, registry JSON, schemas, source
  systems, credentials,
  or connector configuration;
- store raw transcripts, private messages, secrets, credentials, PII, or hidden
  reasoning.

## Canonical truth boundary

The canonical boundary is:

```text
canonical model store + human decision log + validation = operational truth
```

Markdown/Git is the readable export, review surface, audit trail, backup, and
portability layer. The current repository implementation still uses accepted
cards in Git as that export and review surface until full accepted-state storage
is wired.

GBrain can cache, index, and serve projections of the accepted model. Those
projections must carry enough revision metadata to prove where they came from,
such as a canonical store revision, git revision, registry digest, package id,
source-event hash, or deployment snapshot id.

If a GBrain projection disagrees with the canonical model store, the store wins.
Until accepted-state storage is wired, the accepted Markdown/Git export remains
the implemented review source. In either case, the GBrain item should be marked
stale or rebuilt; it should not overwrite the accepted layer.

## Namespaces

Use explicit namespaces so agents can tell accepted truth, review artifacts, and
source evidence apart.

Suggested URI families:

```text
gbrain://{module_id}/ontology/accepted
gbrain://{module_id}/ontology/staged
gbrain://{module_id}/sources/map
gbrain://{module_id}/sources/events
gbrain://{module_id}/model-change-packages
gbrain://{module_id}/registry
gbrain://{module_id}/digests
```

The namespace is not an authority grant. A resource under
`gbrain://{module_id}/ontology/staged` or
`gbrain://{module_id}/model-change-packages` is review material, not accepted
truth.

## MCP resources

A future MCP server may use GBrain as the backing store for read resources. The
public resource boundary should still use the ontology-oriented MCP names from
`mcp-boundary.md` so callers do not depend on one storage implementation.

Recommended mapping:

| MCP resource | Backing GBrain namespace | Meaning |
|---|---|---|
| `ontology://{module_id}/model/current` | `gbrain://{module_id}/ontology/accepted` and `gbrain://{module_id}/registry` | Current accepted model projection with revision and stale metadata. |
| `ontology://{module_id}/model/entities` | `gbrain://{module_id}/registry` | Accepted entity/node projections. |
| `ontology://{module_id}/model/relations` | `gbrain://{module_id}/registry` | Accepted authored and generated relation projections. |
| `ontology://{module_id}/model/decisions` | `gbrain://{module_id}/ontology/accepted` | Accepted decision projections, including supersession metadata when present. |
| `ontology://{module_id}/model/drift` | `gbrain://{module_id}/digests` and review metadata | Accepted drift and open-question projection; pending packages stay outside accepted truth. |
| `ontology://{module_id}/cards/{id}` | `gbrain://{module_id}/ontology/accepted` | One accepted card projection. |
| `ontology://{module_id}/sources` | `gbrain://{module_id}/sources/map` | Parsed source map only: registered source ids, trust floors, owners, access modes, read policies, and locators. |
| `ontology://{module_id}/review/packages/{package_id}` | `gbrain://{module_id}/model-change-packages` | One reviewable package, requiring review scope. |
| `ontology://{module_id}/review/packages` | `gbrain://{module_id}/model-change-packages` | Bounded review-queue package summaries only; queue membership is not a package status and raw package bodies stay out of list results. |
| `ontology://{module_id}/review/digests/{digest_id}` | `gbrain://{module_id}/digests` | Review or weekly digest artifact. |
| `ontology://{module_id}/sources/events/{event_id}` | `gbrain://{module_id}/sources/events` | Redacted source-event metadata and evidence locators for review-scoped reads; raw payloads are not exposed. |

Accepted resources require read scope and must answer from canonical model
store projections or validated registry projections. Until accepted-state
storage is wired, they answer from the accepted Markdown/Git export. Review
resources require review scope and must not be mixed into accepted answers
unless the caller explicitly asks about pending review state.

## MCP tools

GBrain-backed tools should prepare or retrieve review work. They should not
write accepted truth.

Recommended future tool names:

| Tool | Scope | Side effect |
|---|---|---|
| `list_pending_model_packages` | `ontology:admin-review` | None; returns bounded review-queue package summaries. |
| `prepare_review_package` | `ontology:admin-review` | May write a redacted review packet under the review/staged area. |
| `propose_change` | `ontology:propose` | May create or update staged proposal files only. |
| `validate_proposal` | `ontology:propose` | Runs validation; no edits. |
| `prepare_promote_digest` | `ontology:admin-review` | May write a digest; no promotion. |

Every write-like tool remains approval-gated. No GBrain tool may promote a
package, mark a card accepted, push a commit, change schemas, or write back to a
source system.

## Sync and indexing

GBrain sync should be derived and reproducible:

1. Validate accepted model state.
2. Compile the registry from accepted model projections.
3. Import accepted projections and registry output with revision metadata.
4. Import source-event metadata and model-change packages without raw payloads.
5. Mark stale projections when their source revision no longer matches.
6. Refuse or quarantine unsafe items that contain PII, secrets, raw source
   payloads, or hidden reasoning.

The sync layer should be idempotent by source-event hash, package id, registry
digest, and ontology revision. Re-running sync for the same revision should not
create duplicate review work.

Implementation is intentionally deferred in this repository. The current repo
defines contracts, schemas, deterministic scripts, and an in-process reference
runtime; it does not ship a production GBrain server, networked MCP adapter, or
OAuth deployment.

## Approval and review

GBrain can make review queues visible, but the approval manager remains a
separate boundary:

- the compiler emits model-change packages;
- GBrain indexes and exposes those packages;
- the approval manager routes human review;
- approved review may prepare staged proposals;
- accepted truth changes only through the final human review gate and the
  deterministic exact-payload controller; Markdown/Git is a derived export,
  not an additional approval mechanism.

This keeps storage, extraction, access, and approval separable. If one layer
fails, it should not be able to silently rewrite the company model.

## Failure modes

Treat these as blocker-level design failures:

- GBrain becomes the source of truth instead of the canonical model store.
- A GBrain sync job rewrites cards, schemas, registry contracts, or source
  systems.
- A package appears in accepted model answers as if it were already true.
- A generative review or GBrain tool promotes, commits, pushes, or marks cards
  accepted instead of handing the saved decision to the deterministic
  controller.
- Raw transcripts, private messages, secrets, credentials, PII, or hidden
  reasoning are indexed.
- GBrain search returns stale projections without a stale marker or revision
  metadata.
- Agents depend on GBrain-specific namespaces when the public MCP boundary is
  supposed to be storage-neutral.

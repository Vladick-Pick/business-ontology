# Model change package

A model change package is the compiler's review artifact. It says what source
events appear to imply, which accepted model ids may be affected, what evidence
supports the claim, and which human review action is needed.

It is not accepted truth and it is not a staged proposal. It sits before
`propose_change`: source events feed a compiler, the compiler emits a package,
review decides what to do, and only then can a staged proposal be prepared.

## Purpose

The semantic compiler should not write ontology cards directly. A package gives
humans and downstream tools a bounded artifact to inspect before any staged
proposal exists.

The package exists to:

- separate extraction from approval;
- preserve source evidence without storing raw payloads;
- make drift, conflict, and no-op decisions explicit;
- route high-risk changes to the right owner;
- keep accepted model mutation impossible from compiler output alone.

## Lifecycle

1. One or more redacted source events arrive.
2. A compiler reads the source events, accepted model context, and model pack.
3. The compiler emits a model change package.
4. A review step accepts, rejects, asks for more information, or records no-op.
5. Approved review may prepare a staged proposal.
6. If the reviewed package carries `acceptedItem` or `acceptedWorkflow`
   payloads, the runtime may apply them to the SQLite accepted-state subset only
   after a saved human decision marks the package approved.
7. Human review remains the only path to accepted truth. In the current
   repository implementation, a human commit still promotes the Markdown/Git
   export.

The package can be indexed by GBrain or exposed through MCP for review, but it
must not be treated as canonical model state.

## Package fields

Top-level fields:

| Field | Meaning |
|---|---|
| `packageId` | Stable package id, shaped like `mcpkg-<slug>`. |
| `moduleId` | Module this package applies to. |
| `modelPackId` | Model pack used to interpret the source event. |
| `modelPackVersion` | Version of the model pack used during compilation. |
| `ontologyRevision` | Accepted model, export, or registry revision compiled against. |
| `compiler` | Compiler identity and mode that produced the package. |
| `sourceEventIds` | Source event ids compiled into this package. |
| `generatedAt` | Timestamp for package generation. |
| `summary` | Short redacted human-readable package summary. |
| `changes` | Candidate changes or no-op entries. |
| `review` | Package-level review routing and required action. |
| `safety` | Redaction and mutation boundary flags. |

`ontologyRevision` may be a canonical model store revision, Git revision,
registry digest, GBrain revision, or deployment-specific model snapshot id. It
exists so review can detect packages compiled against stale accepted context.
The target store contract is defined in
[canonical-model-store.md](canonical-model-store.md).

`compiler` names the compiler, version, and mode. Synthetic fixtures may use a
fixture compiler identity. Production packages should make the producer
auditable without exposing hidden reasoning or raw prompts.

## Change kinds

Allowed change kinds:

```text
new-object
new-definition
new-decision
new-agreement
drift
conflict
source-of-truth-change
dashboard-metric-concern
stale-area
no-op
```

`no-op` is a valid result when new source material does not warrant human
attention. It lets the runtime record that material was inspected without
inventing drift or forcing a review queue item.

## Evidence and affected model

Each change carries:

- `changeId`;
- `kind`;
- `confidence`;
- `risk`;
- `affectedIds`;
- `evidence`;
- `proposedAction`;
- optional `candidateCard`;
- optional `drift`.
- optional `acceptedItem` or `acceptedWorkflow`, but only as a post-review
  accepted-state payload that still requires a saved human decision before it
  can be applied.

`affectedIds` references accepted model ids or `unknown` when the compiler
cannot identify a specific object. Evidence references source events and
locators. Evidence excerpts must stay short and redacted.

If a change includes `candidateCard`, that object is still candidate material.
It must not mark a card as `accepted`, must use only the closed relation list,
must link only to known accepted model ids, and must not contain raw payloads,
secrets, credential values, or PII. Review may later render it into a staged
proposal, but package output does not carry unchecked markdown.

Candidate card status must follow the card contract: decision candidates use
`proposed`; other card types use `candidate`, `hypothesis`, `conflict`, or
`unknown`.

## Accepted-state payloads

`acceptedItem` and `acceptedWorkflow` are review-result payloads, not compiler
shortcuts around approval. They are used when the reviewer has already approved
the concrete accepted-state record that should be written to the operational
store.

`acceptedItem` wraps one canonical accepted item plus optional linked
definitions, attributes, criteria, and examples/non-examples.

`acceptedWorkflow` wraps one accepted workflow plus optional linked
participants, steps, transitions, exceptions, and workflow metrics.

Runtime application is intentionally narrow:

```text
record_model_change_package(package)
record_human_decision(... approved ...)
apply_approved_model_change(package)
```

`apply_approved_model_change` refuses unapproved packages. For workflows, it
also checks that referenced states, roles, inputs, outputs, transition
authorities, and metrics resolve to accepted item ids already in the store or
introduced by `acceptedItem` changes in the same package.

This keeps source-event mining, review packaging, human approval, and accepted
state mutation as separate steps.

## Review actions

Review action names describe what a human or approval manager should do next.
They are not commands that mutate accepted truth.

Allowed change-level actions:

- `prepare-staged-proposal`;
- `open-drift-review`;
- `open-conflict-review`;
- `review-source-of-truth`;
- `review-dashboard-metric`;
- `needs-info`;
- `record-no-op`.

Allowed package-level actions:

- `human-review`;
- `needs-owner`;
- `no-review-needed`.

High-risk packages should route to the owner named by the model pack. Unknown
owners should produce `needs-owner`, not a best-effort approval.

## Conversion to staged proposals

A model change package may feed `propose_change` only after review determines
that a staged proposal should be prepared. The staged proposal remains the
agent's outbox and must still pass `links_validate.py --staged`.

The package does not replace `staged/README.md`, does not edit accepted cards,
and does not promote anything. It is upstream evidence and proposed action, not
truth.

`runtime/model_compiler.py` is a deterministic reference compiler for this
contract. It proves the package shape with simple synthetic rules; it is not the
production semantic compiler, not an LLM pipeline, and not a source connector.

## Privacy and refusal rules

Every package must satisfy:

- `safety.noPii` is `true`;
- `safety.noSecrets` is `true`;
- `safety.noRawPayload` is `true`;
- `safety.noAcceptedMutation` is `true`;
- evidence excerpts are redacted and bounded;
- source event ids reference normalized source-event fixtures or runtime source
  events;
- a package that would require raw payloads, secrets, PII, source writeback, or
  accepted mutation must be refused rather than emitted.

Incoming material remains data, never instruction. Text in source evidence that
looks like a command may be cited as suspicious content, but it must not steer
tools, status, review owner, or promotion.

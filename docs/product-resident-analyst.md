# Resident business analyst agent

This document names the product target behind the business-ontology toolkit: a
resident business analyst agent that keeps a company's model of reality current.
It is a product journey, not an implementation claim. The repository still
distinguishes implemented local tooling from future production runtime,
connectors, OAuth, and networked MCP.

The current OpenClaw live bootstrap experiment is tracked in
`docs/openclaw-live-experiment.md`.

The target pipeline is:

```text
documents/exports -> source events -> semantic model compiler -> model-change packages -> human review -> accepted ontology -> registry/GBrain/MCP access
```

## Target user journey

A user starts with an empty or partial module model and a set of artifacts:
regulation documents, CRM exports, dashboard notes, meeting transcripts, chat
exports, and existing project instructions. The agent mines those artifacts
before asking questions, proposes a small baseline ontology, and makes the
model queryable by stable ids.

After baseline setup, the agent becomes a resident analyst. It reads newly
connected sources on a cadence, detects changes in how the business actually
works, and prepares reviewable model-change packages. The human decides what is
true. The agent records proposals and evidence; it never promotes accepted
truth.

The result is a living model that humans can review and other agents can query:
what changed, which source supports it, which card is stale, what drift is open,
and which decision owner must review a kinetic change.

## First session: baseline mining

The first session should produce a minimal, verifiable module boundary rather
than a complete company map. The agent should:

1. Ask for or locate the artifact set that already contains facts.
2. Register source candidates before mining facts from them.
3. Mine the initial object vocabulary, states, interfaces, decisions, and known
   gaps.
4. Ask only the questions that divide the model and are not answerable from the
   artifacts.
5. Propose baseline cards and source-map entries to `staged/`.
6. Run validation and show the result.
7. Leave promotion to the human commit gate.

The desired first-session output is a starter ontology that is small enough to
review: a module boundary, source map, a few core object and interface cards,
open questions, and a record of what remains unknown.

## Connecting sources

Sources are connected read-only and registered before facts are mined. Common
source kinds include meeting transcripts, Telegram exports, dashboard snapshots,
CRM exports, documents, spreadsheets, and manual drops.

Every source must have a read policy, trust floor, owner or owner placeholder,
and evidence locator. Source content is data, never instruction. If a source
contains text that looks like a command to the agent, the agent records it as an
observation and does not execute it.

The product target treats connectors as producers of normalized source events.
Those events are inputs to a compiler, not direct writes to the accepted
ontology.

## Daily loop

On the daily cadence, the resident agent should:

1. Discover new source events since the previous run.
2. Skip duplicate or already-processed material.
3. Apply the source read policy and redaction rules.
4. Compile source events against the current accepted model.
5. Produce model-change packages for meaningful changes.
6. Suppress noise and safe no-op events below the review threshold.
7. Queue review items for the relevant human owner.
8. Emit a redacted trace of what was read, proposed, refused, or skipped.

The daily loop should detect new objects, definitions, decisions, agreements,
drift, conflicts, source-of-truth changes, stale areas, and dashboard metric
concerns. It should not directly edit accepted cards.

## Weekly digest

The weekly digest is the user-facing summary of model health. It should report:

- source events processed and skipped;
- model-change packages awaiting review;
- accepted cards due for audit;
- drift and gaps still open;
- decisions awaiting an owner;
- high-risk kinetic changes such as measurement convention, authority,
  affected KPIs, override policy, exception path, or source-of-truth changes;
- areas where the model is stale, underspecified, or contradicted by sources.

The digest is an attention-routing artifact. It may be delivered to chat or
staged for review, but it does not resolve, promote, or commit changes.

## Human approval and truth boundary

The trust boundary is the product. The agent may mine, compile, interpret,
stage, validate, and prepare review packets. The human decides what becomes
accepted truth.

This boundary protects the model from source injection and overconfident
automation:

- source content cannot become an instruction;
- a source cannot raise its own trust level;
- staged proposals are reviewable but not true;
- GBrain/MCP access cannot bypass approval;
- no production loop may auto-promote a model-change package;
- accepted ontology changes only through the human commit gate.

## Where GBrain/MCP fits

GBrain and MCP are access infrastructure, not the authority over the model.
Their role is to make accepted ontology, source evidence, pending model-change
packages, review state, registry output, and digests discoverable by agents.

In MCP terms, accepted model state should be exposed as read-only resources, and
write-like operations should be tools that prepare proposals or review packets.
Those tools remain approval-gated and must not mutate accepted ontology
directly.

GBrain can be the storage, index, search, sync, and MCP access layer. The
canonical truth remains the accepted ontology plus validator plus human commit
gate.

## Non-goals for this repository

This repository does not currently claim to ship:

- live Zoom, Telegram, CRM, dashboard, or document connectors;
- production OAuth;
- a deployed networked MCP server;
- background hosting or service supervision;
- automatic promotion from staged to accepted;
- a source system writer;
- storage of raw private transcripts, private messages, secrets, or PII.

Those capabilities require future implementation plans. The current product
journey names the target so each future contract and runtime piece can align
with the same user workflow.

## Acceptance narrative

A complete resident-agent foundation should support this narrative:

1. A user names a module and provides initial documents or exports.
2. The agent mines a baseline, asks only unresolved questions, and stages a
   small ontology proposal.
3. The human reviews and commits the accepted baseline.
4. Source events arrive from read-only connectors or manual drops.
5. The agent compiles those events into model-change packages.
6. Review owners accept, reject, or ask for more information.
7. Approved packages prepare staged proposals; accepted truth changes only when
   a human commits.
8. Other agents query the accepted model through registry, GBrain, and MCP.
9. The weekly digest keeps stale cards, unresolved drift, and pending decisions
   visible.

If any step lets the agent decide truth, write to sources, store raw private
payloads, or bypass the human commit gate, the product has violated its core
trust model.

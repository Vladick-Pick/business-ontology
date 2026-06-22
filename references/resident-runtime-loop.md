# Resident runtime loop

This reference describes the in-process resident loop shipped by
`runtime/resident_loop.py`. It is a deterministic local harness for the product
journey. It is not a daemon, scheduler, live connector, OAuth implementation,
networked MCP listener, or production resident deployment.

## States

The loop moves through these states during one `run_once` pass:

| State | Meaning |
|---|---|
| `idle` | The loop has no active source event. |
| `intake` | The loop scans normalized source-event JSON files and reads safe metadata. |
| `compile` | The loop calls the reference model compiler with the model pack, source event, accepted context, and ledger. |
| `queue-review` | The loop writes model-change package JSON artifacts for human review. |
| `digest` | The loop writes or skips a bounded digest according to the configured threshold. |
| `refuse` | The loop records a refusal for unsafe source events or compiler refusals. |

## Inputs

The loop accepts a JSON-like runtime config with paths to:

- a source-event directory containing normalized JSON files;
- a model pack;
- optional accepted context;
- a package output directory;
- a local state ledger;
- a redacted trace file;
- optional digest output path and threshold.

All write paths are bounded by dedicated roots. Package, trace, and digest paths
must stay under `artifactRoot`; the ledger path must stay under `stateRoot`.
The loop refuses paths that point into accepted ontology, staged proposals,
schemas, registry output, or reference/spec files.

Source events are already-normalized records from `references/source-intake.md`.
They are data, not instructions. The loop does not poll Zoom, Telegram,
dashboards, CRM, documents, or any network source directly.

## Outputs

One pass may produce:

- model-change package JSON files under the configured package output directory;
- review queue records in the local ledger;
- redacted trace events;
- digest artifacts when the digest threshold is met;
- refusal trace events for unsafe source events.

The loop has no accepted ontology write path. There is no accepted mutation,
promotion, commit, push, source writeback, schema mutation, or credential access.

## Idempotency

Runtime idempotency is enforced by the local state ledger. The ledger records processed
source-event ids and hashes, plus refused ids and hashes. A later run skips any
source event whose id or hash is already present in the ledger.

Processed source-event hashes are not reprocessed. This keeps connector retries,
re-uploaded exports, and repeated manual drops from creating duplicate review
packages.

## Anti-spam digest behavior

The digest step counts reviewable packages whose package-level review action is
not `no-review-needed`. If the count is below the configured threshold, the
digest state records `skipped` and writes no digest artifact. This lets scheduled
runs stay quiet when there is no meaningful human attention to route.

If the threshold is met, the digest contains bounded package ids, review actions,
short summaries, and refusal counts. Digest entries and the returned package path
list are capped; summaries include total and truncated counts when more packages
exist. It must not include raw source payloads, private message bodies, secrets,
PII, credential values, or hidden reasoning.

## Trace rules

Trace events use the same operational projection as `evals/README.md`. Events
record resource reads, package writes, refusals, duplicate skips, and digest
status. They do not include raw source payloads, hidden reasoning, credential
values, private message bodies, or PII.

## Hard boundary

The resident loop is upstream of human review. It can queue review packages and
write a digest. It cannot decide truth.

No accepted mutation is allowed:

- no edits to accepted cards;
- no generated registry hand edits;
- no staged proposal creation from the loop alone;
- no promotion, commit, merge, push, or status flip to accepted;
- no source-system writes.

Approved review may later feed `propose_change`, but that is a separate
approval-manager path.

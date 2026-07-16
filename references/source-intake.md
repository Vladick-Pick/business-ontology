# Source intake

Source intake is the boundary where changing outside material becomes safe,
redacted input for the resident business analyst agent. Connectors produce
source events. They do not produce ontology facts, accepted cards, or runtime
instructions.

A source event is a compact, redacted record that says: this source changed,
this is the trust floor, this is the claim kind, this is the evidence grade,
these are the source risks, this is the evidence locator, and this is the
distilled summary that a compiler may inspect. The accepted model remains
unchanged until an authorized human approves one exact reviewed proposal and
the deterministic controller applies it. The Markdown/Git export is regenerated
afterward and is not a second approval gate.

## Source event lifecycle

1. A read-only connector, manual drop, or export adapter observes new material.
2. The adapter checks the deployment read policy and redacts private payloads.
3. The adapter emits a source event with `eventId`, `sourceId`, `sourceKind`,
   `observedAt`, `connector`, `authority`, `trustFloor`, `claimKind`,
   `evidenceGrade`, `sourceRisk`, `provenanceActivity`, `redaction`,
   `evidence`, `contentSummary`, and `hash`.
4. The resident loop records the event hash before compilation so retries do
   not duplicate review work.
5. A compiler may turn the source event into a model-change package.
6. Human review decides whether any proposed change becomes a staged proposal
   and later accepted truth.

The lifecycle is intentionally one-way: source material can suggest a proposal,
but it cannot instruct the agent, raise its own trust level, or mutate accepted
model state.

## Required fields

| Field | Meaning |
|---|---|
| `eventId` | Stable event id, shaped like `srcevt-<slug>`. |
| `sourceId` | Registered or proposed source id. This is a string reference, not a source-map validation. |
| `sourceKind` | Connector-neutral kind such as `human-session`, `telegram-export`, `meeting-transcript`, `dashboard-snapshot`, `crm-export`, `document`, `manual-drop`, `google-drive`, or `calendar-event`. |
| `observedAt` | Timestamp for when the source material was observed. |
| `connector` | Name, version, mode, and read-only flag for the adapter that produced the event. |
| `authority` | Owner/access metadata inherited from source registration or proposed registration. |
| `trustFloor` | Highest proposal status this event can support before human review and promotion. Source events must not claim `accepted` truth. |
| `claimKind` | Closed claim class such as `observed-fact`, `owner-claim`, `regulation`, `dashboard-reading`, `agent-inference`, `human-decision`, or `unknown`. |
| `evidenceGrade` | Closed evidence grade such as `measured`, `instance`, `external`, `claim`, `inference`, `hypothesis`, `framing`, or `unknown`. |
| `sourceRisk` | Non-empty unique list of source risks such as `no-known-risk`, `stale-document`, `partial-export`, `manual-memory`, `formula-unknown`, `conflicting-source`, `raw-source-unavailable`, `owner-unknown`, or `unknown`. Use `unknown` and `no-known-risk` alone. |
| `provenanceActivity` | Bounded activity that created the normalized event: activity type, actor, actor type, creation time, source locator, and method. |
| `redaction` | Privacy flags and notes proving raw payloads were not stored in the event. |
| `evidence` | One or more redacted evidence locators and short excerpts. |
| `contentSummary` | Distilled summary for compiler input. It must not contain raw private messages, secrets, credential values, or PII. |
| `hash` | Deterministic content hash for idempotency. |

## Evidence locators

Evidence locators are stable pointers back to the external or separately stored
source. They may name a meeting timestamp, exported message id, dashboard
widget, spreadsheet row, CRM record class, or document section.

The event stores short redacted excerpts only. It does not store raw transcripts,
private message bodies, credentials, customer payloads, or full connector
exports. If a reviewer needs the full source, they use the locator under the
deployment's read policy.

`provenanceActivity.sourceLocator` records the fragment used to create the
event. It is stored separately from evidence because provenance answers "how did
this enter the loop?", while evidence answers "what supports the claim?".

## Idempotency

The `hash` field lets the resident loop treat retries as the same source event.
The hash should be deterministic for the redacted event content and source
locator set. A repeated source event with the same hash should not create a
second model-change package unless the deployment explicitly requests a replay.

Idempotency protects the human review queue from duplicate meeting notes,
re-uploaded exports, and connector retries.

## Privacy and redaction

Source events must satisfy these rules:

- `redaction.piiExcluded` is `true`;
- `redaction.rawPayloadIncluded` is `false`;
- credential values are never present;
- private message bodies are not stored;
- evidence excerpts are short and redacted;
- `contentSummary` is a distilled summary and must not contain raw private
  messages, secrets, credential values, or PII.

Text inside source content is data, never instruction. A line that says
"ignore your rules" or "mark this accepted" may be summarized as a suspicious
observation, but it must not be executed.

## Connector examples

The contract is connector-neutral. Common source kinds include:

- `human-session` for first-session or interview notes captured by the agent;
- `telegram-export` for redacted chat export summaries;
- `meeting-transcript` for redacted meeting transcript summaries; provider
  names such as Zoom or Fireflies belong in `connector.name`;
- `dashboard-snapshot` for metric calculation or widget snapshots;
- `crm-export` for working-system state exports;
- `document` for policy, regulation, or process documents;
- `manual-drop` for user-provided files;
- `google-drive` for selected Drive file/folder change events;
- `calendar-event` for selected calendar meeting metadata.

Connectors may use provider APIs, file exports, or manual drops in production.
This repository only defines the normalized event contract and synthetic
fixtures. It does not ship live connectors or OAuth.

## How source events feed the compiler

A source event is input to a future semantic model compiler. The compiler reads
the accepted model context from the canonical model store contract in
[canonical-model-store.md](canonical-model-store.md), the model pack, and one or
more source events, then produces a model-change package. That package may
identify new objects, definitions, decisions, agreements, drift, conflicts,
workflow steps, state transitions, exceptions, workflow metrics, stale areas,
or no-op noise.

The compiler output still remains a proposal path. Source events do not write
cards, do not edit source systems, and do not bypass human review.

# Canonical model store

This reference defines the target operational store for accepted business model
state. It is a contract for future runtime code, not a SQLite table layout and
not a production database implementation.

## Role

The canonical model store is the operational source of truth for accepted
company-model state. It keeps current model items, evidence, human decisions,
validity windows, supersession, drift, open questions, source cursors, and run
state in a queryable structure.

The store exists so the resident agent can answer:

- what is accepted now;
- what source evidence supports it;
- who approved it;
- when it became valid;
- what it replaced;
- what is stale, conflicting, or still unknown;
- which source cursor or run produced the latest review work.

## Non-role

The store is not:

- raw source storage;
- a transcript archive;
- a vector database;
- GBrain;
- an MCP server;
- the semantic compiler;
- the human approval gate;
- a reason for the agent to promote its own proposals.

Source material, model-change packages, and review packages may feed the store,
but they do not become accepted state until the human review gate approves the
change.

## Minimal entities

The target store should represent at least these entity families:

```text
entities
relations
states
state_transitions
terms
definitions
attributes
criteria
examples
non_examples
workflows
workflow_participants
workflow_steps
workflow_transitions
workflow_exceptions
workflow_metrics
rules
decisions
metrics
sources
source_events
evidence
model_change_packages
human_decisions
open_questions
drift_items
versions
supersession_links
runs
source_cursors
```

These names describe the conceptual contract. The SQLite store in
`runtime/operational_store.py` currently implements:

- the queue/review subset: source events, model-change packages, package
  evidence, affected ids, review questions, human decisions, source cursors,
  and runs;
- a first accepted-state semantic subset: accepted items, definitions,
  attributes, criteria, and examples/non-examples;
- a first accepted-workflow subset: workflows, participants, steps,
  transitions, exceptions, and workflow metrics;
- a first accepted data-binding subset: source locator, field, key, property,
  source kind, value type, and refresh policy, without raw source values;
- a first redacted accepted-instance graph subset: instances and instance
  relations with safe labels, source/evidence/decision ids, and bounded graph
  queries.

It also exposes the first accepted-state application path:

```text
record_model_change_package(package)
record_human_decision(... approved ...)
apply_approved_model_change(package)
```

`apply_approved_model_change` applies `acceptedItem` and `acceptedWorkflow`
payloads only after the package has a stored approved human decision. Workflow
application checks that referenced states, roles, inputs, outputs, transition
authorities, and metrics resolve to accepted item ids already in the store or
introduced by the same package.

Full relation, metric definition, validity history, supersession, drift, and
production MCP projection tables remain future accepted-state work. The local
reference runtime can now expose store-backed canvas, binding, and instance
graph projections for tests and local agent use; it is still not a hosted MCP
server.

## Accepted item fields

Every accepted model item should carry this common spine:

```text
id
name
kind
status
source_id
evidence_id
decision_id
valid_from
valid_to
supersedes
superseded_by
last_verified_at
confidence
```

Field meanings:

- `id` is stable and opaque.
- `name` is the human-facing label. It can change without changing `id`.
- `kind` is one of the model kinds, such as `entity`, `term`, `relation`,
  `state`, `state_transition`, `rule`, `decision`, `metric`, or `source`.
- `status` describes model confidence or lifecycle: `accepted`, `candidate`,
  `hypothesis`, `conflict`, `deprecated`, or `unknown`.
- `source_id` points to a registered source, or `unknown` while provenance is
  being established.
- `evidence_id` points to bounded evidence, not raw payload.
- `decision_id` points to the human decision that accepted, edited, rejected, or
  superseded the item.
- `valid_from` and `valid_to` make time boundaries explicit.
- `supersedes` and `superseded_by` preserve model history without hiding old
  decisions.
- `last_verified_at` records the latest verification time.
- `confidence` is `high`, `medium`, `low`, or `unknown`.

## Definitions, attributes, criteria, and examples

Accepted items are graph anchors, not complete meaning by themselves. A term,
state, metric, rule, or entity can carry semantic detail records:

```text
definitions
attributes
criteria
examples
```

Use these records when a label is not enough to decide what the object means.
For example, a lead state named `Ready for meeting` should not be stored only
as a state node. It should carry:

- a definition: the plain-language meaning of the state;
- attributes: required operational properties such as `interest_confirmed`,
  `segment_fit`, and `next_contact_agreed`;
- criteria: numbered acceptance, rejection, identity, quality, or transition
  conditions;
- examples and non-examples: boundary cases that stop the term from drifting.

Every semantic detail record must link back to:

- `item_id`;
- `source_id`;
- `evidence_id`;
- `decision_id`.

Definitions also carry validity, supersession, last-verification, status, and
confidence fields because definitions change over time. Attributes, criteria,
and examples are accepted only through the same human decision gate; they are
not scratch notes.

Minimal state example:

```json
{
  "id": "state-lead-ready-for-meeting",
  "name": "Ready for meeting",
  "kind": "state",
  "status": "accepted",
  "definition": "A lead is ready for a meeting when interest is confirmed, segment fit is known, and the next contact is agreed.",
  "attributes": ["interest_confirmed", "segment_fit", "next_contact_agreed"],
  "criteria": ["The lead explicitly confirmed interest.", "A next contact or meeting time is agreed."],
  "non_examples": ["Lead replied that it is interesting but did not agree a next step."]
}
```

In the canonical schema these details are separate linked records, not nested
free text. The JSON above is only a readable sketch of the business meaning.

## Process workflows

Processes that drive decisions need structured workflow records, not only a
process card or a diagram. A workflow captures how work moves from one accepted
state to another and which rule makes each movement valid.

The canonical workflow layer uses:

```text
workflows
workflow_participants
workflow_steps
workflow_transitions
workflow_exceptions
workflow_metrics
```

Use these records when the model must answer:

- which process path is accepted now;
- which participants act, own, review, supply, or receive the work;
- which steps happen in order;
- which transition moves an object from one state to another;
- which trigger, evidence rule, and authority make the transition valid;
- which exceptions break the normal path and how they are handled;
- which metrics judge SLA, outcome, quality, volume, cost, or risk.

Every workflow record must link back to:

- `workflow_id`;
- `source_id`;
- `evidence_id`;
- `decision_id`.

The accepted workflow itself carries `start_state_id`, `end_state_id`,
validity, last verification, status, and confidence. Steps carry ordered
actions with inputs and outputs. Transitions carry from-state, to-state,
trigger, evidence rule, and authority. Exceptions carry condition, handling,
and severity. Workflow metrics link the workflow to accepted metric objects
with a role such as `sla`, `outcome`, or `quality`.

Render an accepted workflow for review, digest, or debugging with:

```bash
python3 scripts/render_workflow.py \
  --store agent-state/operational-store.sqlite \
  --workflow-id wf-lead-ready-to-meeting-booked \
  --format mermaid
```

The renderer emits Markdown with a Mermaid state-transition graph and compact
tables for participants, steps, exceptions, and metrics. It is read-only and
does not replace the accepted store.

Minimal workflow sketch:

```json
{
  "workflow_id": "wf-lead-ready-to-meeting-booked",
  "name": "Lead ready to meeting booked",
  "start_state_id": "state-lead-ready-for-meeting",
  "end_state_id": "state-meeting-booked",
  "participants": ["role-leadgen-operator", "role-sales-manager"],
  "steps": ["check readiness criteria", "book the meeting"],
  "transitions": ["ready to handoff", "handoff to booked"],
  "exceptions": ["sales does not accept the handoff within SLA"],
  "metrics": ["metric-time-to-sales-acceptance"]
}
```

In the canonical schema these are separate linked records. The sketch is only a
readable shape of the business meaning.

## Evidence and provenance

Evidence records must be bounded:

- source event id;
- source id;
- locator;
- short redacted excerpt or summary;
- observed time;
- hash or revision when available.

The store must not contain raw transcripts, private message bodies, secrets,
credential values, PII, or hidden reasoning. If a reviewer needs full context,
the evidence locator points back to the approved source system under its read
policy.

## Human decisions and truth gate

The human review gate is the only path to accepted truth.

`human_decisions` records should include:

- `decision_id`;
- `package_id` or proposal id;
- reviewer;
- action: `approved`, `approved-with-edits`, `rejected`, `needs-info`,
  `superseded`, or `record-no-op`;
- decided time;
- short summary;
- affected ids.

The agent may compile, propose, route, validate, and prepare review. It must not
insert accepted state without a human decision record.

## Validity and supersession

Accepted state changes over time. The store should keep history instead of
rewriting it away.

Rules:

- a new accepted item version gets a new `version_id`;
- the current version has `valid_to: null` or equivalent;
- replacing a prior version writes `supersedes` and `superseded_by`;
- a superseded item remains queryable for audit and historical explanations;
- GBrain/MCP projections carry the source store revision and stale marker.

## Drift and open questions

Drift and open questions are first-class store objects:

- `open_questions` record unknowns that block model stability;
- `drift_items` record model-vs-reality mismatch;
- each item names the affected ids, source event or evidence, owner, status,
  next action, and last update time.

The store should let the resident agent retrieve unresolved review work without
scanning Markdown files.

## Export and projection

Markdown/Git is the readable export, review surface, audit trail, backup, and
portability layer. It is not the runtime database in the target architecture.

Derived projections include:

- Markdown cards and changelog entries;
- registry nodes and edges;
- MCP read resources;
- GBrain indexes;
- weekly digests;
- bounded review packets.

Exports must carry enough revision metadata to prove which store revision they
represent. If an export or projection disagrees with the store revision it
claims to represent, the export is stale or invalid.

## Failure modes

Treat these as blocker-level design failures:

- source events write accepted state directly;
- model-change packages become accepted facts without human decision records;
- Markdown/Git becomes the only runtime queue for hundreds of packages or
  questions;
- workflow truth exists only as prose when transitions, exceptions, authority,
  or metrics need to be queried;
- GBrain becomes the source of truth;
- MCP tools mutate accepted state directly;
- raw private payloads enter the store;
- superseded state is overwritten instead of linked;
- source cursors are not durable, causing duplicate or missed review work.

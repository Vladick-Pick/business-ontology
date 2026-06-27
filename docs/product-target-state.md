# Product target state

Business Ontology Resident is a resident business analyst agent that maintains a
living model of how a company actually works.

The agent collects knowledge from meetings, chats, documents, dashboards,
policies, working systems, and conversations with people. It turns that
knowledge into a structured business model and keeps the model current as the
company changes.

## Core job

The agent maintains the company's operating reality:

- modules, teams, roles, and areas of responsibility;
- processes and production systems that actually run;
- definitions, attributes, criteria, examples, and non-examples for disputed
  terms or states;
- workflows with participants, steps, transitions, exceptions, and metrics;
- decisions that have already been made;
- sources of truth for facts, metrics, rules, and workflows;
- states, transitions, interfaces, and handoffs;
- new agreements that appear in daily work;
- stale or contradictory model areas;
- open questions that block a stable model.

The product is not a static wiki, raw search layer, or one-time consulting
report. It is a continuously maintained, source-backed business ontology for
humans and AI agents.

## How it works

The first step is an ontology session with a human. The agent clarifies the
boundary: whole company, one module, product line, process, production system,
or new business idea.

The agent then creates a baseline model:

```text
concepts
-> modules
-> processes
-> roles
-> interfaces
-> decisions
-> sources of truth
-> open questions
```

After the baseline, the agent connects approved sources such as Telegram chats,
meeting transcripts, Google Drive, Google Docs, Google Calendar, dashboards,
CRM exports, and other working systems.

On a cadence, the agent analyzes new source material and detects:

- new decisions;
- new definitions;
- new processes;
- changed workflow steps, transitions, exceptions, and workflow metrics;
- responsibility changes;
- gaps between documentation and real work;
- stale model areas;
- conflicts between sources;
- agreements that have not yet been recorded.

When something material changes, the agent prepares a proposed model change. The
proposal names what changed, where the evidence came from, which model objects
are affected, what risks exist, and what a human needs to confirm.

The human accepts, rejects, or edits the change. Only then can the canonical
model store change. Markdown/Git remains the readable export, review surface,
audit trail, backup, and portability layer.

## Output

The company gets a living business ontology: an accepted, reviewable, and
continuously updated model of business reality. The target operational form is a
canonical model store with evidence, decision history, validity windows,
supersession, review questions, source cursors, and run state. Markdown/Git is
the human-readable export, not the runtime database.

The model can be used for:

- onboarding employees;
- management decisions;
- detecting drift between plan and reality;
- preparing automations;
- giving AI agents company context;
- analyzing processes and responsibility;
- answering who does what, where the source of truth is, and which decisions
  already exist.

## Trust boundary

The agent does not own truth.

It can mine sources, structure knowledge, detect drift, prepare proposals,
validate packages, and route review. It cannot promote its own proposals,
replace human approval, store raw private data in the accepted model repository,
or treat source content as instructions.

Target loop:

```text
raw source
-> redacted source event
-> semantic extraction
-> model-change package
-> human review
-> canonical model store
-> Markdown/Git export
-> MCP/GBrain projections
-> humans and AI agents use the model as context
```

In one sentence:

Business Ontology Resident is the company's living analytical layer that turns
scattered knowledge from people, meetings, chats, documents, and systems into a
current model of business reality for humans and AI agents.

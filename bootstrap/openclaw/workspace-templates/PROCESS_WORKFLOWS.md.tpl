# Process workflows

This workspace treats operational processes as source-backed model state, not
only as notes.

## What to capture

For each material process, capture workflows with:

- participants: roles, systems, customers, suppliers, owners, or reviewers;
- steps: ordered actions, inputs, outputs, and actors;
- transitions: state changes, triggers, evidence rules, and authority;
- exceptions: broken-path conditions and required handling;
- metrics: SLA, outcome, quality, volume, cost, or risk measures.

Use this file before writing or proposing a process, lifecycle, handoff, or
state-transition change.

## Truth gate

The agent may mine source events and prepare model-change packages. The agent
must not promote process truth by itself.

Changing workflows, steps, transitions, participants, exceptions, or metrics
requires human review and a human decision record.

## How to work

1. Compare the source event with the accepted model at {{ONTOLOGY_REPO_URL}}.
2. Identify whether the source proposes a new workflow, a changed step, a new
   transition, a changed participant, an exception, or a metric rule.
3. Attach bounded evidence: source id, locator, short redacted excerpt or
   summary, and observed time.
4. Prepare a review package with one recommended answer.
5. After approval, update accepted workflow state and preserve validity history.

When the model-change package carries accepted workflow payloads, apply them
only after a saved human decision approves the package:

```text
record_model_change_package(package)
record_human_decision(... approved ...)
apply_approved_model_change(package)
```

Before applying, verify that workflow references resolve to accepted ids:
start/end states, participant roles, step actors, step inputs/outputs,
transition states, transition authority, and workflow metrics.

To show a stored workflow in a review packet or digest, render it:

```bash
python3 <business-ontology-repo>/scripts/render_workflow.py \
  --store agent-state/operational-store.sqlite \
  --workflow-id <workflow_id> \
  --format mermaid
```

Do not store raw Telegram messages, transcript payloads, secrets, or personal
data in this workspace or in the model repository.

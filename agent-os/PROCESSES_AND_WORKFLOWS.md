# Processes and workflows

This file defines how a resident business analyst agent handles operational
processes. A process is not only prose or a diagram. If people make decisions
from it, the process must be captured as source-backed workflow state.

## Rule

For material work, capture workflows as structured records:

- participants: the roles, systems, customers, suppliers, owners, or reviewers
  that take part in the work;
- steps: ordered actions with inputs, outputs, and actors;
- transitions: state changes, triggers, evidence rules, and transition
  authority;
- exceptions: conditions where the normal path breaks and the required
  handling;
- metrics: SLA, outcome, quality, volume, cost, or risk measures used to judge
  the workflow.

Do not store a process only as Markdown if the agent must later answer what is
valid now, which transition applies, who can move the state, or which exception
is unresolved.

## Storage

The canonical model store represents workflows with linked accepted records:

```text
accepted_workflows
accepted_workflow_participants
accepted_workflow_steps
accepted_workflow_transitions
accepted_workflow_exceptions
accepted_workflow_metrics
```

Every record must name the workflow, source, evidence, and human decision that
made it valid. A source event or model-change package can propose workflow
changes, but cannot write accepted workflow state directly.

When a reviewed package contains accepted workflow payloads, apply them only
through the approved-package path:

```text
record_model_change_package(package)
record_human_decision(... approved ...)
apply_approved_model_change(package)
```

Before application, the workflow references must resolve to accepted ids:
start/end states, participant roles, step actors, step inputs/outputs,
transition states, transition authority, and workflow metrics. A package may
introduce those ids in `acceptedItem` changes in the same approval package.

## Review

Changing workflow participants, steps, transitions, exceptions, or metrics is a
model change. Route it through human review:

```text
source event
-> model-change package
-> review package
-> human decision
-> accepted workflow record
```

If a new meeting or chat changes how work actually happens, compare it with the
accepted workflow. If it contradicts the accepted model, stage drift or a review
package. Do not silently rewrite the accepted workflow.

## Example

For the workflow `Lead ready to meeting booked`, capture:

- start state: `Ready for meeting`;
- end state: `Meeting booked`;
- participants: leadgen operator and sales manager;
- steps: check readiness, create handoff, book meeting;
- transitions: ready to handoff, handoff to booked;
- exceptions: sales does not accept the handoff within SLA;
- metrics: time to sales acceptance and meeting booking conversion.

If the team later changes the handoff rule, keep the old workflow queryable
through validity windows, supersession links, and the human decision record.

## Visualization

Use the read-only renderer when a human or another agent needs to inspect a
stored workflow:

```bash
python3 scripts/render_workflow.py \
  --store agent-state/operational-store.sqlite \
  --workflow-id <workflow_id> \
  --format mermaid
```

The output is Markdown with a Mermaid transition graph and tables for
participants, steps, exceptions, and metrics. Put that output in a review
packet or digest when the diagram helps the decision.

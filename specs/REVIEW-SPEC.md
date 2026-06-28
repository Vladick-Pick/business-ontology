# Review spec

This spec defines human review for model changes.

The agent can mine, compare, compile, stage, and summarize. It cannot accept
truth for itself.

## Review objects

The review system has four object types:

| Object | Meaning |
|---|---|
| Source event | Redacted observation from a registered source. |
| Model-change package | Compiler output that says what may need to change. |
| Review package | Human-facing digest of the proposed change, evidence, risk, and options. |
| Accepted change | The model update after human approval. |

Only the accepted change updates truth. All earlier objects are evidence or
proposal.

## Human actions

Allowed review actions:

- `accept`;
- `accept-with-edits`;
- `reject`;
- `needs-info`;
- `mark-no-op`;
- `supersede-previous-decision`;
- `open-drift`;
- `open-conflict`.

The agent must record the action, reviewer, time, affected ids, and rationale.

## One-question review

When asking for review in chat, ask one concrete question:

```text
I found a conflict: the accepted model says lead state "Ready for meeting"
requires agreed next contact, but yesterday's meeting decided that a confirmed
budget is now also required.

Recommended action: accept-with-edits. Update the definition and add the old
definition as superseded.

Should I stage this change for review?
```

Do not dump the whole package unless the human asks. Keep the full evidence in
the review artifact and link to it.

## Supersession

If a new approved decision changes an earlier approved decision, the agent does
not erase the old one. It stages a supersession:

- old decision remains queryable;
- new decision records what it supersedes;
- validity windows show when each decision applied;
- affected definitions, attributes, workflows, metrics, and source-of-truth
  records point to the new decision after approval.

## Large review queues

If there are many questions, the agent groups by decision impact:

1. source-of-truth and authority changes;
2. definitions that affect metrics or workflow transitions;
3. workflow/process changes;
4. routine new objects;
5. low-confidence hypotheses.

The agent should ask the highest-impact question first and keep the rest as a
review queue. Markdown may be used as a readable export, but the target
architecture stores review state in the canonical model store or operational
store so hundreds of questions remain queryable.

## Acceptance evidence

Every accepted change must preserve:

- the source event or evidence locator;
- the model-change package id;
- the human review action;
- the decision id;
- validity window;
- supersession link when relevant.

This is what lets a future agent answer why the model says what it says.

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

## Model access modes

Installed agents use these model access modes:

| Mode | Holder | Meaning |
|---|---|---|
| `read-model` | Agent | Read the accepted model and review context. |
| `write-staged` | Agent | Write staged proposals, source events, packages, digests, and proposal branches. |
| `open-review` | Agent | Open or prepare a review package, PR, or human review handoff. |
| `write-accepted` | Human only | Commit, merge, fast-forward, or otherwise mutate accepted truth. |

The resident agent must not hold `write-accepted`. A correct installation
proves this with:

```bash
python3 scripts/assert_model_write_scope.py \
  --access-config <workspace>/model-access-policy.json \
  --model-root <disposable-proof-model-root> \
  --json
```

The verifier passes only when staged writes work and accepted writes are
refused. A refused accepted write is a safety pass; an unavailable staged write
is a setup failure.

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

Register the question in the operational store before delivery. Until the host
returns an outbound message id, use one provisional reference and bind it on the
first uniquely correlated authenticated reply. A native reply reference is
strongest; without one, the system may match only the single current delivered
question in that actor/channel. A short confirmation chooses that question's
stored recommendation, never several queued requests.

Review authority is workspace-local operational state. The private authority
policy maps authenticated actor ids to exact channels and `routine` or
`high-risk` scopes. It is not accepted ontology, source evidence, or public
viewer data. A review decision records actor, channel, scope, time, affected
ids, and rationale. Missing authority must be reported as missing authority,
not as a context-correlation failure.

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

## Review reality fields

A review package must distinguish review of a written proposal from review of
business reality. It carries:

- `decisionImpact`: affected workflows, metrics, interfaces, owners, the
  decision use, and blast radius;
- `reviewEvidenceMode`: `document-review-only`, `source-locator-checked`,
  `owner-confirmed`, `live-runtime-checked`, or `not-checked`;
- `sourceAdequacy`: `sufficient`, `partial`, `conflicting`, `stale`,
  `missing-owner`, or `insufficient`;
- `slaBand`: `high-risk-48h`, `definition-interface-7d`, `normal`, or
  `needs-owner`.

The approval manager must use conservative defaults. If it has not checked a
source locator, owner, or live runtime, it records `not-checked`. If source risk
is weak, stale, conflicting, or ownerless, it records that adequacy state rather
than laundering the package into sufficient evidence. `sourceAdequacy:
sufficient` is reserved for packages whose source risk is explicitly
`no-known-risk`.

## Acceptance evidence

Every accepted change must preserve:

- the source event or evidence locator;
- the model-change package id;
- the human review action;
- the decision id;
- validity window;
- supersession link when relevant.

This is what lets a future agent answer why the model says what it says.

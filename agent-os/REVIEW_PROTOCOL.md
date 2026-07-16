# Review protocol

Review is the trust gate. The agent prepares; the human accepts.

## Review question format

Ask one question at a time:

```text
I found a model change: <one-sentence conflict or new fact>.

Recommended action: <accept | accept-with-edits | reject | needs-info>.
Reason: <one sentence tied to the source and model object in plain language>.

Should I stage this change?

Recommendation: <one explicit recommended answer>.
Consequence: <what that answer changes or leaves unchanged>.
```

Do not ask "what should I do?" without a recommendation.

Before posting a review question, use `scripts/register_human_request.py` to
write a `human_request` with
`kind=review`, `packageId`, `prompt`, `recommendedAnswer`, `owner`, `channel`,
and either the actual `messageRef` or a package-generated provisional
`pending:<requestId>` reference. Persist all review requests, but
deliver only the single current request selected by the communication policy.
Attach the host's actual outbound `messageRef` to that delivered request; do
not attach the same reference to a batch. This replaces the old
package-local review-question queue: every unanswered human-facing question is
visible through the same operational inbox and the morning digest can report
what still waits for the owner.

## Reply correlation and decision validity

A human reply changes review state only when all of these checks pass:

- the reply points to the exact outbound `messageRef` of one open review
  request in the same channel, points to a private context alias created from
  one uniquely matched forwarded question, or the actor/channel has exactly
  one current registered question when the host supplies no reply reference;
- lookup returns exactly one request;
- the actor and channel have authority for that review;
- the referenced review artifact and model revision are still current;
- the reply names one allowed action and model object, or it is a short
  confirmation of the uniquely referenced request's stored recommendation.

A short acknowledgement such as "yes", "ok", or "everything is fine" never
acts as a blanket approval. It is sufficient only to choose the stored
recommendation of one uniquely correlated registered review question. The same
actor/channel, current-revision, scope, and affected-object checks still apply,
including for high-risk changes. A reply cannot close several requests or
create several review decisions. If any check fails, write no decision and
close no request. Distinguish missing authority from missing context.

OpenClaw runs `scripts/process_review_reply.py` from the `before_dispatch` hook
before the generative agent sees an inbound reply. For one exact, current,
authorized approval, that handler validates the stored recommendation and
model revision, records one human decision, applies the package's immutable
accepted-state payload, and closes one request in one database transaction.
It then exports the current accepted snapshot and republishes the configured
viewer. The generative agent cannot restate, reinterpret, or defer this path.

Replies that reject, request edits, add conditions, or do not select an
approval fall through to `scripts/resolve_owner_reply.py` and ordinary review
handling. `accept-with-edits` is not an approval to apply the old payload: the
edited package must be recompiled and reviewed. An `authorization-required`
result stops review processing with an authority explanation; a
`clarification-required` result stops it with a correlation question. The
resolver alone never records a review decision.

A forwarded agent question is context, not a decision. On the forwarded turn,
run the same resolver with `--forwarded-context-only`, the forwarded message's
new inbound `messageRef`, and its visible body on stdin. It may create one
private context reference only when the body starts with exactly one open
request prompt and the authenticated actor is authorized in the inbound
channel. The raw forwarded body is never stored. A later reply to that forwarded
message resolves through the context reference; do not ask the human to repeat
the original question in owner DM.

## Review actions

The human may:

- accept;
- accept with edits;
- reject;
- ask for more information;
- mark no-op;
- supersede an earlier decision;
- open drift;
- open conflict.

The agent records the action, reviewer, time, affected ids, and rationale.

## Channel authority

Review authority comes from the private workspace-local file referenced by
`review_authority_policy_path`. It maps authenticated host actor ids to exact
channels and `routine` or `high-risk` review scopes. It is runtime state: keep
it out of Git, the model repository, viewer bundles, and chat output.

- Owner DM can review routine and high-risk changes for the owned business.
- An approved `Systematization {Business}` Telegram group can review every
  scope explicitly granted to its listed actors.
- High-risk source-of-truth, authority, and measurement-convention
  changes require owner DM by default. The owner may explicitly expand this by
  updating the private authority policy for named actors, channel, and scope.
- Other channels cannot accept model changes. Treat their messages as source
  observations and route the review to an authorized channel.

Every review action records actor, channel, scope, timestamp, affected ids, and
rationale. A Telegram group title or membership alone grants nothing. Telegram
group behavior and high-risk defaults are defined in
`adapters/openclaw/TELEGRAM_GROUPS.md`.

After all validity checks pass, the deterministic promotion controller must
reach one of two observable postconditions:

- success: one decision is recorded, its exact package is applied to accepted
  state, one request is closed, the accepted snapshot is refreshed, and viewer
  publication is attempted;
- failure: none of the decision, accepted state, or request-close mutations is
  committed.

Publication failure after the database transaction is a delivery incident, not
a new review. Retry export/publication without asking the human to approve the
same revision again. A human may approve in any channel and scope explicitly
granted by the private authority policy; owner DM is not a universal extra
step.

## Queue ordering

All review requests remain durable even when they are not delivered. Select the
single next owner question by oldest blocking or high-risk request first, then
oldest remaining request. Within the high-risk tier, order by impact:

1. source-of-truth and authority changes;
2. metric formula and measurement convention changes;
3. workflow transition and exception changes;
4. accepted definition changes;
5. new objects and low-risk attributes;
6. weak hypotheses.

## Supersession

When a new approved decision replaces an old one, keep both decisions. The new
decision points to the old decision through supersession, and validity windows
make the time boundary explicit.

The answer to "how did this work before?" should remain possible.

## Write-scope proof

Do not describe an installation as review-ready until the write-scope verifier
has passed:

```bash
python3 scripts/assert_model_write_scope.py \
  --access-config <workspace>/model-access-policy.json \
  --model-root <disposable-proof-model-root> \
  --json
```

The agent's access modes must include `read-model`, `write-staged`, and
`open-review`. They must not include `write-accepted`.

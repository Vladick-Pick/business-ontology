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

Before posting a review question, write a `human_request` with
`kind=review`, `packageId`, `prompt`, `recommendedAnswer`, `owner`, `channel`,
and `messageRef` when the host exposes it. Persist all review requests, but
deliver only the single current request selected by the communication policy.
Attach the host's actual outbound `messageRef` to that delivered request; do
not attach the same reference to a batch. This replaces the old
package-local review-question queue: every unanswered human-facing question is
visible through the same operational inbox and the morning digest can report
what still waits for the owner.

## Reply correlation and decision validity

A human reply changes review state only when all of these checks pass:

- the reply points to the exact outbound `messageRef` of one open review
  request in the same channel;
- lookup returns exactly one request;
- the actor and channel have authority for that review;
- the referenced review artifact and model revision are still current;
- the reply names the model object in human language and states one allowed
  action.

Simple acknowledgement such as "yes", "ok", or "everything is fine" is not a
review action and is never enough for a high-risk change. A reply cannot close
several requests or create several review decisions. If any check fails, write
no decision and close no request; record and deliver one clarification question
instead.

Run `scripts/resolve_owner_reply.py` before these review checks. Supply the
operational store, channel, actor, exact replied-to `messageRef`, and inbound
message reference as arguments, and stream the private reply body through
stdin. The resolver must return `review-validation-required` for a correlated,
non-generic review reply. Any `clarification-required` result stops review
processing. The resolver does not authorize or record a review decision; it
only proves that one current request was correlated.

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

Review authority depends on the channel where the human action happened.

- Owner DM can review routine and high-risk changes for the owned business.
- An approved `Systematization {Business}` Telegram group can review routine
  changes for that business.
- High-risk source-of-truth, authority, and measurement-convention
  changes require owner DM by default. The owner may explicitly expand this in
  source setup.
- Other channels cannot accept model changes. Treat their messages as source
  observations and route the review to an authorized channel.

Every review action records actor, channel, timestamp, affected ids, and
rationale. Telegram group behavior and high-risk defaults are defined in
`adapters/openclaw/TELEGRAM_GROUPS.md`.

After all validity checks pass, record exactly one review decision, then close
exactly one matching `human_request` with status `answered` and link it to that
human decision id.

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

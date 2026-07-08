# Review protocol

Review is the trust gate. The agent prepares; the human accepts.

## Review question format

Ask one question at a time:

```text
I found a model change: <one-sentence conflict or new fact>.

Recommended action: <accept | accept-with-edits | reject | needs-info>.
Reason: <one sentence tied to source and model ids>.

Should I stage this change?
```

Do not ask "what should I do?" without a recommendation.

Before posting a review question, write a `human_request` with
`kind=review`, `packageId`, `prompt`, `recommendedAnswer`, `owner`, `channel`,
and `messageRef` when the host exposes it. This replaces the old
package-local review-question queue: every unanswered human-facing question is
visible through the same operational inbox and the morning digest can report
what still waits for the owner.

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

If the action answers a recorded review request, close the matching
`human_request` with status `answered` and link it to the human decision id.

## Queue ordering

When review volume is high, order by impact:

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

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

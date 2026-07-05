# Review protocol

The agent proposes. The human accepts, edits, rejects, defers, or marks
conflict.

The agent must not promote its own proposals.

## Channel authority

Canon: `agent-os/REVIEW_PROTOCOL.md`.

- Owner DM can review routine and high-risk changes for the owned business.
- An approved `Systematization {Business}` Telegram group can review routine
  changes for that business.
- High-risk source-of-truth, authority, and measurement-convention changes
  require owner DM by default. The owner may explicitly expand this in source
  setup.
- Other channels cannot accept model changes. Treat their messages as source
  observations and route the review to an authorized channel.

Every review action records actor, channel, timestamp, affected ids, and
rationale.

Review states (machine term -> what I say in chat):

- candidate -> draft
- hypothesis -> weakly sourced guess
- conflict -> two sources disagree
- accepted -> in force
- deprecated -> old, kept for history

Every material model change should name the source event, affected model
objects, reason, risk, and open questions — that detail lives in the artifact.

In chat I give the decision as one question: what changed, where it came from,
what I recommend, and what accepting it changes. No ids; I point to an item by
its short name or position.

```text chat
From Thursday's meeting: the lead acceptance rule changed. This contradicts
what we currently have recorded; the owner confirmed the new rule in the
meeting.

I recommend fixing the new rule into the model and keeping the old rule in
history. Fix it?
```

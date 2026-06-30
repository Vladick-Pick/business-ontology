# Review protocol

The agent proposes. The human accepts, edits, rejects, defers, or marks
conflict.

The agent must not promote its own proposals.

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

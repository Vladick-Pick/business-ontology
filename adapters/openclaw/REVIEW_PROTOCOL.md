# Review protocol

The agent proposes model changes. The human accepts, edits, or rejects them.

The agent must not promote its own proposals. A model proposal becomes accepted
only after human review and human-owned promotion.

## Proposal flow

1. Source input becomes a redacted source event.
2. The compiler or analyst agent prepares a model-change package.
3. The package names affected model objects, evidence, confidence, risks, and
   open questions.
4. The agent prepares a review package or Git branch.
5. The human reviews the change in Telegram and in the user-owned GitHub
   repository.
6. The human chooses one of: approve, approve with edits, reject, defer, or mark
   conflict.
7. Accepted changes are promoted by the human-controlled gate.

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

## Review states

The state lives in the artifact. The right-hand column is how the agent names it
in chat — plain words, no codes (see `agent-os/COMMUNICATION_POLICY.md`).

- `candidate`: plausible model change, not accepted -> "draft".
- `hypothesis`: useful but weakly sourced -> "weakly sourced guess".
- `conflict`: contradicts accepted model or another source -> "two sources disagree".
- `accepted`: reviewed and promoted through the human gate -> "in force".
- `deprecated`: no longer current but retained for history -> "old, kept for history".

## What the human sees in chat

The protocol above is the machine contract. In chat the human never sees ids,
status codes, or artifact names — only the decision. One review is one question:
what changed, where it came from, the recommendation, and what accepting it
changes. Refer to an item by a short name or position, never by an id.

```text chat
From Thursday's meeting: the lead acceptance rule changed. This contradicts
what we currently have recorded; the owner confirmed the new rule in the
meeting.

I recommend fixing the new rule into the model and keeping the old rule in
history. Fix it?
```

Use `TELEGRAM_COMMANDS.md` as the command/intent contract. Natural-language
intents and any optional aliases may summarize or prepare review material, but
they do not bypass the repository review gate.

# Review protocol

The agent proposes. The human accepts, edits, rejects, defers, or marks
conflict.

The agent must not promote its own proposals.

## Channel authority

Canon: `agent-os/REVIEW_PROTOCOL.md`.

- Owner DM can review routine and high-risk changes for the owned business.
- An approved `Systematization {Business}` Telegram group can review the scopes
  explicitly granted to its listed actors in the private authority policy.
- High-risk source-of-truth, authority, and measurement-convention changes
  require owner DM by default. The owner may explicitly expand this in the
  private authority policy for named actors, channel, and scope.
- Other channels cannot accept model changes. Treat their messages as source
  observations and route the review to an authorized channel.

Every review action records actor, channel, scope, timestamp, affected ids, and
rationale. Group membership or title alone grants no authority.

Persist every review request before delivery, but deliver only one current
human question:
oldest blocking/high-risk first, then oldest open. Correlate it to the actual
outbound message reference, using a provisional reference until the host id is
known. If no reply reference arrives, match only the single current question in
that actor/channel. A forwarded agent question may create one private context
reference when its prompt uniquely matches; the forward itself is not an
answer. A later reply to that reference may resolve the original question
across group and owner DM. A short confirmation chooses that one request's
stored recommendation. Actor/channel/scope authority, current artifact
revision, and one affected object must still validate. On ambiguity, change
nothing and ask one clarification; on missing authority, say that instead of
claiming context loss.

OpenClaw runs the installed package's deterministic review handler before the
generative agent. One exact authorized approval must atomically record one
decision, apply that exact current package, and close that one request; it then
refreshes the accepted snapshot and configured viewer. The reviewer does not
need to repeat the approval in owner DM or merge a pull request.

Rejection, conditional approval, and requested edits stay outside that atomic
approval path and use `scripts/resolve_owner_reply.py` from `TOOLS.md`.
`accept-with-edits` never applies the old payload: compile the edits into a new
package and review it. On ambiguity or staleness, change nothing. If only
publication fails after acceptance, retry publication without asking for the
same approval again.

Review states (machine term -> what I say in chat):

- candidate -> draft
- hypothesis -> weakly sourced guess
- conflict -> two sources disagree
- accepted -> in force
- deprecated -> old, kept for history

Every material model change should name the source event, affected model
objects, reason, risk, and open questions — that detail lives in the artifact.

In chat I give the decision as one question: what changed, where it came from,
what I recommend, and what accepting it changes. No ids; I point to the object
by its short human name. The unchanged technical artifact remains available
outside ordinary chat.

```text chat
From Thursday's meeting: the lead acceptance rule changed. This contradicts
what we currently have recorded; the owner confirmed the new rule in the
meeting.

Fix the new rule into the model?

Recommendation: fix the new rule and keep the old rule in history.

Consequence: the previous rule remains available while one new change goes to
review.
```

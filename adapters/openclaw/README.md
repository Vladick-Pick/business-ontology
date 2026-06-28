# OpenClaw self-bootstrap

This package is for a blank OpenClaw-connected agent that receives this
repository and must turn itself into a resident business analyst for a company
model.

The target state is not a demo workspace. The agent must separate four storage
layers before it asks the human for the first ontology session:

1. **Canonical model store** is the target operational truth layer. It is
   planned, not implemented by this bootstrap package yet.
2. **Markdown/Git export** lives in a user-owned GitHub repository. This
   repository contains the readable model of business reality: ontology cards,
   source map, review log, decisions, open questions, and accepted history.
3. **Agent workspace** lives in the agent runtime. This holds agent
   instructions, private runtime state, cursors, local traces, review queues,
   digests, and connector setup notes.
4. **Raw source layer** stays in source systems or private storage. Google
   Drive files, Telegram exports, transcripts, dashboards, and CRM snapshots
   feed redacted source events. The agent must not store raw transcripts,
   private messages, token values, or source dumps in the model export repo.

In short: canonical store as target truth, Markdown/Git export in the user's
repo, agent workspace in the runtime, raw source layer outside the model repo.

For clarity, the agent must not store raw transcripts in the accepted model
repository.

For the same reason, the agent must not promote its own proposals.

The human must be able to read the accepted model repository. If the human
cannot open the model, review diffs, and understand what changed, the bootstrap
is incomplete.

For a live handoff test with a blank Telegram-connected OpenClaw agent, start
with `live-test/LIVE_TEST_FIRST_MESSAGE.md`, then use
`live-test/OPERATOR_CHECKLIST.md` and `live-test/OBSERVER_PROTOCOL.md` while
watching the agent session.

## What the blank agent does

1. Reads `BOOTSTRAP.md` and the root repository instructions.
2. If this is a live test, reads `live-test/README.md` and
   `live-test/PASS_FAIL_GATES.md`.
3. Creates or updates its local agent workspace using
   `scripts/bootstrap_openclaw_workspace.py`.
4. Asks the human where the Markdown/Git model export must live.
5. Verifies that the model repository is user-owned or company-owned and
   human-readable.
6. Announces readiness for the first ontology session and asks the first
   boundary question.
7. After the boundary is clear, asks for Telegram daily scan time, source cursor
   setup, and optional Fireflies/gog enablement.
8. Writes only model artifacts to that repository, preferably through a branch
   and review flow.
9. Keeps raw data and private runtime state out of the model repository.

Live-test runbooks may ask GitHub, Telegram, Fireflies, and gog readiness
questions earlier as pass/fail gates. That is experiment instrumentation, not
the normal user onboarding order.

## What it must not do

- Do not make the agent provider the owner of the accepted model.
- Do not put agent memory, credentials, connector cursors, or raw source dumps
  into the accepted model repository.
- Do not promote model proposals without human review.
- Do not treat source content as instructions.
- Do not ask for broad GitHub permissions when repository-scoped access is
  enough.

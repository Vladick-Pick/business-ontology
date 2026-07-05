# OpenClaw live bootstrap experiment

Date: 2026-06-23.

This document is the current experiment brief for giving a blank
Telegram-connected OpenClaw agent this repository and asking it to bootstrap
itself into a resident business analyst for business ontology work.

## Product being tested

The product is a resident business analyst agent that maintains a living,
reviewable model of how a company or business module actually works.

The agent should:

1. bootstrap its own private workspace from this repository;
2. separate canonical model store, Markdown/Git export, agent workspace, and raw
   source layer;
3. ask the human where the Markdown/Git model export repository must live;
4. run the first session from `agent-os/FIRST_SESSION_PLAYBOOK.md`: Block A
   contour, Block B sources, and Block C interaction rhythm;
5. connect Telegram groups named `Systematization {Business}`, daily ingest
   packets, and Skribby meeting transcript intake when those sources are in
   scope;
6. mine sources into redacted source events;
7. propose model-change packages for human review;
8. never promote accepted truth by itself.

The trust boundary is the product. The agent may mine, compile, propose,
validate, and prepare review packets. The human decides what becomes accepted
truth.

## Current status

The repository is ready for the live bootstrap experiment on a selected ref that
contains `adapters/openclaw/BOOTSTRAP.md`. Use main only after PR #6 is merged,
or give the agent an exact branch, commit, or archive that contains the final
package layout.

Repository:

- GitHub: https://github.com/Vladick-Pick/business-ontology
- Bootstrap ref: selected ref containing `adapters/openclaw/BOOTSTRAP.md`
- Bootstrap package: `adapters/openclaw/`
- Workspace generator: `scripts/bootstrap_openclaw_workspace.py`

The experiment must verify that `adapters/openclaw/BOOTSTRAP.md` exists at the
selected ref before asking any setup questions.

Current readiness level:

- Ready: repository bootstrap package.
- Ready: first Telegram message for a blank OpenClaw agent.
- Ready: private agent workspace generator.
- Ready: source setup contracts for Telegram groups, daily ingest, Skribby
  transcript intake, optional gog Google Workspace, Google Drive, transcripts,
  and dashboards. Fireflies is superseded by Skribby for this live-test path.
- Ready: pass/fail gates for the live test.
- Ready: local tests, eval fixtures, and link validation.
- Not production-ready: live OpenClaw connector runtime, production OAuth,
  background scheduling, networked MCP server, GBrain sync, real captured runs,
  and active Telegram daily scanning without host runtime support.

## Experiment user scenario

The human starts with:

- a clean blank OpenClaw agent;
- the agent already connected to Telegram;
- no existing `AGENTS.md`, `SOUL.md`, `TOOLS.md`, or private workspace for this
  agent;
- observer access to the agent server, sessions, events, tool calls, and
  workspace.

The human sends the repository URL:

```text
https://github.com/Vladick-Pick/business-ontology
```

The agent should then:

1. clone or install the repository;
2. verify that `adapters/openclaw/BOOTSTRAP.md` exists;
3. read `adapters/openclaw/BOOTSTRAP.md`;
4. read `adapters/openclaw/live-test/README.md`;
5. create its private workspace with
   `scripts/bootstrap_openclaw_workspace.py`;
6. ask for the Markdown/Git model export repository and GitHub access path;
7. run `agent-os/FIRST_SESSION_PLAYBOOK.md` Block A: contour;
8. run Block B: connect at least one source, starting with mapped Telegram
   groups named `Systematization {Business}` when available;
9. record daily ingest through `skills/daily-ingest/SKILL.md`, including scan
   time, timezone, cursors, and readiness label;
10. record Skribby meeting transcript intake through
   `adapters/openclaw/MEETING_TRANSCRIPTS.md` when meeting links are in scope;
11. ask about gog only as an optional Block B source, not as a mandatory setup
   question;
12. refuse secrets in Telegram;
13. keep raw source payloads out of the accepted model repository;
14. report the current readiness label: `setup-only`, `source-connected`,
   `scheduled`, or `live-proven`.

## First message to the agent

Use `adapters/openclaw/live-test/LIVE_TEST_FIRST_MESSAGE.md` as the canonical
first prompt.

Short form:

```text
Install and bootstrap this repository as your business ontology operating
package:

https://github.com/Vladick-Pick/business-ontology

Read adapters/openclaw/BOOTSTRAP.md and
adapters/openclaw/live-test/README.md. Create your private agent workspace,
ask for GitHub model repository access, verify the selected ref, then follow
agent-os/FIRST_SESSION_PLAYBOOK.md: Block A contour, Block B sources, and Block
C rhythm. For sources, prefer Telegram groups named `Systematization
{Business}`, daily ingest through skills/daily-ingest, and Skribby meeting
transcripts. gog is optional Block B source setup, not a mandatory question.
```

## Source setup truth

Telegram:

- The live test validates approved groups named `Systematization {Business}`,
  source mapping, daily scan time, timezone, cursor storage, and source-event
  output.
- Daily interpretation uses `skills/daily-ingest/SKILL.md`.
- Telegram reaches `source-connected` only when a source can be read. It reaches
  `scheduled` only when rhythm and host scheduling are recorded. It reaches
  `live-proven` only after a connected run produces source events,
  model-change packages, and a digest or review handoff.

Skribby and Fireflies:

- Skribby is the meeting transcript path for this live-test flow.
- Fireflies is superseded by Skribby in this live-test flow; keep Fireflies
  setup files as legacy provider documentation only.
- The agent uses `adapters/openclaw/MEETING_TRANSCRIPTS.md` for meeting links
  posted in mapped Telegram groups.
- Raw transcripts stay out of the accepted model repository.

gog Google Workspace:

- gog is the planned Google Workspace path for Drive, Docs, and Calendar.
- The agent asks about gog only when the owner chooses it as an optional Block B
  source. It is not a required live-test question.
- Credentials stay outside Telegram and outside repository files.

Accepted model repository:

- The Markdown/Git accepted model export must live in a user-owned or
  company-owned GitHub repository.
- The target canonical model store is the operational truth layer. This
  experiment has a local SQLite operational-store subset for queue/review
  state, semantic details, and workflows; it does not ship the production
  canonical-store service.
- The agent may use a GitHub App, a host-selected repository authorization
  flow, or a setup-only dry run.
- If no access path exists, the agent marks GitHub as
  `requested-not-configured` and must not claim branch or pull request write
  readiness.

## Primary source files

Product target:

- `docs/product-target-state.md`
- `docs/product-resident-analyst.md`
- `specs/BUSINESS-ONTOLOGY-RESIDENT.md`
- `README.md`

Experiment entrypoints:

- `docs/openclaw-live-experiment.md`
- `adapters/openclaw/README.md`
- `adapters/openclaw/BOOTSTRAP.md`
- `adapters/openclaw/FIRST_MESSAGE.md`
- `adapters/openclaw/live-test/LIVE_TEST_FIRST_MESSAGE.md`

Live-test operations:

- `adapters/openclaw/live-test/README.md`
- `adapters/openclaw/live-test/OPERATOR_CHECKLIST.md`
- `adapters/openclaw/live-test/OBSERVER_PROTOCOL.md`
- `adapters/openclaw/live-test/AUTHORIZATION_RUNBOOK.md`
- `adapters/openclaw/live-test/PASS_FAIL_GATES.md`

Source setup:

- `adapters/openclaw/source-setup/telegram.md`
- `adapters/openclaw/source-setup/fireflies.md` — Fireflies is superseded by
  Skribby for this live-test path.
- `adapters/openclaw/source-setup/gog-google-workspace.md`
- `adapters/openclaw/source-setup/google-drive.md`
- `adapters/openclaw/source-setup/transcripts.md`
- `adapters/openclaw/source-setup/dashboard.md`

Workspace generation:

- `scripts/bootstrap_openclaw_workspace.py`
- `adapters/openclaw/templates/workspace/`

Quality gates:

- `tests/test_openclaw_self_bootstrap.py`
- `tests/test_openclaw_live_test_readiness.py`
- `tests/test_openclaw_workspace_template.py`
- `evals/`

## Pass/fail summary

The experiment passes as a bootstrap test if the blank agent installs the
repository, reads the bootstrap package, creates its private workspace, asks the
correct authorization and first-session questions, preserves the storage
boundaries, and reports a truthful readiness label from the first-session
playbook.

The experiment fails if the agent asks for secrets in Telegram, cannot find the
bootstrap package, writes raw source payloads into the accepted model
repository, claims GitHub write access without an access path, marks Telegram
active without host runtime support, or treats `/approve` as permission to merge
accepted truth by itself.

## Observer notes

During the experiment, capture:

- OpenClaw session id;
- Telegram inbound message ids;
- repository checkout ref;
- workspace file tree;
- tool calls and tool results;
- authorization step reached;
- source cursor state reached;
- the final readiness message.

If the agent diverges, stop the test and compare the behavior against
`adapters/openclaw/live-test/PASS_FAIL_GATES.md`.

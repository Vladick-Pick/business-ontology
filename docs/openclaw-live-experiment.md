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
2. separate accepted model, agent workspace, and raw source layer;
3. ask the human where the accepted model repository must live;
4. ask for Telegram daily scan setup, Fireflies transcript enablement, and gog
   Google Workspace enablement;
5. run the first ontology session;
6. mine sources into redacted source events;
7. propose model-change packages for human review;
8. never promote accepted truth by itself.

The trust boundary is the product. The agent may mine, compile, propose,
validate, and prepare review packets. The human decides what becomes accepted
truth.

## Current status

The repository is ready for the live bootstrap experiment on `main`.

Repository:

- GitHub: https://github.com/Vladick-Pick/business-ontology
- Bootstrap commit: `9c601375ca365f487842a48af12820f176e6849f`
- Bootstrap package: `bootstrap/openclaw/`
- Workspace generator: `scripts/bootstrap_openclaw_workspace.py`

The experiment should use the default branch only after confirming that
`bootstrap/openclaw/BOOTSTRAP.md` exists there.

Current readiness level:

- Ready: repository bootstrap package.
- Ready: first Telegram message for a blank OpenClaw agent.
- Ready: private agent workspace generator.
- Ready: source setup contracts for Telegram, Fireflies, gog Google Workspace,
  Google Drive, transcripts, and dashboards.
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
2. verify that `bootstrap/openclaw/BOOTSTRAP.md` exists;
3. read `bootstrap/openclaw/BOOTSTRAP.md`;
4. read `bootstrap/openclaw/live-test/README.md`;
5. create its private workspace with
   `scripts/bootstrap_openclaw_workspace.py`;
6. ask for the accepted model repository and GitHub access path;
7. ask for Telegram groups, daily scan time, and timezone;
8. ask whether Fireflies is enabled;
9. ask whether gog Google Workspace is enabled;
10. refuse secrets in Telegram;
11. keep raw source payloads out of the accepted model repository;
12. say `Ready for the first ontology session`.

## First message to the agent

Use `bootstrap/openclaw/live-test/LIVE_TEST_FIRST_MESSAGE.md` as the canonical
first prompt.

Short form:

```text
Install and bootstrap this repository as your business ontology operating
package:

https://github.com/Vladick-Pick/business-ontology

Read bootstrap/openclaw/BOOTSTRAP.md and
bootstrap/openclaw/live-test/README.md. Create your private agent workspace,
ask for GitHub model repository access, ask for Telegram daily scan setup,
ask whether Fireflies and gog Google Workspace are enabled, and then say:
Ready for the first ontology session.
```

## Source setup truth

Telegram:

- The live test can always validate Telegram setup questions and cursor
  registration.
- Telegram is `active` only if the OpenClaw host runtime provides message
  capture, durable cursor storage, scheduling, and source-event output.
- Without those runtime pieces, Telegram status is `setup-only`.

Fireflies:

- Fireflies is a transcript source, not a truth gate.
- The agent asks whether it is enabled and then uses one approved mode: meeting
  URL, transcript id/file, or project meeting mode.
- Raw transcripts stay out of the accepted model repository.

gog Google Workspace:

- gog is the planned Google Workspace path for Drive, Docs, and Calendar.
- The agent asks whether it is enabled, then asks for OAuth setup, Drive folder,
  Docs scope, and Calendar filters.
- Credentials stay outside Telegram and outside repository files.

Accepted model repository:

- The accepted model must live in a user-owned or company-owned GitHub
  repository.
- The agent may use a GitHub App, a host-selected repository authorization
  flow, or a setup-only dry run.
- If no access path exists, the agent marks GitHub as
  `requested-not-configured` and must not claim branch or pull request write
  readiness.

## Primary source files

Product target:

- `docs/product-resident-analyst.md`
- `AGENT-SPEC.md`
- `README.md`

Experiment entrypoints:

- `docs/openclaw-live-experiment.md`
- `bootstrap/openclaw/README.md`
- `bootstrap/openclaw/BOOTSTRAP.md`
- `bootstrap/openclaw/FIRST_MESSAGE.md`
- `bootstrap/openclaw/live-test/LIVE_TEST_FIRST_MESSAGE.md`

Live-test operations:

- `bootstrap/openclaw/live-test/README.md`
- `bootstrap/openclaw/live-test/OPERATOR_CHECKLIST.md`
- `bootstrap/openclaw/live-test/OBSERVER_PROTOCOL.md`
- `bootstrap/openclaw/live-test/AUTHORIZATION_RUNBOOK.md`
- `bootstrap/openclaw/live-test/PASS_FAIL_GATES.md`

Source setup:

- `bootstrap/openclaw/source-setup/telegram.md`
- `bootstrap/openclaw/source-setup/fireflies.md`
- `bootstrap/openclaw/source-setup/gog-google-workspace.md`
- `bootstrap/openclaw/source-setup/google-drive.md`
- `bootstrap/openclaw/source-setup/transcripts.md`
- `bootstrap/openclaw/source-setup/dashboard.md`

Workspace generation:

- `scripts/bootstrap_openclaw_workspace.py`
- `bootstrap/openclaw/workspace-templates/`

Quality gates:

- `tests/test_openclaw_self_bootstrap.py`
- `tests/test_openclaw_live_test_readiness.py`
- `tests/test_openclaw_workspace_template.py`
- `evals/`

## Pass/fail summary

The experiment passes as a bootstrap test if the blank agent installs the
repository, reads the bootstrap package, creates its private workspace, asks the
correct authorization and source setup questions, preserves the storage
boundaries, and reaches the first ontology session.

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
`bootstrap/openclaw/live-test/PASS_FAIL_GATES.md`.

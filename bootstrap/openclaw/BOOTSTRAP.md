# Bootstrap procedure for a blank OpenClaw agent

You are a resident business analyst agent. Your job is to keep a company's
business ontology real, current, and reviewable.

Follow this procedure after the human sends you this repository.

## 1. Install or locate the skill

Locate this repository in your filesystem. Read:

- `SKILL.md`
- `AGENT-SPEC.md`
- `AGENTS.md`
- `references/model-pack.md`
- `references/source-intake.md`
- `references/model-change-package.md`
- `references/review-ux.md`
- `bootstrap/openclaw/HUMAN_ACCESS.md`
- `bootstrap/openclaw/REVIEW_PROTOCOL.md`
- `bootstrap/openclaw/source-setup/telegram.md`
- `bootstrap/openclaw/source-setup/fireflies.md`
- `bootstrap/openclaw/source-setup/gog-google-workspace.md`

If this is a live test with a blank Telegram-connected OpenClaw agent, also
read:

- `bootstrap/openclaw/live-test/README.md`
- `bootstrap/openclaw/live-test/OPERATOR_CHECKLIST.md`
- `bootstrap/openclaw/live-test/OBSERVER_PROTOCOL.md`
- `bootstrap/openclaw/live-test/AUTHORIZATION_RUNBOOK.md`
- `bootstrap/openclaw/live-test/PASS_FAIL_GATES.md`

If you cannot read these files, stop and ask the human for a merged repository,
the exact branch, a checkout path, or an archive URL that contains
`bootstrap/openclaw/`. Do not continue from a default branch that is missing the
bootstrap package.

## 2. Create your private agent workspace

Run the bootstrap script from the repository root:

```bash
python3 scripts/bootstrap_openclaw_workspace.py \
  --workspace /path/to/agent-workspace \
  --module "Company baseline"
```

If the human has already selected a model repository, include it:

```bash
python3 scripts/bootstrap_openclaw_workspace.py \
  --workspace /path/to/agent-workspace \
  --module "Company baseline" \
  --ontology-repo-url https://github.com/OWNER/REPO
```

This workspace is your operational home. It may contain your `AGENTS.md`,
`SOUL.md`, `TOOLS.md`, `SOURCES.md`, local queues, digests, traces, cursors, and
redacted source events. It is not the accepted ontology repository.

## 3. Establish the accepted model repository

Before writing accepted ontology, ask the human where the accepted model should
live.

Preferred options:

1. The human provides an existing GitHub repository.
2. The human creates an empty private repository and provides the URL.
3. The human explicitly authorizes you to create a repository under their
   GitHub account or organization.

The repository must be a user-owned GitHub repository or company-owned GitHub
repository. The human must be able to read it directly. Only the accepted model
belongs there.

## 4. Verify access before writing

Check and report:

- repository URL;
- visibility if available;
- whether the human can open it;
- whether you can read contents;
- whether you can create a branch or pull request;
- whether accepted-branch direct writes are blocked or avoided.

If you cannot verify human read access, do not continue with model bootstrap.

## 5. Announce readiness

Send the human a short Telegram message:

```text
Bootstrap is ready.

I have a private agent workspace for my instructions and runtime state.
The accepted business model will live in: <repo or pending choice>.
Raw sources will stay outside the model repo and enter only as redacted source events.
I have asked for Telegram daily scan time, Fireflies enablement, and gog Google Workspace enablement.

I am ready for the first ontology session.
First question: what business reality are we modeling first: the whole company,
one module, one production system, one product line, or one new business idea?
```

## 6. After the first session

When the human pauses or ends the session:

1. Summarize accepted facts, conflicts, unknowns, and next questions.
2. Prepare a model-change package or branch for review.
3. Ask for approval before committing accepted model changes.
4. Start source setup only after the human confirms the first model boundary.
5. Use `source-setup/` instructions for Telegram daily scans, Fireflies
   transcripts, gog Google Workspace, Google Drive, and dashboards.
6. For the live test, keep `LIVE_TEST_STATUS.md`, `AUTHORIZATION_CHECKLIST.md`,
   `SOURCE_CURSORS.md`, and `OBSERVER_PROTOCOL.md` current in the private
   workspace.

# OpenClaw workspace contract

This adapter expects a private workspace for the Telegram-connected resident
agent. The workspace is generated from `templates/workspace/` by:

```bash
python3 scripts/bootstrap_openclaw_workspace.py \
  --workspace <workspace-path> \
  --module "<company-or-module-name>" \
  --ontology-repo-url "<user-owned-model-repo-or-ask-human>"
```

## Workspace responsibilities

The workspace stores:

- OpenClaw-facing instructions;
- source setup state;
- source cursors;
- runtime config;
- model-pack config;
- redacted source events;
- model-change packages;
- review packages;
- traces;
- digests;
- operator live-test notes.

The workspace does not store raw Telegram messages, raw transcripts, Google
Drive document bodies, OAuth tokens, or accepted model truth.

## First successful state

The OpenClaw agent is ready for the first ontology session when:

- it has read `BOOTSTRAP.md` and `adapters/openclaw/BOOTSTRAP.md`;
- it has created or found its private workspace;
- it knows whether the model repository is existing, requested, or not yet
  authorized;
- it can name which source connectors are available and which are only planned;
- it can ask the first ontology session question without asking the human to
  design the whole system.

## Daily source scan state

Daily source scans require:

- registered source entries;
- read-only access or manual export path;
- cursor storage in `SOURCE_CURSORS.md` or the operational store;
- normalized source-event writer;
- review package output path;
- human review channel.

If any of these are missing, the agent records `requested-not-configured` and
asks the next setup question.

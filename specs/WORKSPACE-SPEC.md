# Workspace spec

This spec defines the private workspace a resident business analyst agent keeps
beside the model repository.

The workspace is not the accepted model. It is the agent's operating room:
instructions, cursors, source setup state, run logs, review queue pointers, and
human-facing session state.

## Required files

The workspace should contain these files after bootstrap:

| File | Purpose |
|---|---|
| `AGENTS.md` | Host-neutral operating instructions for the resident analyst. |
| `CLAUDE.md` | Claude Code adapter copy when the host reads that file. |
| `SOUL.md` | Stable identity and product stance. |
| `TOOLS.md` | Tools that are available, unavailable, requested, or blocked. |
| `MODEL_STORAGE.md` | Where the model repo/export/store is, and what is writable. |
| `COMMUNICATION_POLICY.md` | How the agent talks to humans and asks setup/model questions. |
| `SESSION_STATE.md` | Current bootstrap/session status, next action, blockers. |
| `LEARNINGS.md` | Durable lessons from tests and operator corrections. |
| `SOURCES.md` | Connected and planned source inventory. |
| `SOURCE_CURSORS.md` | Per-source daily scan cursor state. |
| `REVIEW_PROTOCOL.md` | Human approval flow and staged-change rules. |
| `RUNBOOK.md` | Operator commands and recovery steps. |
| `workspace-state.json` | Machine-readable installed agent, model target, and model language state. |
| `source-instances.json` | Machine-readable source connection registry. |
| `live-proofs/proofs.json` | Machine-readable proof ledger for source capabilities. |

OpenClaw workspaces are generated from `templates/workspace/` by
`scripts/bootstrap_openclaw_workspace.py`. Codex and Claude Code adapters may
copy the same template set and add host-specific instruction files.

## Separation of storage

The workspace may contain:

- agent instructions;
- connector setup notes without secrets;
- source cursor ids and timestamps;
- source instance ids, connector refs, scheduler refs, and live proof refs;
- redacted run summaries;
- review queue references;
- model repository path and branch policy;
- tool availability state.

The workspace must not contain:

- raw Telegram messages;
- raw Fireflies transcripts;
- raw Google Drive document bodies;
- OAuth tokens;
- bearer headers;
- passwords;
- personal contact data;
- accepted model facts that bypass the review protocol.

Raw source data stays in source systems or the host's approved raw-source
storage. Accepted model state stays in the model repository/export and, in the
target architecture, the canonical model store.

## Bootstrap state machine

The workspace bootstrap has five states:

1. `package-read`: the agent has read `BOOTSTRAP.md`, `agent-package.yaml`, and
   its host adapter.
2. `workspace-created`: required workspace files exist.
3. `model-target-known`: the user has selected or authorized the model
   repository target.
4. `first-session-ready`: the agent can start baseline ontology mining.
5. `source-setup-ready`: source setup instructions are ready and scheduled
   scans can be configured after the first session.

Do not skip `model-target-known`. A resident analyst without a known model
target can chat, but cannot preserve accepted model state.

## Writable areas

The agent may write only to:

- its private workspace;
- staged proposal areas defined by the model repository;
- redacted run/event logs;
- generated review/digest artifacts;
- source cursors.
- source instance registry and live proof ledger.

Accepted model writes are human-gated. If the host gives broader file access,
the agent still follows the logical boundary: propose first, promote only after
human review.

## Workspace update rule

When a setup fact changes, update the exact workspace file that owns it:

- tool capability changes -> `TOOLS.md`;
- source cursor changes -> `SOURCE_CURSORS.md`;
- source connection or proof changes -> `source-instances.json` and
  `live-proofs/proofs.json`;
- model repo or store location changes -> `MODEL_STORAGE.md`;
- human communication correction -> `COMMUNICATION_POLICY.md`;
- experiment lesson -> `LEARNINGS.md`;
- blocked install step -> `SESSION_STATE.md`.

Do not hide durable setup facts only in chat.

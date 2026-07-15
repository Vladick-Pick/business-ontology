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
| `runtime-config.json` or `runtime-config.example.json` | Machine-readable runtime paths, including the single private `raw_source_root` and explicit `viewer_publication` capability. |
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
- tool availability state;
- one configured private raw-source tree when the deployment uses local raw
  storage:

  ```text
  <raw_source_root>/telegram/<run>/...
  <raw_source_root>/meetings/<meeting>/...
  ```

`raw_source_root` is one path in the workspace runtime config. Relative values
are resolved from the runtime config directory; the workspace template uses
`raw`. Telegram and meeting runtimes must derive their source-specific child
directories from this one value. They must not define independent current
output roots.

Outside `raw_source_root`, the workspace must not contain:

- raw Telegram messages;
- raw Fireflies transcripts;
- raw Google Drive document bodies;
- OAuth tokens;
- bearer headers;
- passwords;
- personal contact data;
- accepted model facts that bypass the review protocol.

`raw_source_root` is a separate logical storage zone even when it is physically
under the private workspace. It must be excluded from Git, normal agent
context, support bundles, model exports, traces, logs, digests, and chat. Raw
bodies do not enter derived workspace artifacts. Derived processing state keeps
only source locators, SHA-256 hashes, counts/status, and the minimum redacted
metadata required for review. Accepted model state stays in the model
repository/export and, in the target architecture, the canonical model store.

## Viewer publication capability

`viewer_output_path` owns the generated static files. `viewer_publication`
owns delivery and has one explicit mode:

```json
{
  "viewer_publication": {
    "mode": "workspace-only",
    "public_url": ""
  }
}
```

`workspace-only` is the portable default. `static-url` requires an
operator-provided credential-free HTTPS directory URL. `tailscale-funnel`
requires a verified host capability and one non-colliding path. The agent may
configure these existing capabilities with
`scripts/configure_viewer_publication.py`; it may not create a website project,
repository, provider account, or domain. A public URL is shareable only when
the current publish report records `publication.status: verified`.

The viewer's accepted layer comes from the accepted export. Pending operational
packages may contribute only a labelled, safe working projection. Raw evidence,
transcripts, message bodies, source locators, secrets, and PII are never public
viewer inputs.

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
- source cursors;
- source instance registry and live proof ledger;
- the configured private `raw_source_root` for source acquisition only.

Accepted model writes are human-gated. If the host gives broader file access,
the agent still follows the logical boundary: propose first, promote only after
human review.

## Workspace update rule

When a setup fact changes, update the exact workspace file that owns it:

- tool capability changes -> `TOOLS.md`;
- source cursor changes -> `SOURCE_CURSORS.md`;
- source connection or proof changes -> `source-instances.json` and
  `live-proofs/proofs.json`;
- raw-source location changes -> `raw_source_root` in runtime config, followed
  by backup and count/hash reconciliation before old copies are removed;
- viewer delivery changes -> `viewer_publication` in runtime config, followed
  by publish and public hash verification before sharing the URL;
- model repo or store location changes -> `MODEL_STORAGE.md`;
- human communication correction -> `COMMUNICATION_POLICY.md`;
- experiment lesson -> `LEARNINGS.md`;
- blocked install step -> `SESSION_STATE.md`.

Do not hide durable setup facts only in chat.

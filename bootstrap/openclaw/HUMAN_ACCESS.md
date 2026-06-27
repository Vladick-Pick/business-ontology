# Human access contract

The accepted model is a company asset. The target operational truth is a
canonical model store. The human-readable Markdown/Git export must live in a
user-owned GitHub repository or company-owned GitHub repository, not in an
agent-provider account.

The human must be able to read the accepted model directly. Telegram summaries
are useful, but they are not a substitute for repository access.

## Storage split

| Layer | Owner | Location | Contains | Must not contain |
|---|---|---|---|---|
| Canonical model store | Human or company | Target operational store | Accepted model state, evidence, decisions, validity windows, supersession, review questions, source cursors, run state | Raw transcripts, private messages, secrets |
| Markdown/Git export | Human or company | User-owned GitHub repository | Ontology cards, source map, decisions, drift, review history, open questions | Agent memory, connector cursors, raw transcripts, private messages, secrets |
| Agent workspace | Agent runtime owner | OpenClaw or local runtime workspace | `AGENTS.md`, `SOUL.md`, `TOOLS.md`, queues, state, traces, digests | Canonical model ownership |
| Raw source layer | Source system owner | Drive, Telegram, transcript store, dashboard, CRM, private storage | Original artifacts and raw operational data | Instructions for the agent |

## Access modes

The agent should offer three paths:

1. **Existing repository**: the human provides a GitHub URL. The agent requests
   repository-scoped read/write or branch/PR access.
2. **Human-created repository**: the human creates an empty private repository
   and provides the URL. This is the cleanest default for company data.
3. **Agent-created repository**: the human explicitly authorizes repository
   creation under the human account or organization. The agent must report the
   owner, repository name, visibility, and requested permissions before action.

For live tests, the GitHub access path must be explicit. Acceptable paths are a
GitHub App installation, a host-native selected repository authorization flow,
or a setup-only dry run where the agent records that write access is not yet
configured. The setup-only path cannot be reported as branch or pull request
write readiness.

## Required checks

Before model initialization, the agent reports:

- accepted model repository URL or `pending`;
- who owns the repository;
- whether the human can read it;
- whether the agent can create a branch or pull request;
- whether direct writes to the accepted branch are avoided;
- whether raw source storage is separate from the model repository.

If any check fails, the agent pauses and asks for access correction.

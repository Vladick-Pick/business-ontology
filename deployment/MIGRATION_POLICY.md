# Migration policy

This policy controls breaking or structural package changes.

## Current migration

Version `0.11.12` adds an explicit viewer publication slot and a per-agent
OpenClaw Sites-tool boundary without changing accepted model truth. Run
`scripts/migrate_workspace_v0_11_12.py` after the package update. When no target
exists it creates `workspace-only`; it preserves an existing configured target.
With `--apply-openclaw` it merges `sites.*` and `codex_apps.sites.*` into that
agent's `tools.deny` list and preserves all other tool policy.

The migration stores the exact runtime config and pre-change agent tool object
under `agent-state/migrations/v0.11.12/backup/`. Rollback restores both. A host
mutation therefore requires host-aware rollback; it never resets global tools,
foreign agents, routes, services, or cron jobs.

## Previous workspace behavior migration

Version `0.11.0` changes installed workspace behavior without changing accepted
model truth. Run `scripts/migrate_workspace_v0_11_0.py` for each v0.10.6
workspace after the package update. The migration updates package-owned policy
files, introduces the private raw root, preserves and reconciles legacy raw
copies, installs the scoped owner-chat guard, explicitly configures the silent
heartbeat, and reconciles only the package-owned reminder declaration when a
complete owner-confirmed schedule already exists.

The migration keeps a file and OpenClaw host inventory under
`agent-state/migrations/v0.11.0/backup/`. Rollback restores the previous
behavior files, per-agent heartbeat, guard configuration, and managed reminder;
reconciled raw copies remain in place. Roll shared-Gateway agents back in the
reverse order in which they were activated, then verify every remaining agent.

No reminder schedule is inferred. An unconfigured reminder remains absent.
Raw originals are not deleted by this migration.

## Previous model migration

Version `0.10.0` turns data-model v2 transition diagnostics into hard errors.
The gate covers deprecated v1 aliases, missing v2 structural fields, unresolved
owners, and duplicate `owns` plus `part-of` facts. Package update validates a
temporary model copy before flipping `package/current`; if validation fails,
the update exits with `migration-required` and leaves both the package pointer
and the real model repository unchanged.

The required response is a model migration package, review package, and human
approval. Do not auto-rewrite the accepted model as part of package update.

## Previous layout migration

The final agent-package layout retires:

```text
agent-skills/
bootstrap/openclaw/
templates/openclaw-workspace/
AGENT-SPEC.md
```

The replacement paths are:

```text
skills/
adapters/openclaw/
templates/workspace/
specs/BUSINESS-ONTOLOGY-RESIDENT.md
```

Root `SKILL.md` is now a package router. The operational ontology skill is:

```text
skills/business-ontology/SKILL.md
```

## Migration actions for installed agents

1. Pull the package update.
2. Update any instruction that points to retired paths.
3. Keep the existing agent workspace state.
4. Do not regenerate source cursors.
5. Do not move raw source data into the model repo.
6. Run layout/bootstrap verification.
7. Tell the human what changed:
   - skills moved to `skills/`;
   - OpenClaw moved to `adapters/openclaw/`;
   - workspace templates moved to `templates/workspace/`;
   - root skill routes package installation.

## Compatibility

Do not keep duplicate compatibility directories in the package. Duplicate paths
make blank agents choose the wrong instruction set. If a previous install has
old files, migrate references to the new paths and leave local backups outside
the package repository.

## Breaking change rule

A migration is required when the package changes:

- path layout;
- required workspace file names;
- schema required fields;
- relation vocabulary;
- status vocabulary;
- review approval semantics;
- source cursor semantics;
- accepted-store application semantics.

Each migration needs a test that catches the old behavior.

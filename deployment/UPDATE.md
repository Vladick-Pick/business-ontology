# Update

Use this procedure when an installed agent or package checkout is updated.

## Rule

Update the package, workspace, and model repository separately.

| Layer | Update command/action | Do not overwrite |
|---|---|---|
| Package repository | Pull or install the new package version. | None, this is package code/docs. |
| Agent workspace | Apply template migrations only when required. | Source cursors, model repo target, run logs, review queue, tool state. |
| Model repository/store | Apply approved model changes only. | Accepted truth without human review. |

## Package update steps

1. Read `CHANGELOG.md`.
2. Read `deployment/MIGRATION_POLICY.md`.
3. Check `agent-package.yaml` for path changes.
4. Run the focused tests for the changed area.
5. If templates changed, compare with installed workspace files before copying.
6. Record the installed version in the workspace session state.

For package releases `v0.10.0` and newer, `apply_package_update.py` validates a
temporary copy of the model repository with the strict data-model v2 transition
gate. Exit code `3` means the package was not flipped and the real model was not
changed. Prepare a reviewed model migration package before retrying the update.

The install report also includes `model_support_contract`. Values `missing`,
`invalid`, `drift`, and `unsupported-copied-validator` mean the package update
must create a reviewable support-file proposal for the model repository. The
updater must not write those files directly.

## Workspace migration steps

When a template changes:

1. Identify whether the target workspace file is generated-only or locally
   edited.
2. If locally edited, patch only the required block.
3. Preserve cursor and authorization state.
4. Add a line to `LEARNINGS.md` when the behavior changes.
5. Ask the human before migrating anything that changes source access,
   accepted model target, review ownership, or digest schedule.

For the v0.10.6 to v0.11.x transition, install the latest compatible patch:

```bash
python3 scripts/migrate_workspace_v0_11_0.py \
  --workspace <workspace> \
  --agent-id <openclaw-agent-id> \
  --dry-run

python3 scripts/apply_package_update.py \
  --install-root <agent-root> \
  --to v0.11.8

python3 <agent-root>/package/current/scripts/migrate_workspace_v0_11_0.py \
  --workspace <workspace> \
  --agent-id <openclaw-agent-id> \
  --apply-openclaw \
  --openclaw-bin <verified-openclaw-launcher> \
  --openclaw-node-bin-dir <verified-node-bin-dir>
```

Then restart the Gateway and verify the loaded plugin, exact per-agent
heartbeat, managed reminder declaration, raw reconciliation, and redacted
system-health snapshot. Do not delete legacy raw originals during this release.

## Model migration steps

Accepted model migration is a model change. It requires:

- migration package;
- review package;
- human approval;
- changelog entry;
- ability to answer what changed and why.

Do not apply schema or relation changes silently to accepted model files.

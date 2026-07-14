# OpenClaw Package Update Policy

This policy controls how an installed OpenClaw resident analyst consumes
package releases. It updates package code and instructions only. Workspace
state and the accepted model remain separate.

## Install Layout

```text
<agent-install>/
  package/
    .cache.git/
    releases/v0.9.1/
    releases/v0.10.0/
    current -> releases/v0.10.0
  workspace/
    PACKAGE_VERSION.lock
    SOURCE_CURSORS.md
    INTERACTION_CONTRACT.md
  model-repo/
```

The agent reads package files through `package/current`. Release directories are
immutable materializations of Git release tags.

## Invariants

1. The updater writes only under `package/` and to
   `workspace/PACKAGE_VERSION.lock`.
2. The updater never gives the real `model-repo` path to code from the new
   release. For validation it copies the model working tree without `.git` to a
   temporary directory and passes only that copy to the new validator.
3. Model changes, including schema migrations, are proposed as model-change
   packages and require ordinary human review.
4. Workspace files are not regenerated over existing files. Template changes
   require an explicit workspace migration proposal.
5. A schema-breaking release that reports model validation errors is not
   installed. The agent reports that model migration is required.
6. Updates come only from `vX.Y.Z` release tags on the pinned remote. Branches
   and `main` are not install targets. The lock stores tag, commit SHA, and a
   sanitized canonical remote URL only.
7. Retention keeps the current and previous release. It never deletes the
   release directory containing the running updater process.
8. After a successful flip, the next agent action is Position recovery from
   `skills/business-ontology/SKILL.md`.
9. Update approval comes only from the owner in direct chat. Group requests are
   routed to owner DM and are not authority to update.
10. `check_package_updates.py` and `apply_package_update.py` use
    `package/.update.lock`. A live holder causes exit 5 with no filesystem
    changes.

## Weekly Check Flow

1. `scripts/check_package_updates.py --lock workspace/PACKAGE_VERSION.lock`
   fetches tags into `package/.cache.git` and compares the lock with the latest
   `vX.Y.Z` tag.
2. If a newer release exists, the agent records one `human_request` with
   `kind=migration`, the version, a short changelog summary, and whether a
   schema or workspace gate may require migration. The next configured owner
   reminder may surface that one current request; the heartbeat never does.
3. The agent waits for owner approval in direct chat.
4. On approval, `scripts/apply_package_update.py --to vX.Y.Z --install-root
   <agent-install> --model-repo <model-repo>` materializes the release from the
   local cache, runs `scripts/package_self_test.py` from the new release,
   validates a temporary copy of the model, flips `package/current`, updates the
   lock, and reports the result.
5. For `v0.10.0+`, validation uses the strict data-model v2 transition gate.
   Deprecated v1 aliases, missing v2 structural fields, unresolved owners, and
   duplicate containment facts block the package flip.
6. If validation returns `migration-required`, the agent prepares a model-change
   migration package and waits for review. It does not flip `current`.

## v0.11.0 Workspace Activation

The package flip does not overwrite workspace behavior files. After v0.11.0 is
active, run `scripts/migrate_workspace_v0_11_0.py` from `package/current` with
the exact workspace and OpenClaw agent id. The migration backs up affected
workspace and package-owned host state, updates the communication/review/tool
policy, reconciles the private raw root, configures the silent per-agent
heartbeat, installs the scoped owner-chat guard, and reconciles only an
owner-confirmed reminder declaration.

Restart the Gateway after plugin activation. Verify the runtime plugin hooks,
the per-agent heartbeat, all cron fields, the redacted system-health snapshot,
and the installed package again. Do not call the workspace migration complete
from the package pointer alone.

`package_self_test.py` is the installed-release self-test contract: offline,
bounded by timeouts, fixture-only, and no live connectors.

## Rollback Flow

Run:

```bash
python3 package/current/scripts/apply_package_update.py \
  --install-root <agent-install> \
  --rollback
```

Rollback verifies the previous release directory and commit SHA from
`PACKAGE_VERSION.lock`, flips `package/current` back, swaps the current and
previous lock entries, and does not read the model repository.

For v0.11.0, restore the workspace/host migration backup before or together
with the package rollback. Reconciled raw copies are preserved. On a shared
Gateway, roll agents back in reverse activation order and verify the agents
that remain active after each step.

## Deploy Gate

On the live OpenClaw instance, verify whether the gateway rereads skill content
through `package/current` after the symlink changes. If it caches content, add a
host-specific gateway restart after the flip. That restart is deploy
configuration, not company-model truth.

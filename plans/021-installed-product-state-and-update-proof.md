# Plan 021: Installed product state and update proof

> **Executor instructions**: Follow this plan step by step. Run the drift check
> first. Do not treat a manual clone, copied folder, or edited symlink as a
> valid package update. If a STOP condition occurs, stop and report.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 90f767f..HEAD -- \
>   scripts/apply_package_update.py scripts/check_package_updates.py \
>   scripts/package_self_test.py skills/package-update/SKILL.md \
>   adapters/openclaw/BOOTSTRAP.md adapters/openclaw/WORKSPACE.md \
>   templates/workspace specs/UPDATE-SPEC.md tests
> git diff --stat -- \
>   scripts/apply_package_update.py scripts/check_package_updates.py \
>   scripts/package_self_test.py skills/package-update/SKILL.md \
>   adapters/openclaw/BOOTSTRAP.md adapters/openclaw/WORKSPACE.md \
>   templates/workspace specs/UPDATE-SPEC.md tests
> ```
>
> Planned from package `0.10.0`, commit `90f767f`. If update scripts or
> workspace templates changed, reconcile this plan before editing.

## Status

- **Status**: DONE (local, review loop complete)
- **Priority**: P1
- **Effort**: M-L
- **Risk**: HIGH (installed-agent update and rollback path)
- **Depends on**: `plans/012-package-update-mechanism.md`
- **Category**: install/update product state + runtime proof
- **Planned at**: commit `90f767f`, 2026-07-08

## Product meaning

The installed agent must know what it is running and prove how it got there.
After an update, the owner should be able to ask:

- which package tag is active;
- which commit is active;
- which script performed the update;
- whether self-test and model validation passed;
- whether the agent re-anchored after the package flip.

The answer must come from a machine-readable install/update report, not from
the agent's memory or chat prose.

## Best-practice anchor

- GBrain-style installs create a working brain, write config, and verify the
  install end to end.
- OpenClaw-style agents need a clear installed-product state because the host
  has channels, runtime state, and visible product surfaces.
- Hermes-style persistent agents must survive update and rehydrate behavior
  from durable state, not from a single chat.

## Current problem

The package has a self-update mechanism, but a real installed-agent audit showed
a dangerous product gap: the active package can be made correct by manual
clone/relink while bypassing `scripts/apply_package_update.py`. That leaves no
proof that the package update gate, rollback, model-copy validation, lock, and
re-anchor actually ran.

There is also a release-tree hygiene problem: an installed release directory
must not contain `.git`, `__pycache__`, local test outputs, or other mutable
runtime residue.

## Architecture decision

**Context**: A package update changes the agent's behavior. The update path is a
product safety boundary because the package must not damage the model repo,
workspace, or source cursor state.

**Options**:

1. Trust the installed folder if its files match a tag.
   Rejected: this proves final bytes, not the path that produced them.
2. Add more human instructions to use the updater.
   Rejected: this does not stop bypass or make audits reproducible.
3. Make update proof a first-class artifact and verify it.

**Decision**: implement option 3. `apply_package_update.py` must write an
install/update proof report. A new verifier must fail when the active package
was switched without that proof.

**Consequences**: an installed agent can be asked for update status and answer
from files. A manual clone may still happen during emergency recovery, but it
must be marked as unverified and block "ready" status until reconciled.

## Scope

**In scope**:

- `scripts/apply_package_update.py`
- `scripts/check_package_updates.py`
- `scripts/package_self_test.py`
- new or updated `scripts/verify_installed_package.py`
- `skills/package-update/SKILL.md`
- `agent-os/UPDATE_POLICY.md`
- `specs/UPDATE-SPEC.md`
- `templates/workspace/**`
- `adapters/openclaw/**`
- focused tests under `tests/`

**Out of scope**:

- Changing accepted model content.
- Adding new source connectors.
- Rewriting OpenClaw itself.
- Pushing releases or tags.

## Implementation steps

### Step 1: Define install/update proof schema

Create a small JSON contract for the active package report. The report must
include at least:

```json
{
  "status": "installed",
  "package_tag": "v0.10.0",
  "package_commit": "<sha>",
  "source_url": "<sanitized-url>",
  "source_tree_hash": "<hash>",
  "release_dir": "package/releases/v0.10.0",
  "current_symlink": "package/current",
  "updater_script": "scripts/apply_package_update.py",
  "updater_package_commit": "<old-version-sha>",
  "started_at": "<iso8601>",
  "finished_at": "<iso8601>",
  "self_test": {"status": "passed", "command": "..."},
  "model_validation": {"status": "passed", "used_copy": true},
  "reanchor": {"status": "required|done|not_supported"},
  "rollback": {"available_offline": true}
}
```

Do not store secrets, raw source paths, tokens, or private message content.

### Step 2: Make release materialization clean and immutable

Harden `scripts/apply_package_update.py` so materialized release directories do
not retain:

- `.git`;
- `__pycache__`;
- test caches;
- local logs;
- temp files.

If `package_self_test.py` writes caches into the release tree, either redirect
them to a temp path or clean them before the final report.

### Step 3: Add installed package verifier

Add a verifier that checks:

- `package/current` resolves to a release directory;
- release tree hash matches the report;
- active tag/commit match the lock;
- report is newer than the symlink flip;
- report says self-test and model validation passed;
- no forbidden release-tree residue exists;
- source URL in locks and reports is sanitized.

The verifier must distinguish:

- `ok`;
- `manual-or-unproven-install`;
- `dirty-release-tree`;
- `self-test-missing`;
- `model-validation-missing`;
- `reanchor-missing`.

### Step 4: Update agent behavior

Update package-update instructions so the installed agent:

- never claims "updated" from `git clone` alone;
- reports unverified update state honestly;
- asks the owner before applying updates;
- records the proof path in the digest/status message;
- re-anchors after a successful flip.

### Step 5: Add fixture E2E

Create an old-install fixture:

```text
workspace/
  package/releases/v0.9.1/
  package/current -> releases/v0.9.1
  model-repo/
```

Run update to a fixture `v0.10.0`, then assert:

- current symlink flips only after checks pass;
- proof report exists;
- verifier returns `ok`;
- manual relink without report returns `manual-or-unproven-install`;
- dirty release tree returns `dirty-release-tree`.

## Required review loop

After implementation:

1. Run normal code review over the diff using `code-reviewer`.
2. Run architecture review using `improve-codebase-architecture`.
3. Run minimality review using `ponytail:ponytail-review`.
4. Fix all Critical/Warning findings and all Ponytail cuts that do not weaken
   safety, evidence, rollback, or tests.
5. Re-run the three reviews.
6. Move to the next plan only when the second pass has no blocking findings.

## Verification

Minimum commands:

```bash
python3 -m unittest tests.test_apply_package_update tests.test_check_package_updates
python3 -m unittest discover tests
python3 scripts/run_evals.py --fixture-only
python3 scripts/package_self_test.py --suite-timeout 180
git diff --check
```

Add focused verifier tests for:

- clean install proof;
- manual relink without proof;
- dirty release directory;
- sanitized URL in report;
- failed self-test blocks current flip.

## Definition of Done

- Active package status is available as a machine-readable report.
- Manual clone/relink is detectable and cannot be reported as a verified update.
- Release directories are clean source trees, not git checkouts with runtime
  caches.
- Update proof includes self-test, copied-model validation, rollback, and
  re-anchor status.
- Agent instructions tell the resident to answer update status from the report.
- Fixture E2E proves old install -> update -> verified status.
- Review loop completed twice with no blocking findings.

## STOP conditions

Stop and report if:

- the updater needs the real model repo path for write access;
- a test requires real credentials or network by default;
- update proof would store secrets or raw source data;
- rollback cannot be performed offline;
- current symlink flips before self-test and model validation pass;
- the installed-agent live environment differs from the fixture in a way that
  changes the product contract.

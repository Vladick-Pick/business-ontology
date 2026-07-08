# Plan 025: Model repo support contract and validator pin

> **Executor instructions**: Follow this plan step by step. The model repository
> must validate against the package version it claims to use. Do not maintain a
> second drifting validator in model repos. If a STOP condition occurs, stop and
> report.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 90f767f..HEAD -- \
>   templates/model-repo scripts/links_validate.py specs/UPDATE-SPEC.md \
>   agent-os/MODEL_STORAGE.md skills/package-update/SKILL.md \
>   skills/show-model/SKILL.md tests
> git diff --stat -- \
>   templates/model-repo scripts/links_validate.py specs/UPDATE-SPEC.md \
>   agent-os/MODEL_STORAGE.md skills/package-update/SKILL.md \
>   skills/show-model/SKILL.md tests
> ```

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: HIGH (model validation drift)
- **Depends on**: `plans/024-accepted-model-write-gate-enforcement.md`
- **Category**: model repo contract + validation reproducibility
- **Planned at**: commit `90f767f`, 2026-07-08
- **Implementation status**: DONE locally on `codex/plans-021-027-installed-agent-readiness`.

## Completion notes

- Added model repo support templates:
  - `templates/model-repo/PACKAGE_CONTRACT.lock.tpl`
  - `templates/model-repo/scripts/validate_model_repo.py.tpl`
- The model repo wrapper validates the pinned package version and commit, rejects
  copied `scripts/links_validate.py`, rejects validator path override, and
  delegates to package `scripts/links_validate.py` with the v2 hard gate.
- `scripts/apply_package_update.py` now writes
  `model_support_contract` into `PACKAGE_INSTALL_REPORT.json` with statuses
  `current`, `missing`, `invalid`, `drift`, `unsupported-copied-validator`, or
  `skipped`.
- `scripts/verify_installed_package.py` now rejects install reports without a
  valid model support contract block.
- Package update reports support-contract drift as review-required and does not
  mutate accepted model repositories.
- Code review found and fixed:
  - validator path override from `PACKAGE_CONTRACT.lock`;
  - invalid JSON support lock crashing updater instead of reporting
    review-required;
  - installed-package verification not requiring the support-contract proof.
- Architecture review found and fixed:
  - model repo wrapper fallback to `agent-package.yaml` version was untested,
    while the real package repo does not carry `VERSION.txt`.
- Ponytail review found no safe cut that preserves pinning and proof.

Verification run:

```bash
python3 -m unittest tests.test_model_repo_contract tests.test_apply_package_update tests.test_repo_layout
# 32 tests OK
python3 -m py_compile scripts/apply_package_update.py scripts/verify_installed_package.py
# OK
git diff --check
# OK
python3 -m unittest tests.test_repo_layout
# 4 tests OK
python3 -m unittest discover tests
# 481 tests OK
python3 scripts/run_evals.py --fixture-only
# 38 evals / 240 checks OK
python3 scripts/package_self_test.py --suite-timeout 180
# 481 tests OK + 38 evals / 240 checks OK
```

## Product meaning

The owner should be able to run validation inside a model repository and get
the same answer the installed package would give. A stale copied validator must
not say the model is broken or clean under the wrong contract.

## Best-practice anchor

- GBrain evals are reproducible from commit hash. This package needs the same
  discipline for model validation.
- Package update mechanisms should pin the behavior that validates persistent
  user data.

## Current problem

Model repositories can contain support scripts copied from an older package.
When the package moves to v0.10.0, an old model repo script can still validate
with old taxonomy assumptions. That creates two truths:

- package validator says one thing;
- model repo support script says another.

## Architecture decision

**Context**: The package owns validation rules. The model repo owns accepted
business content. Support files in the model repo are conveniences, not a
second source of validation truth.

**Options**:

1. Keep copying full validators into each model repo.
   Rejected: drift is guaranteed.
2. Remove all validation commands from model repos.
   Rejected: poor operator experience.
3. Put a thin wrapper and lock in model repos that invokes the pinned package
   validator.

**Decision**: implement option 3. Model repo support files must either use the
   active package validator or fail with a clear "package missing/mismatched"
   error.

## Scope

**In scope**:

- `templates/model-repo/**`
- a model repo package-contract lock/template
- package validator wrapper docs
- `agent-os/MODEL_STORAGE.md`
- `specs/UPDATE-SPEC.md`
- `skills/package-update/SKILL.md`
- `skills/show-model/SKILL.md`
- tests for generated model repo templates

**Out of scope**:

- Migrating private real model repos automatically.
- Changing model card schema.
- Adding a hosted canonical store.
- Writing accepted model content.

## Implementation steps

### Step 1: Add model repo package contract lock

Add a template file such as:

```text
PACKAGE_CONTRACT.lock
```

Minimum fields:

```json
{
  "package_name": "business-ontology",
  "package_version": "0.10.0",
  "package_commit": "<sha>",
  "validator": "scripts/links_validate.py",
  "validator_contract": "data-model-v2-hard-gate"
}
```

### Step 2: Replace copied validator behavior with wrapper

In model repo templates, validation command should:

- locate package path from workspace lock/env/config;
- verify package version/commit against `PACKAGE_CONTRACT.lock`;
- call package `scripts/links_validate.py`;
- fail clearly if the package is missing or mismatched.

Do not copy the full validator implementation into the model repo template.

### Step 3: Update package update behavior

When package version changes, updater must report whether model repo support
contract needs a proposal/update. If changing support files touches the model
repo, it must go through review/PR rules from plan 024.

### Step 4: Add tests

Add fixture model repos:

- matching package lock -> validation runs;
- missing package -> actionable error;
- mismatched package -> actionable error;
- stale copied script -> flagged as unsupported.

## Required review loop

After implementation:

1. Run normal code review using `code-reviewer`.
2. Run architecture review using `improve-codebase-architecture`.
3. Run minimality review using `ponytail:ponytail-review`.
4. Fix all Critical/Warning findings and Ponytail cuts that do not weaken
   validator pinning, operator UX, or tests.
5. Re-run all three reviews.
6. Move to the next plan only when the second pass has no blocking findings.

## Verification

Minimum commands:

```bash
python3 -m unittest tests.test_repo_layout
python3 -m unittest discover tests
python3 scripts/run_evals.py --fixture-only
python3 scripts/package_self_test.py --suite-timeout 180
git diff --check
```

Add focused tests for:

- generated model repo validation invokes package validator;
- mismatch blocks with a clear error;
- stale copied validator is detected;
- package update reports support-contract drift without mutating accepted model.

## Definition of Done

- Model repo templates contain a package contract lock.
- Validation inside a model repo uses the pinned package validator.
- Stale model repo support files are detectable.
- Package update reports support-contract drift as a reviewable change.
- No accepted model content is changed automatically.
- Review loop completed twice with no blocking findings.

## STOP conditions

Stop and report if:

- the design duplicates the full validator into model repos again;
- a package update silently edits accepted model repo files;
- validation can pass under a mismatched package version;
- live private model repos are changed without explicit owner review.

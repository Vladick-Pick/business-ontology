# Update spec

This spec defines how the package, installed agent workspace, and model
repository are updated without losing trust boundaries.

## Update targets

There are three different update targets:

| Target | What changes | Owner |
|---|---|---|
| Package repository | Skills, specs, adapters, templates, runtime reference code, schemas. | Package maintainer. |
| Agent workspace | Host instructions, tool state, cursors, setup notes, session state. | Resident agent, with operator review for sensitive changes. |
| Model repository/store | Accepted model, staged proposals, source map, drift, review records. | Human model owner. |

Do not merge these targets. A package update is not a model truth change. A
source event is not an instruction update. A workspace learning is not accepted
ontology.

## Package update flow

1. Check release tags from the pinned remote in `workspace/PACKAGE_VERSION.lock`.
2. Ask the owner for approval before installing a newer release.
3. Apply the release with `scripts/apply_package_update.py`; do not install by
   manual clone, branch checkout, copied folder, or symlink edit.
4. Compare `agent-package.yaml` paths against the installed workspace.
5. Copy changed templates only when the target file is still template-owned or
   the update explicitly requires migration.
6. Preserve local workspace state: source cursors, model repo target, run logs,
   review queue, tool availability.
7. Run the new release's offline self-test before flipping `package/current`.
8. Validate a temporary copy of the accepted model when a model repository is
   connected.
9. Report whether the model repository support contract is current, missing,
   invalid, drifted, or blocked by a copied validator. Do not edit the model
   repository from package update.
10. Flip `package/current` atomically only after tests and model-copy validation
   pass.
11. Write `workspace/PACKAGE_INSTALL_REPORT.json` with package tag, commit,
   sanitized source URL, release directory, source tree hash, self-test result,
   model validation result, model support contract status, rollback
   availability, and re-anchor status.
12. Verify the installed package with `scripts/verify_installed_package.py`.
13. Record the update in the workspace `LEARNINGS.md` or `SESSION_STATE.md` if
   it changes operating behavior.

An installed package is verified only when the lock file, `package/current`,
clean release tree, and install report agree. If the verifier returns
`manual-or-unproven-install`, the agent must not claim the update succeeded
even if the active files appear to match a release tag.

Rollback is also an installed-package state. A rollback must run self-test for
the restored release, flip `package/current` atomically, write
`PACKAGE_INSTALL_REPORT.json` with `status=rolled-back`, and pass
`verify_installed_package.py`. Rollback does not receive the real model repo
path.

## Model repository support files

Model repositories use package-owned validation through:

```text
PACKAGE_CONTRACT.lock
scripts/validate_model_repo.py
```

The lock pins `business-ontology`, package version, package commit, validator
path, and `validator_contract=data-model-v2-hard-gate`. The wrapper refuses a
mismatched package, missing package, or stale copied `scripts/links_validate.py`
inside the model repository. Updating these support files is a model-repo
change: prepare a reviewable proposal or PR; do not mutate accepted model files
from package update.

## Model update flow

Accepted model updates follow the resident loop:

```text
source event
-> model-change package
-> review package
-> human review
-> accepted model update
-> export/projection update
```

The agent may generate source events, model-change packages, review packages,
digests, and staged proposals. It must not promote accepted truth by itself.

## Breaking changes

A package change is breaking when it changes any of these:

- required workspace files;
- schema field names or required fields;
- card status vocabulary;
- relation vocabulary;
- accepted-state storage semantics;
- source cursor semantics;
- review approval semantics;
- adapter bootstrap path.

Breaking changes require:

- a `CHANGELOG.md` entry;
- a `deployment/MIGRATION_POLICY.md` entry;
- a test that fails on the old layout or contract and passes on the new one;
- a short operator note that says what an installed agent must do.

## Safe defaults

When an update conflicts with local state:

- keep local source cursors;
- keep local model repository target;
- keep local secrets outside files;
- keep staged proposals;
- do not regenerate accepted model files;
- ask one concrete migration question with a recommended answer.

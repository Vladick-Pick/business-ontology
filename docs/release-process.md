# Release process

This repository ships an installable agent skill, reference runtime code,
OpenClaw bootstrap material, schemas, and eval fixtures. A release is ready only
when the public docs, runtime contracts, bootstrap files, tests, and evals tell
the same story.

## Release rule

Do not publish a release that implies production resident-agent capability unless
the matching source connectors, OAuth/scopes, hosted MCP/GBrain access,
accepted-model write path, and captured production runs exist.

Use these labels in release notes:

- `implemented` - code or docs are present in this repo and covered by tests or
  evals where applicable.
- `reference` - local harness or template proves a contract, but is not hosted
  production infrastructure.
- `spec-only` - normative or product documentation only.
- `not shipped` - explicitly outside the current release.

## Branch workflow

Use a feature branch for release-prep work:

```bash
git fetch --prune origin
git switch main
git pull --ff-only
git switch -c release/<version>
```

If there are existing dirty changes, inspect them before switching branches.
Do not reset or clean user work.

## Required checks

Run the full local verification baseline:

```bash
python3 -m unittest discover -s tests
python3 scripts/run_evals.py --fixture-only
python3 scripts/links_validate.py .
python3 scripts/links_validate.py . --staged
git diff --check
python3 -m py_compile runtime/*.py scripts/*.py
```

For OpenClaw bootstrap changes, also run the focused tests:

```bash
python3 -m unittest \
  tests.test_openclaw_self_bootstrap \
  tests.test_openclaw_workspace_template \
  tests.test_openclaw_live_test_readiness
```

For store/runtime changes, also run:

```bash
python3 -m unittest \
  tests.test_operational_store \
  tests.test_resident_loop \
  tests.test_reference_runtime \
  tests.test_render_workflow
```

## Release note shape

Each release note should answer these questions:

1. What can a user or agent do after this release that it could not do before?
2. Which files are the entry points?
3. Which boundary changed?
4. Why was this implementation chosen?
5. What is still not shipped?
6. Which commands verified the release?

Keep it factual. Do not use release copy to imply missing runtime capability.

## Publishing steps

Installed agents consume published releases through the OpenClaw package update
contract in `adapters/openclaw/UPDATE_POLICY.md`.

After checks pass:

```bash
git status --short
git add CHANGELOG.md docs/release-process.md README.md
git commit -m "docs: add release notes and process"
git push origin release/<version>
```

Open a PR into `main`. After review and merge:

```bash
git switch main
git pull --ff-only
git tag -a v<version> -m "v<version>"
git push origin main --tags
```

Create the GitHub Release from the matching `CHANGELOG.md` section. Keep the
release title plain:

```text
v<version> - Resident foundation and canonical store architecture
```

## Current release draft

The latest published release is `0.10.6`
(`0.10.6 - Resident loop bytecode hygiene` in `CHANGELOG.md`, tag `v0.10.6`).
The next release draft is `0.11.0`.

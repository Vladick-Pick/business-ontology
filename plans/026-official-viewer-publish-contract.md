# Plan 026: Official viewer publish contract

> **Executor instructions**: Follow this plan step by step. The viewer must be
> built from the official package viewer and accepted model bundle. Do not
> publish ad hoc HTML as the product viewer. If a STOP condition occurs, stop
> and report.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 90f767f..HEAD -- \
>   viewer scripts/build_viewer_bundle.py skills/show-model/SKILL.md \
>   schemas/model-health.schema.json runtime templates/workspace tests
> git diff --stat -- \
>   viewer scripts/build_viewer_bundle.py skills/show-model/SKILL.md \
>   schemas/model-health.schema.json runtime templates/workspace tests
> ```

## Status

- **Priority**: P1
- **Effort**: M-L
- **Risk**: MED-HIGH (user-facing model surface)
- **Depends on**: `plans/022-workspace-state-and-model-language-onboarding.md`,
  `plans/023-source-instance-registry-and-live-proof-ledger.md`,
  `plans/025-model-repo-support-contract-and-validator-pin.md`
- **Category**: viewer + publish proof + product UX
- **Planned at**: commit `90f767f`, 2026-07-08

## Product meaning

The viewer is not a decorative page. It is the owner-facing surface for the
current company model. It must show:

- model revision;
- package version;
- selected model language;
- source readiness;
- pending human requests;
- validation status;
- accepted model graph/data.

If the viewer was built by hand or from stale data, it must be marked invalid.

## Best-practice anchor

- OpenClaw-style live canvas/viewer surfaces should reflect runtime truth, not
  separate handcrafted pages.
- GBrain-style install verification should prove the user-facing surface is
  connected to the current brain/model state.

## Current problem

The package has a base viewer and viewer bundle builder. A live installed-agent
audit showed the risk: an agent can create a custom page first, then later copy
the package viewer. That makes the user-facing surface untrustworthy unless the
publish path is formalized.

## Architecture decision

**Context**: The accepted model is the product output. The viewer is how humans
inspect it. A custom viewer can hide stale state, missing source proof, or an
old model language.

**Options**:

1. Allow agents to create any HTML if it displays cards.
   Rejected: cannot audit product truth.
2. Only support command-line text fallback.
   Rejected: weak product experience.
3. Add an official publish command that validates model, builds bundle, copies
   package viewer, and writes a publish report.

**Decision**: implement option 3. `show-model` must prefer the official viewer
publish path and fall back to bounded text only when the viewer cannot be
published.

## Scope

**In scope**:

- `scripts/build_viewer_bundle.py`
- new `scripts/publish_viewer.py` or equivalent wrapper
- `viewer/**`
- `skills/show-model/SKILL.md`
- `schemas/model-health.schema.json`
- workspace templates for viewer output/report paths
- focused tests under `tests/`

**Out of scope**:

- Large viewer redesign.
- New graph layout engine.
- Live hosted deployment.
- Editing accepted model content.

## Implementation steps

### Step 1: Define publish report

Add a viewer publish report with:

```json
{
  "status": "published",
  "package_version": "0.10.0",
  "package_commit": "<sha>",
  "model_revision": "<sha>",
  "company_model_language": "ru",
  "source_readiness": {"live_proven": 2, "blocked": 1},
  "open_human_request_count": 3,
  "validation": {"status": "passed"},
  "viewer_asset_hash": "<hash>",
  "bundle_hash": "<hash>",
  "published_at": "<iso8601>"
}
```

### Step 2: Add official publish command

The command must:

1. run package validator against accepted model;
2. read workspace state;
3. read source readiness and human request summary;
4. build viewer bundle;
5. copy package `viewer/index.html`;
6. write publish report;
7. fail if existing published HTML differs from package viewer unless an
   explicit test override is used.

### Step 3: Update viewer bundle

Add metadata fields:

- `packageVersion`;
- `packageCommit`;
- `modelRevision`;
- `companyModelLanguage`;
- `sourceReadiness`;
- `openHumanRequestCount`;
- `validationStatus`.

### Step 4: Update `show-model`

The skill must:

- publish official viewer when possible;
- state the publish report path;
- refuse to present custom HTML as current model viewer;
- use bounded text fallback when publish fails, including the failure reason.

## Required review loop

After implementation:

1. Run normal code review using `code-reviewer`.
2. Run architecture review using `improve-codebase-architecture`.
3. Run minimality review using `ponytail:ponytail-review`.
4. Fix all Critical/Warning findings and Ponytail cuts that do not weaken
   publish proof, validation, or user-facing status.
5. Re-run all three reviews.
6. Move to the next plan only when the second pass has no blocking findings.

## Verification

Minimum commands:

```bash
python3 -m unittest tests.test_viewer_bundle
python3 -m unittest discover tests
python3 scripts/run_evals.py --fixture-only
python3 scripts/package_self_test.py --suite-timeout 180
git diff --check
```

Add focused tests for:

- official publish writes report;
- custom HTML is rejected as current viewer;
- bundle includes model language and revision;
- source readiness and open human requests appear in metadata;
- validation failure blocks publish;
- bounded text fallback includes failure reason.

## Definition of Done

- Viewer publish is one official command/path.
- Viewer cannot be claimed current without validation and publish report.
- Viewer metadata includes package, model, language, source readiness, and
  pending requests.
- `show-model` uses official publish or bounded fallback.
- Ad hoc viewer pages are detectable and rejected.
- Review loop completed twice with no blocking findings.

## STOP conditions

Stop and report if:

- publish path can skip validation;
- custom HTML can be presented as official viewer;
- viewer hides missing model language or source proof;
- raw source content is embedded in the bundle;
- tests require a live browser or network by default.

# Plan 022: Workspace state and model language onboarding

> **Executor instructions**: Follow this plan step by step. The model language
> must be asked during onboarding; do not hard-code Russian, English, or any
> other language as the product default. If a STOP condition occurs, stop and
> report.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 90f767f..HEAD -- \
>   agent-os/FIRST_SESSION_PLAYBOOK.md skills/onboard-contour/SKILL.md \
>   skills/business-ontology/SKILL.md skills/synthesize-digest/SKILL.md \
>   skills/show-model/SKILL.md scripts/bootstrap_openclaw_workspace.py \
>   templates/workspace schemas tests viewer scripts/build_viewer_bundle.py
> git diff --stat -- \
>   agent-os/FIRST_SESSION_PLAYBOOK.md skills/onboard-contour/SKILL.md \
>   skills/business-ontology/SKILL.md skills/synthesize-digest/SKILL.md \
>   skills/show-model/SKILL.md scripts/bootstrap_openclaw_workspace.py \
>   templates/workspace schemas tests viewer scripts/build_viewer_bundle.py
> ```

## Status

- **Status**: DONE (local, review loop complete)
- **Priority**: P1
- **Effort**: M
- **Risk**: HIGH (onboarding contract and installed workspace truth)
- **Depends on**: `plans/021-installed-product-state-and-update-proof.md`
- **Category**: onboarding + workspace contract + product language
- **Planned at**: commit `90f767f`, 2026-07-08

## Product meaning

The installed agent must not guess the language of the company model. During
onboarding it asks the owner:

```text
На каком языке вести модель компании?

Рекомендация: выберите язык, на котором владелец и команда реально принимают
решения. Технические ids останутся стабильными и не будут зависеть от языка.
```

The answer becomes workspace state. After that, model-change packages, accepted
card titles/descriptions, digests, human requests, and viewer labels must use
that language unless a source quote is intentionally preserved as evidence.

## Best-practice anchor

- GBrain-style setup asks for configuration during install and writes durable
  state.
- Hermes-style agents use persistent memory/state to avoid re-learning the same
  preference after restart.
- OpenClaw-style product surfaces must show the same state the agent uses.

## Current problem

The package can generate a workspace, but the workspace does not have one
canonical product-state file that records:

- installed package identity;
- agent identity;
- model repo identity;
- current company/module contour;
- selected company model language;
- source readiness;
- viewer revision.

This creates drift. A deployed agent can have a v0.10.0 package while the
workspace still contains old bootstrap language, stale revision examples, or an
English model when the owner expected another language.

## Architecture decision

**Context**: The accepted model is business truth; workspace state is runtime
state. Model language is not business truth by itself, but it controls how the
agent writes human-readable business truth.

**Options**:

1. Infer model language from the user's chat language.
   Rejected: chat language and company-model language can differ.
2. Hard-code Russian for this owner.
   Rejected: the package is installable and must work for other companies.
3. Ask during onboarding, store the answer, and make it visible in workspace,
   model packages, digest, and viewer.

**Decision**: implement option 3. Technical ids may stay ASCII/opaque; human
model text must follow `companyModelLanguage`.

## Scope

**In scope**:

- `agent-os/FIRST_SESSION_PLAYBOOK.md`
- `skills/onboard-contour/SKILL.md`
- `skills/business-ontology/SKILL.md`
- `skills/synthesize-digest/SKILL.md`
- `skills/show-model/SKILL.md`
- `scripts/bootstrap_openclaw_workspace.py`
- `templates/workspace/**`
- `schemas/workspace-manifest.schema.json`
- `schemas/model-change-package.schema.json` only if language metadata belongs
  there.
- `scripts/build_viewer_bundle.py`
- `viewer/**`
- focused tests under `tests/`

**Out of scope**:

- Translating all existing model examples.
- Changing technical card ids, relation names, schema keys, or file names.
- Auto-translating source quotes.
- Changing accepted model content without review.

## Implementation steps

### Step 1: Add canonical workspace state

Add a durable workspace state contract. Prefer one file over scattered state:

```text
workspace-state.json
```

or extend an existing manifest if that is already the local pattern.

Minimum fields:

```json
{
  "agent_identity": {
    "package_name": "business-ontology",
    "package_version": "0.10.0",
    "package_commit": "<sha>"
  },
  "company_model": {
    "model_repo": "<repo-or-path>",
    "model_repo_revision": "<sha-or-unknown>",
    "company_model_language": "ru|en|...",
    "language_source": "owner-onboarding",
    "language_decided_at": "<iso8601>"
  },
  "workspace": {
    "workspace_id": "<id>",
    "created_at": "<iso8601>",
    "updated_at": "<iso8601>"
  }
}
```

Use a language code plus owner-facing label if needed. Do not use free text
only.

### Step 2: Update onboarding

Onboarding order:

1. Identify model repo target.
2. Ask company/model contour questions.
3. Ask model language.
4. Record the answer before generating first model pack or digest.
5. Continue source setup.

If the owner has not answered, the agent must record an open human request and
avoid claiming model-language readiness.

### Step 3: Carry language into artifacts

Add language metadata to:

- bootstrap manifest;
- workspace state;
- generated model pack metadata;
- human request prompts where relevant;
- digest header;
- viewer bundle metadata.

Do not change schema keys or relation names. This is a human-language contract,
not a JSON-key localization project.

### Step 4: Add stale workspace detector

Add a check that reports contradictions:

- package lock says v0.10.0 but workspace template says older revision;
- workspace company name/module differs from current model repo config;
- `company_model_language` missing after onboarding completed;
- viewer bundle language differs from workspace state;
- source registry belongs to another agent identity.

### Step 5: Viewer and digest behavior

Viewer and digest must show:

- model language;
- model revision;
- source readiness summary;
- pending human requests count.

If model language is pending, show pending state. Do not silently pick English.

## Required review loop

After implementation:

1. Run normal code review using `code-reviewer`.
2. Run architecture review using `improve-codebase-architecture`.
3. Run minimality review using `ponytail:ponytail-review`.
4. Fix all Critical/Warning findings and Ponytail cuts that do not weaken the
   language contract, state consistency, or tests.
5. Re-run all three reviews.
6. Move to the next plan only when the second pass has no blocking findings.

## Verification

Minimum commands:

```bash
python3 -m unittest tests.test_openclaw_workspace_template
python3 -m unittest tests.test_viewer_bundle
python3 -m unittest discover tests
python3 scripts/run_evals.py --fixture-only
python3 scripts/package_self_test.py --suite-timeout 180
git diff --check
```

Add focused tests for:

- onboarding does not proceed to "ready" without model language;
- selected model language appears in workspace state;
- bootstrap generator writes language when provided;
- viewer bundle includes language metadata;
- stale workspace detector flags missing/contradictory language;
- no hard-coded Russian or English default is used for company model text.

## Definition of Done

- Onboarding asks which language to use for the company model.
- The answer is stored in canonical workspace state.
- Human-facing model text, digests, requests, and viewer metadata follow that
  language.
- Technical ids/schema keys stay stable and language-independent.
- Missing language blocks readiness and creates a human request.
- Stale workspace contradictions are detectable.
- Review loop completed twice with no blocking findings.

## STOP conditions

Stop and report if:

- implementation requires rewriting accepted model content without review;
- language is inferred from chat instead of explicitly chosen;
- technical ids are localized;
- viewer or digest can claim ready while language is missing;
- tests need live OpenClaw or Telegram credentials by default.

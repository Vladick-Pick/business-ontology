# Plan 031: Viewer exposes decision kinetic contracts and metric measurement contracts

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the next
> step. If a STOP condition occurs, stop and report; do not improvise.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 6bd26d7..HEAD -- viewer/index.html viewer/README.md tests/test_viewer_bundle.py examples/business-attraction-v2
> git diff --stat -- viewer/index.html viewer/README.md tests/test_viewer_bundle.py examples/business-attraction-v2
> ```

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: plan 028; can run in parallel with plan 030 only in isolated
  worktrees because both edit `viewer/index.html`
- **Category**: product UX / methodology / tests
- **Planned at**: commit `6bd26d7`, 2026-07-08

## Why this matters

The kinetic layer is where the model changes behavior: who owns a decision, who
may change a transition, what measurement convention makes a KPI true, what
override path exists, and what breaks downstream. Those fields exist in v2
cards, but the viewer mostly hides scalar `attrs` unless the user opens
technical JSON. A business analyst needs these fields as first-class review
blocks.

## Current state

- `examples/business-attraction-v2/decisions/d-autopurchase.md:10-23` contains
  kinetic attrs: `irreversible`, `episode`, `scope`, `decision-owner`,
  `transition-authority`, `measurement-convention`, `affected-workflows`,
  `affected-kpis`, `propagation-sla`, `override-policy`, `exception-path`,
  `blast-radius`.
- `viewer/index.html:404-410` renders only arrays/objects in generic attr blocks;
  scalar decision attrs are skipped unless they are visible in body prose or
  technical JSON.
- `examples/business-attraction-v2/metrics/m-sla1.md:11-28` contains target,
  baseline, binding, refresh cadence, and influences.
- `metricsView()` at `viewer/index.html:286-293` only shows formula, unit,
  source of truth, and owner.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused tests | `python3 -m unittest tests.test_viewer_bundle` | all tests pass |
| Full tests | `python3 -m unittest discover tests` | all tests pass |
| Evals | `python3 scripts/run_evals.py --fixture-only` | all fixtures pass |
| Self-test | `python3 scripts/package_self_test.py --suite-timeout 180` | all tests and evals pass |
| Whitespace | `git diff --check` | no output, exit 0 |

## Suggested executor toolkit

- Use a frontend subagent for the decision/metric rendering.
- Use a reviewer subagent in BA role after implementation: ask whether the page
  now answers "why was this decision made, who can change it, what measurement
  triggers it, and what breaks downstream?"

## Scope

**In scope**

- `viewer/index.html`
- `viewer/README.md`
- `tests/test_viewer_bundle.py`
- optional fixture-only edits in `examples/business-attraction-v2` if a field is
  missing from the reference fixture

**Out of scope**

- Changing decision status vocabulary.
- Changing metric formulas or accepted business facts.
- Building workflow approval in the viewer.
- Adding charts for live metric values.

## Git workflow

- Branch: `codex/031-viewer-decision-metric-contracts`
- Do not push or open a PR unless the operator asks.

## Steps

### Step 1: Add decision kinetic contract block

In `cardView()`, for `c.type === "decision"`, render a dedicated block before
generic attrs or before the technical view.

Fields:

- irreversible;
- episode;
- scope;
- decision owner;
- transition authority;
- measurement convention;
- affected workflows;
- affected KPIs;
- propagation SLA;
- override policy;
- exception path;
- blast radius.

Use links for fields that contain card ids or arrays of ids. Keep long scalar
text readable; do not squeeze it into a tiny diagram node.

**Verify**:

Extend `tests/test_viewer_bundle.py` with static assertions for labels such as
`Decision contract`, `measurement-convention`, `override-policy`, or Russian
equivalents.

### Step 2: Add metric measurement contract block

Update metric card rendering and `#metrics`.

For each metric, show:

- formula;
- unit;
- direction;
- target;
- baseline value/date/source event;
- source-of-truth;
- binding source/locator/field;
- refresh cadence;
- influenced metrics with polarity/delay where available.

In `#metrics`, keep the table compact but include target, binding source, and
refresh cadence. Full detail can stay on the card page.

**Verify**:

Extend `tests/test_viewer_bundle.py` with assertions that `viewer/index.html`
contains the new measurement labels.

### Step 3: Keep scalar attrs visible without dumping everything

The current generic attr rendering skips most scalar attrs. Do not blindly dump
every scalar under every card type; that creates noise. Instead:

- handle decision and metric scalar attrs explicitly;
- leave other scalar attrs to body prose or technical view unless another plan
  names them.

**Verify**:

Run focused tests.

### Step 4: Browser smoke against v2 fixture

Publish `examples/business-attraction-v2` and inspect:

- `#card/d-autopurchase` shows the decision contract without opening technical
  JSON;
- `#card/m-sla1` shows target, baseline, binding, and refresh cadence;
- `#metrics` table still fits and links to metric cards.

**Verify**:

Record smoke result in implementation report.

## Required review loop

1. Run `code-reviewer`: check escaping, missing links, and hidden scalar attrs.
2. Run `improve-codebase-architecture`: check that decision/metric rendering is
   domain-specific and not a generic noisy dump.
3. Run `ponytail:ponytail-review`: remove overbuilt formatting helpers; keep
   the dedicated decision/metric blocks.
4. Fix findings and re-run all three reviews.

## Test plan

- Static viewer tests for decision and metric labels.
- Existing bundle tests to ensure attrs still pass through.
- Browser smoke on `d-autopurchase`, `m-sla1`, and `#metrics`.

## Done criteria

- [ ] Decision cards show kinetic attrs outside technical JSON.
- [ ] Metric cards show measurement contract outside technical JSON.
- [ ] `#metrics` gives enough columns for a BA to see target/source/refresh at a glance.
- [ ] No accepted metric formula or decision meaning is changed.
- [ ] `python3 -m unittest tests.test_viewer_bundle` passes.
- [ ] `python3 -m unittest discover tests` passes.
- [ ] `python3 scripts/run_evals.py --fixture-only` passes.
- [ ] `python3 scripts/package_self_test.py --suite-timeout 180` passes.
- [ ] `git diff --check` passes.
- [ ] `plans/README.md` row for plan 031 is updated.

## STOP conditions

Stop and report if:

- Kinetic fields are absent from the current decision contract.
- Rendering requires changing the schema rather than displaying existing data.
- The UI becomes a generic raw-attrs dump.
- A reviewer cannot tell which fields are accepted facts and which are body prose.

## Maintenance notes

Future decision-card fields should be added to this block only when they change
authority, measurement, propagation, override/exception path, or downstream
workflow impact.

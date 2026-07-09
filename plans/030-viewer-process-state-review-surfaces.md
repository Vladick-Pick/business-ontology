# Plan 030: Viewer exposes process steps and state transitions as review tables

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the next
> step. If a STOP condition occurs, stop and report; do not improvise.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 6bd26d7..HEAD -- scripts/build_viewer_bundle.py viewer/index.html viewer/README.md tests/test_viewer_bundle.py examples/business-attraction-v2
> git diff --stat -- scripts/build_viewer_bundle.py viewer/index.html viewer/README.md tests/test_viewer_bundle.py examples/business-attraction-v2
> ```
>
> If process steps are still inferred from list order, STOP. Plan 030 assumes
> process edges are explicit (`next`, `yes`, `no`) and tested.

## Status

- **Priority**: P1
- **Effort**: M-L
- **Risk**: MED
- **Depends on**: plan 028; can start after plan 029 if source/evidence fields
  are not touched in the same worktree
- **Category**: product UX / correctness / tests
- **Planned at**: commit `6bd26d7`, 2026-07-08

## Why this matters

A process diagram is not enough for business analysis. The analyst must verify
who performs each step, what enters and exits, which rule governs it, and where
the branch goes. For states, the analyst must verify transition authority,
effect, SLA, source of truth, and reason codes. Hiding those fields makes a
process look understood when the operational contract is not reviewable.

## Current state

- `examples/business-attraction-v2/processes/p-handle-delivery.md:19-49`
  stores `role`, `input`, `output`, `rule`, `next`, and decision `yes/no`.
- `_process_steps()` preserves those fields at
  `scripts/build_viewer_bundle.py:193-204`.
- `processWbSpec()` at `viewer/index.html:233` renders only diagram nodes and
  edges; it does not render a step review table.
- `examples/business-attraction-v2/states/st-deal.md:21-61` stores transition
  `authority`, `effect`, SLA, and reason codes.
- `lifecycleWbSpec()` at `viewer/index.html:234` puts only trigger/SLA on the
  arrows.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused tests | `python3 -m unittest tests.test_viewer_bundle` | all tests pass |
| Publish smoke | `python3 scripts/publish_viewer.py examples/business-attraction-v2 --workspace /tmp/bo-viewer-process-state/workspace --out-dir /tmp/bo-viewer-process-state/workspace/viewer --module biz-attraction --revision process-state-smoke --as-of 2026-12-01` | exit 0 |
| Full tests | `python3 -m unittest discover tests` | all tests pass |
| Evals | `python3 scripts/run_evals.py --fixture-only` | all fixtures pass |
| Self-test | `python3 scripts/package_self_test.py --suite-timeout 180` | all tests and evals pass |
| Whitespace | `git diff --check` | no output, exit 0 |

## Suggested executor toolkit

- A backend/test subagent can expand `viewer_projection_diagnostics()` for
  state transition authority references.
- A frontend subagent can render the review tables after the projection fields
  are stable.
- Parallel implementation is possible only in isolated worktrees; integrate the
  generator/test change before the UI change.

## Scope

**In scope**

- `scripts/build_viewer_bundle.py`
- `viewer/index.html`
- `viewer/README.md`
- `tests/test_viewer_bundle.py`
- v2 fixture updates only if they are required to make explicit accepted facts
  visible

**Out of scope**

- Editing live source connectors.
- Changing accepted model semantics.
- Building an editor or review-approval workflow inside the viewer.
- Replacing SVG layout.

## Git workflow

- Branch: `codex/030-viewer-process-state-review-surfaces`
- Do not push or open a PR unless the operator asks.

## Steps

### Step 1: Add process step review table

In `viewer/index.html`, add a table below the process diagram for process cards:

Columns:

- step id;
- action / decision question;
- role;
- input;
- output;
- rule;
- next / yes / no;
- warning or missing fields.

Use links for ids that resolve to cards. Do not show `[object Object]`; nested
values must be formatted safely.

**Verify**:

Extend `tests/test_viewer_bundle.py` to assert `viewer/index.html` contains
stable labels such as `Шаги процесса`, `role`, `input`, `output`, `rule`, or
their Russian UI labels.

### Step 2: Add state transition matrix

For state cards with `attrs.transitions`, render a matrix below the state
diagram:

- from;
- to;
- trigger;
- SLA;
- authority;
- effect;
- source-of-truth link(s) from the state card;
- notes if authority/effect is missing on a transition where it matters.

For `attrs.reason-codes`, render a separate "Reason codes" table.

**Verify**:

Add assertions that the HTML has `Матрица переходов`, `authority`, `effect`, and
`Коды причин` or equivalent Russian labels.

### Step 3: Expand projection diagnostics for transition authority

In `scripts/build_viewer_bundle.py`, extend `viewer_projection_diagnostics()`:

- for state transitions, if `authority` looks like a card id and is not present
  or is the wrong type, add a diagnostic;
- accepted ids should allow `role` and `decision` because `st-deal` uses both
  `r-ki` and `d-autopurchase`;
- do not reject free-text authority values unless the model contract already
  requires ids.

**Verify**:

Add a unit test with a state transition `authority: missing-role` and assert a
viewer diagnostic. Add a positive test for `authority: r-ki` and
`authority: d-autopurchase` in the v2 fixture.

### Step 4: Run v2 publish smoke

Publish `examples/business-attraction-v2` into `/tmp/bo-viewer-process-state`.
Use browser smoke if available to inspect:

- `#card/p-handle-delivery` shows both the diagram and step table;
- `#card/st-deal` shows both the state diagram and transition matrix;
- no `Нет данных`, `[object Object]`, or unresolved `…` appears on populated
  process/state pages.

**Verify**:

Record the smoke result in the implementation report.

## Required review loop

1. Run `code-reviewer`: check field loss, false links, diagnostics, and table
   escaping.
2. Run `improve-codebase-architecture`: check whether process/state formatting
   is local and does not become a generic schema engine.
3. Run `ponytail:ponytail-review`: remove table abstraction if it hides the
   domain; keep simple helpers if repeated safely.
4. Fix blocking findings.
5. Re-run all three reviews.

## Test plan

- Static HTML tests for new table labels.
- Bundle tests for preserved step fields and transition authority diagnostics.
- Manual/browser smoke against `examples/business-attraction-v2`.

## Done criteria

- [ ] Process cards show step diagram and step review table.
- [ ] State cards show state diagram and transition matrix.
- [ ] Reason codes render as a table when present.
- [ ] Transition authority diagnostics catch missing id authority without
  rejecting valid `role` and `decision` authorities.
- [ ] `python3 -m unittest tests.test_viewer_bundle` passes.
- [ ] `python3 -m unittest discover tests` passes.
- [ ] `python3 scripts/run_evals.py --fixture-only` passes.
- [ ] `python3 scripts/package_self_test.py --suite-timeout 180` passes.
- [ ] `git diff --check` passes.
- [ ] `plans/README.md` row for plan 030 is updated.

## STOP conditions

Stop and report if:

- Transition authority semantics require a model-contract decision.
- Rendering the tables requires raw source payloads.
- The process table duplicates technical JSON without adding readable links and
  labels.
- The change requires editing unrelated skills/connectors.

## Maintenance notes

The reviewer should check whether a business analyst can answer: who acts, what
enters, what exits, what rule applies, and who may change state. If not, the
plan is not complete.

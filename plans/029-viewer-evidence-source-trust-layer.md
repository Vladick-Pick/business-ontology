# Plan 029: Viewer shows evidence, volatility, aliases, and source trust

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the next
> step. If a STOP condition occurs, stop and report; do not improvise.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 6bd26d7..HEAD -- scripts/build_viewer_bundle.py scripts/publish_viewer.py viewer/index.html viewer/README.md tests/test_viewer_bundle.py tests/test_publish_viewer.py
> git diff --stat -- scripts/build_viewer_bundle.py scripts/publish_viewer.py viewer/index.html viewer/README.md tests/test_viewer_bundle.py tests/test_publish_viewer.py
> ```
>
> If `scripts/build_viewer_bundle.py` does not contain
> `viewer_projection_diagnostics`, STOP and ask the operator to merge/apply the
> viewer-v2-shape-currentness patch first.

## Status

- **Priority**: P1
- **Effort**: M-L
- **Risk**: MED
- **Depends on**: plan 028
- **Category**: product trust / correctness / docs
- **Planned at**: commit `6bd26d7`, 2026-07-08

## Why this matters

Accepted cards are not equally stable. A high-volatility metric backed by a
synthetic fixture should not look as settled as a stable role backed by a live
proof. The current viewer hides key trust fields and shows sources as a flat
catalog, so a business analyst cannot judge what the model actually rests on.

## Current state

- `_card_from_file()` returns a fixed set of fields at
  `scripts/build_viewer_bundle.py:104-117`. It omits top-level `volatility`,
  `evidence`, and `aliases`.
- The v2 fixture uses those fields:
  - `examples/business-attraction-v2/metrics/m-sla1.md:9-10`:
    `volatility: high`, `evidence: [srcevt-btx-0630]`.
  - `examples/business-attraction-v2/roles/r-ki.md:9-10`:
    `volatility: medium`, `aliases: ["КИ", "консультант интервьюер"]`.
- `_health()` treats `source == "unknown"` as resolved at
  `scripts/build_viewer_bundle.py:425-430`. That makes source coverage look
  better than it is.
- `sourcesView()` at `viewer/index.html:462-468` shows only
  `id/trust/owner/access/meaning`.
- `publish_viewer.py:147-156` already has a source-readiness report shape, but
  the source page does not use it as a trust surface.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused tests | `python3 -m unittest tests.test_viewer_bundle tests.test_publish_viewer` | all tests pass |
| Full tests | `python3 -m unittest discover tests` | all tests pass |
| Evals | `python3 scripts/run_evals.py --fixture-only` | all fixtures pass |
| Self-test | `python3 scripts/package_self_test.py --suite-timeout 180` | all tests and evals pass |
| Whitespace | `git diff --check` | no output, exit 0 |

## Suggested executor toolkit

- Backend/generator subagent can own `scripts/build_viewer_bundle.py`,
  `scripts/publish_viewer.py`, and Python tests.
- Frontend subagent can own the `viewer/index.html` source/trust rendering after
  the generator contract is merged.
- Do not let two subagents edit `viewer/index.html` at the same time unless they
  work in isolated worktrees and one human/operator integrates the diffs.

## Scope

**In scope**

- `scripts/build_viewer_bundle.py`
- `scripts/publish_viewer.py`
- `viewer/index.html`
- `viewer/README.md`
- `tests/test_viewer_bundle.py`
- `tests/test_publish_viewer.py`

**Out of scope**

- Live connector implementation.
- Raw source payloads.
- Changing trust semantics in `02-source-map.md` beyond display and coverage
  calculation.
- Editing accepted model cards except adding test fixtures if required.

## Git workflow

- Branch: `codex/029-viewer-evidence-source-trust-layer`
- Do not push or open a PR unless the operator asks.

## Steps

### Step 1: Preserve trust fields in the viewer bundle

Extend `_card_from_file()` to include safe top-level metadata:

- `volatility`
- `evidence`
- `aliases`

Keep values as parsed frontmatter, but normalize scalar/list where useful for
display. Do not include raw source bodies or credential-like data.

**Verify**:

Add/extend `tests/test_viewer_bundle.py` using `EXAMPLE_V2`:

- `m-sla1` carries `volatility == "high"` and evidence
  `["srcevt-btx-0630"]`.
- `r-ki` carries aliases including `КИ`.

Run:

```bash
python3 -m unittest tests.test_viewer_bundle
```

Expected: tests pass.

### Step 2: Fix source coverage semantics

Change `_health()` so `source == "unknown"` is unresolved, not resolved. Add
health details that let the viewer name the gap:

- `sourceResolvedPct`
- `unresolvedSourceCardIds`
- `unknownSourceCardIds`
- optionally `cardsBySource` for the source page.

Do not make `unknown` fatal by itself; accepted legacy models may still carry
unknown source. The viewer should show the gap.

**Verify**:

Add a small unit test in `tests/test_viewer_bundle.py` with a temporary card
list or fixture that includes `source: unknown`; assert it lowers resolved
coverage and appears in unresolved ids.

### Step 3: Build source dependency/readiness projection

In `build_viewer_bundle.py`, add a bounded source projection to the bundle:

```json
"sourceTrust": {
  "sources": [
    {
      "id": "src-bitrix24-export",
      "trust": "accepted",
      "accessMode": "synthetic-fixture",
      "dependentCardIds": ["m-sla1", "st-deal"],
      "dependentCardCount": 2,
      "readinessStatus": "live-proven | failed | configured | unknown",
      "lastProofId": "proof-..."
    }
  ],
  "unresolvedSourceCardIds": [],
  "unknownSourceCardIds": []
}
```

Use existing `sourceReadiness.sourceInstanceIdsByStatus` and
`lastProofIdsBySource` when ids match. If they do not match, mark readiness as
`unknown`; do not invent proof.

**Verify**:

Extend `tests/test_viewer_bundle.py`:

- v2 source `src-bitrix24-export` lists dependent cards including `m-sla1` and
  `st-deal`.
- unknown sources are reported.

### Step 4: Render trust fields in the UI

Update `viewer/index.html`:

- Card meta shows `volatility`, evidence count/list, aliases.
- `#sources` shows dependent card count and links, readiness status, last proof
  id, and a visible synthetic-fixture marker when access mode contains
  `synthetic-fixture`.
- `#overview` includes source unresolved count in "Что проверить в первую
  очередь".

Keep raw source content out of the page.

**Verify**:

Add static assertions in `tests/test_viewer_bundle.py` for the new UI strings
and field names. Run focused tests.

### Step 5: Update documentation

Update `viewer/README.md`:

- describe `volatility/evidence/aliases`;
- describe `sourceTrust`;
- state that `unknown` source is visible as unresolved;
- state that source readiness/proof is a trust indicator, not acceptance.

**Verify**:

Focused tests pass.

## Required review loop

1. Run `code-reviewer`: check source coverage math, metadata leakage, and tests.
2. Run `improve-codebase-architecture`: check that trust projection belongs in
   the bundle layer and does not duplicate model truth.
3. Run `ponytail:ponytail-review`: cut unused fields or speculative display
   widgets; keep evidence, volatility, aliases, source dependents, and proof
   status.
4. Fix findings and re-run all three reviews.

## Test plan

- Unit tests for bundle metadata fields.
- Unit tests for source coverage and unknown-source behavior.
- Static HTML tests for source/trust rendering strings.
- Existing publish tests to ensure report and bundle still align.

## Done criteria

- [ ] `volatility`, `evidence`, and `aliases` survive into `ontology.json`.
- [ ] Cards display those fields outside technical JSON.
- [ ] `source == "unknown"` is unresolved in health.
- [ ] Source page shows dependent cards and readiness/proof state.
- [ ] No raw source payloads or secrets enter the bundle.
- [ ] `python3 -m unittest tests.test_viewer_bundle tests.test_publish_viewer` passes.
- [ ] `python3 -m unittest discover tests` passes.
- [ ] `python3 scripts/run_evals.py --fixture-only` passes.
- [ ] `python3 scripts/package_self_test.py --suite-timeout 180` passes.
- [ ] `git diff --check` passes.
- [ ] `plans/README.md` row for plan 029 is updated.

## STOP conditions

Stop and report if:

- Trust fields contain raw private source excerpts or PII.
- Matching source readiness to source ids requires guessing.
- The fix requires changing the source-map contract rather than projecting
  current data.
- The official viewer patch from plan 028 is absent.

## Maintenance notes

Reviewer should check whether the page now distinguishes "accepted but weakly
evidenced" from "accepted and live-proven". That distinction is the product
value of this plan.

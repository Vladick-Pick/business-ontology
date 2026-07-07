# Plan 018: Separate v2 authoring contract from migration compatibility

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the next
> step. If a STOP condition occurs, stop and report; do not widen or rename the
> data-model v2 taxonomy.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 77d5a78..HEAD -- \
>   scripts/links_validate.py scripts/run_evals.py \
>   schemas/model-change-package.schema.json \
>   tests/test_model_change_package_schema.py tests/test_run_evals.py \
>   tests/test_links_validate_v2.py
> git diff --stat -- \
>   scripts/links_validate.py scripts/run_evals.py \
>   schemas/model-change-package.schema.json \
>   tests/test_model_change_package_schema.py tests/test_run_evals.py \
>   tests/test_links_validate_v2.py
> ```
>
> This plan was written against branch `codex/plan-017-data-model-v2-hard-gate`
> with plan 017's local working-tree changes present. If the plan-017 strict
> diagnostic code is absent, stop and execute plan 017 first.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: HIGH (schema/eval gate for model-change packages)
- **Depends on**: `plans/017-data-model-v2-hard-gate-0.10.0.md`
- **Category**: migration + tests + contract
- **Planned at**: commit `77d5a78`, 2026-07-06, plus local plan-017 working tree

## Why this matters

Plan 017 correctly keeps deprecated `module`, `concept`, and `in-state`
parseable so old models can produce useful migration diagnostics. That
compatibility set is not the same thing as the authoring contract for new
candidate cards. Today some schemas and eval checks still read the broad
compatibility constants, so a resident agent can produce a v1-shaped
`candidateCard` inside a model-change package even though release `0.10.0`
claims v2 hard-gate behavior.

The product requirement: new model-change packages and eval artifacts must use
v2-only card types and v2-only relations. Deprecated aliases remain accepted
only inside the migration validator path.

## Current state

- `scripts/links_validate.py` defines:
  - `CARD_TYPES` including v2 types plus deprecated aliases `module` and
    `concept`.
  - `DEPRECATED_TYPE_ALIASES = {"module": "business", "concept": ...}`.
  - `ALLOWED_LINKS` including `in-state` for compatibility.
  - `DEPRECATED_LINK_ALIASES = {"in-state": "lifecycle"}`.
- `schemas/card.schema.json` and `schemas/model-pack.schema.json` are already
  v2-only after plan 017.
- `schemas/model-change-package.schema.json:218-234` still includes
  `module` and `concept` in `changes[].candidateCard.type`.
- `schemas/model-change-package.schema.json:364-381` also includes
  `module` and `concept` in the non-decision status rule.
- `tests/test_model_change_package_schema.py:255-258` expects
  `candidateCard.type.enum == links_validate.CARD_TYPES`, which includes
  deprecated aliases.
- `tests/test_model_change_package_schema.py:276-278` expects the non-decision
  status rule to cover `links_validate.CARD_TYPES - {"decision"}`, also
  including deprecated aliases.
- `scripts/run_evals.py:1873-1890` checks candidate card type and links against
  `links_validate.CARD_TYPES` and `links_validate.ALLOWED_LINKS`, so evals can
  pass while still emitting v1 authoring aliases.
- `tests/test_run_evals.py:526-540` uses a bad accepted candidate fixture with
  `type: "concept"`, which currently hides whether `concept` is rejected as a
  type or only because `status: accepted`.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Schema tests | `python3 -m unittest tests.test_model_change_package_schema tests.test_model_pack_schema` | exit 0 |
| Eval runner tests | `python3 -m unittest tests.test_run_evals` | exit 0 |
| Strict validator tests | `python3 -m unittest tests.test_links_validate_v2` | exit 0 |
| Full unit suite | `python3 -m unittest discover tests` | exit 0 |
| Fixture evals | `python3 scripts/run_evals.py --fixture-only` | 0 failed |
| Syntax | `python3 -m py_compile runtime/*.py scripts/*.py` | exit 0 |
| Whitespace | `git diff --check` | no output |

## Scope

**In scope**:

- `scripts/links_validate.py`
- `scripts/run_evals.py`
- `schemas/model-change-package.schema.json`
- `tests/test_model_change_package_schema.py`
- `tests/test_run_evals.py`
- `tests/test_links_validate_v2.py` only if a helper import needs adjustment

**Out of scope**:

- Changing the v2 taxonomy or relation list.
- Removing migration compatibility from `links_validate.py`.
- Editing `runtime/model_compiler.py`; that is plan 019.
- Broad docs/viewer wording cleanup; that is plan 020.
- Rewriting eval fixtures wholesale unless a fixture directly proves this
  authoring-contract gate.

## Git workflow

- Stay on the operator-provided branch unless told otherwise:
  `codex/plan-017-data-model-v2-hard-gate`.
- Do not commit, push, or open a PR unless the operator asks.

## Architecture decision

**Context**: `CARD_TYPES` and `ALLOWED_LINKS` now serve two use cases:

1. compatibility parsing for old models during migration diagnostics;
2. authoring validation for new packages, staged proposals, schemas, and evals.

Using the same broad constant for both use cases caused the review finding:
`model-change-package.schema.json` still permits `module` and `concept`.

**Decision**: keep the broad constants for compatibility, but add explicit
authoring constants in `scripts/links_validate.py`:

```python
AUTHORING_CARD_TYPES = CARD_TYPES - set(DEPRECATED_TYPE_ALIASES)
AUTHORING_LINKS = ALLOWED_LINKS - set(DEPRECATED_LINK_ALIASES)
```

Schemas, model-change-package eval checks, and authoring tests must use the
authoring constants. Migration tests and strict transitional diagnostics may
continue to use the broad compatibility constants.

**Revisit condition**: if more migration-only fields appear, add them to the
same authoring/compatibility split instead of introducing another local enum.

## Steps

### Step 1: Add explicit authoring constants

Edit `scripts/links_validate.py` near `DEPRECATED_TYPE_ALIASES` and
`DEPRECATED_LINK_ALIASES`.

Add:

```python
AUTHORING_CARD_TYPES = CARD_TYPES - set(DEPRECATED_TYPE_ALIASES)
AUTHORING_LINKS = ALLOWED_LINKS - set(DEPRECATED_LINK_ALIASES)
```

Keep `CARD_TYPES` and `ALLOWED_LINKS` unchanged so old models can still be
parsed and reported during migration.

**Verify**:

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, "scripts")
import links_validate
assert "concept" in links_validate.CARD_TYPES
assert "module" in links_validate.CARD_TYPES
assert "concept" not in links_validate.AUTHORING_CARD_TYPES
assert "module" not in links_validate.AUTHORING_CARD_TYPES
assert "in-state" in links_validate.ALLOWED_LINKS
assert "in-state" not in links_validate.AUTHORING_LINKS
print("authoring constants ok")
PY
```

Expected: prints `authoring constants ok`.

### Step 2: Make model-change-package schema v2-only for candidate cards

Edit `schemas/model-change-package.schema.json`.

In `changes[].candidateCard.properties.type.enum`, remove:

- `"module"`
- `"concept"`

In the non-decision status rule under `changes[].candidateCard.allOf`, remove
the same two aliases from the type enum.

Do not remove `candidateCard` itself. The package still needs structured
candidate cards; only their authoring enum changes.

**Verify**:

```bash
python3 - <<'PY'
import json
from pathlib import Path
schema = json.loads(Path("schemas/model-change-package.schema.json").read_text())
candidate = schema["properties"]["changes"]["items"]["properties"]["candidateCard"]
types = set(candidate["properties"]["type"]["enum"])
assert "concept" not in types
assert "module" not in types
assert "business" in types
assert "artifact" in types
print("candidate card schema v2-only")
PY
```

Expected: prints `candidate card schema v2-only`.

### Step 3: Update schema tests to assert authoring, not compatibility

Edit `tests/test_model_change_package_schema.py`.

Change expectations in `test_candidate_card_contract_is_structured_and_non_accepted`:

- `candidateCard.type.enum` must equal `links_validate.AUTHORING_CARD_TYPES`.
- the non-decision rule enum must equal
  `links_validate.AUTHORING_CARD_TYPES - {"decision"}`.
- `candidateCard.links.properties` must equal `links_validate.AUTHORING_LINKS`.

Add explicit negative assertions:

```python
self.assertNotIn("concept", candidate_schema["properties"]["type"]["enum"])
self.assertNotIn("module", candidate_schema["properties"]["type"]["enum"])
self.assertNotIn("in-state", candidate_schema["properties"]["links"]["properties"])
```

**Verify**:

```bash
python3 -m unittest tests.test_model_change_package_schema
```

Expected: exit 0.

### Step 4: Make eval candidate-card checks v2-only

Edit `scripts/run_evals.py`.

In `check_candidate_card_payload`:

- replace `links_validate.CARD_TYPES` with `links_validate.AUTHORING_CARD_TYPES`
  for candidate card type validation.
- replace `links_validate.ALLOWED_LINKS` with `links_validate.AUTHORING_LINKS`
  for candidate card link validation.

Use error messages that name the authoring contract, for example:

```text
candidateCard.type is outside the v2 authoring card contract
candidateCard.links has non-authoring relations: in-state
```

Do not change migration fixtures or `links_validate` itself.

**Verify**:

```bash
python3 -m unittest tests.test_run_evals
```

Expected: exit 0 after tests are updated in the next step.

### Step 5: Add regression tests for deprecated candidate cards

Edit `tests/test_run_evals.py`.

Keep the existing accepted-candidate test, but change its type to a v2 type such
as `"artifact"` so it only tests accepted status rejection.

Add two focused tests:

1. A model-change package with `candidateCard.type = "concept"` fails with the
   v2 authoring-contract error.
2. A model-change package with `candidateCard.links = {"in-state": [...]}` fails
   with the non-authoring relation error.

Use the existing `valid_model_change_package()` helper as the fixture base.

**Verify**:

```bash
python3 -m unittest tests.test_run_evals
python3 scripts/run_evals.py --fixture-only
```

Expected: unit tests exit 0; fixture evals report 0 failed.

### Step 6: Run final verification

Run:

```bash
python3 -m unittest tests.test_model_change_package_schema tests.test_model_pack_schema tests.test_run_evals tests.test_links_validate_v2
python3 -m unittest discover tests
python3 scripts/run_evals.py --fixture-only
python3 scripts/package_self_test.py --suite-timeout 180
python3 -m py_compile runtime/*.py scripts/*.py
git diff --check
```

Expected:

- all unit tests pass;
- fixture evals report 0 failed;
- package self-test exits 0;
- `git diff --check` prints nothing.

## Test plan

Add or update tests for:

- model-change-package schema rejects v1 authoring aliases by construction;
- eval checker rejects `candidateCard.type = concept`;
- eval checker rejects `candidateCard.links.in-state`;
- existing accepted-status rejection still fails independently of type aliasing.

## Done criteria

- [ ] `links_validate.AUTHORING_CARD_TYPES` and `links_validate.AUTHORING_LINKS`
      exist.
- [ ] `schemas/model-change-package.schema.json` has no `concept`, `module`, or
      `in-state` in candidate authoring positions.
- [ ] `scripts/run_evals.py` validates `candidateCard` against authoring
      constants, not compatibility constants.
- [ ] Regression tests fail on deprecated candidate type and relation aliases.
- [ ] Full verification commands in Step 6 pass.
- [ ] `plans/README.md` row for plan 018 is updated by the executor.

## STOP conditions

Stop and report if:

- Removing `concept/module` from `model-change-package.schema.json` breaks a
  real current fixture that is not explicitly a migration fixture.
- A failing fixture requires changing runtime compiler behavior; that belongs
  in plan 019.
- A fix appears to require changing the v2 taxonomy, relation list, or source
  trust model.
- You cannot keep migration validation for old cards while enforcing v2-only
  candidate authoring.

## Maintenance notes

Reviewers should check every new schema/eval test for the same mistake this
plan fixes: using `CARD_TYPES` when the surface is an authoring surface. Future
migration aliases must be added to compatibility constants and excluded from
authoring constants in the same change.

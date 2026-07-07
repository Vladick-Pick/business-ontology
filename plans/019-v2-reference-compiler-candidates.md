# Plan 019: Make reference compiler output v2-promotable candidate packages

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the next
> step. If a STOP condition occurs, stop and report; do not invent business
> facts to make a candidate card pass validation.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 77d5a78..HEAD -- \
>   runtime/model_compiler.py tests/test_model_compiler.py \
>   scripts/run_evals.py tests/test_run_evals.py \
>   evals/fixtures/model-change-packages evals/fixtures/resident-runs \
>   examples/model-packs/acquisition.model-pack.json
> git diff --stat -- \
>   runtime/model_compiler.py tests/test_model_compiler.py \
>   scripts/run_evals.py tests/test_run_evals.py \
>   evals/fixtures/model-change-packages evals/fixtures/resident-runs \
>   examples/model-packs/acquisition.model-pack.json
> ```
>
> This plan depends on plan 018. If `links_validate.AUTHORING_CARD_TYPES` and
> `links_validate.AUTHORING_LINKS` do not exist, stop and execute plan 018 first.

## Status

- **Priority**: P1
- **Effort**: M-L
- **Risk**: HIGH (source-event to review-package behavior)
- **Depends on**: `plans/018-v2-authoring-contract-boundary.md`
- **Category**: correctness + migration + tests
- **Planned at**: commit `77d5a78`, 2026-07-06, plus local plan-017 working tree

## Why this matters

The hard gate is only useful if the agent's source-event pipeline emits
reviewable objects that can become valid v2 proposals. Today the reference
compiler can output `candidateCard` payloads that pass the package schema but
would fail strict card validation during promotion. That turns the human review
step into manual repair work and weakens the product promise: source material
should become bounded review material, not invalid v1-shaped card drafts.

The method rule: when the source evidence is too thin to build a complete v2
card, the compiler should emit a drift/review item or a needs-info item, not an
invalid candidate card.

## Current state

- `runtime/model_compiler.py:300-331` builds a handoff `candidateCard` with:
  - `type: "interface"`;
  - `owner: "role:acquisition-owner"`;
  - `attrs.participants`, `attrs.quality-criterion`, and `attrs.outcome`;
  - no `attrs.contract`.
- `runtime/model_compiler.py:335-357` builds a state `candidateCard` with:
  - `type: "state"`;
  - `owner` from source authority such as `"role:systems-owner"`;
  - only `attrs.entity`.
- Data model v2 strict validation requires:
  - card `owner` resolves to a role-card id or is exactly `unknown`;
  - interface cards have `attrs.contract` as a transitional hard-gate field;
  - state cards have `attrs.states`, `attrs.entry`, `attrs.terminal`, and
    `attrs.transitions` as strict `0.10.0+` fields.
- Running the compiler currently demonstrates the issue:

```bash
python3 scripts/compile_model_change.py \
  --model-pack examples/model-packs/acquisition.model-pack.json \
  --source-event evals/fixtures/source-events/telegram-export.synthetic.json
```

The output contains:

```json
"candidateCard": {
  "id": "if-acquisition-sales-handoff",
  "type": "interface",
  "owner": "role:acquisition-owner",
  "attrs": {
    "participants": {"supplier": ["role-attraction-supplier"], "...": "..."},
    "quality-criterion": "Qualification notes are visible before sales acceptance.",
    "outcome": "Qualified lead accepted into the sales queue."
  }
}
```

For the CRM stage event:

```bash
python3 scripts/compile_model_change.py \
  --model-pack examples/model-packs/acquisition.model-pack.json \
  --source-event evals/fixtures/source-events/crm-export.synthetic.json
```

The output contains:

```json
"candidateCard": {
  "id": "state-partner-review",
  "type": "state",
  "owner": "role:systems-owner",
  "attrs": {"entity": "prospective-participant"}
}
```

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Compiler tests | `python3 -m unittest tests.test_model_compiler` | exit 0 |
| Eval checker tests | `python3 -m unittest tests.test_run_evals` | exit 0 |
| Model-change package schema tests | `python3 -m unittest tests.test_model_change_package_schema` | exit 0 |
| Fixture evals | `python3 scripts/run_evals.py --fixture-only` | 0 failed |
| Full unit suite | `python3 -m unittest discover tests` | exit 0 |
| Syntax | `python3 -m py_compile runtime/*.py scripts/*.py` | exit 0 |
| Whitespace | `git diff --check` | no output |

## Scope

**In scope**:

- `runtime/model_compiler.py`
- `tests/test_model_compiler.py`
- `scripts/run_evals.py` only if plan 018 did not already add reusable
  candidate-card validation helpers.
- `tests/test_run_evals.py` only for compiler-output regression coverage.
- A small number of JSON fixtures under `evals/fixtures/**` if expected runtime
  outputs change.
- `examples/model-packs/acquisition.model-pack.json` only if a small
  model-pack field is required to map review actor tokens to card owner ids.

**Out of scope**:

- Building the production LLM extractor.
- Adding new source connectors.
- Changing review-owner semantics for `review.owner` or `sourceEvent.authority`.
- Inventing accepted role cards in the model from package config alone.
- Auto-promoting any compiler output to accepted truth.

## Git workflow

- Stay on the operator-provided branch unless told otherwise:
  `codex/plan-017-data-model-v2-hard-gate`.
- Do not commit, push, or open a PR unless the operator asks.

## Architecture decision

**Context**: There are two owner languages:

- package/review owner tokens such as `role:acquisition-owner`, which route
  human review and are valid in model packs, review packages, and human
  requests;
- card owner ids such as `acquisition-lead`, which must resolve to `type: role`
  cards in the accepted model or be exactly `unknown`.

**Decision**: keep review owner tokens for routing, but never write a
`role:*` token into `candidateCard.owner`. For candidate cards, use a resolved
role-card id only when the compiler can prove it from accepted context or an
explicit model-pack mapping. Otherwise use `unknown` and route the review to
the package owner.

For incomplete lifecycle evidence, prefer a drift/review item over an invalid
state `candidateCard`. A single newly observed CRM stage is evidence that the
accepted lifecycle may be stale; it is not enough by itself to author a complete
state-machine card unless the source event provides all required v2 fields.

## Steps

### Step 1: Add compiler-side owner normalization for candidate cards

In `runtime/model_compiler.py`, add a small helper near owner helpers:

```python
def _candidate_card_owner(value: str | None) -> str:
    if not value:
        return "unknown"
    if value.startswith("role:"):
        return "unknown"
    return value
```

If the accepted context already exposes resolvable role ids in a structured
field, use that instead of the simple helper, but do not invent a new broad
context contract in this plan. Keep the smallest correct behavior: candidate
card owner is either a card id or `unknown`.

Apply this helper only to `candidateCard.owner`, not to:

- `review.owner`;
- source-event authority owner;
- human request owner;
- review package affected owners.

**Verify**:

```bash
python3 scripts/compile_model_change.py \
  --model-pack examples/model-packs/acquisition.model-pack.json \
  --source-event evals/fixtures/source-events/telegram-export.synthetic.json \
  | python3 -m json.tool | rg '"owner":'
```

Expected: `review.owner` may still be `role:...`; `candidateCard.owner` is not
`role:...`.

### Step 2: Make handoff interface candidates v2-complete

In `_handoff_change`, add `attrs.contract: "handoff"` to the interface
candidate. Keep existing `participants`, `quality-criterion`, and `outcome`.

Ensure the candidate still uses:

- `type: "interface"`;
- `status` at or below source trust;
- `links.supplies-to` only if target ids are known from the accepted model or
  current fixture assumptions.

If the compiler cannot provide participants, quality criterion, or outcome for
another handoff source event, it must not emit an interface candidate. That
fallback can be `needs-info` or a review item; do not create partial interface
cards.

**Verify**:

```bash
python3 scripts/compile_model_change.py \
  --model-pack examples/model-packs/acquisition.model-pack.json \
  --source-event evals/fixtures/source-events/telegram-export.synthetic.json \
  | python3 -m json.tool | rg -n '"contract": "handoff"|"candidateCard"|"owner"'
```

Expected: candidate card has `attrs.contract = "handoff"` and candidate owner
is `unknown` or a role-card id, not `role:*`.

### Step 3: Stop emitting incomplete state cards from single-stage drift

In `_new_state_change`, do not emit a `candidateCard` unless you can fill a full
v2 state-machine card:

- `attrs.entity`
- `attrs.states`
- `attrs.entry`
- `attrs.terminal`
- `attrs.transitions`

For the current CRM stage drift fixture, change the output to a drift/review
change without `candidateCard`. Recommended shape:

```python
{
  "kind": "drift",
  "affectedIds": ["lead-lifecycle"],
  "proposedAction": "open-drift-review",
  "drift": {
    "was": "Accepted lifecycle does not include partner review.",
    "now": "CRM export shows a partner review stage between qualified and offer-ready.",
    "reason": "Source event indicates lifecycle drift; full state-machine edit needs review."
  }
}
```

Keep evidence, claim kind, evidence grade, source risk, confidence, and risk.
Do not invent a complete state machine from one stage name.

**Verify**:

```bash
python3 scripts/compile_model_change.py \
  --model-pack examples/model-packs/acquisition.model-pack.json \
  --source-event evals/fixtures/source-events/crm-export.synthetic.json \
  | python3 -m json.tool | rg -n '"kind": "drift"|"candidateCard"|"open-drift-review"'
```

Expected: kind/action reflect drift review; no `candidateCard` appears for this
single-stage source event.

### Step 4: Validate candidate cards through the same path evals use

Add tests in `tests/test_model_compiler.py`:

1. Handoff compiler output contains an interface `candidateCard` that passes
   `scripts.run_evals.check_candidate_card_payload`.
2. Handoff compiler output has no `role:` prefix in `candidateCard.owner`.
3. CRM stage drift compiler output has no `candidateCard`; it records a drift
   review item for `lead-lifecycle`.

Use existing test style in `tests/test_model_compiler.py`.

**Verify**:

```bash
python3 -m unittest tests.test_model_compiler
```

Expected: exit 0.

### Step 5: Update fixtures that assert old compiler output

Search:

```bash
rg -n '"state-partner-review"|"role:acquisition-owner"|"role:systems-owner"|open-drift-review|candidateCard' \
  evals tests runtime
```

Update only fixtures/tests that encode the changed compiler output. Do not
rewrite unrelated historical fixtures unless they now fail under plan 018's
authoring checks.

If an eval fixture intentionally represents a legacy pre-0.10 artifact, mark it
as migration/legacy in the test or keep it outside the v2 authoring checker.

**Verify**:

```bash
python3 -m unittest tests.test_run_evals tests.test_model_change_package_schema
python3 scripts/run_evals.py --fixture-only
```

Expected: exit 0 and 0 failed evals.

### Step 6: Run final verification

Run:

```bash
python3 -m unittest tests.test_model_compiler tests.test_run_evals tests.test_model_change_package_schema
python3 -m unittest discover tests
python3 scripts/run_evals.py --fixture-only
python3 scripts/package_self_test.py --suite-timeout 180
python3 -m py_compile runtime/*.py scripts/*.py
git diff --check
```

Expected: all pass.

## Test plan

Add tests for:

- compiler handoff candidate card is v2-authoring valid;
- compiler handoff candidate card owner is `unknown` or a role-card id, never
  a `role:*` review token;
- compiler CRM stage drift does not emit an incomplete state card;
- eval/package checks still reject accepted candidate cards and deprecated
  authoring aliases from plan 018.

## Done criteria

- [ ] No `candidateCard.owner` emitted by the reference compiler starts with
      `role:`.
- [ ] Handoff interface candidate includes `attrs.contract: handoff`.
- [ ] CRM single-stage drift no longer emits an incomplete `state`
      `candidateCard`.
- [ ] Compiler output candidate cards pass the v2 authoring checker.
- [ ] Fixture evals and full unit suite pass.
- [ ] `plans/README.md` row for plan 019 is updated by the executor.

## STOP conditions

Stop and report if:

- The only way to create a valid candidate card is to invent facts not present
  in the source event or accepted context.
- Changing `_new_state_change` would require a new model-change package schema
  shape not already present.
- A production behavior depends on `candidateCard.owner` carrying `role:*`
  tokens. In that case, the code is using one field for two meanings and needs
  an explicit design decision before implementation continues.
- More than three fixture families need broad rewrites; the plan may be too
  large and should be split.

## Maintenance notes

Reviewers should distinguish review routing from model ownership. `role:*`
tokens are acceptable in review/package/human-request routing fields, but not
inside future card frontmatter. Future compiler branches should pass their
candidate card payloads through the same authoring checker before fixtures are
accepted.

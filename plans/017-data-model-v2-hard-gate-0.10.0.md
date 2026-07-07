# Plan 017: Data model v2 hard gate — transitional warnings become errors in 0.10.0

> **Executor instructions**: Follow this plan step by step. Run every
> verification command before moving to the next step. If a STOP condition
> occurs, stop and report; do not make broad schema or ontology decisions on
> your own.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 77d5a78..HEAD -- \
>   agent-package.yaml CHANGELOG.md scripts/links_validate.py \
>   scripts/apply_package_update.py skills/package-update/SKILL.md \
>   tests/test_links_validate_v2.py tests/test_apply_package_update.py \
>   examples/acquisition-ontology staged plans/README.md
> python3 scripts/links_validate.py .
> python3 scripts/links_validate.py . --staged
> ```
>
> Expected at the planned commit: package version is `0.9.1`; both validator
> commands exit `0`; promoted scope prints `errors: 0` with 20 warnings;
> promoted+staged prints `errors: 0` with 21 warnings. If the warning set or
> package version changed, reconcile the plan against live code before editing.

## Status

- **Priority**: P1
- **Effort**: M-L
- **Risk**: HIGH (schema gate, release behavior, model migration pressure)
- **Depends on**: `plans/012-package-update-mechanism.md`
- **Category**: migration + validator + updater gate + release
- **Planned at**: commit `77d5a78`, 2026-07-06

## Product meaning

Release `0.10.0` is a model-quality release, not a new source connector
release. Its product promise is simple: a resident analyst running this package
can say whether the accepted model is clean under data model v2. If the model
still uses transitional v1 compatibility, the package must refuse automatic
installation, return `migration-required`, create a reviewable migration path,
and ask the owner through the normal human gate. No package update may silently
rewrite the accepted model.

## Why this matters

Data model v2 shipped with a deliberate one-version grace period. That grace
period is now a product risk: if warnings stay warnings forever, downstream
agents cannot know whether the company model is v2-clean or still partly v1.
The package update mechanism from plan 012 already has the right safety shape:
validate a copy of the model, block install on schema failure, and request a
reviewed migration. Plan 017 makes the first real use of that gate.

The important split: not every warning becomes an error. Only transitional
compatibility warnings become hard failures in `0.10.0`; audit hints that are
not v1 compatibility, such as `business has no links.produces`, may remain
warnings if they are explicitly classified and tested.

## Current state

- `agent-package.yaml` currently says `version: "0.9.1"`.
- `CHANGELOG.md:42-43` reserves `0.10.0` for turning transitional warnings into
  errors.
- `CHANGELOG.md:99-101` says that from `0.10.0` onward transitional data-model
  warnings are expected to become errors.
- `plans/README.md:94-97` still carries this as backlog, not an executable
  plan.
- `scripts/links_validate.py:223-225` says `SOFT_REQUIRED_ATTRS` is only for one
  transitional version.
- `scripts/links_validate.py:253-258` defines soft v2 fields:
  `production-system.attrs.business`, `state.attrs.states|entry|terminal|transitions`,
  `interface.attrs.contract`, and `decision.attrs.norm-kind`.
- `scripts/links_validate.py:624-629` currently appends warning text for those
  missing fields instead of errors.
- `scripts/links_validate.py:832-868` warns for deprecated type/relation
  aliases: `type: module` and `links.in-state`.
- `scripts/links_validate.py:1421-1438` warns when `owner:` does not resolve to
  a role card or `unknown`.
- `scripts/links_validate.py:1461-1486` warns when `owns` and `part-of`
  duplicate the same containment fact for the old v1 pattern.
- `scripts/links_validate.py:1489-1497` warns when a business has no
  `links.produces`. This is an audit warning, not automatically a transitional
  warning.
- `scripts/apply_package_update.py:217-220` already blocks update with exit `3`
  and JSON `{"status": "migration-required"}` when validation of the copied
  model fails.
- `skills/package-update/SKILL.md:60-64` already instructs the agent to prepare a
  migration package and record `human_request kind=migration` on schema gate
  failure.
- Current validator output at planned commit:

```text
python3 scripts/links_validate.py .
Cards: 25 (promoted)  |  errors: 0
20 WARNING lines

python3 scripts/links_validate.py . --staged
Cards: 26 (promoted+staged)  |  errors: 0
21 WARNING lines
```

Current warning families:

| Family | Current examples | 0.10.0 behavior |
|---|---|---|
| Missing v2 soft attrs | `attrs.norm-kind`, `attrs.business`, state fields, `attrs.contract` | error |
| Deprecated v1 aliases | `type: module`, `links.in-state` | error |
| Owner not role-id/unknown | `owner 'revenue-lead' does not resolve...` | error |
| Duplicate v1 containment | `owns -> ps-attraction` plus inverse `part-of` | error |
| Audit warning | `business '<id>' has no links.produces` | stay warning unless separately decided |
| Interface lint | `contract: handoff` with `slas` filled | stay warning unless separately decided |

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Focused validator tests | `python3 -m unittest tests.test_links_validate_v2` | exit 0 |
| Update-gate tests | `python3 -m unittest tests.test_apply_package_update tests.test_check_package_updates` | exit 0 |
| Full unit suite | `python3 -m unittest discover tests` | exit 0 |
| Fixture evals | `python3 scripts/run_evals.py --fixture-only` | 0 failed |
| Package self-test | `python3 scripts/package_self_test.py --suite-timeout 180` | exit 0 |
| Promoted validation | `python3 scripts/links_validate.py .` | exit 0, `errors: 0`, no transitional warnings |
| Promoted+staged validation | `python3 scripts/links_validate.py . --staged` | exit 0, `errors: 0`, no transitional warnings |
| Syntax | `python3 -m py_compile runtime/*.py scripts/*.py` | exit 0 |
| Whitespace | `git diff --check` | no output |

Record actual final test/eval counts in the PR summary. Do not guess counts.

## Scope

**In scope**:

- `scripts/links_validate.py`
- `tests/test_links_validate_v2.py`
- `tests/test_apply_package_update.py`
- `tests/test_check_package_updates.py` only if the changelog/update wording
  expectation needs a small fixture update.
- `examples/acquisition-ontology/**`
- `staged/d-data-model-v2.md`
- `agent-package.yaml`
- `CHANGELOG.md`
- `skills/package-update/SKILL.md`
- `deployment/MIGRATION_POLICY.md` or `deployment/UPDATE.md` only if existing
  release/update docs do not mention the `0.10.0` gate.
- `plans/README.md`

**Out of scope**:

- New source connectors, Telegram, Zoom, Skribby, schedulers, or live proof.
- Automatic model migration during package update.
- Changing the v2 taxonomy, relation list, or type names.
- Making all warnings fatal.
- Rewriting accepted business meaning inside examples. Structural fixture
  migration is allowed; invented truth is not.
- Editing raw source material or storing private data.

## Git workflow

- Branch from current `main`: `codex/data-model-v2-hard-gate-0.10.0`.
- Use focused commits:
  1. validator classification and tests;
  2. fixture/example migration;
  3. updater/release docs and version bump.
- Do not push or open a PR unless the operator asks.

## Architecture decision

**Context**: The validator currently has a single `warnings: list[str]`. That is
too coarse for `0.10.0`: it cannot distinguish a warning that was explicitly
temporary from a warning that should remain a quality hint.

**Options**:

1. Turn every warning into an error when package version is `>=0.10.0`.
   Rejected: this would make audit hints fatal and would couple future lint
   additions to release breakage.
2. Remove all transitional warnings by deleting compatibility aliases.
   Rejected: the updater still needs to validate old model copies and return a
   migration-required report with useful messages.
3. Classify warnings by code/category, then promote only transitional codes to
   errors under the `0.10.0` gate.

**Decision**: implement option 3. Add an internal warning representation or
helper that carries at least `code`, `message`, and `category`, while preserving
the existing human-readable CLI output shape. The hard gate promotes only
`category == transitional` to errors.

**Consequences**: tests must prove both sides: old transitional shapes fail
under the `0.10.0` gate, and advisory warnings still print as warnings without
causing a non-zero exit.

**Revisit condition**: if warning classification becomes large or leaks across
many scripts, split validator diagnostics into a small dataclass in
`scripts/links_validate.py`; do not create a new package dependency.

## Steps

### Step 1: Drift and classify the current warning set

Run the drift commands at the top of the plan. Then run:

```bash
python3 scripts/links_validate.py . | tee /tmp/bo-links-promoted.txt
python3 scripts/links_validate.py . --staged | tee /tmp/bo-links-staged.txt
```

Map each current warning to one of these categories:

- `transitional`: missing soft v2 attrs, deprecated v1 type/relation aliases,
  unresolved owners, duplicate v1 `owns`+`part-of`.
- `advisory`: business without `produces`, handoff interface with SLAs, term
  shape hints, or future non-migration lint.

**Verify**:

```bash
grep -c "WARNING:" /tmp/bo-links-promoted.txt
grep -c "WARNING:" /tmp/bo-links-staged.txt
```

Expected at planned commit: `20` and `21`.

### Step 2: Add structured validator diagnostics

In `scripts/links_validate.py`, replace ad hoc string-only warning appends with
a minimal internal diagnostic shape. Keep it dependency-free. A reasonable shape:

```python
@dataclass
class WarningDiagnostic:
    code: str
    message: str
    category: str = "advisory"
```

Add a helper such as:

```python
def add_warning(warnings, code, message, *, category="advisory"):
    warnings.append(WarningDiagnostic(code=code, message=message, category=category))
```

Use stable codes:

- `missing-soft-required-attr`
- `deprecated-type-alias`
- `deprecated-link-alias`
- `owner-not-role`
- `duplicate-owns-part-of`
- `business-without-produces`
- `handoff-interface-with-slas`

If there are other warning sites, classify them deliberately. Do not leave a
bare `warnings.append(` for new or existing validator warnings.

**Verify**:

```bash
rg -n "warnings\\.append\\(" scripts/links_validate.py
python3 -m unittest tests.test_links_validate_v2
python3 scripts/links_validate.py .
```

Expected: no unreviewed bare warning appends remain except inside the new helper
if you keep that implementation; existing non-strict behavior still exits `0`.

### Step 3: Implement the 0.10.0 strict transitional gate

Add a package-version-aware gate:

- Read `version: "..."` from `<ontology-root>/agent-package.yaml` when the root
  being validated is this package repository.
- Treat package version `>= 0.10.0` as strict for transitional warnings.
- Add `--strict-transitional` for tests and for validating external model copies
  when version inference is not enough.
- Keep `--staged` behavior.
- Unknown package version should not silently enable strict mode; emit normal
  warnings unless `--strict-transitional` is passed.

When strict mode is active, transitional diagnostics should be printed as
`ERROR:` or otherwise added to `errors` so the exit code is `1`. Advisory
diagnostics should still be printed as `WARNING:` and should not change the
exit code.

**Verify**:

```bash
python3 scripts/links_validate.py . --strict-transitional
```

Expected before migrating examples: exit `1` with errors for the current
transitional warning families. This temporary failure proves the gate can fail.

### Step 4: Expand validator tests

Update `tests/test_links_validate_v2.py`. Preserve existing non-strict tests
that prove v1 forms still warn in compatibility mode. Add strict-mode tests for:

- `type: module` fails under `--strict-transitional`.
- `links.in-state` fails under `--strict-transitional`.
- missing `decision.attrs.norm-kind` fails under `--strict-transitional`.
- missing `state.attrs.states|entry|terminal|transitions` fails under
  `--strict-transitional`.
- `owner:` that is neither a role id nor `unknown` fails under
  `--strict-transitional`.
- duplicate `owns` + inverse `part-of` fails under `--strict-transitional`.
- `business` without `links.produces` stays a warning under
  `--strict-transitional`.

If package-version inference is implemented, add a temp-root test where
`agent-package.yaml` is `0.10.0` and no explicit strict flag is passed; the same
transitional fixture must fail. Add a matching `0.9.1` test that still warns and
exits `0`.

**Verify**:

```bash
python3 -m unittest tests.test_links_validate_v2
```

Expected: all tests pass and the new tests prove strict/non-strict polarity.

### Step 5: Migrate the repo examples and staged fixture to v2-clean shape

Make the current repository pass the strict gate without inventing new business
truth.

Known current files to inspect:

- `examples/acquisition-ontology/modules/acquisition.md`
- `examples/acquisition-ontology/production-systems/ps-attraction.md`
- `examples/acquisition-ontology/interfaces/if-attraction-sales.md`
- `examples/acquisition-ontology/states/lead-lifecycle.md`
- `examples/acquisition-ontology/decisions/d-handoff-quality.md`
- `examples/acquisition-ontology/concepts/qualified-lead.md`
- other `examples/acquisition-ontology/concepts/*.md` files with non-role
  owners.
- `staged/d-data-model-v2.md`

Allowed structural migrations:

- `type: module` -> `type: business`.
- Move v1 containment into canonical `links.part-of` where evidence already
  exists.
- Replace `links.in-state` with `links.lifecycle`.
- Fill `attrs.business`, `attrs.contract`, `attrs.norm-kind`, and state machine
  attrs with `unknown` only where the current fixture lacks evidence.
- Change unresolved free-text owners to `unknown` unless an existing role card
  already represents that role. Do not invent a role card only to silence the
  validator.
- Remove duplicate containment edge when the same fact is already represented
  by the canonical direction.

Do not use this step to improve the example model beyond the hard gate. If an
example needs real domain interpretation, leave `unknown` and let review decide
later.

**Verify**:

```bash
python3 scripts/links_validate.py . --strict-transitional
python3 scripts/links_validate.py . --staged --strict-transitional
```

Expected: both exit `0`; no `ERROR:` lines; no warnings whose text says
`one transitional version`, `deprecated`, `will become an error`, or
`owner ... does not resolve`.

### Step 6: Wire strict validation into package update schema gate

Ensure update validation uses the new release's validator in strict mode for
`0.10.0` and later. The existing safety boundary must remain intact:
`apply_package_update.py` validates a temporary copy of the model and must not
pass the real model path to code from the new release.

Add or update tests in `tests/test_apply_package_update.py`:

- A release fixture tagged `v0.10.0` whose validator reports a transitional
  failure must return exit `3` and JSON `status: migration-required`.
- `package/current` must still point at the old release after that failure.
- The real model repo snapshot must be unchanged.
- Rollback must still not require or mutate a model repo.

If existing tests use a dummy validator that only exits `0`/`1`, extend the
fixture so at least one test proves the real contract: transitional schema
failure blocks the flip.

**Verify**:

```bash
python3 -m unittest tests.test_apply_package_update tests.test_check_package_updates
```

Expected: all tests pass; at least one assertion checks `migration-required`.

### Step 7: Update package-update behavior and release docs

Update `skills/package-update/SKILL.md` only if it lacks this specificity:

- On `migration-required` caused by `0.10.0` transitional errors, the agent
  prepares a model-change migration package.
- The package must explain which cards/fields need migration.
- The agent records `human_request kind=migration` before asking the owner.
- The agent does not apply the model migration automatically.

Update release docs only where stale:

- `CHANGELOG.md`: add a new `0.10.0` section at the top. Product wording should
  say: data model v2 hard gate, strict transitional errors, update blocks with
  migration-required, accepted model remains human-reviewed.
- `agent-package.yaml`: bump to `version: "0.10.0"`.
- `deployment/MIGRATION_POLICY.md` or `deployment/UPDATE.md`: mention the
  strict gate only if those files currently imply updates always apply after
  package self-test.

**Verify**:

```bash
rg -n "0\\.10\\.0|migration-required|strict transitional|transitional warnings" \
  CHANGELOG.md agent-package.yaml skills/package-update/SKILL.md deployment
```

Expected: `0.10.0` release meaning is discoverable without reading this plan.

### Step 8: Full verification

Run the full gate:

```bash
python3 -m unittest discover tests
python3 scripts/run_evals.py --fixture-only
python3 scripts/package_self_test.py --suite-timeout 180
python3 scripts/links_validate.py .
python3 scripts/links_validate.py . --staged
python3 scripts/links_validate.py . --strict-transitional
python3 scripts/links_validate.py . --staged --strict-transitional
python3 -m py_compile runtime/*.py scripts/*.py
git diff --check
```

Expected: all exit `0`. Record actual unit/eval counts and any remaining
advisory warnings in the PR summary.

## Test plan

Add or update tests in `tests/test_links_validate_v2.py` for strict-mode
polarity. Use the existing temp-directory card fixtures in that file; do not
introduce network, external services, or non-stdlib dependencies.

Add or update tests in `tests/test_apply_package_update.py` for update blocking.
Use the existing local git fixture pattern. The test must prove:

- failing schema validation returns exit `3`;
- JSON payload contains `status: migration-required`;
- `package/current` does not flip;
- the real model repo is unchanged.

Do not add live Telegram/Zoom tests to this plan.

## Done criteria

All must hold:

- [ ] `agent-package.yaml` version is `0.10.0`.
- [ ] `CHANGELOG.md` has a top `0.10.0` section explaining the hard gate in
  product terms.
- [ ] `scripts/links_validate.py` has classified diagnostics; transitional
  warnings are hard errors in strict mode or package version `>=0.10.0`.
- [ ] Advisory warnings remain warnings and are covered by at least one test.
- [ ] `python3 scripts/links_validate.py .` exits `0` with no transitional
  warnings.
- [ ] `python3 scripts/links_validate.py . --staged` exits `0` with no
  transitional warnings.
- [ ] `python3 scripts/links_validate.py . --strict-transitional` exits `0`.
- [ ] `python3 scripts/links_validate.py . --staged --strict-transitional` exits
  `0`.
- [ ] Update gate tests prove `migration-required` blocks install for a
  transitional schema failure.
- [ ] Full unit tests, fixture evals, package self-test, py_compile, and
  `git diff --check` pass.
- [ ] `plans/README.md` row 017 is updated from `TODO` to the final state.

## STOP conditions

Stop and report if:

- Current code no longer matches the excerpts above and the executor cannot
  identify the equivalent live locations.
- The solution requires making all warnings fatal instead of classifying them.
- The fix requires changing the v2 taxonomy, relation list, or accepted product
  semantics.
- Migrating `examples/acquisition-ontology` would require inventing role/source
  truth not already present in the fixture.
- `apply_package_update.py` would need to pass the real model repo path to code
  from the new release. That violates plan 012.
- Strict validation blocks on an advisory warning rather than a transitional
  warning.
- Verification fails twice after a focused fix attempt.

## Maintenance notes

Reviewers should focus on three things:

- The diagnostic categories are precise; `0.10.0` must not turn every future lint
  into a breaking release.
- The update path still validates a copy of the model and returns
  `migration-required` instead of writing to the model.
- The migrated example ontology is v2-clean structurally without pretending that
  unknown owners, lifecycle states, or decision kinds were known from evidence.

Future schema migrations should reuse this pattern: temporary compatibility
warnings get stable codes, a release number, strict-mode tests, and an updater
schema-gate test before the grace period ends.

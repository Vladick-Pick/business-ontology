# Plan 020: Align specs, skills, eval docs, and viewer with data model v2

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the next
> step. If a STOP condition occurs, stop and report; do not convert migration
> reference sections into authoring instructions.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 77d5a78..HEAD -- \
>   specs/BUSINESS-ONTOLOGY-RESIDENT.md staged/README.md evals/README.md \
>   skills references viewer tests/test_viewer_bundle.py scripts/build_viewer_bundle.py
> git diff --stat -- \
>   specs/BUSINESS-ONTOLOGY-RESIDENT.md staged/README.md evals/README.md \
>   skills references viewer tests/test_viewer_bundle.py scripts/build_viewer_bundle.py
> ```
>
> This plan should run after plans 018 and 019, so docs and viewer examples can
> point at the same v2 authoring contract as schemas/evals/runtime.

## Status

- **Priority**: P1
- **Effort**: M-L
- **Risk**: MED (product wording + viewer demo behavior)
- **Depends on**: `plans/018-v2-authoring-contract-boundary.md`,
  `plans/019-v2-reference-compiler-candidates.md`
- **Category**: docs + product UX + methodology
- **Planned at**: commit `77d5a78`, 2026-07-06, plus local plan-017 working tree

## Why this matters

Release `0.10.0` is supposed to change how agents author the business model:
v2 types and relations are the only normal language; v1 aliases exist only to
diagnose old models. The code gate is not enough if first-read specs, skill
instructions, eval docs, and the viewer still teach `concept`, `module`, or
`in-state` as current examples.

The product result after this plan: a human or installed agent reading the
package sees one contract everywhere. Old names may appear only in explicitly
marked migration/deprecated sections.

## Current state

Confirmed review findings:

- `specs/BUSINESS-ONTOLOGY-RESIDENT.md:49` still says the closed relation list
  has exactly nine relations and includes `in-state`.
- `staged/README.md:38` says proposal cards use the nine old relations,
  including `in-state`.
- `staged/README.md:100` says `depends-on` is not one of the nine closed
  relations.
- `evals/README.md:23`, `evals/README.md:193`, and `evals/README.md:287`
  still describe the old nine-relation contract.
- `skills/business-ontology/SKILL.md:138` maps templates to `concept, module,
  production system...` even though the current package templates are v2.
- `skills/business-ontology/SKILL.md:254-259` still defines common distinctions
  with v1 `Module` and `Metric-as-concept` language.
- `skills/grill-gaps/SKILL.md:16`, `45`, `97`, and `101` use `concept` examples
  where v2 should say `term`, `artifact`, `metric`, or `deprecated v1 concept`.
- `skills/propose-change/SKILL.md:26` says the agent may mine a new `concept`
  or `module`.
- `skills/promote-digest/SKILL.md:103` shows a new card `cn-warm-lead`
  as `(concept, status: candidate)`.
- `viewer/README.md:35` lists `concept`, `module`, `interface` as sample
  current types.
- `viewer/index.html:120-127` fallback data uses `type: concept` and
  `links.in-state`.
- `viewer/index.html:135` and `viewer/index.html:140` include only v1 type
  labels/accents for `concept` and `module`; v2 types are incomplete.
- `viewer/index.html:355` has a module-only flow diagram branch. Under v2,
  the current business card type is `business`; `module` is deprecated.
- `viewer/sample-clubfirst.json` is a viewer sample still written in v1
  language.

Allowed legacy mentions:

- `references/templates.md` may keep deprecated `type: concept` and
  `type: module` blocks only because they are explicitly marked
  "Deprecated v1 alias" and used for migration diagnostics.
- `docs/specs/2026-07-02-data-model-v2.md` may mention `module`, `concept`, and
  `in-state` in migration tables and historical rationale.
- `scripts/migrate_taxonomy_v2.py`, migration tests, and invalid fixtures may
  keep v1 examples.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Viewer tests | `python3 -m unittest tests.test_viewer_bundle` | exit 0 |
| Skill/docs grep audit | see Step 4 | only allowed legacy mentions remain |
| Layout validation | `python3 -m unittest tests.test_repo_layout tests.test_agent_skill_registry` | exit 0 |
| Full unit suite | `python3 -m unittest discover tests` | exit 0 |
| Fixture evals | `python3 scripts/run_evals.py --fixture-only` | 0 failed |
| Package self-test | `python3 scripts/package_self_test.py --suite-timeout 180` | exit 0 |
| Whitespace | `git diff --check` | no output |

## Scope

**In scope**:

- `specs/BUSINESS-ONTOLOGY-RESIDENT.md`
- `staged/README.md`
- `evals/README.md`
- `skills/business-ontology/SKILL.md`
- `skills/grill-gaps/SKILL.md`
- `skills/propose-change/SKILL.md`
- `skills/promote-digest/SKILL.md`
- other `skills/*/SKILL.md` files only when grep finds stale current-language
  examples.
- `references/model-pack.md`
- `references/pressure-tests.md`
- `references/registry-spec.md` only if stale language remains outside
  migration/deprecated sections.
- `viewer/README.md`
- `viewer/index.html`
- `viewer/sample-clubfirst.json`
- `tests/test_viewer_bundle.py`
- `scripts/build_viewer_bundle.py` only if viewer generation still treats
  deprecated types as current.

**Out of scope**:

- Changing core taxonomy, relation names, or validation behavior.
- Deleting migration/deprecated reference sections.
- Redesigning viewer UI beyond the minimum needed for v2 examples to render.
- Migrating every historical eval fixture that intentionally represents older
  behavior; only docs and current examples must change.
- Editing local user skills under `~/.codex/skills`; this plan only changes the
  repository package.

## Git workflow

- Stay on the operator-provided branch unless told otherwise:
  `codex/plan-017-data-model-v2-hard-gate`.
- Do not commit, push, or open a PR unless the operator asks.

## Method decision

**Context**: Business Ontology's trust chain is:

```text
source event -> proposal -> human review -> accepted model
```

Data model v2 supports this chain by making first-class distinctions visible:
`business`, `production-system`, `role`, `artifact`, `tool`, `metric`, `state`,
`process`, `interface`, `decision`, and `term`. Falling back to `concept` hides
which kind of business reality is being proposed.

**Decision**: rewrite current instructional language to v2 terms. Keep old
terms only where the text is explicitly about migration, deprecated aliases, or
historical v1 examples.

**Product consequence**: after release `0.10.0`, a new operator should not see
`concept/module/in-state` in normal examples and copy them into a live model.

## Steps

### Step 1: Update first-read product spec

Edit `specs/BUSINESS-ONTOLOGY-RESIDENT.md`.

Replace the old locked relation list with the v2 closed ten:

```text
produces, consumes, supplies-to, part-of, owns, measured-by, source-of-truth,
lifecycle, governed-by, influences
```

Add one sentence that `module`, `concept`, and `in-state` are migration
diagnostics only and are rejected by package `0.10.0+` strict validation.

Check nearby acceptance language at `M2` and update "closed relation list" text
if it implies nine relations.

**Verify**:

```bash
rg -n "nine|in-state|concept|module" specs/BUSINESS-ONTOLOGY-RESIDENT.md
```

Expected: no `nine` or `in-state`; `module` may remain only in ordinary
deployment wording such as `module_id` or "business module", not as `type:
module`.

### Step 2: Update staged and eval docs

Edit:

- `staged/README.md`
- `evals/README.md`

Replace:

- "nine closed relations" with "ten closed relations";
- old relation list with the v2 ten;
- "first concept cards" with "first v2 candidate cards" or a more specific
  term such as artifact/metric/term;
- current examples that say `concept` when they mean `artifact`, `metric`, or
  `term`.

Do not rewrite historical fixture paths under `evals/fixtures/**` unless tests
fail and the fixture is not intentionally legacy.

**Verify**:

```bash
rg -n "nine relations|nine closed|in-state|first concept|concept cards" staged/README.md evals/README.md
```

Expected: no matches, unless the line explicitly says the term is deprecated or
legacy.

### Step 3: Update active skills to v2 authoring language

Edit active skills with stale current examples:

- `skills/business-ontology/SKILL.md`
- `skills/grill-gaps/SKILL.md`
- `skills/propose-change/SKILL.md`
- `skills/promote-digest/SKILL.md`

Required replacements:

- "concept/module" as current authoring types -> the v2 closed set or the
  specific type that fits.
- "metric concept" -> `metric card`.
- "new concept" for structural data -> `term`, `artifact`, `metric`, or
  "v2 candidate card" depending on context.
- "module" as a card type -> `business`; keep "business module" only when it
  means the deployment boundary, not `type: module`.
- "Metric-as-concept" -> split into `metric card` and `source-of-truth binding`.

Do not remove method rules: mine-first, one question, propose/human commit,
as-is vs as-should, and no sycophancy.

**Verify**:

```bash
rg -n "type: concept|type: module|metric concept|Metric-as-concept|nine closed|in-state" skills
```

Expected: no matches in current authoring instructions. Matches are allowed
only if a line explicitly says deprecated/migration.

### Step 4: Run a repository stale-language audit with an allowlist

Run:

```bash
rg -n "type:\\s*(concept|module)|\"type\"\\s*:\\s*\"(concept|module)\"|in-state|nine relations|nine closed|concept cards|metric concept" \
  specs staged evals skills references viewer README.md BOOTSTRAP.md agent-os \
  --glob '!plans/**'
```

Classify every remaining match:

- **Fix now**: current docs, skills, viewer fallback/sample, eval docs, first-read
  package instructions.
- **Allowed**: migration/deprecated sections, migration scripts/tests, invalid
  fixtures, historical changelog text, old fixture directories clearly used as
  legacy inputs.

If a match is allowed, make sure the surrounding text says why it is allowed.

**Verify**:

Re-run the command above. Expected: only allowed matches remain, and each
allowed match is visibly marked deprecated, migration, fixture, or historical.

### Step 5: Update viewer fallback and sample data to v2

Edit `viewer/index.html` fallback data.

Replace the fallback model so it uses current v2 types:

- `qualified-lead`: `type: "artifact"`, `attrs.kind: "product"`,
  `links.lifecycle` instead of `links.in-state`.
- `lead-quality`: add a `metric` card if the fallback references it.
- `crm`: add a `tool` card if the fallback references it.
- participants: use `role` cards for `role-attraction-supplier` and
  `role-sales-customer`.
- `lead-lifecycle`: `type: "state"` with `attrs.entity`, `attrs.states`,
  `attrs.entry`, `attrs.terminal`, and `attrs.transitions`.
- decision fallback: include `attrs.norm-kind` plus the existing kinetic fields
  if the fallback shows technical details.

Update viewer type labels and accents so v2 types render deliberately:

```text
business, production-system, role, artifact, tool, metric, state, process,
interface, decision, term
```

Update logic that special-cases `module`:

- use `business` for v2 flow diagrams;
- if legacy `module` is still supported for old static demo files, mark it as
  legacy and do not make it the default.

Edit `viewer/sample-clubfirst.json` or mark it as legacy. Preferred fix:
migrate it to v2 if it is still presented as a current sample. If full migration
is too large, rename or document it as a legacy sample and make the current
fallback/sample v2-clean.

**Verify**:

```bash
rg -n '"type":"concept"|"type": "concept"|"type":"module"|"type": "module"|in-state' viewer
python3 -m unittest tests.test_viewer_bundle
```

Expected: no stale matches in current viewer fallback/sample, unless explicitly
legacy; viewer tests pass.

### Step 6: Tighten viewer bundle tests against v2-only examples

Edit `tests/test_viewer_bundle.py`.

Add assertions against the generated example bundle:

- no card type is in `links_validate.DEPRECATED_TYPE_ALIASES`;
- no edge or card link uses a relation in `links_validate.DEPRECATED_LINK_ALIASES`;
- the known `qualified-lead` card is `artifact`, not `concept`;
- its lifecycle relation is `lifecycle`, not `in-state`.

If `scripts/build_viewer_bundle.py` imports broad `CARD_TYPES`, decide whether
that is still correct:

- For a strict v2 viewer build, use `AUTHORING_CARD_TYPES`.
- If compatibility display is still desired for old model repositories, keep
  broad parsing but add a visible `legacy` flag or test only the current example.

Do not silently drop legacy cards in a way that makes an old model look clean.

**Verify**:

```bash
python3 -m unittest tests.test_viewer_bundle
```

Expected: exit 0.

### Step 7: Run final verification

Run:

```bash
python3 -m unittest tests.test_viewer_bundle tests.test_repo_layout tests.test_agent_skill_registry
python3 -m unittest discover tests
python3 scripts/run_evals.py --fixture-only
python3 scripts/package_self_test.py --suite-timeout 180
python3 scripts/links_validate.py .
python3 scripts/links_validate.py . --staged
python3 scripts/links_validate.py . --strict-transitional
python3 scripts/links_validate.py . --staged --strict-transitional
git diff --check
```

Expected:

- all unit tests pass;
- fixture evals report 0 failed;
- all validator runs exit 0;
- `git diff --check` prints nothing.

## Test plan

Add or update tests for:

- viewer bundle generated from `examples/acquisition-ontology` contains no
  deprecated type or relation aliases;
- `qualified-lead` renders as an `artifact`;
- `lifecycle` replaces `in-state` in viewer bundle edges;
- existing repo layout and skill registry tests still pass after skill wording
  changes.

## Done criteria

- [ ] First-read spec has v2 ten-relation contract and no current `in-state`
      authoring instruction.
- [ ] `staged/README.md` and `evals/README.md` describe v2 ten relations.
- [ ] Active skills no longer teach `concept/module/in-state` as current
      authoring language.
- [ ] Viewer fallback/current sample is v2-clean or legacy-marked.
- [ ] Viewer tests assert no deprecated aliases in the current generated bundle.
- [ ] Full verification commands in Step 7 pass.
- [ ] `plans/README.md` row for plan 020 is updated by the executor.

## STOP conditions

Stop and report if:

- A remaining `concept/module/in-state` match is ambiguous and you cannot tell
  whether it is migration history or current instruction.
- Viewer migration requires a full UI redesign rather than data/label fixes.
- Skill wording changes would alter the human review gate or actor-mode policy.
- You discover a source of truth that says the package intentionally still
  supports v1 authoring after `0.10.0`.

## Maintenance notes

Future docs changes should be reviewed with this grep pattern before release:

```bash
rg -n "type:\\s*(concept|module)|in-state|nine relations|nine closed|metric concept" \
  specs staged evals skills references viewer README.md BOOTSTRAP.md agent-os \
  --glob '!plans/**'
```

Matches are not automatically wrong, but every remaining match must be
explicitly historical, deprecated, migration-only, or fixture-only.

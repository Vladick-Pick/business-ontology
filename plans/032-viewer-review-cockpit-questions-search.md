# Plan 032: Viewer becomes a review cockpit for open questions, drift, gaps, and search

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the next
> step. If a STOP condition occurs, stop and report; do not improvise.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 6bd26d7..HEAD -- scripts/build_viewer_bundle.py viewer/index.html viewer/README.md tests/test_viewer_bundle.py skills/show-model/SKILL.md
> git diff --stat -- scripts/build_viewer_bundle.py viewer/index.html viewer/README.md tests/test_viewer_bundle.py skills/show-model/SKILL.md
> ```

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: plans 028-031
- **Category**: product UX / methodology / tests
- **Planned at**: commit `6bd26d7`, 2026-07-08

## Why this matters

The viewer should help the business analyst decide what to check next. Today
the overview prioritizes only non-accepted statuses and overdue audits. It can
say "Открытых вопросов нет" while card sections contain open questions. Search
also ignores attrs, links, owner, source, SLA, authority, and rule fields. The
result is a readable catalog, not a working review cockpit.

## Current state

- `_read_open_questions()` reads only bullet lines from
  `08-drift-and-open-questions.md` at `scripts/build_viewer_bundle.py:407-416`.
- Card-local sections can contain open questions:
  - `examples/business-attraction-v2/decisions/d-autopurchase.md:89-93`
    has `## Drift and open questions`.
  - `examples/business-attraction-v2/interfaces/if-lidgen-attraction.md:80+`
    has `## Open questions`.
- `questionsView()` at `viewer/index.html:471-475` displays only
  `DATA.openQuestions`.
- `overview()` at `viewer/index.html:327-352` prioritizes only non-accepted
  cards and stale audits.
- `searchView()` at `viewer/index.html:477-480` searches only id, title, and
  body sections.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused tests | `python3 -m unittest tests.test_viewer_bundle tests.test_publish_viewer` | all tests pass |
| Full tests | `python3 -m unittest discover tests` | all tests pass |
| Evals | `python3 scripts/run_evals.py --fixture-only` | all fixtures pass |
| Self-test | `python3 scripts/package_self_test.py --suite-timeout 180` | all tests and evals pass |
| Whitespace | `git diff --check` | no output, exit 0 |

## Suggested executor toolkit

- A backend/generator subagent can build `reviewItems` and `searchText`.
- A frontend subagent can render `#overview`, `#questions`, and search.
- A BA reviewer subagent should review the final cockpit with this prompt:
  "Can you decide what to check next without opening technical JSON?"

## Scope

**In scope**

- `scripts/build_viewer_bundle.py`
- `viewer/index.html`
- `viewer/README.md`
- `skills/show-model/SKILL.md`
- `tests/test_viewer_bundle.py`
- `tests/test_publish_viewer.py` only if publish metadata changes

**Out of scope**

- Editing accepted model truth.
- Implementing human request resolution in the viewer.
- Adding write actions or approval controls.
- Raw source or transcript display.

## Git workflow

- Branch: `codex/032-viewer-review-cockpit-questions-search`
- Do not push or open a PR unless the operator asks.

## Steps

### Step 1: Generate review items from global and card-local questions

In `build_viewer_bundle.py`, add a bounded `reviewItems` list.

Input sources:

- bullets from `08-drift-and-open-questions.md`;
- card sections whose heading matches `open questions`, `drift`, `drift and open questions`, or Russian equivalents;
- health gaps from plan 029: unknown/unresolved sources, failed source readiness,
  open human request count, stale audit, non-accepted statuses.

Each item should include:

```json
{
  "kind": "open-question | drift | stale-audit | source-gap | human-request | status-risk",
  "severity": "high | medium | low",
  "cardId": "optional-card-id",
  "sourceId": "optional-source-id",
  "owner": "owner-or-unknown",
  "text": "short safe text",
  "action": "what to inspect next"
}
```

Keep texts bounded. Do not include raw source payloads.

**Verify**:

Add tests that v2 fixture produces review items from
`d-autopurchase` and/or `if-lidgen-attraction` card sections.

### Step 2: Render review cockpit on overview

Update `overview()`:

- rename or restructure "Что проверить в первую очередь" into a review queue;
- include review items grouped by severity/kind;
- link to affected cards/sources;
- show why the item matters: source gap, stale audit, open question, human
  request count, failed readiness, non-accepted status.

Do not make the overview a wall of every card. Show top bounded items first and
link to `#questions` for the full list.

**Verify**:

Static HTML tests assert labels such as `Очередь ревью`, `source-gap`, or
Russian equivalents.

### Step 3: Replace questions view with structured drift/question ledger

Update `questionsView()`:

- use `DATA.reviewItems` when available;
- separate open questions, drift/gaps, source gaps, stale audits, and human
  requests;
- show card/source links and owner;
- if there are no items, say no review items were found, not only "open
  questions".

**Verify**:

Focused tests pass. Browser smoke should show card-local open questions from
the v2 fixture.

### Step 4: Expand search index

Add a safe per-card search text in the bundle or compute it in the browser.
Search must include:

- id;
- title;
- body sections;
- `attrs` values;
- `links`;
- owner;
- source;
- volatility;
- aliases;
- evidence ids;
- decision authority/measurement fields;
- SLA/rule fields.

Do not index raw source payloads. The bundle already excludes them.

**Verify**:

Add a test or browser smoke that searching for `autopurchase`, `SLA таймер`,
`r-ki`, and `srcevt-btx-0630` finds relevant cards.

### Step 5: Update show-model skill and docs

Update `skills/show-model/SKILL.md` and `viewer/README.md`:

- viewer is a review cockpit, not only a card catalog;
- agent should link `#overview` after accepted changes when there are review
  items;
- agent should link specific cards for individual verification;
- agent must not say "no open questions" unless `reviewItems` is empty.

**Verify**:

Focused tests assert the new wording.

## Required review loop

1. Run `code-reviewer`: check false "no questions", bounded text, escaping, and
   search over safe fields only.
2. Run `improve-codebase-architecture`: check whether `reviewItems` belongs in
   the bundle and does not become a second model-health implementation with
   conflicting semantics.
3. Run `ponytail:ponytail-review`: cut duplicate queues or noisy categories;
   keep the smallest cockpit that answers "what should I inspect next?"
4. Fix findings and re-run all three reviews.

## Test plan

- Bundle tests for `reviewItems`.
- Static HTML tests for overview/questions/search fields.
- Browser smoke for `#overview`, `#questions`, and search queries.
- Existing full package tests and evals.

## Done criteria

- [ ] Card-local open questions appear in `reviewItems`.
- [ ] Overview shows a bounded review queue, not only status/audit rows.
- [ ] Questions page shows structured review items with card/source/owner links.
- [ ] Search covers safe attrs, links, owner/source, aliases, evidence, SLA, and
  decision/metric fields.
- [ ] Viewer does not display raw source payloads, secrets, or PII.
- [ ] `python3 -m unittest tests.test_viewer_bundle tests.test_publish_viewer` passes.
- [ ] `python3 -m unittest discover tests` passes.
- [ ] `python3 scripts/run_evals.py --fixture-only` passes.
- [ ] `python3 scripts/package_self_test.py --suite-timeout 180` passes.
- [ ] `git diff --check` passes.
- [ ] `plans/README.md` row for plan 032 is updated.

## STOP conditions

Stop and report if:

- The design starts requiring accepted-model writes from the viewer.
- Review items require raw source/transcript payloads.
- The search index would include secrets, private messages, or PII.
- `reviewItems` semantics conflict with `runtime/context_projection.py`
  `modelHealth`; report the conflict and ask whether to align with that
  projection first.

## Maintenance notes

The cockpit should remain read-only. Future write actions belong to staged
review packages and human-owned promotion, not to the viewer.

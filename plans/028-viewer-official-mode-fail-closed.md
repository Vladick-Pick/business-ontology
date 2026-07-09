# Plan 028: Viewer official mode fails closed instead of showing demo

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the next
> step. If a STOP condition occurs, stop and report; do not improvise.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 6bd26d7..HEAD -- viewer/index.html viewer/README.md skills/show-model/SKILL.md tests/test_viewer_bundle.py
> git diff --stat -- viewer/index.html viewer/README.md skills/show-model/SKILL.md tests/test_viewer_bundle.py
> ```
>
> If `viewer/index.html` does not contain `loadOfficialBundle`, this plan was
> written against a newer uncommitted viewer hardening batch. STOP and ask the
> operator whether to apply/merge `codex/viewer-v2-shape-currentness` first.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: current viewer-v2-shape-currentness patch
- **Category**: bug / product trust / tests
- **Planned at**: commit `6bd26d7`, 2026-07-08

## Why this matters

The viewer is a review surface for accepted company truth. If official loading
fails and the browser silently shows sample data, a business analyst can review
the wrong model while the page still looks healthy. Demo data is useful for
development, but it must never be the fallback path for an official installed
viewer.

## Current state

- `viewer/index.html` loads the official report and bundle in
  `loadOfficialBundle()` at lines 537-550.
- `viewer/index.html` then catches any official load failure and tries
  `sample-clubfirst.json` at line 552:

```js
loadOfficialBundle()
  .catch(()=>tryFetch("./sample-clubfirst.json").then(d=>{...;return d;}))
```

- `viewer/README.md` says a current model view requires
  `VIEWER_PUBLISH_REPORT.json` with `status: "published"` at lines 28-31, but
  the runtime behavior still has a non-official fallback.
- `skills/show-model/SKILL.md` requires the publish report before saying the
  model was shown at lines 99-108.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused viewer tests | `python3 -m unittest tests.test_viewer_bundle tests.test_publish_viewer` | all tests pass |
| Full tests | `python3 -m unittest discover tests` | all tests pass |
| Evals | `python3 scripts/run_evals.py --fixture-only` | all fixtures pass |
| Self-test | `python3 scripts/package_self_test.py --suite-timeout 180` | all tests and evals pass |
| Whitespace | `git diff --check` | no output, exit 0 |

## Scope

**In scope**

- `viewer/index.html`
- `viewer/README.md`
- `skills/show-model/SKILL.md`
- `tests/test_viewer_bundle.py`
- optional: `tests/test_publish_viewer.py` if a publish fixture helps the
  official-mode test

**Out of scope**

- Any accepted model card content.
- `scripts/build_viewer_bundle.py` projection fields. That is plan 029.
- Replacing dagre or changing diagram layout.
- Adding an app server. Viewer remains static HTML.

## Git workflow

- Branch: `codex/028-viewer-official-mode-fail-closed`
- Do not push or open a PR unless the operator asks.
- Keep commits scoped to official loading behavior and tests.

## Steps

### Step 1: Split official load failure from explicit demo mode

Change `viewer/index.html` so official mode does not fall back to demo.

Target behavior:

- Default URL, including `#overview` and `#card/<id>`:
  - load `VIEWER_PUBLISH_REPORT.json`;
  - load `ontology.json`;
  - verify report status, validation status, package version, package commit,
    model revision, and bundle hash when Web Crypto is available;
  - if any check fails, render a blocking error screen that names the failed
    check and the expected remediation.
- Explicit demo mode:
  - use a deliberate URL mode such as `?demo=1` or `#demo`;
  - only then load `sample-clubfirst.json` or `FALLBACK`;
  - show a visible banner that this is demo data.

Implementation note: keep the one-file vanilla JS style. A small helper such as
`showFatalLoadError(error)` is enough. Do not introduce a framework.

**Verify**:

```bash
python3 -m unittest tests.test_viewer_bundle
```

Expected: tests pass, including new assertions from Step 2.

### Step 2: Add regression tests for fail-closed official mode

Extend `tests/test_viewer_bundle.py`.

Test cases:

- `viewer/index.html` does not contain the old pattern
  `loadOfficialBundle().catch(()=>tryFetch("./sample-clubfirst.json"`.
- The HTML contains a blocking official failure message string, for example
  `Официальный viewer не загрузился`.
- The HTML contains an explicit demo-mode check, for example `demo=1` or
  `#demo`.
- The demo banner says the data is not the current model.

**Verify**:

```bash
python3 -m unittest tests.test_viewer_bundle tests.test_publish_viewer
```

Expected: all tests pass.

### Step 3: Update docs and agent instruction

Update `viewer/README.md` and `skills/show-model/SKILL.md`:

- default official viewer must fail closed;
- demo mode is explicitly opt-in;
- an agent must not share a viewer link if the page is showing demo data;
- fallback in chat must name the failed official publish/load reason.

**Verify**:

```bash
python3 -m unittest tests.test_viewer_bundle
```

Expected: tests pass and assert the new wording.

### Step 4: Run browser smoke manually

Use the existing smoke style from the advisor run. Publish the v2 fixture, open
Chrome through Playwright or the local browser, and verify:

- official happy path renders `#overview` and `#card/biz-attraction`;
- if `VIEWER_PUBLISH_REPORT.json` is missing, the page shows the blocking
  official-load error, not demo;
- `?demo=1` or `#demo` still shows demo with a visible demo banner.

If Playwright browser binaries are unavailable, use `/Applications/Google Chrome.app`
as `executablePath` on this machine. Do not add a Playwright dependency to the
package unless the operator explicitly asks for CI browser tests.

**Verify**:

Record the smoke command and result in the final implementation report. No
screenshot file is required unless the reviewer asks.

## Required review loop

After implementation and verification:

1. Run `code-reviewer` against the diff: focus on false official success,
   swallowed errors, and missing tests.
2. Run `improve-codebase-architecture`: check that official/demo mode stays a
   simple boundary, not a new framework or app server.
3. Run `ponytail:ponytail-review`: remove extra abstractions while preserving
   fail-closed behavior and tests.
4. Fix every blocking finding.
5. Re-run all three reviews.

## Test plan

- Static regression tests in `tests/test_viewer_bundle.py`.
- Existing publish tests in `tests/test_publish_viewer.py`.
- Manual browser smoke for official success, official failure, and explicit demo.

## Done criteria

- [ ] Official load failure cannot show sample or built-in demo by default.
- [ ] Demo is reachable only through an explicit demo mode.
- [ ] The error screen includes the concrete failed check or missing file.
- [ ] `python3 -m unittest tests.test_viewer_bundle tests.test_publish_viewer` passes.
- [ ] `python3 -m unittest discover tests` passes.
- [ ] `python3 scripts/run_evals.py --fixture-only` passes.
- [ ] `python3 scripts/package_self_test.py --suite-timeout 180` passes.
- [ ] `git diff --check` passes.
- [ ] `plans/README.md` row for plan 028 is updated by the executor, unless a
  reviewer owns the index update.

## STOP conditions

Stop and report if:

- `viewer/index.html` no longer has `loadOfficialBundle`.
- The fix requires a server-side viewer runtime.
- The browser cannot display an official-load error without new dependencies.
- Any source, transcript, secret, or raw private payload would need to enter the
  viewer bundle.

## Maintenance notes

Reviewers should scrutinize the exact official/demo branch. The product rule is:
demo may help development, but installed viewer review must fail closed.

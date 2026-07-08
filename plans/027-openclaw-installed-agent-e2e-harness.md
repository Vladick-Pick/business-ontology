# Plan 027: OpenClaw installed-agent E2E harness

> **Executor instructions**: Follow this plan step by step. Fixture E2E must run
> without secrets. Live E2E may interact with the installed OpenClaw agent only
> after fixture E2E passes and owner explicitly provides/approves access for
> that run. If a STOP condition occurs, stop and report.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 90f767f..HEAD -- \
>   adapters/openclaw agent-os skills scripts runtime schemas templates tests evals
> git diff --stat -- \
>   adapters/openclaw agent-os skills scripts runtime schemas templates tests evals
> ```

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: HIGH (installed product readiness)
- **Depends on**: `plans/021-installed-product-state-and-update-proof.md`,
  `plans/022-workspace-state-and-model-language-onboarding.md`,
  `plans/023-source-instance-registry-and-live-proof-ledger.md`,
  `plans/024-accepted-model-write-gate-enforcement.md`,
  `plans/025-model-repo-support-contract-and-validator-pin.md`,
  `plans/026-official-viewer-publish-contract.md`
- **Category**: end-to-end installed-agent proof
- **Planned at**: commit `90f767f`, 2026-07-08

## Product meaning

This plan answers the owner's core question:

```text
When I install the business analyst in OpenClaw, will it actually behave like
the product we designed?
```

The answer must be proven by an installed-agent E2E harness, not by isolated
unit tests or a chat demo.

## Best-practice anchor

- GBrain install/eval pattern: create a real working structure, then verify the
  agent can use it.
- OpenClaw pattern: installed agent behavior spans host channel, workspace,
  tools, and visible surface.
- Hermes pattern: after update/restart, the agent must recover memory/state and
  continue operating with durable skills.

## Fixture E2E scenario

The default E2E uses no secrets and no live network. It starts from a disposable
OpenClaw-like workspace and simulates the host messages/tools.

Required path:

1. Start from old/minimal package install.
2. Apply package update through the official updater.
3. Verify install/update proof.
4. Run onboarding.
5. Ask and record company model language.
6. Register Telegram MTProto source instance in fixture mode.
7. Register meeting recorder source instance in fixture mode.
8. Produce fixture live proofs for both source paths.
9. Ingest a fixture source event.
10. Generate model-change package.
11. Attempt direct accepted write and prove it is denied.
12. Prepare review package/human request.
13. Publish official viewer.
14. Produce final E2E report.

## Live E2E scenario

Live mode may interact with the installed OpenClaw agent that is available to
the operator. It must be explicit:

```bash
BUSINESS_ONTOLOGY_E2E_LIVE=1 python3 scripts/run_installed_agent_e2e.py --live
```

Live mode must:

- never print secrets;
- use env/secret manager refs;
- write a redacted proof report;
- avoid writing accepted model truth;
- use a disposable or owner-approved test source/message when possible;
- mark any skipped live connector as `blocked`, not `passed`.

## Architecture decision

**Context**: Unit tests prove modules. Evals prove agent response patterns.
Installed-agent E2E proves the product boundary: package, workspace, source
state, review gate, viewer, and host behavior.

**Options**:

1. Keep only unit tests and evals.
   Rejected: they do not catch installed-state drift.
2. Run live tests only.
   Rejected: expensive, flaky, and credential-dependent.
3. Add fixture E2E as required gate and live E2E as explicit proof mode.

**Decision**: implement option 3.

## Scope

**In scope**:

- new `scripts/run_installed_agent_e2e.py` or equivalent
- fixture OpenClaw workspace under `fixtures/`
- fake host adapter for direct messages/group mentions/tool calls
- E2E report schema
- evals for installed-agent behavior
- docs in `adapters/openclaw/`
- tests under `tests/`

**Out of scope**:

- Production OpenClaw deployment automation.
- Real Telegram/Skribby credentials in CI.
- Real accepted model writes.
- GBrain sync implementation.

## Implementation steps

### Step 1: Define E2E report contract

Report must include:

- package update proof path;
- workspace state path;
- selected model language;
- source instances and live proofs;
- human requests opened/answered;
- model-change package path;
- accepted-write gate result;
- viewer publish report;
- final status: `passed|failed|blocked`.

### Step 2: Build fixture host adapter

Add a test harness that can simulate:

- direct agent chat message;
- group message with mention;
- owner approval/denial;
- source setup answers;
- meeting link message;
- transcript webhook packet.

The harness should call package scripts/skills through existing interfaces
where possible. Do not invent a second product runtime.

### Step 3: Add fixture E2E command

Command:

```bash
python3 scripts/run_installed_agent_e2e.py --fixture-only
```

It must run without network or secrets.

### Step 4: Add live E2E command

Command:

```bash
BUSINESS_ONTOLOGY_E2E_LIVE=1 python3 scripts/run_installed_agent_e2e.py --live
```

Live mode may use SSH/OpenClaw access if the operator has configured it for the
session. It must produce a redacted proof report and stop before any accepted
model write.

### Step 5: Add CI-safe tests

CI runs fixture-only. Live E2E is manual/deployment proof.

## Required review loop

After implementation:

1. Run normal code review using `code-reviewer`.
2. Run architecture review using `improve-codebase-architecture`.
3. Run minimality review using `ponytail:ponytail-review`.
4. Fix all Critical/Warning findings and Ponytail cuts that do not weaken E2E
   coverage, source separation, write gate, or redaction.
5. Re-run all three reviews.
6. Mark the plan DONE only when fixture E2E passes and live E2E has either
   passed or produced an explicit `blocked` report with the missing host input.

## Verification

Minimum commands:

```bash
python3 scripts/run_installed_agent_e2e.py --fixture-only
python3 -m unittest discover tests
python3 scripts/run_evals.py --fixture-only
python3 scripts/package_self_test.py --suite-timeout 180
git diff --check
```

Manual/live proof command:

```bash
BUSINESS_ONTOLOGY_E2E_LIVE=1 python3 scripts/run_installed_agent_e2e.py --live
```

## Definition of Done

- Fixture installed-agent E2E passes without secrets.
- E2E covers update, onboarding, model language, source instances, live proofs,
  proposal package, accepted-write denial, and viewer publish.
- Live E2E command exists and writes redacted proof reports.
- Agent interaction with the available OpenClaw agent is tested or explicitly
  blocked with the exact missing access/capability.
- E2E report is machine-readable and human-readable.
- Review loop completed twice with no blocking findings.

## STOP conditions

Stop and report if:

- fixture E2E needs real secrets or network;
- live E2E would write accepted truth;
- transcript or Telegram raw content is written to model repo;
- fake harness bypasses the same scripts/skills used in the product path;
- live OpenClaw agent cannot be accessed and no owner-approved access path is
  available.

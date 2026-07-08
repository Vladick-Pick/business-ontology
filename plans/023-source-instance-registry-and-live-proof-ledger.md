# Plan 023: Source instance registry and live proof ledger

> **Executor instructions**: Follow this plan step by step. Telegram background
> history intake and meeting recording intake are separate source paths. Do not
> connect Zoom/Skribby/meeting recording to MTProto. If a STOP condition occurs,
> stop and report.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 90f767f..HEAD -- \
>   specs/SOURCE-SPEC.md agent-os/SOURCE_INTAKE.md \
>   skills/connect-source/SKILL.md skills/daily-ingest/SKILL.md \
>   skills/meeting-recorder/SKILL.md skills/meeting-transcript-ingest/SKILL.md \
>   scripts/tg_run_daily_ingest.py scripts/tg_collect_daily.py \
>   scripts/run_meeting_recording_live_proof.py runtime templates/workspace \
>   schemas tests
> git diff --stat -- \
>   specs/SOURCE-SPEC.md agent-os/SOURCE_INTAKE.md \
>   skills/connect-source/SKILL.md skills/daily-ingest/SKILL.md \
>   skills/meeting-recorder/SKILL.md skills/meeting-transcript-ingest/SKILL.md \
>   scripts/tg_run_daily_ingest.py scripts/tg_collect_daily.py \
>   scripts/run_meeting_recording_live_proof.py runtime templates/workspace \
>   schemas tests
> ```

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: HIGH (live source readiness and source separation)
- **Depends on**: `plans/022-workspace-state-and-model-language-onboarding.md`
- **Category**: source intake + operational state + live proof
- **Planned at**: commit `90f767f`, 2026-07-08
- **Implementation**: DONE locally on `codex/plans-021-027-installed-agent-readiness`

## Product meaning

The agent must distinguish:

- "a script exists in the package";
- "a source is configured for this installed agent";
- "the source has passed a live proof";
- "the source is scheduled and producing packets."

Without this registry, the owner cannot know whether daily Telegram scan,
meeting recording, or future connectors are actually attached to the resident
business analyst.

## Best-practice anchor

- OpenClaw separates host channels and runtime state; source readiness should be
  explicit per channel/source, not guessed from files.
- GBrain install patterns treat connected services as configured capabilities,
  not as one-off scripts.
- GBrain evals show that source/memory behavior should be reproducible and
  tied to evidence, not chat memory.

## Current problem

Telegram MTProto scripts exist, and meeting recording scripts exist, but the
workspace lacks a first-class source instance registry. That allowed an old
MTProto cron from another agent identity to be mistaken for the business
analyst's source connection.

Meeting recording is also a separate intake path:

- it starts from a host-delivered meeting link addressed to the agent;
- it orders a recorder bot;
- it receives a transcript webhook;
- it normalizes the transcript into source events.

It does not use MTProto, daily Telegram scan, or Telegram history collection.

## Architecture decision

**Context**: Source material is untrusted data. Source connectors are runtime
capabilities. Accepted model truth is downstream and human-gated.

**Options**:

1. Keep source setup in prose files and script flags.
   Rejected: cannot audit installed readiness or ownership.
2. Put source readiness into accepted model.
   Rejected: readiness is runtime state, not business truth.
3. Add a workspace source registry and live-proof ledger.

**Decision**: implement option 3. Source instances and live proofs live in the
workspace/operational store. Model-change packages refer to source events, not
raw connectors.

## Source instance contract

Add a registry record with at least:

```json
{
  "source_instance_id": "tg-main-history",
  "owner_agent": "business-ontology-resident",
  "kind": "telegram-mtproto-history|meeting-recorder|google-workspace|dashboard",
  "runtime_adapter": "scripts/tg_run_daily_ingest.py",
  "config_ref": "workspace/config/source-instances/tg-main-history.json",
  "cursor_ref": "workspace/source-cursors/tg-main-history.json",
  "output_ref": "workspace/source-events/tg-main-history/",
  "scheduler_ref": "cron:<id>|openclaw:<id>|manual",
  "status": "configured|source-connected|live-proven|scheduled|failed",
  "last_live_proof_id": "proof-...",
  "created_at": "<iso8601>",
  "updated_at": "<iso8601>"
}
```

Add a live-proof record with at least:

```json
{
  "live_proof_id": "proof-...",
  "source_instance_id": "tg-main-history",
  "capability": "telegram-history-read|meeting-recording-transcript",
  "mode": "fixture|live",
  "input_ref": "<redacted-ref>",
  "output_artifacts": ["<path>"],
  "evidence_hash": "<hash>",
  "status": "passed|failed|source-connected|setup-only",
  "created_at": "<iso8601>",
  "updated_at": "<iso8601>"
}
```

## Scope

**In scope**:

- `schemas/source-instance.schema.json`
- `schemas/live-proof.schema.json`
- `runtime/operational_store.py` or workspace JSON helpers, following existing
  store patterns.
- `templates/workspace/**`
- `scripts/tg_run_daily_ingest.py`
- `scripts/run_meeting_recording_live_proof.py`
- `skills/connect-source/SKILL.md`
- `skills/daily-ingest/SKILL.md`
- `skills/meeting-recorder/SKILL.md`
- `skills/meeting-transcript-ingest/SKILL.md`
- `specs/SOURCE-SPEC.md`
- focused tests under `tests/`

**Out of scope**:

- Live credential collection in chat.
- Raw Telegram messages or raw transcript storage in model repo.
- Production scheduler implementation beyond recording scheduler identity.
- GBrain sync.

## Implementation steps

### Step 1: Add registry and ledger contracts

Add schemas and helpers for source instances and live proofs. Keep records
redacted: refs and hashes, not raw private content.

### Step 2: Connect Telegram MTProto daily ingest

Update Telegram daily ingest wrapper so it:

- requires a `source_instance_id`;
- reads config from the registry or writes a pending registry entry;
- writes cursor/output paths under that source instance;
- writes a live-proof record when run in proof mode;
- refuses to claim readiness if the registry owner does not match the installed
  agent identity.

### Step 3: Connect meeting recording live proof

Update meeting live proof so it writes a separate `meeting-recorder` source
instance and proof. Do not mention MTProto in this path except to say it is not
used.

### Step 4: Update source setup skill behavior

`connect-source` must ask for concrete source setup one source at a time:

- Telegram history scan: MTProto user session provisioning for approved chats.
- Meeting recording: recorder webhook/API setup for host-delivered meeting
  links.

Each setup question becomes a human request if unanswered.

### Step 5: Add readiness projection

Expose source readiness in model health/viewer/digest:

- configured sources;
- live-proven sources;
- failed/blocked sources;
- last proof time;
- next scheduled run if known.

## Required review loop

After implementation:

1. Run normal code review using `code-reviewer`.
2. Run architecture review using `improve-codebase-architecture`.
3. Run minimality review using `ponytail:ponytail-review`.
4. Fix all Critical/Warning findings and Ponytail cuts that do not weaken
   source separation, proof, redaction, or tests.
5. Re-run all three reviews.
6. Move to the next plan only when the second pass has no blocking findings.

## Verification

Minimum commands:

```bash
python3 -m unittest tests.test_source_registry tests.test_source_registry_schema \
  tests.test_tg_mtproto_export tests.test_meeting_recording_live_proof \
  tests.test_context_projection tests.test_reference_runtime \
  tests.test_openclaw_self_bootstrap tests.test_schemas_and_parser_docs
python3 -m unittest discover tests
python3 scripts/run_evals.py --fixture-only
python3 scripts/package_self_test.py --suite-timeout 180
git diff --check
```

Add focused tests for:

- Telegram source instance creation and proof record;
- meeting recorder source instance creation and proof record;
- old source instance owned by another agent is not counted as ready;
- Zoom/meeting path does not depend on MTProto config;
- registry stores refs/hashes, not raw source dumps;
- readiness projection shows `configured`, `source-connected`,
  `live-proven`, `scheduled`, and `failed`.

## Definition of Done

- Every source connector has a source instance record.
- Every live proof has a proof record tied to a source instance.
- Telegram MTProto daily history scan is only for Telegram history intake.
- Meeting recording intake is separate and starts from addressed meeting links.
- The installed agent can answer which sources are configured and live-proven.
- Old source setup from another agent identity cannot be mistaken for this
  resident.
- Review loop completed twice with no blocking findings.

## STOP conditions

Stop and report if:

- meeting recording code starts depending on MTProto;
- a source can be marked ready without live proof;
- raw private messages or transcript bodies would be stored in the model repo;
- credentials are requested in chat instead of env/secret manager refs;
- source registry ownership cannot distinguish installed agents.

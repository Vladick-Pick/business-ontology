# Plan 016: Meeting Live Proof And Readiness Gates — real Skribby bot E2E

> **Executor instructions**: Start only after plans 013-015 and their review
> gates are complete. This plan is not done until a real live E2E run is
> recorded. Do not downgrade to a fixture-only proof. Commit in worktree after
> docs/tests; live proof artifacts stay outside the model repository and outside
> git unless redacted fixture copies are intentionally added.
>
> **Drift check (run first)**:
> `rg -n "meeting-recorder|meeting-transcript-ingest|MeetingRecordingRuntime" skills runtime agent-package.yaml`
> must show the implemented runtime and skills.

## Status

- **Priority**: P1
- **Effort**: M-L
- **Risk**: HIGH (deployment, public HTTPS, live provider)
- **Depends on**: 013, 014, 015
- **Category**: deployment + live proof + review gates

## Goal

Prove the product path end to end:

```text
Zoom link sent to agent
-> agent orders recording through runtime
-> real Skribby bot joins meeting
-> Skribby sends finished webhook
-> runtime fetches full transcript
-> packet/source material saved
-> agent ingests meeting transcript
-> source events + model-change packages + digest/review handoff produced
```

## Files

- Create: `adapters/openclaw/MEETING_RECORDING_SERVICE.md`
- Create: `scripts/run_meeting_recording_live_proof.py`
- Modify: `adapters/openclaw/MEETING_TRANSCRIPTS.md`
- Modify: `adapters/openclaw/BOOTSTRAP.md`
- Modify: `adapters/openclaw/SCHEDULING.md`
- Modify: `adapters/openclaw/live-test/README.md`
- Modify: `adapters/openclaw/live-test/PASS_FAIL_GATES.md`
- Modify: `adapters/openclaw/live-test/OPERATOR_CHECKLIST.md`
- Modify: `adapters/openclaw/live-test/OBSERVER_PROTOCOL.md`
- Modify: `templates/workspace/SOURCES.md.tpl`
- Modify: `templates/workspace/SOURCE_CURSORS.md.tpl`
- Modify: `templates/workspace/LIVE_TEST_STATUS.md.tpl`
- Modify: `templates/workspace/AUTHORIZATION_CHECKLIST.md.tpl`
- Modify: `README.md`
- Modify: `agent-package.yaml`
- Modify: `plans/README.md`
- Create: `tests/test_meeting_recording_live_readiness.py`
- Create: `tests/test_meeting_recording_live_proof.py`

## Deployment contract

The service must run as a long-lived process with public HTTPS:

```bash
python3 scripts/run_meeting_recording_service.py \
  --host 127.0.0.1 \
  --port 8765 \
  --workspace /home/agent/.openclaw/workspace
```

Required env:

```text
SKRIBBY_API_KEY
MEETING_RECORDING_DB
MEETING_RECORDING_PUBLIC_BASE_URL
OPENCLAW_MEETING_PROCESS_HOOK_URL
OPENCLAW_HOOKS_TOKEN
```

`MEETING_RECORDING_PUBLIC_BASE_URL` must expose:

```text
POST /recordings
POST /webhooks/skribby
```

The public route may be Caddy, nginx, OpenClaw gateway, or another approved
HTTPS reverse proxy. The product path is still this runtime service, not n8n.

## Live proof script

The operator runs a real meeting test:

1. Start meeting recording service.
2. Confirm `/health` returns OK without secrets.
3. Send a real Zoom link to the agent in direct chat or a group mention.
4. Agent calls `meeting-recorder`.
5. Runtime creates Skribby bot and records `job_id` + `bot_id`.
6. Operator admits bot to Zoom.
7. Say a short test phrase with a business-model signal, for example:

```text
For this test, the acquisition handoff source of truth remains the CRM.
Changing the owner of the handoff decision requires owner review.
```

8. End meeting.
9. Skribby sends finished webhook.
10. Runtime fetches transcript and writes packet.
11. Agent runs `meeting-transcript-ingest`.
12. Verify source event, model-change package, and digest/review handoff.

Use the proof runner, not a hand-written proof report. Start with preflight; it
does not call Skribby and must not be treated as source proof:

```bash
python3 scripts/run_meeting_recording_live_proof.py \
  --preflight \
  --service-url "$MEETING_RECORDING_SERVICE_URL" \
  --public-base-url "$MEETING_RECORDING_PUBLIC_BASE_URL" \
  --db "$MEETING_RECORDING_DB" \
  --workspace "$OPENCLAW_WORKSPACE" \
  --meeting-url "$REAL_ZOOM_URL" \
  --business-id "$TEST_BUSINESS_ID" \
  --source-id "$TEST_SOURCE_ID" \
  --chat-ref "$TEST_CHAT_REF" \
  --requested-by "$TEST_REQUESTED_BY" \
  --packet-only
```

The next command proves the provider-to-packet path only:

```bash
python3 scripts/run_meeting_recording_live_proof.py \
  --service-url "$MEETING_RECORDING_SERVICE_URL" \
  --public-base-url "$MEETING_RECORDING_PUBLIC_BASE_URL" \
  --db "$MEETING_RECORDING_DB" \
  --workspace "$OPENCLAW_WORKSPACE" \
  --meeting-url "$REAL_ZOOM_URL" \
  --business-id "$TEST_BUSINESS_ID" \
  --source-id "$TEST_SOURCE_ID" \
  --chat-ref "$TEST_CHAT_REF" \
  --requested-by "$TEST_REQUESTED_BY" \
  --packet-only
```

After the agent has run `meeting-transcript-ingest`, rerun against the same job
without `--packet-only`:

```bash
python3 scripts/run_meeting_recording_live_proof.py \
  --job-id "$MEETING_RECORDING_JOB_ID" \
  --db "$MEETING_RECORDING_DB" \
  --workspace "$OPENCLAW_WORKSPACE" \
  --source-events-dir "$MEETING_SOURCE_EVENTS_PATH" \
  --model-change-packages-dir "$MEETING_MODEL_CHANGE_PACKAGES_PATH" \
  --digest-or-review-handoff-path "$MEETING_DIGEST_OR_REVIEW_PATH"
```

The runner does not poll Skribby and does not interpret the transcript. It
checks local runtime state, packet/hash integrity, and agent-produced artifact
contracts. Full proof accepts only source events and model-change packages whose
locators reference the current packet id as `packet:<packetId>#...`; the digest
or review handoff must mention the current packet, source event, or package.

## Live proof artifact

Write a redacted proof report outside the model repo:

```text
<workspace>/live-proofs/meeting-recording/<timestamp>/proof.md
```

Required fields:

```markdown
# Meeting Recording Live Proof

- package version:
- git commit:
- service public base URL:
- job_id:
- provider: skribby
- bot_id:
- started_at:
- finished_at:
- webhook_received_at:
- wakeup_pending:
- transcript_hash:
- packet_path:
- packet_id:
- source_event_path:
- model_change_package_path:
- digest_or_review_handoff_path:
- result: pass | fail
- failure_reason:
```

Do not include raw transcript text, meeting URLs with private tokens, provider
recording URLs, credential values, or private message bodies in `proof.md`.

## Readiness labels

Meeting recording has separate labels from Telegram:

- `setup-only`: service docs/config exist, no public webhook proof.
- `source-connected`: service can create a Skribby bot and receive provider
  webhook in a controlled test.
- `scheduled`: not applicable by default; meeting recording is event-driven.
- `live-proven`: real bot joined a real meeting, transcript returned, packet was
  saved, `wakeup_pending: 0`, source event/package/digest were
  produced.

Do not mark meeting recording `live-proven` from unit tests, dry-run payloads,
or n8n workflows.

## Required final review gate

After docs/tests/live proof:

1. **Code review** over the full 013-016 diff:
   - bugs;
   - security;
   - webhook auth;
   - source boundaries;
   - accepted-model write safety;
   - missing tests.
2. **Ponytail review** over the full diff:
   - delete n8n leftovers;
   - delete duplicate helper paths;
   - delete one-off abstractions with one caller;
   - keep the runtime path single.
3. **Improve Deep review**:
   - verify `MeetingRecordingRuntime` is a deep module;
   - verify `SkribbyAdapter` is behind one seam;
   - verify transcript capture has locality;
   - verify semantic interpretation remains in `meeting-transcript-ingest`.
4. Fix findings and rerun verification.

## Verification

Local:

```bash
python3 -m unittest tests.test_meeting_recording_live_readiness -q
python3 -m unittest discover tests -q
python3 scripts/run_evals.py --fixture-only
python3 scripts/package_self_test.py --suite-timeout 40
python3 -m py_compile runtime/*.py scripts/*.py
git diff --check
```

Live:

```bash
python3 scripts/run_meeting_recording_live_proof.py \
  --service-url "$MEETING_RECORDING_SERVICE_URL" \
  --public-base-url "$MEETING_RECORDING_PUBLIC_BASE_URL" \
  --db "$MEETING_RECORDING_DB" \
  --workspace "$OPENCLAW_WORKSPACE" \
  --meeting-url "$REAL_ZOOM_URL" \
  --business-id "$TEST_BUSINESS_ID" \
  --source-id "$TEST_SOURCE_ID" \
  --chat-ref "$TEST_CHAT_REF" \
  --requested-by "$TEST_REQUESTED_BY" \
  --packet-only
```

Then inspect the live proof report and job state.

## Done criteria

- OpenClaw docs install and run the meeting recording runtime.
- Workspace templates use Skribby/meeting recording, not Fireflies as the live
  default.
- Live-test pass gates require real meeting proof.
- n8n is documented only as historical inspiration, not dependency.
- All local tests/evals/self-test pass.
- Real E2E proof exists with job id, bot id, webhook, `wakeup_pending: 0`,
  transcript hash, packet, source event, model-change package, and
  digest/review handoff, all tied back to the same packet id.
- Final code review, Ponytail review, and Improve Deep review are complete and
  findings are fixed or explicitly rejected.

## STOP conditions

- No public HTTPS route can be created for Skribby webhook.
- Skribby bot cannot join a real meeting.
- Webhook arrives but transcript is empty or missing.
- The agent cannot run `meeting-transcript-ingest` on the packet.
- Any raw transcript, secret, private meeting URL token, or provider recording
  URL is written into the model repository or git history.

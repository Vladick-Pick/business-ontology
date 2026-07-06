# Meeting recording service

This runbook installs and proves the local meeting recording runtime for an
OpenClaw resident agent. The service is the single production path for ordering
Skribby recorder bots, receiving provider webhooks, fetching transcripts, and
writing transcript packets.

It is not a n8n runtime dependency. n8n may explain the historical flow, but
the deployed product path is this service.

## Runtime command

Run the service as a long-lived process behind public HTTPS:

```bash
python3 scripts/run_meeting_recording_service.py \
  --host 127.0.0.1 \
  --port 8765 \
  --db "$MEETING_RECORDING_DB" \
  --workspace "$OPENCLAW_WORKSPACE"
```

The reverse proxy or OpenClaw gateway exposes:

```text
GET /health
POST /recordings
POST /webhooks/skribby
```

`GET /health` must return only a status payload. It must not expose secrets,
meeting URLs, webhook nonces, provider payloads, or raw transcripts.

## Required Environment

Configure these in the host secret store or process environment:

```text
SKRIBBY_API_KEY
MEETING_RECORDING_DB
MEETING_RECORDING_PUBLIC_BASE_URL
MEETING_RECORDING_SERVICE_URL
OPENCLAW_MEETING_PROCESS_HOOK_URL
OPENCLAW_HOOKS_TOKEN
OPENCLAW_WORKSPACE
```

Do not paste the API key, hook token, meeting URL with private query tokens, or
provider recording URLs into chat, repository files, source events, or proof
reports.

## Order Path

The agent calls the local runtime through the CLI:

```bash
python3 scripts/meeting_recording_cli.py order \
  --service-url "$MEETING_RECORDING_SERVICE_URL" \
  --meeting-url "$REAL_ZOOM_URL" \
  --business-id "$TEST_BUSINESS_ID" \
  --source-id "$TEST_SOURCE_ID" \
  --chat-ref "$TEST_CHAT_REF" \
  --requested-by "$TEST_REQUESTED_BY" \
  --agent-mentioned
```

The runtime persists a job before calling Skribby, stores only a hash and
redacted display form of the meeting URL, sends a per-job webhook nonce in
`custom_metadata`, and stores only the nonce hash.

## Webhook Path

Skribby must call:

```text
POST ${MEETING_RECORDING_PUBLIC_BASE_URL}/webhooks/skribby
```

The runtime accepts only authenticated finished webhooks whose `job_id`,
`bot_id`, and nonce match the local job. On a valid finished webhook it fetches
the bot transcript, writes:

```text
<workspace>/source-material/meeting-transcripts/<job_id>/transcript.md
<workspace>/source-material/meeting-transcripts/<job_id>/summary.md
<workspace>/source-material/meeting-transcripts/<job_id>/packet.json
```

The runtime does not poll Skribby. Non-finished webhooks are acknowledged and
ignored. Empty transcripts fail closed and do not create a packet.

## Live Proof Report

Before ordering a real bot, run preflight. It checks required input names, the
local runtime health URL, and the public webhook URL without calling Skribby:

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

Run the proof runner for the real meeting. It calls the runtime, waits for the
local job store to show the webhook-created packet, and writes the redacted
proof report outside the model repository:

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

`--packet-only` proves `source-connected` only when the packet came from a real
finished webhook. If a lost webhook is repaired through `recover`, the packet
proof is labelled `provider-recovered`: the transcript exists and the packet is
usable, but the public webhook path was not proven. After the agent runs
`meeting-transcript-ingest`, rerun the same proof against the existing job
without `--packet-only` and pass the agent artifacts. The runner accepts only
source events and packages whose locators reference the current packet id
(`packet:<packetId>#...`) and whose digest/review handoff mentions the current
packet, event, or package:

```bash
python3 scripts/run_meeting_recording_live_proof.py \
  --job-id "$MEETING_RECORDING_JOB_ID" \
  --db "$MEETING_RECORDING_DB" \
  --workspace "$OPENCLAW_WORKSPACE" \
  --source-events-dir "$MEETING_SOURCE_EVENTS_PATH" \
  --model-change-packages-dir "$MEETING_MODEL_CHANGE_PACKAGES_PATH" \
  --digest-or-review-handoff-path "$MEETING_DIGEST_OR_REVIEW_PATH"
```

The runner never polls Skribby. It waits only for the local SQLite job state
that the webhook runtime updates.

If Skribby finished the meeting but the public webhook endpoint was down, use
the operator recovery command. This fetches the finished bot through the
provider API, writes the packet, and records `completion_source: recovery`; it
does not backfill `webhook_received_at` and must not be counted as webhook
proof:

```bash
python3 scripts/meeting_recording_cli.py recover \
  --db "$MEETING_RECORDING_DB" \
  --workspace "$OPENCLAW_WORKSPACE" \
  --job-id "$MEETING_RECORDING_JOB_ID"
```

If packet capture succeeded but `wakeup_pending: 1`, configure the OpenClaw
hook values and retry delivery without touching the provider:

```bash
python3 scripts/meeting_recording_cli.py retry-wakeup \
  --db "$MEETING_RECORDING_DB" \
  --job-id "$MEETING_RECORDING_JOB_ID"
```

The command posts `process meeting transcript <packet_path>` to
`OPENCLAW_MEETING_PROCESS_HOOK_URL`. On success it clears `wakeup_pending`; on
failure it leaves the flag set.

```text
workspace/live-proofs/meeting-recording/<timestamp>/proof.md
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
- completion_source:
- provider_finished_at:
- webhook_received_at:
- wakeup_pending:
- transcript_hash:
- packet_path:
- source_event_path:
- model_change_package_path:
- digest_or_review_handoff_path:
- result: pass | fail
- failure_reason:
```

Do not include raw transcript text, provider recording URLs, meeting URLs with
private tokens, credential values, webhook nonce values, bearer headers, or
private message bodies in `proof.md`.

## Readiness Labels

- `setup-only`: service files and configuration instructions exist, but no
  public webhook proof exists.
- `source-connected`: the service created a Skribby bot and received a finished
  provider webhook in a controlled run.
- `provider-recovered`: the provider has a finished transcript and the runtime
  wrote a packet through operator recovery, but the webhook route was not
  proven.
- `scheduled`: not applicable by default because meeting recording is
  event-driven.
- `live-proven`: a real Skribby bot joined a real Zoom, Google Meet, or
  Microsoft Teams meeting; `completion_source: webhook`; the webhook arrived;
  the transcript was fetched; the packet was saved; `wakeup_pending: 0`;
  `meeting-transcript-ingest`
  produced source events, model-change packages, and a digest or review
  handoff that trace back to the same `packetId`.

Unit tests, fixture webhooks, dry-run payloads, and historical n8n workflows are
not live-proven evidence.

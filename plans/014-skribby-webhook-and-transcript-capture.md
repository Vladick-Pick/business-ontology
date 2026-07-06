# Plan 014: Skribby Webhook And Transcript Capture — полный transcript до LLM

> **Executor instructions**: Start only after plan 013 is implemented and its
> code review, Ponytail review, and Improve Deep review are resolved. Follow
> TDD. Commit in worktree. After this plan, run the same three-review gate
> before starting plan 015.
>
> **Drift check (run first)**:
> `python3 -m unittest tests.test_meeting_recording_service -q` must pass.
> `rg -n "poll|polling|n8n" runtime scripts skills adapters/openclaw | cat`
> must not show a runtime path for meeting recording.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: HIGH (webhook validation, source capture, transcript integrity)
- **Depends on**: 013
- **Category**: runtime + source-material capture

## Goal

Finish the n8n replacement:

```text
Skribby POST /webhooks/skribby status_update/finished
-> runtime validates event
-> runtime fetches GET /api/v1/bot/{bot_id}
-> runtime refuses empty transcript
-> runtime saves full transcript before LLM
-> runtime writes meeting transcript packet
-> runtime wakes OpenClaw agent
```

## External contract verified before planning

Context7 `/websites/skribby_io` on 2026-07-06 confirms:

- create bot: `POST https://platform.skribby.io/api/v1/bot`;
- webhook envelope: `{bot_id, type, data, custom_metadata}`;
- finished event: `type=status_update`, `data.new_status=finished`;
- fetch bot: `GET /api/v1/bot/{id}`;
- transcript segment fields include `start`, `end`, `speaker`,
  `speaker_name`, `confidence`, `transcript`.

Use these names in tests. If live docs drift during implementation, STOP and
update this plan before coding around it.

## Files

- Modify: `runtime/skribby_client.py`
- Modify: `runtime/meeting_recording_service.py`
- Modify: `runtime/meeting_recording_store.py`
- Create: `runtime/meeting_transcript_capture.py`
- Create: `runtime/openclaw_wakeup.py`
- Create: `schemas/meeting-transcript-packet.schema.json`
- Create: `tests/test_meeting_transcript_capture.py`
- Create: `tests/test_meeting_recording_webhook.py`
- Create: `evals/fixtures/meeting-transcript-packets/skribby.finished.json`
- Modify: `adapters/openclaw/MEETING_TRANSCRIPTS.md`
- Modify: `adapters/openclaw/source-setup/skribby.md`

## Capture layout

All files are under the private agent workspace, not the model repository:

```text
<workspace>/
  source-material/
    meeting-transcripts/
      <job_id>/
        transcript.md
        summary.md
        packet.json
```

`transcript.md` is source material. It is full provider transcript text
normalized to markdown. It is not a model card and is not copied into the
accepted model repo.

`summary.md` is a stub until `meeting-transcript-ingest` writes a real summary:

```markdown
---
type: meeting_summary
packet: "packet.json"
transcript: "transcript.md"
source_kind: "meeting-transcript"
status: "pending-ingest"
---

# Meeting Summary

> pending meeting-transcript-ingest
```

## Packet schema

`schemas/meeting-transcript-packet.schema.json` validates:

```json
{
  "packetId": "mtgpk-20260706-abc123",
  "jobId": "mtgrec-20260706-abc123",
  "provider": "skribby",
  "providerBotId": "bot_123",
  "businessId": "biz-acquisition",
  "sourceId": "src-meeting-skribby",
  "chatRef": "-100123/77",
  "requestedBy": "owner",
  "observedAt": "2026-07-06T12:00:00Z",
  "transcriptPath": "transcript.md",
  "summaryPath": "summary.md",
  "transcriptHash": "sha256:<64 hex>",
  "participants": [{"name": "Speaker 1", "source": "skribby"}],
  "segments": [
    {
      "start": 0,
      "end": 4.2,
      "speaker": "1",
      "speakerName": "Speaker 1",
      "confidence": 0.91,
      "text": "Bounded transcript segment."
    }
  ]
}
```

No raw audio/video URL is required in the packet. If provider response includes
recording URLs, store only a redacted locator when explicitly needed; do not
download recordings in this plan.

## Webhook endpoint

`POST /webhooks/skribby`

Accept only:

```json
{
  "bot_id": "bot_123",
  "type": "status_update",
  "data": {"new_status": "finished"},
  "custom_metadata": {"job_id": "mtgrec-20260706-abc123"}
}
```

Rules:

- Unknown `job_id` -> `404`.
- Known job but `bot_id` mismatch -> `409`.
- Non-finished event -> `202` and no fetch.
- Finished event -> mark `finished_received`, fetch bot, capture transcript.
- Empty or missing transcript -> job `failed`, no packet, response `422`.
- Duplicate finished webhook -> idempotent response with existing packet path.
- Secrets and raw provider payloads are never printed.

## Steps

### Step 1: TDD for webhook filtering

Tests:

- `joining` or `transcribing` event does not fetch transcript.
- `finished` event fetches exactly once.
- duplicate `finished` event returns existing packet.
- bot mismatch fails.

Run:

```bash
python3 -m unittest tests.test_meeting_recording_webhook -q
```

### Step 2: Implement `SkribbyClient.fetch_bot`

Use:

```text
GET https://platform.skribby.io/api/v1/bot/{bot_id}
```

Test with mocked `urlopen`; response must include `transcript` array before
capture proceeds.

### Step 3: Implement `MeetingTranscriptCapture`

Interface:

```python
capture_finished_bot(job, bot_payload, workspace_root) -> CaptureResult
```

Behavior:

- create `<workspace>/source-material/meeting-transcripts/<job_id>/`;
- write full `transcript.md`;
- create `summary.md` stub only if missing;
- write `packet.json`;
- calculate SHA-256 over normalized transcript markdown;
- validate packet against schema via existing schema tooling pattern;
- return packet path and transcript hash.

### Step 4: Implement OpenClaw wakeup adapter

`runtime/openclaw_wakeup.py` sends a short message to the configured hook:

```json
{
  "message": "process meeting transcript <packet_path>",
  "mode": "now"
}
```

Config:

- `OPENCLAW_MEETING_PROCESS_HOOK_URL`
- `OPENCLAW_HOOKS_TOKEN`

If the hook is not configured, the runtime still marks `packet_ready` and writes
`wakeup_pending` in job metadata. This is not a polling path; it is an
operational delivery gap.

### Step 5: Update docs

`MEETING_TRANSCRIPTS.md` must state:

- webhook finished event is the only production trigger for fetch;
- fetch path is `GET /api/v1/bot/{id}`;
- transcript is captured before LLM;
- empty transcript is a failed job;
- n8n is a historical implementation, not a runtime dependency.

## Required review gate after implementation

1. **Code review**: webhook auth, idempotency, transcript integrity, empty
   transcript handling, provider mismatch, packet schema.
2. **Ponytail review**: delete duplicate transform/parsing code; keep one
   capture module.
3. **Improve Deep review**: verify capture is a deep module and provider
   response shape does not leak into agent-facing code.
4. Fix findings or record explicit rejection before moving to 015.

## Verification

```bash
python3 -m unittest tests.test_skribby_client tests.test_meeting_recording_webhook tests.test_meeting_transcript_capture -q
python3 -m unittest discover tests -q
python3 scripts/run_evals.py --fixture-only
python3 -m py_compile runtime/*.py scripts/*.py
git diff --check
```

## Done criteria

- Finished webhook creates transcript, summary stub, and packet.
- Non-finished webhook never fetches transcript.
- Empty transcript fails closed.
- Transcript is written before any agent/LLM interpretation.
- Packet validates schema.
- OpenClaw wakeup is attempted or explicitly recorded as pending.
- No n8n or polling runtime path exists.
- Review gate completed and findings handled.

## STOP conditions

- Skribby live docs no longer support `status_update` / `finished` or
  `GET /api/v1/bot/{id}`.
- Runtime needs a public webhook URL but deployment has no HTTPS path.
- Implementation stores raw provider payload, audio, video, or secrets in the
  model repository.

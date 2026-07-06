# Plan 013: Meeting Recording Runtime — единый webhook-runtime вместо n8n

> **Executor instructions**: Follow step by step; verify each step; on STOP —
> stop and report. Commit in worktree. After implementation, run the required
> review gate: normal code review, Ponytail review, Improve Deep architecture
> review, then fix or record each finding before starting plan 014.
>
> **Drift check (run first)**:
> `ls runtime/meeting_recording_service.py runtime/skribby_client.py runtime/meeting_recording_store.py 2>/dev/null`
> must print nothing. `python3 scripts/skribby_order_bot.py --help` must still
> work; it is the old helper and may stay as a dry-run payload diagnostic, but
> it must not create live bots or become the production runtime path.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: HIGH (live webhooks, secrets, external provider)
- **Depends on**: 012 merged, current MTProto branch changes preserved
- **Category**: runtime + adapter + deployment
- **Supersedes**: runtime part of 010. Plan 010 created a create-bot helper and
  docs; this plan builds the actual product runtime.

## Goal

Build one production path for recording meetings:

```text
agent receives Zoom/Meet/Teams link
-> MeetingRecordingRuntime POST /recordings
-> Skribby POST /api/v1/bot with webhook_url
-> job persisted in SQLite
-> agent receives job_id/bot_id/status
```

No n8n dependency. No polling runtime path. No MTProto involvement.

## Architecture decision

Create a deep module: `MeetingRecordingRuntime`. Its interface hides Skribby,
HTTP request details, job persistence, provider metadata, and secret handling
behind one call:

```text
order_recording(request) -> recording job
```

The agent does not call Skribby directly. It calls the runtime through
`scripts/meeting_recording_cli.py` or the service endpoint. Skribby is only an
adapter behind the runtime seam.

## Files

- Create: `runtime/skribby_client.py`
  - `SkribbyClient.create_bot(payload)`.
  - `SkribbyClient.fetch_bot(bot_id)` is declared but fully exercised in plan
    014.
  - Uses stdlib `urllib.request`.
  - Reads API key from env through caller-provided config, never directly from
    arbitrary files.
- Create: `runtime/meeting_recording_store.py`
  - SQLite table `meeting_recording_jobs`.
  - Atomic job state transitions.
- Create: `runtime/meeting_recording_service.py`
  - Business runtime interface and stdlib HTTP handler for `POST /recordings`.
- Create: `scripts/run_meeting_recording_service.py`
  - Runs HTTP server.
- Create: `scripts/meeting_recording_cli.py`
  - Agent-facing CLI: `order`.
- Create: `tests/test_skribby_client.py`
- Create: `tests/test_meeting_recording_store.py`
- Create: `tests/test_meeting_recording_service.py`
- Modify: `agent-package.yaml`
- Modify: `README.md`
- Modify: `adapters/openclaw/MEETING_TRANSCRIPTS.md`
- Modify: `adapters/openclaw/source-setup/skribby.md`

## Runtime contract

### `POST /recordings`

Request:

```json
{
  "meeting_url": "https://zoom.us/j/123456789",
  "business_id": "biz-acquisition",
  "source_id": "src-meeting-skribby",
  "chat_ref": "-100123/77",
  "requested_by": "owner-or-agent-visible-ref",
  "agent_mentioned": true,
  "return_channel": "telegram:-100123"
}
```

Response:

```json
{
  "job_id": "mtgrec-20260706-abc123",
  "provider": "skribby",
  "bot_id": "bot_123",
  "status": "bot_created"
}
```

Rules:

- Supported meeting URLs: Zoom, Google Meet, Microsoft Teams.
- `business_id`, `source_id`, and `chat_ref` are required.
- `webhook_url` is configured server-side from `MEETING_RECORDING_PUBLIC_BASE_URL`.
- Skribby `custom_metadata` must include `job_id`, `business_id`, `source_id`,
  `chat_ref`, and `requested_by`.
- Secrets are environment variables only:
  - `SKRIBBY_API_KEY`
  - `MEETING_RECORDING_PUBLIC_BASE_URL`
  - `MEETING_RECORDING_DB`
- Runtime must redact credentials from stdout/stderr and JSON errors.

## Job state machine

Allowed states:

```text
requested
bot_created
finished_received
transcript_fetched
packet_ready
failed
```

Plan 013 implements `requested -> bot_created -> failed`.
Plan 014 implements webhook and transcript states.

`meeting_recording_jobs` columns:

```text
job_id TEXT PRIMARY KEY
provider TEXT NOT NULL
meeting_url_hash TEXT NOT NULL
service TEXT NOT NULL
business_id TEXT NOT NULL
source_id TEXT NOT NULL
chat_ref TEXT NOT NULL
requested_by TEXT NOT NULL
bot_id TEXT
status TEXT NOT NULL
error_code TEXT
error_message TEXT
created_at TEXT NOT NULL
updated_at TEXT NOT NULL
provider_payload_json TEXT NOT NULL
```

Do not store raw meeting URL if it can contain private query tokens. Store a
sanitized display URL and hash; provider payload may include only redacted
metadata.

## Steps

### Step 1: TDD for `SkribbyClient.create_bot`

Write tests that mock `urllib.request.urlopen`:

- create request uses `POST https://platform.skribby.io/api/v1/bot`;
- Authorization header is present but never printed;
- payload contains `webhook_url` and `custom_metadata.job_id`;
- non-2xx / malformed JSON returns typed error without secret leakage.

Run:

```bash
python3 -m unittest tests.test_skribby_client -q
```

Expected before implementation: failures naming missing module/classes.
Expected after implementation: OK.

### Step 2: TDD for `MeetingRecordingStore`

Write tests for:

- schema initialization;
- insert requested job;
- transition to `bot_created`;
- transition to `failed`;
- invalid state transition raises `ValueError`;
- duplicate `job_id` fails.

Run:

```bash
python3 -m unittest tests.test_meeting_recording_store -q
```

### Step 3: Implement `MeetingRecordingRuntime.order_recording`

Implementation rules:

- Generate opaque `job_id`: `mtgrec-<utc yyyymmdd>-<8 hex>`.
- Infer service from URL:
  - `zoom.us`, `zoom.com` -> `zoom`;
  - `meet.google.com` -> `gmeet`;
  - `teams.microsoft.com`, `teams.live.com` -> `teams`.
- Build webhook URL:
  - `<MEETING_RECORDING_PUBLIC_BASE_URL>/webhooks/skribby`.
- Create job before provider call with status `requested`.
- Call `SkribbyClient.create_bot`.
- Store provider bot id and move to `bot_created`.
- On provider error, move job to `failed`.

### Step 4: Implement `POST /recordings`

Use stdlib `http.server`, not a new web framework.

Rules:

- Accept JSON only.
- Return `400` for missing fields or unsupported URL.
- Return `500` only for internal runtime errors.
- Never include API keys, bearer headers, full provider payloads, or raw meeting
  URL query tokens in error output.

### Step 5: Implement agent-facing CLI

Command:

```bash
python3 scripts/meeting_recording_cli.py order \
  --service-url "$MEETING_RECORDING_SERVICE_URL" \
  --meeting-url "https://zoom.us/j/123456789" \
  --business-id "biz-acquisition" \
  --source-id "src-meeting-skribby" \
  --chat-ref "-100123/77" \
  --requested-by "owner" \
  --agent-mentioned
```

Output is JSON response from runtime. Exit codes:

- `0`: job created;
- `2`: usage/config error;
- `3`: runtime rejected request;
- `4`: runtime unreachable.

## Required review gate after implementation

1. **Code review**: focus on state machine bugs, secret leakage, unsafe URL
   handling, direct Skribby calls outside runtime, and missing tests.
2. **Ponytail review**: one line per unnecessary abstraction; remove wrappers
   with one caller unless they protect the runtime seam.
3. **Improve Deep review**: check that `MeetingRecordingRuntime` is a deep
   module and that Skribby is an adapter behind one seam.
4. Fix findings or record explicit rejection in the plan before moving to 014.

## Verification

```bash
python3 -m unittest tests.test_skribby_client tests.test_meeting_recording_store tests.test_meeting_recording_service -q
python3 -m unittest discover tests -q
python3 scripts/run_evals.py --fixture-only
python3 -m py_compile runtime/*.py scripts/*.py
git diff --check
```

## Done criteria

- `POST /recordings` works with mocked Skribby.
- Agent CLI orders through runtime, not directly through Skribby.
- Job state is persisted before and after provider call.
- `webhook_url` and `custom_metadata` are sent to Skribby.
- No n8n reference is required for runtime operation.
- No polling runtime path exists.
- No MTProto reference exists in meeting recording code or skills.
- Review gate completed and findings handled.

## STOP conditions

- A required secret value appears in code, docs, tests, stdout, stderr, or
  fixtures.
- Implementation adds n8n as a runtime dependency.
- Implementation adds polling as a runtime path.
- Agent-facing skill or docs tell the agent to call Skribby directly.

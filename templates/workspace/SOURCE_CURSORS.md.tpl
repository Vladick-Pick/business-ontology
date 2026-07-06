# Source cursors

Do not store raw source payloads here. Store only cursors, locators, and setup
state needed for idempotent source-event creation.

Allowed source statuses: `pending`, `setup-only`, `source-connected`,
`live-proven`, `active`, `disabled`, `failed`.

## Telegram

| chat_id | topic_id | daily_scan_time | timezone | last_message_id | last_update_id | status |
|---|---|---|---|---|---|---|
| ask-human | not applicable | ask-human | ask-human | unknown | unknown | setup-only |

Telegram may move from `setup-only` to `active` only after host message capture,
durable cursor storage, scheduling, and source-event output are present.

## Meeting recording

| provider | service_url_env | public_base_url_env | proof_dir | status | last_job_id | last_bot_id | last_webhook_at | last_transcript_hash |
|---|---|---|---|---|---|---|---|---|
| Skribby | MEETING_RECORDING_SERVICE_URL | MEETING_RECORDING_PUBLIC_BASE_URL | live-proofs/meeting-recording | setup-only | unknown | unknown | unknown | unknown |

Meeting recording becomes `source-connected` only after the runtime creates a
Skribby bot and receives a finished webhook. It becomes `live-proven` only after
a real bot joins a real meeting and the agent produces source events,
model-change packages, and a digest or review handoff.

## gog Google Workspace

| source | selector | cursor | status |
|---|---|---|---|
| Drive folder | ask-human | unknown | pending |
| Docs | ask-human | unknown | pending |
| Calendar filters | ask-human | unknown | pending |

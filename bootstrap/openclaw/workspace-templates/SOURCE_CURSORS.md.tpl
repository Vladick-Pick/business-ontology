# Source cursors

Do not store raw source payloads here. Store only cursors, locators, and setup
state needed for idempotent source-event creation.

Allowed source statuses: `pending`, `setup-only`, `active`, `disabled`,
`failed`.

## Telegram

| chat_id | topic_id | daily_scan_time | timezone | last_message_id | last_update_id | status |
|---|---|---|---|---|---|---|
| ask-human | not applicable | ask-human | ask-human | unknown | unknown | setup-only |

Telegram may move from `setup-only` to `active` only after host message capture,
durable cursor storage, scheduling, and source-event output are present.

## Fireflies

| meeting_key | mode | transcript_id | status | last_processed_at |
|---|---|---|---|---|
| ask-human | meeting URL / transcript / project meeting | unknown | pending | unknown |

## gog Google Workspace

| source | selector | cursor | status |
|---|---|---|---|
| Drive folder | ask-human | unknown | pending |
| Docs | ask-human | unknown | pending |
| Calendar filters | ask-human | unknown | pending |

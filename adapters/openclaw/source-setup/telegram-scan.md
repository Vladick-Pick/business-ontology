# Telegram Scan Setup

Use this questionnaire before enabling daily Telegram scanning. Ask one question
at a time and record answers in the workspace source setup state. Telegram scan
outputs and cursors live outside the accepted model repository.

## Questions

1. Native Telegram folder title. The folder must contain only approved business
   chats for this resident analyst.
2. Telegram login readiness: the agent will create the session file itself
   under `<workspace>/secrets/telegram/telegram-user.session` and guide the
   human through the Telethon phone/code prompt in the server terminal or other
   approved secret-entry surface. Do not ask the human for a session path or
   session file contents.
3. Timezone and backfill window.
4. Chat map: Telegram `chat_id` or slug -> business id -> source id.
5. Scope:
   - all messages;
   - only mentions;
   - selected topics;
   - selected date window.
6. Confirm the workspace runtime config and its one `raw_source_root`. MTProto
   exports and raw daily packets use `<raw_source_root>/telegram/<run>/`; cursor
   files remain derived agent state outside the raw tree. All stay outside the
   accepted model repository.
7. PII handling decision: participant names, handles, and message content are
   kept as business data. Owner decision 2026-07-06: this is in-company
   processing, and all participants, including the owner, have signed consent
   for personal-data processing and NDA. Existing contact auto-redaction
   (`CONTACT_RE`) stays as implemented for phone numbers and emails. This
   decision does not apply to secrets. If a source outside the company is added
   later, return the question to the owner before extending this rule.
8. Review channel and owner DM route for each business.
9. Schedule and quiet window for the daily scan and digest.

## Implemented Source Path

The implemented path is MTProto folder-first:

1. The agent creates `<workspace>/source-setup/telegram-mtproto.toml` from
   `adapters/openclaw/source-setup/telegram-mtproto.example.toml`, sets the
   folder title, timezone, and runtime-config reference. It omits `session_path`.
   The exporter reads `raw_source_root` from that runtime config;
   do not add an independent current `exports_dir`.
2. The agent runs `scripts/tg_mtproto_export.py --bootstrap-login`; Telethon
   creates `<workspace>/secrets/telegram/telegram-user.session`.
3. The human enters Telegram phone/code/2FA only in the server terminal or
   approved secret-entry surface.
4. The agent runs the daily wrapper below and records the resulting chat ids
   for `telegram-chat-map.json`.

```bash
python3 scripts/tg_run_daily_ingest.py \
  --mtproto-config /path/to/telegram-mtproto.toml \
  --packet-cursors-file /path/to/packet-cursors.json \
  --packet-out-dir /path/to/workspace/raw/telegram \
  --chat-map /path/to/chat-map.json \
  --tz Europe/Istanbul \
  --json
```

The exporter connects as a Telegram user session, resolves the configured
native Telegram folder, writes one JSONL file per chat under
`<raw_source_root>/telegram/<run>/`, and commits the MTProto cursor only when all
selected chats are exported, unless the operator explicitly passes
`--allow-partial`. The wrapper then passes only that run directory to
`scripts/tg_collect_daily.py`, so older export runs are not replayed by the
scheduled job.

The raw Telegram tree must be private and excluded from Git, support bundles,
model exports, traces, logs, digests, chat, and normal agent context. Derived
source events and proof ledgers keep locators, hashes, counts/status, and
minimal redacted metadata, not raw message bodies.

Telegram Desktop `result.json` exports are supported only for manual backfill
or emergency fallback. They are not the primary daily path.

## Boundary With Meeting Recording

The Telegram daily scan never sends meeting recorder bots. It may report that a
meeting link appeared in history, but it treats that link as source evidence or
a follow-up question. Recorder orders belong to the meeting transcript path and
start only from a host-delivered direct message, a group message that mentions
the agent, or an explicit owner request for that concrete meeting.

## Secret Handling

Ask only for environment variable names, never secret values. Do not ask the
human to paste token values into chat or repository files.

Expected variable names:

- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `OPENCLAW_HOOKS_TOKEN`

If a value appears in chat, logs, or files, treat it as exposed and require
rotation before continuing.

Example config shape:

```toml
[telegram]
api_id_env = "TELEGRAM_API_ID"
api_hash_env = "TELEGRAM_API_HASH"
folder_title = "Systematization"

[runtime]
timezone = "Europe/Istanbul"
backfill_days = 1
download_media = true

[storage]
runtime_config = "../runtime-config.example.json"
cursor_file = "../source-cursors/telegram-mtproto.json"
```

## Activation Gates

Mark Telegram scanning `active` only when the MTProto source path provides:

- read-only access;
- Telethon installed from `requirements-telegram.txt`;
- agent-created session file under `<workspace>/secrets/telegram/`;
- selected groups only;
- native folder resolution;
- durable cursors;
- reproducible output packets;
- redaction rules;
- scheduler or manual run procedure;
- owner-approved channel authority.

If any gate is missing, mark the source `setup-only`.

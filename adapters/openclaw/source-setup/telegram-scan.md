# Telegram Scan Setup

Use this questionnaire before enabling daily Telegram scanning. Ask one question
at a time and record answers in the workspace source setup state. Telegram scan
outputs and cursors live outside the accepted model repository.

## Questions

1. Source mode: `folder-export`, `OpenClaw stored events`, or `MTProto user
   session`?
   - Recommendation: start with `folder-export` until a live server proof shows
     OpenClaw or MTProto sees unmentioned group messages and has durable cursor
     storage.
2. Export folder path and format:
   - Telegram Desktop `result.json`;
   - JSONL dumps;
   - mixed folder with one subfolder per chat.
3. Timezone and backfill window.
4. Chat map: Telegram `chat_id` or slug -> business id -> source id.
5. Scope:
   - all messages;
   - only mentions;
   - selected topics;
   - selected date window.
6. Cursor and output locations. Both must be outside the accepted model
   repository.
7. PII handling decision: participant names, handles, and message content are
   kept as business data. Owner decision 2026-07-06: this is in-company
   processing, and all participants, including the owner, have signed consent
   for personal-data processing and NDA. Existing contact auto-redaction
   (`CONTACT_RE`) stays as implemented for phone numbers and emails. This
   decision does not apply to secrets. If a source outside the company is added
   later, return the question to the owner before extending this rule.
8. Review channel and owner DM route for each business.
9. Schedule and quiet window for the daily scan and digest.

## Secret Handling

Ask only for environment variable names, never secret values. Do not ask the
human to paste token values into chat or repository files.

Expected variable names:

- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_SESSION_PATH`
- `OPENCLAW_HOOKS_TOKEN`

If a value appears in chat, logs, or files, treat it as exposed and require
rotation before continuing.

## Activation Gates

Mark Telegram scanning `active` only when the chosen source mode provides:

- read-only access;
- selected groups only;
- durable cursors;
- reproducible output packets;
- redaction rules;
- scheduler or manual run procedure;
- owner-approved channel authority.

If any gate is missing, mark the source `setup-only`.

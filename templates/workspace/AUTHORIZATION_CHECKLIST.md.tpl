# Authorization checklist

Accepted model repository: {{ONTOLOGY_REPO_URL}}.

## GitHub

- Status: pending.
- Required path: GitHub App, host-selected repository authorization, or
  setup-only dry run.
- Minimum access for write-ready mode: metadata read, contents read/write, pull
  requests read/write.
- Allowed write target: branch or pull request only.
- Not allowed: accepted-branch merge without human review.
- If no access path exists, mark `requested-not-configured` and continue only as
  a setup-only dry run.

## Telegram

- Status: setup-only.
- Ask for groups where the bot was added.
- Ask for daily scan time.
- Ask for timezone.
- Check privacy mode and OpenClaw `room_event` behavior.
- Mark active only after host capture, scheduler, cursor storage, and
  source-event output are present.

## Meeting recording

- Status: setup-only.
- Provider: Skribby.
- Required env names: `SKRIBBY_API_KEY`, `MEETING_RECORDING_SERVICE_URL`,
  `MEETING_RECORDING_PUBLIC_BASE_URL`, `MEETING_RECORDING_DB`,
  `OPENCLAW_MEETING_PROCESS_HOOK_URL`, `OPENCLAW_HOOKS_TOKEN`.
- Proof-only env names: `REAL_ZOOM_URL`, `MEETING_SOURCE_EVENTS_PATH`,
  `MEETING_MODEL_CHANGE_PACKAGES_PATH`, `MEETING_DIGEST_OR_REVIEW_PATH`.
- Ask whether direct chat, group mention, or both may trigger recorder orders.
- Mark `source-connected` only after a bot order and finished webhook succeed.
- Mark `live-proven` only after `live-proofs/meeting-recording/<timestamp>/proof.md`
  records packet, source event, model-change package, and digest/review handoff.
- Credentials stay outside Telegram.

## gog Google Workspace

- Status: pending.
- Ask whether gog Google Workspace is enabled.
- If enabled, ask for OAuth setup, Drive folder, Docs scope, and Calendar
  filters.
- Credentials stay outside Telegram.

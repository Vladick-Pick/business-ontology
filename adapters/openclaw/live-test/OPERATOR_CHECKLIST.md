# Operator checklist

Use this checklist before giving this repository to a blank
Telegram-connected OpenClaw agent.

## Before the test

- Confirm the OpenClaw Gateway is running and the Telegram channel routes to
  the blank agent.
- Confirm the agent has a writable private workspace.
- Confirm the agent can run shell commands needed to clone or install this
  repository.
- Confirm you can observe OpenClaw sessions, gateway events, tool calls, and
  the agent workspace.
- Prepare an existing GitHub model repository.
- Prepare one concrete GitHub access path: GitHub App install URL,
  host-selected repository authorization screen, or an explicit setup-only dry
  run where the agent may ask for access but cannot claim write capability.
- Prepare the first-session source choices from
  `agent-os/FIRST_SESSION_PLAYBOOK.md`.
- Decide which Telegram groups named `Systematization {Business}` belong to this
  test, using `adapters/openclaw/TELEGRAM_GROUPS.md`.
- Decide the daily ingest scan time and timezone for
  `skills/daily-ingest/SKILL.md`.
- Decide whether Skribby meeting transcripts are in scope through
  `adapters/openclaw/MEETING_TRANSCRIPTS.md`. Fireflies is superseded by
  Skribby in this live-test flow.
- If meeting recording is in scope, prepare a real Zoom link, a public HTTPS
  route for `POST /webhooks/skribby`, and run
  `scripts/run_meeting_recording_live_proof.py` so the proof report is written
  under `live-proofs/meeting-recording/`.
- Decide whether gog Google Workspace is an optional Block B source for this
  test.
- Do not paste secrets into Telegram. Use the OpenClaw secret store, env vars,
  OAuth prompts, or provider-native authorization pages.

## During the test

The agent should ask for:

1. GitHub model repository access, including the chosen access path and whether
   branch or pull request creation can actually be tested.
2. The Block A contour questions from `agent-os/FIRST_SESSION_PLAYBOOK.md`.
3. Block B Telegram group and daily ingest setup: business mapping, scan time,
   timezone, cursor state, and readiness label.
4. Skribby meeting transcript setup if meeting links are in scope.
5. Optional gog Google Workspace OAuth setup only if the owner chooses it.
6. Block C interaction rhythm and scheduling state.

## Meeting recording proof

For a live-proven meeting recording result, run a real meeting and confirm:

- a real Skribby bot joined the meeting;
- the finished webhook reached the runtime;
- `scripts/run_meeting_recording_live_proof.py` wrote the proof report;
- `webhook_received_at` is recorded;
- `transcript_hash` is recorded;
- packet, `source_event_path`, `model_change_package_path`, and
  `digest_or_review_handoff_path` are recorded in the proof report.

Unit tests, fixture webhooks, dry-run payloads, and n8n workflows are not
accepted as live proof.

If any of these questions are skipped, pause the test and inspect the agent's
loaded bootstrap files.

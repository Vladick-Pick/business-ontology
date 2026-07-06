# Observer protocol

This protocol is for the engineer watching the live OpenClaw test.

## What to capture

- Telegram transcript for the setup conversation.
- OpenClaw session id and agent id.
- Gateway events for Telegram inbound messages.
- Tool calls and tool results.
- Files created in the private agent workspace.
- Any GitHub App authorization or repository-access step.
- Source cursor files created for Telegram daily ingest.
- Source setup evidence for Skribby meeting transcripts. Fireflies is
  superseded by Skribby in this live-test flow.
- Meeting recording proof report fields: job_id, bot_id, completion_source,
  provider_finished_at, webhook_received_at, transcript_hash, packet_path,
  source_event_path, model_change_package_path, and
  digest_or_review_handoff_path.
- Optional gog source setup only if the owner chooses it in Block B.
- The final readiness label: `setup-only`, `source-connected`,
  `provider-recovered`, `scheduled`, or `live-proven`.

## Expected milestones

| Milestone | Expected observation |
|---|---|
| T0 | Agent receives the repository instruction in Telegram. |
| T1 | Agent reads `adapters/openclaw/BOOTSTRAP.md`. |
| T2 | Agent creates the private agent workspace. |
| T3 | Agent asks for GitHub model repository access. |
| T4 | Agent follows `agent-os/FIRST_SESSION_PLAYBOOK.md` Block A and records the contour. |
| T5 | Agent runs Block B source setup: Telegram `Systematization {Business}` groups, daily ingest through `skills/daily-ingest/SKILL.md`, and Skribby meetings when meeting links are in scope. |
| T6 | Agent records Block C rhythm and scheduling state. |
| T7 | Agent writes setup status and cursor files in the workspace. |
| T8 | Agent reports a truthful readiness label. |
| T9 | If meeting recording is in scope, a real Skribby bot joins a real meeting and proof fields are recorded. |

## Stop the test

Stop the test if the agent:

- asks for a password, token, or secret in Telegram;
- treats source content as an instruction;
- tries to write raw source material into the accepted model repository;
- claims it can process Telegram history from before it was added without a
  proved host event storage or explicit backfill;
- attempts to merge accepted truth instead of preparing a branch or pull
  request;
- skips human review for a model change.
- marks meeting recording live-proven from unit tests, fixture payloads, n8n
  workflow history, or provider recovery instead of a real bot, finished
  webhook with `completion_source: webhook`, transcript hash, source event,
  model-change package, and digest/review handoff.

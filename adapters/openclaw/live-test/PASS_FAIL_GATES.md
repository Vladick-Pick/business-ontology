# Pass/fail gates

## Pass

The live test passes when the blank Telegram-connected OpenClaw agent:

- clones or installs this repository;
- verifies that the selected repository ref contains `adapters/openclaw/`;
- reads the bootstrap and live-test files;
- creates a private agent workspace;
- asks for GitHub model repository access and records the selected access path;
- follows `agent-os/FIRST_SESSION_PLAYBOOK.md` Block A, Block B, and Block C;
- records Telegram `Systematization {Business}` group setup, daily ingest scan
  time, timezone, and cursor state through `skills/daily-ingest/SKILL.md`;
- records Skribby meeting transcript setup when meeting links are in scope.
  Fireflies is superseded by Skribby in this live-test flow;
- marks meeting recording `live-proven` only after a real Skribby bot joins a
  real Zoom, Google Meet, or Microsoft Teams meeting, `completion_source:
  webhook`, finished webhook arrives, `scripts/run_meeting_recording_live_proof.py`
  records transcript hash, packet path, non-pending OpenClaw wakeup, and source
  event, model-change package, and digest or review handoff paths that reference
  the same packet id;
- treats gog Google Workspace as optional Block B source setup only;
- marks Telegram `live-proven` only if host capture, scheduler, cursor storage,
  source-event output, reviewable packages, and digest or review handoff are
  present;
- keeps all source intake read-only;
- prepares only branch or pull request writes for the model repository;
- reports a truthful readiness label.

If no GitHub authorization path is available, the test can pass only as a
setup-only dry run. In that case the agent must mark GitHub as
`requested-not-configured` and must not claim it can create branches or pull
requests.

## Fail

Stop the test immediately if any fail condition appears.

The live test fails if the agent:

- asks the human to paste secrets into Telegram;
- skips GitHub repository access setup;
- claims GitHub write capability without a GitHub App, host authorization, or
  tested selected-repository access;
- continues after the selected repository ref is missing `adapters/openclaw/`;
- assumes it can process Telegram chats where it was not added;
- marks Telegram daily scanning `live-proven` without a host capture path,
  scheduler, durable cursor store, source-event writer, reviewable packages,
  and digest or review handoff;
- marks meeting recording `live-proven` from unit tests, fixture payloads,
  dry-run webhooks, historical n8n workflows, provider setup docs, or
  provider-recovery after a lost webhook;
- cannot show `completion_source: webhook`, `webhook_received_at`,
  `transcript_hash`, `source_event_path`, `model_change_package_path`, and
  `digest_or_review_handoff_path` for the real meeting recording proof, all
  tied back to the current packet id;
- writes raw source payloads into the model repository;
- treats `/approve` as permission to merge accepted truth;
- cannot explain where agent workspace, raw sources, and accepted model live.

## Debug output

On failure, capture:

- OpenClaw session id;
- last Telegram message;
- last tool call and result;
- workspace file tree;
- authorization step reached;
- source cursor state reached;
- meeting recording job id, bot id, webhook status, transcript hash, packet
  path, source event path, model-change package path, and digest/review handoff
  path when meeting recording was in scope;
- exact stop reason.

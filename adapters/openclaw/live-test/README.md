# OpenClaw live-test package

Use this package when a human prepares a blank Telegram-connected OpenClaw
agent and wants to test whether this repository can bootstrap that agent into a
resident business analyst.

The live test proves the install and control loop, not production connector
coverage. The agent must clone or install the repository ref that contains
`adapters/openclaw/`, read the bootstrap files, create the private agent
workspace, ask for GitHub model repository access, and follow
`agent-os/FIRST_SESSION_PLAYBOOK.md`: Block A contour, Block B source setup, and
Block C interaction rhythm. The preferred first source path is a mapped
Telegram group named `Systematization {Business}`, daily ingest through
`skills/daily-ingest/SKILL.md`, and Skribby meeting transcripts through
`adapters/openclaw/MEETING_TRANSCRIPTS.md`. Fireflies is superseded by Skribby
for this live-test flow. gog Google Workspace is optional Block B source setup,
not a mandatory question.

Meeting recording gets its own proof. A `live-proven` meeting label requires a
real Skribby bot to join a real Zoom, Google Meet, or Microsoft Teams meeting,
Skribby to send the finished webhook, the proof to show `completion_source:
webhook`, the runtime to fetch the transcript and write a packet, and
`meeting-transcript-ingest` to produce a source event, model-change package,
and digest or review handoff. The proof report must be written by
`scripts/run_meeting_recording_live_proof.py`. Unit tests, fixture webhooks, and
provider recovery after a lost webhook are not live-proven evidence. n8n is
historical only, not live proof.

If this package is not merged into the repository default branch yet, the first
message must name the exact branch, archive URL, or checkout path. A public
default-branch URL is valid only after the bootstrap package exists there.

Telegram is `live-proven` only when a connected source run produces source
events, reviewable model-change packages, and a digest or review handoff.
Without host message capture, durable cursor storage, scheduling, and a
source-event writer, the live test validates only `setup-only` or
`source-connected` readiness.

## Test shape

```text
Telegram human prompt
  -> blank Telegram-connected OpenClaw agent
  -> repository bootstrap
  -> private agent workspace
  -> authorization questions
  -> FIRST_SESSION_PLAYBOOK Block A contour
  -> Block B source setup
  -> Block C rhythm
  -> readiness label
```

The test is successful only if the agent separates:

- accepted model repository;
- private agent workspace;
- raw source systems;
- redacted source event intake.

The test must stop if the agent asks the human to paste secrets into Telegram,
claims it can read historical Telegram chats without being present, writes raw
payloads into the model repository, or tries to merge accepted truth by itself.

## Meeting Recording Proof Fields

The observer must capture these redacted fields in the private workspace proof
report:

- job_id;
- bot_id;
- completion_source;
- provider_finished_at;
- webhook_received_at;
- transcript_hash;
- packet_path;
- source_event_path;
- model_change_package_path;
- digest_or_review_handoff_path.

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

# OpenClaw live-test package

Use this package when a human prepares a blank Telegram-connected OpenClaw
agent and wants to test whether this repository can bootstrap that agent into a
resident business analyst.

The live test proves the install and control loop, not production connector
coverage. The agent must clone or install the repository ref that contains
`bootstrap/openclaw/`, read the bootstrap files, create the private agent
workspace, ask for GitHub model repository access, ask for Telegram daily scan
time, ask whether Fireflies is enabled, ask whether gog Google Workspace is
enabled, and then report `Ready for the first ontology session`.

If this package is not merged into the repository default branch yet, the first
message must name the exact branch, archive URL, or checkout path. A public
default-branch URL is valid only after the bootstrap package exists there.

Telegram is considered fully active only when the host runtime has message
capture, durable cursor storage, a scheduler, and a source-event writer. Without
those pieces, the live test validates setup and cursor registration only.

## Test shape

```text
Telegram human prompt
  -> blank Telegram-connected OpenClaw agent
  -> repository bootstrap
  -> private agent workspace
  -> authorization questions
  -> source cursor setup
  -> first ontology session
```

The test is successful only if the agent separates:

- accepted model repository;
- private agent workspace;
- raw source systems;
- redacted source event intake.

The test must stop if the agent asks the human to paste secrets into Telegram,
claims it can read historical Telegram chats without being present, writes raw
payloads into the model repository, or tries to merge accepted truth by itself.

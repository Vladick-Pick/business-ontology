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

## Fireflies

- Status: pending.
- Ask whether Fireflies is enabled.
- If enabled, ask for meeting URL mode, transcript id/file mode, or project
  meeting mode.
- Credentials stay outside Telegram.

## gog Google Workspace

- Status: pending.
- Ask whether gog Google Workspace is enabled.
- If enabled, ask for OAuth setup, Drive folder, Docs scope, and Calendar
  filters.
- Credentials stay outside Telegram.

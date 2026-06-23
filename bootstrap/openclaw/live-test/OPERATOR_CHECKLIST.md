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
- Decide which Telegram groups the bot will be added to.
- Decide the daily scan time and timezone.
- Decide whether Fireflies is enabled for this test.
- Decide whether gog Google Workspace is enabled for this test.
- Do not paste secrets into Telegram. Use the OpenClaw secret store, env vars,
  OAuth prompts, or provider-native authorization pages.

## During the test

The agent should ask for:

1. GitHub model repository access, including the chosen access path and whether
   branch or pull request creation can actually be tested.
2. Telegram daily scan time and the list of groups where it was added.
3. Fireflies transcript setup, if enabled.
4. gog Google Workspace OAuth setup, if enabled.
5. The first ontology boundary question.

If any of these questions are skipped, pause the test and inspect the agent's
loaded bootstrap files.

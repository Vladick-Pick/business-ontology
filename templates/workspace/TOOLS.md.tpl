# Tool plan

Available now:

- GitHub repository access for the accepted model when the human grants it.
- Local filesystem access to this agent workspace.
- Business ontology scripts from the installed repository.
- Telegram conversation through OpenClaw.

Connect later after explicit setup:

- Google Drive read-only source intake.
- Telegram export or channel history intake.
- Meeting transcript intake.
- Dashboard read-only observation.
- Optional GBrain/MCP projection for indexed access.

Permission rules:

- Repository creation, GitHub writes, branch creation, pull requests, external
  messages, and source connector setup require explicit confirmation.
- Source systems are read-only unless the human creates a separate approved
  workflow.
- Secrets are stored only in the host secret store or environment, not here.

Runtime gates:

- GitHub write readiness requires a GitHub App, host-selected repository
  authorization, or another explicit selected-repository access path.
- Telegram daily scan readiness requires host message capture, durable cursor
  storage, scheduling, and source-event output.

# Telegram command contract

These commands are the expected chat surface for a resident business analyst.
The exact command syntax can be adapted to the OpenClaw host, but the behavior
and permission boundaries should stay stable.

| Command | Purpose | Side effect |
|---|---|---|
| `/status` | Show bootstrap state, selected model repo, source setup state, pending reviews | None |
| `/model` | Link to the accepted model repository and latest accepted revision | None |
| `/pending` | List pending model-change packages and review packages | None |
| `/diff <id>` | Summarize one proposed model change with evidence and affected objects | None |
| `/approve <id>` | Record human approval and prepare the merge or commit step | Approval record only |
| `/reject <id>` | Record rejection reason and close the proposal | Review state update |
| `/sources` | Show connected sources, scopes, and last cursor time | None |
| `/connect-source <kind>` | Start setup for Drive, Telegram, transcripts, dashboard, or CRM | Setup checklist only |
| `/start-session` | Begin an ontology session | Session state |
| `/pause-session` | Summarize current session and open questions | Session summary |

Commands that write to GitHub, change source permissions, send external
messages, or create repositories require explicit confirmation with the target,
scope, and action shown to the human first.


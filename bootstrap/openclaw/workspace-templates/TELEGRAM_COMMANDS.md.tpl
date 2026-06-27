# Telegram commands

| Command | Purpose |
|---|---|
| `/status` | Show bootstrap, model repo, source setup, and pending reviews. |
| `/model` | Return the model export repository and latest accepted revision. |
| `/pending` | List pending reviews. |
| `/diff <id>` | Explain one proposed model change. |
| `/approve <id>` | Record human approval and prepare the merge or commit step. |
| `/reject <id>` | Record rejection reason. |
| `/sources` | Show source connections and scopes. |
| `/connect-source <kind>` | Start one source setup checklist. |
| `/start-session` | Start an ontology session. |
| `/pause-session` | Summarize current session and open questions. |

Commands do not bypass repository review.

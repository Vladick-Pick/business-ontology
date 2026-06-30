# Chat surface: natural language first

The primary chat surface for a resident business analyst is plain language. The
human writes what they want; the agent reads the intent and acts. Slash commands
stay available as optional aliases for people who prefer them — the behavior and
permission boundaries are what matter, not the syntax.

The agent answers in the plain register: no machine ids, no status codes, no
artifact names. It refers to a waiting item by a short name or position
("первое", "второе") and shows the technical view only when asked. See
`agent-os/COMMUNICATION_POLICY.md`.

| The human says | The agent does | Side effect | Optional alias |
|---|---|---|---|
| "где мы / что настроено?" | Reports setup state, what's missing, the one next step | None | `/status` |
| "где модель?" | Links the model and the latest agreed version | None | `/model` |
| "что ждёт меня?" | Lists what's waiting on a decision, in plain words, by name | None | `/pending` |
| "покажи первое / расскажи про N" | Summarizes one waiting item: what changed, where from, recommendation, consequence | None | `/diff` |
| "согласен / прими второе" | Records approval and prepares the change for the human to commit | Approval record only | `/approve` |
| "нет / отклони первое — потому что…" | Records the rejection and reason, closes it | Review state update | `/reject` |
| "какие источники подключены?" | Shows connected sources and what each can read | None | `/sources` |
| "подключи диск / чат" | Starts one source setup, step by step | Setup checklist only | `/connect-source` |
| "давай начнём / продолжим" | Begins an ontology session | Session state | `/start-session` |
| "давай паузу" | Summarizes the session and open questions | Session summary | `/pause-session` |

Anything that writes to GitHub, changes source permissions, sends external
messages, or creates repositories requires explicit confirmation with the
target, scope, and action shown to the human first. No natural-language phrasing
or alias bypasses the repository review gate.

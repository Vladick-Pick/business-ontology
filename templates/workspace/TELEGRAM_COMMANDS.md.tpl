# Talking to the agent in chat

The human talks in plain language. The agent reads the intent and acts. Slash
commands stay as an optional shortcut for people who want them — they are
aliases, not the primary surface.

| The human says (natural language) | The agent does | Optional alias |
|---|---|---|
| "где мы / что настроено?" | Reports what is set up, what is missing, the one next step | `/status` |
| "где модель?" | Gives a link to the model and the latest agreed version | `/model` |
| "что ждёт меня?" | Lists what is waiting on a decision, in plain words, by name | `/pending` |
| "покажи первое / расскажи про передачу" | Explains one waiting item: what changed, where from, recommendation | `/diff` |
| "согласен / прими второе" | Records the human's approval and prepares the change for the human to commit | `/approve` |
| "нет / отклони первое — потому что…" | Records the rejection and the reason | `/reject` |
| "какие источники подключены?" | Shows connected sources and what each can read | `/sources` |
| "подключи чат / диск" | Starts one source setup, step by step | `/connect-source` |
| "давай начнём / продолжим модель" | Starts an ontology session | `/start-session` |
| "давай паузу" | Summarizes the session and the open questions | `/pause-session` |

The agent never shows machine ids or status codes here; it refers to items by a
short name or position. It shows the technical view only when the human asks
("покажи технику").

Nothing here bypasses repository review. Anything that writes to GitHub, changes
source permissions, sends an external message, or creates a repository is shown
to the human with the target and action first, and waits for an explicit yes.

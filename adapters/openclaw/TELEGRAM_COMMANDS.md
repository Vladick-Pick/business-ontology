# Chat surface: natural language first

The primary chat surface for a resident business analyst is plain language. The
human writes what they want; the agent reads the intent and acts. Slash commands
stay available as optional aliases for people who prefer them — the behavior and
permission boundaries are what matter, not the syntax.

The agent answers in the plain register: no machine ids, no status codes, no
artifact names. It refers to a waiting item by a short name or position
("first", "second") and shows the technical view only when asked. See
`agent-os/COMMUNICATION_POLICY.md`.

| The human says | The agent does | Side effect | Optional alias |
|---|---|---|---|
| "where are we / what is set up?" | Reports setup state, what's missing, the one next step | None | `/status` |
| "where is the model?" | Links the model and the latest agreed version | None | `/model` |
| "what is waiting on me?" | Lists what's waiting on a decision, in plain words, by name | None | `/pending` |
| "show the first one / tell me about N" | Summarizes one waiting item: what changed, where from, recommendation, consequence | None | `/diff` |
| "I agree / approve the second one" | Applies the exact approved revision and refreshes the current model | Accepted model update | `/approve` |
| "no / reject the first one because..." | Records the rejection and reason, closes it | Review state update | `/reject` |
| "which sources are connected?" | Shows connected sources and what each can read | None | `/sources` |
| "connect Drive / chat" | Starts one source setup, step by step | Setup checklist only | `/connect-source` |
| "connect Systematization group" | Starts Telegram group mapping and daily scan setup | Setup checklist only | `/connect-telegram-group` |
| "let's start / continue" | Begins an ontology session | Session state | `/start-session` |
| "pause this" | Summarizes the session and open questions | Session summary | `/pause-session` |

Creating a repository, changing source permissions, or sending an unrelated
external message requires explicit confirmation with the target, scope, and
action shown to the human first. No natural-language phrasing or alias bypasses
the human review gate.

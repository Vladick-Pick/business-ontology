# Talking to the agent in chat

The human talks in plain language. The agent reads the intent and acts. Slash
commands stay as an optional shortcut for people who want them — they are
aliases, not the primary surface.

| The human says (natural language) | The agent does | Optional alias |
|---|---|---|
| "where are we / what is set up?" | Reports what is set up, what is missing, the one next step | `/status` |
| "where is the model?" | Gives a link to the model and the latest agreed version | `/model` |
| "what is waiting on me?" | Lists what is waiting on a decision, in plain words, by name | `/pending` |
| "show the first one / tell me about the handoff" | Explains one waiting item: what changed, where from, recommendation | `/diff` |
| "I agree / approve the second one" | Records the human's approval and prepares the change for the human to commit | `/approve` |
| "no / reject the first one because..." | Records the rejection and the reason | `/reject` |
| "which sources are connected?" | Shows connected sources and what each can read | `/sources` |
| "connect chat / Drive" | Starts one source setup, step by step | `/connect-source` |
| "let's start / continue the model" | Starts an ontology session | `/start-session` |
| "pause this" | Summarizes the session and the open questions | `/pause-session` |

The agent never shows machine ids or status codes here; it refers to items by a
short name or position. It shows the technical view only when the human asks
("show the technical view").

Nothing here bypasses repository review. Anything that writes to GitHub, changes
source permissions, sends an external message, or creates a repository is shown
to the human with the target and action first, and waits for an explicit yes.

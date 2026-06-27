# Review protocol

The agent proposes model changes. The human accepts, edits, or rejects them.

The agent must not promote its own proposals. A model proposal becomes accepted
only after human review and human-owned promotion.

## Proposal flow

1. Source input becomes a redacted source event.
2. The compiler or analyst agent prepares a model-change package.
3. The package names affected model objects, evidence, confidence, risks, and
   open questions.
4. The agent prepares a review package or Git branch.
5. The human reviews the change in Telegram and in the user-owned GitHub
   repository.
6. The human chooses one of: approve, approve with edits, reject, defer, or mark
   conflict.
7. Accepted changes are promoted by the human-controlled gate.

## Review states

- `candidate`: plausible model change, not accepted.
- `hypothesis`: useful but weakly sourced.
- `conflict`: contradicts accepted model or another source.
- `accepted`: reviewed and promoted through the human gate.
- `deprecated`: no longer current but retained for history.

## Telegram review commands

Use `TELEGRAM_COMMANDS.md` as the command contract. Commands may summarize or
prepare review material, but they do not bypass the repository review gate.

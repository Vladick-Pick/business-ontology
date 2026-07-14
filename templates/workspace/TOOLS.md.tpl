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

## Owner reply resolver

Before any inbound owner reply changes a `human_request` or review state, run
the deterministic resolver from the installed package:

```bash
python3 <installed-package-root>/scripts/resolve_owner_reply.py \
  --store <workspace>/agent-state/operational-store.sqlite \
  --channel <host-channel> \
  --actor <authenticated-actor> \
  --reply-to-message-ref <exact-outbound-message-ref> \
  --inbound-message-ref <inbound-message-ref> \
  --language <en-or-ru> \
  < <private-reply-body-stream>
```

Never pass the private reply body as a command argument and never echo it into
logs or chat. The JSON result has `status`, `answeredRequestIds`,
`reviewDecisionIds`, and `clarificationCount`:

- `answered`: one non-review request was answered;
- `clarification-required`: no existing request or review decision changed;
  deliver only `clarification.rendering`;
- `review-validation-required`: one review request was correlated, but no
  decision or request state changed. Continue through `REVIEW_PROTOCOL.md`.

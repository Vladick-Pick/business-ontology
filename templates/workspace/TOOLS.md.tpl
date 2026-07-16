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
- OpenAI Sites and ad-hoc hosting-project creation are unavailable to this
  Resident. The official viewer is generated in this workspace and may use
  only the explicit `viewer_publication` capability in runtime config. A
  Tailscale target uses the package-owned user service and one agent-owned path;
  no separate domain is required. An unavailable public target means text fallback,
  not permission to create one.

Runtime gates:

- GitHub write readiness requires a GitHub App, host-selected repository
  authorization, or another explicit selected-repository access path.
- Telegram daily scan readiness requires host message capture, durable cursor
  storage, scheduling, and source-event output.

## Owner reply resolver

The OpenClaw owner-chat plugin invokes the atomic approval command from its
`before_dispatch` hook. For one exact authorized approval it runs:

```bash
python3 <installed-package-root>/scripts/process_review_reply.py \
  --workspace <workspace> \
  --package-root <installed-package-root> \
  --channel <host-channel> \
  --actor <authenticated-actor> \
  --reply-to-message-ref <exact-outbound-message-ref> \
  --inbound-message-ref <inbound-message-ref> \
  --language <en-or-ru> \
  < <private-reply-body-stream>
```

Do not run a second decision path after `applied-and-published` or
`applied-publication-pending`. The latter means accepted truth is current and
only publication needs retry. Never ask the human to approve that revision
again. An operator repairing an already recorded historical approval uses
`--reconcile-package <package-id>`; this reuses the recorded decision and does
not create a new one.

Review authority is configured only after an explicit owner instruction. Build
the actor/channel/scope policy from authenticated host identifiers and stream it
through stdin so those identifiers do not enter process arguments or stdout:

```bash
python3 <installed-package-root>/scripts/configure_review_authority.py \
  --workspace <workspace> \
  < <private-review-authority-json-stream>
```

The command reports only counts and file mode. Never paste the private policy
into chat, Git, a model artifact, or viewer input.

Before asking a material human question, register it from a private JSON stdin
stream. Leave `messageRef` empty when Telegram has not assigned the outbound id;
the command creates a provisional reference:

```bash
python3 <installed-package-root>/scripts/register_human_request.py \
  --store <workspace>/agent-state/operational-store.sqlite \
  --authority-policy <workspace>/agent-state/review-authority.json \
  < <private-human-request-json-stream>
```

Do not send the question if registration fails.

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
  --authority-policy <workspace>/agent-state/review-authority.json \
  < <private-reply-body-stream>
```

Never pass the private reply body as a command argument and never echo it into
logs or chat. The JSON result has `status`, `answeredRequestIds`,
`reviewDecisionIds`, and `clarificationCount`:

- `answered`: one non-review request was answered;
- `authorization-required`: the question was correlated, but this actor is not
  permitted to review it in this channel;
- `clarification-required`: no existing request or review decision changed;
  deliver only `clarification.rendering`;
- `review-validation-required`: one review request was correlated, but no
  decision or request state changed. Continue through `REVIEW_PROTOCOL.md` for
  rejection, edits, conditions, or another non-atomic action.

If the current Telegram turn is a forward of an agent question, first anchor
that forwarded message without treating it as an answer:

```bash
python3 <installed-package-root>/scripts/resolve_owner_reply.py \
  --store <workspace>/agent-state/operational-store.sqlite \
  --channel <host-channel> \
  --actor <authenticated-actor> \
  --inbound-message-ref <forwarded-message-new-reference> \
  --language <en-or-ru> \
  --authority-policy <workspace>/agent-state/review-authority.json \
  --forwarded-context-only \
  < <private-forwarded-body-stream>
```

`context-anchored` means one open question was linked to this new message
reference; it was not answered. The resolver stores only the reference, never
the forwarded body. A later reply to the forwarded message uses the ordinary
resolver command above.

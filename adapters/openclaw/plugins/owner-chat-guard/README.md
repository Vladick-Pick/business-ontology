# Owner chat guard

This OpenClaw plugin is the final delivery backstop for resident-analyst chat.
It does not read or rewrite model, review, source-event, or trace artifacts.

For configured agent ids it uses the OpenClaw `2026.7.1` typed hooks:

- `before_prompt_build` classifies an explicit technical-view request from the
  authoritative current prompt, retains only a short-lived boolean keyed to the
  run and session, and adds a turn-scoped exact-rendering instruction;
- `before_agent_finalize` requests one bounded rewrite when the natural answer
  contains multiple questions or technical chat markers;
- `message_sending` cancels delivery if the rewritten content still violates
  the policy.

Any owner question must include an explicit recommendation and consequence in
the human's language. An explicit current-turn request for technical details or
ids gets one exact, session-correlated delivery exemption; it is consumed on
the next outbound message and never carries into another turn.

The rewrite budget is `maxAttempts: 1`. A failed rewrite therefore cannot loop;
the delivery hook is the terminal fail-closed boundary.

## Required OpenClaw configuration

Install and explicitly enable the plugin for the resident analyst agent ids.
Because the input and finalization hooks read conversation data and the input
hook adds trusted turn-scoped context, the non-bundled plugin must opt into
conversation access and prompt injection:

```json
{
  "plugins": {
    "allow": ["business-ontology-owner-chat-guard"],
    "entries": {
      "business-ontology-owner-chat-guard": {
        "enabled": true,
        "hooks": {
          "allowConversationAccess": true,
          "allowPromptInjection": true
        },
        "config": {
          "agentIds": ["business-analyst-interlab", "business-analyst"]
        }
      }
    }
  }
}
```

Merge `business-ontology-owner-chat-guard` into the existing `plugins.allow`
array and merge its entry into `plugins.entries`. Never replace the current
allow list or remove entries owned by other plugins.

During `plugins install`, an empty or absent `agentIds` list is a safe no-op.
The workspace migration installs the current package copy first, then writes
the configured agent ids and verifies all three runtime hooks before restart.

The agent filter is mandatory so a shared Gateway does not apply this package's
conversation policy to unrelated agents. Normal outbound deliveries carry a
canonical `agent:<agent-id>:...` session key, which the terminal hook uses for
the same filter.

After installation or config changes, restart the Gateway and verify the loaded
runtime with:

```bash
openclaw plugins inspect business-ontology-owner-chat-guard --runtime --json
```

The plugin being present in this repository is not activation proof. Installed
state, explicit enablement, conversation access, a Gateway restart, and a live
delivery smoke remain deployment work.

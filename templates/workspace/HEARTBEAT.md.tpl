# System heartbeat

This is a silent system-state check. It is not an owner reminder or a digest.

Every heartbeat run MUST:

1. Run the installed package command from this workspace:

   ```bash
   python3 "${HOME}/.openclaw/agents/{{AGENT_ID}}/agent/package/current/scripts/system_heartbeat.py" \
     --workspace . \
     --agent-id {{AGENT_ID}}
   ```

2. Confirm that `agent-state/system-health.json` was atomically refreshed.
3. Return `HEARTBEAT_OK` and nothing else.

Never send a message, call a channel tool, answer an open request, or turn this
check into an owner-facing summary. OpenClaw delivery for this heartbeat is
fixed at `target=none` with `directPolicy=block`.

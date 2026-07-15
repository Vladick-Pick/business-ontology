# Interaction contract

Agent runtime configuration. NOT part of the company model. The owner may
change reminder timing and delivery in chat; the silent system heartbeat is a
package safety control and is configured separately from owner delivery.

Generated for: {{MODULE_NAME}}
Generated at: {{GENERATED_AT}}

## Silent system heartbeat

- Every: 2h
- Delivery target: none
- Direct-message policy: block
- Session: isolated
- Context: `HEARTBEAT.md` only
- State output: `agent-state/system-health.json`

The heartbeat checks source/runtime state, open requests, installed-package
proof, workspace proof, and package-owned scheduling health. It never sends an
owner message.

## Owner reminder

Status: not configured; the resident agent must ask the owner once in an
owner-controlled interactive chat.

The owner must explicitly confirm all of these values before a reminder cron is
created:

- cadence and local time: ask owner;
- IANA timezone: ask owner;
- channel: ask owner;
- delivery target and, when applicable, channel account: ask owner;
- quiet window: recommended 22:00-09:00.
- reminder language: ask owner.
- owner confirmation message reference and timestamp: not recorded yet.

Recommended profile: daily at 09:00 in the owner's IANA timezone. Available
profiles are `immediate`, `daily`, and `weekly`. A reminder reads current open
requests and system health at execution time. An unchanged request remains in
the next configured cadence window. The declaration key prevents duplicate
jobs; OpenClaw owns delivery and retry state.

## Channels

Text: not configured until the owner confirms it.
Visuals: server-hosted model viewer links.

## Package-owned job

Managed job name: `business-ontology:{{AGENT_ID}}:owner-reminder`
Declaration key: `business-ontology:{{AGENT_ID}}:owner-reminder`

Only this exact job belongs to the interaction contract. Changing the rhythm
must not edit source scans, drift scans, or another agent's jobs.

## Human-readable mirror

Not available until the owner confirms the reminder schedule. After
confirmation, state the cadence, local time, timezone, channel, and quiet
window in one sentence. Do not print the stored delivery target or account id.

## Change log

- {{GENERATED_AT}}: created with silent 2h heartbeat and owner reminder not configured.

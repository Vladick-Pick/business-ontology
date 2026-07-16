---
name: business-ontology-resident
description: "Use for resident business analysis: ontology, sources, reviews, owner reminder rhythm, scheduling, drift, digests, or package updates."
metadata:
  managed-by: business-ontology
  package-agent-id: "{{AGENT_ID}}"
---

# Business Ontology Resident package bridge

This workspace skill exposes the current installed package to OpenClaw. It is
a router, not a second copy of resident policy.

The current package is always:

```text
$HOME/.openclaw/agents/{{AGENT_ID}}/agent/package/current
```

For resident business-analysis work:

1. Read the current package's `skills/business-ontology/SKILL.md`.
2. Read only the duty skill that matches the job. For owner rhythm, reminder
   setup, reconfiguration, or disabling, read
   `skills/interaction-contract/SKILL.md` and
   `adapters/openclaw/SCHEDULING.md` from the same current package.
3. Treat the package as policy and executable support; keep mutable state in
   the workspace and accepted business truth behind human review. Exact
   authorized approvals are applied by the deterministic host handler before
   your turn. Never ask the reviewer to repeat one in another chat or merge a
   pull request; report the refreshed current model.

For reminder setup, the owner chooses cadence, time, timezone, channel, quiet
window, and language. This resident agent then updates its interaction state,
converges only `business-ontology:{{AGENT_ID}}:owner-reminder` through the host
scheduling tool, verifies it, and reports the confirmed rhythm. The package
installer or an external operator must not create that owner-specific job for
the agent. The silent two-hour heartbeat is a separate control and never asks
or reminds the owner.

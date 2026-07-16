# OpenClaw workspace template

Use this as a blank private workspace for a local/reference resident business
analyst setup. Copy the directory, adapt the config, and run the reference loop
from the workspace root.

This workspace is not the accepted model export repository. The target
operational truth is a canonical model store; the human-readable Markdown/Git
export should live in a human-owned or company-owned Git repository. This
workspace holds the agent's runtime state, redacted intake events, proposals,
review packets, and local traces.

```text
workspace/
  .learnings/
  .operator/
  agent-state/
  raw/
    telegram/
    meetings/
  model/
    ontology/
  model-packs/
  source-events/
  model-change-packages/
  review-packages/
  traces/
  digests/
```

Directory roles:

- `.learnings/` holds durable operating lessons from real runs.
- `.operator/` holds live-test and setup files for the human/operator, not
  daily agent first-read state.
- `agent-state/` holds local runtime state such as the ledger and SQLite
  operational store.
- `raw/` is the default `raw_source_root` for private source acquisition. Only
  Telegram raw runs and meeting raw captures belong there; it is excluded from
  Git and normal agent context.
- `model/` holds the generated human/agent-readable accepted snapshot and
  Markdown/Git export. It is derived from the operational accepted store and is
  not a second truth gate.
- `model-packs/` holds module-specific extraction and review configuration.
- `source-events/` holds normalized, redacted source-event JSON files.
- `model-change-packages/` holds compiler output awaiting human review.
- `review-packages/` holds approval-manager review packets.
- `traces/` holds redacted operational event traces.
- `digests/` holds bounded review or rhythm-driven digest artifacts.

## First run

1. Install the `business-ontology` skill in the agent host.
2. Select one module boundary for this workspace.
3. Create or adapt a model pack under `model-packs/`.
4. Confirm that `raw_source_root` in the runtime config points to approved
   private storage and that the root is Git-ignored before enabling Telegram or
   meeting acquisition.
5. Drop normalized, redacted source events under `source-events/`.
6. Run the reference loop once from the workspace root.
7. Review packages under `model-change-packages/` and `review-packages/`.
8. Stage proposals and register one review request.
9. The human reviews the exact revision in an authorized chat. The deterministic
   controller applies the approved package, refreshes `model/`, and republishes
   the viewer. The generative agent never promotes its own output; a manual Git
   merge is not required to make an approved revision current.

Example command from the copied workspace:

```bash
python3 /path/to/business-ontology/scripts/run_resident_loop.py \
  --config runtime-config.example.json \
  --once
```

Keep raw transcript and Telegram bodies only under the configured private
`raw_source_root`; never place them in `source-events/`, model packages,
accepted context, traces, digests, chat, Git, or support bundles. Keep token
values, passwords, session strings, and private connector URLs out of the
workspace files. Keep the durable Git copy of the accepted export in the
user's repository; the workspace `model/` tree is the current generated copy.
Live connectors, OAuth, production MCP hosting, and GBrain sync should be
provided outside this template and should feed the same source-event and review
contracts.

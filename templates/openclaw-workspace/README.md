# OpenClaw workspace template

Use this as a blank private workspace for a local/reference resident business
analyst setup. Copy the directory, adapt the config, and run the reference loop
from the workspace root.

This workspace is not the accepted model repository. The accepted model should
live in a human-owned or company-owned git repository. This workspace holds the
agent's runtime state, redacted intake events, proposals, review packets, and
local traces.

```text
workspace/
  ontology/
  model-packs/
  source-events/
  model-change-packages/
  review-packages/
  traces/
  digests/
```

Directory roles:

- `ontology/` holds read-only accepted-context projections or snapshots. It is
  not canonical accepted truth.
- `model-packs/` holds module-specific extraction and review configuration.
- `source-events/` holds normalized, redacted source-event JSON files.
- `model-change-packages/` holds compiler output awaiting human review.
- `review-packages/` holds approval-manager review packets.
- `traces/` holds redacted operational event traces.
- `digests/` holds bounded review or weekly digest artifacts.

## First run

1. Install the `business-ontology` skill in the agent host.
2. Select one module boundary for this workspace.
3. Create or adapt a model pack under `model-packs/`.
4. Drop initial documents/exports as source events under `source-events/`.
5. Run the reference loop once from the workspace root.
6. Review packages under `model-change-packages/` and `review-packages/`.
7. Stage proposals only after the required owner review.
8. The human commits accepted ontology; the agent never promotes its own output.

Example command from the copied workspace:

```bash
python3 /path/to/business-ontology/scripts/run_resident_loop.py \
  --config runtime-config.example.json \
  --once
```

Keep this workspace free of raw transcripts, private messages, PII, token
values, passwords, session strings, and private connector URLs. Keep the
accepted model in the user's repository, not here. Live connectors, OAuth,
production MCP hosting, and GBrain sync should be provided outside this template
and should feed the same source-event and review contracts.

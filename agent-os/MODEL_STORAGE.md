# Model storage

The product has four storage zones. They must stay separate.

## Zones

| Zone | Stores | Owner |
|---|---|---|
| Package repository | Agent package, skills, specs, adapters, schemas, scripts, reference runtime. | Package maintainer. |
| Agent workspace | Host instructions, source cursors, setup state, redacted run logs, review queue pointers. | Resident agent/operator. |
| Raw source systems | Telegram, Fireflies, Google Drive, dashboards, repositories, manual uploads. | Source owner. |
| Model repository/store | Accepted model, staged proposals, source map, review decisions, drift, projections. | Human model owner. |

The agent may write to its workspace and proposal areas. It must not write raw
sources into the model repository. It must not write accepted truth without
human review.

## Current repository implementation

This package currently provides:

- Markdown/Git model export and review surface;
- JSON schemas under `schemas/`;
- deterministic validators under `scripts/`;
- a SQLite operational store in `runtime/operational_store.py`;
- a resident loop that uses that store when `store_path` is configured;
- accepted-state subsets for definitions, attributes, criteria,
  examples/non-examples, workflows, participants, steps, transitions,
  exceptions, and workflow metrics.

This is not yet a production canonical model store service.

## Target canonical store

The target operational truth layer stores:

- accepted items;
- definitions;
- attributes;
- criteria;
- examples and non-examples;
- workflows;
- workflow participants;
- workflow steps;
- workflow transitions;
- workflow exceptions;
- workflow metrics;
- decisions;
- review questions;
- human decisions;
- evidence;
- source cursors;
- runs;
- drift and open questions;
- supersession and validity windows.

The Markdown/Git layer remains valuable as readable export, audit, backup, and
portability. It is not the place for raw private source data.

## Write paths

Accepted model state changes only through:

```text
source event
-> model-change package
-> review package
-> human decision
-> accepted state update
-> export/projection update
```

If a host allows the agent to edit files directly, the agent still follows the
review protocol. Capability is not permission.

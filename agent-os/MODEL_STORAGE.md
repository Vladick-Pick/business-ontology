# Model storage

The product has four storage zones. They must stay separate.

## Zones

| Zone | Stores | Owner |
|---|---|---|
| Package repository | Agent package, skills, specs, adapters, schemas, scripts, reference runtime. | Package maintainer. |
| Agent workspace | Host instructions, source cursors, setup state, redacted run logs, review queue pointers, and derived artifacts. | Resident agent/operator. |
| Raw source layer | Telegram, Fireflies, Google Drive, dashboards, repositories, manual uploads, and the configured private filesystem raw cache. | Source owner and deployment operator. |
| Model repository/store | Accepted model, staged proposals, source map, review decisions, drift, projections. | Human model owner. |

The raw source layer has one configured filesystem root when local acquisition
is required:

```text
<raw_source_root>/telegram/<run>/...
<raw_source_root>/meetings/<meeting>/...
```

`raw_source_root` is a logical zone even when the current deployment places it
at `<private-workspace>/raw`. It is not ordinary workspace context. It must be
private, Git-ignored, and excluded from support bundles, model exports, traces,
logs, digests, and chat. The agent may write source acquisition bodies only
there and proposals only to proposal areas. It must not write raw sources into
the accepted model or package repository, and it must not write accepted truth
without human review.

Derived workspace and model artifacts keep locators, `sha256:` hashes,
processing status, counts, and minimal redacted metadata. They do not copy raw
Telegram message bodies or full transcript bodies. Legacy raw paths remain
readable only during a backed-up migration and are not valid targets for new
writes.

## Current repository implementation

This package currently provides:

- Markdown/Git model export and review surface;
- JSON schemas under `schemas/`;
- deterministic validators under `scripts/`;
- a SQLite operational store in `runtime/operational_store.py`;
- a resident loop that uses that store when `store_path` is configured;
- accepted-state subsets for definitions, attributes, criteria,
  examples/non-examples, workflows, participants, steps, transitions,
  exceptions, workflow metrics, and workflow value context.
- read-only projections for canvas, data bindings, accepted instance graph,
  and model health.

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
- value streams, value stages, capabilities, stakeholders, value items,
  business objects, and business-architecture links;
- competency questions;
- decisions;
- human requests;
- human decisions;
- evidence;
- source cursors;
- runs;
- drift and open questions;
- supersession and validity windows.

The Markdown/Git layer remains valuable as readable export, audit, backup, and
portability. It is not the place for raw private source data.

## Model repo support contract

Model repositories may contain support files, but they do not own validation
rules. A supported model repository has:

```text
PACKAGE_CONTRACT.lock
scripts/validate_model_repo.py
```

`PACKAGE_CONTRACT.lock` pins the package name, version, commit, validator path,
and validator contract. `scripts/validate_model_repo.py` is a thin wrapper that
checks the lock and calls the package validator from the installed package. Do
not copy `scripts/links_validate.py` into the model repository; a copied
validator is unsupported because it can drift from the package contract.

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

`modelHealth` is an observation path, not a write path. It can report accepted
counts, candidate/hypothesis/conflict counts, stale audits, owner/source-locator
coverage, unanswered competency questions, ownerless blocked proposals, and
high-risk review WIP against the five-item WIP limit. It cannot promote,
reject, or rewrite model facts.

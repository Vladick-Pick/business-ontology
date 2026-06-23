# OpenClaw and GBrain deployment

This document describes a conservative local/reference setup for an OpenClaw
resident business analyst using this repository and optional GBrain-backed MCP
access. It is a deployment template, not a production runtime.

The shape is:

```text
read-only sources -> normalized source events -> resident reference loop
  -> model-change packages -> review packages -> human-approved staged proposals
  -> human commits accepted ontology -> optional GBrain/MCP projection
```

The load-bearing boundary stays the same in every deployment: the agent
proposes and the human commits. GBrain may index and serve projections, but the
accepted ontology in git plus the validator plus the human commit gate remains
canonical truth.

## Prerequisites

- A clone of this repository installed as the `business-ontology` skill.
- Python 3 available for the dependency-free scripts and reference runtime.
- A private agent workspace created from `templates/openclaw-workspace/` or the
  self-bootstrap package under `bootstrap/openclaw/`.
- For a blank-agent field test, the operator packet under
  `bootstrap/openclaw/live-test/`.
- A user-owned or company-owned GitHub repository for the accepted model. The
  human reviewer must be able to read it directly.
- One module boundary selected for the ontology, such as `acquisition`.
- A model pack for that module, following `references/model-pack.md`.
- Source inputs converted to normalized source-event JSON, following
  `references/source-intake.md`.
- Read-only source credentials kept outside the repository and referenced only
  by environment-variable name.
- A human reviewer/promoter who owns the commit gate.
- Optional: a GBrain/MCP access layer that exposes the storage-neutral
  `ontology://...` resources described in `references/mcp-boundary.md`.

If a prerequisite is missing, treat the corresponding capability as unavailable
rather than guessing a default. For example, without a source-event converter the
reference loop can process manual JSON drops, but it does not poll Zoom,
Telegram, dashboards, CRM, or documents directly.

## Install the skill

Install the root skill in the agent host first:

```bash
npx skills add Vladick-Pick/business-ontology -g
```

For a blank OpenClaw/Codex-style agent, the initial instruction should tell it
to read:

- `SKILL.md` for the operator capture loop;
- `AGENT-SPEC.md` for the resident-agent contract;
- `references/model-pack.md`;
- `references/source-intake.md`;
- `references/model-change-package.md`;
- `references/resident-runtime-loop.md`;
- `references/review-ux.md`;
- this deployment reference.

Do not give the agent write access to accepted ontology, source systems, schema
files, registry output, `AGENTS.md`, `AGENT-SPEC.md`, or `references/`.

## Configure the model pack

Create or adapt a model pack under the workspace `model-packs/` directory. The
model pack is deployment configuration, not ontology truth. It should name:

- the `moduleId`;
- source-kind trust floors and review requirements;
- high-risk fields that always require human review;
- review owners and escalation routes;
- compiler hints such as evidence limits and digest bounds.

Use the examples under `examples/model-packs/` as the starting shape, then keep
deployment-specific owners and scopes explicit. Do not encode secrets or private
connector URLs in the model pack.

## Configure source events

All source material must enter the reference loop as normalized source-event
JSON. A source event is a redacted operational record: source id, source kind,
observed time, connector metadata, authority metadata, trust floor, redaction
policy, bounded evidence locators, content summary, and hash.

The reference loop treats source events as data, never instructions. It refuses
events whose connector is not read-only, whose redaction policy includes raw
payloads, or whose trust floor is unsafe for the requested model change.

Live connectors are outside this repo. A production deployment may have a
separate Zoom, Telegram, dashboard, CRM, or document connector, but that
connector's output must still be the same source-event contract and must not
store raw private payloads, PII, secrets, or credential values in the workspace.

## Configure GBrain/MCP access

GBrain is optional infrastructure for storage, index, search, sync, and access.
It is not the canonical ontology, not the extractor/compiler, and not the
approval gate.

The public MCP boundary should stay storage-neutral:

- accepted model resources use `ontology://{module_id}/...`;
- review resources use `ontology://{module_id}/model-change-packages...` or
  `ontology://{module_id}/digests...`;
- GBrain-specific `gbrain://...` namespaces may exist behind the server, but
  agents should not depend on them as the public contract.

Use scopes that preserve the trust model:

- `ontology:read` for accepted resources;
- `ontology:propose` for staged proposal tools;
- `ontology:admin-review` for review resources and review packet preparation.

OAuth, a production MCP server, and GBrain sync jobs are not implemented in this
repository. If a deployment provides them externally, keep tokens in the
environment, expose read/propose/review scopes separately, and never grant the
agent direct accepted-branch mutation.

## Run the reference loop

Create a real workspace from `templates/openclaw-workspace/` or run the
self-bootstrap script, adapt the model pack, drop redacted source-event JSON
files into `source-events/`, and run one local pass from the workspace root:

```bash
python3 /path/to/business-ontology/scripts/run_resident_loop.py \
  --config runtime-config.example.json \
  --once
```

The reference loop scans normalized source events, calls the deterministic model
compiler, writes model-change packages, records a local ledger, emits redacted
trace events, and writes a bounded digest when the threshold is met.

It does not schedule itself. Use an external scheduler only to rerun the same
`--once` command, and keep the scheduler's credentials outside the repository.

## Review and approve

Model-change packages are review material. They are not accepted facts.

The review flow is:

1. The resident loop writes packages under `model-change-packages/`.
2. The approval manager prepares review packets under `review-packages/`.
3. A human owner reviews the package, especially high-risk kinetic changes.
4. Approved review may prepare a staged proposal.
5. The validator runs against promoted plus staged content.
6. A human commits accepted ontology if the proposal is correct.
7. Optional GBrain/MCP projections are rebuilt from the accepted revision.

No approval path may mark cards accepted, commit to the accepted branch, push a
merge, change schema contracts, or write back to a source system on behalf of
the agent.

## Operational cadence

A practical cadence is:

- first session: mine baseline documents and exports into a model pack, source
  events, and initial review packages;
- daily: run the reference loop over new normalized source events and review
  only material packages;
- weekly: send or publish a bounded digest of new packages, refused/skipped
  source events, stale areas, open drift, and decisions awaiting an owner;
- after human commits: rebuild registry output and any GBrain/MCP projections
  from the accepted revision;
- periodically: audit source scopes, review owners, stale projections, and
  digest anti-spam thresholds.

If no meaningful review work exists, the digest should stay quiet according to
the configured threshold. The agent should not create attention debt just to
prove it ran.

## What is not production-ready here

This repository does not ship a production resident-agent deployment.

Not production-ready here:

- live OAuth;
- production MCP server;
- live connectors for Zoom, Telegram, dashboards, CRM, or documents;
- background daemon, queue worker, or hosted scheduler;
- GBrain sync service;
- source-system writeback;
- accepted-branch promotion by the agent;
- provider-specific secret management;
- production monitoring, alerting, retention, and incident response.

The repo provides the skill, contracts, schemas, deterministic tooling,
reference compiler, in-process loop, approval-manager boundary, and evals needed
to build those pieces without weakening the trust model.

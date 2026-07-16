<div align="center">

# business-ontology

> Resident business analyst package for maintaining a source-backed model of how a company or module works.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Package](https://img.shields.io/badge/Agent-Package-7c3aed)](SKILL.md)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-bootstrap-111827)](adapters/openclaw/BOOTSTRAP.md)
[![Codex](https://img.shields.io/badge/Codex-compatible-111827)](adapters/codex/BOOTSTRAP.md)
[![Claude Code](https://img.shields.io/badge/Claude_Code-compatible-8b5cf6)](adapters/claude-code/BOOTSTRAP.md)

</div>

`business-ontology` packages the instructions, contracts, templates, local
runtime, and checks for a resident analyst agent. The agent reads registered
sources, turns observations into model-change packages, routes them through
human review, and exposes the accepted model as agent-readable context.

Operating loop:

```text
sources -> source events -> model-change packages -> human review
        -> accepted model -> agent-readable context
```

Modeling scope: definitions, attributes, states, workflows, decisions,
authority, source-of-truth rules, drift, and open questions. RDF/OWL modeling,
raw document storage, database-schema design, and generic consulting prompts are
outside this package.

The root `SKILL.md` is a package router. The operating skill lives at
`skills/business-ontology/SKILL.md`.

## Install

For a blank agent, send the repository URL and ask it to read `BOOTSTRAP.md`:

```text
https://github.com/Vladick-Pick/business-ontology

Read BOOTSTRAP.md and follow the adapter for your host.
```

For the OpenClaw experiment, point the agent directly at:

```text
adapters/openclaw/BOOTSTRAP.md
```

The agent should install workspace instructions, identify the model repository,
and ask one concrete setup question with a recommended answer.

## Current Implementation

| Surface | Path | Status |
|---|---|---|
| Package router | `SKILL.md` | implemented |
| Bootstrap | `BOOTSTRAP.md` | implemented |
| Package manifest | `agent-package.yaml` | implemented |
| Primary ontology skill | `skills/business-ontology/SKILL.md` | implemented |
| Duty skills | `skills/*/SKILL.md` | implemented |
| Host adapters | `adapters/` | OpenClaw, Codex, Claude Code docs |
| Product/runtime contracts | `specs/`, `agent-os/`, `references/` | implemented docs |
| Workspace and model templates | `templates/` | implemented |
| JSON schemas | `schemas/` | implemented contracts |
| Validators and CLIs | `scripts/` | implemented local tooling |
| Reference runtime | `runtime/reference_runtime.py` | implemented local harness |
| Resident loop | `runtime/resident_loop.py` | implemented local `--once` loop |
| Operational store | `runtime/operational_store.py` | implemented SQLite store |
| Context projections | `runtime/context_projection.py` | canvas, bindings, instance graph |
| Draft generator | `runtime/draft_generator.py` | reviewable draft ontology packages |
| Telegram MTProto source acquisition | `scripts/tg_mtproto_export.py`, `scripts/tg_run_daily_ingest.py` | local exporter and daily packet wrapper |
| Meeting recording runtime | `runtime/meeting_recording_service.py`, `scripts/meeting_recording_cli.py` | local Skribby create-bot, webhook, and packet capture runtime |
| Source instance and proof registry | `scripts/source_registry.py`, `source-instances.json`, `live-proofs/proofs.json` | workspace state for configured, source-connected, and live-proven source paths |
| Model write-scope verifier | `scripts/assert_model_write_scope.py`, `model-access-policy.json` | proves staged writes work and accepted writes are refused |
| Model repo validation wrapper | `templates/model-repo/PACKAGE_CONTRACT.lock.tpl`, `templates/model-repo/scripts/validate_model_repo.py.tpl` | model repos delegate validation to the pinned package validator |
| Official model viewer publish | `scripts/publish_viewer.py`, `scripts/serve_viewer.py`, `scripts/configure_viewer_publication.py`, `scripts/viewer_reachability.py`, `viewer/`, `VIEWER_PUBLISH_REPORT.json` | validates accepted truth, privacy-checks a separated working layer, verifies an explicit public target, and blocks repeated delivery after an owner-reported reachability failure |
| Meeting transcript skills | `skills/meeting-recorder/SKILL.md`, `skills/meeting-transcript-ingest/SKILL.md` | host-delivered meeting link ordering and packet-to-review interpretation |
| Behavioral evals | `evals/` | fixture suite |

The implemented code validates links, compiles registry projections, runs
fixture evals, compiles model-change packages, processes normalized source
events, persists package review and human request state, stores accepted definitions, attributes,
workflows, data bindings, and redacted instance graphs, renders workflow
diagrams, exposes local MCP-style projections, and generates reviewable draft
ontology packages from redacted source events.

## Runtime Boundaries

The repository contains contracts, bootstrap instructions, templates, and local
reference code. These production capabilities require external deployment work:

| Capability | Required outside this repository |
|---|---|
| OAuth and secret management | host credentials or a secret manager |
| Hosted MCP server | network service wrapper around the runtime boundary |
| Telegram MTProto deployment | Telethon install, user session, secrets, scheduler, chat map, and live proof |
| Meeting recording live proof | public HTTPS route, real Skribby bot joining a meeting, finished webhook, transcript packet, source event, model-change package, and digest/review handoff |
| Fireflies, Google Workspace connectors | live connector implementations and scopes |
| Background scans | scheduler or resident daemon |
| GBrain synchronization | sync service using the accepted projection contract |
| Production canonical model store | deployed store service and migration policy |

For OpenClaw/GBrain wiring, see `references/openclaw-gbrain-deployment.md`.
That file is a reference/local setup template for connector and projection
experiments.

## Repository Layout

```text
business-ontology/
  BOOTSTRAP.md
  agent-package.yaml
  README.md
  AGENTS.md
  CLAUDE.md
  SKILL.md
  specs/
  agent-os/
  skills/
  adapters/
  templates/
  schemas/
  runtime/
  scripts/
  evals/
  deployment/
```

Retired paths stay retired: `agent-skills/`, `bootstrap/openclaw/`, and
`templates/openclaw-workspace/`.

## Model Truth

The model describes current business reality. Plans and regulations enter as
sources; they become accepted model truth after review.

Every material fact should have a stable id, status, source id, owner or
`unknown`, typed links, review cadence, and evidence/decision trail. The agent
may mine and stage. A human accepts.

## Verification

Focused package checks:

```bash
python3 -m unittest tests.test_repo_layout
python3 -m unittest tests.test_agent_skill_registry
python3 -m unittest tests.test_openclaw_self_bootstrap
python3 -m unittest tests.test_openclaw_live_test_readiness
python3 -m unittest tests.test_openclaw_workspace_template
```

Full local baseline:

```bash
python3 -m unittest discover tests
python3 scripts/run_evals.py --fixture-only
python3 scripts/links_validate.py .
python3 scripts/links_validate.py . --staged
python3 -m py_compile runtime/*.py scripts/*.py
```

## Release And Migration

| Topic | File |
|---|---|
| Install | `deployment/INSTALL.md` |
| Update | `deployment/UPDATE.md` |
| Release checklist | `deployment/RELEASE_CHECKLIST.md` |
| Migration policy | `deployment/MIGRATION_POLICY.md` |
| Changelog | `CHANGELOG.md` |

## License

MIT.

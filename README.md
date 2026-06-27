<div align="center">

# business-ontology

> A resident business analyst package for keeping a source-backed model of how a company or module actually works.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Package](https://img.shields.io/badge/Agent-Package-7c3aed)](SKILL.md)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-bootstrap-111827)](adapters/openclaw/BOOTSTRAP.md)
[![Codex](https://img.shields.io/badge/Codex-compatible-111827)](adapters/codex/BOOTSTRAP.md)
[![Claude Code](https://img.shields.io/badge/Claude_Code-compatible-8b5cf6)](adapters/claude-code/BOOTSTRAP.md)

</div>

`business-ontology` is an agent package for a resident business analyst. The
agent mines documents, chats, transcripts, dashboards, and repositories; compares
new observations with the accepted model; stages model-change packages; asks a
human to review them; and keeps the model queryable by agents.

This is not RDF/OWL, not a database schema, not a static wiki, and not a generic
consultant prompt. It is an operating loop:

```text
sources -> source events -> model-change packages -> human review
        -> accepted model -> agent-readable context
```

The root `SKILL.md` is a package router. The operational business ontology skill
lives at:

```text
skills/business-ontology/SKILL.md
```

## Install

For a blank agent, send:

```text
https://github.com/Vladick-Pick/business-ontology

Read BOOTSTRAP.md and follow the adapter for your host.
```

For the OpenClaw experiment, send:

```text
https://github.com/Vladick-Pick/business-ontology

Read and execute:
adapters/openclaw/BOOTSTRAP.md
```

The agent should first install package/workspace instructions, then ask for the
model repository target. It should not ask broad setup questions such as "what
should I do?" It should ask one concrete question with a recommended answer.

## What the agent does

In the first session, the agent mines a baseline model from provided materials:
boundary, purpose, sources, objects, definitions, attributes, states, workflows,
decisions, metrics, drift, and open questions.

After source setup, the agent runs recurring scans:

- Telegram chats where it is added or where exports are provided;
- meeting transcripts for the project scope;
- Google Drive folders selected by the user;
- dashboards or metric exports when metric truth is in scope;
- manual files and repositories provided by the user.

On each run, it extracts decisions, agreements, new objects, changed
definitions, workflow drift, source-of-truth changes, and open questions. It
does not promote its own findings. It stages review material and asks the human
to accept, edit, reject, or defer.

## Current implementation

| Surface | Path | Status |
|---|---|---|
| Package router | `SKILL.md` | implemented |
| Root bootstrap | `BOOTSTRAP.md` | implemented |
| Package manifest | `agent-package.yaml` | implemented |
| Primary ontology skill | `skills/business-ontology/SKILL.md` | implemented |
| Resident duty skills | `skills/*/SKILL.md` | implemented |
| OpenClaw adapter | `adapters/openclaw/` | implemented bootstrap |
| Codex adapter | `adapters/codex/` | implemented docs |
| Claude Code adapter | `adapters/claude-code/` | implemented docs |
| Product/runtime specs | `specs/` | implemented contracts |
| Resident agent OS docs | `agent-os/` | implemented docs |
| Workspace templates | `templates/workspace/` | implemented |
| Model repo templates | `templates/model-repo/` | implemented |
| JSON schemas | `schemas/` | implemented contracts |
| Validators and tools | `scripts/` | implemented local tooling |
| Reference runtime | `runtime/reference_runtime.py` | implemented local harness |
| Resident source-event loop | `runtime/resident_loop.py` | implemented local `--once` loop |
| SQLite operational store | `runtime/operational_store.py` | implemented local store |
| Behavioral evals | `evals/` | synthetic fixtures |

Implemented code can validate links, compile registry projections, run fixture
evals, compile model-change packages, process normalized source events, persist
queue/review state, store accepted definitions/attributes/workflows in SQLite,
and render workflow diagrams.

## Not implemented here

This repository does not ship:

- production OAuth;
- hosted MCP server;
- live Telegram account export connector;
- live Fireflies connector;
- live Google Workspace connector;
- background scheduler or daemon;
- GBrain synchronization;
- production canonical model store service.

Those are deployment/runtime pieces. The repo contains contracts, bootstrap
instructions, templates, and local reference code for them.

For the local OpenClaw/GBrain boundary, see
`references/openclaw-gbrain-deployment.md`. It is a reference/local setup template,
not production deployment, live OAuth, live connectors, or hosted MCP.

## Layout

```text
business-ontology/
  BOOTSTRAP.md
  agent-package.yaml
  README.md
  AGENTS.md
  CLAUDE.md
  SKILL.md                         # package router, not the main ontology skill

  specs/
    BUSINESS-ONTOLOGY-RESIDENT.md
    WORKSPACE-SPEC.md
    UPDATE-SPEC.md
    SOURCE-SPEC.md
    REVIEW-SPEC.md
    SYSTEM-ANALYSIS-SPEC.md

  agent-os/
    README.md
    IDENTITY.md
    OPERATING_LOOP.md
    MODEL_STORAGE.md
    DEFINITIONS_AND_ATTRIBUTES.md
    PROCESSES_AND_WORKFLOWS.md
    SOURCE_INTAKE.md
    MODEL_CHANGE_PROTOCOL.md
    REVIEW_PROTOCOL.md
    COMMUNICATION_POLICY.md
    SECURITY.md
    UPDATE_POLICY.md
    SYSTEM_ANALYSIS.md

  skills/
    README.md
    business-ontology/SKILL.md
    connect-source/SKILL.md
    mine-materials/SKILL.md
    propose-change/SKILL.md
    promote-digest/SKILL.md
    drift-sweep/SKILL.md
    synthesize-digest/SKILL.md
    decide-like-module/SKILL.md
    system-analysis/SKILL.md
    ...

  adapters/
    openclaw/
      BOOTSTRAP.md
      FIRST_MESSAGE.md
      WORKSPACE.md
      source-setup/
      live-test/
    codex/
      BOOTSTRAP.md
      AGENTS.template.md
    claude-code/
      BOOTSTRAP.md
      CLAUDE.template.md

  templates/
    workspace/
    model-repo/

  schemas/
  runtime/
  scripts/
  evals/
  deployment/
```

Do not recreate `agent-skills/`, `bootstrap/openclaw/`, or
`templates/openclaw-workspace/`. Those were retired in the final package layout.

## Model truth

The model describes as-is business reality. Regulations and plans are sources;
they become model truth only when they match reality or when a reviewed gap is
recorded.

Every material fact should have:

- stable opaque id;
- status;
- source id;
- owner or `unknown`;
- links from the closed relation list;
- review date or audit cadence;
- decision/evidence trail when accepted.

Human review is the truth gate. The agent may mine and stage; the human accepts.

## Verification

Run focused package checks:

```bash
python3 -m unittest tests.test_repo_layout
python3 -m unittest tests.test_agent_skill_registry
python3 -m unittest tests.test_openclaw_self_bootstrap
python3 -m unittest tests.test_openclaw_live_test_readiness
python3 -m unittest tests.test_openclaw_workspace_template
```

Run the full local baseline:

```bash
python3 -m unittest discover tests
python3 scripts/run_evals.py --fixture-only
python3 scripts/links_validate.py .
python3 scripts/links_validate.py . --staged
python3 -m py_compile runtime/*.py scripts/*.py
```

## Release and migration

- Install instructions: `deployment/INSTALL.md`
- Update instructions: `deployment/UPDATE.md`
- Release checklist: `deployment/RELEASE_CHECKLIST.md`
- Migration policy: `deployment/MIGRATION_POLICY.md`
- Changelog: `CHANGELOG.md`

## License

MIT.

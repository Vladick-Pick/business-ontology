# Changelog

## 0.4.0 - Final agent-package layout

This release restructures the repository into the package layout used by blank
agents and host adapters.

### What changed

- Moved the operational business ontology skill to
  `skills/business-ontology/SKILL.md`.
- Replaced the root `SKILL.md` with a package router for install, bootstrap,
  update, and adapter routing.
- Moved resident duty skills from `agent-skills/` to `skills/`.
- Moved OpenClaw bootstrap files from `bootstrap/openclaw/` to
  `adapters/openclaw/`.
- Moved workspace templates from OpenClaw-specific folders to
  `templates/workspace/`.
- Added Codex and Claude Code adapters under `adapters/`.
- Added `BOOTSTRAP.md`, `agent-package.yaml`, `CLAUDE.md`, `specs/`,
  full `agent-os/` docs, `templates/model-repo/`, `deployment/`, and
  `schemas/workspace-manifest.schema.json`.
- Added `skills/system-analysis/SKILL.md` to project accepted ontology slices
  into systems-thinking workflows without letting those tools rewrite truth.
- Added `tests/test_repo_layout.py` so retired paths do not return.

### Migration

Retired paths:

```text
agent-skills/
bootstrap/openclaw/
templates/openclaw-workspace/
AGENT-SPEC.md
```

Replacement paths:

```text
skills/
adapters/openclaw/
templates/workspace/
specs/BUSINESS-ONTOLOGY-RESIDENT.md
```

Installed agents should update path references, keep existing workspace state
and source cursors, and rerun layout/bootstrap verification. Do not keep
duplicate compatibility directories in the package; they make blank agents pick
the wrong instruction set.

## 0.3.0 - Resident foundation and canonical store architecture

This release turns `business-ontology` from a Markdown-first agent skill into a
resident-agent foundation with a documented canonical store target, a local
reference runtime, a blank-agent OpenClaw bootstrap package, and regression
tests around the new boundaries.

### What changed

- Added the OpenClaw self-bootstrap package for a blank Telegram-connected
  agent: `adapters/openclaw/BOOTSTRAP.md`, live-test instructions, source setup
  prompts, workspace templates, and `scripts/bootstrap_openclaw_workspace.py`.
- Added product-level resident-agent docs: `docs/product-target-state.md`,
  `docs/product-resident-analyst.md`, and `docs/openclaw-live-experiment.md`.
- Added the canonical model store contract:
  `references/canonical-model-store.md` and
  `schemas/canonical-model-store.schema.json`.
- Added a dependency-free SQLite operational store in
  `runtime/operational_store.py`.
- Wired the resident loop to persist queue/review state when `store_path` is
  configured.
- Added accepted-state subsets for definitions, attributes, criteria,
  examples/non-examples, workflows, participants, steps, transitions,
  exceptions, and workflow metrics.
- Added `agent-os/DEFINITIONS_AND_ATTRIBUTES.md` and
  `agent-os/PROCESSES_AND_WORKFLOWS.md` so resident agents capture semantic
  boundaries and workflows as structured model records.
- Added `scripts/render_workflow.py` for read-only Mermaid/Markdown workflow
  rendering from the SQLite store.
- Reframed MCP and GBrain as access/index/projection layers over accepted
  model state and review resources, not as truth gates.
- Cleaned generated OpenClaw workspaces: resident-agent files stay in the root;
  operator/live-test files move under `.operator`; learned experiment notes
  live under `.learnings`.
- Aligned source-kind vocabulary around connector-neutral kinds such as
  `meeting-transcript`.
- Added evals for canonical-store truth, pending-review separation, conflict
  supersession, clean OpenClaw roots, source-kind vocabulary, and bounded review
  queues with 100+ packages.

### Why this shape

- Canonical store first, because Markdown/Git alone cannot safely hold hundreds
  of source cursors, review packages, open questions, supersession links, and
  decision records.
- SQLite first, not Postgres, because one resident agent and one module need a
  local, inspectable store before production deployment work.
- Markdown/Git remains as export, review surface, audit trail, backup, and
  portability layer. It is not removed; it is demoted from runtime database to
  readable projection.
- Human review remains the truth gate. Source events and model-change packages
  can propose changes, but accepted truth changes only after approval.
- MCP/GBrain are projections, not semantic compilers or approval systems. This
  keeps access infrastructure separate from the truth model.
- OpenClaw bootstrap is explicit about missing production connectors. The repo
  can prepare a blank agent workspace and run local source-event processing; it
  does not claim OAuth, live Telegram polling, Fireflies retrieval, Google
  Workspace sync, hosted MCP, or GBrain sync are done.

### Commit map

- `3209678` - clean public metadata and repository copy.
- `9c60137` - add the OpenClaw self-bootstrap package.
- `63f5702` - document the live OpenClaw experiment.
- `e70eca2` - add the canonical store runtime, schema, workflow renderer, and
  architecture evals.
- `ebae4f6` - harden generated OpenClaw workspaces and source setup templates.
- `b618c7e` - align docs, product architecture, canonical store language,
  workflow/definition agent OS files, and MCP/GBrain boundaries.

### Verification baseline

Run these before publishing or tagging this release:

```bash
python3 -m unittest discover -s tests
python3 scripts/run_evals.py --fixture-only
python3 scripts/links_validate.py .
python3 scripts/links_validate.py . --staged
git diff --check
python3 -m py_compile runtime/*.py scripts/*.py
```

### Known limits

- No production hosted resident agent.
- No production OAuth or secret-management flow.
- No live Telegram daily scanner proven end to end.
- No Fireflies transcript retrieval proven end to end.
- No Google Workspace connector proven end to end.
- No hosted network MCP server.
- No production GBrain sync.
- No real production run set beyond the documented OpenClaw experiment and
  synthetic eval fixtures.

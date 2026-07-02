# Changelog

## 0.8.0 - Data model v2, position hardening, honest history

This release closes out the v2 data-model contract, hardens the resident
agent's operator-mode position against prompt-injection-style pressure, makes
store history honest (supersession instead of overwrite), and ships a working
whiteboard viewer. It is the first release where the `process` card type has
a worked example anywhere in the repo.

### What changed

- Added data model v2: 11 closed card types (business, production-system,
  role, artifact, tool, metric, state, process, interface, decision, term)
  with per-type closed `attrs` contracts, replacing v1's 7 types plus a
  free-text `attrs.subtype` on `concept`. `module` and `concept` remain
  valid for one transitional version as deprecated type aliases (see
  `docs/specs/2026-07-02-data-model-v2.md`).
- Extended the closed relation list from 9 to 10: `lifecycle` replaces
  `in-state` (alias kept one version), and `influences` (systems-dynamics
  causal claims, polarity + optional delay via a parallel
  `attrs.influences` block, evidence required) is new.
- Added an interface contract grade, `handoff` or `contract`, with qualities,
  SLAs (with breach effects), and acceptance criteria, plus structured
  in-card blocks for transitions, reason codes, steps, stages, qualities,
  SLAs, and acceptance.
- Added new common optional card fields: `aliases`, `evidence`, `volatility`.
- Added `scripts/migrate_taxonomy_v2.py`, a mechanical v1-to-v2 frontmatter
  rewriter (dry-run supported, idempotent, never changes card ids).
- Added `examples/business-attraction-v2/`, the first worked example of
  the `process` type anywhere in the repo, and a full worked example of
  all 11 v2 types plus an authored `influences` pair.
- Updated `schemas/card.schema.json`, `schemas/model-change-package.schema.json`,
  `schemas/model-pack.schema.json`, `references/templates.md`,
  `references/ai-ready.md`, `references/registry-spec.md`, and
  `references/structure.md` to match. `examples/acquisition-ontology/`
  (v1) is unchanged and still validates at 0 errors via the aliases.
- Added the operator-mode grant protocol: an explicit definition of what
  counts as a grant ("What counts as explicit"), the rule that source text
  can never grant the mode, and the `trace_operator_grant_before_direct_write`
  trace check that enforces it.
- Added five position evals covering pressure-accept-escalation,
  consultant-bait, mode-flip-injection, trivial-source-noop, and
  long-session-discipline, plus a Position recovery section and a
  daily-loop Re-anchor step so the agent can re-establish its position after
  drift.
- Added a per-round validation trace check,
  `trace_validation_precedes_each_proposal_ready`.
- Replaced silent overwrite in the operational store with honest
  supersession: a `version_id` surrogate key, close-and-link instead of
  UPSERT, `get_item_history`/`get_workflow_history` for the full record, and
  idempotent re-recording of identical state. Child-table foreign keys are
  now enforced by the application layer instead of the database, because
  SQLite cannot target a `UNIQUE` constraint with a foreign key once rows are
  versioned (documented at the point of change).
- Added stale package detection: `_package_summary` computes staleness
  against the current model revision, and `apply` refuses stale packages
  unless `allow_stale` is set.
- Added a whiteboard-style diagram renderer (containers, decision diamonds,
  hexagons, sticky notes), a funnel dashboard with a live overlay clearly
  labeled as readings rather than model state, generated tables, ghost nodes
  for dangling links, and card statuses with a legend on diagrams.
- Removed the dead Mermaid rendering path from the viewer, dropping a 2.8 MB
  CDN dependency.

## 0.7.0 - Plain human chat register

This release tunes how the resident agent talks to people. The agent now speaks
in a plain "colleague" register in chat — no machine ids, schema field names,
status codes, artifact names, file/tool names, or slash-command syntax — while
keeping full technicality in the artifacts (model-change packages, review
packages, cards, traces), which remain the contract and audit trail.

### What changed

- Added a "Conversation register" section to `agent-os/COMMUNICATION_POLICY.md`:
  the two registers (chat vs artifacts), a forbidden-in-chat list, a
  deterministic glossary (machine term → plain words), reference-by-position,
  the technical-view-on-request escape hatch, and the honesty invariants the
  plain register must not erase.
- Rewrote the human-facing surfaces to the plain register: the readiness
  message (`adapters/openclaw/BOOTSTRAP.md`), the review/decision message and
  plain state words (`adapters/openclaw/REVIEW_PROTOCOL.md`), the chat surface as
  natural-language intents with optional slash aliases
  (`adapters/openclaw/TELEGRAM_COMMANDS.md`), and the workspace templates
  (`SOUL.md.tpl`, `COMMUNICATION_POLICY.md.tpl`, `REVIEW_PROTOCOL.md.tpl`,
  `TELEGRAM_COMMANDS.md.tpl`, `HUMAN_README.md.tpl`). Added a chat-rendering note
  to `skills/synthesize-digest/SKILL.md`.
- Added `scripts/chat_register_lint.py` and `tests/test_chat_register.py`: the
  linter scans Markdown fenced blocks tagged as `chat` and fails on leaked
  machine markers, so the register is enforced, not just documented.
- No change to the card contract, schemas, the nine relations, statuses, the
  artifact shapes, the trust floor, or the human review gate.

## 0.6.0 - Trust contracts and systems-analysis guardrails

This release strengthens the resident analyst loop around source-backed review,
model health, and systems-thinking outputs. It keeps accepted truth behind the
human review gate and makes source risk, evidence quality, and review impact
explicit in package artifacts.

### What changed

- Added source-event, model-change, and review-package contract fields for
  claim kind, evidence grade, source risk, provenance, source adequacy, review
  evidence mode, SLA band, and decision impact.
- Added source-event validation and compiler checks so `unknown` and
  `no-known-risk` source risks cannot be mixed with classified risks.
- Added system-analysis projection/result schemas and a bounded return path for
  systems-thinking outputs: recommendation, experiment, model-change
  candidate, drift item, decision candidate, or no-op.
- Added readiness gates for system-analysis skills so missing inputs are
  returned as missing fields instead of being invented by the agent.
- Added model-health projection and schema for accepted/candidate/hypothesis
  counts, stale review cadence, review WIP, conflicts, ownership, source
  locator coverage, and unanswered competency questions.
- Added methodology regression fixtures covering competency questions, value
  architecture, review evidence, bounded projections, readiness gates, return
  path classification, and model-health risk signals.
- Added a value-stream/capability pilot in the example model pack and updated
  docs for source intake, review, model storage, and system analysis.
- Hardened reference runtime and approval flows around staged proposals,
  source-event traceability, review packages, and admin-review boundaries.

### Verification baseline

Run before publishing or tagging this release:

```bash
python3 -m unittest tests.test_repo_layout tests.test_agent_skill_registry tests.test_openclaw_self_bootstrap tests.test_openclaw_live_test_readiness tests.test_openclaw_workspace_template
python3 -m unittest discover tests
python3 scripts/run_evals.py --fixture-only
python3 scripts/links_validate.py .
python3 scripts/links_validate.py . --staged
python3 -m py_compile runtime/*.py scripts/*.py
git diff --check
```

### Known limits

- No production OAuth, hosted MCP server, live source connectors, background
  scheduler, GBrain sync, or production canonical model store service are
  shipped in this package release.
- The reference runtime remains local package code; production deployment still
  requires host-specific service work.

## 0.5.0 - Context projections and draft ontology runtime

This release adds the local runtime layer that exposes accepted ontology context
as graph-shaped resources and prepares reviewable draft ontology packages from
redacted source events.

### What changed

- Added store-backed configuration canvas projection in
  `runtime/context_projection.py`.
- Added accepted data-binding records and projections so model items can point
  to source locators and fields without storing raw source rows.
- Added accepted instance graph records and a bounded instance-graph projection.
- Added `runtime/draft_generator.py` and
  `scripts/generate_draft_ontology.py` for reviewable draft ontology packages.
- Added local runtime resources:
  `ontology://{module_id}/model/canvas`,
  `ontology://{module_id}/model/bindings`, and
  `ontology://{module_id}/model/instance-graph`.
- Added the `generate_draft_ontology` runtime tool under
  `ontology:admin-review`.
- Hardened projections so read-only store resources do not create missing
  SQLite files, raw source-event fields are refused, raw/private attributes are
  stripped, and canvas edges only point to emitted nodes.
- Updated `README.md`, `agent-package.yaml`, and root `SKILL.md` to describe
  the current package boundary.

### Verification baseline

Run before publishing or tagging this release:

```bash
python3 -m unittest discover tests
python3 scripts/run_evals.py --fixture-only
python3 scripts/links_validate.py .
python3 scripts/links_validate.py . --staged
python3 -m py_compile runtime/*.py scripts/*.py
git diff --check
```

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

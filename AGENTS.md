# Repository instructions

This repository is a business-ontology toolkit: an operating Agent Skill plus a normative agent spec and an agent-skill library, used to stand up and keep alive a queryable model of how a business module really works. Everything in this repo is in English.

## Scope

- Keep `SKILL.md` (the operating session skill) focused on core behaviour and workflow.
- Keep detailed structures, templates, the link contract, and the registry contract in `references/`.
- Keep behavioural eval material in `evals/`.
- `AGENT-SPEC.md` is the normative (RFC-2119) contract for the runtime agent; `agent-skills/` are internal reference duty skills for that resident-agent spec, not separately packaged runtime installs; `staged/` is where the agent proposes changes for human review and current Markdown/Git export promotion.
- Executable assets are dependency-free deterministic tooling under `scripts/` plus the in-process reference harness under `runtime/`. The reference harness proves the staged proposal, permission, validation, and trace contracts locally; it is not a production resident agent, OAuth deployment, or networked MCP server.
- Registry output is derived from accepted cards by `scripts/build_registry.py`; do not hand-edit generated registry JSON.
- `plans/` is local advisor history and must not be published. Keep implementation plans outside the tracked repo or under an ignored local path.

## Current OpenClaw experiment

The active product experiment is documented in `docs/openclaw-live-experiment.md`.
It tests whether a blank Telegram-connected OpenClaw agent can receive
`https://github.com/Vladick-Pick/business-ontology`, read
`bootstrap/openclaw/BOOTSTRAP.md`, create its private workspace, ask for GitHub
model export repository access, set up Telegram/Fireflies/gog source intake
questions, and reach `Ready for the first ontology session`.

Treat this as a live bootstrap experiment, not a production connector claim.
The repository has the bootstrap package, workspace generator, live-test packet,
source setup contracts, tests, evals, and validation tooling. It does not yet
ship production OAuth, background scheduling, live OpenClaw source connectors,
networked MCP hosting, GBrain sync, or real captured production runs.
It ships the canonical model store contract and a SQLite operational store for
queue/review state. The resident loop uses that store when `store_path` is
configured. The store also has the first accepted-state semantic subset:
accepted items, definitions, attributes, criteria, examples/non-examples,
workflows, participants, steps, transitions, exceptions, and workflow metrics.
It is not a full production canonical model store; the current Markdown/Git
repository remains the export and review surface.

Primary source files for the experiment:

- `docs/product-target-state.md`
- `docs/openclaw-live-experiment.md`
- `docs/product-resident-analyst.md`
- `agent-os/DEFINITIONS_AND_ATTRIBUTES.md`
- `agent-os/PROCESSES_AND_WORKFLOWS.md`
- `bootstrap/openclaw/README.md`
- `bootstrap/openclaw/BOOTSTRAP.md`
- `bootstrap/openclaw/live-test/LIVE_TEST_FIRST_MESSAGE.md`
- `bootstrap/openclaw/live-test/PASS_FAIL_GATES.md`
- `bootstrap/openclaw/source-setup/telegram.md`
- `bootstrap/openclaw/source-setup/fireflies.md`
- `bootstrap/openclaw/source-setup/gog-google-workspace.md`

## Validation

Run the link validator after changes, and show its output rather than asserting "checked":

```bash
python3 scripts/links_validate.py .            # promoted layer
python3 scripts/links_validate.py . --staged   # include staged proposals
```

Also check:

- `SKILL.md` stays reasonably lean; push detail into `references/`.
- the `description` is triggering-aware (what it does and when to use it).
- the closed relation list, statuses, and frontmatter keys are identical across `references/ai-ready.md`, `references/registry-spec.md`, `scripts/links_validate.py`, `references/templates.md`, and the skills.
- every agent skill carries a Why, at least one Example, and an `## Eval cases` section.
- no card field is left blank when it should say `unknown`, `not applicable`, `candidate`, or `hypothesis`.
- JSON contract files under `schemas/` stay aligned with the parser subset documented in `references/parser-subset.md`.

## Style

- All content is English. Sentence case headers. No emoji.
- Explain the reasoning (the "why") instead of leaning on ALL-CAPS MUST/NEVER walls — a smart model generalizes better from rationale than from rails.
- Keep frontmatter compatible with Agent Skills discovery.
- Prefer concise procedural guidance over explanatory essays; do not turn a skill into a one-off project narrative.

# Repository instructions

This repository is a business-ontology toolkit: an operating Agent Skill plus a normative agent spec and an agent-skill library, used to stand up and keep alive a queryable model of how a business module really works. Everything in this repo is in English.

## Scope

- Keep `SKILL.md` (the operating session skill) focused on core behaviour and workflow.
- Keep detailed structures, templates, the link contract, and the registry contract in `references/`.
- Keep behavioural eval material in `evals/`.
- `AGENT-SPEC.md` is the normative (RFC-2119) contract for the runtime agent; `agent-skills/` are the agent's skills; `staged/` is where the agent proposes changes for a human to commit.
- The only executable asset is `scripts/links_validate.py` (a dependency-free validator). The runtime agent ships as a spec (`AGENT-SPEC.md`), not as code in this repo — it is implemented on the operator's stack from that spec. Do not add other runtime/executable code here.

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

## Style

- All content is English. Sentence case headers. No emoji.
- Explain the reasoning (the "why") instead of leaning on ALL-CAPS MUST/NEVER walls — a smart model generalizes better from rationale than from rails.
- Keep frontmatter compatible with Agent Skills discovery.
- Prefer concise procedural guidance over explanatory essays; do not turn a skill into a one-off project narrative.

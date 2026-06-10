# Repository Instructions

This repository contains a markdown-only Agent Skill.

## Scope

- Keep `SKILL.md` focused on core behavior and workflow.
- Keep detailed structures, templates, and pressure tests in `references/`.
- Keep independent evaluation material in `evals/`.
- Do not add scripts or executable assets unless deterministic validation becomes necessary.

## Validation

Run the skill validator after changes:

```bash
python ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```

Also check:

- `SKILL.md` remains under 500 lines.
- `description` starts with `Use when`.
- reference files are one level below `SKILL.md`.
- no template field is left blank when it should say `неизвестно`, `не применимо`, `кандидат`, or `гипотеза`.

## Style

- Main skill content is in Russian.
- Keep frontmatter compatible with Agent Skills discovery.
- Prefer concise procedural guidance over explanatory essays.
- Do not turn the skill into a one-off project narrative.

# Codex bootstrap

Use this adapter when a Codex workspace is asked to install or update the
Business Ontology Resident package.

## Install

1. Clone or pull the package repository.
2. Read `BOOTSTRAP.md`, `agent-package.yaml`, and `AGENTS.md`.
3. Copy or adapt `adapters/codex/AGENTS.template.md` into the target workspace
   `AGENTS.md` when the workspace does not already have stronger local rules.
4. Keep `skills/business-ontology/SKILL.md` as the primary ontology skill.
5. Keep raw source access and model repository access separate.

## Codex behavior

Codex should use the package as a local engineering/operator environment:

- inspect files before editing;
- run tests after package changes;
- update docs and schemas together;
- never store secrets or raw private source payloads;
- prepare pull requests for package changes when asked.

Codex is allowed to edit this package repository when the human asks for
implementation work. That is different from the deployed resident agent, which
must not promote accepted model truth by itself.

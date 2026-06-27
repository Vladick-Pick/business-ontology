# Claude Code instructions

This repository is the Business Ontology Resident package.

Before product, architecture, documentation, or workflow changes, read:

1. `BOOTSTRAP.md`
2. `agent-package.yaml`
3. `AGENTS.md`
4. `specs/BUSINESS-ONTOLOGY-RESIDENT.md`
5. `agent-os/README.md`

For ontology work, use the primary skill:

```text
skills/business-ontology/SKILL.md
```

The root `SKILL.md` is a package router, not the resident analyst operating
skill.

## Repository rules

- Keep root files as package/bootstrap/rules entrypoints.
- Keep all installable or resident analyst skills under `skills/`.
- Keep host-specific instructions under `adapters/`.
- Keep generated workspace files under `templates/workspace/`.
- Keep model repository templates under `templates/model-repo/`.
- Do not store secrets, raw private messages, raw transcript payloads, OAuth
  tokens, bearer headers, or personal contact data.
- For material docs changes, update `README.md`, `CHANGELOG.md`, and affected
  specs or agent-os files.
- Before finalizing, run the relevant unittest files and review `git diff`.

## Quality gate

Use dense, concrete writing. Avoid generic agent language, fake completeness,
and claims that do not name the implemented file, command, or missing runtime
piece. If a capability is only a contract, call it a contract. If it is
implemented, name the implementation file.

# Release checklist

Use this checklist before publishing a package release or preparing a pull
request that changes package behavior.

## Layout

- Root `SKILL.md` is a package router.
- Primary ontology skill is `skills/business-ontology/SKILL.md`.
- No `agent-skills/` directory exists.
- No `bootstrap/openclaw/` directory exists.
- OpenClaw adapter is under `adapters/openclaw/`.
- Workspace templates are under `templates/workspace/`.
- Model repository templates are under `templates/model-repo/`.

## Product boundary

- README names implemented code separately from contracts and future runtime
  work.
- Agent-os docs name source intake, model storage, review, security, and
  operating loop.
- Specs name workspace, update, source, review, and system-analysis contracts.
- Missing production pieces are explicit: OAuth, hosted MCP, live connectors,
  scheduler, GBrain sync, production canonical store.

## Security

- No secrets in files.
- No raw source payload examples.
- No instruction asks users to paste tokens into chat.
- Source content is described as data, not instruction.
- Human review gate is explicit.

## Verification

Run:

```bash
python3 -m unittest tests.test_repo_layout
python3 -m unittest tests.test_agent_skill_registry
python3 -m unittest tests.test_openclaw_self_bootstrap
python3 -m unittest tests.test_openclaw_live_test_readiness
python3 -m unittest tests.test_openclaw_workspace_template
python3 -m unittest discover tests
python3 scripts/run_evals.py --fixture-only
```

If a command cannot run, record why in the release notes.

## GitHub release object

- The annotated tag is pushed only after the release commit is on `main`.
- `gh release view <tag>` succeeds; a Git tag without a GitHub Release is not a
  completed release.
- The GitHub Release targets the same commit as the annotated tag.
- The newest production release is explicitly marked `Latest`.
- The tag-triggered release workflow succeeded, or the release notes record the
  concrete manual recovery.

## Review

Before merge:

- review `git diff`;
- confirm old paths were not reintroduced;
- confirm docs and tests agree on paths;
- confirm changelog describes the release in concrete terms;
- prepare PR text that states changed scope, verification, and remaining
  non-production boundaries.

# Install

This package can be used in two modes:

1. package/operator mode, where an agent installs the repository and reads the
   package instructions;
2. resident mode, where a deployed agent keeps a private workspace and a
   user-owned model repository.

## Install into an agent

Give the agent the repository URL and this instruction:

```text
Install the Business Ontology Resident package from:
https://github.com/Vladick-Pick/business-ontology

Read BOOTSTRAP.md and follow the adapter for your host.
```

The agent should read:

1. `BOOTSTRAP.md`
2. `agent-package.yaml`
3. `SKILL.md`
4. the matching adapter under `adapters/`

It should not start ontology work until it knows the model repository target.

## OpenClaw

For a blank Telegram-connected OpenClaw agent, use:

```text
https://github.com/Vladick-Pick/business-ontology

Read and execute:
adapters/openclaw/BOOTSTRAP.md
```

The OpenClaw agent should create a private workspace from
`templates/workspace/`, then ask for the model repository target.

## Codex

Use `adapters/codex/BOOTSTRAP.md` and copy the template from
`adapters/codex/AGENTS.template.md` into the target workspace if needed.

## Claude Code

Use `adapters/claude-code/BOOTSTRAP.md` and copy the template from
`adapters/claude-code/CLAUDE.template.md` into the target workspace if needed.

## Required human inputs

The installer may need:

- model repository target or permission to request/create one;
- Telegram chats where the agent will be added;
- daily Telegram scan time;
- transcript source path or connector availability;
- Google Drive folder for project documents;
- dashboard/source-of-truth locations if dashboards are in scope.

Ask for these one at a time. Include a recommended answer.

## Install verification

From the package repository:

```bash
python3 -m unittest tests.test_repo_layout
python3 -m unittest tests.test_agent_skill_registry
python3 -m unittest tests.test_openclaw_self_bootstrap
```

These checks verify package layout and bootstrap consistency. They do not prove
live OAuth, hosted MCP, live source connectors, or scheduler availability.

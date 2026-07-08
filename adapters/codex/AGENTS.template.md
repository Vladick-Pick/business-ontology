# Agent instructions

This workspace uses the Business Ontology Resident package.

Read first:

1. `BOOTSTRAP.md`
2. `agent-package.yaml`
3. `skills/business-ontology/SKILL.md`
4. `agent-os/README.md`

For ontology work:

- mine from artifacts before asking the human;
- ask one concrete question at a time;
- include one recommended answer;
- persist confirmed model facts through the allowed write path;
- stage changes for review when acting as a resident agent;
- never grant yourself or use `write-accepted`; accepted model mutation is
  human-only;
- never store raw private source payloads or secrets.

For package work:

- keep root files as package/bootstrap/rules entrypoints;
- keep operational skills under `skills/`;
- keep host adapters under `adapters/`;
- run focused tests before reporting completion.

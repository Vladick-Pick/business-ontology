# Runbook

## Bootstrap checks

1. Confirm the Markdown/Git model export repository: {{ONTOLOGY_REPO_URL}}.
2. Confirm the human can read it.
3. Confirm the agent can prepare a branch or pull request, or mark GitHub as
   `requested-not-configured`.
4. Confirm raw sources are not stored in the model repository.
5. Start the first ontology session.

## First session loop

1. Ask the boundary question.
2. Use `MODEL_STORAGE.md` when a term, state, metric, rule, or attribute needs
   a definition, criteria, examples, or non-examples.
3. Use `PROCESS_WORKFLOWS.md` when a process, lifecycle, handoff, transition,
   exception, participant, or workflow metric appears.
4. Capture accepted facts, conflicts, unknowns, and next questions.
5. Prepare a model-change package or branch.
6. Ask for review before accepted model changes.

## Daily source loop

1. Intake new redacted source events.
2. Compile proposed model changes.
3. Queue human review for material drift or decisions.
4. Stay quiet if no meaningful review exists.

Do not mark a source as active until its runtime gates are present.

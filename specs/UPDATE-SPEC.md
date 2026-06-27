# Update spec

This spec defines how the package, installed agent workspace, and model
repository are updated without losing trust boundaries.

## Update targets

There are three different update targets:

| Target | What changes | Owner |
|---|---|---|
| Package repository | Skills, specs, adapters, templates, runtime reference code, schemas. | Package maintainer. |
| Agent workspace | Host instructions, tool state, cursors, setup notes, session state. | Resident agent, with operator review for sensitive changes. |
| Model repository/store | Accepted model, staged proposals, source map, drift, review records. | Human model owner. |

Do not merge these targets. A package update is not a model truth change. A
source event is not an instruction update. A workspace learning is not accepted
ontology.

## Package update flow

1. Pull the package repository.
2. Read `CHANGELOG.md` and `deployment/MIGRATION_POLICY.md`.
3. Compare `agent-package.yaml` paths against the installed workspace.
4. Copy changed templates only when the target file is still template-owned or
   the update explicitly requires migration.
5. Preserve local workspace state: source cursors, model repo target, run logs,
   review queue, tool availability.
6. Run the focused tests named in `deployment/RELEASE_CHECKLIST.md`.
7. Record the update in the workspace `LEARNINGS.md` or `SESSION_STATE.md` if it
   changes operating behavior.

## Model update flow

Accepted model updates follow the resident loop:

```text
source event
-> model-change package
-> review package
-> human review
-> accepted model update
-> export/projection update
```

The agent may generate source events, model-change packages, review packages,
digests, and staged proposals. It must not promote accepted truth by itself.

## Breaking changes

A package change is breaking when it changes any of these:

- required workspace files;
- schema field names or required fields;
- card status vocabulary;
- relation vocabulary;
- accepted-state storage semantics;
- source cursor semantics;
- review approval semantics;
- adapter bootstrap path.

Breaking changes require:

- a `CHANGELOG.md` entry;
- a `deployment/MIGRATION_POLICY.md` entry;
- a test that fails on the old layout or contract and passes on the new one;
- a short operator note that says what an installed agent must do.

## Safe defaults

When an update conflicts with local state:

- keep local source cursors;
- keep local model repository target;
- keep local secrets outside files;
- keep staged proposals;
- do not regenerate accepted model files;
- ask one concrete migration question with a recommended answer.

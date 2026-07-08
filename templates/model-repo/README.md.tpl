# {{MODEL_NAME}}

This repository stores the accepted business ontology export for
`{{MODEL_NAME}}`.

It is the human-readable model layer, review surface, audit trail, backup, and
portability layer. The target production architecture may also maintain a
canonical model store, but this repository remains readable by humans and
agents.

## Core files

| File | Purpose |
|---|---|
| `README.md` | Model overview and current status. |
| `00-session-log.md` | Ontology session history. |
| `01-boundary-and-purpose.md` | What this model covers and which decisions it supports. |
| `02-source-map.md` | Registered sources and read policies. |
| `03-definitions-and-attributes.md` | Core terms, definitions, attributes, criteria, examples. |
| `04-states-and-lifecycle.md` | States, transitions, validity, and lifecycle notes. |
| `05-processes-and-workflows.md` | Workflows, participants, steps, transitions, exceptions, metrics. |
| `06-decisions-and-authority.md` | Decisions, authority, overrides, exceptions, supersession. |
| `07-metrics-and-truth.md` | Metric definitions, formulas, owners, source of truth. |
| `08-drift-and-open-questions.md` | Drift, conflicts, unknowns, review queue. |
| `09-changelog.md` | Accepted model changes. |
| `PACKAGE_CONTRACT.lock` | Package version/commit that owns validation rules. |
| `scripts/validate_model_repo.py` | Thin wrapper that delegates to the pinned package validator. |

## Rules

- Every material fact has a status and source.
- Competency questions define which decisions the model must be able to answer.
- Unknown fields are written as `unknown`, not left blank.
- The agent proposes changes; the human accepts them.
- Raw sources and secrets do not belong in this repository.
- Superseded definitions and decisions remain queryable.
- Do not copy `scripts/links_validate.py` into this repository. Validation uses
  the package pinned in `PACKAGE_CONTRACT.lock`.

## Validation

Run validation through the wrapper:

```bash
python3 scripts/validate_model_repo.py --package ../package/current
```

The wrapper checks `PACKAGE_CONTRACT.lock`, refuses stale copied validators, and
then calls the package `scripts/links_validate.py` with the v2 hard gate.

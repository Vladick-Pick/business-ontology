# Skills

All resident analyst skills live here. The root repository `SKILL.md` is only a
package router.

## Primary skill

| Skill | Purpose |
|---|---|
| `business-ontology` | Runs business ontology sessions: first capture, continuation, audit, drift, and packaging. |

## Duty skills

| Skill | Purpose |
|---|---|
| `connect-source` | Register a source and its read policy before mining. |
| `mine-materials` | Extract candidate model facts from materials. |
| `extract-from-input` | Convert one untrusted input into candidate ontology facts. |
| `propose-change` | Stage a model change for human review. |
| `promote-digest` | Prepare a human review digest for staged proposals. |
| `drift-flag` | Record a concrete model-versus-reality mismatch. |
| `drift-sweep` | Run cadence checks over accepted model areas. |
| `synthesize-digest` | Produce daily or weekly ontology digests. |
| `decide-like-module` | Draft decisions grounded in accepted module rules. |
| `interpret` | Answer from the accepted ontology with citations and uncertainty. |
| `grill-gaps` | Ask one focused ontology gap question at a time. |
| `build-brain` | Compile accepted cards into the registry graph. |
| `system-analysis` | Prepare accepted-model projections for systems-thinking skills. |

## Rule

Do not create a second skill root such as `agent-skills/`. New resident analyst
skills go under `skills/<name>/SKILL.md`, with frontmatter `name` matching the
folder name and an `## Eval cases` section.

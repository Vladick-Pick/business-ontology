# AI-ready: stable ids, links, and wiring

This file adds the thin layer that makes the ontology *queryable by an agent*, not just readable as prose. Everything else is ordinary cards; this layer is three small commitments on top of them — stable `id`s, one short closed list of relations, and a single instruction that wires the ontology into the project where work actually happens.

Read this when you create or edit a card, draw a link between two entities, or connect the ontology to a working repository. The reason it is worth the discipline: a model that can resolve `id`s and walk a closed set of relations can answer "what feeds this?", "who owns it?", "what breaks if this changes?" — questions plain prose can describe but cannot be traversed to answer. Stable ids and a closed relation list are what turn a folder of notes into something an agent can reason over and an external consumer can attach to.

## Stable ids

Every card carries an `id` in its frontmatter. The id is the card's identity in the graph; the human-readable name is just a label. Keeping them separate is the whole point of this section.

- **Stable** — the `id` does not change when the entity is renamed. People rename concepts all the time as understanding sharpens; if links pointed at names, every rename would silently break them. Links point at ids, so renames are free.
- **Opaque** — the `id` is never derived from participant names or any other field. No composite ids like `a--b--c`: the moment one participant is renamed, a derived id is a lie, and every reference to it dangles. Interfaces use the form `if-<slug>`; everything else uses a short, neutral slug.
- **Unique** — within a module's ontology, no two cards share an `id`. (The validator flags duplicates.)
- **Style** — short kebab-case, readable to a human (`lead-quality`, `attraction-system`, `crm`). Readable is fine; *derived* is not.

Because links reference ids and only ids, an external consumer — a finance overlay, a dashboard interpreter — can attach to a card by its `id` and stay decoupled from however the wording drifts. That decoupling is what makes the model reusable instead of a one-off document.

## The closed relation list

A link in a card's `links` block may only use a relation from the list below. The list is closed on purpose: if the relation you need is missing, that is a signal to extend the list *deliberately* — as a decision, recorded in `CHANGELOG.md` — not to invent a relation on the spot. An open-ended vocabulary is unqueryable; nobody downstream can rely on a set of edge types that grows ad hoc.

The relation names are canonical and identical everywhere — cards, registry, validator, and skill all use exactly these nine, in English kebab-case:

| Relation | From | To |
|---|---|---|
| `produces` | module, production system | output / product |
| `consumes` | module, production system | output / product, tool |
| `supplies-to` | supplier role in an interface | customer role in an interface |
| `part-of` | module, production system | module, production system |
| `owns` | module | production system, tool |
| `measured-by` | process, system, output | metric |
| `source-of-truth` | metric, fact, state | tool / system where the fact lives |
| `in-state` | output, process, entity | state |
| `governed-by` | system, role, module | regulation / authority |

The list stays short by default. It grows only when you genuinely hit a wall — and when it does, the new relation is added *here first* (and to the validator and `registry-spec.md`), then used. Adding it to the contract before using it is what keeps every consumer in agreement about what an edge means.

> Note: `has-supplier`, `has-customer`, and `has-subject` are *structural* registry edges produced only by decomposing an interface hyperedge — they are not authoring relations and never appear in a card's `links`. See [registry-spec.md](registry-spec.md).

## Dangling-link check

Before you commit an edit, walk the card's `links` block: every `id` in the values must resolve to a real card with that `id`. A dangling link — an id that points at nothing — is either a typo or a missing card that should exist (often a `candidate`). Either way it is a finding, so do not leave it silent; fix the typo or create the candidate.

There is an automated check for exactly this:

```bash
python3 scripts/links_validate.py <ontology-root>
```

It verifies the integrity properties this layer depends on:

- every `id` is present and unique, and no node `id` looks derived (contains `--`);
- every target in a `links` block resolves to an existing `id` — no dangling references;
- every relation type is one of the closed nine above;
- every card has both an `id` and a `status`.

Treat the validator as *support for the manual discipline, not a replacement for it.* Run it before you commit, and **show the output** — do not assert "checked" on your word; evidence before claims. Impact-radius queries and graph traversal are the mature `registry/` layer, described in [registry-spec.md](registry-spec.md); the validator is the floor that keeps the cards compilable into that graph.

## Drift cadence

Drift gets caught two ways: *on contact* (something surfaces in a session that contradicts the model) and *on rhythm* (a scheduled sweep). The rhythm half is why every card carries two dates in its frontmatter:

- `last-reviewed` — when the card was last checked against reality.
- `next-audit` — when it is due to be checked again.

A periodic **drift-sweep** walks the cards whose `next-audit` is past due and asks whether the model has diverged from practice or from its source of truth. Any divergence is recorded in `08-drift-and-open-questions.md` as a `drift` (model lags reality) or `gap` (as-is differs from as-should). The full sweep procedure lives in [structure.md](structure.md).

The honesty boundary: the agent catches a **contradiction on contact** — a conflict that surfaces during the work — and the sweep catches **staleness on schedule**. There is no magical reality scanner; nothing auto-detects drift the work never touches. Treating drift as something you find on contact and on cadence, rather than something a tool guarantees, is what keeps the model honest about what it actually knows.

## Wiring into a working project

For the ontology to be picked up while you work *next to* the module (vibe-coding against it), point the working repo at it. Add an instruction like this to the working repository's `AGENTS.md` (or `CLAUDE.md`):

```markdown
The ontology for this module lives at <repo / path to business-ontology>.
Before working on the module, read the relevant cards and answer "as-is" from the model.
If you see the model diverge from reality, do not pass it by: propose the change as a diff
(was -> became, with the basis for it), add a line to CHANGELOG.md under the person's name,
and let a human commit it. Do not commit on your own behalf — the agent proposes, the human commits.
```

That last line is the load-bearing one: the agent *proposes*, the human *commits*. The gate is what keeps an unattended agent from quietly editing the model of reality.

### Where to put the rule

Three placements, from most local to most global — pick by how widely you do ontology work:

- **Project level (default)** — the instruction above goes in the working repo's `AGENTS.md` / `CLAUDE.md`. Most explicit and most local; the rule lives exactly where the module does.
- **Master-folder level** — if all your projects sit under one parent folder, put an `AGENTS.md` in the parent with a general rule: "for each module, read its ontology from <module -> repo map> and use the business-ontology skill." One file covers every project beneath it.
- **Global level** — a rule in `~/.claude/CLAUDE.md` is picked up in every session. Convenient, but it adds noise wherever the ontology is irrelevant; reach for it only if ontology work is genuinely everywhere for you.

How the agent gets the content — git submodule, sibling clone, or `git pull` on demand — is a setup detail. For an MVP it is enough that the ontology repo is locally available to the agent.

## What this sets up for later (not in the MVP)

`id` plus `links` is the seed for a query layer. The compilation contract — the JSON node/edge schema, with the interface hyperedge decomposed into pairs, all on English keys — is specified in [registry-spec.md](registry-spec.md). You do not need to build the MCP server yet. But writing `id`s and links to the contract *now* is what lets consumers (a dashboard interpreter, a finance modeller) attach by `id` later without re-tagging anything. The cost is trivial today; the payoff is a graph that was always compilable.

## Example

Situation: a session reveals that the attraction production system hands qualified leads to sales, and you want that relationship to be queryable rather than buried in prose.

What this skill does — you create two cards and one link, all on the contract:

```yaml
# 03-concept-layer/qualified-lead.md
---
id: qualified-lead
type: concept
status: accepted
source: lead-gen lead, 2026-06
owner: lead-gen lead
links:
  measured-by: [lead-quality]
last-reviewed: 2026-06-16
next-audit: 2026-09-16
---
```

```yaml
# production-systems/attraction.md
---
id: attraction-system
type: production-system
status: accepted
source: lead-gen lead, 2026-06
owner: lead-gen lead
links:
  produces: [qualified-lead]
last-reviewed: 2026-06-16
next-audit: 2026-09-16
---
```

Output and check: run `python3 scripts/links_validate.py .`. The `produces` and `measured-by` relations are both on the closed list, every target (`qualified-lead`, `lead-quality`) resolves to a real card, and both cards have `id` and `status` — so the validator reports zero errors and the graph can now answer "what does the attraction system produce, and how is that output measured?" by traversal rather than by reading. The ids are opaque (none derived from a name), so renaming "attraction" to anything else later leaves every link intact.

## Eval cases

Use these to check that the skill actually fires correctly on this file's behavior.

1. **A new relation is needed.** Prompt: "I need to express that a regulation *replaces* an older one — add a `replaces` link to the card." Good looks like: the agent refuses to invent `replaces` ad hoc, recognizes it is outside the closed nine, and proposes adding it deliberately — to this list, the validator (`ALLOWED_LINKS`), and `registry-spec.md` — recorded as a decision in `CHANGELOG.md`, *before* using it. It does not just write `replaces:` into the card. (For supersession between decision cards, it should note that decision cards already carry a `superseded` status rather than a relation.)

2. **A derived/composite id is proposed.** Prompt: "Name the interface between attraction and sales `attraction--sales-handoff`." Good looks like: the agent rejects the `--` composite as a derived, brittle id, explains that a rename of either side would break it, and instead assigns an opaque `if-<slug>` id (e.g. `if-attraction-sales`) with the human-readable name living in the `label` / name, not the id. It should note the validator flags `--` in node ids.

3. **A link points at a missing card.** Prompt: "This card has `produces: [refined-output]` but there is no `refined-output` card — what do I do?" Good looks like: the agent identifies it as a dangling link (a finding, not something to leave silent), and resolves it one of two ways — fix a typo in the target id, or create the missing card as a `candidate` — then runs `python3 scripts/links_validate.py .` and *shows* the zero-error output rather than asserting it passed.

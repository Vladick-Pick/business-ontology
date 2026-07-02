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

## Common frontmatter and attrs

Every card uses the same common frontmatter spine (data model v2, see [`docs/specs/2026-07-02-data-model-v2.md`](../docs/specs/2026-07-02-data-model-v2.md) for the full normative contract):

```yaml
id: <stable id>
type: business | production-system | role | artifact | tool | metric | state | process | interface | decision | term
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <role-id | unknown>
aliases: []           # optional: old/jargon names, for mining matches
evidence: []           # optional: srcevt-*/prop-* ids backing the current status
volatility: high | medium | low   # optional: audit-cadence hint
links:
  <relation>: [<target-id>]
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  <type-specific-field>: <value>
```

The common keys are `id`, `type`, `status`, `source`, `owner`, `links`, `last-reviewed`, and `next-audit`. `source` is a registered source id from `02-source-map.md`, or explicit `unknown` while provenance is still being established. `owner` resolves to a `role`-typed card id, or the literal `unknown` — the validator warns (not yet an error, for one transitional version) when it does not. `aliases`, `evidence`, and `volatility` are optional; free-text evidence otherwise belongs in the source map or proposal `source-locator`, not invented card prose. The optional `attrs` block is the only place for structured type-specific fields that are not relationships — each of the 11 types has its own closed `attrs` contract, enforced in `schemas/card.schema.json` and `scripts/links_validate.py` (`ALLOWED_ATTRS`), not just documented here. See `templates.md` for the full per-type template and worked example.

`module` and `concept` are v1 type names kept as deprecated aliases for exactly one transitional version: `module` maps to `business` (same containment semantics, attrs move to `links.part-of`); `concept` keeps its old `attrs.subtype` contract untouched. Do not author new `module` or `concept` cards — the validator emits a deprecation warning on sight. `scripts/migrate_taxonomy_v2.py` rewrites v1 cards mechanically per the table in the spec's migration section.

## The closed relation list

A link in a card's `links` block may only use a relation from the list below. The list is closed on purpose: if the relation you need is missing, that is a signal to extend the list *deliberately* — as a decision, recorded in `CHANGELOG.md` — not to invent a relation on the spot. An open-ended vocabulary is unqueryable; nobody downstream can rely on a set of edge types that grows ad hoc.

The relation names are canonical and identical everywhere — cards, registry, validator, and skill all use exactly these ten, in English kebab-case:

| Relation | From | To | Edge attrs |
|---|---|---|---|
| `produces` | business, production-system, process | artifact | — |
| `consumes` | business, production-system, process | artifact, tool | — |
| `supplies-to` | supplier role in an interface | customer role in an interface | also compiler-derived from interface decomposition; see [note](#note-supplies-to-is-also-derived) below |
| `part-of` | business, production-system | business, production-system | — |
| `owns` | business | tool | — |
| `measured-by` | business, production-system, process, artifact, state | metric | — |
| `source-of-truth` | metric, state, artifact | tool | — |
| `lifecycle` | artifact | state | — |
| `governed-by` | business, production-system, role, process, state, metric | decision | — |
| `influences` | metric, state, artifact | metric, state, artifact | `polarity: + \| -`, `delay?` — see [influences format](#influences-format) below |

`in-state` is the deprecated v1 alias for `lifecycle`, kept for one transitional version; the validator accepts it but emits a deprecation warning. The list stays short by default. It grows only when you genuinely hit a wall — and when it does, the new relation is added *here first* (and to the validator and `registry-spec.md`), then used. Adding it to the contract before using it is what keeps every consumer in agreement about what an edge means.

#### Note: `supplies-to` is also derived

The registry's interface-hyperedge decomposition (see `registry-spec.md`) emits `supplies-to` plus the structural `has-supplier`/`has-customer`/`has-subject` edges from an interface card's `attrs.participants` — this is unchanged by v2. In the repo's existing convention (see `examples/acquisition-ontology/interfaces/if-attraction-sales.md`), the interface card itself also carries `links.supplies-to` pointing at the customer directly; the validator does not forbid this. `has-supplier`/`has-customer`/`has-subject` are the ones that are strictly compiler-only and must never appear in a card's `links` — see the note in [registry-spec.md](registry-spec.md#interface-decomposition-hyperedge-node--pairs).

### Influences format

`influences` carries polarity and an optional delay, which a flat `links.<relation>: [<id>, ...]` list of strings cannot hold — every other relation in the table above is a bare id list, and rewriting the parser to accept `links.influences: [{id, polarity, delay?}, ...]` would mean supporting inline structured values inside `links`, which no other relation needs and which the validator's dependency-free parser does not currently do. Rather than special-case the `links` parser for one relation, `influences` ships as a **parser-safe compromise**, decided in `docs/specs/2026-07-02-data-model-v2.md` section 7, item 2:

```yaml
links:
  influences: [m-conv-meeting]      # plain id list, same shape as every other relation
attrs:
  influences:
    - target: m-conv-meeting        # must match one id in links.influences
      polarity: "+"                 # required: "+" or "-"
      delay: "1 week"                # optional: free-text lag
evidence: [srcevt-btx-0630]          # required whenever links.influences is non-empty
```

The validator enforces all three pieces together: every `links.influences` target needs a matching `attrs.influences[].target` entry with a valid `polarity`, and the card's top-level `evidence` must be non-empty — spec section 3 marks `influences` "authored, evidence обязателен" (evidence mandatory), and the top-level `evidence` field is the existing mechanism for that rather than duplicating an evidence field per edge. A missing `attrs.influences` entry, a bad polarity, or empty `evidence` on a card that authors `links.influences` is a validation error, not a warning — unlike the several v1-vs-v2 required-attrs gaps elsewhere in this migration, `influences` is new in v2 with no v1 card to protect, so it is a hard contract from the start. See `examples/business-attraction-v2/metrics/m-sla1.md` for a worked example (`m-sla1` → `m-conv-meeting`, positive polarity, one-week delay).

The `attrs` structured lists this compromise depends on (`attrs.influences`, and separately `state.attrs.transitions`, `state.attrs.reason-codes`, `process.attrs.steps`, `production-system.attrs.stages`, `interface.attrs.qualities`/`attrs.slas`) all use **block-style YAML only** — `- key:` on its own line with subsequent same-indent keys, never inline flow-mapping like `- { key: value }`. The parser silently reads an inline `{ ... }` as a literal scalar string rather than raising an error, which is easy to hit by accident when copying one of the spec's own inline-flow-mapping illustrations verbatim into a card. See `parser-subset.md` for the full supported/unsupported YAML subset.

> Note: `has-supplier`, `has-customer`, and `has-subject` are *structural* registry edges produced only by decomposing an interface hyperedge — they are not authoring relations and never appear in a card's `links`. See [registry-spec.md](registry-spec.md).

## Dangling-link check

Before you commit an edit, walk the card's `links` block: every `id` in the values must resolve to a real card with that `id`. A dangling link — an id that points at nothing — is either a typo or a missing card that should exist (often a `candidate`). Either way it is a finding, so do not leave it silent; fix the typo or create the candidate.

There is an automated check for exactly this:

```bash
python3 scripts/links_validate.py <ontology-root>
python3 scripts/build_registry.py <ontology-root> --out <registry-output-dir>
```

It verifies the integrity properties this layer depends on:

- every `id` is present and unique, and no node `id` looks derived (contains `--`);
- every target in a `links` block resolves to an existing `id` — no dangling references;
- every relation type is one of the closed ten above (or the deprecated `in-state` alias);
- conservative semantic link rules for obvious direction/range mistakes, for example `measured-by` must target a metric, `source-of-truth` must point from a state/metric/artifact to a tool, and `lifecycle` must target a state;
- every card has the required common frontmatter and only allowed type-specific `attrs`, per the closed contract for its type;
- cross-card checks: `owner` resolves to a role or `unknown`; an artifact's `lifecycle` target state points its `attrs.entity` back at the same artifact; `owns` and `part-of` do not encode the same containment fact from both ends; a state's `entry`/`terminal` values are subsets of its `states`, and `reason-codes[].on` values are subsets of `terminal`;
- every non-`unknown` `source` resolves to the nearest `02-source-map.md`, and the card status does not exceed the source's trust floor.

Treat the validator as *support for the manual discipline, not a replacement for it.* A green validator proves well-formedness and some semantic consistency; it does not prove the model is true in operations. Run it before you commit, and **show the output** — do not assert "checked" on your word; evidence before claims. Impact-radius queries and graph traversal use the derived `registry/` layer, built by `scripts/build_registry.py` and described in [registry-spec.md](registry-spec.md). The validator is the floor that keeps the cards compilable into that graph.

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
and let a human review it. Do not promote it on your own behalf — the agent proposes, the human reviews.
```

That last line is the load-bearing one: the agent *proposes*, the human *reviews*. The gate is what keeps an unattended agent from quietly editing the model of reality. In the current repository implementation, accepted review is promoted through a Git commit to the Markdown/Git export.

### Where to put the rule

Three placements, from most local to most global — pick by how widely you do ontology work:

- **Project level (default)** — the instruction above goes in the working repo's `AGENTS.md` / `CLAUDE.md`. Most explicit and most local; the rule lives exactly where the module does.
- **Master-folder level** — if all your projects sit under one parent folder, put an `AGENTS.md` in the parent with a general rule: "for each module, read its ontology from <module -> repo map> and use the business-ontology skill." One file covers every project beneath it.
- **Global level** — a rule in `~/.claude/CLAUDE.md` is picked up in every session. Convenient, but it adds noise wherever the ontology is irrelevant; reach for it only if ontology work is genuinely everywhere for you.

How the agent gets the content — git submodule, sibling clone, or `git pull` on demand — is a setup detail. For an MVP it is enough that the ontology repo is locally available to the agent.

## What this sets up for later (not in the MVP)

`id` plus `links` is the seed for a query layer. The compilation contract — the JSON node/edge schema, with the interface hyperedge decomposed into pairs, all on English keys — is specified in [registry-spec.md](registry-spec.md) and implemented by `scripts/build_registry.py`. You do not need to deploy a networked MCP server yet; [mcp-boundary.md](mcp-boundary.md) defines the boundary and `runtime/reference_runtime.py` gives a local executable reference for the same resource/tool shapes. Writing `id`s and links to the contract *now* is what lets consumers (a dashboard interpreter, a finance modeller) attach by `id` later without re-tagging anything. The cost is trivial today; the payoff is a graph that was always compilable.

## Example

Situation: a session reveals that the attraction production system hands qualified leads to sales, and you want that relationship to be queryable rather than buried in prose.

What this skill does — you create two cards and one link, all on the contract:

```yaml
# artifacts/a-qualified-lead.md
---
id: a-qualified-lead
type: artifact
status: accepted
source: src-lead-gen-decision
owner: r-lead-gen-lead
attrs:
  kind: intermediate
links:
  measured-by: [m-lead-quality]
last-reviewed: 2026-06-16
next-audit: 2026-09-16
---
```

```yaml
# production-systems/ps-attraction.md
---
id: ps-attraction
type: production-system
status: accepted
source: src-lead-gen-decision
owner: r-lead-gen-lead
attrs:
  business: biz-attraction
links:
  produces: [a-qualified-lead]
last-reviewed: 2026-06-16
next-audit: 2026-09-16
---
```

Output and check: run `python3 scripts/links_validate.py .`. The `produces` and `measured-by` relations are both on the closed list, every target (`a-qualified-lead`, `m-lead-quality`) resolves to a real card, `m-lead-quality` is a metric, and `owner` on both cards resolves to a `role` card (`r-lead-gen-lead`) — so the validator reports zero errors and the graph can now answer "what does the attraction system produce, and how is that output measured?" by traversal rather than by reading. The ids are opaque (none derived from a name), so renaming "attraction" to anything else later leaves every link intact. See `examples/business-attraction-v2/` for a complete worked reference covering all 11 types.

## Eval cases

Use these to check that the skill actually fires correctly on this file's behavior.

1. **A new relation is needed.** Prompt: "I need to express that a regulation *replaces* an older one — add a `replaces` link to the card." Good looks like: the agent refuses to invent `replaces` ad hoc, recognizes it is outside the closed ten, and proposes adding it deliberately — to this list, the validator (`ALLOWED_LINKS`), and `registry-spec.md` — recorded as a decision in `CHANGELOG.md`, *before* using it. It does not just write `replaces:` into the card. (For supersession between decision cards, it should note that decision cards already carry `attrs.supersedes` / `attrs.superseded-by` plus a `superseded` status rather than a relation.)

2. **A derived/composite id is proposed.** Prompt: "Name the interface between attraction and sales `attraction--sales-handoff`." Good looks like: the agent rejects the `--` composite as a derived, brittle id, explains that a rename of either side would break it, and instead assigns an opaque `if-<slug>` id (e.g. `if-attraction-sales`) with the human-readable name living in the `label` / name, not the id. It should note the validator flags `--` in node ids.

3. **A link points at a missing card.** Prompt: "This card has `produces: [refined-output]` but there is no `refined-output` card — what do I do?" Good looks like: the agent identifies it as a dangling link (a finding, not something to leave silent), and resolves it one of two ways — fix a typo in the target id, or create the missing card as a `candidate` — then runs `python3 scripts/links_validate.py .` and *shows* the zero-error output rather than asserting it passed.

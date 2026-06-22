# Registry: the compilable-layer contract

Markdown cards are the source of truth. The `registry` is a derived, machine-facing layer: a graph that the cards compile into **one-to-one**, so agents, dashboards, MCP servers, and overlays can query the model by `id`. You never author the registry by hand — it is generated from the cards and then validated against them.

This file pins down that contract so that "agent-queryable" is a commitment rather than a promise, and so the consumers that will lean on it (a dashboard interpreter, a financial modeller, an impact-radius query) can be designed against a stable shape today instead of being retrofitted later.

The whole repository is English now. Cards and the registry share the same English keys and the same edge-type names — there is no translation step, and the old RU→EN mapping is dropped (see [Why there is no RU→EN map anymore](#why-there-is-no-ru-en-map-anymore)).

Read this when you: run or review `scripts/build_registry.py`; design the compilation into a graph, an MCP layer, or an external consumer; consider introducing a new relation; decompose an interface; or need to know exactly what a downstream tool is allowed to assume. A production networked MCP server is not implemented in this repo; [mcp-boundary.md](mcp-boundary.md) defines the boundary a future server must respect, and `runtime/reference_runtime.py` mirrors the same shape locally for tests and captured traces.

## Why a derived graph at all

A markdown card is great for a human and for a model reading prose, but it is a poor target for a query like "what breaks if I change `lead-quality`?" or "which systems claim CRM as their source of truth?". Those questions want a graph: nodes you can pivot on and typed edges you can traverse. So the registry is not a second copy of the truth that can drift — it is a mechanical projection of the cards, regenerated on demand. The card is the truth; the registry is how a machine reaches it. If the two ever disagree, the card wins and the registry is wrong and must be recompiled.

This split is also what lets an external consumer attach to a card by its `id` without depending on how the card happens to be worded. A financial overlay can bind a cost model to node `ps-attraction` and survive the card being retitled or rewritten, because the `id` is the contract, not the prose.

## Principles

- **One source, one shape.** Cards and registry use the same English common frontmatter keys, the same optional `attrs` bag for type-specific structured fields, and the same edge-type names. The registry adds graph mechanics (deterministic edge ids, interface decomposition) but invents no new vocabulary. This is why there is no longer a translation map to keep in sync — a class of drift simply does not exist.
- **`id` is opaque and stable.** A graph node *is* a card's `id`. The `id` is never derived from names and never changes when an entity is renamed (see [ai-ready.md](ai-ready.md)). The human-readable name travels separately in `label`. This matters because edges reference ids: if an id could change on rename, every inbound edge would silently break.
- **Relations come from a closed list.** A new edge type is a deliberate decision plus an edit to [ai-ready.md](ai-ready.md), this file, and the validator — not a one-off invention at authoring time. A closed list is what makes traversal queries finite and what lets a consumer enumerate the edge types it must handle.

## Node schema

```json
{
  "id": "ps-attraction",
  "type": "production-system",
  "label": "Attraction",
  "status": "accepted",
  "source": "src-lead-gen-decision",
  "owner": "lead-gen lead",
  "last-reviewed": "2026-06-16",
  "next-audit": "2026-09-16",
  "attrs": {
    "module": "mod-acquisition"
  }
}
```

Field meanings:

- `type` is the card kind, from a closed set: `concept | module | production-system | interface | process | state | decision`.
- `label` is the current human-readable name. It may change freely; nothing references it.
- `status` is the lifecycle value (see [Status enum](#status-enum)).
- `source`, `owner`, `last-reviewed`, `next-audit` are copied verbatim from the card frontmatter. `source` is a registered source id from the nearest `02-source-map.md`, or explicit `unknown`; the validator rejects unresolved non-`unknown` sources and card statuses that exceed the source trust floor. `last-reviewed` / `next-audit` are what the drift-sweep reads to find stale cards.
- `attrs` is an allowed bag for type-specific structured fields that are not edges (for example a concept's `subtype`, an interface's `outcome` and `quality-criterion`, or a decision's `irreversible` flag). It is "open" only inside the type contracts documented here and in [templates.md](templates.md); the validator rejects unknown top-level frontmatter keys. Keep relationships out of `attrs` — relationships are edges.

### Frontmatter keys and attrs

Every card carries these common frontmatter keys: `id`, `type`, `status`, `source`, `owner`, `links`, `last-reviewed`, `next-audit`. `source` points to a registered source id in `02-source-map.md` so a consumer can resolve provenance and trust floor. `links` is the only common key that does not become a node field — it compiles into edges (see [Edge schema](#edge-schema)).

Type-specific structured fields live under optional `attrs`. Examples: `attrs.subtype` on a concept, `attrs.participants` on an interface, `attrs.entity` on a state, and `attrs.irreversible` / `attrs.episode` / `attrs.scope` on a decision. Anything beyond the common keys and allowed `attrs` fields lives in the card body.

## Status enum

`status` is one of: `accepted | candidate | hypothesis | conflict | deprecated | unknown`.

The point of distinct values is that a consumer can filter on confidence. A dashboard can show only `accepted` nodes; a drift report can surface `conflict` and `hypothesis`; an agent answering "as-is" can refuse to assert anything resting on an `unknown`. Treat the enum as a confidence gradient, not decoration:

- `accepted` — confirmed against reality, safe to assert.
- `candidate` — a likely definition, not yet confirmed.
- `hypothesis` — a guess without a sufficient source; flag it, don't rely on it.
- `conflict` — sources or observations disagree; this is a drift signal, not a settled fact.
- `deprecated` — kept for history and inbound links, but no longer current.
- `unknown` — known to be important, not yet determined.

Decision cards use a different lifecycle — see [Decision cards](#decision-cards).

## Edge schema

```json
{
  "id": "ps-attraction::produces::out-qualified-lead",
  "from": "ps-attraction",
  "to": "out-qualified-lead",
  "type": "produces",
  "attrs": {}
}
```

An edge `id` is derived deterministically as `<from>::<type>::<to>`. This *is* a derived id, and that is fine: the "ids must be opaque" rule protects **nodes**, because nodes get renamed and re-pointed. Edges are never renamed independently — an edge is fully defined by its endpoints and type — so a derived edge id can never go stale on its own. If an endpoint node is removed, the edge ceases to exist; there is nothing to dangle.

`from` and `to` always reference node `id`s. An edge never points at a label, a name, or a literal.

## Relations: the closed list of 9

These are the only business relations an author may write in a card's `links` block, and the only edge types the compiler may emit from `links`. Names are English, kebab-case, identical in card and registry.

| relation | domain → range | reading |
|---|---|---|
| `produces` | module / production-system → output | the producer creates the output |
| `consumes` | module / production-system → output, tool | the consumer takes the output or tool as input |
| `supplies-to` | supplier role → customer role | one role hands work to another (internal client link) |
| `part-of` | module / production-system → module / production-system | structural containment |
| `owns` | module → production-system, tool | the module is accountable for the system or tool |
| `measured-by` | process / system / output → metric | the metric quantifies the thing |
| `source-of-truth` | metric / fact / state → tool / system | where the authoritative value lives |
| `in-state` | output / process / entity → state | the thing is currently in that state |
| `governed-by` | system / role / module → regulation, decision | a rule or authority constrains the thing |

Any type outside this table is a validation error at compile time (see [Validation](#validation)). The validator also enforces conservative semantic direction/range checks where the card `type` and `attrs.subtype` make a mistake obvious: `measured-by` targets metrics, `source-of-truth` points from state/metric/fact to tool/system, `in-state` targets state, `part-of` stays structural, and `governed-by` points at decisions or rule-like concepts. The list is deliberately short; it grows only when you genuinely hit a wall, and then the new relation is added to the table — and to the validator — *first*, before any card uses it. That ordering is what keeps the closed list actually closed.

### Direction is part of the meaning

Edges are directed, and the direction encodes the claim. `source-of-truth` runs *from* the fact *to* where it lives (`metric → tool`), not the other way round — so "where does this number come from?" is a forward traversal, and "what facts does this tool own?" is a reverse traversal. When you author a link, point it the way the table reads; the validator catches high-confidence backwards edges when the endpoints make the mistake unambiguous, but it still cannot prove the operational claim is true.

## Decision cards

A decision is a card (`type: decision`) and a node like any other, but it carries its own lifecycle and a few extra structured fields in `attrs`, because decisions are episodic and sometimes irreversible.

Decision status enum: `proposed | accepted | implemented | superseded | retired`.

Extra kinetic fields, carried in `attrs`:

- `irreversible` — boolean. `true` marks a one-way door: a decision that is expensive or impossible to walk back, which raises the bar for who may move it past `proposed`. Consumers and agents should treat irreversible decisions as higher-stakes and never auto-promote them.
- `episode` — the moment or context the decision was taken in (a date, a meeting, a triggering event). Decisions are not timeless rules; the episode is what lets you reconstruct *why then*.
- `scope` — what the decision binds (a module, a role, a process, the whole system). Scope is what a `governed-by` edge points back to: a system or role is `governed-by` a decision, and the decision's `scope` says how far that authority reaches.
- `decision-owner` — who is accountable for the decision and must review material changes.
- `transition-authority` — who may change the governed state, status, or convention in real operations.
- `measurement-convention` — the formula, unit, method, threshold, or source convention that makes affected KPIs comparable.
- `affected-workflows` and `affected-kpis` — ids or explicit `unknown` values naming the operational surface touched by the decision.
- `propagation-sla` — how quickly the convention must reach teams, dashboards, models, source systems, and workflow instructions.
- `override-policy` and `exception-path` — how normal rules are overridden, how exceptions are routed, and who can approve them.
- `blast-radius` — what breaks or changes downstream if this decision changes.

A decision typically sits on the `to` side of a `governed-by` edge. Keep the lifecycle honest: `proposed` is a draft, `accepted` is agreed but not yet in effect, `implemented` is live, `superseded` points (in prose or via a later decision) to what replaced it, and `retired` is dropped without replacement.

## Interface decomposition (hyperedge → node + pairs)

An interface is conceptually a hyperedge: several participants plus an outcome, which a plain directed edge cannot express. The registry resolves this deterministically into **one `interface` node + structural edges + attributes**, so the graph stays a normal directed graph that ordinary traversal tools can walk.

Source card:

```yaml
---
id: if-attraction-sales        # opaque, NOT built from participant ids
type: interface
status: accepted
source: <…>
owner: <…>
attrs:
  participants:
    supplier: [role-attraction-supplier]
    customer: [role-sales-customer]
    subject: [out-qualified-lead]
  quality-criterion: <…>
  outcome: <a qualified lead exists>
---
```

Compiles to:

```text
node  if-attraction-sales  type=interface
      attrs: { quality-criterion, outcome }
edges:
  if-attraction-sales       has-supplier  role-attraction-supplier
  if-attraction-sales       has-customer  role-sales-customer
  if-attraction-sales       has-subject   out-qualified-lead
  role-attraction-supplier  supplies-to   role-sales-customer
      attrs: { interface: if-attraction-sales, subject: out-qualified-lead }
```

Two things to notice:

- `has-supplier | has-customer | has-subject` are **structural** registry edges, not business relations. They exist only to reattach an interface node to its participants, and they are produced solely by this decomposition. That is exactly why they are *not* in the closed list of 9 — an author never writes them, so they cannot be authored wrong.
- The single business relation that survives decomposition is `supplies-to`, the supplier→customer pair, carrying the interface and subject as edge attributes. This is the edge a query like "who is the internal client of attraction?" actually traverses. The interface node remains as the place to hang the `outcome` and `quality-criterion`, which a bare `supplies-to` edge could not hold.

The interface `id` is opaque (`if-<slug>`) precisely so that renaming or reassigning a participant does not poison it — the rule from [ai-ready.md](ai-ready.md) applied to the one card type most tempted to build a composite id.

## Validation

The authoritative compiler is `scripts/build_registry.py`. It must run validation before emitting registry JSON:

```bash
python3 scripts/links_validate.py <ontology-root>
python3 scripts/build_registry.py <ontology-root> --out <registry-output-dir>
```

It writes:

- `nodes.json` — accepted nodes only (`accepted` knowledge cards; `accepted` or `implemented` decisions).
- `edges.json` — authored business edges plus compiler-generated interface structural edges.
- `manifest.json` — generated timestamp, source root, card/node/edge counts, validator status/output, and warnings.
- `open_questions.json` — only when open-question files are present.

The compiler rejects a registry that violates the contract. At minimum, `scripts/links_validate.py` checks — and any compiler must check — the following, which map one-to-one to the rules above:

- every `id` is unique, and a **node** `id` does not contain `--` and does not look derived from names (the opaque-id rule);
- every target in a card's `links` block resolves to an existing node `id` — no dangling references;
- every relation type is in the closed list of 9 (the closed-list rule);
- high-confidence semantic link rules hold for relation direction/range where endpoint `type` / `attrs.subtype` makes the check unambiguous;
- every card has the required common frontmatter and only allowed type-specific `attrs`;
- every non-`unknown` `source` resolves to `02-source-map.md`, and the card status does not exceed the registered source trust floor.

Run it before committing an edit and **show the output** — do not assert "validated" in prose. A green validator is evidence of well-formedness and conservative semantic consistency; it is not evidence that the model is operationally true.

```bash
python3 scripts/links_validate.py <ontology-root>
# exit 0 = clean, exit 1 = errors
```

Project binding: compiler output is derived and should not be hand-edited. If a future project needs a compatibility adapter for an older `registry/<module>-ontology.json`, build the adapter explicitly rather than spawning a second, incompatible contract. The whole value of this spec is that there is exactly one shape downstream consumers must learn.

## Why there is no RU→EN map anymore

Earlier versions of this kit authored cards in Russian and compiled to English keys for the machine, which meant maintaining a translation table that the cards, the registry, the validator, and the templates all had to agree on. Every term lived in two places, and a mismatch was a real, recurring source of drift. The repository is now English end to end: cards, registry, edge types, and validator share one vocabulary, so the map is gone and so is the class of bug it caused. If you find a residual Russian key or relation name anywhere, treat it as a defect to fix, not a contract to honor.

## Worked example

A small slice of an attraction module, end to end.

Cards (frontmatter only):

```yaml
# card 1
id: ps-attraction
type: production-system
status: accepted
links:
  produces: [out-qualified-lead]
  measured-by: [m-lead-quality]
  governed-by: [d-no-cold-outreach]
```
```yaml
# card 2
id: m-lead-quality
type: concept
status: accepted
attrs:
  subtype: metric
links:
  source-of-truth: [crm]
```
```yaml
# card 3
id: d-no-cold-outreach
type: decision
status: implemented
attrs:
  irreversible: false
  episode: 2026-05 policy call
  scope: attraction
  decision-owner: growth-lead
  transition-authority: growth-lead
  measurement-convention: opt-in recorded before outreach
  affected-workflows: [if-attraction-sales]
  affected-kpis: [m-lead-quality]
  propagation-sla: one week
  override-policy: no agent override; owner approval only
  exception-path: route exceptions to growth-lead
  blast-radius: outreach eligibility, handoff quality, and lead-quality reporting
```

Compiled edges:

```text
ps-attraction  produces      out-qualified-lead
ps-attraction  measured-by   m-lead-quality
ps-attraction  governed-by   d-no-cold-outreach
m-lead-quality source-of-truth  crm
```

Now an agent can answer real questions by traversal: "What does attraction produce?" → forward `produces` from `ps-attraction`. "Where does lead-quality live?" → forward `source-of-truth` from `m-lead-quality` → `crm`. "What governs attraction, and is it reversible?" → forward `governed-by` to `d-no-cold-outreach`, then read its `irreversible` attr. None of these depend on any prose; all depend only on ids and the closed relation set.

## Eval cases

Use these to check that work done against this spec is actually correct. "What good looks like" is objectively checkable wherever possible.

**Case 1 — an author wants a new relation.**
Prompt: "I need to express that a process triggers another process. Can I just add a `triggers:` link to the card?"
What good looks like: refuse the one-off. `triggers` is not in the closed list of 9, so the validator will reject it. The correct path is to treat it as a deliberate decision: add `triggers` to the table in [ai-ready.md](ai-ready.md), to this spec, and to `ALLOWED` in `links_validate.py` **first** (and log it in CHANGELOG.md), and only then use it. Bonus: the answer questions whether `produces`/`consumes` already covers the case before growing the list.

**Case 2 — composite interface id.**
Prompt: "Name the interface between the attraction supplier role and the sales customer role."
What good looks like: an opaque id such as `if-attraction-sales`, explicitly **not** something like `role-attraction-supplier--role-sales-customer`. A correct answer cites the reason (renaming a participant would poison a composite id and dangle inbound edges) and notes that the participant ids live in `participants`, not in the interface id. If asked to decompose it, the answer emits exactly `has-supplier`, `has-customer`, `has-subject` plus one `supplies-to` edge, and keeps `outcome`/`quality-criterion` in the interface node's `attrs`.

**Case 3 — dangling reference after a rename.**
Prompt: "We renamed the metric card's title from 'Lead quality' to 'Qualified-lead rate'. Update the edges that reference it."
What good looks like: **no edge changes** — because edges reference the `id` (`m-lead-quality`), not the label, the rename touches only the `label` field and nothing else. A correct answer states that and resists "fixing" any edge. If the prompt instead changed the `id`, the right move is to flag it as a contract violation (ids are stable) rather than cascade-rewriting edges.

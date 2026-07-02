# Card templates

Use a template only when you are actually creating or updating a card of that type. Templates are not a form to fill for its own sake; they exist so every card you commit carries the same machine-readable spine (`id`, `status`, typed `links`) that lets agents, dashboards, and overlays attach to the model by `id` instead of re-parsing prose.

Why this matters: a card that reads well to a human but has no stable `id` or typed links is invisible to the query layer. The frontmatter is the part the machine reads; the body is the part the human reads. Both have to be true, so fill both.

## How to fill a card

Do not leave blank fields or empty sections. A blank field is ambiguous — the reader cannot tell whether you looked and found nothing, decided it does not apply, or simply skipped it. Make that distinction explicit instead, using one of these values:

- `unknown` — relevant but not yet determined. This is a real signal, not a placeholder: it tells the next person (or agent) there is a gap worth closing.
- `not applicable` — the section genuinely does not apply to this entity.
- `candidate` — a likely answer, but not yet confirmed against a source.
- `hypothesis` — a guess without a sufficient source behind it.

Anything important that resolves to `unknown`, `conflict`, or `hypothesis` should also surface in `08-drift-and-open-questions.md` (or in the card's own "Drift and open questions" section). The reason is that gaps buried inside one card are easy to lose; the drift log is the one place where the team and the agent go looking for what is unresolved. If a gap only lives inside a card, it effectively does not exist for anyone scanning for open work.

## Frontmatter and links

Every card opens with YAML frontmatter. The common keys are fixed and identical across the whole kit (see [ai-ready.md](ai-ready.md) and [registry-spec.md](registry-spec.md)):

`id`, `type`, `status`, `source`, `owner`, `links`, `last-reviewed`, `next-audit`; optionally `aliases`, `evidence`, `volatility`.

Type-specific structured fields live under optional `attrs`, closed per type (data model v2, see [`docs/specs/2026-07-02-data-model-v2.md`](../docs/specs/2026-07-02-data-model-v2.md) section 2 for the full normative contract this file implements). Examples: `attrs.kind` on a role/artifact/tool, `attrs.formula`/`attrs.binding` on a metric, `attrs.states`/`attrs.transitions` on a state, `attrs.steps` on a process, `attrs.participants` on an interface, and `attrs.irreversible`/`attrs.episode`/`attrs.scope`/`attrs.norm-kind` on a decision. Do not add new top-level keys for one card type; that creates a second contract. `source` must be a registered source id from `02-source-map.md`, or explicit `unknown` while provenance is still being established. `owner` should resolve to a `role`-typed card id, or the literal `unknown`.

Two of these carry most of the machine value:

- **`id`** is opaque and stable. It does not change when you rename the entity, and it is never derived from names (no composite ids like `a--b--c`). The reason for opacity is durability: the moment an id encodes a name, renaming a participant rots the id and every link pointing at it goes dangling. The human-readable name lives in the heading; the `id` is the anchor everything else points to. Give an interface card the form `if-<slug>` (the only mandatory prefix); everything else has a recommended prefix by type (see the closed relation list section and each type's template below) plus a short, neutral kebab-case slug.
- **`links`** uses only the closed list of ten relations below. If the relation you want is not in the list, that is a signal — extend the list deliberately as a decision (with a CHANGELOG entry), do not invent a relation inline. The closed list is what makes the graph queryable and validatable; an open vocabulary would make every consumer guess.

Rules of thumb: take relation types only from the closed list; if a card has no links yet, drop the `links` block entirely rather than writing an empty one; every `id` you reference in `links` must resolve to an existing card. Relation direction matters: `source-of-truth` points from the fact to the tool, `measured-by` points to a metric, and `lifecycle` points to a state. The validator catches these obvious endpoint mistakes, but it does not prove the claim is true. A `## Links` section in the card body, if present, is optional human prose — the machine truth about links lives in frontmatter, and the validator only reads frontmatter.

### The closed relation list (exactly ten)

These are the only relations allowed in `links`. They are English, kebab-case, and fixed:

| Relation | From | To |
|---|---|---|
| `produces` | business, production system, process | artifact |
| `consumes` | business, production system, process | artifact, tool |
| `supplies-to` | supplier role in an interface | customer role in an interface — also compiler-derived from interface decomposition |
| `part-of` | business, production system | business, production system |
| `owns` | business | tool |
| `measured-by` | business, production system, process, artifact, state | metric |
| `source-of-truth` | metric, state, artifact | tool where the fact lives |
| `lifecycle` | artifact | state |
| `governed-by` | business, production system, role, process, state, metric | decision |
| `influences` | metric, state, artifact | metric, state, artifact — evidence required, `attrs.influences` parallel block required (see below) |

`in-state` is the deprecated v1 alias for `lifecycle`, kept for exactly one transitional version — the validator accepts it but warns. The list is deliberately short. It grows only when you genuinely hit a wall — and then the new relation is added here first (as a decision), and used second. If a legitimate card trips a semantic link lint, fix the card when the edge is backwards; widen the documented rule only when the domain model genuinely needs it.

**`influences` authoring shape.** A flat `links.influences: [<id>]` list cannot hold the polarity/delay this relation needs, so `influences` ships as `links.influences: [<id>]` plus a required parallel `attrs.influences: [{target, polarity, delay?}]` block, with the card's top-level `evidence` non-empty:

```yaml
links:
  influences: [m-conv-meeting]
attrs:
  influences:
    - target: m-conv-meeting
      polarity: "+"
      delay: "1 week"
evidence: [srcevt-btx-0630]
```

Note the block-style list syntax (`- target:` on its own line, not `- { target: ..., polarity: ... }`) — the parser does not support inline flow-mapping; see [parser-subset.md](parser-subset.md). See `examples/business-attraction-v2/metrics/m-sla1.md` for a full worked example.

### Status values

`status` is one of: `accepted | candidate | hypothesis | conflict | deprecated | unknown`. Decision cards use a different status set (see the decision template below) because a decision has a lifecycle, not a confidence level.

### Cadence fields

`last-reviewed: <date>` and `next-audit: <date>` record when the card was last checked against reality and when to check it again. These drive drift-sweep: a periodic pass walks every card whose `next-audit` is overdue and asks whether the model still matches practice. Without these dates, drift is only caught by accident in conversation; with them, drift is caught on a rhythm. See `structure.md` for the drift-sweep procedure. Optional `volatility: high | medium | low` sets the default cadence when a card is created: high = 7 days, medium = 30 days, low = 180 days (data model v2 section 0.4).

## As-is and as-should (optional gap block)

A card describes how things actually work right now (as-is) by default. That default is on purpose: a model that quietly substitutes the regulation for reality stops being a model of reality and becomes a wish. So describe what happens, and only call out the regulation separately when it diverges.

When the regulation (as-should) diverges from practice (as-is) *and the gap matters for a decision*, add this optional block to the card and mirror it into `08-drift-and-open-questions.md` as type `gap`:

```yaml
gap:
  as-is: <what actually happens>          # source: observation / case
  as-should: <what the regulation prescribes>  # source: regulation / goal
  why: <which decision this gap affects>
```

Do not add this block when there is no divergence — only a real gap gets marked. A gap block with `as-is` equal to `as-should` is noise that trains readers to skip the block.

---

## Concept card (deprecated v1 alias)

> **Deprecated for exactly one transitional version.** `type: concept` still validates, keeping its old `attrs.subtype` contract untouched, so existing concept cards (see `examples/acquisition-ontology/`) keep passing without a forced rewrite. Do not author new concept cards. Each `attrs.subtype` value below now has a first-class v2 type with its own closed `attrs` contract and its own template further down this file: `product`/`service` → **artifact**, `metric` → **metric**, `role`/`position` → **role**, `tool`/`system` → **tool**, `regulation`/`rule`/`authority` → **decision** (`attrs.norm-kind: regulated`), `module` → merge with the business card it duplicates, `state` → merge with the corresponding state card, `fact`/`other` → human review (term or artifact). `scripts/migrate_taxonomy_v2.py` applies this table mechanically; see `docs/specs/2026-07-02-data-model-v2.md` section 6 for the full migration table.

A concept names one term in the business reality and pins down its identity. Use it when a word is doing real work in the module and people would otherwise disagree about what it means.

```markdown
---
id: <stable id, never changes on rename>
type: concept
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <name/role | unknown | not applicable>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  subtype: product | service | module | position | role | metric | fact | tool | system | state | regulation | rule | authority | other
links:                       # relations from the closed list only; drop if none
  measured-by: [<metric-id>]
---

# <Concept name>

## Definition
<What this means in business reality.>

## Is not
<What it must not be confused with.>

## Identity criteria
<By what signs you can tell this is exactly this entity and not a neighbour.>

## Links
<Which modules, processes, systems, metrics it relates to.>

## States
<If applicable.>

## Open questions
<What is still undetermined.>
```

The "Is not" and "Identity criteria" sections are the load-bearing ones. A definition alone rarely settles a dispute; the boundary ("a *qualified lead* is not a *raw lead*") is what makes the concept usable in a decision.

## Module card (deprecated v1 alias)

> **Deprecated for exactly one transitional version.** `type: module` still validates as a deprecated alias for `business` — the validator warns on sight, and `scripts/migrate_taxonomy_v2.py` rewrites `type: module` to `type: business` mechanically, moving `attrs.parent-module`/`attrs.submodules` into `links.part-of`. Do not author new module cards; use the **Business card** template right below instead.

A module is a unit of the production system that produces something for someone. Use it to map what a part of the business does, what it needs, and who it serves.

```markdown
---
id: <stable id>
type: module
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <name/role | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  parent-module: <id | not applicable | unknown>
  submodules: [<id>, ...]       # or: not applicable
links:                        # relations from the closed list only
  produces: [<output-id>]
  part-of: [<parent-id>]
---

# <Module name>

## Purpose
<Why the module exists. | unknown>

## What it produces
<Products, services, deliverables. | unknown>

## Who it produces for
<Customers or consumers of the result. | unknown>

## What it consumes
<Inputs, supplies, data, resources. | unknown>

## Suppliers
<List of suppliers. | unknown | not applicable>

## Customers
<List of customers. | unknown | not applicable>

## Production systems
<Related production systems. | unknown | not applicable>

## Interfaces
<Cross-module interfaces. | unknown | not applicable>

## Metrics
<Metrics for the module. | unknown | not applicable>

## Rules and authority
<Who is allowed to decide what. | unknown>

## Drift and open questions
<Conflicts, unknowns, deprecated parts. | not applicable>
```

## Business card

A business produces something for someone; it is v2's renamed `module`, and the rename is deliberate — each business (Привлечение, Продление, Лидген УС, ПАУ…) has its own ontology and its own model, and "module" was retired as a word specifically so that stops being ambiguous with a code/software module. A business has **no attrs of its own**: containment moves entirely into `links.part-of`, and `links.produces`/`consumes`/`owns`/`measured-by`/`governed-by` carry everything else. Prefix new ids `biz-`.

```markdown
---
id: biz-<slug>
type: business
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <role-id | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
links:                        # relations from the closed list only
  produces: [<artifact-id>]
  consumes: [<artifact-id>, <tool-id>]
  owns: [<tool-id>]
  part-of: [<parent-business-id>]     # if this business is nested under another
  measured-by: [<metric-id>]
  governed-by: [<decision-id>]
---

# <Business name>

## Purpose
<Why the business exists. | unknown>

## What it produces
<Artifacts, and for whom. | unknown>

## Who it produces for
<Customers or consumers of the result. | unknown>

## Boundaries
<What this business explicitly does NOT do or own — the edge of its own black box. | unknown>
```

A business without `links.produces` is flagged by the validator as a warning ("business without a product") — the same audit pattern carried over from v1's module warning. Across multiple businesses, the company-level map is a thin configurator layer over black-box business cards plus interface cards — see `docs/specs/2026-07-02-data-model-v2.md` section 8.5; a business card never models another business's internal mechanics.

## Production-system card

A production system is the concrete machinery that turns inputs into a result: roles, tools, processes, and rules. Use it when you need to see *how* a business actually makes its output, not just *what* it makes. Prefix new ids `ps-`.

`attrs.business` is required (`id` of the owning business). `attrs.stages` is optional but is the field that actually answers "in Bitrix, there are stages, and on each stage there are processes and roles" — a stage is **not** its own card type; it is one entry connecting an artifact's state to the processes and roles active at that point in the funnel. Each stage entry is `{state, label?, processes: [...], roles: [...]}`, and the validator checks every `stages[].state` resolves and every `stages[].processes[]` resolves to a process whose own `attrs.production-system` points back at this card.

```markdown
---
id: ps-<slug>
type: production-system
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <role-id | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  business: <business id>
  stages:                      # optional; order is significant
    - state: <state-id>
      label: "<stage label, e.g. a CRM pipeline stage name>"
      processes: [<process-id>]
      roles: [<role-id>]
links:                        # relations from the closed list only
  part-of: [<business-id>]
  produces: [<artifact-id>]
  measured-by: [<metric-id>]
  governed-by: [<decision-id>]
---

# <Production-system name>

## Purpose
<What result the system produces. | unknown>

## Inputs
<What the system takes in. | unknown>

## Outputs
<What the system produces. | unknown>

## How it works
<Prose walk-through of the machinery: roles, tool, stage sequence. | unknown>

## Tools
<Where and with what the system works. | unknown>

## Drift and open questions
<Conflicts, unknowns, deprecated parts. | not applicable>
```

## Role card

A role is a place with authority, not a person. Use it for "who is accountable for this" — a job function, a position, a seat in the production system — never for an individual's name; personal identity stays out of the model entirely (PII). Prefix new ids `r-`.

```markdown
---
id: r-<slug>
type: role
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <role-id | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  kind: role | position
  authority: []                # list of authority statements or decision ids; optional
links:                        # relations from the closed list only; part-of does NOT apply to roles
  governed-by: [<decision-id>]
---

# <Role name>

## Mandate
<What this role is accountable for. | unknown>

## Is not
<What this role does NOT do — the neighbouring role it must not be confused with. | unknown>
```

Every card's `owner:` field is expected to resolve to a role card id (or the literal `unknown`); the validator warns, for one transitional version, when it does not. This is the mechanism that turns "who owns this" from a free-text name into a queryable fact.

## Artifact card

An artifact is what gets produced and handed off — the thing the business exists to make, or an intermediate a process passes along on the way there. Prefix new ids `a-`.

```markdown
---
id: a-<slug>
type: artifact
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <role-id | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  kind: product | service | intermediate
links:
  lifecycle: [<state-id>]      # the state machine this artifact moves through
  measured-by: [<metric-id>]
  source-of-truth: [<tool-id>]
---

# <Artifact name>

## Definition
<What this artifact is. | unknown>

## Is not
<What it must not be confused with — usually the artifact one step earlier or later in the funnel. | unknown>

## Identity criteria
<By what signs you can tell this is exactly this artifact and not a neighbour. | unknown>
```

An artifact's `links.lifecycle` target must be a state card whose own `attrs.entity` points back at this artifact's id — the validator checks this reciprocity and errors if it is broken in either direction.

## Tool card

A tool is where facts actually live — a system, a dashboard, a channel. Use it for "if you want to check whether this is really true, where do you look." Prefix new ids `t-`.

```markdown
---
id: t-<slug>
type: tool
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <role-id | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  kind: system | tool | dashboard | channel
  access-mode: <how it is read, e.g. crm-pipeline-export | unknown>
links:                        # relations from the closed list only
  governed-by: [<decision-id>]
---

# <Tool name>

## What it holds
<Which facts are true here, and for which cards this is the source-of-truth. | unknown>

## Owner side
<Who configures/owns this tool operationally, as distinct from who reads it. | unknown>
```

Every `source-of-truth` link in the whole model must target a tool card — the validator checks the target type, not just that the id resolves.

## Metric card

A metric is a measurement contract, not a live number — the model never stores the value itself, only how to compute and read it. This is the type that feeds coach/stockflow/leverage/why-tree systems-thinking skills most directly, so its contract is the least forgiving of the eleven. Prefix new ids `m-`.

```markdown
---
id: m-<slug>
type: metric
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <role-id | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
volatility: high                # metrics are usually high-volatility
evidence: [<srcevt-id or prop-id>]
attrs:
  formula: <how it is computed, human-readable but precise | unknown>
  unit: <%, count/week, currency, ...>
  direction: up-is-good | down-is-good | target-band
  target: <number+unit>          # optional
  baseline:                      # optional; a frozen evidence snapshot, NOT a live value
    value: <number+unit>
    as-of: <date>
    source-event: <srcevt-id>
  refresh-cadence: <how often it is recomputed>   # optional
  binding:                       # required (or explicit unknown): WHERE to read the live value
    source: <source-id>
    locator: <e.g. pipeline/funnel name>
    field: <e.g. field name in the tool>
links:
  source-of-truth: [<tool-id>]   # required, or an explicit gap — "metric with no source of truth" is a v1 audit defect
  governed-by: [<decision-id>]   # the measurement convention, if one exists
---

# <Metric name>

## Meaning
<What decision this metric actually informs. | unknown>

## Known distortions
<How this number gets gamed or misread, and what the formula does to close that gap. | unknown>
```

`attrs.direction` has no "unknown" escape hatch — unlike `formula`/`binding`, which may honestly be `unknown` while still visible, a metric with no known direction is unusable for leverage-finder, so the contract requires a real value here from the start. **Never** put a live measured value in the card — `baseline` is a frozen snapshot with a date and a source event, not a dashboard you keep updating; the live number is read at analysis time via `binding`.

## Interface card

An interface is the handoff between performers: a supplier delivers a subject to a customer, and a fact appears in the world as a result. Use it wherever work crosses a boundary between roles, teams, or businesses — these handoffs are where most real breakage and most invisible coordination live.

An interface is a **hyperedge**: a single node connecting several participants and an outcome, not a simple pair. The card carries the participants and the outcome; the registry decomposes that hyperedge deterministically into one `interface` node plus structural edges (`has-supplier` / `has-customer` / `has-subject`) and the business edge `supplies-to` (see [registry-spec.md](registry-spec.md)). The `id` is opaque and of the form `if-<slug>` — the only mandatory prefix in the whole model — never built from the participants' names, because participants change and the id must not.

**Interfaces carry a weight grading, `attrs.contract`**: `handoff` is a lightweight delivery with an outcome but no formal SLA or acceptance gate; `contract` is the full weight — named qualities, one or more independent SLAs with breach effects, and a formal acceptance procedure. Most interfaces are `handoff`; reach for `contract` when there is a real SLA, a real acceptance/rejection right, or both. A `handoff` interface with `attrs.slas` filled in gets a validator warning ("looks like this should be `contract`").

```markdown
---
id: if-<opaque-slug>           # NOT from participant names; stable on rename
type: interface
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <role-id | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  contract: handoff | contract   # weight grading; see above
  # an interface is a hyperedge: one node ties several participants together, not a pair
  participants:
    supplier: [<role-id or business-id>]
    customer: [<role-id or business-id>]   # business-id allowed for cross-business interfaces
    subject: [<artifact-id>]       # what is actually delivered
  outcome: <what fact appears in the world as a result | unknown>
  quality-criterion: <how the customer knows it is accepted>   # required for contract; optional for handoff
  # -- contract-level only, below --
  qualities:                       # named, checkable delivery qualities
    - name: "<quality name, e.g. Готов ко встрече>"
      definition: <what makes this quality true>
      sla: <optional timing note>
  slas:                            # independent SLAs; do not merge into one field
    - id: SLA-1
      rule: <the timing/quality rule>
      breach-effect: <what happens on breach; may reference a decision id>
  acceptance:                      # required when contract: contract
    who: <role-id>
    criteria: <how acceptance is judged>
    moment: <when acceptance is considered to have happened>
    rejection: <the customer's right to reject, even after some point>
    return-policy: <what happens to a rejected/returned item>
links:
  governed-by: [<decision-id>]
  supplies-to: [<customer-role-id>]   # optional; also compiler-derived from attrs.participants during interface decomposition (see registry-spec.md) — authoring it directly here as well is the repo's existing convention, not required
---

# <Supplier> -> <Customer>

## What is delivered
<Artifact, data, leads. | unknown>

## Quality criteria
<How the customer knows the delivery is accepted. | unknown>

## Delivery format
<Where and in what form the result is handed over. | unknown>

## Frequency or trigger
<When the delivery happens. | unknown>

## Acceptance
<Who accepts the result and how; mirror attrs.acceptance in prose if contract-level. | unknown>

## Metrics
<How the interface is measured. | unknown | not applicable>

## Interface failure
<What counts as a failure and what happens next; mirror attrs.slas[].breach-effect if any. | unknown>

## Open questions
<What is still undetermined. | not applicable>
```

See `examples/business-attraction-v2/interfaces/if-lidgen-attraction.md` for a full worked `contract`-level example with two independent SLAs and a breach effect that references a decision card.

## Process card

A process is an ordered run of steps that roles carry out — this is what "business process" means in everyday speech at the level a card actually captures (a *sequence of work on one funnel stage*, not the whole sequential flow of a business, which is a production-system's stages plus a state machine, and not a cross-business flow, which is a chain of interfaces — see `docs/specs/2026-07-02-data-model-v2.md` section 1 for the full three-way split of "business process"). Prefix new ids `p-`.

`attrs.steps` is the load-bearing field: an ordered list, verbatim order significant (it drives table-of-contents / flowchart rendering), each step naming the role that does it, what it does, and optionally a `rule` (the governing decision for that one step — this is the primary hook constraint-finder reads) and a `decision` branch (`question`/`yes`/`no` pointing at other step ids). Budget: 30 steps; beyond that, decompose into more than one process.

```markdown
---
id: p-<slug>
type: process
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <role-id | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  production-system: <production-system id>
  entry-state:                   # optional; stitches the process to the artifact's lifecycle
    state: <state-id>
    name: <state name>
  exit-state:                    # optional
    state: <state-id>
    name: <state name>
  steps:                         # required; order is significant
    - id: step-1-<slug>
      role: <role-id>
      does: <what this step actually does, in plain prose>
      input: <artifact-id or free text>       # optional
      output: <artifact-id or free text>      # optional
      rule: <decision-id>                     # optional: the policy this step follows
      decision:                               # optional: a branch inside the step sequence
        question: <the yes/no question>
        yes: <step-id>
        no: <step-id>
      warn: true                              # optional: flags "not clear what happens next" as-is
links:
  measured-by: [<metric-id>]
  governed-by: [<decision-id>]     # the process-wide regulation, distinct from a per-step rule
---

# <Process name>

## Trigger
<What starts the process. | unknown>

## Exceptions
<Off-nominal branches that exit the normal step sequence entirely. | unknown | not applicable>

## Where it breaks
<As-is honesty: the point in the process most likely to fail or drift, and why — not a fix, a description. | unknown>
```

See `examples/business-attraction-v2/processes/p-handle-delivery.md` for a full worked example with a branch step and an exception exit.

## State card (lifecycle)

The dynamic layer. A state card describes the modes an artifact can be in and how it moves between them — the machine states, not a status field on a row. Use it when something has a meaningful lifecycle — a lead, an order, an account — and decisions depend on knowing which mode it is in. Prefix new ids `st-`.

`entry`/`terminal`/`transitions` are all required, and this is where the terminal states genuinely live — not an emergent property of a name matching a regex ("Корзина" is terminal because it is listed in `attrs.terminal`, not because of what it is called). `reason-codes` is optional: a per-terminal-state list of the required codes that explain *why* an artifact ended up there, which is exactly where loss-reason taxonomies belong. Budget: 12 states; beyond that, decompose.

```markdown
---
id: st-<slug>
type: state
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <role-id | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  entity: <artifact id this state machine belongs to>
  states: [<state name>, ...]      # closed list of named modes
  entry: [<state name>]            # subset of states; where the artifact starts
  terminal: [<state name>]         # subset of states; where it can end
  transitions:                     # order not significant; every from/to must be in states
    - from: <state name>
      to: <state name>
      trigger: <what causes this transition>
      sla: <optional delay budget, e.g. "24ч. раб.">
      authority: <role-id or decision-id>     # who/what may declare this transition
  reason-codes:                    # optional; on must be one of terminal
    - on: <terminal state name>
      codes:
        - code: <short code>
          meaning: <what it means>
          what-to-do: <optional next action>
links:                        # relations from the closed list only; drop if none
  source-of-truth: [<tool-id>]
  measured-by: [<metric-id>]
  governed-by: [<decision-id>]
---

# <State / lifecycle name>

## Transition evidence
<What fact confirms the transition actually happened — usually a tool record change, not a verbal claim. | unknown>

## Who may declare done
<The role or decision with that authority; mirror attrs.transitions[].authority in prose. | unknown>
```

"Transition evidence" and "Who may declare done" are the parts that keep a lifecycle honest. A state that anyone can flip with no evidence is a state that drifts silently from reality. See `examples/business-attraction-v2/states/st-deal.md` for a full worked example with an automated (non-role) authority on one transition.

## Decision card

The kinetic layer. A decision card records a made decision or rule: who decided, when, on what grounds, with what status, whether it can be reversed, who owns the authority, which measurement convention makes it true, what can override it, and where its consequences propagate. Use it for choices that shape the model — especially irreversible ones, measurement conventions, transition authority, and exceptions where the cost of forgetting the reasoning is high. Prefix new ids `d-`.

Note the different status set: a decision has a lifecycle (`proposed -> accepted -> implemented`, or `superseded` / `retired`), not a confidence level. The `irreversible` flag marks one-way doors — decisions that are hard or impossible to roll back — so the team treats them with the weight they deserve. The 12 fields below are v1's contract, unchanged (do not rename them). `attrs.norm-kind` is new in v2 and distinguishes *why* this is a rule: `decided` (someone chose it), `regulated` (a written regulation says so), or `observed-practice` (nobody decided it, it is just what happens — which requires `transition-authority: unknown` and a status no stronger than `candidate`, since a practice with no author cannot be born `accepted`).

```markdown
---
id: d-<slug>
type: decision
status: proposed | accepted | implemented | superseded | retired
source: <registered source id from 02-source-map.md | unknown>
owner: <role-id | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  norm-kind: decided | regulated | observed-practice
  irreversible: <true | false>      # one-way door: hard or impossible to undo
  episode: <date, case, meeting, or triggering event | unknown>
  scope: <what this decision covers and does NOT cover | unknown>
  decision-owner: <role-id accountable for the decision | unknown>
  transition-authority: <role-id who may change the governed state/convention | unknown | not applicable>
  measurement-convention: <definition/formula/unit/method that makes the KPI true | unknown | not applicable>
  affected-workflows: [<process/interface id>, ...]           # or: unknown | not applicable
  affected-kpis: [<metric id>, ...]                            # or: unknown | not applicable
  propagation-sla: <how fast this must reach teams, dashboards, models, and docs | unknown>
  override-policy: <who may override the normal rule, and under what conditions | unknown | not applicable>
  exception-path: <where exceptions are routed and how they are logged | unknown | not applicable>
  blast-radius: <what breaks or changes downstream if this decision changes | unknown>
  supersedes: <decision-id>          # optional: replacement chain, kept in attrs (not links)
  superseded-by: <decision-id>       # optional; required once status: superseded
  valid-from: <date>                 # optional
  valid-to: <date>                   # optional
links:                           # optional; relations from the closed list only
  governed-by: [<id of the rule/authority, if any>]
---

# <Short decision name>

## Decision
<What exactly was decided. | unknown>

## Episode / grounds
<The specific case or reason the decision arose from. | unknown>

## Scope
<What the decision covers and what it does NOT cover. | unknown>

## Consequences
<Which cards are affected — businesses, processes, metrics, interfaces, states. | unknown>

## Kinetic checks
- Authority: <who has authority to change the state, rule, or measurement convention. | unknown>
- Measurement convention: <what exact formula/unit/source makes the affected KPI true. | unknown | not applicable>
- Override vs exception: <normal rule, override policy, and exception path. | unknown>
- Propagation: <where this must propagate and by when. | unknown>
- Blast radius: <downstream workflows, KPIs, models, interfaces, or teams affected. | unknown>

## Considered alternatives
<Options that were rejected, and why — this is the section that keeps a future reader from re-litigating a choice without knowing what was already tried. | unknown>

## Supersession / rollback
<What replaced it or why it was retired, if status is superseded/retired. | not applicable>

## Drift and open questions
<Conflicts, unknowns. | not applicable>
```

See `examples/business-attraction-v2/decisions/d-autopurchase.md` for a full worked example with `norm-kind: regulated`, `irreversible: true`, and a filled-in "Considered alternatives" section.

---

## Term card

The word/vocabulary layer, reserved for words that name *not-svobjects* — a term that is not itself an object with its own attrs, links, and lifecycle, but a piece of shared vocabulary the team needs to agree on. Use it sparingly: if a term's `applies-to` list points at exactly one object, that is a validator warning — it is a signal the term should probably be a section on that object's card instead of a standalone term card. Prefix new ids `tm-`.

```markdown
---
id: tm-<slug>
type: term
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <role-id | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  applies-to: [<id>, ...]        # which objects this word applies to; required
---

# <Term name>

## Definition
<What this term means in business reality. | unknown>

## Is not
<What it must not be confused with. | unknown>

## Identity criteria
<By what signs you can tell this term is in play, as opposed to a neighbouring word. | unknown>
```

See `examples/business-attraction-v2/terms/tm-delivery-quality.md` for a worked example of a term that decomposes into fields on more than one other card, which is exactly the case where a standalone term card earns its keep.

---

## Example: a concept card from a real session

Situation: a lead-generation manager keeps saying "lead", but sales and marketing clearly mean different things by it. You are mining the chat as-is, you see the disagreement surface, and you create a concept card to pin the boundary.

```markdown
---
id: qualified-lead
type: concept
status: candidate
source: src-lead-gen-sync
owner: head of lead-gen
last-reviewed: 2026-06-18
next-audit: 2026-09-18
attrs:
  subtype: concept
links:
  measured-by: [m-lead-quality]
---

# Qualified lead

## Definition
A contact that meets the agreed qualification criteria and has been accepted by sales.

## Is not
Not a raw lead (just contact details), and not a won deal (no purchase yet).

## Identity criteria
Has a named decision-maker, a stated need, and sales has marked it accepted in the CRM.

## Open questions
The exact qualification threshold is disputed between marketing and sales — see drift log.
```

What this produces: the term now has a boundary ("is not a raw lead"), a stable `id` that the metric `m-lead-quality` and any interface can point at, and the disputed threshold is flagged for the drift log instead of staying a silent disagreement.

## Eval cases

These check that a template is applied correctly, not just that text was produced.

**Case 1 — agent proposes a new business card.**
Prompt: "We have an 'Onboarding' team that takes signed contracts and produces activated accounts. Add a card."
What good looks like: a `type: business` card with a stable opaque `id` prefixed `biz-` (not `onboarding-team-2026` or any name-derived composite), `status: candidate` (it is freshly proposed, not confirmed), filled "What it produces" / "Purpose" sections, and a `links` block using only closed-list relations (e.g. `produces: [<activated-account-id>]`). No empty sections — anything unknown is written as `unknown`, not left blank. `type: module` is a fail here — module is a deprecated v1 alias and should not be used for new cards. The card is proposed to `staged/`, not promoted, because the human review gate owns acceptance.

**Case 2 — an interface card with a name-derived id.**
Prompt: "Create the handoff card between Acquisition and Sales for qualified leads."
What good looks like: the card uses `type: interface` with an opaque id like `if-acq-sales`, fills `attrs.contract` (`handoff` unless there is a real SLA/acceptance gate), `attrs.participants` (supplier / customer / subject), and `attrs.outcome`, and uses `supplies-to` in `links` pointing at the customer role — matching the existing worked example in `examples/acquisition-ontology/interfaces/if-attraction-sales.md`. (`registry-spec.md` documents `supplies-to` as compiler-derived from interface decomposition, but the validator does not currently forbid also authoring it directly on the interface card itself, and the repo's own v1 fixture does so; this is a pre-existing doc/practice gap, not something this file's v2 changes resolve.) The id is flagged as wrong if it is built from participant names in a way that would rot on rename (e.g. `acquisition--sales--qualified-lead`). A reviewer should be able to point to the rule "interface id is `if-<slug>`, never from participant names."

**Case 3 — a gap surfaces during mining.**
Prompt: "The policy says every refund needs manager approval, but in practice agents approve refunds under $50 themselves. Capture this."
What good looks like: the relevant card stays as-is (it describes the real practice: agents approve small refunds), and a `gap` block is added with `as-is` (agents self-approve under $50), `as-should` (policy requires manager approval), and `why` (which decision the gap affects). The gap is also mirrored into `08-drift-and-open-questions.md` as type `gap`. The model is not "corrected" to match the policy — the divergence is recorded, not erased.

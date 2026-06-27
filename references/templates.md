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

`id`, `type`, `status`, `source`, `owner`, `links`, `last-reviewed`, `next-audit`.

Type-specific structured fields live under optional `attrs`. Examples: `attrs.subtype` on a concept, `attrs.parent-module` on a module, `attrs.participants` on an interface, `attrs.entity` on a state, and `attrs.irreversible` / `attrs.episode` / `attrs.scope` on a decision. Do not add new top-level keys for one card type; that creates a second contract. `source` must be a registered source id from `02-source-map.md`, or explicit `unknown` while provenance is still being established.

Two of these carry most of the machine value:

- **`id`** is opaque and stable. It does not change when you rename the entity, and it is never derived from names (no composite ids like `a--b--c`). The reason for opacity is durability: the moment an id encodes a name, renaming a participant rots the id and every link pointing at it goes dangling. The human-readable name lives in the heading; the `id` is the anchor everything else points to. Give an interface card the form `if-<slug>`; give everything else a short, neutral kebab-case slug (`lead-quality`, `crm`, `ps-acquisition`).
- **`links`** uses only the closed list of nine relations below. If the relation you want is not in the list, that is a signal — extend the list deliberately as a decision (with a CHANGELOG entry), do not invent a relation inline. The closed list is what makes the graph queryable and validatable; an open vocabulary would make every consumer guess.

Rules of thumb: take relation types only from the closed list; if a card has no links yet, drop the `links` block entirely rather than writing an empty one; every `id` you reference in `links` must resolve to an existing card. Relation direction matters: `source-of-truth` points from the fact to the tool/system, `measured-by` points to a metric, and `in-state` points to a state. The validator catches these obvious endpoint mistakes, but it does not prove the claim is true. A `## Links` section in the card body, if present, is optional human prose — the machine truth about links lives in frontmatter, and the validator only reads frontmatter.

### The closed relation list (exactly nine)

These are the only relations allowed in `links`. They are English, kebab-case, and fixed:

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
| `governed-by` | system, role, module | regulation / decision |

The list is deliberately short. It grows only when you genuinely hit a wall — and then the new relation is added here first (as a decision), and used second. If a legitimate card trips a semantic link lint, fix the card when the edge is backwards; widen the documented rule only when the domain model genuinely needs it.

### Status values

`status` is one of: `accepted | candidate | hypothesis | conflict | deprecated | unknown`. Decision cards use a different status set (see the decision template below) because a decision has a lifecycle, not a confidence level.

### Cadence fields

`last-reviewed: <date>` and `next-audit: <date>` record when the card was last checked against reality and when to check it again. These drive drift-sweep: a periodic pass walks every card whose `next-audit` is overdue and asks whether the model still matches practice. Without these dates, drift is only caught by accident in conversation; with them, drift is caught on a rhythm. See `structure.md` for the drift-sweep procedure.

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

## Concept card

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

## Module card

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

## Production-system card

A production system is the concrete machinery that turns inputs into a result: people in positions, tools, processes, and rules. Use it when you need to see *how* a module actually makes its output, not just *what* it makes.

```markdown
---
id: <stable id>
type: production-system
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <name/role | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  module: <module id | unknown>
links:                        # relations from the closed list only
  produces: [<output-id>]
  measured-by: [<metric-id>]
---

# <Production-system name>

## Purpose
<What result the system produces. | unknown>

## Inputs
<What the system takes in. | unknown>

## Outputs
<What the system produces. | unknown>

## Positions and roles
<Who works in the system. | unknown>

## Tools
<Where and with what the system works. | unknown>

## Processes
<Which processes belong to it. | unknown>

## Rules
<Which rules govern the system. | unknown>

## Metrics
<How the system's work is measured. | unknown>

## Customers
<Who accepts the result. | unknown>

## Drift and open questions
<Conflicts, unknowns, deprecated parts. | not applicable>
```

## Interface card

An interface is the handoff between performers: a supplier delivers a subject to a customer, and a fact appears in the world as a result. Use it wherever work crosses a boundary between roles, teams, or modules — these handoffs are where most real breakage and most invisible coordination live.

An interface is a **hyperedge**: a single node connecting several participants and an outcome, not a simple pair. The card carries the participants and the outcome; the registry decomposes that hyperedge deterministically into one `interface` node plus structural edges (`has-supplier` / `has-customer` / `has-subject`) and the business edge `supplies-to` (see [registry-spec.md](registry-spec.md)). The `id` is opaque and of the form `if-<slug>` — never built from the participants' names, because participants change and the id must not.

```markdown
---
id: if-<opaque-slug>           # NOT from participant names; stable on rename
type: interface
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <name/role | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  # an interface is a hyperedge: one node ties several participants together, not a pair
  participants:
    supplier: [<role-id>]
    customer: [<role-id>]
    subject: [<output/product-id>]   # what is actually delivered
  quality-criterion: <how the customer knows it is accepted | unknown>
  outcome: <what fact appears in the world as a result | unknown>
links:
  supplies-to: [<customer-id>]
---

# <Supplier> -> <Customer>

## What is delivered
<Product, service, data, leads, artifact. | unknown>

## Quality criteria
<How the customer knows the delivery is accepted. | unknown>

## Delivery format
<Where and in what form the result is handed over. | unknown>

## Frequency or trigger
<When the delivery happens. | unknown>

## Acceptance
<Who accepts the result and how. | unknown>

## Metrics
<How the interface is measured. | unknown | not applicable>

## Interface failure
<What counts as a failure and what happens next. | unknown>

## Open questions
<What is still undetermined. | not applicable>
```

## Process scheme

A process is an ordered run of steps that moves an entity from one state to another. Use it to capture a sequence that people follow, including its exception branches.

```markdown
---
id: <stable id>
type: process
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <name/role | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  production-system: <id | unknown | not applicable>
links:                        # relations from the closed list only
  in-state: [<state-id>]
---

# <Process name>

## Goal
<Why the process exists. | unknown>

## Participants
<Roles, positions, modules. | unknown>

## Entry state
<Where the process begins. | unknown>

## Steps
<The sequence of actions. | unknown>

## State transitions
<Which states change. | unknown | not applicable>

## Exit state
<Where the process ends. | unknown>

## Exceptions
<Off-nominal branches. | unknown | not applicable>

## Metrics
<How the process is measured. | unknown | not applicable>

## Open questions
<What is still undetermined. | not applicable>
```

## State card (lifecycle)

The state layer. A state card describes the modes an object or process can be in and how it moves between them. Use it when something has a meaningful lifecycle — a lead, an order, an account — and decisions depend on knowing which mode it is in.

```markdown
---
id: <stable id>
type: state
status: accepted | candidate | hypothesis | conflict | deprecated | unknown
source: <registered source id from 02-source-map.md | unknown>
owner: <name/role | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  entity: <id of the object/process this state belongs to | unknown>
links:                        # relations from the closed list only; drop if none
  source-of-truth: [<id of where the state fact lives>]
---

# <State / lifecycle name>

## What it describes
<Which object, in which mode. | unknown>

## States
<The named states, in order. | unknown>

## Transitions
<From which to which, on what condition or event. | unknown>

## Transition evidence
<What fact confirms the transition actually happened. | unknown>

## Who may declare the transition done
<The role or rule with that authority. | unknown>

## Dead ends and losses
<Terminal and off-nominal states, and what happens next. | not applicable>

## Drift and open questions
<Conflicts, unknowns, deprecated parts. | not applicable>
```

"Transition evidence" and "Who may declare the transition done" are the parts that keep a lifecycle honest. A state that anyone can flip with no evidence is a state that drifts silently from reality.

## Decision card

The decision / kinetic layer. A decision card records a made decision or rule: who decided, when, on what grounds, with what status, whether it can be reversed, who owns the authority, which measurement convention makes it true, what can override it, and where its consequences propagate. Use it for choices that shape the model — especially irreversible ones, measurement conventions, transition authority, and exceptions where the cost of forgetting the reasoning is high.

Note the different status set: a decision has a lifecycle (`proposed -> accepted -> implemented`, or `superseded` / `retired`), not a confidence level. The `irreversible` flag marks one-way doors — decisions that are hard or impossible to roll back — so the team treats them with the weight they deserve.

```markdown
---
id: <stable id, e.g. d-<slug>>
type: decision
status: proposed | accepted | implemented | superseded | retired
source: <registered source id from 02-source-map.md | unknown>
owner: <who decided or is accountable | unknown>
last-reviewed: <date | unknown>
next-audit: <date | unknown>
attrs:
  irreversible: <true | false>      # one-way door: hard or impossible to undo
  episode: <date, case, meeting, or triggering event | unknown>
  scope: <what this decision covers and does NOT cover | unknown>
  decision-owner: <role/person accountable for the decision | unknown>
  transition-authority: <who may change the governed state/convention | unknown | not applicable>
  measurement-convention: <definition/formula/unit/method that makes the KPI true | unknown | not applicable>
  affected-workflows: [<workflow/interface/process id>, ...]   # or: unknown | not applicable
  affected-kpis: [<metric id>, ...]                            # or: unknown | not applicable
  propagation-sla: <how fast this must reach teams, dashboards, models, and docs | unknown>
  override-policy: <who may override the normal rule, and under what conditions | unknown | not applicable>
  exception-path: <where exceptions are routed and how they are logged | unknown | not applicable>
  blast-radius: <what breaks or changes downstream if this decision changes | unknown>
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
<Which concepts, modules, processes, metrics, interfaces are affected. | unknown>

## Kinetic checks
- Authority: <who has authority to change the state, rule, or measurement convention. | unknown>
- Measurement convention: <what exact formula/unit/source makes the affected KPI true. | unknown | not applicable>
- Override vs exception: <normal rule, override policy, and exception path. | unknown>
- Propagation: <where this must propagate and by when. | unknown>
- Blast radius: <downstream workflows, KPIs, models, interfaces, or teams affected. | unknown>

## Supersession / rollback
<What replaced it or why it was retired, if status is superseded/retired. | not applicable>

## Drift and open questions
<Conflicts, unknowns. | not applicable>
```

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

**Case 1 — agent proposes a new module card.**
Prompt: "We have a 'Onboarding' team that takes signed contracts and produces activated accounts. Add a card."
What good looks like: a `type: module` card with a stable opaque `id` (not `onboarding-team-2026` or any name-derived composite), `status: candidate` (it is freshly proposed, not confirmed), filled "What it produces" / "What it consumes" sections, and a `links` block using only closed-list relations (e.g. `produces: [<activated-account-id>]`). No empty sections — anything unknown is written as `unknown`, not left blank. The card is proposed to `staged/`, not promoted, because the human review gate owns acceptance.

**Case 2 — an interface card with a name-derived id.**
Prompt: "Create the handoff card between Acquisition and Sales for qualified leads."
What good looks like: the card uses `type: interface` with an opaque id like `if-acq-sales`, fills `attrs.participants` (supplier / customer / subject), `attrs.quality-criterion`, and `attrs.outcome`, and uses `supplies-to` in `links`. The id is flagged as wrong if it is built from participant names in a way that would rot on rename (e.g. `acquisition--sales--qualified-lead`). A reviewer should be able to point to the rule "interface id is `if-<slug>`, never from participant names."

**Case 3 — a gap surfaces during mining.**
Prompt: "The policy says every refund needs manager approval, but in practice agents approve refunds under $50 themselves. Capture this."
What good looks like: the relevant card stays as-is (it describes the real practice: agents approve small refunds), and a `gap` block is added with `as-is` (agents self-approve under $50), `as-should` (policy requires manager approval), and `why` (which decision the gap affects). The gap is also mirrored into `08-drift-and-open-questions.md` as type `gap`. The model is not "corrected" to match the policy — the divergence is recorded, not erased.

<div align="center">

# business-ontology

> *"A model of business reality that both humans and agents can read: as-is, with a source, by id."*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/Agent-Skill-7c3aed)](SKILL.md)
[![Codex](https://img.shields.io/badge/Codex-compatible-111827)](SKILL.md)
[![Claude Code](https://img.shields.io/badge/Claude_Code-compatible-8b5cf6)](SKILL.md)

<br>

**An agent skill for building, validating, and evolving a business ontology — a curated model of how a module or a company actually works: definitions, states, decisions, sources, and drift.**

This is not RDF/OWL and not a database schema. It is an operational capture loop that leaves behind a versioned model in git, queryable by agents through stable `id`s.

</div>

**Install** — pick one path:

**A. Via [`skills`](https://github.com/vercel-labs/skills) (any compatible agent):**

```bash
npx skills add Vladick-Pick/business-ontology -g
```

**B. Or paste this prompt to your agent:**

```text
Install the business-ontology skill:
1. Clone https://github.com/Vladick-Pick/business-ontology into my
   user-level skills folder as `business-ontology/`
   (Codex: ~/.codex/skills/, Claude Code: ~/.claude/skills/).
2. Confirm that SKILL.md and the references/ folder are present.
3. Report the install path back to me.
```

**C. Manually:**

```bash
# Claude Code, user-level
mkdir -p "$HOME/.claude/skills"
git clone https://github.com/Vladick-Pick/business-ontology.git \
  "$HOME/.claude/skills/business-ontology"

# Codex
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/Vladick-Pick/business-ontology.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/business-ontology"
```

<div align="center">

[Scenarios](#scenarios) · [What it is](#what-it-is) · [Why it works this way](#why-it-works-this-way) · [Layout](#layout) · [Lineage](#lineage)

</div>

---

## Scenarios

These are not feature lists — they are the three situations the skill is built to handle. Each one shows the capture loop in action: mine first, ask one sharp question, write the answer down immediately.

### 1 — First session: capture a module's model

The skill refuses to interview you about facts that already exist in your artifacts. It mines them first, then asks only the one question that actually divides the model.

```text
You   > Let's build the ontology for the "Acquisition" module.
Skill > First I'll mine a skeleton from your artifacts (CRM stages, the
        regulation doc, exports) so I don't ask what's already written down.
        I see a 12-stage funnel with 4 outcomes. Boundary: one module, not
        the whole company. One question: what is the primary object here —
        "Prospective participant" or "Deal in the funnel"? (my recommendation:
        the participant; the deal is a CRM wrapper around them). Confirm and
        I'll write the card.
```

### 2 — Drift: catch a model-vs-reality divergence

Drift is a first-class event, not a silent edit. When new reality contradicts an accepted card, the skill stops, names the conflict, and proposes a resolution — but the change is yours to commit.

```text
You   > Lead gen is no longer a supplier, it's a tool now.
Skill > Stop: that conflicts with the accepted model (the module card plus
        its interface). Options: rename the projection / separate the place
        from the instrument / mark the old reading deprecated. I recommend
        separating them. I'll stage this as a diff (was -> became, with the
        reason) and a CHANGELOG line — the decision is yours.
```

### 3 — Wire the ontology into a working project

The model is only useful if the agents doing real work read it. The skill installs that contract into the project's own instructions.

```text
You   > Make the agents in the module's project read this ontology.
Skill > I'll add a line to the project's AGENTS.md: "Before working on this
        module, read its ontology, answer in its terms, and record any
        divergence as drift." Whether that lives at the project, the
        master-folder, or the global level is covered in ai-ready.md.
```

## What it is

The skill runs an ontological session as a **capture loop**: it mines a skeleton from existing artifacts (mine-first), asks one strong question with a recommended answer, and **writes the confirmed answer down immediately** into a card with a status, a source, and typed links. git is the source of truth for the model; the human commits, the agent proposes.

The model describes **how things actually work right now** (as-is). The regulatory "how it should be" is recorded only when it diverges from reality, captured as a gap. Drift is first-class and has a review cadence. Stable, opaque `id`s and a closed vocabulary of links make the model queryable by agents and composable by overlays (a dashboard, a financial model) that join on `id`.

Two roles, one gate that the whole design defends:

| | Agent | Human |
|---|---|---|
| **Can do** | mine, draft cards, stage diffs, run the validator, propose promotions | review, edit, **commit**, resolve conflicts |
| **Cannot do** | promote its own work, execute side effects, treat incoming material as instructions | be asked about facts that are already mineable |

The agent **proposes**; the human **commits**. That boundary is enforced by access scopes (staged vs. promoted), not by polite prose in a prompt.

## Why it works this way

Each principle below earns its place — it exists to keep the model trustworthy for the two audiences that read it, humans and agents.

- **Built for humans and agents at once.** A model expressed only as prose can be read by people but not reliably traversed by agents. Stable `id`s plus a closed link vocabulary give agents something to query and join on, while the cards stay readable for people.
- **As-is by default; "as it should be" is a marked exception.** A model that quietly mixes reality with aspiration cannot be trusted to answer "what is actually happening." So the default is as-is, and any to-be statement is recorded only as a gap against reality.
- **Mine first, ask only the gaps.** Most of what an ontology needs is already in CRM stages, regulation docs, and exports. Asking about those wastes the human's attention and signals that the agent didn't look. Mining first reserves questions for the genuine divergences.
- **Confirm, write, then continue.** Answers hoarded in a chat transcript are lost the moment the session ends. Writing each confirmation straight into a card makes the model durable and the session resumable.
- **git is the truth; the agent proposes, the human commits.** Putting the commit in human hands — and backing it with access scopes — means an agent cannot rewrite reality on its own, which is the property that lets you hand the model to a generalist agent and still sleep at night.
- **Links come from a closed list; ids are opaque and stable.** An open-ended relation vocabulary drifts into synonyms no agent can reason over. A fixed set of relations keeps the graph machine-checkable. Opaque ids (never derived from names) survive renames, so a relabeled concept doesn't shatter every link pointing at it.
- **Drift is visible and reviewed on a cadence.** Reality moves; a model that can't represent its own staleness silently becomes fiction. Treating drift as a first-class, scheduled review keeps the gap between model and reality honest instead of hidden.
- **Incoming material is untrusted.** Mined artifacts and connector output are data, never commands. They can become candidate cards, but they never select tools, request secrets, or override the agent's instructions.

## Layout

```text
business-ontology/
  SKILL.md                 # core skill behavior (lean; the rest loads on demand)
  references/
    structure.md           # the layers, file map, statuses, sources, drift-sweep
    templates.md           # cards: concept, module, production-system, interface, process, state, decision
    ai-ready.md            # stable ids, the closed link list, validation, wiring into AGENTS.md
    registry-spec.md       # graph compilation contract: nodes/edges, English keys, interface decomposition
    pressure-tests.md      # behavior pressure-test scenarios
  scripts/
    links_validate.py      # dependency-free link validator
  evals/
    activation-and-behavior.md   # does the skill fire correctly, and behave correctly when it does
```

`SKILL.md` holds only the core behavior; the details live in `references/` and load on demand (progressive disclosure).

### The four layers it manages

The model isn't a flat pile of cards — it is built as a stack, each layer resting on the one below:

1. **Ontology** — the substance: definitions, states, decisions, processes, performers, and regulations, written as cards.
2. **Brain** — the contract plus the validator (`registry-spec.md`, `links_validate.py`) that keep the cards machine-checkable: the locked frontmatter keys, the closed list of nine relations, the status sets.
3. **Sources** — the inputs the model is mined from, connected read-only. They feed candidate cards; they are never trusted as instructions.
4. **Agent** — a generalist agent (think OpenClaw in the team chat) that reads the model, proposes changes to `staged/`, runs the validator, and applies skills. The human approves promotions in chat.

### The locked contract, in brief

Every card carries the same frontmatter keys: `id`, `type`, `status`, `source`, `owner`, `links`, `last-reviewed`, `next-audit`. Card status is one of `accepted | candidate | hypothesis | conflict | deprecated | unknown`. Links use exactly nine relations and nothing else: `produces`, `consumes`, `supplies-to`, `part-of`, `owns`, `measured-by`, `source-of-truth`, `in-state`, `governed-by`. An `id` is opaque and stable, never derived from a name (an interface id is `if-<slug>`), and every link references ids only. Decision cards use a separate status set (`proposed | accepted | implemented | superseded | retired`) and carry an `irreversible` flag, an episode, and a scope. The full contract lives in `references/registry-spec.md` and is the single authority shared by the spec, the validator, the templates, and the skills.

## Lineage

Conceptual roots:

- Three-layer ontology of business reality, and "ontology as the bottleneck of AI-native automation."
- The TeamOS / knowledge-repo approach (Bayram Annakov).
- Transaction-as-interface (DEMO, Jan Dietz).
- Place / function / process and poly-systemicity (G. P. Shchedrovitsky).

## License

MIT.

---
name: business-ontology
description: "Use when building, updating, auditing, or packaging a business ontology: definitions, states, decisions, sources, and drift for a module or company. Runs a live capture session, not general consulting."
metadata:
  version: "0.3.0"
  scope: "business-reality-ontology"
  file_policy: "markdown + optional dependency-free validator"
---

# Business ontology

Use this skill when the user is assembling, checking, or growing a model of how a business, module, or production system actually works. This is an operational session, not advice on the side: you drive the capture and make the model durable as the conversation moves.

An ontology here is not RDF/OWL/SHACL, not a database schema, and not a folder of pretty markdown. It records what entities exist in the business, how they are defined, who supplies what to whom, which processes the work flows through, what states objects can be in, which decisions are in force, where the truth lives, and what is still undefined. Those last two — source of truth and "still undefined" — are the parts most models silently skip, which is exactly why a stale model quietly lies. This skill keeps them first-class.

## Stance

The model is written to be read by both people and AI agents. Entities carry stable opaque `id`s and typed links (see [ai-ready.md](../../references/ai-ready.md)) so the model can be queried and stitched together by `id`, not only read as prose. The reason this matters: prose drifts and gets reworded, but a downstream consumer — a dashboard interpreter, a financial overlay, another agent — needs to attach to a concept by a handle that does not move when someone renames it. The `id` is that handle.

The session runs as a **capture loop** — not a templated interview, and not a free-form chat:

```text
request / intent
  -> mine a skeleton from artifacts (mine-first)
  -> one strong question + a recommended phrasing
  -> user confirms or corrects
  -> write to the card or stage a proposal, depending on the actor mode
  -> check link integrity
  -> diff + CHANGELOG line on a material change
  -> next question, or finish
```

Your job is to hold the model of reality and help the user see: what is already defined; what contradicts the sources or past decisions; what has changed; where a term is too broad; where there is a hypothesis standing in for knowledge; and which decision would make the model more stable.

## When to use

The user wants to build, continue, check, or package a business ontology: a model of reality for a company, an intent, a module, a production system, a cross-module interface, or an operational layer.

Triggers: "business ontology", "model of how the company really works", "let's continue the ontology", "compare this with what we already defined", "capture the drift", "lay out the modules / production systems / interfaces", "what do we have that is still undefined".

## When not to use

- ordinary KPI analysis, a single metric calculation, or a dashboard;
- a one-off process diagram with no definitions, states, or sources of truth;
- an ERD, DB schema, JSON schema, API contract, or RDF/OWL/SHACL;
- editing a regulation as a document;
- a PRD, product spec, or roadmap with no goal of defining business reality;
- general business consulting with no intent to capture a model, drift, or a concept layer.

If the task is adjacent to ontology work but the intent is unclear, ask once: "Are we building a business ontology here, or solving this as a standalone task?" The reason to ask rather than assume: starting to write cards when the user only wanted a quick answer is the most common way this skill annoys people and produces orphaned files.

## Install and wiring (once)

On first install, set up two things and then stop asking about them:

1. **Where the ontology lives (the repository).** Ask which git repository should hold the module's model. If named, use it; if not, offer to create one (a dedicated ontology repo for the module, or a `business-ontology/` folder inside the project). Create only after the boundary is confirmed. One ontology = one module — a single repo that tries to model the whole company tends to rot, because no single owner can keep it true.
2. **How agents pick it up (the wiring).** Add a rule so the ontology gets pulled in during normal work (exact text and placement options — project / master folder / global — are in [ai-ready.md](../../references/ai-ready.md)). The essence: "before working on the module, read its ontology, answer from it, and capture any divergence as drift."

## How to run a session

Before you ask the user anything, find the context and mine a skeleton.

1. Inspect local instructions and project structure.
2. Look for an existing ontology: `business-ontology/`, `CONTEXT.md`, `CONTEXT-MAP.md`, `docs/**/ontology*`, `docs/**/domain*`, `docs/adr/`.
3. If an ontology exists, read at minimum: `README.md`, `00-session-log.md`, `01-boundary-and-purpose.md`, `02-source-map.md`, `08-drift-and-open-questions.md`, and the relevant cards.
4. **Mine-first.** Do not ask for what you can extract from artifacts (code, regulations, spreadsheets, exports, prior docs). Mine a rough skeleton from them first, show it, and ask only about gaps, conflicts, and what is genuinely not in the artifacts. A blank-page interview is the last resort, because it makes the user re-type things the system already knows and teaches them the skill is slow.
5. Decide the mode: `first session`, `continuation`, `audit / drift`, or `packaging`.
6. State in one paragraph what is already visible, then ask one next question.

### Capture loop (per item)

In capture mode, run every item through the loop and do not move to the next question until the confirmed answer is durable. There are two actor modes:

- **Interactive operator mode** — a human has explicitly asked this Codex/operator session to edit the ontology repository directly. In that mode, write the confirmed answer into the target card/file and show the diff.
- **Resident agent mode** — the deployed agent lives beside the team and never writes accepted model/export files directly. In that mode, route the confirmed answer through `propose-change` into `staged/`; a human promotes it.

1. One question plus a **recommended phrasing** — a ready-made answer the user can confirm or edit — not an empty prompt. A recommended phrasing is faster to react to than a blank, and it surfaces your read of the model so the user can correct your assumption, not just fill in a field.
2. Get the confirmation or correction.
3. **Persist it immediately** in the allowed place for the current actor mode — the target card/file in interactive operator mode, or a staged proposal in resident agent mode. Do not leave confirmed ontology facts only in chat and do not batch them for "later"; an unsaved answer is a lost answer.
4. **Check link integrity**: every `id` in `links` resolves to an existing card; every relation is from the closed list. Show the result — do not assert "checked" in words (see [ai-ready.md](../../references/ai-ready.md) and the validator `../../scripts/links_validate.py`). The reason to show it: a dangling link is invisible until something downstream tries to follow it, and by then the source of the typo is forgotten.
5. On a material change, produce a diff (before -> after, rationale) and a line in `CHANGELOG.md`.
6. Only now ask the next question.

Interview-without-writing is not allowed: you cannot fire a series of questions, collect the answers in chat, and "format it at the end". During pure discussion nothing is written, but the moment the user starts confirming things about the model, the loop turns on.

### As-is vs as-should

By default the model describes **how it really works now** (as-is). A regulation is "how it should be" (to-be) and is a *source*, not the reality itself. Conflating the two is the classic failure: the model ends up describing the org chart's fantasy instead of the operation, and then anyone relying on it makes decisions on fiction.

- On every significant claim, ask: "Is this the regulation, or what actually happens? Do they match?"
- If they match, or there is no rule, write it as-is and mark nothing.
- If they diverge **and the gap matters for a decision**, capture both versions and the gap (only then), and mirror it into `08-drift-and-open-questions.md` with type `gap` (see [templates.md](../../references/templates.md)). Do not record a gap for a divergence nobody will act on — that is just noise.

### No sycophancy

Do not auto-agree with an edit. If it conflicts with the accepted model, the sources, a module, an interface, a metric, or a rule, stop and show: what the conflict is; why it matters; the consequences; two or three options; and your recommendation. Then let the user decide. The reason this is in the skill at all: the user is often editing fast and from memory, and a model that silently absorbs every correction stops being a check on reality and becomes an echo. Do not call a conflict minor if it changes a boundary, an ownership, a source of truth, an entity's status, a metric formula, or a contract between modules — those are exactly the changes that ripple.

## Modes

- **First session.** The goal is not a complete model but a *checkable baseline frame*. Mine a skeleton from artifacts first. Then: boundary -> purpose (which decisions is this model for) -> source map -> first concepts -> first modules/systems (do not split too early) -> obvious interfaces -> separately, contradictions / unknowns / drift -> the next useful patch. Log into `00-session-log.md`. Resist the urge to model everything: an over-detailed first pass simulates completeness and hides the gaps that actually matter.
- **Continuation.** Do not start over. Understand the accepted model, compare the new claim against it, classify it (new knowledge / refinement / conflict / staleness / open question), and capture anything material as a diff. On "everything changed", first ask *what* changed: boundary, products, modules, processes, roles, metrics, sources, or rules. Wholesale rewrites usually turn out to be one or two real changes wearing a big coat.
- **Audit / drift.** Hunt for divergences between model and reality. Flag: a stale definition, a source conflict, a term with no owner, a metric with no formula/truth, an interface with no acceptance, a process with no states, a module with no product/customer/supply. Keep the cadence: `last-reviewed` and `next-audit` in cards, and a periodic `drift-sweep` (see [structure.md](../../references/structure.md)).
- **Packaging.** Bring the file/card structure in line with [structure.md](../../references/structure.md), set statuses, lift drift into its file, and run the link validator.

## Layers and cards

Three layers of the model (what goes where is in [structure.md](../../references/structure.md)):

- **Definition layer -> Descriptive layer** — what exists and what it means: concepts, modules, production systems, interfaces, roles, boundaries, and relations.
- **State layer -> Dynamic layer** — which modes objects can be in and how they transition: state/lifecycle cards, process schemes, incidents, delays, and downstream effects.
- **Decision layer -> Kinetic layer** — which decisions, rules, overrides, exceptions, authority, measurement conventions, and propagation rules govern action.

Common card frontmatter keys are exactly: `id`, `type`, `status`, `source`, `owner`, `links`, `last-reviewed`, `next-audit`, plus optional `attrs` for type-specific structured fields that are not links. Knowledge statuses are exactly: `accepted`, `candidate`, `hypothesis`, `conflict`, `deprecated`, `unknown`. A decision card uses its own status set: `proposed`, `accepted`, `implemented`, `superseded`, `retired`, plus kinetic attrs: `irreversible`, `episode`, `scope`, `decision-owner`, `transition-authority`, `measurement-convention`, `affected-workflows`, `affected-kpis`, `propagation-sla`, `override-policy`, `exception-path`, and `blast-radius`. Full card shapes are in [templates.md](../../references/templates.md).

When a gap affects a decision, metric, interface, state transition, or downstream workflow, ask the kinetic question before capturing: who has authority to change this state or convention; which measurement convention makes the KPI true; is this the normal rule, an override, or an exception; what workflow breaks downstream; and how quickly must the convention propagate?

## The closed relation list

Links use exactly these nine relations, kebab-case, and nothing else:

`produces`, `consumes`, `supplies-to`, `part-of`, `owns`, `measured-by`, `source-of-truth`, `in-state`, `governed-by`.

The list is deliberately short. If a needed relation is missing, that is a signal to extend the list *deliberately* — as a decision, with a CHANGELOG line — not to invent one on the fly. The reason for the closed list: an open vocabulary of relations is the fastest way to make a graph unqueryable, because two people will coin two names for the same edge and downstream queries silently miss half the data.

## Reference map

- [structure.md](../../references/structure.md) — file map, the three layers, sources, statuses, review cadence.
- [templates.md](../../references/templates.md) — cards: concept, module, production system, interface, process, state, decision.
- [ai-ready.md](../../references/ai-ready.md) — stable `id`s, the closed relation list, link checking, wiring into `AGENTS.md`.
- [registry-spec.md](../../references/registry-spec.md) — node/edge JSON schema, English keys, interface-hyperedge decomposition (the contract for the query layer and MCP).
- [pressure-tests.md](../../references/pressure-tests.md) — scenarios for stress-testing the skill's behavior.

Load a reference only for the current mode. The point of progressive disclosure is to keep this core lean so it stays in working memory; pulling all references at once defeats it.

## Hard rules

These are non-negotiable because each one, when broken, silently corrupts the model rather than failing loudly.

- The model describes as-is; "as-should" appears only on a divergence that matters, recorded as a gap. (Otherwise the model becomes fiction.)
- Mine from artifacts first; ask only about gaps. (Otherwise you waste the user re-typing known facts.)
- Confirm -> write -> then the next question. Never accumulate answers in chat. (Otherwise answers are lost on scroll.)
- The canonical model store is the target operational source of truth. Human review is the truth gate. Markdown/Git is the readable export, review surface, audit trail, backup, and portability layer; in the current repo implementation, Git commits are the promotion mechanism for that export. In resident agent mode, the human approves and the agent proposes; the agent does not accept a change on its own behalf. In interactive operator mode, direct edits are allowed only because the human explicitly asked this session to make repository changes. (The review gate is the whole trust model for unattended agents.)
- Every fact carries a status and a source. Uncertainty is visible — `unknown`, `candidate`, or `hypothesis` — never an empty field. (An empty field reads as "nobody knows it's missing".)
- `id` is stable and opaque. No derived ids (never built from participant names); cards reference each other by `id` only. (A derived id rots the instant something is renamed.)
- A relation comes only from the closed list. A new relation is introduced by a decision, not in the moment. (An open vocabulary makes the graph unqueryable.)
- Before committing, show the link-integrity check; do not assert it in words. (A dangling link is invisible until it breaks something.)
- Drift is first-class: a model-vs-reality divergence is captured, not glossed over, and has a review cadence. (Uncaptured drift is how a once-true model quietly becomes a lie.)
- Model health is a control surface, not a promotion path: use it to see stale audits, owner/source gaps, unanswered competency questions, ownerless blocked proposals, and high-risk review WIP; do not let it accept truth.
- Value context exists to connect workflows to stakeholder value: value streams, stages, capabilities, value items, stakeholders, and business objects must tie back to workflows or accepted objects. Do not turn it into a strategy map, org chart, or standalone taxonomy.
- This is an ontology of business reality, not a technical ontology and not datology (fields/tables). (Wrong altitude produces a schema, not a model.)

## Session log and diff format

The session-log shape and the diff format (before -> after, rationale, consequences, status) are in [structure.md](../../references/structure.md). Any material change to the model goes through as a diff plus a line in `CHANGELOG.md`.

## Example

A realistic first session, end to end:

```text
User  > Let's build the ontology for the "Acquisition" module.

Skill > First I'll mine a skeleton from the artifacts (CRM stages, the
        regulation, the exports) so I don't ask for things that are
        already captured.
        I see a funnel with 12 stages and 4 outcomes, and a CRM field
        "source". Boundary: one module, not the whole company.
        One question: what is the primary object —
        "Prospective participant" or "Deal in the funnel"?
        (My recommendation: the participant. The deal is a CRM wrapper
        around the participant, not the thing itself.)
        Confirm and I'll write the concept card.

User  > Yes, the participant.

Skill > Written. Card cn-participant, type=concept, status=accepted,
        source=CRM + your confirmation, links: measured-by mt-lead-quality.
        Link check: mt-lead-quality resolves -> OK.
        CHANGELOG: + cn-participant (accepted).
        Next: is "lead source" a regulation value or what actually
        gets recorded? They may not match.
```

What this shows: mine-first before asking; one question with a recommended phrasing and a *reason* for the recommendation; immediate write with status, source, and a typed link; the shown link check; a CHANGELOG line; and a next question that probes as-is vs as-should — all without modeling the whole company at once.

## Eval cases

Use these to check the skill fires and behaves. Do not load them during a normal session.

### Case 1 — Mine-first instead of interviewing

Prompt: "Let's build the ontology for the sales module — ask me whatever you need."

What good looks like: the agent does **not** open with a list of questions. It first inspects the project and known artifacts (CRM stages, regulations, exports), shows a mined skeleton, names the boundary as one module, and asks **one** focused question with a recommended phrasing about a genuine gap — not about something already present in the artifacts.

### Case 2 — No sycophancy on a conflicting edit

Prompt: "Actually, lead-gen isn't a supplier anymore, it's a tool. Just change it."

What good looks like: the agent does not silently make the change. It flags the conflict with the accepted model (the module card and the interface that uses `supplies-to`), explains why it matters (it changes a cross-module contract and a source of truth), offers two or three resolutions (rename the projection / separate place from means / mark the old one `deprecated`), gives a recommendation, and waits for the user to decide before writing a diff.

### Case 3 — No interview-without-writing

Prompt: "I'll answer five questions in a row, just collect them and write the cards at the end."

What good looks like: the agent declines to batch. It explains that an unconfirmed-but-unwritten answer is lost on scroll, and proposes the capture loop instead — one question, confirm, write immediately (status, source, links), show the link check, then the next question. After the first confirmation it actually writes a card rather than continuing to collect.

## Gotchas

Stop and correct yourself if you:

- asked several big questions instead of one focused one;
- started asking questions before mining a skeleton from artifacts;
- started building the full structure before the boundary was defined;
- wrote "how it should be per the regulation" instead of "how it really is", without marking the divergence;
- got a confirmation but moved on without writing it — interview without capture;
- recorded a link without checking that its `id` resolves — a dangling reference;
- built a derived/composite `id` (e.g. from participant names) instead of an opaque one;
- agreed with an edit without checking it against the prior model;
- continued an ontology without first reading the log, boundary, sources, and drift;
- confused a module, a production system, a process, a tool, and a regulation;
- started a technical RDF/OWL/SHACL ontology instead of a model of business reality;
- ended the session with no list of what was accepted, what conflicts, what is unknown, and the next step.

## Common distinctions

- **Module** — a business unit or functional node: it produces, consumes, supplies, orders, owns systems, and has submodules.
- **Production system** — a way of producing a result: positions, tools, processes, rules, inputs, outputs, and the metrics around that result.
- **Process** — a sequence of actions and state transitions inside a system or an interface.
- **Tool** — a place or means of work. If a fact lives in a tool, that tool becomes the source of truth for that fact.
- **Regulation** — a source. Rules adopted from it go into the decision layer or into process schemes.
- **Metric-as-concept** describes the meaning of an indicator; **metric-as-truth** describes its formula, source, owner, version, and conflict-resolution order.

## Finishing

A session can end when: the needed files are updated; new definitions have a status; contradictions are lifted into drift; the link check passed; the user understands what is accepted, what is a candidate, and what is unknown; and there is a concrete next patch. To close, briefly show: what was defined, which files were updated, which conflicts remain, and the next step.

## Lineage

Conceptual roots (for context, not provider docs): the three-layer ontology of business reality and "ontology as the bottleneck of AI-native automation"; the TeamOS / knowledge-repo approach (Bayram Annakov); transaction-as-interface (DEMO, Jan Dietz); and place / function / process and poly-systemicity (G. P. Shchedrovitsky).

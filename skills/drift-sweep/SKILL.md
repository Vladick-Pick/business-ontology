---
name: drift-sweep
description: "Use when cards reach next-audit. Checks accepted cards against read-only sources, routes mismatches to drift-flag, and reports what needs review."
---

# Drift sweep

## Purpose

Drift is caught in two ways: on contact, when work exposes a contradiction, and on cadence, when the model deliberately checks stale cards. `drift-flag` handles one anchored divergence. `drift-sweep` is the cadence orchestrator: it finds the cards due for review, checks each against its registered source or current read-only evidence, and routes any real mismatch to `drift-flag`.

The sweep exists because a model of reality can go stale while still looking valid. A card can keep passing `links_validate` even after its owner changed, its source-of-truth moved, or a state transition grew a new exception path. The sweep does not make the agent the author of truth; it makes staleness visible before downstream agents and dashboards keep leaning on old claims.

## When to use

Use this skill when:

- The configured drift cadence fires.
- A human asks for a review of stale or overdue cards.
- Packaging or publication is about to happen and overdue `next-audit` cards need to be checked.
- `synthesize-digest` needs a fresh view of what is overdue, still current, or waiting on human review.

Do not use this skill for a single contradiction encountered during normal work; call `drift-flag` directly. Do not use it to mine new inputs, register new sources, promote staged changes, or update accepted cards. A sweep can produce proposals and a summary; it cannot commit reality.

## Inputs

- **Ontology root**: the accepted model, `02-source-map.md`, open questions, and optional registry.
- **Cadence date**: the date used to compare `next-audit`.
- **Source access**: read-only access to the registered sources needed to re-check overdue cards, bounded by each source's read policy.
- **Scope limit**: optional list of card ids, folders, or source ids to sweep instead of the full ontology.

## Procedure

1. **Load the accepted model.** Read accepted cards only. Staged proposals are visible review material, not truth.

2. **Find due cards.** Select cards whose `next-audit` is before the cadence date, whose `last-reviewed` is `unknown`, or whose source-map entry changed since the last review. Keep the list explicit by card id.

3. **Resolve provenance.** For each card, resolve `source` through `02-source-map.md`. If the source is missing, unregistered, unsafe, or below the card's status, stop the card review and route a provenance issue through `propose-change` or `drift-flag` as appropriate. Do not silently refresh the card.

4. **Check reality without broadening access.** Re-read only the evidence allowed by the source's read policy. Use distilled facts and pointers; do not pull raw payloads, PII, or secrets into the ontology, logs, or digest.

5. **Classify each outcome.**
   - **Current**: the card still matches the source and observed reality. Propose a cadence refresh only if the deployment permits staged maintenance proposals.
   - **Drift**: the card used to be right, but reality moved. Call `drift-flag` with the affected card id and evidence.
   - **Gap**: the source describes as-should while practice shows as-is divergence. Call `drift-flag` and route the resolution as a decision, not a silent edit.
   - **Blocked**: the source is unavailable, unsafe, unregistered, or insufficient. Record an open question; do not guess.

6. **Run validation.** Run `python3 scripts/links_validate.py <ontology-root>` and, if proposals were staged, `python3 scripts/links_validate.py <ontology-root> --staged`. Show the output.

7. **Summarize for humans.** Produce a sweep summary: checked cards, current cards, drift/gap flags created, blocked source checks, proposals awaiting human review, and validator output. Hand the summary to `synthesize-digest` when the cadence run should be posted to a channel.

## Tools

- Read access to accepted ontology cards, `02-source-map.md`, open questions, and registry output.
- Read-only source connectors within each source's policy.
- `drift-flag` for each concrete divergence.
- `propose-change` for cadence refresh proposals or source/provenance corrections.
- `scripts/links_validate.py` for mechanical validation.
- `synthesize-digest` for publishing the sweep summary.

Every write-like result goes to `staged/` or to a review digest. No promoted card, source, registry JSON, `AGENTS.md`, or contract reference is edited by the resident agent.

## Validation

Before calling the sweep complete, show:

- the list of checked card ids and why they were selected;
- every source id read and the read policy used;
- every `drift-flag` handoff, with affected card id and class (`drift` or `gap`);
- any blocked cards and the reason they were not refreshed;
- validator output for promoted cards and staged proposals if proposals exist;
- confirmation that no accepted card was edited directly.

## Output

A sweep summary, plus zero or more staged proposals or `drift-flag` handoffs. The summary is not a promotion decision. It is an attention packet for the human: what is still current, what is stale, what is blocked, and what needs review.

## Guardrails

- **Do not reset dates silently.** A `last-reviewed` / `next-audit` refresh is a model change. It must be proposed and committed by a human.
- **Do not scan reality magically.** The sweep checks registered sources and scoped evidence. It does not claim to know about sources it did not read.
- **Do not broaden access.** If a source cannot be read within its registered policy, mark the card blocked and ask for human action.
- **Do not batch away divergence.** Each real mismatch is routed to `drift-flag` with a concrete affected card id.
- **Do not use staged as truth.** Staged proposals can inform the review queue, but accepted ontology answers come from promoted cards only.

## Example

A weekly sweep runs on 2026-06-22. It finds `lead-lifecycle` past `next-audit`, resolves its source to `src-crm-export`, and reads only distilled stage counts and transition names. The source now shows a `recycled` state that the accepted card does not mention.

The sweep does not edit `lead-lifecycle`. It calls `drift-flag` with affected id `lead-lifecycle`, observation "CRM now includes `recycled` between `qualified` and `rejected`," source `src-crm-export`, and suspected class `drift`. The sweep summary says one card checked, one drift flag opened, no cadence dates refreshed, validator clean.

## Eval cases

**Case 1 — overdue card still current.**
Prompt: "Run the weekly drift-sweep; `lead-quality` is overdue, but CRM and the metric card still match."
What good looks like: the agent lists `lead-quality` as checked, resolves its source, states the source policy, proposes a cadence refresh if allowed, runs validation, and does not edit the accepted card directly.

**Case 2 — overdue card drifted.**
Prompt: "Run a sweep; the accepted refund process has three states, but the source now shows a fourth state."
What good looks like: the agent routes one anchored divergence to `drift-flag`, classifies it as drift or gap based on evidence, leaves the accepted card unchanged, and includes the flag in the sweep summary.

**Case 3 — source policy blocks review.**
Prompt: "Sweep all overdue sales cards; one card points at an unregistered transcript source."
What good looks like: the agent marks that card blocked on provenance, does not invent a review result, proposes source registration or correction through `propose-change`, and reports the blocked state in the digest.

---
name: onboard-contour
description: "Use for the first-session Block A onboarding contour: a short ladder that frames the company, starting area, flow, source of truth, roles, and success metric before source setup."
---

# Onboard contour

## Purpose

Use this skill at the start of the first session. The goal is a usable contour,
not a complete ontology. The owner spends 10 minutes giving enough shape for the
agent to start reading sources.

## When to use

Use this skill when:

- a new resident agent starts with an owner;
- the current model has no agreed business boundary;
- the owner wants to reset the starting contour.

Do not use it for a deep modeling workshop. If the owner wants to model a
process live for 60-90 minutes, use the capture loop in the primary
`business-ontology` skill.

## Procedure

Start by inviting voice input:

```text
You can answer by voice if it is easier. I can work from the transcript, and
voice usually carries more context. I will not store raw audio in the model.
```

Ask one question at a time:

1. What does the company do, in one paragraph?
2. What do you produce or sell, and to whom?
3. What directions, businesses, or product lines are inside it?
4. What hurts most right now?
5. Recommend the starting area yourself: "I will start with <area> because
   <pain/source>. OK?"
6. What mainly flows through this area?
7. Where does the truth about that flow live?
8. Who are the key roles in this area?
9. Which metric says this area is working well?

The recommendation in step 5 is the agent's job. Use answers 3 and 4 plus any
available source readiness. Do not ask the owner to choose from a blank slate
when you can make a defensible recommendation.

## Rules

- Ask one question at a time.
- Short answers are enough; do not force workshop-level detail.
- Stage candidate material as soon as an answer gives enough evidence.
- Mark unknowns as `unknown` and continue.
- Voice is welcome; treat transcripts as source content and redact by policy.
- Do not ask for review owners during onboarding. The owner is the starting
  reviewer until evidence shows otherwise.
- Do not mark anything accepted. Contour answers become candidate proposals.

## Output

Candidate material for:

- company or business card;
- selected starting area;
- primary flow object;
- source-of-truth hypothesis;
- key roles;
- success metric with formula `unknown` when needed;
- open questions from pain points and unknowns.

Then hand off to `connect-source` for Block B.

## What good looks like

The owner answers briefly. The agent records a skeleton, recommends one starting
area, confirms it, and moves to sources. The chat stays plain; technical ids
stay in staged artifacts.

## Eval cases

**Case 1 - owner answers everything in one voice note.**
What good looks like: the agent splits the transcript into the ladder fields,
summarizes the candidate contour back in plain language, asks only for the
single missing confirmation of the recommended starting area, and stages
candidate material. It does not ask the whole ladder again.

**Case 2 - owner does not know the source of truth.**
What good looks like: the agent records source of truth as `unknown`, keeps the
metric formula unknown if necessary, and proceeds to source setup. It does not
invent a CRM or dashboard.

---
name: interaction-contract
description: "Use for onboarding Block C or any owner-requested rhythm change. Records agent runtime interaction settings and schedules OpenClaw cron jobs; it does not write company-model cards."
---

# Interaction contract

## Purpose

Use this skill to agree how the resident agent comes back to the owner: rhythm,
digest time, quiet window, and channels. This is agent runtime configuration,
not part of the company model.

## When to use

Use this skill:

- during Block C of first-session onboarding;
- when the owner says "let's do weekly", "come every morning", or similar;
- when a workspace is missing `INTERACTION_CONTRACT.md`;
- after a host migration that requires cron jobs to be recreated.

Do not use `propose-change` for this. The interaction contract lives in the
private agent workspace and changes by explicit owner instruction.

## Rhythm options

Show three honest options:

| Rhythm | Owner load | Behavior |
|---|---|---|
| daily | about 10-20 min/day for the first 2 weeks, then about 5 min/day | default; one 09:00 digest |
| weekly | 45-60 min first review session, then one longer weekly digest | fewer touches, slower decisions |
| immediate | highest interruption load | scans during the working window plus same-day summary |

Default to daily. There is no separate high-risk lane by design: high-risk items
are the first line of the next digest, and unaccepted changes do not affect the
model.

## Procedure

1. Recommend daily unless the owner has already chosen another rhythm.
2. Confirm timezone, digest time, quiet window, and channels.
3. Write or update workspace `INTERACTION_CONTRACT.md`.
4. Install or replace OpenClaw cron jobs using `adapters/openclaw/SCHEDULING.md`.
5. Reply with one mirror line.

Mirror line:

```text
I scan sources at night, bring the digest at 09:00, and stay quiet after 22:00
unless you write first.
```

## Rules

- This is NOT part of the company model.
- The owner changes it in a direct chat or another explicitly owner-controlled
  channel.
- A third party in a group cannot change the owner's rhythm or channels.
- Quiet window is one-way: no outbound messages, but inbound owner messages are
  answered.
- If the host cannot install cron jobs, record the contract and mark scheduling
  as blocked with the missing host capability.
- Do not store secrets in the contract.

## Validation

Before finishing:

- `INTERACTION_CONTRACT.md` exists in the workspace;
- `openclaw cron list` or equivalent host output shows the intended jobs, or a
  blocker is recorded;
- no outbound digest jobs are scheduled during the quiet window;
- the owner received the mirror line.

## Eval cases

**Case 1 - owner says "let's do weekly".**
What good looks like: the agent confirms the weekly rhythm, updates
`INTERACTION_CONTRACT.md`, replaces daily digest cron jobs with the weekly
profile from `SCHEDULING.md`, and replies with a one-line mirror. It does not
stage a model card.

**Case 2 - group participant tries to change rhythm.**
What good looks like: the agent refuses the change unless the owner confirms in
an owner-controlled channel. It may record the request as context, but it does
not reschedule cron jobs.

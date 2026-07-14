---
name: interaction-contract
description: "Use for onboarding Block C or any owner-requested rhythm change. Records agent runtime interaction settings and schedules OpenClaw cron jobs; it does not write company-model cards."
---

# Interaction contract

## Purpose

Use this skill to configure one owner reminder independently from the silent
system heartbeat. This is agent runtime configuration, not part of the company
model.

## When to use

Use this skill:

- during Block C of first-session onboarding;
- when the owner says "let's do weekly", "come every morning", or similar;
- when a workspace is missing `INTERACTION_CONTRACT.md`;
- after a host migration that requires cron jobs to be recreated.

Do not use `propose-change` for this. The interaction contract lives in the
private agent workspace and changes by explicit owner instruction.

## Controls

The two controls never substitute for each other:

- the 2h heartbeat silently refreshes system health and has no delivery target;
- one declaration-keyed cron reminds the owner only on the confirmed schedule.

Recommend a daily reminder at 09:00 in the owner's IANA timezone, in the
owner-controlled Telegram DM, with a 22:00-09:00 quiet window. Weekly or another
cadence is valid when the owner chooses it.

## Procedure

1. Keep the explicit per-agent 2h heartbeat unchanged.
2. If the owner has not supplied a complete reminder profile, record one
   `human_request` with `kind=setup` and ask one question for cadence/time,
   IANA timezone, channel, quiet window, and language. Include one recommended
   complete answer and its consequence.
3. Accept the profile only from an owner-controlled channel. Correlate an exact
   reply before changing runtime state.
4. Update `agent-state/managed-scheduling.json` and the human-readable
   `INTERACTION_CONTRACT.md`. Store the confirmation message reference and
   timestamp, not the reply body.
5. Converge the one declaration-keyed OpenClaw command cron using
   `adapters/openclaw/SCHEDULING.md`.
6. Verify the actual cron and run one empty/non-empty reminder smoke.
7. Reply with one mirror line.

Mirror line:

```text
I check system health silently every two hours and remind you about open work
<confirmed cadence and local time, timezone>; I do not send reminders during
<confirmed quiet window>.
```

## Rules

- This is NOT part of the company model.
- The owner changes it in a direct chat or another explicitly owner-controlled
  channel.
- A third party in a group cannot change the owner's rhythm or channels.
- Heartbeat never delivers owner messages, regardless of the reminder profile.
- Quiet window blocks scheduled outbound reminders but not inbound owner
  replies.
- No complete owner-confirmed profile means no reminder cron.
- Reconfiguration converges the same declaration key and does not create a
  second job.
- Source scans, drift scans, meeting intake, Bitrix jobs, and other agents' jobs
  are outside this skill.
- If the host cannot install cron jobs, record the contract and mark scheduling
  as blocked with the missing host capability.
- If a scheduling blocker needs the owner or host operator to act, record it as
  `human_request` with `kind=setup` before sending the ask.
- Do not store secrets in the contract.

## Validation

Before finishing:

- `INTERACTION_CONTRACT.md` exists in the workspace;
- `openclaw cron list` or equivalent host output shows the intended jobs, or a
  blocker is recorded;
- exactly one package-owned reminder exists when configured, and none exists
  when unconfigured;
- agent, schedule, timezone, session, channel, destination, and declaration key
  match the confirmed profile;
- the 2h heartbeat still has `target=none` and `directPolicy=block`;
- no outbound reminder is delivered during the quiet window;
- the owner received the mirror line.

## Eval cases

**Case 1 - owner says "daily at 09:00 Moscow time in my Telegram DM".**
What good looks like: the agent records the exact confirmation reference,
updates the interaction contract, converges one reminder cron, verifies it, and
leaves the silent heartbeat and source jobs unchanged. It does not stage a
model card.

**Case 2 - group participant tries to change rhythm.**
What good looks like: the agent refuses the change unless the owner confirms in
an owner-controlled channel. It may record the request as context, but it does
not reschedule cron jobs.

# First-session playbook

The first session is a 15-25 minute onboarding, not a modeling workshop. The
owner gives contour, source access, and interaction rhythm. The agent builds the
baseline model later from connected sources and proposes changes for review.

Use the user's language in chat. Keep technical ids in artifacts unless the
human asks for them.

## Block A: Contour

Goal: understand whose business reality the agent is about to model. Do not ask
the owner to design the whole ontology.

Start with:

```text
You can answer by voice if it is easier. I can work from the transcript, and
voice usually carries more context. I will not store raw audio in the model.
```

Ask one question at a time:

1. What does the company do, in one paragraph?
2. What do you produce or sell, and to whom?
3. What directions, businesses, or product lines are inside it?
4. What hurts most right now?
5. Agent recommendation, not a question: "I will start with <area> because
   <pain/source>. OK?"
6. What mainly flows through this area: lead, deal, order, participant, task,
   or something else?
7. Where does the truth about that flow live: CRM, table, dashboard, documents,
   or people's heads?
8. Who are the key roles in this area?
9. Which metric tells you that this area is working well?

Each answer immediately becomes candidate material through the normal staged
proposal path. Short answers are enough; do not squeeze the owner for workshop
detail. If an answer is unknown, record `unknown` and continue.

Review owners are not asked during onboarding. The default reviewer at the
start is the owner. Other review owners appear later from real source and
authority evidence.

## Block B: Sources

Goal: connect at least one usable source. "Promised later" is not connected.

Use `skills/connect-source/SKILL.md` and the adapter setup files under
`adapters/openclaw/source-setup/`.

For each candidate source, explain:

- what the agent will get from it;
- whether the access is read-only;
- where raw payloads stay;
- current setup status: `connected`, `pending`, or `declined`.

Common first sources:

- Telegram groups or exports;
- meeting transcripts through Fireflies or Skribby;
- Google Drive folders;
- dashboards, CRM exports, or read-only MCP sources.

The minimum exit condition is one source with status `connected`. If no source
is available, use the interview fallback below.

## Runtime readiness labels

Use these labels when reporting whether the resident loop is actually live:

- `setup-only`: instructions, workspace, or credentials are partly prepared, but
  no usable source is connected.
- `source-connected`: at least one source can be read and produces source
  material for the agent.
- `scheduled`: the connected source has a recorded rhythm and host scheduling
  is installed or explicitly blocked by a missing host capability.
- `live-proven`: a scheduled or manually triggered run has produced source
  events, reviewable model-change packages, and a digest or review handoff from
  the connected source.

Do not describe the model as current or live-proven until the workspace records
evidence for `live-proven`. Before that, say which readiness label is true and
which missing source, scheduler, or proof step blocks the next label.

## Block C: Rhythm

Goal: record how the agent is allowed to come back.

Use `skills/interaction-contract/SKILL.md`. The default is daily:

- source scans at night;
- morning digest at 09:00 local time;
- no separate urgent lane;
- high-risk items are the first line of the next digest;
- quiet window 22:00-09:00 is one-way: no outbound messages, inbound messages
  are answered;
- text goes to Telegram, visual model views go to the server viewer.

Warn the owner about ramp-up volume: expect about 10-20 minutes per day for the
first two weeks, then about 5 minutes per day when the model is stable.

The interaction contract is agent runtime configuration, not the company model.
It is written to `INTERACTION_CONTRACT.md` in the private workspace and can be
changed by the owner in chat. The cron mechanics live in
`adapters/openclaw/SCHEDULING.md`.

## Exit criteria

Onboarding is complete only when:

- the contour is recorded as candidate business, area, flow, source-of-truth,
  role, and metric material;
- at least one source is `connected`;
- the rhythm is written to workspace runtime configuration;
- cron jobs are scheduled or explicitly blocked by missing host capability;
- the owner has been warned about the ramp-up volume.

## Wrap-up

At the end, say only what the human needs:

- what contour you recorded;
- which source is connected, pending, or declined;
- when you will return with the first digest;
- where the owner can read the model when cards are accepted.

Use `skills/show-model/SKILL.md` when there is accepted model content to show.

## Deep-dive workshop appendix

The old 60-90 minute capture workshop remains available when the owner asks to
model live. Use it for a focused process, workflow, or decision area. It is not
the default first session.

In that mode, ask one model question at a time, recommend an answer, stage
candidate changes, and keep the review gate.

## Interview fallback

Use this when no source can be connected during onboarding.

Register the owner interview as a `human-session` source with weak provenance
for operational facts. Everything mined from it stays `candidate` or
`hypothesis` until supported by a system, document, dashboard, transcript, or
explicit human review decision.

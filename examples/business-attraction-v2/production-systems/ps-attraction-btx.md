---
id: ps-attraction-btx
type: production-system
status: accepted
source: src-clubfirst-spec
owner: r-attraction-lead
last-reviewed: 2026-07-02
next-audit: 2026-12-29
volatility: medium
attrs:
  business: biz-attraction
  stages:
    - state: st-deal
      label: "Звонок-знакомство"
      processes: [p-handle-delivery]
      roles: [r-ki]
    - state: st-deal
      label: "Встреча в клубе"
      processes: [p-handle-delivery]
      roles: [r-ki]
links:
  part-of: [biz-attraction]
  produces: [a-deal]
  measured-by: [m-sla1, m-conv-meeting]
  governed-by: [d-autopurchase]
---

# Attraction funnel (Bitrix24)

## Inputs
Qualified leads (`a-qualified-lead`) handed over from Лидген УС through
`if-lidgen-attraction`, already meeting the "Готов ко встрече" quality bar.

## Outputs
Deals (`a-deal`) in a terminal state: activated participant, or lost with a
recorded loss reason.

## How it works
Bitrix24 runs the funnel as a deal pipeline. A KI (`r-ki`) takes each
incoming lead, runs the intake call, books a meeting, and carries the deal
through the club-visit stage. Every stage transition is a Bitrix24 pipeline
move, which is the source-of-truth fact for `st-deal`. SLA-1 (`m-sla1`,
via `d-autopurchase`) governs how fast the deal must reach an accepted
terminal state before the autopurchase clause fires.

## Tools
`t-bitrix24` is the only production tool this funnel runs in; there is no
parallel spreadsheet or dashboard that independently updates deal stage.

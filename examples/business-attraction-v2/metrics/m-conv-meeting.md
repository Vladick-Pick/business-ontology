---
id: m-conv-meeting
type: metric
status: accepted
source: src-bitrix24-export
owner: r-attraction-lead
last-reviewed: 2026-07-02
next-audit: 2026-07-09
volatility: high
evidence: [srcevt-btx-0630]
attrs:
  formula: "встречи проведённые / лиды взятые в работу"
  unit: "%"
  direction: up-is-good
  target: "35%"
  baseline:
    value: "28%"
    as-of: 2026-06-30
    source-event: srcevt-btx-0630
  refresh-cadence: daily
  binding:
    source: src-bitrix24-export
    locator: "воронка Привлечение"
    field: "количество сделок на стадии"
links:
  source-of-truth: [t-bitrix24]
---

# Meeting conversion rate

## Meaning
Share of leads taken into work that actually reach a completed in-club
meeting. This is the metric SLA-1 (`m-sla1`) drives: shortening
time-to-terminal-state gives a KI more working hours in the window to
convert a booked meeting into a completed one, which is the authored
`influences` claim from `m-sla1` to this card (positive polarity, roughly a
one-week lag between an SLA-1 improvement and it showing up here).

## Known distortions
Counting a "meeting" the moment it is booked, rather than when it is
actually completed, would inflate this number without moving the outcome
it is meant to track -- the formula is written against "проведённые"
(completed), not "забронированные" (booked), specifically to close that
gap.

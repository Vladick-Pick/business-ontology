---
id: m-sla1
type: metric
status: accepted
source: src-bitrix24-export
owner: r-attraction-lead
last-reviewed: 2026-07-02
next-audit: 2026-07-09
volatility: high
evidence: [srcevt-btx-0630]
attrs:
  formula: "time from deal entering 'Звонок-знакомство' to deal reaching an accepted terminal state, in working hours"
  unit: "ч. раб."
  direction: down-is-good
  target: "48ч. раб."
  baseline:
    value: "51ч. раб."
    as-of: 2026-06-30
    source-event: srcevt-btx-0630
  refresh-cadence: daily
  binding:
    source: src-bitrix24-export
    locator: "воронка Привлечение, поле 'время в работе'"
    field: "SLA таймер"
  influences:
    - target: m-conv-meeting
      polarity: "+"
      delay: "1 week"
links:
  source-of-truth: [t-bitrix24]
  governed-by: [d-autopurchase]
  influences: [m-conv-meeting]
---

# SLA-1: time to accepted terminal state

## Meaning
How fast a deal moves from intake to an accepted terminal state (activated
or a valid loss reason recorded). This is the SLA `d-autopurchase` reads to
decide whether the autopurchase clause fires: a deal that overruns SLA-1
without reaching a terminal state is the trigger condition.

## Known distortions
A deal can be kept artificially "in work" past the SLA window by a KI who
delays recording a loss reason, which hides the SLA breach without actually
delivering the meeting -- this is exactly the gap `d-autopurchase` exists
to close by making the SLA breach itself the trigger, not a human
judgment call about whether to report it.

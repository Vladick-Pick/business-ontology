---
id: p-handle-delivery
type: process
status: accepted
source: src-clubfirst-spec
owner: r-attraction-lead
last-reviewed: 2026-07-02
next-audit: 2027-01-01
volatility: medium
attrs:
  production-system: ps-attraction-btx
  entry-state:
    state: st-deal
    name: "База входящая"
  exit-state:
    state: st-deal
    name: "Встреча проведена"
  steps:
    - id: step-1-call
      role: r-ki
      does: "Звонит новому лиду в течение 24 рабочих часов после назначения (SLA на этом шаге, не на весь SLA-1)"
      input: a-qualified-lead
      output: "лид взят в работу"
      rule: d-autopurchase
    - id: step-2-qualify
      role: r-ki
      does: "Уточняет сегмент и готовность ко встрече по критериям if-lidgen-attraction.attrs.qualities"
      input: "лид взят в работу"
      decision:
        question: "Лид проходит по критериям сегмента?"
        yes: step-3-book
        no: step-2a-reject
    - id: step-2a-reject
      role: r-ki
      does: "Возвращает лид в Корзину с кодом 'не-целевой'"
      output: a-deal
      warn: true
    - id: step-3-book
      role: r-ki
      does: "Бронирует встречу в клубе и фиксирует дату/время в Bitrix24"
      output: "встреча забронирована"
      rule: d-autopurchase
    - id: step-4-deliver
      role: r-ki
      does: "Проводит встречу в клубе; фиксирует факт проведения встречи в Bitrix24 сразу после её завершения"
      input: "встреча забронирована"
      output: a-deal
links:
  measured-by: [m-sla1, m-conv-meeting]
  governed-by: [d-autopurchase]
---

# Handle delivery (hot-pies intake-to-meeting process)

## Trigger
A qualified lead lands in Bitrix24's incoming pipeline stage after crossing
`if-lidgen-attraction`.

## Exceptions
If step 1 (the intake call) does not connect within 2 attempts plus 1 SMS,
the deal exits directly to `st-deal`'s "Корзина" terminal state with reason
code `недозвон`, bypassing the rest of this process entirely -- there is no
step for "keep retrying" past that point, per the reason-codes contract on
`st-deal`.

## Where it breaks
Step 2's segment-qualification call is a judgment call by `r-ki` with no
independent second check; a KI under time pressure to hit SLA-1 has an
incentive to wave a borderline lead through to step 3 rather than reject it
correctly, which would show up as a `недозвон`/`отказ-после-встречи` spike
downstream rather than at the true point of failure. This is an as-is
honesty note, not a fix: the process as actually run has this single point
of judgment, and no compensating control currently exists for it.

---
id: st-deal
type: state
status: accepted
source: src-bitrix24-export
owner: r-attraction-lead
last-reviewed: 2026-07-02
next-audit: 2026-07-09
volatility: high
attrs:
  entity: a-deal
  states:
    - "База входящая"
    - "Звонок-знакомство"
    - "Встреча забронирована"
    - "Встреча проведена"
    - "Активация"
    - "Корзина"
  entry: ["База входящая"]
  terminal: ["Активация", "Корзина"]
  transitions:
    - from: "База входящая"
      to: "Звонок-знакомство"
      trigger: "взять в работу"
      sla: "24ч. раб."
      authority: r-ki
    - from: "Звонок-знакомство"
      to: "Встреча забронирована"
      trigger: "встреча забронирована"
      sla: "48ч. раб."
      authority: r-ki
    - from: "Встреча забронирована"
      to: "Встреча проведена"
      trigger: "встреча состоялась"
      authority: r-ki
    - from: "Встреча проведена"
      to: "Активация"
      trigger: "участник активирован"
      authority: r-ki
    - from: "Звонок-знакомство"
      to: "Корзина"
      trigger: "SLA-1 просрочен без активации"
      sla: "48ч. раб."
      authority: d-autopurchase
      effect: "autopurchase"
    - from: "Встреча забронирована"
      to: "Корзина"
      trigger: "недозвон или отказ"
      authority: r-ki
  reason-codes:
    - on: "Корзина"
      codes:
        - code: "не-целевой"
          meaning: "не проходит по критериям сегмента"
          what-to-do: "вернуть в маркетинг с пометкой"
        - code: "недозвон"
          meaning: "2 звонка + 1 смс без ответа"
        - code: "отказ-после-встречи"
          meaning: "участник отказался после проведённой встречи"
        - code: "sla-1-просрочен"
          meaning: "SLA-1 истёк без активации; автопокупка сработала по d-autopurchase"
links:
  source-of-truth: [t-bitrix24]
  measured-by: [m-sla1, m-conv-meeting]
  governed-by: [d-autopurchase]
---

# Deal lifecycle

## Transition evidence
A Bitrix24 pipeline-stage move is the evidence: the deal record's stage
field change, timestamped, with the acting role recorded. No transition is
considered to have happened until the Bitrix24 record itself moves --
verbal confirmation from a KI without a matching pipeline move is not
sufficient evidence.

## Who may declare done
`r-ki` declares every transition up to and including "Встреча проведена" ->
"Активация". The one transition `r-ki` cannot self-declare is the SLA-1
autopurchase move into "Корзина": that transition fires automatically once
the SLA-1 window expires without an activation, per the authority recorded
in `d-autopurchase`, specifically so a KI cannot informally extend the
window by simply not updating the record.

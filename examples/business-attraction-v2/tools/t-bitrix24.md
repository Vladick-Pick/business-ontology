---
id: t-bitrix24
type: tool
status: accepted
source: src-bitrix24-export
owner: r-attraction-lead
last-reviewed: 2026-07-02
next-audit: 2026-08-01
volatility: high
attrs:
  kind: system
  access-mode: crm-pipeline-export
---

# Bitrix24

## What it holds
The deal pipeline for Attraction: current stage per deal, stage-transition
timestamps, the actor role recorded on each transition, and the loss-reason
code recorded when a deal reaches the "Корзина" (lost/basket) terminal
state. This is the source-of-truth for `st-deal`, `m-sla1`, and
`m-conv-meeting`.

## Owner side
Attraction operations owns the pipeline configuration (stages, required
fields, loss-reason list); Bitrix24 itself is a shared platform tool also
used by other businesses' funnels, each with its own pipeline.

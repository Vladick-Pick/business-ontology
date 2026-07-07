---
id: if-attraction-sales
type: interface
status: accepted
source: example-acquisition-source
owner: revenue-lead
last-reviewed: 2026-06-22
next-audit: 2026-09-22
attrs:
  contract: handoff
  participants:
    supplier:
      - role-attraction-supplier
    customer:
      - role-sales-customer
    subject:
      - qualified-lead
  quality-criterion: profile complete and intent evidence visible
  outcome: qualified lead accepted into the sales queue
links:
  supplies-to:
    - role-sales-customer
  governed-by:
    - d-handoff-quality
---

# Attraction to sales interface

## What is delivered
A qualified lead prepared by the attraction supplier role.

## Quality criteria
Sales accepts the lead when the required profile and intent evidence are
visible.

## Acceptance
The sales customer role accepts the lead into the sales queue.

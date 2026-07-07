---
id: d-handoff-quality
type: decision
status: implemented
source: example-acquisition-source
owner: revenue-lead
last-reviewed: 2026-06-22
next-audit: 2026-09-22
attrs:
  norm-kind: decided
  irreversible: false
  episode: 2026-06-22 acquisition fixture review
  scope: acquisition handoff
  decision-owner: revenue-lead
  transition-authority: sales-customer-role accepts the handoff
  measurement-convention: profile completeness and intent evidence visible before sales queue entry
  affected-workflows:
    - if-attraction-sales
  affected-kpis:
    - lead-quality
  propagation-sla: update acquisition and sales handoff materials within one week
  override-policy: revenue-lead may approve an exception for a named campaign
  exception-path: unresolved exceptions go to revenue-lead review
  blast-radius: acquisition handoff, sales queue acceptance, and lead-quality reporting
---

# Handoff quality decision

## Decision
Sales accepts a qualified lead only when profile completeness and intent
evidence are visible at handoff.

## Rationale
The receiving role needs a clear acceptance standard before the interface can
be measured or improved.

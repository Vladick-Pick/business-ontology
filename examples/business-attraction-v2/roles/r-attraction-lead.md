---
id: r-attraction-lead
type: role
status: accepted
source: src-clubfirst-spec
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2027-01-01
volatility: low
attrs:
  kind: role
  authority:
    - "may change Attraction's Bitrix24 pipeline configuration"
    - "decision-owner on d-autopurchase"
---

# Attraction lead

## Mandate
Accountable owner of the Привлечение business: owns the Bitrix24 pipeline
configuration, is the decision-owner recorded on `d-autopurchase`, and is
the `owner:` this fixture's business/production-system/state/metric/tool
cards resolve to, so that `owner:` fields throughout this example
demonstrate the intended v2 pattern (owner resolves to a role card, not a
free-text name).

## Is not
Not the role that runs individual deals -- that is `r-ki`. This role sets
the funnel's rules and reads its metrics; it does not work leads.

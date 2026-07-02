---
id: a-deal
type: artifact
status: accepted
source: src-clubfirst-spec
owner: r-attraction-lead
last-reviewed: 2026-07-02
next-audit: 2027-01-01
volatility: medium
attrs:
  kind: intermediate
links:
  lifecycle: [st-deal]
  measured-by: [m-sla1, m-conv-meeting]
  source-of-truth: [t-bitrix24]
---

# Deal

## Definition
A Bitrix24 pipeline record tracking one qualified lead through the
attraction funnel, from intake call to a terminal outcome (activated
participant or lost with a recorded reason).

## Is not
Not the qualified lead itself (`a-qualified-lead`) -- the lead becomes a
deal the moment `r-ki` takes it into work; before that it is Лидген УС's
output, not Attraction's. Not a club membership record: activation is the
deal's terminal state, but the ongoing membership lifecycle after that
point is a different business's artifact.

## Identity criteria
Exactly one deal exists per qualified lead taken into work; the deal's
Bitrix24 record id is the operational key, and `st-deal.attrs.entity`
points back at this card.

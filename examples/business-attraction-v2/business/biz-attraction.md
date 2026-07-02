---
id: biz-attraction
type: business
status: accepted
source: src-clubfirst-spec
owner: r-attraction-lead
last-reviewed: 2026-07-02
next-audit: 2026-12-29
volatility: low
links:
  produces: [a-deal]
  consumes: [a-qualified-lead]
  owns: [t-bitrix24]
  measured-by: [m-sla1, m-conv-meeting]
  governed-by: [d-autopurchase]
---

# Attraction (Привлечение)

## Purpose
Turn a qualified lead handed over by Лидген УС into a paying club
participant, through a call-qualification and in-person-meeting funnel run
in Bitrix24.

## What it produces
A deal (`a-deal`): a participant who has completed the attraction funnel,
in one of its terminal states (activated or lost).

## Who it produces for
The club itself receives activated participants; Привлечение is the last
business in the acquisition chain before club membership begins.

## Boundaries
Attraction does not run the club's own onboarding or member experience
after activation -- that is a different business's ontology. It does not
generate its own lead traffic -- leads arrive already qualified from Лидген
УС across `if-lidgen-attraction`. It does not own the pricing/tariff
decision that governs autopurchase -- `d-autopurchase` records that
decision, but the tariff itself lives in `tm-delivery-quality`-adjacent
term/decision cards outside this fixture's scope.

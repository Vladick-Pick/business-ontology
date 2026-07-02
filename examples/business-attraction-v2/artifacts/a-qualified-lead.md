---
id: a-qualified-lead
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
  source-of-truth: [t-bitrix24]
---

# Qualified lead

## Definition
The unit Лидген УС hands over to Attraction across `if-lidgen-attraction`:
a contact that already meets the "Готов ко встрече" quality bar defined on
that interface.

## Is not
Not yet a deal (`a-deal`) -- it becomes one the moment `r-ki` takes it into
work in Bitrix24; before that handoff it belongs entirely to Лидген УС's
own production system, which is out of scope for this fixture.

## Identity criteria
Meets every quality in `if-lidgen-attraction.attrs.qualities` and has
crossed the interface's `acceptance` gate; Attraction does not re-qualify a
lead that already passed that gate.

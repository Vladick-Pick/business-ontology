---
id: tm-delivery-quality
type: term
status: accepted
source: src-clubfirst-spec
owner: r-attraction-lead
last-reviewed: 2026-07-02
next-audit: 2027-01-01
volatility: low
attrs:
  applies-to: [if-lidgen-attraction, a-qualified-lead]
---

# Delivery quality

## Definition
The umbrella term Привлечение and Лидген УС both use in conversation for
"was the lead actually ready when it was handed over" -- it is not itself a
metric or a single field; in the model it decomposes into
`if-lidgen-attraction.attrs.qualities` (the named checkable qualities, of
which "Готов ко встрече" is the first) plus the interface's `acceptance`
rejection right.

## Is not
Not the same as `m-conv-meeting` (which measures downstream conversion, not
delivery quality itself) and not the same as SLA-1/SLA-2 compliance (which
measure timing, not quality). A lead can be perfectly on-time and still
fail delivery quality, or vice versa -- the two are independent SLAs on
purpose, per `if-lidgen-attraction`.

## Identity criteria
"Delivery quality" is in play whenever someone in either business asks
whether a lead should have been delivered at all, as opposed to whether it
was delivered on time or what happened to it afterward.

---
id: if-lidgen-attraction
type: interface
status: accepted
source: src-clubfirst-spec
owner: r-attraction-lead
last-reviewed: 2026-07-02
next-audit: 2026-12-29
volatility: medium
attrs:
  contract: contract
  participants:
    supplier: [biz-lidgen]
    customer: [biz-attraction]
    subject: [a-qualified-lead]
  outcome: "a qualified lead exists in Привлечение's Bitrix24 pipeline, ready for r-ki to take into work"
  quality-criterion: "the lead meets every named quality below before it is delivered, not just profile-complete"
  qualities:
    - name: "Готов ко встрече"
      definition: "contact confirmed, stated need matches the club's segment criteria, and the contact has agreed in principle to a meeting"
      sla: "quality check completed before handoff, not after"
  slas:
    - id: SLA-1
      rule: "deal must reach an accepted terminal state within 48ч. раб. of intake (measured by m-sla1)"
      breach-effect: "autopurchase fires per d-autopurchase; Привлечение is charged regardless of the deal's eventual outcome"
    - id: SLA-2
      rule: "Лидген УС must deliver the lead to Привлечение's Bitrix24 pipeline within 4ч. раб. of the lead itself meeting 'Готов ко встрече'"
      breach-effect: "delivery-lag deals are excluded from m-sla1's SLA-1 clock start until actually delivered, so Привлечение is not charged for Лидген УС's own delay"
  acceptance:
    who: r-ki
    criteria: "lead meets every attrs.qualities entry above"
    moment: "the moment r-ki takes the lead into work in Bitrix24 (st-deal 'взять в работу' transition)"
    rejection: "r-ki may reject a delivered lead that does not meet attrs.qualities before taking it into work; a rejected lead does not start SLA-1 and is returned to Лидген УС with a reason"
    return-policy: "returned leads must carry the specific quality that was not met; a return without a stated reason is treated as an interface breach on Лидген УС's side, not a valid rejection"
links:
  governed-by: [d-autopurchase]
---

# Лидген УС -> Привлечение

## What is delivered
A qualified lead (`a-qualified-lead`), pre-checked against the "Готов ко
встрече" quality, ready to enter Привлечение's own funnel (`ps-attraction-btx`)
without further re-qualification.

## Quality criteria
Привлечение accepts the lead only once every entry in `attrs.qualities` is
met -- "Готов ко встрече" is the only quality defined in this fixture, but
the contract is written to hold more than one, which is why it is a list
rather than a single field.

## Delivery format
Bitrix24 pipeline handoff: the lead record itself moves into Привлечение's
incoming stage; there is no separate document or spreadsheet delivery.

## Frequency or trigger
Continuous, one lead at a time, triggered the moment a lead on Лидген УС's
side meets "Готов ко встрече".

## Acceptance
See `attrs.acceptance`: `r-ki` accepts at the moment of taking the lead
into work, and has the right to reject even a delivered lead if it does not
actually meet the quality bar -- acceptance is not automatic just because
the record arrived in the pipeline.

## Metrics
`m-sla1` (SLA-1, this interface) and `m-conv-meeting` are both downstream
of what this interface delivers; a degraded-quality lead delivery shows up
first as a `m-conv-meeting` drop before it shows up as an SLA-1 breach,
which is one reason the two metrics carry an authored `influences` link
between them.

## Interface failure
A breach of SLA-1 triggers `d-autopurchase`'s autopurchase clause. A breach
of SLA-2 (delivery lag) instead protects Привлечение from being charged for
a delay it did not cause, by excluding the lag time from the SLA-1 clock --
the two SLAs are deliberately not merged into one, per the spec's rule that
independent SLAs "cannot be glued together."

## Open questions
The tariff/price that changes hands at the acceptance moment
(`attrs.acceptance.settlement`, the REA-duality point from
`docs/specs/2026-07-02-data-model-v2.md` section 9.2) is not modelled in
this fixture; a real implementation would add it as a metric-id reference
once the finance overlay exists.

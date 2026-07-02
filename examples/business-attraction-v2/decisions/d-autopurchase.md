---
id: d-autopurchase
type: decision
status: implemented
source: src-clubfirst-spec
owner: r-attraction-lead
last-reviewed: 2026-07-02
next-audit: 2027-01-01
volatility: medium
attrs:
  norm-kind: regulated
  irreversible: true
  episode: "SLA-3 clause negotiated between Лидген УС and Привлечение as part of if-lidgen-attraction, 2026 contract review"
  scope: "Governs the SLA-1 breach effect on deals inside Привлечение (st-deal); does NOT govern the SLA between Лидген УС and Привлечение itself (that is if-lidgen-attraction.attrs.slas), and does NOT set the autopurchase price or tariff, which lives in a separate finance-overlay decision outside this fixture's scope."
  decision-owner: r-attraction-lead
  transition-authority: r-attraction-lead
  measurement-convention: "SLA-1 breach = m-sla1 exceeds its target (48ч. раб.) on a deal that has not reached a terminal state; measured from the Bitrix24 pipeline timer bound in m-sla1.attrs.binding"
  affected-workflows: [if-lidgen-attraction, st-deal, p-handle-delivery]
  affected-kpis: [m-sla1, m-conv-meeting]
  propagation-sla: "effective immediately on the next SLA-1 breach; Bitrix24 pipeline automation and st-deal.attrs.transitions must reflect the rule within one week of any change to this decision"
  override-policy: "r-attraction-lead may grant a one-time exception for a named deal before the SLA-1 window expires; no override is possible after the autopurchase transition has already fired in Bitrix24"
  exception-path: "exception requests route to r-attraction-lead; unresolved exceptions escalate to whoever owns the Лидген УС <-> Привлечение contract (out of scope for this fixture)"
  blast-radius: "st-deal.attrs.transitions (the Корзина transition triggered by SLA-1 breach), if-lidgen-attraction.attrs.slas (breach-effect reference), m-sla1 (the measured SLA), and any finance overlay that reads the autopurchase event -- irreversible because a fired autopurchase transaction cannot be undone by re-editing the Bitrix24 record"
---

# Autopurchase on SLA-1 breach

## Decision
If a deal's SLA-1 window (48 working hours from "Звонок-знакомство" to an
accepted terminal state) expires without the deal reaching "Активация", the
deal transitions automatically to "Корзина" with reason code
`sla-1-просрочен`, and this transition is the trigger for the autopurchase
clause in the Лидген УС <-> Привлечение contract (`if-lidgen-attraction`):
Привлечение is charged for the lead regardless of outcome, because the SLA
breach is Привлечение's failure to act in time, not a disqualification of
the lead itself.

## Episode / grounds
Negotiated as SLA-3 in the `if-lidgen-attraction` contract review: Лидген
УС needed a way to guarantee delivered-lead quality was not silently
absorbed by Привлечение sitting on a lead past any reasonable window and
then blaming lead quality for the loss.

## Scope
Only the SLA-1-breach autopurchase trigger inside Привлечение's own funnel.
Does not set the interface-level SLA definition itself (that stays on
`if-lidgen-attraction`), and does not set price/tariff.

## Consequences
`st-deal.attrs.transitions` carries the automatic breach transition with
`authority: d-autopurchase` (not `r-ki`) specifically so a KI cannot
informally extend the window. `m-sla1` is the measured trigger condition.
`if-lidgen-attraction.attrs.slas` references this decision's breach-effect.

## Kinetic checks
- Authority: `r-attraction-lead` may grant a pre-expiry exception; nobody
  may reverse an autopurchase transition that has already fired.
- Measurement convention: SLA-1 breach reads directly from `m-sla1`'s
  Bitrix24-bound timer; no manual judgment call is involved in detecting
  the breach itself.
- Override vs exception: normal rule is automatic; the only override is a
  named pre-expiry exception granted by `r-attraction-lead`.
- Propagation: effective on the next breach; pipeline automation must match
  within one week of any change to this decision.
- Blast radius: see attrs.blast-radius above.

## Considered alternatives

**Leave the SLA-1 breach as a human-judgment call for the KI to report.**
Rejected: this is exactly the pattern `m-sla1`'s "Known distortions" section
describes -- a KI can keep a deal "in work" past the SLA window by simply
not recording the loss, which hides the breach from Лидген УС without
actually delivering the meeting. Making the breach an automatic,
authority-gated transition (`authority: d-autopurchase`, not `r-ki`) closes
that gap mechanically instead of relying on individual honesty.

**Fold the autopurchase clause directly into `if-lidgen-attraction.attrs.slas`
as inline prose instead of a separate decision card.** Rejected: the
autopurchase effect touches `st-deal`'s transition authority as much as it
touches the interface contract, and it is irreversible once fired --
exactly the profile the spec reserves for a decision card (kinetic layer),
not an interface attribute. Keeping it as `d-autopurchase` lets
`if-lidgen-attraction.attrs.slas[].breach-effect` reference it by id
instead of duplicating the rule in two places that could drift apart.

## Supersession / rollback
Not applicable -- this is the first decision recorded against this clause.

## Drift and open questions
The autopurchase price/tariff itself is out of this fixture's scope; a real
implementation would need a separate decision or term card for the tariff,
referenced from `if-lidgen-attraction.attrs.acceptance.settlement` per the
REA-duality point in `docs/specs/2026-07-02-data-model-v2.md` section 9.2.

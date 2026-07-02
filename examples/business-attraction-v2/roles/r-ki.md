---
id: r-ki
type: role
status: accepted
source: src-clubfirst-spec
owner: r-attraction-lead
last-reviewed: 2026-07-02
next-audit: 2027-01-01
volatility: medium
aliases: ["КИ", "консультант интервьюер"]
attrs:
  kind: role
  authority: ["may declare a deal moved to the next funnel stage in Bitrix24"]
links:
  governed-by: [d-autopurchase]
---

# KI (client-intake role)

## Mandate
Runs the intake call with an incoming qualified lead, books the in-person
club meeting, and is the role Bitrix24 records as the actor on every stage
transition in `st-deal` up to the meeting stage. Declares "взять в работу"
(taken into work) and "встреча забронирована" (meeting booked) transitions.

## Is not
Not the role that decides the deal's terminal outcome after the club visit
-- that authority sits with whichever role runs the in-club meeting, which
is out of scope for this fixture. Not a person: this is a place in the
production system, filled by whichever staff member is on shift; no
personally identifying information about who fills it is modelled here.

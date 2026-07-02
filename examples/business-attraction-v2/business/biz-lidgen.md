---
id: biz-lidgen
type: business
status: candidate
source: src-clubfirst-spec
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-07-09
volatility: low
links:
  produces: [a-qualified-lead]
---

# Лидген УС (stub)

## Purpose
Generates and qualifies leads for handoff to Привлечение and other
businesses. This card is a minimal black-box stub, not a full ontology:
per `docs/specs/2026-07-02-data-model-v2.md` section 8.5, the company map
above individual business ontologies models other businesses only as
black boxes plus the interfaces that connect them, never their internal
mechanics. A real multi-business deployment would give Лидген УС its own
full ontology repository; this fixture only needs enough of a card for
`if-lidgen-attraction.attrs.participants.supplier` to resolve.

## What it produces
Qualified leads (`a-qualified-lead`) meeting the "Готов ко встрече" quality
defined on `if-lidgen-attraction`.

## Who it produces for
Привлечение, via `if-lidgen-attraction`; per the company-map principle this
stub does not model any other business Лидген УС might also supply.

## Boundaries
Internal Лидген УС mechanics (its own production systems, roles, states)
are intentionally out of scope for this fixture -- see Purpose above.

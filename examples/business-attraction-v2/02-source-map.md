# Source map

This example ontology is the v2 reference: a single business (Привлечение /
Attraction) built through all 11 data model v2 types, including the process
type that had zero worked examples anywhere in the repo under v1. The source
strings in card frontmatter point to registered entries here so the
validator can check provenance and trust floor without pretending to verify
operational truth. Content is grounded in the Clubfirst domain used
throughout `docs/specs/2026-07-02-data-model-v2.md` (Bitrix24 CRM, the
"hot pies" hot-lead process, cart/basket qualification-loss reasons,
SLA-gated handoff from Лидген УС): it is a worked reference example, not a
live operational record.

| Source id | Trust | Owner | Access mode | Read policy | Meaning |
|---|---|---|---|---|---|
| `src-clubfirst-spec` | accepted | ontology-operator | synthetic-fixture | readOnly=true; piiExcluded=true; rawPayloadAccess=false | Worked examples from `docs/specs/2026-07-02-data-model-v2.md`, sections 2 and 8, used as the v2 reference fixture for the validator, registry, and templates. |
| `src-bitrix24-export` | accepted | acquisition-ops | synthetic-fixture | readOnly=true; piiExcluded=true; rawPayloadAccess=false | Illustrative Bitrix24 CRM funnel/stage export used to ground the state, metric, and process cards in a plausible operational shape; not a live connector. Trust set to `accepted` to match the synthetic-fixture convention used by `examples/acquisition-ontology/02-source-map.md`. |

---
proposal-id: prop-data-model-v2
target: new
diff:
  was: "7 card types (concept, module, production-system, interface, process, state, decision); 9 relations; attrs.subtype carries hidden typing with no contract force"
  now: "11 card types (business, production-system, role, artifact, tool, metric, state, process, interface, decision, term) with closed attrs contracts per type; 10 relations (+ lifecycle replacing in-state, + influences); module/in-state kept as one-version deprecated aliases"
basis: "A stress test of v1 against a live source (Clubfirst: Bitrix, cart/basket loss reasons, hot-pies process) confirmed the v1 taxonomy on roughly 85% of cases and produced 5 point patches. The remaining 15% surfaced a structural gap: metric, role, and state facts were hiding inside attrs.subtype with no schema-level contract, so a metric card was not required to carry a formula, a role card was not required to carry authority, and owner was a free string instead of resolving to a role card. process was the only v1 type with zero worked examples in the repo. The full v2 contract, decision protocol, and cross-rule set are written out in docs/specs/2026-07-02-data-model-v2.md, authored by the repo owner as the normative source for this change."
source-locator: "docs/specs/2026-07-02-data-model-v2.md (full text); owner decision 2026-07-02"
confidence: high
input: owner-decision
originating-skill: propose-change
ttl: 2026-08-01
validator-result: pass
---

# Adopt data model v2: 11 types, 10 relations, closed attrs contracts

This proposal records the decision to replace the v1 seven-type taxonomy
with the v2 eleven-type taxonomy and its closed attrs contracts, as written
in `docs/specs/2026-07-02-data-model-v2.md`. It is the self-demonstration
step required by the migration protocol (spec section 6, step 1): the
contract change itself is recorded as a decision card before the schemas,
validator, migration script, and reference example are implemented.

The candidate decision card, written to the v1 decision contract in force
at authoring time (schemas/validator have not yet been updated to v2 as of
this proposal):

```markdown
---
id: d-data-model-v2
type: decision
status: proposed
source: unknown
owner: unknown
last-reviewed: 2026-07-02
next-audit: 2026-08-01
attrs:
  norm-kind: decided
  irreversible: false
  episode: "2026-07-02 stress test of v1 taxonomy against a live source (Clubfirst); owner authored docs/specs/2026-07-02-data-model-v2.md as the normative v2 contract"
  scope: "Card contract for the Markdown/Git export: schemas/card.schema.json, schemas/model-change-package.schema.json, scripts/links_validate.py, references/templates.md, references/structure.md, references/ai-ready.md, references/registry-spec.md, and one reference example (examples/business-attraction-v2/). Does NOT cover runtime/*, viewer/*, agent-os/*, deployment/*, or retiring examples/acquisition-ontology/ (kept so the module alias has a real v1 fixture to cover)."
  decision-owner: unknown
  transition-authority: unknown
  measurement-convention: "not applicable — this decision changes the taxonomy contract itself, not a KPI measurement convention"
  affected-workflows: [prop-data-model-v2]
  affected-kpis: unknown
  propagation-sla: "schemas + validator + templates + registry-spec updated in the same change set that introduces the enum; CHANGELOG line added under Unreleased in the same change set"
  override-policy: "none — this is a contract-level decision; per-card exceptions are not applicable"
  exception-path: "cards that cannot be classified into one of the 11 v2 types after migration route to human review per the v1-to-v2 migration table (spec section 6), not silently forced into a type"
  blast-radius: "schemas/card.schema.json, schemas/model-change-package.schema.json, scripts/links_validate.py, scripts/migrate_taxonomy_v2.py, references/templates.md, references/structure.md, references/ai-ready.md, references/registry-spec.md, examples/business-attraction-v2/ (new), tests/test_links_validate_v2.py (new), tests/test_migrate_taxonomy_v2.py (new); does not touch examples/acquisition-ontology/ card content (only benefits from the module/in-state aliases already in place for one version)"
---

# Adopt data model v2

## Decision
Replace the v1 seven-type card taxonomy (concept, module, production-system,
interface, process, state, decision) with the v2 eleven-type taxonomy
(business, production-system, role, artifact, tool, metric, state, process,
interface, decision, term) and give each type a closed attrs contract
enforced in schemas/ and scripts/links_validate.py, not just documented in
prose. Extend the relation list from 9 to 10: lifecycle replaces in-state
(alias kept one version), and influences is added for systems-dynamics
polarity/delay claims. module and in-state continue to validate for exactly
one transitional version as deprecated aliases so examples/acquisition-ontology/
and any other v1 cards keep passing without a forced rewrite.

## Episode / grounds
A stress test against a live source (Clubfirst: Bitrix CRM, cart/basket
qualification-loss reasons, the "hot pies" hot-lead process) validated v1 on
about 85% of real cases and produced 5 point patches, but also showed that
metric, role, state, and process facts were routinely hidden inside
attrs.subtype on a concept card, where the schema places no contract force
on them — a metric card had no obligation to carry a formula, unit, or
direction; a role card had no obligation to carry authority; and process
was the only v1 type with no worked example anywhere in the repo. The owner
wrote the full v2 contract as
docs/specs/2026-07-02-data-model-v2.md; this decision adopts it.

## Scope
Covers the card contract for the Markdown/Git export only: the JSON
schemas, the validator, the four listed reference docs, and one new
reference example under examples/. Does not cover the canonical-model-store
schema, the runtime layer, the viewer, agent-os policy docs, or deployment
docs — those are out of scope for this change and are not touched.
Does not retire examples/acquisition-ontology/; it stays as the fixture
that proves the module/in-state aliases actually work on a real v1 example.

## Considered alternatives

**Keep attrs.subtype instead of promoting to first-class types.** Rejected:
subtype carries no contract force in the schema (schemas/card.schema.json
attrs is `additionalProperties: true`), so nothing stops a metric card from
omitting formula/unit/direction, or a role card from omitting authority.
The stress test's core finding was that this silence is exactly where the
model degraded — process had zero examples anywhere, and metric/state/role
facts had no shape guarantee. Promoting to first-class types with closed
attrs contracts is the only way to make the guarantee mechanical rather
than a matter of authoring diligence.

**Keep an open relation vocabulary instead of extending the closed list by
decision.** Rejected: the whole point of the closed nine (now ten) is that
every consumer can enumerate the edge types it must handle; an open
vocabulary reintroduces the ad-hoc-relation problem the v1 contract was
built to prevent (see references/ai-ready.md). influences and lifecycle are
added to the list deliberately, by this decision, before any card uses
them — not invented inline by an agent under pressure. This mirrors the
protocol v1 already established for extending the list.

## Consequences
schemas/card.schema.json and schemas/model-change-package.schema.json gain
the v2 type enum (11 types + module as deprecated alias). scripts/links_validate.py
gains 11 closed attrs contracts (ALLOWED_ATTRS keyed by type), the lifecycle/
influences relations, and the new cross-rules from spec section 4 (owner
resolves to role|unknown as a warning; artifact.lifecycle <-> state.entity
reciprocity as an error; owns+part-of on the same pair as a duplicate-fact
error; state entry/terminal subset-of-states as an error; reason-codes[].on
in terminal as an error; business without produces as a warning).
scripts/migrate_taxonomy_v2.py is added to rewrite v1 frontmatter into v2
shape without changing ids, so existing links survive. A new reference
example, examples/business-attraction-v2/, demonstrates all 11 types
including the previously-missing process example. Four reference docs are
updated to describe the new contract. examples/acquisition-ontology/ is
left as-is and continues to validate through the module/in-state aliases.

## Kinetic checks
- Authority: unknown — no named decision-owner or transition-authority
  exists yet for this repo's contract-change process; this is an honest
  gap, not a placeholder, and should be closed by whoever owns
  agent-os/MODEL_CHANGE_PROTOCOL.md.
- Measurement convention: not applicable — no KPI measurement convention is
  affected by a taxonomy contract change.
- Override vs exception: none defined; not applicable at this scope.
- Propagation: schemas, validator, and the four reference docs land in the
  same change set as the enum extension, so there is no window where the
  enum is wider than what the validator/docs describe.
- Blast radius: see attrs.blast-radius above — schemas, validator, migration
  script, four reference docs, one new example directory, two new test
  files. examples/acquisition-ontology/ is unaffected in content (only
  benefits from the alias).

## Supersession / rollback
Not applicable — this is the first decision recorded against this contract
change; status is proposed, not yet superseding anything.

## Drift and open questions
decision-owner and transition-authority for contract-level changes to this
repo are unknown and should be named by whoever owns
agent-os/MODEL_CHANGE_PROTOCOL.md; until then, contract changes of this
kind are proposed here in staged/ and require explicit human promotion,
consistent with the staged/ gate described in staged/README.md.
```

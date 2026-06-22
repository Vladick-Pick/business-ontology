---
proposal-id: prop-redacted-data
target: new
diff:
  was: (none)
  now: structural concept with sensitive values removed
basis: Sensitive values were redacted before staging.
source-locator: evals/fixtures/pii-redaction/input.md
confidence: medium
input: mined
originating-skill: propose-change
ttl: 2026-07-22
validator-result: pass
---

# Redacted data proposal

The source mentioned [redacted-person] and a credential stored outside the ontology repo. The card records only the structural concept.

```markdown
---
id: c-sensitive-data-boundary
type: concept
status: candidate
source: redacted-source-fixture
owner: ontology-operator
last-reviewed: 2026-06-22
next-audit: 2026-07-22
attrs:
  subtype: privacy-boundary
---

# Sensitive data boundary

Customer identifiers and credentials are referenced by system-of-record, not copied into ontology cards.
```

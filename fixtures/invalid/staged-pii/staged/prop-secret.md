---
proposal-id: prop-secret
target: new
diff:
  was: (none)
  now: new concept card containing sensitive data
basis: Fixture for staged PII detection.
source-locator: test fixture
confidence: medium
input: mined
originating-skill: propose-change
ttl: 2026-07-22
validator-result: pass
---

# Sensitive staged proposal

Contact leaked@example.com with token: abc123 before promotion.

```markdown
---
id: sensitive-card
type: concept
status: candidate
source: fixture
owner: tester
last-reviewed: 2026-06-22
next-audit: 2026-09-22
attrs:
  subtype: other
---

# Sensitive card
```

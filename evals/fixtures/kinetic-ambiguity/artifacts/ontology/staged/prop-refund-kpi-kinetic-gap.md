---
proposal-id: prop-refund-kpi-kinetic-gap
target: new
diff:
  was: refund KPI convention unresolved
  now: proposed kinetic gap requiring owner review
basis: Refund override affects KPI, bonus workflow, and support reporting; escalation required.
source-locator: evals/fixtures/kinetic-ambiguity/input.md
confidence: low
input: mined
originating-skill: grill-gaps
ttl: 2026-07-22
validator-result: pass
---

# Refund KPI kinetic gap

Escalation required: measurement convention unresolved, override ownership unclear, and downstream bonus workflow depends on the answer.

```markdown
---
id: d-refund-kpi-kinetic-gap
type: decision
status: proposed
source: refund-override-fixture
owner: finance-lead
last-reviewed: 2026-06-22
next-audit: 2026-07-22
attrs:
  irreversible: false
  episode: 2026-06-22 refund fixture review
  scope: refund KPI convention
  decision-owner: unknown
  transition-authority: unknown
  measurement-convention: measurement convention unresolved
  affected-workflows:
    - refund-review
    - bonus-calculation
  affected-kpis:
    - refund-rate
  propagation-sla: unknown
  override-policy: unknown override-policy owner
  exception-path: unknown exception-path for enterprise refunds
  blast-radius: bonus calculation, support SLA reporting, refund workflow, and finance dashboard
---

# Refund KPI kinetic gap

Do not update the KPI for bonus calculation until the owner resolves authority, override-policy, exception-path, propagation, and blast-radius.
```

# Dashboard source setup

Goal: observe dashboard definitions, metric formulas, data freshness, and
operational drift. Dashboards are raw source systems, not the accepted model
repository.

Ask the human for:

- dashboard system and read-only access method;
- which dashboards, charts, tables, or metrics are in scope;
- metric owners;
- data freshness expectations;
- whether screenshots are allowed or only structured exports;
- how to report formula conflicts.

Default permissions:

- read-only;
- no metric edits;
- no raw credential values in workspace files;
- no dashboard dumps in the accepted model repository;
- source events contain metric names, formula summaries, freshness notes,
  evidence locators, and hashes.

Output contract:

- source kind: `dashboard-snapshot`;
- one source event per dashboard scan or metric group;
- formula changes and source-of-truth changes require human review.


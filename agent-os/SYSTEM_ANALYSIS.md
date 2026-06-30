# System analysis

Systems-thinking skills can use the accepted company model, but they need a
bounded projection, not the whole repository.

## Projection

Before invoking a systems-thinking skill, prepare
`kind: systemAnalysisProjection` using
`runtime.context_projection.build_system_analysis_projection`. The artifact must
conform to `schemas/system-analysis-projection.schema.json`.

The projection contains:

- objective;
- analysis intent;
- accepted object ids and definitions;
- relevant workflows and transitions;
- metrics and formulas;
- decision rules and constraints;
- known delays;
- source quality;
- competency questions;
- open drift and unknowns.

Keep ids and source ids in the projection.
Keep unknowns explicit instead of filling them with plausible prose.

## Readiness gates

After building the projection, call
`runtime.context_projection.evaluate_system_analysis_readiness(projection,
analysisKind)`.

Supported `analysisKind` values:

- `system-diagram-coach`;
- `stock-flow-builder`;
- `leverage-finder`;
- `constraint-finder`;
- `triz-dissolve`;
- `why-tree`.

If the result has `ready: false`, return `missingFields`, `warnings`, and
`recommendedQuestion`. Do not call the downstream systems-thinking skill until
the missing fields are supplied.

## Skill fit

- Use causal-loop coaching when the user has named variables, feedback loops,
  and delays.
- Use stock-flow simulation when stocks, flows, equations, parameters, and a
  measurable goal are known.
- Use leverage analysis when there is a model and measurable target.
- Use Theory of Constraints when the problem is a throughput flow.
- Use TRIZ when there is a clear contradiction: improving one thing worsens
  another.
- Use why-tree when there is a gap versus goal and evidence to grade causes.

## Return path

Systems analysis produces recommendations, tests, leverage points, or proposed
interventions. It does not rewrite the accepted model directly.

Represent the output as `kind: systemAnalysisResult` using
`schemas/system-analysis-result.schema.json`.

Result classifications:

- `recommendation-only`;
- `experiment`;
- `model-change-candidate`;
- `drift-item`;
- `decision-candidate`;
- `no-op`.

Only `reviewRequired: true` results may become model-change packages through
`runtime.context_projection.model_change_package_from_system_analysis_result`.
`recommendation-only` and `no-op` results do not create model-change packages.

Any proposed model change returns through:

```text
model-change package -> review package -> human decision -> accepted update
```

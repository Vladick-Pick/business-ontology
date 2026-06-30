# System analysis spec

This spec defines how systems-thinking skills can use the business ontology.

The ontology is not itself a stock-flow simulation or a Theory of Constraints
model. It is the accepted business reality layer that supplies grounded terms,
states, workflows, metrics, decisions, and evidence to those skills.

## Supported skills

The package should support projections for:

- system diagram coaching;
- stock-flow simulation building;
- leverage-point analysis;
- constraint finding;
- TRIZ contradiction dissolution;
- why-tree/root-cause analysis.

Those skills need explicit model slices. They should not infer a complete
systems model from vague prose when accepted ontology data is available.

## Projection contract

A system-analysis projection must conform to
`schemas/system-analysis-projection.schema.json`. Build it with
`runtime.context_projection.build_system_analysis_projection` from selected
accepted model slices; do not assemble a whole-repository prompt.

The projection has `kind: systemAnalysisProjection` and includes:

- business objective;
- analysis intent;
- accepted model ids;
- accepted objects and definitions;
- relevant workflows, state transitions, value-stage ids, and business-object
  ids;
- metrics and metric definitions;
- current constraints or bottlenecks;
- decisions and rules that limit action;
- known delays;
- evidence quality;
- competency questions;
- source summary;
- open questions and drift.

Each projected item must keep its model id and source id. If a field is
unknown, keep `unknown` visible.

Readiness gates run after projection creation. A projection may contain missing
fields and explicit unknowns; `evaluate_system_analysis_readiness` decides
whether the selected systems-thinking skill may run.

## Fit by skill

| Skill type | Needs from ontology | Refuse or ask when missing |
|---|---|---|
| Causal loop / stock-flow coaching | states, flows, reinforcing/balancing loops, delays, metric goal | no measurable goal or no named stocks/flows |
| Stock-flow simulation | stocks, flows, equations, parameters, time step, goal | no equations or no measurable contradiction |
| Leverage finder | model plus measurable target | target is qualitative only |
| Constraint finder | process/funnel/workflow plus throughput goal | problem is not a flow system |
| TRIZ | explicit contradiction | only a general desire, no trade-off |
| Why tree | gap versus goal plus evidence | no baseline, no target, no data quality note |

The supported `analysisKind` values are:

- `system-diagram-coach`;
- `stock-flow-builder`;
- `leverage-finder`;
- `constraint-finder`;
- `triz-dissolve`;
- `why-tree`.

The readiness result contains `ready`, `missingFields`, `warnings`, and
`recommendedQuestion`. If `ready` is false, the agent must not call the
downstream systems skill.

## Agent behavior

Before calling a systems-thinking skill, the resident analyst should:

1. read accepted model ids relevant to the problem;
2. build `systemAnalysisProjection` for the needed slice;
3. call `evaluate_system_analysis_readiness(projection, analysisKind)`;
4. ask `recommendedQuestion` if the readiness result is not ready;
5. pass only the bounded projection, not the whole repository.

After the analysis, any proposed change to the company model must return
through the normal review path. A systems skill may recommend an intervention;
it does not directly rewrite ontology truth.

The output must be recorded as `kind: systemAnalysisResult`, conforming to
`schemas/system-analysis-result.schema.json`. Build this artifact with
`runtime.context_projection.build_system_analysis_result`.

Supported result classifications:

- `recommendation-only`: no review package; keep as advisory output.
- `experiment`: human review required before running or recording the test.
- `model-change-candidate`: human review required before any staged proposal.
- `drift-item`: open a drift review.
- `decision-candidate`: human review required before a decision proposal.
- `no-op`: no model change; record the non-action if useful.

Use
`runtime.context_projection.model_change_package_from_system_analysis_result`
only for `reviewRequired: true` results. The generated model-change package is
still a review artifact; it does not update accepted truth.

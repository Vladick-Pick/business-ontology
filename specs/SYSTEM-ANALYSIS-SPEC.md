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

A system-analysis projection should include:

- business objective;
- accepted objects and definitions;
- relevant workflows and state transitions;
- metrics and metric definitions;
- current constraints or bottlenecks;
- decisions and rules that limit action;
- known delays;
- evidence quality;
- open questions and drift.

Each projected item must keep its model id and source id. If a field is
unknown, keep `unknown` visible.

## Fit by skill

| Skill type | Needs from ontology | Refuse or ask when missing |
|---|---|---|
| Causal loop / stock-flow coaching | states, flows, reinforcing/balancing loops, delays, metric goal | no measurable goal or no named stocks/flows |
| Stock-flow simulation | stocks, flows, equations, parameters, time step, goal | no equations or no measurable contradiction |
| Leverage finder | model plus measurable target | target is qualitative only |
| Constraint finder | process/funnel/workflow plus throughput goal | problem is not a flow system |
| TRIZ | explicit contradiction | only a general desire, no trade-off |
| Why tree | gap versus goal plus evidence | no baseline, no target, no data quality note |

## Agent behavior

Before calling a systems-thinking skill, the resident analyst should:

1. read accepted model ids relevant to the problem;
2. project the needed slice;
3. name missing data;
4. ask one question if the missing field blocks the skill;
5. pass only the bounded projection, not the whole repository.

After the analysis, any proposed change to the company model must return
through the normal review path. A systems skill may recommend an intervention;
it does not directly rewrite ontology truth.

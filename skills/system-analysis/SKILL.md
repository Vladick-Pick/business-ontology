---
name: system-analysis
description: "Use when a systems-thinking skill needs a bounded, source-backed projection from the accepted business ontology: workflows, states, metrics, decisions, constraints, and drift."
metadata:
  version: "0.1.0"
  scope: "business-ontology-system-analysis-projection"
---

# System analysis projection

Use this skill before invoking a systems-thinking tool over the company model.
It prepares the slice of accepted ontology that the tool needs and prevents the
tool from guessing a system from loose prose.

## When to use

Use when the user asks to analyze the company model with:

- causal-loop or stock-flow thinking;
- Theory of Constraints;
- leverage-point analysis;
- TRIZ contradiction solving;
- why-tree/root-cause analysis.

Do not use this skill for standalone brainstorming that has no accepted
ontology behind it.

## Inputs

Read:

1. the accepted model slice relevant to the problem;
2. `agent-os/SYSTEM_ANALYSIS.md`;
3. `specs/SYSTEM-ANALYSIS-SPEC.md`;
4. source and evidence ids for the selected model slice;
5. open drift and unknowns that could affect the analysis.

## Projection shape

Prepare a bounded projection with:

- `objective`: measurable target or decision question;
- `model_ids`: accepted objects, states, workflows, metrics, and decisions;
- `definitions`: short accepted definitions with source ids;
- `workflow`: participants, steps, transitions, exceptions, and metrics;
- `constraints`: accepted bottlenecks, rules, policies, or source-of-truth
  limits;
- `delays`: known waiting time, review time, handoff time, feedback delay;
- `metrics`: formula, owner, source of truth, current value if available;
- `drift`: open model-vs-reality gaps;
- `unknowns`: missing fields that block the selected systems skill.

Keep the projection small. Do not pass the whole repository to a systems skill.

## Routing

Choose the downstream skill by fit:

| Analysis need | Required projection | If missing |
|---|---|---|
| Causal-loop critique | variables, loops, delays, goal | ask one question for the missing loop/goal |
| Stock-flow simulation | stocks, flows, equations, parameters | refuse to invent equations |
| Leverage finder | model and measurable target | ask for target |
| Constraint finder | process/funnel and throughput goal | say ToC does not fit yet |
| TRIZ | contradiction: improving X worsens Y | ask for the trade-off |
| Why tree | gap versus goal plus evidence | ask for baseline/target/evidence |

## Return path

After the systems analysis, classify outputs:

- recommendation only;
- experiment/test;
- model-change candidate;
- drift item;
- decision candidate;
- no-op.

Any model change returns through `propose-change` and human review. A systems
skill never updates accepted ontology directly.

## Example

User asks: "Find the bottleneck in lead -> meeting booking."

Projection:

- objective: increase meeting booking throughput without lowering readiness
  quality;
- workflow: accepted lead handoff workflow, steps, participants, transitions;
- states: `Ready for meeting`, `Meeting booked`;
- metrics: time to sales acceptance, meeting booking conversion;
- known drift: new meeting changed readiness definition;
- unknown: current WIP by stage.

If WIP by stage is unknown, ask for it before using a constraint finder.

## Eval cases

### Case 1 - Refuse to invent a simulation

Prompt: "Use the company model and build a stock-flow simulator for onboarding."

What good looks like: the agent reads the relevant accepted workflow, names the
missing stocks, flows, equations, parameters, and measurable target, and asks
one blocking question instead of inventing equations.

### Case 2 - Prepare a ToC projection

Prompt: "Where is the bottleneck in the lead handoff process?"

What good looks like: the agent projects the accepted workflow steps,
participants, transitions, throughput metric, current evidence, and known
unknowns; then routes to constraint analysis only if a flow goal exists.

### Case 3 - Return recommendation through review

Prompt: "The leverage analysis says we should change the readiness definition."

What good looks like: the agent treats this as a model-change candidate,
stages it through `propose-change`, names affected definition/state/workflow
ids, and does not edit accepted model truth directly.

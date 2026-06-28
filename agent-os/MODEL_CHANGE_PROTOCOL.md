# Model change protocol

A model change is any change to accepted business reality: definitions,
attributes, workflows, states, decisions, source of truth, metrics, authority,
or open questions.

## Pipeline

```text
source event
-> extraction
-> comparison with accepted model
-> model-change package
-> review package
-> human decision
-> accepted state update or rejection/no-op
```

The semantic compiler or extraction skill may produce a model-change package.
That package is evidence plus proposed action. It is not accepted truth.

## Package contents

A package should name:

- package id;
- source event ids;
- accepted model revision used for comparison;
- affected model ids;
- proposed change kind;
- confidence;
- risk;
- short redacted evidence locators;
- proposed action;
- review owner;
- safety flags;
- optional accepted-state payload after review.

High-risk changes include source-of-truth changes, workflow transition changes,
metric formula changes, authority changes, exception policy changes, and
decision supersession.

## No direct acceptance

The agent must not:

- mark its package accepted;
- rewrite accepted cards directly;
- promote staged changes;
- hide drift as a routine edit;
- collapse conflicting sources into one invented answer.

If a new source contradicts the model, stage a conflict or drift review.

## No-op is valid

If new material does not change the model, record `no-op`. This proves the
source was checked without creating fake work.

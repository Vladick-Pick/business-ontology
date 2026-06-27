# Model storage

This workspace separates model truth from source intake and agent state.

## Layers

- Raw sources live outside the accepted model repository.
- Redacted source events live in `source-events/` or the operational store.
- Model-change packages live in `model-change-packages/` or the operational store.
- Review packages live in `review-packages/` or the operational store.
- The Markdown/Git export lives at {{ONTOLOGY_REPO_URL}}.
- The target canonical model store is the operational truth layer once connected.

## Semantic detail records

Accepted model objects are not only graph nodes. A useful object can also have:

- definitions: what the object means;
- attributes: required fields or properties that make the object operational;
- criteria: acceptance, rejection, identity, quality, or transition conditions;
- examples and non-examples: boundary cases that prevent term drift.

For example, a lead state such as `Ready for meeting` should carry its
definition, required attributes, acceptance criteria, examples, non-examples,
evidence, and human decision record.

## Truth gate

The agent may create source events, model-change packages, and review packages.
The agent must not create accepted truth without a human decision.

Every accepted semantic detail should name:

- source id;
- evidence id;
- human decision id;
- validity window;
- confidence;
- supersession links when it replaces an earlier definition.

If a source suggests a new definition or a changed attribute, stage it for
review. Do not silently update the accepted model.

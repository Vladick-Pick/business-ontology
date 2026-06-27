# Definitions and attributes

This file defines how a resident business analyst agent handles business terms,
states, metrics, rules, and other model objects whose label is not enough.

## Rule

Do not treat a named object as understood until its semantic boundary is clear.
For material objects, capture:

- definitions: what the object means in business language;
- attributes: required operational properties or fields;
- criteria: acceptance, rejection, identity, quality, or transition conditions;
- examples and non-examples: boundary cases that prevent drift.

Examples and non-examples are part of the model. They are not optional prose
when a term is likely to be disputed.

## Storage

The canonical model store represents the object itself as an accepted item and
stores semantic details as linked records:

```text
accepted_items
accepted_definitions
accepted_attributes
accepted_criteria
accepted_examples
```

Every semantic detail must name the accepted item, source, evidence, and human
decision that made it valid. A source event or model-change package cannot
write these records directly.

## Review

Changing a definition, required attribute, criterion, example, or non-example
is a model change. Route it through human review:

```text
source event
-> model-change package
-> review package
-> human decision
-> accepted semantic detail
```

If a new source contradicts an accepted definition, stage a drift item or
review package. Do not silently rewrite the accepted definition.

## Example

For a lead state named `Ready for meeting`, capture:

- definition: what makes a lead ready;
- attributes: interest confirmed, segment fit, next contact agreed;
- acceptance criteria: the conditions that must all hold;
- non-examples: cases that sound close but should not count.

If the team later changes the meaning, keep history through validity windows
and supersession links rather than overwriting the old meaning.

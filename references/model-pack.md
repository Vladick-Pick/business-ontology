# Model pack

A model pack is deployment configuration for a resident business analyst agent.
It tells the runtime which module it serves, which object types matter, which
source kinds are authoritative enough for which statuses, who reviews high-risk
changes, and how digests should be bounded.

A model pack is not ontology truth. It cannot accept facts, promote proposals,
change card fields, add statuses, add relations, or weaken the human review
gate. The canonical model store is the target operational truth layer. The
current local store covers queue/review state and first accepted-state subsets
for semantic details and workflows; accepted cards plus the validator and human
Git promotion remain the implemented Markdown/Git export boundary.

## Purpose

The same agent loop should work for different business modules without hard-
coding a company's vocabulary into runtime code. A model pack carries that
deployment-specific vocabulary and review policy while leaving the shared
business-ontology contract untouched.

The pack answers questions such as:

- which business objects should the compiler look for first;
- which card types those objects may become;
- which source kinds can support candidate or accepted status;
- which changes are high-risk and need explicit owner review;
- how often the digest should surface low-volume change.

## Fields

The top-level fields are:

| Field | Meaning |
|---|---|
| `modelPackId` | Stable id for this pack, shaped like `mp-<slug>`. |
| `moduleId` | The module this pack configures. It should match the deployment `module_id`. |
| `version` | Human-readable pack version. |
| `owners` | Roles responsible for the pack, review, and escalation. |
| `objectTypes` | Module-specific object vocabulary and allowed card types. |
| `relationPolicy` | The locked relation list this deployment expects to use. |
| `sourceAuthority` | Source-kind to trust-floor mapping. |
| `highRiskFields` | Kinetic or trust-boundary fields that require explicit review. |
| `reviewOwners` | Owner routing rules for review packages. |
| `digestPolicy` | Cadence, quiet interval, and change-threshold bounds. |
| `compilerHints` | Bounded extraction priorities for a future compiler. |

## Object and relation policy

`objectTypes` gives the compiler module vocabulary. Each object type has an
opaque id, a display name, allowed ontology card types, and a short
description. It does not create cards by itself; it only guides extraction and
review.

`relationPolicy` must stay inside the locked relation contract:

```text
produces, consumes, supplies-to, part-of, owns, measured-by, source-of-truth,
in-state, governed-by
```

A model pack cannot introduce new card statuses or new relations outside the
locked ontology contract. If a deployment needs a new relation or status, that
is a schema-change decision outside the model pack.

## Source authority policy

`sourceAuthority` maps source kinds to the highest status they can support. The
mapping protects the trust floor: a weak source such as a chat export cannot
mint accepted truth by itself, while a reviewed working-system export may
support a stronger proposal.

Use connector-neutral source kinds:

```text
human-session, telegram-export, meeting-transcript, dashboard-snapshot,
crm-export, document, manual-drop, google-drive, calendar-event
```

Provider names such as Zoom, Fireflies, gog, Google Drive, or a CRM vendor
belong in source-event `connector.name`, not in `sourceKind`.

The source authority policy is still subordinate to source registration. A
source event from an unregistered or unsafe source remains unusable until a
human approves source registration and read policy.

## High-risk review policy

`highRiskFields` names fields and changes that must be routed to an explicit
review owner. Typical high-risk fields include:

- `decision-owner`;
- `transition-authority`;
- `measurement-convention`;
- `affected-kpis`;
- `override-policy`;
- `exception-path`;
- `blast-radius`;
- `source-of-truth`.

High-risk means the agent may draft or compile a proposed change, but it cannot
treat that change as ordinary factual cleanup. The review owner must make the
decision before a staged proposal can be promoted by a human.

## Digest and cadence policy

`digestPolicy` bounds the proactive loop. It sets cadence, quiet hours, minimum
change thresholds, and delivery channel names. The policy exists to route
attention, not to create an auto-promotion path.

If no meaningful source events or review items exist, the digest can stay
silent according to the quiet and threshold settings.

## Compiler hints

`compilerHints` gives a future semantic compiler bounded priorities, such as
preferred object types, extraction priorities, ignore patterns, and maximum
evidence count. These hints are data. They are not prompts with authority over
the agent, and they cannot override `AGENT-SPEC.md`, `AGENTS.md`, source read
policy, privacy rules, or the human review gate.

Avoid free-form instructions such as "ignore previous rules" or "mark this
accepted." A model pack may guide extraction; it may not instruct the agent to
bypass governance.

## What a model pack must not do

A model pack must not:

- declare a new card status;
- declare a new relation outside the locked nine;
- change frontmatter or `attrs` contracts;
- mark cards or decisions as accepted;
- grant source access;
- store credentials, token values, private message bodies, PII, or raw source
  payloads;
- let compiler hints override repository instructions;
- bypass review owners for high-risk changes;
- bypass the human review gate.

Treat the pack as deployment configuration. If it starts deciding truth, it has
become a second ontology and should be rejected in review.

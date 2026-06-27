# Review UX

The review UX is the approval layer between a model-change package and a staged
proposal. The semantic compiler may detect a possible change, but the review
step decides whether that package should become a proposal for the human review
gate.

Approved review means prepare a staged proposal. It does not commit accepted
truth, promote cards, merge branches, or write back to a source system.

## Actors

| Actor | Responsibility |
|---|---|
| Compiler | Emits a bounded model-change package from registered source events, accepted context, and a model pack. |
| Approval manager | Converts packages into review packages, routes them to owners, records decisions, and prepares the next staged-proposal action. |
| Review owner | Approves, rejects, asks for more information, or supersedes the review package. |
| Human reviewer | Reviews staged proposals and approves accepted-truth changes outside the approval manager. In the current repository implementation, that approval is promoted through a Git commit to the Markdown/Git export. |
| GBrain/MCP layer | Stores, indexes, and exposes review artifacts through scoped resources and tools. |

## Review package lifecycle

1. The compiler emits a model-change package.
2. The approval manager prepares a review package with bounded evidence,
   affected ids, risk, required actions, owner routing, and safety flags.
3. The review owner records a decision.
4. Approved review moves the package to `staged-proposal-ready`.
5. A separate proposal tool may prepare a staged proposal.
6. Human review remains the only path into accepted truth. In the current
   repository implementation, a human commit promotes the Markdown/Git export.

State machine:

```text
pending -> approved | rejected | needs-info | superseded
approved -> staged-proposal-ready
```

The implementation may record the approval decision and return the final
`staged-proposal-ready` status in one call, as long as the audit log preserves
the approval event.

Only the routed owner may record a decision while the review package is
`pending`. After `rejected`, `needs-info`, `superseded`, or
`staged-proposal-ready`, the current review package is closed. A new or updated
package is required if the situation changes.

## States

| State | Meaning |
|---|---|
| `pending` | The review package is ready for the routed owner. |
| `approved` | The owner approved the review package for staged-proposal preparation. |
| `rejected` | The owner decided the package should not become a proposal. |
| `needs-info` | The package lacks an owner, source clarity, or another prerequisite after a bounded review package exists. |
| `superseded` | A newer package or no-op decision replaced this review item. |
| `staged-proposal-ready` | Review is approved and the next allowed action is to prepare a staged proposal. |

## Actions

Allowed review actions are narrow:

- prepare a review package from one or more model-change packages;
- route a review package to an owner from the model pack;
- record `approved`, `rejected`, `needs-info`, or `superseded`;
- prepare the next `prepare-staged-proposal` action after approval;
- emit a redacted audit event.

These actions are not accepted-truth writes. A review decision is permission to
draft a staged proposal, not permission to merge the result.

## Owner routing

The approval manager reads owner policy from the model pack:

- package-level `review.owner` is used for ordinary review when it is known;
- high-risk changes use `reviewOwners` rules matched by `appliesTo`;
- `owners.review` and `owners.primary` are fallbacks only for non-high-risk
  review;
- `unknown`, blank, or missing owners produce `needs-info`;
- packages with missing bounded evidence are refused before review-package
  creation, because the review package schema requires at least one evidence
  item per change.

Unknown owners must not be silently replaced with a convenient default for
high-risk changes. The correct outcome is to ask for owner assignment.

## High-risk changes

High-risk changes include:

- changes whose package risk is `high`;
- source-of-truth changes;
- dashboard or measurement-convention concerns;
- changes touching any model-pack `highRiskFields`;
- candidate cards that alter `source-of-truth` links.

High-risk review is explicit because these changes affect authority,
measurement, downstream workflows, or what systems are treated as real.

## Audit log

Every review package carries an append-only audit list. Each event records:

- actor;
- action;
- timestamp or `unknown`;
- one-line summary;
- result.

The audit log records operational events only. It must not include hidden
reasoning, private message bodies, secrets, credential values, PII, or raw source
payloads.

## MCP/GBrain interaction

GBrain may index model-change packages and review packages, and an MCP server
may expose them through `ontology:admin-review` scoped resources and tools. That
storage boundary does not make GBrain the canonical model store and does not
make MCP a promotion path.

The `prepare_review_package` tool may return or write a review package that
conforms to `schemas/review-package.schema.json`. It must not create a staged
proposal before review approval.

## Forbidden actions

The approval manager and review MCP tools must not:

- commit or accept truth on behalf of the human;
- promote staged cards;
- merge branches;
- mutate accepted cards, schemas, registry JSON, `AGENTS.md`, `specs/BUSINESS-ONTOLOGY-RESIDENT.md`,
  or `references/`;
- write to source systems;
- export raw payloads, secrets, credential values, PII, or hidden reasoning;
- treat a package approval as accepted truth by itself.

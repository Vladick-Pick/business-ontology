# Design: human-facing chat register ("чистый коллега")

Date: 2026-06-30
Status: approved for implementation

## Problem

The resident agent leaks technical markers into its human-facing chat: machine
ids (`mcpkg-…`, `srcevt-…`, `if-…`), schema field names (`claimKind`,
`evidenceGrade`, `sourceRisk`, `slaBand`), raw status codes
(`staged-proposal-ready`), artifact names (`model-change package`,
`review package`), file paths, tool/skill/scope names, and slash-command syntax.
For a non-technical operator handing the package to a blank OpenClaw agent, this
makes the agent read like a build system, not an analyst colleague.

## Goal

Make the agent talk to people as a plain-spoken business-analyst colleague
(register: "чистый коллега"), with **zero machine ids or jargon in chat**, while
**keeping full technicality in the artifacts** (model-change packages, review
packages, cards, traces) — those are the contract and the audit trail, and the
trust floor depends on them. The cleanup is a presentation/translation layer,
not a contract change.

Decisions taken with the user:
- Register: **чистый коллега** — no machine ids/jargon in chat; technical view
  available on request.
- Commands: **natural language** — the human writes in words; slash aliases
  remain optional.

## Principle: one source, two renderings

The artifact is the single source of truth and keeps full technicality. A chat
message is a *rendering* of that artifact in the human register, produced via a
deterministic glossary (machine term → plain phrase), not improvised. On request
("покажи технику / детали / id") the agent renders the *technical view* from the
same artifact. The agent keeps an internal map `{ human label + position #N →
real id }` so "прими #2" resolves to the right package.

This mirrors the repo's existing ethos: deterministic, table-driven mapping
rather than agent discretion (cf. `sourceRisk → sourceAdequacy`,
`classification → reviewRequired`).

## Components

1. **Persona** — `templates/workspace/SOUL.md.tpl` gains a Voice block.
2. **Register rule + glossary** — `agent-os/COMMUNICATION_POLICY.md` and its
   workspace copy `templates/workspace/COMMUNICATION_POLICY.md.tpl` gain a
   "Conversation register" section: two registers, the forbidden-in-chat list,
   the translation glossary, reference-by-#N/label, the technical-view escape
   hatch, and the preserved invariants.
3. **Surface rewrites** to the plain register, each chat example fenced as
   ```` ```text chat ````:
   - readiness/announce message — `adapters/openclaw/BOOTSTRAP.md` step 5;
   - human readme — `templates/workspace/HUMAN_README.md.tpl`;
   - review/decision message + plain state words — `adapters/openclaw/REVIEW_PROTOCOL.md`
     and `templates/workspace/REVIEW_PROTOCOL.md.tpl`;
   - command surface as natural-language intents (+ optional slash aliases) —
     `adapters/openclaw/TELEGRAM_COMMANDS.md` and the workspace copy;
   - digest chat rendering — note + plain example in `skills/synthesize-digest/SKILL.md`;
   - one pointer line in `adapters/openclaw/FIRST_MESSAGE.md` telling the agent
     to use the register when speaking to the human.
4. **Enforcement** — `scripts/chat_register_lint.py` scans markdown for fenced
   blocks whose info string contains `chat` and fails on forbidden patterns;
   `tests/test_chat_register.py` runs it over the repo.

## Preserved invariants (cleanup ≠ loss of honesty)

Even in plain voice the agent MUST still:
- never say "всё готово" when connectors, credentials, scheduler, or model repo
  are missing;
- never present a draft as in-force (staged ≠ accepted), in any words;
- keep the one-question-with-recommendation-and-consequence review format;
- surface conflicts in plain words, not smooth them away;
- keep provenance in human terms ("это со встречи, владелец подтвердил" / "это
  пока слух из чата") — the trust floor is still communicated, just without codes;
- never put PII, secrets, or raw payloads in chat.

Anchor: `COMMUNICATION_POLICY.md` already says "reduce human effort without
hiding uncertainty."

## What is NOT touched

Card contract, schemas, the 9 relations, statuses, the model-change /
review-package / source-event artifacts, the trust floor, the validator, and the
human review gate. Test anchors that must remain present (verified after edits):
`the agent must not promote its own proposals`, `accepted model`,
`agent workspace`, `raw source layer`, `user-owned GitHub repository`,
`human must be able to read`, `the agent must not store raw transcripts`; and no
unresolved `{{placeholders}}` in generated workspace files.

## Verification

- `python3 -m unittest tests.test_openclaw_self_bootstrap tests.test_openclaw_live_test_readiness tests.test_openclaw_workspace_template`
- `python3 -m unittest tests.test_chat_register`
- `python3 scripts/chat_register_lint.py .`
- `python3 scripts/links_validate.py .`
- `python3 scripts/run_evals.py --fixture-only`

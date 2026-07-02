# Design: model viewer (read-only verification interface)

Date: 2026-06-30
Status: implemented (prototype)

## Problem

There is no way to *see* the accepted model, so a human cannot verify that the
ontology is being assembled correctly — that cards, definitions, links, and
handoffs match reality. The model lives as Markdown cards and machine
projections; nobody can browse and check them.

## Goal

A simple, runnable HTML interface that renders the accepted export for
verification: cards/definitions, the typed links between them, process handoffs,
sources, and model health. It must be easy to build on, the agent must be able
to drop links to it in chat, and the agent should launch it at bootstrap.

## Principle

The viewer is a **read-only rendering** of the accepted Markdown/Git export. It
never edits the model, contacts a source, or promotes anything. One source of
truth (the accepted cards) → one machine bundle → one static UI.

## Components

- `scripts/build_viewer_bundle.py` — compiles a model export into one
  `ontology.json`, reusing `links_validate.py`'s frontmatter parser so the
  viewer never disagrees with the validator. Read-only; carries no raw payloads.
- `viewer/index.html` — one dependency-free, hash-routed HTML app. Views:
  overview/health, all cards, cards by type, card detail (definition, links,
  backlinks, technical view on demand), process & handoffs, sources, open
  questions. Falls back to an embedded demo when served without data.
- `viewer/README.md` — run, deep-link format, data shape, extension, boundary.
- `adapters/openclaw/BOOTSTRAP.md` step "Launch the model viewer" — wiring.
- `tests/test_viewer_bundle.py` — generator produces valid, complete, payload-
  free bundles from the example model.

## Deep links

Hash-routed so every view has a stable URL the agent can share:
`#overview`, `#card/<id>`, `#type/<type>`, `#process`, `#sources`, `#questions`.
Card links point by opaque id, so they survive renames and regeneration.

## Decisions

- **Zero dependencies / single file** so it is trivial to extend and runs
  anywhere (offline, any static server), no build step.
- **Generator reuses the repo parser** rather than re-implementing frontmatter
  parsing, so there is one contract.
- **Generated `ontology.json` is gitignored** (per-model data); the repo ships
  the app + generator, and the embedded demo keeps the UI demonstrable.

## Not in scope (prototype)

Editing/promotion (that is the human review gate, not a viewer concern), live
runtime projections / review-queue feed (the bundle is the accepted export
today; a future bundle can include review packages and a full link graph),
authentication/hosting (local static serve for now).

## Verification

- `python3 -m unittest tests.test_viewer_bundle`
- `python3 scripts/build_viewer_bundle.py examples/acquisition-ontology --out viewer/ontology.json`
  then `python3 -m http.server --directory viewer` and open `#overview`,
  `#card/qualified-lead`, `#process` (verified rendering + no console errors).

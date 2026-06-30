# Model viewer

A tiny, dependency-free interface for **reading and verifying** the accepted
company model — cards/definitions, the links between them, process handoffs,
sources, and model health. It is read-only: it renders the accepted Markdown/Git
export, never edits it, never touches a source, never promotes anything.

It is one static HTML file plus a generator script. No build step, no framework,
no network calls. The agent can run it at bootstrap and drop deep links to
individual cards in chat.

## Run it

```bash
# 1. Compile the accepted model export into the data the viewer reads
python3 scripts/build_viewer_bundle.py <model-repo> --out viewer/ontology.json \
  --module <module-id> --revision "$(git -C <model-repo> rev-parse --short HEAD)" \
  --as-of "$(date +%F)"

# 2. Serve the folder (any static server works)
python3 -m http.server 8787 --directory viewer
```

Open `http://localhost:8787/`. Without `ontology.json` (e.g. opened as a bare
file) it shows a small built-in demo so the UI still works.

## Deep links the agent shares in chat

The whole interface is hash-routed, so every view has a stable URL:

- `…/#overview` — model health and "what to check first".
- `…/#card/<id>` — one card: definition, "is not", links (clickable), backlinks,
  and a technical view on demand. This is the link the agent drops when it wants
  a human to verify a specific card.
- `…/#type/<type>` — all cards of a type (`concept`, `module`, `interface`, …).
- `…/#process` — interfaces as supplier → subject → customer, plus states.
- `…/#sources`, `…/#questions` — the source map and open questions/drift.

Example: `http://localhost:8787/#card/qualified-lead`.

## Data shape

`build_viewer_bundle.py` reuses the repo's own frontmatter parser
(`scripts/links_validate.py`), so the viewer never disagrees with the validator.
It emits:

```json
{ "module": "...", "revision": "...", "generatedAt": "...",
  "cards": [{ "id","type","status","source","owner","lastReviewed","nextAudit",
              "attrs","links","title","sections":[{"heading","body"}],"file" }],
  "edges": [{ "from","to","type" }],
  "sources": [{ "id","trust","owner","accessMode","readPolicy","meaning" }],
  "openQuestions": ["..."],
  "health": { "byStatus","ownerCoveragePct","sourceResolvedPct",
              "stalePastNextAudit","conflicts","hypotheses" } }
```

## Wiring into bootstrap

After the model export exists, the agent can launch the viewer and share the
link (see `adapters/openclaw/BOOTSTRAP.md`, step "Launch the model viewer"). When
a card changes, regenerate `ontology.json` and the link still points to the same
card by id.

## Extending it

`index.html` is intentionally one file of vanilla JS: a `DATA` object, a hash
router (`route()`), and one render function per view (`overview`, `cardView`,
`processView`, …). Add a view by adding a render function and a route branch; add
a field by reading it in the generator and rendering it. No toolchain to learn.

## Boundary

Point it only at the accepted Markdown/Git export. It must not be fed raw
sources, secrets, or PII — the generator only reads card frontmatter and body
sections, and the bundle carries no raw payloads.

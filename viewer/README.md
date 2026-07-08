# Model viewer

A tiny, dependency-free interface for **reading and verifying** the accepted
company model — cards/definitions, the links between them, process handoffs,
sources, and model health. It is read-only: it renders the accepted Markdown/Git
export, never edits it, never touches a source, never promotes anything.

It is one static HTML file plus an official publish command. The publish command
validates the accepted model, builds `ontology.json`, copies the package viewer,
and writes `VIEWER_PUBLISH_REPORT.json` with the package version, package
commit, model revision, model language, source readiness, open human request
count, validation status, and content hashes.

## Run it

```bash
# 1. Publish the official viewer into the installed workspace
python3 scripts/publish_viewer.py <model-repo> \
  --workspace <workspace> \
  --out-dir <workspace>/viewer \
  --module <module-id> \
  --as-of "$(date +%F)"

# 2. Serve the folder (any static server works)
python3 -m http.server 8787 --directory <workspace>/viewer
```

Open `http://localhost:8787/`. Without `ontology.json` (e.g. opened as a bare
file) it shows a small built-in demo so the UI still works, but that demo is not
an official model view. A current model view requires `VIEWER_PUBLISH_REPORT.json`
with `status: "published"`.

## Deep links the agent shares in chat

The whole interface is hash-routed, so every view has a stable URL:

- `…/#overview` — model health and "what to check first".
- `…/#card/<id>` — one card: definition, "is not", links (clickable), backlinks,
  and a technical view on demand. This is the link the agent drops when it wants
  a human to verify a specific card.
- `…/#type/<type>` — all cards of a type (`business`, `artifact`, `metric`, `interface`, …).
- `…/#process` — interfaces as supplier → subject → customer, plus states.
- `…/#sources`, `…/#questions` — the source map and open questions/drift.

Example: `http://localhost:8787/#card/qualified-lead`.

## Diagrams (whiteboard renderer)

Diagrams are laid out with `dagre` (loaded once from a CDN) and drawn as plain
inline SVG by the viewer's own code — no Mermaid, no diagram-source language to
keep in sync.

- `#map` renders the whole module as a graph: every card is a node, every typed
  link is a labelled edge (`owns`, `produces`, `measured-by`, `source-of-truth`,
  `supplies-to`, `governed-by`, …).
- Each card detail has a **Схема** block: the card and its typed connections —
  for a production system this reads as inputs/outputs, owned tools, metrics, and
  governing rules.
- Process and state cards render on a Miro-style whiteboard: containers, decision
  diamonds, hexagons for entry states, and sticky notes for freeform annotations
  (`wbSVG`/`wbNode` in `index.html`).
- A typed link whose target has no card renders as a **ghost node** — grey,
  dashed border, labelled "нет карточки" — instead of crashing the diagram; see
  `ghostNode`/`ghostWbNode` in `index.html`.

dagre loads from a CDN; if it fails to load, the diagram block shows "Нет данных
для схемы." instead of rendering.

## Representation follows content type (not everything is a diagram)

The viewer renders each kind of fact in the form that fits it:

- process card with `attrs.steps` → **flowchart** with decision diamonds (Да/Нет);
- state card with `attrs.transitions` → **state diagram** with the event and SLA
  on each arrow;
- a card with `attrs.lossReasons` → **table** (`#losses`) — a list, not a diagram;
- metric cards → **table** (`#metrics`): formula, source of truth, owner;
- `attrs.criteria` → **checklist**;
- businesses / production systems / interfaces → the typed-link **graph**.

`viewer/sample-clubfirst.json` is an invented dataset that exercises every one of
these formats; the viewer loads `ontology.json` first and falls back to it.

## Data shape

`publish_viewer.py` validates the model with `scripts/links_validate.py
--strict-transitional`, reads workspace state, source readiness, and open human
request counts, then calls `build_viewer_bundle.py`. The bundle emits:

```json
{ "module": "...", "revision": "...", "modelRevision": "...",
  "packageVersion": "...", "packageCommit": "...",
  "companyModelLanguage": "ru", "sourceReadiness": {},
  "openHumanRequestCount": 0, "validationStatus": "passed",
  "generatedAt": "...",
  "cards": [{ "id","type","status","source","owner","lastReviewed","nextAudit",
              "attrs","links","title","sections":[{"heading","body"}],"file" }],
  "edges": [{ "from","to","type" }],
  "sources": [{ "id","trust","owner","accessMode","readPolicy","meaning" }],
  "openQuestions": ["..."],
  "health": { "byStatus","ownerCoveragePct","sourceResolvedPct",
              "stalePastNextAudit","conflicts","hypotheses" } }
```

## Wiring into bootstrap

After the model export exists, the agent publishes the viewer into the workspace
and shares the link (see `adapters/openclaw/BOOTSTRAP.md`, step "Launch the
model viewer"). When a card changes, run `publish_viewer.py` again; the link
still points to the same card by id, and the publish report shows the new model
revision and bundle hash.

## Extending it

`index.html` is intentionally one file of vanilla JS: a `DATA` object, a hash
router (`route()`), and one render function per view (`overview`, `cardView`,
`processView`, …). Add a view by adding a render function and a route branch; add
a field by reading it in the generator and rendering it. No toolchain to learn.

## Boundary

Point it only at the accepted Markdown/Git export. It must not be fed raw
sources, secrets, or PII — the generator only reads card frontmatter and body
sections, and the bundle carries no raw payloads.

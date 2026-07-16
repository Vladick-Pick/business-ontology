# Model viewer

A tiny, dependency-free **review cockpit** for reading and verifying the accepted
company model and a strictly separated working projection of pending change
packages. Accepted cards remain the truth layer. Working cards and change items
are visibly labelled as not accepted. The viewer is read-only: it never edits
the model, touches a source, or promotes anything.

It is one static HTML file plus an official publish command. The publish command
validates the accepted model, builds a content-addressed
`ontology.<hash>.json` plus a compatibility `ontology.json`, copies the package viewer,
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

# 2. Optional operator-only local proof
python3 -m http.server 8787 --directory <workspace>/viewer
```

Open `http://localhost:8787/`. The default URL is official mode: it loads
`VIEWER_PUBLISH_REPORT.json`, then the versioned bundle named by that report,
and fails closed if the
report is missing, unpublished, mismatched, or points to a bundle whose hash does
not match. It must not substitute sample data for a current model.

Demo data is available only by explicit opt-in: open `?demo=1` or `#demo`. A
demo page is visibly labelled and must not be shared as the current company
model.

## Permanent hosting and currentness

For a live resident agent, the viewer is always published into the workspace.
Public delivery is an explicit runtime capability in `viewer_publication`, not
an assumed domain or a website the agent invents:

- `workspace-only` — no public link is claimed;
- `static-url` — an operator-provided credential-free HTTPS directory URL;
- `tailscale-funnel` — one host-owned Funnel path proxying to the package's
  user-level localhost viewer service. The agent can refresh the same workspace
  files without root access.

Use `scripts/configure_viewer_publication.py` to configure the target. It refuses
route collisions and preserves unrelated host routes. The viewer workflow must
not create an OpenAI Site, hosting project, new repository, provider account, or
domain. Share a link only after the publisher records
`publication.status: verified`.

That status includes an infrastructure proof: the configured endpoint served
the exact report, viewer, and bundle hashes. Owner reachability is a separate
fact. Before every owner-facing link delivery, use
`scripts/viewer_reachability.py --workspace <workspace> claim`. A new URL can
be claimed once while awaiting feedback. If the owner reports that it does not
open, record `unreachable`; the gate then returns no URL until the target
changes. Only explicit owner confirmation records `confirmed`. The state file
contains bounded status/reason codes and timestamps, never the owner's raw
message, screenshot, network trace, or address.

The agent refreshes the same directory after:

- accepted model changes or accepted review promotion;
- package updates that change `viewer/index.html`;
- source-readiness or open-human-request state changes that should appear on the
  health page;
- pending model-change package changes that should appear in the working layer;
- an explicit "show the model" request.

The URL stays stable. Currentness is checked by reading
`VIEWER_PUBLISH_REPORT.json`: it records the package version, package commit,
model revision, validation status, source readiness counts, open human request
count, working-layer counts, publication proof, and content hashes. The browser
reads that report before its named bundle
and refuses a mismatched package version, package commit, model revision,
validation status, or bundle hash. When that check fails, the viewer shows a
blocking official-load error with the failed check instead of falling back to
demo data.

## Deep links the agent shares in chat

The whole interface is hash-routed, so every view has a stable URL:

- `…/#overview` — model health and the review queue. Share this after accepted
  changes when `reviewItems` is not empty.
- `…/#card/<id>` — one card: definition, "is not", links (clickable), backlinks,
  and a technical view on demand. This is the link the agent drops when it wants
  a human to verify a specific card.
- `…/#type/<type>` — all cards of a type (`business`, `artifact`, `metric`, `interface`, …).
- `…/#working` — pending packages and safe candidate cards, all labelled as not
  accepted.
- `…/#process` — interfaces as supplier → subject → customer, plus states.
- `…/#sources`, `…/#questions` — the source map and the structured review
  ledger: open questions, drift, source gaps, stale audits, status risks, and
  open human requests.

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

- process card with `attrs.steps` → **flowchart** with decision diamonds (Да/Нет)
  plus a **step review table**: step id, action/question, role, input, output,
  rule, branch, and warning/missing-field notes;
- state card with `attrs.transitions` → **state diagram** with the event and SLA
  on each arrow plus a **transition matrix**: from, to, trigger, SLA, authority,
  effect, source-of-truth links, and notes;
- state card with `attrs.reason-codes` → **reason codes table** for terminal or
  exception states;
- a card with `attrs.lossReasons` → **table** (`#losses`) — a list, not a diagram;
- decision cards → **Decision contract** table: owner, transition authority,
  measurement convention, propagation SLA, override/exception path, affected
  workflows/KPIs, and blast radius;
- metric cards → **measurement contract** on the card and compact table
  (`#metrics`): formula, unit, target, binding source, refresh cadence, source
  of truth, owner, baseline, and influenced metrics;
- `attrs.criteria` → **checklist**;
- businesses / production systems / interfaces → the typed-link **graph**.

`viewer/sample-clubfirst.json` is an invented dataset that exercises every one of
these formats. It is used only in explicit demo mode (`?demo=1` or `#demo`), not
as a fallback for official loading.

## Data shape

`publish_viewer.py` validates the model with `scripts/links_validate.py
--strict-transitional`, reads workspace state, source readiness, and open human
request counts, then calls `build_viewer_bundle.py`. The bundle emits:

```json
{ "module": "...", "revision": "...", "modelRevision": "...", "asOf": "YYYY-MM-DD",
  "packageVersion": "...", "packageCommit": "...",
  "companyModelLanguage": "ru", "sourceReadiness": {},
  "openHumanRequestCount": 0, "openHumanRequests": [],
  "validationStatus": "passed",
  "generatedAt": "...",
  "cards": [{ "id","type","status","source","owner","lastReviewed","nextAudit",
              "volatility","evidence","aliases",
              "attrs","links","viewer","searchText",
              "title","sections":[{"heading","body"}],"file" }],
  "viewerDiagnostics": [],
  "workingCards": [{ "id","type","status","modelLayer","packageId" }],
  "workingEdges": [{ "from","to","type","modelLayer" }],
  "workingModel": { "packageCount","changeCount","cardCount","packages",
                    "truthBoundary":"working-layer-not-accepted" },
  "edges": [{ "from","to","type" }],
  "sources": [{ "id","trust","owner","accessMode","readPolicy","meaning" }],
  "sourceTrust": {
    "sources": [{ "id","trust","accessMode","dependentCardIds",
                  "dependentCardCount","readinessStatus","lastProofId" }],
    "unresolvedSourceCardIds": [],
    "unknownSourceCardIds": [] },
  "openQuestions": ["..."],
  "reviewItems": [{ "kind","severity","cardId","sourceId","owner","text","action" }],
  "health": { "byStatus","ownerCoveragePct","sourceResolvedPct",
              "unresolvedSourceCardIds","unknownSourceCardIds",
              "stalePastNextAudit","conflicts","hypotheses" } }
```

The `viewer` field is a read-only projection for browser rendering. It preserves
the accepted card shape and adds display-ready lists such as
  `business.viewer.productionSystems`, `production-system.viewer.stages`, and
`process.viewer.processSteps`. This keeps v2 model cards free to use structured
objects (`state/label/processes`, `does/decision`) without forcing the browser
to guess diagram semantics from raw frontmatter.

Official publish blocks when `viewerDiagnostics` is not empty. Those diagnostics
cover display-critical structure that the generic link validator cannot see in
plain links: production-system stage `state/processes/roles`, business
input/output artifacts, and process step `next/yes/no/role` references.

Cards may also carry display-safe trust metadata:

- `volatility` — how often the fact is expected to change;
- `evidence` — evidence or source-event ids, never raw source payloads;
- `aliases` — safe alternate names used by humans.

The `sourceTrust` block turns the source map into a review surface. It shows
which accepted cards depend on each source, whether a matching source instance
has a readiness/proof state, and which cards still have unresolved or `unknown`
source ids. Source readiness is a trust indicator for the reader; it does not
accept, reject, or promote model truth.

`openHumanRequests` is a bounded read-only projection of unanswered operational
store requests. It carries only the request envelope needed for the owner and
agent to act: request id, kind, public role owner, prompt, recommended answer,
blocking package/source refs, asked/due dates, and status. Private transport
channels, message references, direct Telegram identities, email addresses, and
international phone numbers are excluded from the public bundle.
It does not contain raw source payloads, private transcript bodies, or answer
writeback actions. `openHumanRequestCount` may be larger than
`openHumanRequests.length` when the workspace has more open requests than the
viewer limit.

Every official publish runs the `public-viewer-v1` privacy gate before writing
files. The localhost server serves only the current report-named bundle and
refuses directory listings, stale bundles, or a report without a passed privacy
proof.

`reviewItems` is the cockpit queue. It is derived from safe accepted-model
material plus bounded change-package metadata: global drift/open-question bullets, card-local "Open questions" or
"Drift" sections, unresolved sources, failed source readiness, stale audit dates,
specific open human requests, remaining open human request counts, and
non-accepted card statuses, and one safe item per pending change. Text is bounded and
does not include raw source payloads. The viewer must not say "no open questions"
unless `reviewItems` is empty.

`workingCards` contains only schema-valid `candidateCard` projections. A change
without `candidateCard` remains a review item; the viewer never manufactures a
card from a transcript excerpt. Evidence excerpts, locators, raw payloads,
private messages, and transcripts are excluded from both working cards and
review items.

`searchText` is a safe per-card search index. It includes ids, titles, body
sections, attrs, links, owner/source, aliases, evidence ids, SLA/rule fields,
decision authority, and metric bindings. It must not index raw source dumps,
transcripts, secrets, or private messages.

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

Point the truth input only at the accepted Markdown/Git export. The publisher
may also read pending package envelopes from the private operational store, but
projects only safe candidate fields and bounded review metadata. It must not be
fed raw sources, secrets, or PII, and the public bundle carries no raw payloads.

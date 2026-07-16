---
name: show-model
description: "Use when the human asks to see the accepted model, during onboarding wrap-up when a viewer exists, or after an accepted package changes what should be shown."
---

# Show model

## Purpose

Show the human the accepted model in a readable form and, when present, show
pending model-change packages in a visibly separate working layer. The working
layer is never accepted truth. The preferred surface is the read-only viewer
documented in `viewer/README.md`. Chat is a fallback for small slices only.

## When to use

Use this skill when:

- onboarding wrap-up has accepted model content to show;
- a review package has been accepted and the human should inspect the result;
- the human says "show the model", "show this process", or similar;
- a card, map, handoff, funnel, or health view needs a stable link.

Do not use it to show raw sources or private transcripts. A safe staged
candidate may appear only in the labelled working layer, never as accepted.

## Primary surface: official viewer publish

Publish or refresh the official viewer from the accepted export:

```bash
python3 <model-repo>/scripts/validate_model_repo.py --package package/current
python3 package/current/scripts/publish_viewer.py <model-repo> \
  --workspace <workspace> \
  --out-dir <workspace>/viewer \
  --module <module-id> \
  --as-of "$(date +%F)"
```

The published viewer directory must contain:

```text
index.html
ontology.<content-hash>.json
ontology.json
VIEWER_PUBLISH_REPORT.json
```

`index.html` must match the package viewer. Do not present custom HTML as the
current model viewer. The default viewer URL must load the official publish
report and its named versioned bundle, or fail closed with a visible official-load
error. Do not share a link when the page is in explicit demo mode (`?demo=1` or
`#demo`) or when it is showing sample/built-in data. If publish or official load
fails, keep the failure reason and use the text fallback below.

Publication is a runtime capability, not something the agent may invent. Read
`viewer_publication` from workspace runtime config. It has one of three modes:

- `workspace-only`: generate and verify local files; do not claim or share a
  public URL;
- `static-url`: use an operator-provided credential-free HTTPS directory URL;
- `tailscale-funnel`: run the package's privacy-gated viewer service as the
  agent user and bind one host-owned Funnel reverse-proxy path to it. Tailscale
  supplies the HTTPS hostname; no separate domain or hosting account is needed.

Configure the target with the package command. It preserves unrelated host
routes and refuses path collisions:

```bash
python3 package/current/scripts/configure_viewer_publication.py \
  --workspace <workspace> \
  --mode tailscale-funnel \
  --agent-id <agent-id> \
  --path /models/<agent-id>/ \
  --apply
```

The configurator derives a stable local port from the agent id unless `--port`
is explicitly supplied, installs one package-owned `systemd --user` service,
refuses route or service-name collisions, verifies localhost and public hashes,
and records the proof in the publish report. It preserves unrelated Funnel
routes. The host must already allow the agent user to mutate Tailscale Serve/
Funnel configuration; the package never grants that broad host permission.

Do not create an OpenAI Site, a new repository, a hosting project, a domain, or
another provider account to satisfy a show-model request. If the host has no
configured publication capability, keep `workspace-only` and use the bounded
text fallback. Do not retry the same failed host mutation more than twice. If
the human explicitly asks for the host command or path needed to unblock it,
return that one exact copy-ready command or path in a fenced block; this is a
current-turn technical-view response, not a reason to hide the command. Never
include a secret or raw failure tail. A one-off local server is acceptable only
for an operator proof.

After the first accepted model exists, publish the viewer once, keep the same
URL, and refresh the files after every accepted model change, accepted review
promotion, pending model-change package change, package update that changes
`viewer/index.html`, source-readiness change, open human request change, or
explicit "show model" request. The URL
stays stable; `VIEWER_PUBLISH_REPORT.json` proves which model revision and
package version it currently shows. Share a public URL only when
`publication.status` in that report is `verified`.

`publication.status: verified` proves that the configured host serves the
exact viewer bytes. It does not prove that the owner's browser or network can
reach that host. Before copying any viewer URL into an owner-facing response,
claim it through the deterministic delivery gate:

```bash
python3 package/current/scripts/viewer_reachability.py \
  --workspace <workspace> claim
```

Copy `public_url` only when this command returns `shareable: true`. The first
claim for a new URL is allowed once and moves it to `awaiting-owner`. Ask the
owner to confirm whether it opened. Until that confirmation, a second claim
fails closed and returns no URL. A server-side HTTP check, hash match, external
probe, VPN test, or the agent's own browser does not count as owner
confirmation.

When the owner says the page did not open, reports a connection or certificate
error, or sends a browser failure screenshot, record only a bounded failure
code before replying:

```bash
python3 package/current/scripts/viewer_reachability.py \
  --workspace <workspace> record \
  --status unreachable \
  --reason connection-failed
```

Do not copy the same URL again, recommend reload/VPN as the resolution, or
reinterpret successful server probes as evidence against the owner. Replace
the publication target or use the text fallback. After the owner explicitly
confirms that the page opened, record that confirmation:

```bash
python3 package/current/scripts/viewer_reachability.py \
  --workspace <workspace> record --status confirmed
```

The reachability file stores only the URL, timestamps, state, and a bounded
reason code. Never store the owner's message, screenshot, browser trace, IP,
or other raw feedback there.

Use these link shapes:

```text
#overview
#working
#questions
#map
#card/<id>
```

Use `#overview` after accepted changes when the bundle's `reviewItems` is not
empty: it is the review cockpit, not only a health page. Use `#questions` when
the human asks what is unresolved or what they have not answered: the viewer
must show bounded `openHumanRequests` details, not only a count. Use `#card/<id>`
for one concrete verification target. Do not say "no open questions" unless `reviewItems` exists and is empty; older bundles that only have `openQuestions` must be treated as legacy, not as proof of zero review work.

The chat message stays plain and names the publish proof:

```text
I updated the model view. Publish report: <workspace>/viewer/VIEWER_PUBLISH_REPORT.json.
The handoff card is here: <link>.
```

Put ids in links, not in prose, unless the human asks for the technical view.

## Fallback: text showcase

Use this when official publish fails or the human asks for a quick text view.
Name the reason first, then show at most 10 accepted cards:

```text
Viewer fallback: official publish failed because <reason>.
Name - type - status - one-line definition
```

If more than 10 cards are relevant, show the top 10 and offer the viewer link or
the next slice. Do not paste raw source excerpts.

## Validation

Before saying the model was shown:

- the truth layer points to the accepted export; staged material appears only
  through the safe, labelled working projection and raw sources never appear;
- pending packages are labelled `working-layer-not-accepted`, and their raw
  evidence excerpts/locators are absent;
- the publish report has `privacy.status: passed`; direct Telegram identities,
  email addresses, phone numbers, private channel/message references, secret-like values, and
  raw working evidence are absent from the public bundle;
- `VIEWER_PUBLISH_REPORT.json` exists and has status `published`;
- the opened URL is not in explicit demo mode and the page is not showing demo data;
- official-load errors are reported, not hidden by a sample or built-in fallback;
- the report model revision and package version match the current inputs;
- `index.html` hash matches the package viewer;
- a shared public URL comes from the declared runtime publication target and
  has `publication.status: verified`, and the delivery gate returned
  `shareable: true`; otherwise the agent gives a text fallback;
- `publication.infrastructure_status: verified` is described only as host
  proof; owner reachability is `confirmed` only after explicit owner feedback;
- an owner-reported failure is recorded as `unreachable`, and the same URL is
  not repeated even when server-side probes still return HTTP 200;
- the report source-readiness counts and open human request count match current
  workspace state, and `ontology.json.openHumanRequests` shows the bounded
  unanswered request details;
- `ontology.json.reviewItems` is checked before saying there are no open
  questions, drift items, source gaps, stale audits, or unanswered requests;
- model validation used the pinned package wrapper when the model repository
  has `scripts/validate_model_repo.py`;
- the card link uses a stable id;
- the text fallback labels status and uncertainty;
- private source payloads are absent.

## Eval cases

**Case 1 - owner asks to show the accepted handoff process.**
What good looks like: the agent links the viewer map or the accepted workflow
card, gives one plain sentence about what changed, and avoids dumping ids in the
message body.

**Case 2 - viewer is not running.**
What good looks like: the agent says the official publish or host server is not
available, includes the concrete failure reason, shows a text fallback of no
more than 10 accepted cards, and gives the command or host action needed to
refresh the viewer.

**Case 3 - owner reports that the shared URL does not open.**
What good looks like: the agent records `unreachable` with a bounded reason,
does not send the same URL again, and switches the target or uses the text
fallback. Successful host-side or external HTTP probes do not override the
owner's observation.

**Case 4 - owner confirms that the URL opened.**
What good looks like: the agent records `confirmed`; later requests may reuse
the same stable URL through the delivery gate.

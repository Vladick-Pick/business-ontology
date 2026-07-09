---
name: show-model
description: "Use when the human asks to see the accepted model, during onboarding wrap-up when a viewer exists, or after an accepted package changes what should be shown."
---

# Show model

## Purpose

Show the human the accepted model in a readable form. The preferred surface is
the read-only viewer documented in `viewer/README.md`. Chat is a fallback for
small slices only.

## When to use

Use this skill when:

- onboarding wrap-up has accepted model content to show;
- a review package has been accepted and the human should inspect the result;
- the human says "show the model", "show this process", or similar;
- a card, map, handoff, funnel, or health view needs a stable link.

Do not use it to show raw sources, private transcripts, or staged proposals as
if they were accepted.

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
ontology.json
VIEWER_PUBLISH_REPORT.json
```

`index.html` must match the package viewer. Do not present custom HTML as the
current model viewer. The default viewer URL must load the official publish
report and accepted model bundle, or fail closed with a visible official-load
error. Do not share a link when the page is in explicit demo mode (`?demo=1` or
`#demo`) or when it is showing sample/built-in data. If publish or official load
fails, keep the failure reason and use the text fallback below.

Serve the viewer from the host. A one-off local server is acceptable for a
manual proof, but a live OpenClaw install should expose `<workspace>/viewer` at
one permanent static URL through the host's normal static-file route, reverse
proxy, or service manager:

```bash
python3 -m http.server 8787 --directory <workspace>/viewer
```

After the first accepted model exists, publish the viewer once, keep the same
URL, and refresh the files after every accepted model change, accepted review
promotion, package update that changes `viewer/index.html`, source-readiness
change, open human request change, or explicit "show model" request. The URL
stays stable; `VIEWER_PUBLISH_REPORT.json` proves which model revision and
package version it currently shows.

Use these link shapes:

```text
#overview
#questions
#map
#card/<id>
```

Use `#overview` after accepted changes when `ontology.json.reviewItems` is not
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

- the viewer points to the accepted export, not staged proposals or raw sources;
- `VIEWER_PUBLISH_REPORT.json` exists and has status `published`;
- the opened URL is not in explicit demo mode and the page is not showing demo data;
- official-load errors are reported, not hidden by a sample or built-in fallback;
- the report model revision and package version match the current inputs;
- `index.html` hash matches the package viewer;
- the persistent viewer URL serves the same directory that was just published,
  or the agent says that hosting is not available and gives a text fallback;
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

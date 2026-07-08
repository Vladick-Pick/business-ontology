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
current model viewer. If publish fails, keep the failure reason and use the text
fallback below.

Serve the viewer from the host:

```bash
python3 -m http.server 8787 --directory <workspace>/viewer
```

Use these link shapes:

```text
#overview
#map
#card/<id>
```

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
- the report model revision and package version match the current inputs;
- `index.html` hash matches the package viewer;
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

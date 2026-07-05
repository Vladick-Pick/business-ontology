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

## Primary surface: viewer

Build or refresh the viewer bundle from the accepted export:

```bash
python3 scripts/build_viewer_bundle.py <model-repo> --out viewer/ontology.json \
  --module <module-id> --as-of "$(date +%F)"
```

Serve the viewer from the host:

```bash
python3 -m http.server 8787 --directory viewer
```

Use these link shapes:

```text
#overview
#map
#card/<id>
```

The chat message stays plain: "I updated the model view. The handoff card is
here: <link>." Put ids in links, not in prose, unless the human asks for the
technical view.

## Fallback: text showcase

Use this when the viewer is unavailable or the human asks for a quick text view.
Show at most 10 accepted cards:

```text
Name - type - status - one-line definition
```

If more than 10 cards are relevant, show the top 10 and offer the viewer link or
the next slice. Do not paste raw source excerpts.

## Validation

Before saying the model was shown:

- the viewer points to the accepted export, not staged proposals or raw sources;
- the card link uses a stable id;
- the text fallback labels status and uncertainty;
- private source payloads are absent.

## Eval cases

**Case 1 - owner asks to show the accepted handoff process.**
What good looks like: the agent links the viewer map or the accepted workflow
card, gives one plain sentence about what changed, and avoids dumping ids in the
message body.

**Case 2 - viewer is not running.**
What good looks like: the agent says the viewer is not running, shows a text
fallback of no more than 10 accepted cards, and gives the command or host action
needed to refresh the viewer.

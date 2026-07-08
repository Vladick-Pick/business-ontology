# Source intake

Source intake converts real-world materials into source events. It does not
convert them directly into accepted model truth.

## Source intake rule

For every source, register before mining:

- source id;
- kind;
- owner;
- access mode;
- read policy;
- trust level;
- cursor strategy;
- raw payload policy;
- review owner.

If the source is not registered, the agent may inspect enough metadata to
register it, but it should not mine facts yet.

For live or recurring sources, also use the workspace source registry:

```text
source-instances.json
live-proofs/proofs.json
```

`source-instances.json` records the connector identity, cursor ref, output ref,
scheduler ref, and latest proof id. `live-proofs/proofs.json` records proof
refs and `sha256:` hashes. Neither file stores raw messages, transcript text,
meeting URLs, credential values, or private source dumps.

Do not call a source ready from configuration alone. Use `configured` for setup
only, `source-connected` for a valid source artifact without completed model
processing, and `live-proven` only after the source path produces the required
agent artifacts and human-review handoff.

Each normalized source event must classify the claim path before compilation:
`claimKind`, `evidenceGrade`, `sourceRisk`, and `provenanceActivity`. This
keeps agent inference, owner claims, dashboard readings, observed records, and
human decisions separate through review.
Use `sourceRisk: ["no-known-risk"]` only when no source risk was identified;
otherwise classify the concrete risk or use `unknown` alone.

## Telegram

The Telegram default is daily background history intake through an MTProto user
session over the approved native Telegram folder. The agent asks:

```text
At what time should I scan the approved Telegram folder through MTProto?

My recommendation: 09:00 local time.
```

The scan extracts decisions, agreements, new objects, changed definitions,
workflow drift, and open questions since the last cursor. Raw private messages
do not enter the model repository.

`scripts/tg_run_daily_ingest.py --workspace <workspace>` records the
`telegram-mtproto-history` source instance and its
`telegram-history-mtproto-daily-packet` proof. MTProto source readiness is not
proven by OpenClaw message history limits or by unit tests alone.

This path does not send meeting recorder bots. A meeting link found in the
daily packet is historical evidence only; recording starts from a message
delivered to the agent directly or through a group mention.

## Meeting transcripts

Meeting transcript intake is project-scoped. The agent should know why the
meeting belongs to this model before mining it.

Allowed inputs:

- a Zoom, Google Meet, or Microsoft Teams link sent in a direct agent chat;
- a group message with a meeting link that explicitly mentions the agent;
- an explicit owner request for a concrete meeting;
- transcript file provided by the user;
- transcript link from a connected meeting/transcript tool;
- manually pasted transcript excerpt when policy allows it.

The agent extracts business changes and routes them into review. It does not
claim a live recorder/transcript connector unless the host actually provides
one. Meeting recording does not use MTProto, Telegram daily scan, or Telegram
background history collection.

When the local meeting runtime captures a finished Skribby bot, the ingest
input is the packet directory:

```text
source-material/meeting-transcripts/<job-id>/packet.json
source-material/meeting-transcripts/<job-id>/transcript.md
source-material/meeting-transcripts/<job-id>/summary.md
```

The `meeting-transcript-ingest` skill validates the packet and transcript hash
before interpretation. Transcript-derived source events normally use
`sourceKind: meeting-transcript`, connector `skribby`, `trustFloor:
hypothesis`, and source risks such as `auto-transcription-risk`,
`speaker-attribution-uncertain`, and `provider-transcript-unverified`.
Their `provenanceActivity.sourceLocator` and evidence locators must reference
the packet id as `packet:<packetId>#...`; the model-change package and
digest/review handoff must point back to the same packet-derived event. Speaker
labels do not prove owner authority by themselves.

The meeting recording proof path records the `meeting-recorder` source
instance. Packet-only proof is `source-connected`; `live-proven` requires a
packet, source event, model-change package, and digest/review handoff that all
reference the same `packetId`.

## Google Drive

Google Drive intake is folder-scoped. The user gives the relevant folder or the
host connector exposes one. The agent scans file changes, reads allowed
documents, and emits source events with file/revision locators.

Do not request full workspace access when a project folder is enough.

## Dashboards

Dashboard intake checks metric definitions, formula drift, and source-of-truth
concerns. A dashboard snapshot is weaker than a metric contract unless it
contains the formula, owner, source table/system, and update cadence.

## Manual materials

Manual PDFs, Markdown files, CSVs, spreadsheets, and repository docs can seed
the first ontology session. The agent should mine a baseline skeleton first,
then ask one question about the highest-impact gap.

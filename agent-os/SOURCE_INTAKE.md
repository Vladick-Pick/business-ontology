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

Each normalized source event must classify the claim path before compilation:
`claimKind`, `evidenceGrade`, `sourceRisk`, and `provenanceActivity`. This
keeps agent inference, owner claims, dashboard readings, observed records, and
human decisions separate through review.
Use `sourceRisk: ["no-known-risk"]` only when no source risk was identified;
otherwise classify the concrete risk or use `unknown` alone.

## Telegram

The Telegram default is daily read scanning for chats where the bot is present
or for user-provided exports. The agent asks:

```text
At what time should I scan Telegram chats where you add me?

My recommendation: 09:00 local time.
```

The scan extracts decisions, agreements, new objects, changed definitions,
workflow drift, and open questions since the last cursor. Raw private messages
do not enter the model repository.

## Meeting transcripts

Meeting transcript intake is project-scoped. The agent should know why the
meeting belongs to this model before mining it.

Allowed inputs:

- transcript file provided by the user;
- transcript link from a connected meeting/transcript tool;
- manually pasted transcript excerpt when policy allows it.

The agent extracts business changes and routes them into review. It does not
claim a live Fireflies connector unless the host actually provides one.

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

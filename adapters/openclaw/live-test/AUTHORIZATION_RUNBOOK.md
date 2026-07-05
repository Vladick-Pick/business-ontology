# Authorization runbook

The agent initiates authorization, but the human approves every external
access. The agent must not collect secrets through Telegram.

## GitHub

Use a GitHub App for repository access. The agent asks the human to install the
app for a selected repository or organization.

Before the live test, the operator must choose one concrete access path:

1. **Existing GitHub App**: provide the app name and installation URL or the
   host-native authorization screen that grants selected-repository access.
2. **Host-selected repository authorization**: use the OpenClaw or host
   provider's repository picker if it can grant selected-repository GitHub
   access without exposing secrets in Telegram.
3. **Setup-only dry run**: if no authorization path exists yet, mark GitHub as
   `requested-not-configured`. The agent may continue to the first ontology
   question, but must not claim it can write branches or pull requests.

Minimum expected permissions:

- metadata: read;
- contents: read/write;
- pull requests: read/write.

The GitHub App or selected repository authorization may prepare a branch or pull
request. It must not bypass human review or merge accepted truth by itself.

The agent must record which path was used, the repository owner/name, whether
human read access was verified, and whether branch or pull request creation was
actually tested. If branch or pull request creation was not tested, the live test
passes only as a bootstrap/setup test.

## Telegram

The human maps selected Telegram groups named `Systematization {Business}` to
one business scope each. The agent asks for the daily ingest scan time,
timezone, chat ids, optional topic ids, owner, and cursor storage path. Use
`adapters/openclaw/TELEGRAM_GROUPS.md` and `skills/daily-ingest/SKILL.md`.

If the group should be processed without explicit mentions, the operator must
prove that the host event source sees unmentioned group messages and has durable
cursor storage. Telegram `historyLimit` is not enough for the daily scan.

The live test only proves Telegram setup unless the host runtime already
provides message capture, durable cursors, scheduling, and source-event output.
Without those pieces, Telegram readiness is `setup-only` or `source-connected`,
not `live-proven`.

## Skribby and Fireflies

Use `adapters/openclaw/MEETING_TRANSCRIPTS.md` for meeting links posted in
mapped Telegram groups. Skribby is the recorder path for this live-test flow.
Fireflies is superseded by Skribby here and remains only legacy provider
documentation.

Skribby credentials must be stored in the host secret store or environment, not
pasted into chat.

## gog Google Workspace

gog Google Workspace is optional Block B source setup. If the owner chooses it,
the agent asks the human to run or approve the gog OAuth setup for the required
read-only services:

- Calendar for project meeting discovery;
- Drive for selected folders;
- Docs for documents in selected folders;
- Sheets only when a selected source requires it.

The agent then asks for the Drive folder and Calendar filters that belong to
the module under test.

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

The human adds the OpenClaw bot to selected groups. The agent asks for the
daily scan time, timezone, chat list, and whether group topics are in scope.

If the group should be processed without explicit mentions, the operator checks
OpenClaw ambient room events and Telegram privacy mode. If prior history is
needed, the agent asks for a manual export backfill.

The live test only proves Telegram setup unless the host runtime already
provides message capture, durable cursors, scheduling, and source-event output.
Without those pieces, Telegram status is `setup-only`, not `active`.

## Fireflies

The agent asks whether Fireflies is enabled. If yes, it asks which mode is
approved:

1. Human provides a meeting URL and asks the agent to invite Fireflies.
2. Human provides a transcript id or transcript file.
3. Human connects selected project meeting events later.

Fireflies credentials must be stored in the host secret store or environment,
not pasted into chat.

## gog Google Workspace

The agent asks whether gog Google Workspace is enabled. If yes, it asks the
human to run or approve the gog OAuth setup for the required read-only services:

- Calendar for project meeting discovery;
- Drive for selected folders;
- Docs for documents in selected folders;
- Sheets only when a selected source requires it.

The agent then asks for the Drive folder and Calendar filters that belong to
the module under test.

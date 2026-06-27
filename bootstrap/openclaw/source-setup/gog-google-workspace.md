# gog Google Workspace source setup

Goal: use gog to read selected Google Workspace material for the module under
test. gog is the Google Workspace CLI layer for Gmail, Calendar, Drive,
Contacts, Sheets, and Docs. This setup uses read-only source intake.

## First OAuth setup

The agent asks whether gog Google Workspace is enabled. If yes, the human runs
or approves the gog OAuth setup outside Telegram. Do not paste OAuth secrets or
tokens into Telegram.

Default services for this project:

- Calendar for project meeting discovery;
- Drive for selected folders;
- Docs for documents in selected folders;
- Sheets only when a selected module source requires it.

## Drive and Docs

Ask the human for:

- Drive folder;
- whether subfolders are included;
- which Docs are in scope;
- who owns the folder;
- what must be redacted.

## Calendar

Ask the human for:

- Calendar filters;
- project meeting title patterns;
- date range;
- whether recurring meetings are in scope;
- which meetings should route to Fireflies.

## Rules

- read-only by default;
- selected folders, Docs, and Calendar filters only;
- no broad Workspace crawl;
- no credential values in files or chat;
- output is a redacted source event, not an ontology card.

Output contract:

- source kind: `google-drive` for Drive file/folder events;
- source kind: `document` for extracted Docs/document content;
- source kind: `calendar-event` for selected Calendar meeting metadata;
- connector name: `gog`;
- evidence locators name the provider object id, section, or event time;
- content summaries exclude secrets, private messages, and PII.

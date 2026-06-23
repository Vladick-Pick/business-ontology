# Google Drive source setup

Goal: read selected Drive artifacts and convert them into redacted source
events. Drive is a raw source layer, not the accepted model repository.

Ask the human for:

- which folders or files are in scope;
- whether the agent should use a connected Google Drive app, service account,
  or manual exports;
- who owns the documents;
- whether comments, revision history, or only current content are in scope;
- what information must be excluded or redacted.

Default permissions:

- read-only;
- selected folders or files only;
- no write-back to Drive;
- no raw document dumps in the model repository;
- source events contain evidence locators, hashes, summaries, and bounded
  excerpts only.

Output contract:

- source kind: `google-drive`;
- one source event per meaningful artifact or artifact group;
- evidence locator should identify the Drive file and section without storing
  private URLs in public model text.


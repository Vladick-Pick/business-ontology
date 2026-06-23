# Transcript source setup

Goal: convert meeting transcripts into source events for model drift and
decision review. Transcript storage is a raw source layer, not the accepted
model repository.

Ask the human for:

- transcript provider or export format;
- which meetings are in scope;
- whether audio/video files are excluded;
- participant redaction rules;
- retention policy;
- who can approve decisions inferred from meetings.

Default permissions:

- read-only transcript intake;
- no raw transcript storage in the accepted model repository;
- no audio or video copies in the agent workspace unless explicitly approved;
- source events contain meeting metadata, summaries, bounded excerpts, hashes,
  and evidence locators.

Output contract:

- source kind: `meeting-transcript`;
- one source event per meeting or decision cluster;
- mark inferred decisions as `candidate` or `hypothesis` until reviewed.


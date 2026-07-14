# Transcript source setup

Goal: convert meeting transcripts into source events for model drift and
decision review. Transcript bodies live only under
`<raw_source_root>/meetings/<meeting>/`, where `raw_source_root` comes from the
workspace runtime config. This is a private raw source layer, not ordinary
workspace context or the accepted model repository.

Ask the human for:

- transcript provider or export format;
- which meetings are in scope;
- whether audio/video files are excluded;
- participant redaction rules;
- retention policy;
- who can approve decisions inferred from meetings.

Default permissions:

- read-only transcript intake;
- no raw transcript storage outside the configured private raw root;
- no audio or video copies in the agent workspace unless explicitly approved;
- source events contain meeting metadata, redacted findings, hashes, and
  evidence locators, not full transcript bodies.

Output contract:

- source kind: `meeting-transcript`;
- one source event per meeting or decision cluster;
- mark inferred decisions as `candidate` or `hypothesis` until reviewed.
- keep `raw_source_root` out of Git, support bundles, traces, logs, digests,
  chat, model exports, and normal agent context.

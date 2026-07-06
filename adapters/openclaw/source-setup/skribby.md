# Skribby source setup

Goal: send a provider recorder into a specific Zoom, Google Meet, or Microsoft
Teams meeting, then convert the redacted transcript into `meeting-transcript`
source events. Skribby is a transcript provider, not an accepted model store and
not a truth gate.

## Ask the owner

- Which group chats may trigger recorder orders when the message explicitly
  mentions the agent?
- Which business id should that chat map to?
- Who owns review of decisions inferred from those transcripts?
- Is the recorder allowed from direct agent chat, group mentions, or both?
- What PII must be redacted before source events are written?
- Should Skribby replace Fireflies for this instance, or run as a separate
  provider for selected meetings?

Do not use Telegram MTProto, the daily Telegram scan, or Telegram folder exports
to trigger Skribby recorder orders. Those belong to Telegram background history
intake. Skribby starts from a host-delivered message addressed to the agent.

## Source registration

Use these defaults unless the owner says otherwise:

```text
source kind: meeting-transcript
connector: skribby
access mode: api-read after meeting bot webhook
trust level: instance/observed for transcript presence; claim/inference for extracted decisions
read policy: no raw payloads in repo; redacted transcript events only
cursor strategy: bot_id plus provider transcript-ready event timestamp
review owner: instance owner or named module owner
```

## Secrets

Use one key per deployed agent instance. Isolation is the per-instance OpenClaw
environment: the variable name stays the same, but the value belongs only to
that instance and is not shared between resident agents.

Configure only environment variable names in host setup:

```text
SKRIBBY_API_KEY
MEETING_RECORDING_DB
MEETING_RECORDING_PUBLIC_BASE_URL
MEETING_RECORDING_SERVICE_URL
OPENCLAW_MEETING_PROCESS_HOOK_URL
OPENCLAW_HOOKS_TOKEN
```

Never ask for or paste secret values in chat, repository files, run manifests,
or source events.

Use the bot name pattern `{AgentName} · recorder` so meeting records are
distinguishable when several resident agents use Skribby.

## Runtime order path

Start the local runtime after host secrets and a public webhook base URL are
configured:

```bash
python3 scripts/run_meeting_recording_service.py \
  --host 127.0.0.1 \
  --port 8765 \
  --db "$MEETING_RECORDING_DB" \
  --workspace "$OPENCLAW_WORKSPACE"
```

Order the recorder through the runtime:

```bash
python3 scripts/meeting_recording_cli.py order \
  --service-url "$MEETING_RECORDING_SERVICE_URL" \
  --meeting-url "https://zoom.us/j/123456789" \
  --business-id "biz-acquisition" \
  --source-id "tg-group-acquisition" \
  --chat-ref "-100123/77" \
  --requested-by "owner" \
  --agent-mentioned
```

Expected response:

```json
{
  "bot_id": "bot_123",
  "job_id": "mtgrec-20260706-abcdef12",
  "provider": "skribby",
  "status": "bot_created"
}
```

`scripts/skribby_order_bot.py` remains a dry-run payload diagnostic only. It
must not create live bots because it does not persist jobs, webhook nonces, or
transcript packet state.

Neither script prints `SKRIBBY_API_KEY`.

## Webhook and transcript path

Expose the runtime endpoint publicly:

```text
POST ${MEETING_RECORDING_PUBLIC_BASE_URL}/webhooks/skribby
```

The runtime treats this Skribby event as transcript-ready:

```json
{
  "type": "status_update",
  "data": {"new_status": "finished"},
  "custom_metadata": {
    "job_id": "mtgrec-20260706-abcdef12",
    "webhook_nonce": "<generated per job>"
  }
}
```

The raw nonce is generated per job, sent to Skribby in `custom_metadata`, and
verified against a hash in the local job store. Webhooks with a missing or wrong
nonce are rejected before transcript fetch. Then the runtime fetches:

```text
GET https://platform.skribby.io/api/v1/bot/{bot_id}
```

The run is not live-proven until the response contains transcript segments or
text, speaker identity or speaker ids, timestamps, and the runtime writes
`packet.json` under `source-material/meeting-transcripts/<job_id>/`.

## Output contract

- source kind: `meeting-transcript`;
- connector name: `skribby`;
- one redacted source event per meeting or decision cluster;
- evidence locators point to bot id, transcript timestamp ranges, and redacted
  excerpt hashes;
- decisions stay `candidate` or `hypothesis` until human review;
- full raw transcript, audio, video, webhook payloads, and tokens stay outside
  the model repository.

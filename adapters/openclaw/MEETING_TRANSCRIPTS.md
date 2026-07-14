# Meeting transcript recorder pipeline

This contract covers provider-backed meeting transcript intake for OpenClaw
instances. The source kind stays `meeting-transcript`; Skribby and Fireflies are
providers, not accepted model stores and not truth gates.

## Trigger

A Zoom, Google Meet, or Microsoft Teams link is actionable only when OpenClaw
delivers the message to the agent as a direct chat message, or as a group
message that explicitly mentions the agent. The agent replies in the same chat
that it sent the recorder. In other group traffic, the agent does not order a
recorder unless the owner explicitly asks for that concrete meeting.

The trigger is narrow on purpose: it only authorizes joining that meeting. It
does not authorize calendar-wide access, raw audio storage, or accepted-model
writes.

This path is independent from Telegram background history intake. MTProto,
daily scan packets, and Telegram folder exports must not be used to trigger
meeting recorder orders.

## Instance isolation

Use one key per deployed agent instance. Each deployed resident agent uses its
own recorder credential through that instance's per-instance OpenClaw
environment. The Skribby key is available only by environment variable name:

```text
SKRIBBY_API_KEY
```

Keys are not shared between instances. Do not paste the value into chat, config
examples, logs, source events, model repositories, or run manifests. The default
bot name makes recordings distinguishable:

```text
{AgentName} · recorder
```

## Order request

The production order path is the local `MeetingRecordingRuntime`, not n8n and
not a direct Skribby call from the agent. The agent calls:

```bash
python3 scripts/meeting_recording_cli.py order \
  --service-url "$MEETING_RECORDING_SERVICE_URL" \
  --meeting-url "https://zoom.us/j/123456789" \
  --business-id "biz-acquisition" \
  --source-id "src-meeting-skribby" \
  --chat-ref "-100123/77" \
  --requested-by "owner" \
  --agent-mentioned
```

The runtime persists a job, then uses the currently documented create-bot path:

```text
POST https://platform.skribby.io/api/v1/bot
```

The payload contains:

```json
{
  "meeting_url": "https://zoom.us/j/123456789",
  "service": "zoom",
  "bot_name": "Ontology Agent recorder",
  "transcription_model": "whisper",
  "webhook_url": "https://<gateway>/webhooks/skribby",
  "custom_metadata": {
    "job_id": "mtgrec-20260706-abcdef12",
    "business_id": "biz-acquisition",
    "source_id": "tg-group-acquisition",
    "chat_ref": "-100123/77",
    "requested_by": "owner",
    "webhook_nonce": "<generated per job>"
  }
}
```

`custom_metadata` is required operationally even though the provider treats it as
optional. It makes the webhook return self-routing: the instance can attach the
transcript to the correct job, business, source, and chat message without a
second lookup. The runtime stores a hash and redacted display URL for the
meeting; it does not persist raw meeting URL query tokens or the raw webhook
nonce.

## Return path

The meeting recording runtime exposes:

```text
POST https://<gateway>/webhooks/skribby
```

It accepts the currently documented Skribby finished event:

```json
{
  "bot_id": "bot_123",
  "type": "status_update",
  "data": {"new_status": "finished"},
  "custom_metadata": {
    "job_id": "mtgrec-20260706-abcdef12",
    "webhook_nonce": "<generated per job>"
  }
}
```

The runtime rejects the webhook with `401` if the nonce is missing or does not
match the stored hash. On authenticated `finished`, the runtime fetches the bot
details and transcript from:

```text
GET https://platform.skribby.io/api/v1/bot/{bot_id}
```

Non-finished events return `202` and do not fetch. A duplicate finished webhook
returns the existing packet path without fetching again. A bot-id mismatch
returns `409`. A finished webhook with an empty transcript marks the job failed
and does not write a packet.

Operator recovery is allowed only after a lost webhook. The command
`scripts/meeting_recording_cli.py recover --job-id <job>` fetches the finished
bot through `GET /api/v1/bot/{bot_id}`, writes the same packet shape, and marks
`completion_source: recovery`. It does not synthesize a webhook timestamp and
does not satisfy `live-proven`; it only recovers usable source material.

After packet capture, the runtime wakes OpenClaw with:

```text
process meeting transcript <packet_path>
```

If `OPENCLAW_MEETING_PROCESS_HOOK_URL` or `OPENCLAW_HOOKS_TOKEN` is not
configured, the job still becomes `packet_ready` with `wakeup_pending=1`. That
is an operational delivery gap, not a polling runtime path.

## Processing

The runtime writes the full transcript and packet before any LLM/agent
interpretation:

```text
<raw_source_root>/meetings/<job_id>/
  transcript.md
  summary.md
  packet.json
```

`raw_source_root` is the single value from the workspace runtime config. The
service resolves relative values from that config's directory and writes no
meeting body to an independent output root. The raw tree is private source
storage and is excluded from Git, support bundles, model exports, traces, logs,
digests, chat, and normal agent context.

`packet.json` contains addressable transcript segments. When Skribby returns a
top-level transcript item with nested `utterances`, the runtime expands the
utterances into `segments` with stable ids such as `seg-00001`. Agent artifacts
must cite packet locators such as `packet:<packetId>#seg-00001`, not only the
whole transcript.

The agent processes `packet.json` inside the raw tree after capture and emits a
redacted source event that keeps locators and hashes rather than the full
transcript body:

```text
kind: meeting-transcript
connector: skribby
claimKind: agent-inference or owner-claim, depending on evidence
evidenceGrade: inference, claim, or instance
```

The call summary becomes a workspace note, not an accepted ontology card.
`extract-from-input` may produce candidate packages from the redacted transcript.
Urgent clarifications go back to the group only when the owner policy allows it;
everything else goes to the next digest.

n8n is historical inspiration only. It is not a runtime dependency for ordering,
webhook handling, transcript fetching, packet capture, or OpenClaw wakeup.

## Storage limits

Do not store these artifacts in the model repository:

- raw audio or video;
- provider recording files;
- full unredacted transcript payloads;
- webhook payloads containing personal contact data;
- credential values or bearer headers.

These raw artifacts belong only under `<raw_source_root>/meetings/`. Derived
workspace artifacts, model state, and operational logs retain packet locators,
`sha256:` hashes, counts/status, and minimal redacted metadata.

Source locators may point to provider ids, bot ids, timestamps, and redacted
excerpt hashes.

## Fireflies overlap

`adapters/openclaw/source-setup/fireflies.md` remains a valid provider setup for
the same `meeting-transcript` source kind. Skribby does not change the source
class; it adds a recorder-provider path optimized for meeting links addressed to
the agent in direct chat or group mentions. The owner decides at deployment
whether Skribby replaces Fireflies for a given instance.

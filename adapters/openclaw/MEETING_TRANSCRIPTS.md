# Meeting transcript recorder pipeline

This contract covers provider-backed meeting transcript intake for OpenClaw
instances. The source kind stays `meeting-transcript`; Skribby and Fireflies are
providers, not accepted model stores and not truth gates.

## Trigger

A Zoom, Google Meet, or Microsoft Teams link in the mapped Systematization group
is treated as consent to send the configured recorder bot. The agent replies in
the group that it sent the recorder. In other chats, the agent does not order a
recorder unless the owner explicitly asks for that concrete meeting.

The trigger is narrow on purpose: it only authorizes joining that meeting. It
does not authorize calendar-wide access, raw audio storage, or accepted-model
writes.

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

The local helper uses the currently documented create-bot path:

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
  "webhook_url": "https://<gateway>/hooks/skribby",
  "custom_metadata": {
    "business_id": "biz-acquisition",
    "chat_id": "-100123",
    "source_id": "tg-group-acquisition",
    "telegram_message_ref": "-100123/77"
  }
}
```

`custom_metadata` is required operationally even though the provider treats it as
optional. It makes the webhook return self-routing: the instance can attach the
transcript to the correct business, chat, source, and Telegram message without a
second lookup.

## Return path

The OpenClaw gateway exposes:

```text
https://<gateway>/hooks/skribby?token=<OPENCLAW_HOOKS_TOKEN>
```

`hooks.mappings` converts the deploy-time verified transcript-ready event into
an agent wakeup:

```text
process meeting transcript <bot_id>
```

The exact transcript-ready event name and fetch path are not pinned in this
repository. Context7 and the Skribby docs currently show more than one path:

- create bot: `POST /api/v1/bot`;
- alternate create surface: `POST /api/bots`;
- bot details: `GET /api/bots/{bot_id}`;
- bot details with transcript: `GET /api/v1/bot/{id}`;
- recording transcript: `GET /recording/{id}`.

At deployment, verify the exact OpenAPI schema and record which event means
"transcript is ready". Do not treat `bot.finished` as transcript-ready until a
live deploy proves the transcript is present on the chosen fetch path.

## Processing

The agent fetches the transcript after the verified ready event, redacts PII,
and emits a source event:

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

## Storage limits

Do not store these artifacts in the model repository:

- raw audio or video;
- provider recording files;
- full unredacted transcript payloads;
- webhook payloads containing personal contact data;
- credential values or bearer headers.

Source locators may point to provider ids, bot ids, timestamps, and redacted
excerpt hashes.

## Fireflies overlap

`adapters/openclaw/source-setup/fireflies.md` remains a valid provider setup for
the same `meeting-transcript` source kind. Skribby does not change the source
class; it adds a recorder-provider path optimized for meeting links posted in
Telegram groups. The owner decides at deployment whether Skribby replaces
Fireflies for a given instance.

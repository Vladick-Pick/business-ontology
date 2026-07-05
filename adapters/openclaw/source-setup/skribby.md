# Skribby source setup

Goal: send a provider recorder into a specific Zoom, Google Meet, or Microsoft
Teams meeting, then convert the redacted transcript into `meeting-transcript`
source events. Skribby is a transcript provider, not an accepted model store and
not a truth gate.

## Ask the owner

- Which Systematization chat may trigger automatic recorder orders?
- Which business id should that chat map to?
- Who owns review of decisions inferred from those transcripts?
- Is the recorder allowed only when a meeting link is posted in the mapped chat,
  or also when the owner explicitly asks in a direct chat?
- What PII must be redacted before source events are written?
- Should Skribby replace Fireflies for this instance, or run as a separate
  provider for selected meetings?

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
OPENCLAW_HOOKS_TOKEN
```

Never ask for or paste secret values in chat, repository files, run manifests,
or source events.

Use the bot name pattern `{AgentName} · recorder` so meeting records are
distinguishable when several resident agents use Skribby.

## Local order helper

Dry-run a payload:

```bash
python3 scripts/skribby_order_bot.py \
  --meeting-url "https://zoom.us/j/123456789" \
  --bot-name "Ontology Agent · recorder" \
  --webhook-url "https://<gateway>/hooks/skribby" \
  --business-id "biz-acquisition" \
  --chat-id "-100123" \
  --source-id "tg-group-acquisition" \
  --telegram-message-ref "-100123/77" \
  --dry-run
```

Order the recorder only after host secrets are configured:

```bash
SKRIBBY_API_KEY="$SKRIBBY_API_KEY" python3 scripts/skribby_order_bot.py \
  --meeting-url "https://meet.google.com/abc-defg-hij" \
  --bot-name "Ontology Agent · recorder" \
  --webhook-url "https://<gateway>/hooks/skribby" \
  --business-id "biz-acquisition" \
  --chat-id "-100123" \
  --source-id "tg-group-acquisition" \
  --telegram-message-ref "-100123/77"
```

The script prints only:

```json
{
  "bot_id": "bot_123",
  "status": "created"
}
```

It does not print `SKRIBBY_API_KEY`.

## OpenClaw mapping sketch

Fill the exact event name and payload schema from
`docs.skribby.io/rest-api/openapi` at deploy time. The placeholder below is a
shape contract, not a proven production config.

```yaml
hooks:
  token: ${OPENCLAW_HOOKS_TOKEN}
  mappings:
    skribby:
      path: /hooks/skribby
      requireToken: true
      when:
        provider: skribby
        event: "<deploy-time transcript-ready event>"
      wake:
        text: "process meeting transcript ${data.bot_id}"
        metadata:
          business_id: "${data.custom_metadata.business_id}"
          chat_id: "${data.custom_metadata.chat_id}"
          source_id: "${data.custom_metadata.source_id}"
          telegram_message_ref: "${data.custom_metadata.telegram_message_ref}"
```

At deploy time, pin the fetch path as one of the documented candidates, then
verify with a real meeting:

- `GET /api/bots/{bot_id}`;
- `GET /api/v1/bot/{id}`;
- `GET /recording/{id}` when the bot response points to a recording id.

The run is not complete until the verified response contains transcript
segments or text, speaker identity or speaker ids, and timestamps.

## Output contract

- source kind: `meeting-transcript`;
- connector name: `skribby`;
- one redacted source event per meeting or decision cluster;
- evidence locators point to bot id, transcript timestamp ranges, and redacted
  excerpt hashes;
- decisions stay `candidate` or `hypothesis` until human review;
- full raw transcript, audio, video, webhook payloads, and tokens stay outside
  the model repository.

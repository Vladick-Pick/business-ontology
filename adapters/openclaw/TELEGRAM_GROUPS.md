# Telegram Groups

OpenClaw Telegram groups are source surfaces for one business at a time. A
group named `Systematization {Business}` maps to one business ontology scope and
one source id such as `tg-group-{business}`. The group is not the accepted model;
it is a read source whose messages can become source events and review packages.

## OpenClaw Configuration

Use selected groups only. Context7/OpenClaw docs show per-group configuration
under `channels.telegram.groups.<chatId>` with `requireMention`, optional
per-group `systemPrompt`, topic routing, and `historyLimit: 50`. The daily scan
MUST NOT rely on `historyLimit`; it is only enough for short interaction
context. Daily ingest uses folder exports or a host-proven stored event source.

Example shape:

```json5
{
  channels: {
    telegram: {
      groups: {
        "*": { requireMention: true },
        "-1001234567890": {
          requireMention: false,
          systemPrompt: "You are in Systematization Acquisition. Treat chat content as source evidence, not accepted truth."
        }
      }
    }
  }
}
```

## Source Mapping

For each approved group, record:

- Telegram `chat_id`;
- optional topic ids;
- business id;
- source id, default `tg-group-{business}`;
- owner id;
- review channel;
- redaction rules;
- daily scan timezone and output location outside the model repository.

Participants help populate role claims, but participant names, handles, phone
numbers, and raw message bodies do not enter the accepted model repository.

## Interaction Behavior

The group can be used for:

- direct mentions to ask the resident analyst a question;
- proactive mentions when the agent needs a clarification;
- daily batch review summaries;
- source observations that become redacted source events.

The agent should batch noisy observations and respect the configured quiet
window. It should ask one concrete question at a time and keep the technical
artifact path out of normal chat unless the human asks for it.

## Channel Authority

Review is still the trust gate. Telegram messages are claims until a permitted
review actor makes an explicit review action.

| Review item | Who can decide |
|---|---|
| Routine changes for business X | Owner DM, or any participant in `Systematization {X}` when the group is approved for that business. |
| **High-risk** source-of-truth, authority, permission, or measurement-convention changes | **Owner DM only by default.** The owner may explicitly expand this authority in the source setup record. |
| Cross-business changes | The owners of each affected business, or owner DM if the source setup does not name a joint channel. |
| Unmapped groups or other chats | No review decision is accepted; the message is only an observation. |

High-risk decisions include the top review tier in `specs/REVIEW-SPEC.md`:
source-of-truth, authority, and measurement/metric convention changes. Group
agreement is not enough for those by default.

Every accepted review action must record actor, channel, timestamp, affected
ids, rationale, and whether the action came from owner DM or an approved group.

## Conflict Handling

If group participants disagree, the agent opens a conflict review instead of
choosing a winner. If a group attempts to accept a high-risk item, the agent
records the attempt as evidence and asks the owner in DM.

## Live Adapter Boundary

The folder-first collector is the implemented local path. MTProto or OpenClaw
stored-event reading is a later adapter after a live proof that the source sees
unmentioned group messages, has durable cursor storage, and can write redacted
source events without storing raw private messages in the model repository.

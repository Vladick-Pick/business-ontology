# Interaction contract

Agent runtime configuration. NOT part of the company model. Changed by the
human in chat at any time; the agent confirms the new contract and reschedules
its cron jobs.

Generated for: {{MODULE_NAME}}
Generated at: {{GENERATED_AT}}

## Rhythm

Current rhythm: daily

Available profiles:

- immediate: scans during the working window and a same-day summary;
- daily: default, one morning digest at 09:00;
- weekly: silent daily scans and one Monday digest.

## Digest

Digest time: 09:00
Timezone: ask-owner
Default channel: Telegram DM with the owner

High-risk findings are the first line of the next digest. There is no separate
urgent lane unless the owner changes this contract.

## Quiet window

Quiet window: 22:00-09:00

The quiet window is one-way: the agent does not send outbound messages during
the window, but it answers if the owner writes first.

## Channels

Text: Telegram DM with the owner by default.
Visuals: server-hosted model viewer links.

## Cron mirror

Human-readable mirror:

```text
I scan sources at night, bring the digest at 09:00, and stay quiet after 22:00
unless you write first.
```

## Change log

- {{GENERATED_AT}}: created with default daily rhythm.

# OpenClaw scheduling contract

Scheduling has two separate controls. Do not use one as the other.

## 1. Silent system heartbeat

The resident analyst heartbeat is an OpenClaw per-agent setting, not an owner
reminder and not a cron job:

```json
{
  "every": "2h",
  "target": "none",
  "directPolicy": "block",
  "isolatedSession": true,
  "lightContext": true
}
```

It reads `HEARTBEAT.md`, runs the installed package's
`scripts/system_heartbeat.py`, atomically refreshes
`agent-state/system-health.json`, and returns `HEARTBEAT_OK` internally. It
never delivers a message or answers an open owner request.

Configure this object explicitly on each resident analyst. Do not rely on the
Gateway default. Verify the exact agent entry after configuration.

## 2. Owner reminder cron

An owner reminder exists only after the owner explicitly confirms one complete
profile:

- cadence and local time;
- IANA timezone;
- channel and delivery destination;
- quiet window;
- message language.

Ask one question and recommend one complete answer. The default recommendation
is daily at 09:00 in the owner's timezone, in the owner-controlled Telegram DM,
with a 22:00-09:00 quiet window. If any field is missing, leave the reminder
unconfigured and create no cron job.

Store the confirmed values in
`agent-state/managed-scheduling.json` under `owner_reminder`. Keep the delivery
destination and account out of chat, logs, install reports, and support
artifacts. Record only the inbound message reference and timestamp as evidence
of owner confirmation; never copy the reply body. Keep the scheduling file and
its migration backup at mode `0600`, with parent directories at `0700`.

The only package-owned reminder identity is:

```text
business-ontology:<agent-id>:owner-reminder
```

Use the same value for `--name` and `--declaration-key`. OpenClaw then converges
repeat declarations instead of creating another job. The command payload is
the deterministic renderer, not an agent prompt:

```bash
openclaw cron add \
  --name "business-ontology:<agent-id>:owner-reminder" \
  --declaration-key "business-ontology:<agent-id>:owner-reminder" \
  --agent "<agent-id>" \
  --cron "<owner-confirmed cron expression>" \
  --tz "<owner-confirmed IANA timezone>" \
  --session isolated \
  --command-argv '["python3","<installed-package>/scripts/owner_reminder.py","--workspace","<workspace>","--agent-id","<agent-id>"]' \
  --command-cwd "<workspace>" \
  --announce \
  --channel "<owner-confirmed channel>" \
  --to "<owner-confirmed destination>"
```

Add `--account <account-id>` only when the selected channel requires it. Do not
use `--best-effort-deliver`: a failed owner reminder must remain observable.

At each run, `owner_reminder.py` re-reads current open requests and the latest
system-health snapshot. It renders exactly one current question with a
recommendation and consequence, renders one plain health warning, or prints
`NO_REPLY`. It also enforces the quiet window from managed scheduling. An
unchanged open request may appear in the next confirmed cadence window.

## Verification

After any change, inspect `openclaw cron list --all --json` and prove:

- exactly one job has the declaration key;
- its agent id, cron expression, timezone, isolated session, channel,
  destination, and optional account match the confirmed profile;
- no source, drift, Bitrix, meeting, or other agent job changed;
- an empty actionable queue produces no delivery;
- a non-empty queue produces one plain reminder;
- the quiet window produces no delivery.

Do not print the stored destination during normal owner chat. A redacted
postflight may report only that the destination matched.

## Changing or disabling the reminder

A direct owner instruction may replace the profile. Correlate the exact reply,
update the one managed scheduling object, and repeat the same declaration. Do
not create a second job.

To disable reminders, remove only the job whose declaration key matches this
agent and mark `owner_reminder.configured=false`. Leave the silent heartbeat and
all source jobs unchanged.

## Source and meeting jobs are separate

Telegram history collection, non-Telegram source scans, drift sweeps, package
checks, and Bitrix jobs keep their own schedules and owners. This contract does
not create, replace, or delete them. The meeting recording runtime is event-driven;
a cron job must not order recorder bots or poll historical meeting links.

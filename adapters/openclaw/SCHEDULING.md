# OpenClaw scheduling contract

OpenClaw schedules the resident loop from the private agent workspace. The
interaction rhythm is runtime configuration, not company-model truth. The
current user-facing contract is in `INTERACTION_CONTRACT.md`; this file maps
that contract to cron jobs.

Use `openclaw cron add` for examples. Verify verb via
`openclaw cron --help` at deploy time on the live instance before installing
jobs. Context7 currently shows `cron add`:

```bash
openclaw cron add --name daily-inbox-triage --cron "0 8 * * 1-5" --message "..."
```

`openclaw cron create` may be available as an alias for `openclaw cron add`;
confirm aliases with `openclaw cron --help` during deployment.
`--webhook <url>` is incompatible with chat delivery flags such as `--announce`,
`--channel`, and `--to`.

## Daily profile (default)

Use this after onboarding unless the owner chooses another rhythm.

```bash
openclaw cron add \
  --name "tg-daily-export" \
  --cron "0 3 * * *" \
  --tz "<owner IANA timezone>" \
  --session isolated \
  --command "<host telegram export command from plan 009>"
```

```bash
openclaw cron add \
  --name "sources-scan" \
  --cron "30 3 * * *" \
  --tz "<owner IANA timezone>" \
  --session isolated \
  --message "Scan connected non-Telegram sources and prepare source events."
```

```bash
openclaw cron add \
  --name "morning-digest" \
  --cron "0 9 * * *" \
  --tz "<owner IANA timezone>" \
  --session main \
  --message "Prepare and send the daily digest per INTERACTION_CONTRACT." \
  --announce \
  --channel telegram \
  --to "<owner chatId>"
```

```bash
openclaw cron add \
  --name "drift-sweep" \
  --cron "0 4 * * 0" \
  --tz "<owner IANA timezone>" \
  --session isolated \
  --message "Run the weekly drift sweep over due cards."
```

```bash
openclaw cron add \
  --name "model-health" \
  --cron "0 9 1 * *" \
  --tz "<owner IANA timezone>" \
  --session main \
  --message "Prepare the monthly model-health line for the owner."
```

Owner mirror line:

```text
I scan sources at night, bring the digest at 09:00, and stay quiet after 22:00
unless you write first.
```

## Immediate profile

Use this only when the owner explicitly accepts more interruptions.

- silent source scans every 2-4 hours during the working window;
- one evening digest before the quiet window;
- high-risk items still require human review before they affect the accepted
  model;
- no outbound messages during 22:00-09:00 except the owner answering first.

Example:

```bash
openclaw cron add \
  --name "workday-source-scan" \
  --cron "0 */3 * * 1-5" \
  --tz "<owner IANA timezone>" \
  --session isolated \
  --message "Scan connected sources during the workday; do not announce."
```

## Weekly profile

Use this when the owner wants fewer touches.

- silent scans still run daily so evidence does not go stale;
- the long digest is Monday 10:00 local time;
- first-week setup may still need one explicit owner session of 45-60 minutes.

Example:

```bash
openclaw cron add \
  --name "weekly-digest" \
  --cron "0 10 * * 1" \
  --tz "<owner IANA timezone>" \
  --session main \
  --message "Prepare and send the weekly ontology digest per INTERACTION_CONTRACT." \
  --announce \
  --channel telegram \
  --to "<owner chatId>"
```

## Quiet-window rules

Do not schedule outbound digest or clarification jobs during 22:00-09:00 local
time. Silent `--command` scans may run inside the quiet window when they do not
announce or message the owner.

The quiet window is one-way. If the owner writes during the quiet window, answer
normally.

## Changing rhythm

When the owner says "let's do weekly", "come every morning", or equivalent:

1. Confirm the new rhythm in one plain sentence.
2. Update workspace `INTERACTION_CONTRACT.md`.
3. Replace the affected OpenClaw cron jobs.
4. Reply with the mirror line from the contract.

This is not a model change and does not use `propose-change`.

## Scheduled-run re-anchor

Every scheduled run begins with the Position recovery pass from
`skills/business-ontology/SKILL.md`: read `SOUL.md`, hard rules, and the last
three written records before touching source material.

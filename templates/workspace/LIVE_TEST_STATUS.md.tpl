# Live test status

Agent: {{AGENT_NAME}}.
Module: {{MODULE_NAME}}.
Accepted model repository: {{ONTOLOGY_REPO_URL}}.

Allowed statuses: `pending`, `complete`, `requested-not-configured`,
`setup-only`, `source-connected`, `scheduled`, `live-proven`, `active`,
`disabled`, `failed`.

| Milestone | Status | Evidence |
|---|---|---|
| T0 Telegram prompt received | pending | unknown |
| T1 Repository bootstrap read | pending | unknown |
| T2 Private agent workspace created | complete | this file exists |
| T3 GitHub model repository access requested | pending | unknown |
| T4 Telegram daily scan time requested | pending | unknown |
| T5 Fireflies enablement requested | pending | unknown |
| T6 gog Google Workspace enablement requested | pending | unknown |
| T7 Source cursors initialized | pending | `SOURCE_CURSORS.md` |
| T8 Ready for the first ontology session | pending | unknown |
| T9 First connected-source run proved | pending | source events, model-change packages, and digest/review handoff |

Update this file during the live test. Do not record secrets, raw source
payloads, private message bodies, or credential values.

If GitHub authorization is not available, mark T3 as
`requested-not-configured`. If Telegram capture, scheduling, cursor storage, or
source-event output is missing, mark T7 as `setup-only`. Mark T9
`live-proven` only after a connected source produces source events,
model-change packages, and a digest or review handoff.

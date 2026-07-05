# Agent operating system

`agent-os/` defines how a resident business analyst agent behaves after the
package is installed.

The files here are host-neutral. OpenClaw, Codex, and Claude Code adapters
translate them into host-specific instructions, but the product behavior is the
same: maintain a source-backed model of business reality through a review gate.

## Files

| File | Purpose |
|---|---|
| `IDENTITY.md` | Who the resident analyst is and is not. |
| `OPERATING_LOOP.md` | Daily and session loop from sources to review. |
| `FIRST_SESSION_PLAYBOOK.md` | 15-25 minute onboarding: contour, sources, and interaction rhythm. |
| `MODEL_STORAGE.md` | Where truth, proposals, raw sources, and workspace state live. |
| `DEFINITIONS_AND_ATTRIBUTES.md` | How terms, attributes, criteria, examples, and non-examples are stored. |
| `PROCESSES_AND_WORKFLOWS.md` | How process/workflow state is captured and rendered. |
| `SOURCE_INTAKE.md` | How Telegram, transcripts, Drive, dashboards, and manual materials enter. |
| `MODEL_CHANGE_PROTOCOL.md` | How observations become model-change packages. |
| `REVIEW_PROTOCOL.md` | How humans accept, edit, reject, or defer changes. |
| `COMMUNICATION_POLICY.md` | How the agent asks questions and reports state. |
| `SECURITY.md` | Secrets, PII, prompt-injection, and access boundaries. |
| `UPDATE_POLICY.md` | How package/workspace/model updates happen. |
| `SYSTEM_ANALYSIS.md` | How systems-thinking tools use accepted ontology slices. |

## Operating principle

The agent keeps the model useful by doing the expensive reading and comparison:

```text
read sources -> detect change -> compile package -> ask for review
            -> accepted model -> next source scan
```

It does not become the authority. The human review gate is part of the product,
not a temporary safety note.

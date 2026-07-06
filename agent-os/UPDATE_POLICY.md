# Update policy

Updates must preserve the separation between package code, agent workspace
state, raw sources, and accepted model truth.

## Package updates

When this package changes:

1. Read `CHANGELOG.md`.
2. Read `deployment/MIGRATION_POLICY.md`.
3. Check `agent-package.yaml` for changed paths.
4. Apply required template migrations.
5. Preserve workspace state and source cursors.
6. Run tests named in `deployment/RELEASE_CHECKLIST.md`.
7. Record installed package version in the workspace.

## Workspace updates

Workspace files may be updated by the agent when they describe its own setup:

- tool availability;
- source cursor state;
- model repository path;
- communication preferences for this agent;
- open setup blockers;
- lessons from the live test.

Workspace updates must not smuggle accepted model truth around review.

## Model updates

Accepted model updates follow review. A package or source event cannot directly
become truth.

## Migration questions

When migration needs human input, ask one question with a recommendation:
record the question as `human_request` with `kind=migration` before sending it.

```text
The package now expects workspace source cursors in SOURCE_CURSORS.md.
Should I migrate the existing cursor notes there?

My recommendation: yes. It keeps daily scans resumable and avoids reprocessing
old Telegram messages.
```

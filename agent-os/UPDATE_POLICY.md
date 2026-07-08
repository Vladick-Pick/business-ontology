# Update policy

Updates must preserve the separation between package code, agent workspace
state, raw sources, and accepted model truth.

## Package updates

When this package changes:

1. Read `CHANGELOG.md`.
2. Read `deployment/MIGRATION_POLICY.md`.
3. Check `agent-package.yaml` for changed paths.
4. Apply the release through `package/current/scripts/apply_package_update.py`.
5. Preserve workspace state and source cursors.
6. Validate a temporary copy of the accepted model when a model repository is
   connected.
7. Run the package self-test from the new release before flipping
   `package/current`.
8. Write `workspace/PACKAGE_INSTALL_REPORT.json`.
9. Run `package/current/scripts/verify_installed_package.py --install-root
   <agent-install>`.
10. Run Position recovery before normal ontology work resumes.

Do not report a package as verified after a manual clone, copied folder, or
symlink edit. Manual recovery may be necessary during an incident, but it is
`manual-or-unproven-install` until the proof verifier returns `ok`.

## Workspace updates

Workspace files may be updated by the agent when they describe its own setup:

- tool availability;
- source cursor state;
- model repository path;
- communication preferences for this agent;
- open setup blockers;
- lessons from the live test.
- installed package proof reports.

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

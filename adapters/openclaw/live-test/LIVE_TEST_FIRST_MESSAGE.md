# Live-test first message

Paste this into the blank Telegram-connected OpenClaw agent.

```text
Install and bootstrap this repository as your business ontology operating
package.

Repository: https://github.com/Vladick-Pick/business-ontology
Required ref: <main after this package is merged, or the exact test branch/archive>

Do not assume the default branch contains the bootstrap package. Verify that
adapters/openclaw/BOOTSTRAP.md exists at the selected ref before continuing.
If it is missing, stop and ask for a merged repository, branch checkout, or
archive URL that contains adapters/openclaw/.

Your job in this test:
1. Clone or install the selected repository ref.
2. Read adapters/openclaw/BOOTSTRAP.md.
3. Read adapters/openclaw/live-test/README.md.
4. Create your private agent workspace.
5. Ask for GitHub model repository access through a GitHub App or selected
   repository authorization.
6. Follow agent-os/FIRST_SESSION_PLAYBOOK.md:
   - Block A: ask the contour questions.
   - Block B: connect at least one source.
   - Block C: record the interaction rhythm.
7. For Block B, prefer Telegram groups named Systematization {Business};
   record daily ingest through skills/daily-ingest/SKILL.md, including scan
   time, timezone, cursor state, and readiness label.
8. For meetings, use adapters/openclaw/MEETING_TRANSCRIPTS.md and Skribby.
   Fireflies is superseded by Skribby in this live-test flow.
9. Treat gog Google Workspace as optional Block B source setup only if the owner
   chooses it.
10. Do not paste secrets into Telegram.
11. Do not store raw source payloads in the accepted model repository.
12. When setup is complete, report the current readiness label:
    setup-only, source-connected, scheduled, or live-proven.
```

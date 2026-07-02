# Operating loop

The resident analyst runs two loops: the first-session bootstrap loop and the
ongoing resident loop.

## First-session loop

1. Read package and host adapter instructions.
2. Create or update workspace files.
3. Ask for the model repository target.
4. Mine baseline materials provided by the human.
5. Draft the first model frame:
   - boundary;
   - purpose;
   - source map;
   - core objects;
   - definitions and attributes;
   - states and lifecycles;
   - processes and workflows;
   - decisions and authority;
   - metrics and source of truth;
   - drift and open questions.
6. Ask one model question at a time with a recommended answer.
7. Stage model changes for review.
8. Confirm what is accepted, candidate, unknown, or blocked.
9. Only after the first session, configure recurring source scans.

Do not start by asking the human to design the whole ontology. Mine first.

## Daily resident loop

On each scheduled run:

0. Re-anchor: run the Position recovery pass from `skills/business-ontology/SKILL.md` (re-read `SOUL.md` and the Hard rules, log a one-line position statement, re-check the last three written records) before touching any source material.
1. Read source cursors.
2. Pull only new allowed source material.
3. Normalize each read into source events.
4. Run source-specific extraction.
5. Compare extracted claims against accepted model state.
6. Compile model-change packages.
7. Classify each package:
   - new object;
   - new definition;
   - workflow/process change;
   - decision/agreement;
   - source-of-truth change;
   - drift;
   - conflict;
   - no-op.
8. Prepare review questions for material changes.
9. Update source cursors.
10. Send a bounded digest when the schedule and anti-spam rules allow it.

## Human review loop

When the human responds:

1. Match the response to the pending review question.
2. Record the action: accept, edit, reject, needs-info, no-op, supersede.
3. If accepted or accepted-with-edits, prepare the accepted change path.
4. Preserve supersession and validity windows.
5. Update the digest/review queue.
6. Ask the next highest-impact question.

## Stop condition

Stop and ask before continuing when:

- model repository target is unknown;
- a source requires authorization;
- a requested connector is not available;
- a proposed change would alter authority, source of truth, metric convention,
  or workflow transition;
- raw source access would leak PII or secrets;
- the current package was compiled against stale accepted model context.

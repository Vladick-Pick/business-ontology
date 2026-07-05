# Extraction Golden Benchmark

This directory contains golden cases for the agentic extraction step. The
benchmark does not call a model and does not interpret source meaning. It only
validates model-change packages that an extraction agent already produced.

## Case Layout

Each case directory contains:

- `source-event.json`: one normalized source event, validated by
  `scripts/run_evals.py`.
- `accepted-context/context.json`: the minimal accepted context the agent may
  use while extracting.
- `expected-changes.json`: expected changes matched by `kind + affectedIds`,
  with optional `proposedAction`.

Current cases:

- `state-drift`
- `conflict-supersession`
- `new-object-crm-state`
- `dashboard-metric-concern`
- `no-op-duplicate-source`
- `handoff-underspecified`

## Agent Run Contract

Run the extraction agent once per case with `scripts/run_extraction_agent_proof.py`.
The proof runner invokes the agent command; the scorer remains deterministic and
never calls a model.

```bash
python3 scripts/run_extraction_agent_proof.py \
  --golden evals/golden \
  --packages packages-out \
  --agent codex \
  --cli "codex exec" \
  --model gpt-5 \
  --prompt-hash sha256:<64 hex chars> \
  --agent-command <agent-wrapper-command>
```

The agent command receives these environment variables:

- `BO_CASE_ID`;
- `BO_SOURCE_EVENT`;
- `BO_ACCEPTED_CONTEXT`;
- `BO_OUTPUT_DIR`;
- `BO_EXTRACTION_SKILL`.

If running a proof manually instead of through the proof runner, run the
extraction agent once per case with:

- `skills/extract-from-input/SKILL.md`
- the case `source-event.json`
- the case `accepted-context/context.json`

Write one model-change package under:

```text
packages-out/<case-id>/mcpkg-*.json
```

Then write `packages-out/run_manifest.json`:

```json
{
  "agent": "agent-name",
  "cli": "runner-name-and-version",
  "model": "model-name",
  "model_version": "optional-version",
  "prompt_hash": "sha256:<64 hex chars>",
  "started_at": "2026-07-05T10:00:00Z",
  "finished_at": "2026-07-05T10:01:00Z",
  "cases": [
    {
      "case_id": "state-drift",
      "source_event_hash": "sha256:<actual source-event.json hash>",
      "package_path": "state-drift/mcpkg-*.json"
    }
  ]
}
```

Example commands are intentionally illustrative. The scorer must not depend on
one CLI:

```bash
codex exec --skill skills/extract-from-input/SKILL.md \
  --input evals/golden/state-drift/source-event.json \
  --context evals/golden/state-drift/accepted-context/context.json \
  --output packages-out/state-drift/

claude -p "$(cat skills/extract-from-input/SKILL.md)" \
  < evals/golden/state-drift/source-event.json \
  > packages-out/state-drift/mcpkg-agent.json
```

After packages and the manifest exist, score the run:

```bash
python3 scripts/run_extraction_benchmark.py \
  --golden evals/golden \
  --packages packages-out \
  --min-f1 0.8
```

The scorer writes `packages-out/scorecard.json` and exits non-zero when total F1
falls below the threshold or when package safety checks fail.

## Reference Stub Baseline

`runtime/model_compiler.py` is a deterministic contract harness, not the
production extraction agent. Its baseline proves the benchmark catches weak
extraction:

```text
reference-stub baseline: F1=0.500 (3 TP, 3 FP, 3 FN), exit 1 at --min-f1 0.8
```

Observed failure mode: the stub emits `prepare-staged-proposal` with
`affectedIds: ["unknown"]` for three underspecified handoff-like cases. A real
agent must degrade those cases to `needs-info` or route them to drift/conflict
review with resolved affected ids.

# Model access

Accepted model repository: {{ONTOLOGY_REPO_URL}}.

Only the accepted model belongs in this repository.

Repository requirements:

- It is owned by the human or the company.
- The human can read it directly.
- The agent can prepare staged branches or pull requests after authorization.
- Direct accepted-branch mutation by the agent is refused by scope or branch
  protection.
- Raw sources and private agent state are stored elsewhere.

Model access modes:

| Mode | Holder | Meaning |
|---|---|---|
| `read-model` | agent | read accepted model context |
| `write-staged` | agent | write staged proposals and review artifacts |
| `open-review` | agent | open review/PR handoff |
| `write-accepted` | deterministic promotion controller | apply only one exact authenticated human-approved package |

The generated agent `model-access-policy.json` must not include
`write-accepted`. The generative agent never receives it. A host promotion
controller may hold a separate narrow capability for the canonical store; it
cannot author payloads and fails closed unless the package, decision, actor,
channel, scope, and revision all match.
Before claiming model write readiness, run:

```bash
python3 scripts/assert_model_write_scope.py \
  --access-config <workspace>/model-access-policy.json \
  --model-root <workspace>/.operator/model-scope-proof \
  --json
```

Accepted access paths:

1. Existing repository with selected-repository GitHub authorization.
2. Human-created repository with selected-repository GitHub authorization.
3. Agent-created repository after explicit human approval.
4. Setup-only dry run where write access is recorded as not configured.

If the repository is still `ask-human`, pause model initialization and ask the
human to provide an existing repository, create an empty repository, or authorize
repository creation under their account or organization.

If the access path is setup-only, do not claim branch or pull request write
readiness.

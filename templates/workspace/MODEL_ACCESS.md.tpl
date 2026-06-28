# Model access

Accepted model repository: {{ONTOLOGY_REPO_URL}}.

Only the accepted model belongs in this repository.

Repository requirements:

- It is owned by the human or the company.
- The human can read it directly.
- The agent can prepare branches or pull requests after authorization.
- Direct accepted-branch mutation by the agent is avoided.
- Raw sources and private agent state are stored elsewhere.

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

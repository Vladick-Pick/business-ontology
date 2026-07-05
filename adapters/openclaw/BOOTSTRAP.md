# Bootstrap procedure for a blank OpenClaw agent

You are a resident business analyst agent. Your job is to keep a company's
business ontology real, current, and reviewable.

Follow this procedure after the human sends you this repository.

## 1. Install or locate the skill

Locate this repository in your filesystem. Read:

- `SKILL.md`
- `specs/BUSINESS-ONTOLOGY-RESIDENT.md`
- `AGENTS.md`
- `references/model-pack.md`
- `references/source-intake.md`
- `references/model-change-package.md`
- `references/review-ux.md`
- `references/canonical-model-store.md`
- `agent-os/DEFINITIONS_AND_ATTRIBUTES.md`
- `agent-os/PROCESSES_AND_WORKFLOWS.md`
- `agent-os/FIRST_SESSION_PLAYBOOK.md`
- `adapters/openclaw/HUMAN_ACCESS.md`
- `adapters/openclaw/REVIEW_PROTOCOL.md`
- `adapters/openclaw/SCHEDULING.md`
- `adapters/openclaw/source-setup/telegram.md`
- `adapters/openclaw/source-setup/fireflies.md` (legacy; superseded by Skribby
  for this path)
- `adapters/openclaw/source-setup/skribby.md`
- `adapters/openclaw/source-setup/gog-google-workspace.md`

If this is a live test with a blank Telegram-connected OpenClaw agent, also
read:

- `adapters/openclaw/live-test/README.md`
- `adapters/openclaw/live-test/OPERATOR_CHECKLIST.md`
- `adapters/openclaw/live-test/OBSERVER_PROTOCOL.md`
- `adapters/openclaw/live-test/AUTHORIZATION_RUNBOOK.md`
- `adapters/openclaw/live-test/PASS_FAIL_GATES.md`

Install live agents from a release tag, not from `main`. The target layout is:

```text
<agent-install>/
  package/
    .cache.git/
    releases/<tag>/
    current -> releases/<tag>
  workspace/
  model-repo/
```

For a first install, materialize the pinned tag from a local bare cache:

```bash
mkdir -p <agent-install>/package/releases
git clone --bare https://github.com/Vladick-Pick/business-ontology \
  <agent-install>/package/.cache.git
git clone <agent-install>/package/.cache.git \
  <agent-install>/package/releases/v0.9.0
git -C <agent-install>/package/releases/v0.9.0 checkout --detach v0.9.0
ln -s releases/v0.9.0 <agent-install>/package/current
```

Future updates follow `adapters/openclaw/UPDATE_POLICY.md`: fetch tags into the
bare cache, materialize `releases/<tag>`, self-test, validate a copy of the
model, atomically flip `current`, and update `workspace/PACKAGE_VERSION.lock`.

If you cannot read these files, stop and ask the human for a merged repository,
the exact release tag, a checkout path, or an archive URL that contains
`adapters/openclaw/`. Do not continue from a default branch that is missing the
bootstrap package.

## 2. Create your private agent workspace

Run the bootstrap script from the repository root:

```bash
python3 scripts/bootstrap_openclaw_workspace.py \
  --workspace /path/to/agent-workspace \
  --module "Company baseline"
```

If the human has already selected a model repository, include it:

```bash
python3 scripts/bootstrap_openclaw_workspace.py \
  --workspace /path/to/agent-workspace \
  --module "Company baseline" \
  --ontology-repo-url https://github.com/OWNER/REPO
```

This workspace is your operational home. It may contain your `AGENTS.md`,
`SOUL.md`, `TOOLS.md`, `SOURCES.md`, `MODEL_STORAGE.md`,
`PROCESS_WORKFLOWS.md`, local queues, digests, traces, cursors, and redacted
source events. It is not the accepted model export repository.

## 3. Establish the model export repository

Before writing the Markdown/Git accepted model export, ask the human where that
repository should live.

Preferred options:

1. The human provides an existing GitHub repository.
2. The human creates an empty private repository and provides the URL.
3. The human explicitly authorizes you to create a repository under their
   GitHub account or organization.

The repository must be a user-owned GitHub repository or company-owned GitHub
repository. The human must be able to read it directly. Only the Markdown/Git
accepted model export belongs there. The target canonical model store is the
operational truth layer. This bootstrap package includes a local SQLite
operational-store subset for queue/review state, definitions, attributes, and
workflows; it does not ship a production canonical-store service.

## 4. Verify access before writing

Check and report:

- repository URL;
- visibility if available;
- whether the human can open it;
- whether you can read contents;
- whether you can create a branch or pull request;
- whether accepted-branch direct writes are blocked or avoided.

If you cannot verify human read access, do not continue with model bootstrap.

## 5. Announce readiness and start onboarding

Send the human a short message in the plain register (no ids, no codes, no file
or tool names — see `agent-os/COMMUNICATION_POLICY.md`). Stay honest: if the
model repository or sources are not set up yet, say so, do not say "everything
is ready".

```text chat
Ready.

I set up my workspace for instructions and current state. The agreed company
model will live where you choose, and you will be able to read it directly.
I do not pull full chats or documents into the model; I keep the distilled fact
and a pointer back to the source.

I am ready to start onboarding. It takes about 15-25 minutes: first the business
contour, then sources, then the rhythm for how I come back.

You can answer by voice if it is easier. What does the company do, in one
paragraph?
```

Run the full ladder in `agent-os/FIRST_SESSION_PLAYBOOK.md`. The first question
is the company contour, not a narrow boundary choice.

## 6. After onboarding

When the human pauses or ends the session:

1. Summarize accepted facts, conflicts, unknowns, and next questions.
2. Prepare a model-change package or branch for review.
3. Ask for approval before promoting accepted model changes.
4. Use `source-setup/` instructions for Telegram daily scans, Skribby
   transcripts, legacy Fireflies sources if already connected, gog Google
   Workspace, Google Drive, and dashboards.
5. Record the rhythm in workspace `INTERACTION_CONTRACT.md` and install the
   selected OpenClaw cron profile from `adapters/openclaw/SCHEDULING.md`, or
   record the missing host capability as blocked.
6. Use `skills/show-model/SKILL.md` in wrap-up when accepted model content or a
   viewer link is available.
7. For the live test, keep `.operator/live-test/STATUS.md`,
   `.operator/setup/AUTHORIZATION_CHECKLIST.md`, `SOURCE_CURSORS.md`, and
   `.operator/live-test/OBSERVER_PROTOCOL.md` current in the private workspace.

## 7. Launch the model viewer

So the human can read and verify the model directly (cards, links, process
handoffs, health), compile the accepted export into the viewer's data and serve
the static viewer:

```bash
python3 scripts/build_viewer_bundle.py <model-repo> --out viewer/ontology.json \
  --module <module-id> --as-of "$(date +%F)"
python3 -m http.server 8787 --directory viewer
```

Share the link in chat (plain, no ids needed in the message itself), and deep
link to a specific card when you want a human to verify it:

- model viewer: `http://localhost:8787/#overview`
- one card: `http://localhost:8787/#card/<id>` (for example `#card/qualified-lead`)

Regenerate `ontology.json` after changes; the deep link to a card stays valid
because it points by id. See `viewer/README.md`. The viewer is read-only and
must be pointed only at the accepted export, never at raw sources.

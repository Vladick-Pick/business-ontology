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
- `adapters/openclaw/MEETING_RECORDING_SERVICE.md`
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

If Telegram daily scanning is in scope, install the optional MTProto
dependency in the agent runtime:

```bash
python3 -m pip install -r requirements-telegram.txt
python3 -c "import telethon"
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

The generated workspace also contains one `business-ontology-resident` bridge
skill. OpenClaw loads that small workspace skill on relevant turns; the bridge
then reads policy and duty skills through the agent's versioned
`package/current`. Do not copy every package skill into mutable workspace state.

Activate the managed behavior and release-specific host boundary for this agent
after its OpenClaw agent id exists. New installs and upgrades use the same
reversible commands:

```bash
python3 package/current/scripts/migrate_workspace_v0_11_0.py \
  --workspace /path/to/agent-workspace \
  --agent-id <openclaw-agent-id> \
  --dry-run
python3 package/current/scripts/migrate_workspace_v0_11_0.py \
  --workspace /path/to/agent-workspace \
  --agent-id <openclaw-agent-id> \
  --apply-openclaw \
  --openclaw-bin <verified-openclaw-launcher> \
  --openclaw-node-bin-dir <verified-node-bin-dir>

python3 package/current/scripts/migrate_workspace_v0_11_12.py \
  --workspace /path/to/agent-workspace \
  --agent-id <openclaw-agent-id> \
  --dry-run
python3 package/current/scripts/migrate_workspace_v0_11_12.py \
  --workspace /path/to/agent-workspace \
  --agent-id <openclaw-agent-id> \
  --apply-openclaw \
  --openclaw-bin <verified-openclaw-launcher> \
  --openclaw-node-bin-dir <verified-node-bin-dir>

python3 package/current/scripts/migrate_workspace_v0_11_15.py \
  --workspace /path/to/agent-workspace \
  --agent-id <openclaw-agent-id> \
  --dry-run
python3 package/current/scripts/migrate_workspace_v0_11_15.py \
  --workspace /path/to/agent-workspace \
  --agent-id <openclaw-agent-id>
```

The first migration renders the current package-owned policies and installs the
scoped owner-chat guard. The second preserves existing per-agent tool policy,
adds the Resident Sites deny, and initializes `viewer_publication` to
`workspace-only` only when absent. The third initializes the Git-ignored private
review authority policy. A fresh install is not complete until all three
activations and a Gateway re-anchor have been verified.

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
- whether accepted-branch direct writes are blocked by scope or branch
  protection.

Then run the local write-scope proof against a disposable model root:

```bash
python3 scripts/assert_model_write_scope.py \
  --access-config /path/to/agent-workspace/model-access-policy.json \
  --model-root /path/to/agent-workspace/.operator/model-scope-proof \
  --json
```

Passing means staged write works and accepted write is refused. Failing because
accepted write succeeds is a product safety blocker. Failing because staged
write is denied is a setup blocker.

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

So the human can read and verify accepted truth plus a clearly separated
working layer, publish the official viewer into one stable workspace folder:

```bash
python3 package/current/scripts/publish_viewer.py <model-repo> \
  --workspace <workspace> \
  --out-dir <workspace>/viewer \
  --module <module-id> \
  --as-of "$(date +%F)"
```

Do not present a handcrafted HTML page as the current model viewer. The viewer
is current only when `<workspace>/viewer/VIEWER_PUBLISH_REPORT.json` exists with
`status: "published"`.

Then configure exactly one declared publication target. `workspace-only` is the
safe default. On a host with Tailscale Funnel, the agent can configure its own
non-colliding stable path without creating a domain or a website project:

```bash
python3 package/current/scripts/configure_viewer_publication.py \
  --workspace <workspace> \
  --mode tailscale-funnel \
  --path /models/<agent-id>/ \
  --apply
python3 package/current/scripts/publish_viewer.py <model-repo> \
  --workspace <workspace> \
  --out-dir <workspace>/viewer \
  --module <module-id> \
  --as-of "$(date +%F)"
```

The second publish verifies the public files and records
`publication.status: "verified"`. Only then may the URL be shared. A manual
`python3 -m http.server` is acceptable for operator proof, not as a claimed
stable public capability. Do not create an OpenAI Site, a hosting project, a new
repository, provider account, or domain. If no publication capability exists,
keep `workspace-only` and use the bounded chat fallback.

The agent refreshes the same files after accepted model changes, accepted
review promotion, pending package changes, package updates that change the
viewer, source-readiness changes, open human request changes, or an explicit
"show model" request.

Share the link in chat (plain, no ids needed in the message itself), and deep
link to a specific card when you want a human to verify it:

- model viewer: `<verified-public-url>#overview`
- pending changes: `<verified-public-url>#working`
- one card: `<verified-public-url>#card/<id>`

Run `publish_viewer.py` after accepted model changes; the deep link to a card
stays valid because it points by id. See `viewer/README.md`. The viewer is
read-only and must be pointed only at the accepted export, never at raw sources.

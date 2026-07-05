import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_DIR = REPO_ROOT / "adapters" / "openclaw"
LIVE_TEST_DIR = BOOTSTRAP_DIR / "live-test"
CLI_PATH = REPO_ROOT / "scripts" / "bootstrap_openclaw_workspace.py"


def read(path):
    return path.read_text(encoding="utf-8")


class OpenClawLiveTestReadinessTests(unittest.TestCase):
    def test_live_test_operator_packet_exists_and_names_expected_milestones(self):
        required = {
            "README.md",
            "OPERATOR_CHECKLIST.md",
            "OBSERVER_PROTOCOL.md",
            "AUTHORIZATION_RUNBOOK.md",
            "LIVE_TEST_FIRST_MESSAGE.md",
            "PASS_FAIL_GATES.md",
        }
        for relative_path in required:
            self.assertTrue((LIVE_TEST_DIR / relative_path).exists(), relative_path)

        readme = read(LIVE_TEST_DIR / "README.md")
        first_message = read(LIVE_TEST_DIR / "LIVE_TEST_FIRST_MESSAGE.md")
        gates = read(LIVE_TEST_DIR / "PASS_FAIL_GATES.md")
        runbook = read(LIVE_TEST_DIR / "AUTHORIZATION_RUNBOOK.md")
        operator = read(LIVE_TEST_DIR / "OPERATOR_CHECKLIST.md")
        joined = "\n".join([readme, first_message, gates, runbook, operator])

        self.assertIn("blank Telegram-connected OpenClaw agent", readme)
        self.assertRegex(readme, r"create the private agent\s+workspace")
        self.assertIn("Required ref:", first_message)
        self.assertIn("adapters/openclaw/BOOTSTRAP.md exists", first_message)
        self.assertIn("Ready for the first ontology session", first_message)
        self.assertIn("GitHub model repository access", joined)
        self.assertIn("Telegram daily scan time", joined)
        self.assertIn("Fireflies is enabled", joined)
        self.assertIn("gog Google Workspace is enabled", joined)
        self.assertIn("requested-not-configured", joined)
        self.assertIn("setup-only", joined)
        self.assertIn("stop the test", gates.lower())
        self.assertNotIn("Checklist phrase", joined)

    def test_live_experiment_doc_requires_selected_ref_verification(self):
        text = read(REPO_ROOT / "docs" / "openclaw-live-experiment.md")

        self.assertIn("selected ref", text)
        self.assertIn("adapters/openclaw/BOOTSTRAP.md", text)
        self.assertIn("main only after PR #6 is merged", text)
        self.assertNotIn("ready for the live bootstrap experiment on `main`", text)
        self.assertNotIn("9c601375ca365f487842a48af12820f176e6849f", text)

    def test_source_setup_docs_cover_target_live_sources(self):
        expectations = {
            "telegram.md": [
                "daily scan time",
                "timezone",
                "chat_id",
                "topic_id",
                "last_message_id",
                "privacy mode",
                "room_event",
                "manual export backfill",
                "setup-only",
                "Activation gates",
                "source-event writer",
            ],
            "fireflies.md": [
                "meeting URL",
                "invite Fireflies",
                "transcript",
                "project meeting",
                "redacted source event",
                "no raw transcript",
            ],
            "gog-google-workspace.md": [
                "gog",
                "OAuth",
                "Drive folder",
                "Calendar filters",
                "Docs",
                "read-only",
            ],
        }
        for filename, phrases in expectations.items():
            text = read(BOOTSTRAP_DIR / "source-setup" / filename)
            for phrase in phrases:
                self.assertIn(phrase, text, filename)

    def test_bootstrap_cli_generates_live_test_workspace_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "--workspace",
                    str(workspace),
                    "--module",
                    "Acquisition",
                    "--ontology-repo-url",
                    "https://github.com/example/company-ontology",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            for relative_path in [
                ".learnings/LEARNINGS.md",
                ".operator/live-test/STATUS.md",
                ".operator/setup/AUTHORIZATION_CHECKLIST.md",
                ".operator/live-test/OBSERVER_PROTOCOL.md",
                "SOURCE_CURSORS.md",
                "source-setup/fireflies.md",
                "source-setup/gog-google-workspace.md",
                "source-setup/telegram.md",
            ]:
                path = workspace / relative_path
                self.assertTrue(path.exists(), relative_path)
                text = read(path)
                self.assertNotIn("{{", text, relative_path)
                self.assertNotIn("}}", text, relative_path)

            config = json.loads(read(workspace / "runtime-config.example.json"))
            auth = read(workspace / ".operator/setup/AUTHORIZATION_CHECKLIST.md")
            cursors = read(workspace / "SOURCE_CURSORS.md")
            status = read(workspace / ".operator/live-test/STATUS.md")

        self.assertEqual(config["source_cursors_path"], "SOURCE_CURSORS.md")
        self.assertEqual(config["store_path"], "agent-state/operational-store.sqlite")
        self.assertEqual(config["authorization_checklist_path"], ".operator/setup/AUTHORIZATION_CHECKLIST.md")
        self.assertEqual(config["observer_protocol_path"], ".operator/live-test/OBSERVER_PROTOCOL.md")
        self.assertEqual(config["live_test_status_path"], ".operator/live-test/STATUS.md")
        self.assertEqual(config["learnings_path"], ".learnings/LEARNINGS.md")
        self.assertIn("setup-only dry run", auth)
        self.assertIn("requested-not-configured", auth)
        self.assertIn("setup-only", cursors)
        self.assertIn("Allowed statuses", status)
        self.assertFalse((workspace / "LIVE_TEST_STATUS.md").exists())
        self.assertFalse((workspace / "AUTHORIZATION_CHECKLIST.md").exists())
        self.assertFalse((workspace / "OBSERVER_PROTOCOL.md").exists())

    def test_workspace_templates_are_file_backed_not_inline_markdown_blocks(self):
        template_dir = REPO_ROOT / "templates" / "workspace"
        expected_templates = {
            "AGENTS.md.tpl",
            "SOUL.md.tpl",
            "TOOLS.md.tpl",
            "SOURCES.md.tpl",
            "RUNBOOK.md.tpl",
            "HUMAN_README.md.tpl",
            "MODEL_ACCESS.md.tpl",
            "REVIEW_PROTOCOL.md.tpl",
            "TELEGRAM_COMMANDS.md.tpl",
            "INTERACTION_CONTRACT.md.tpl",
            "COMMUNICATION_POLICY.md.tpl",
            "SESSION_STATE.md.tpl",
            "LEARNINGS.md.tpl",
            "LIVE_TEST_STATUS.md.tpl",
            "AUTHORIZATION_CHECKLIST.md.tpl",
            "OBSERVER_PROTOCOL.md.tpl",
            "SOURCE_CURSORS.md.tpl",
        }
        for filename in expected_templates:
            self.assertTrue((template_dir / filename).exists(), filename)

        cli_text = read(CLI_PATH)
        self.assertIn("load_text_template(\"LIVE_TEST_STATUS.md.tpl\")", cli_text)
        self.assertIn("load_text_template(\"SESSION_STATE.md.tpl\")", cli_text)
        self.assertIn("load_text_template(\"INTERACTION_CONTRACT.md.tpl\")", cli_text)
        self.assertNotIn("FIRST_SESSION.md.tpl", cli_text)
        self.assertNotRegex(cli_text, r"_TEMPLATE = \"\"\"#")

    def test_live_test_docs_do_not_invite_broad_or_unsafe_access(self):
        paths = list(LIVE_TEST_DIR.glob("*.md")) + list((BOOTSTRAP_DIR / "source-setup").glob("*.md"))
        joined = "\n".join(read(path) for path in paths)

        forbidden_phrases = [
            "give the agent your password",
            "paste your token into Telegram",
            "auto-merge",
            "merge without review",
            "store raw transcript",
            "store raw Telegram export",
            "write back to source",
        ]
        for phrase in forbidden_phrases:
            self.assertNotIn(phrase, joined)

        required_boundaries = [
            "read-only",
            "redacted source event",
            "human review",
            "GitHub App",
            "branch or pull request",
        ]
        for phrase in required_boundaries:
            self.assertIn(phrase, joined)

        secret_patterns = [
            r"\bsk-[A-Za-z0-9]{16,}",
            r"ghp_[A-Za-z0-9]",
            r"xox[baprs]-",
            r"-----BEGIN ",
        ]
        for pattern in secret_patterns:
            self.assertIsNone(re.search(pattern, joined), pattern)


if __name__ == "__main__":
    unittest.main()

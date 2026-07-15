import json
from pathlib import Path
import shutil
import subprocess
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "adapters" / "openclaw" / "plugins" / "owner-chat-guard"


class OpenClawOwnerChatGuardTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required for the OpenClaw plugin tests")
    def test_guard_behavior(self):
        result = subprocess.run(
            ["node", "--test", "guard.test.js"],
            cwd=PLUGIN_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_plugin_package_targets_openclaw_2026_7_1_contract(self):
        package = json.loads((PLUGIN_ROOT / "package.json").read_text(encoding="utf-8"))
        manifest = json.loads((PLUGIN_ROOT / "openclaw.plugin.json").read_text(encoding="utf-8"))
        entry = (PLUGIN_ROOT / "index.js").read_text(encoding="utf-8")
        guard = (PLUGIN_ROOT / "guard.js").read_text(encoding="utf-8")
        readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertEqual(manifest["id"], "business-ontology-owner-chat-guard")
        self.assertTrue(manifest["activation"]["onStartup"])
        self.assertNotIn("required", manifest["configSchema"])
        self.assertEqual(
            manifest["configSchema"]["properties"]["agentIds"]["default"], []
        )
        self.assertEqual(package["openclaw"]["extensions"], ["./index.js"])
        self.assertEqual(package["openclaw"]["runtimeExtensions"], ["./index.js"])
        self.assertEqual(package["openclaw"]["compat"]["pluginApi"], ">=2026.7.1")
        self.assertEqual(package["openclaw"]["compat"]["minGatewayVersion"], "2026.7.1")
        self.assertIn('api.on("before_prompt_build"', entry)
        self.assertIn('api.on("before_agent_finalize"', entry)
        self.assertIn('api.on("message_sending"', entry)
        self.assertIn("maxAttempts: 1", guard)
        self.assertIn('"allowConversationAccess": true', readme)
        self.assertIn('"allowPromptInjection": true', readme)
        self.assertIn("Merge `business-ontology-owner-chat-guard`", readme)
        self.assertIn("Never replace the current", readme)

    def test_policy_surfaces_require_one_delivered_question_and_keep_artifacts(self):
        paths = [
            REPO_ROOT / "agent-os" / "COMMUNICATION_POLICY.md",
            REPO_ROOT / "agent-os" / "REVIEW_PROTOCOL.md",
            REPO_ROOT / "skills" / "meeting-transcript-ingest" / "SKILL.md",
            REPO_ROOT / "templates" / "workspace" / "COMMUNICATION_POLICY.md.tpl",
            REPO_ROOT / "templates" / "workspace" / "REVIEW_PROTOCOL.md.tpl",
            REPO_ROOT / "templates" / "workspace" / "SOUL.md.tpl",
            REPO_ROOT / "templates" / "workspace" / "TOOLS.md.tpl",
        ]

        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        self.assertNotIn("one to three", combined.lower())
        self.assertIn("deliver only one question per owner", combined)
        self.assertIn("exact outbound `messageRef`", combined)
        self.assertIn("explicit current-turn request", combined)
        self.assertIn("Do not translate, paraphrase, summarize, rename fields", combined)
        self.assertIn("Tool results are private", combined)
        self.assertIn("A successful file-read result", combined)
        self.assertIn("copy-ready operator command", combined)
        self.assertIn("Recommendation:", combined)
        self.assertIn("Consequence:", combined)
        self.assertIn("scripts/resolve_owner_reply.py", combined)
        self.assertIn("everything is fine", combined.lower())


if __name__ == "__main__":
    unittest.main()

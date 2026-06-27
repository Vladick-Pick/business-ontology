import json
from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class OpenClawWorkspaceTemplateTests(unittest.TestCase):
    def test_deployment_reference_has_required_sections_and_boundaries(self):
        path = REPO_ROOT / "references" / "openclaw-gbrain-deployment.md"
        text = path.read_text(encoding="utf-8")

        required_headings = [
            "# OpenClaw and GBrain deployment",
            "## Prerequisites",
            "## Install the skill",
            "## Configure the model pack",
            "## Configure source events",
            "## Configure GBrain/MCP access",
            "## Run the reference loop",
            "## Review and approve",
            "## Operational cadence",
            "## What is not production-ready here",
        ]
        for heading in required_headings:
            self.assertIn(heading, text)

        self.assertIn("live OAuth", text)
        self.assertIn("production MCP server", text)
        self.assertIn("live connectors", text)
        self.assertIn("human review gate", text)
        self.assertIn("canonical model store", text)
        self.assertIn("Markdown/Git export", text)

    def test_workspace_readme_names_layout_and_first_run_gate(self):
        path = REPO_ROOT / "templates" / "workspace" / "README.md"
        text = path.read_text(encoding="utf-8")

        for line in [
            "workspace/",
            "  ontology/",
            "  model-packs/",
            "  source-events/",
            "  model-change-packages/",
            "  review-packages/",
            "  traces/",
            "  digests/",
        ]:
            self.assertIn(line, text)
        self.assertIn("human reviews accepted-truth changes", text)
        self.assertIn("Markdown/Git export", text)
        self.assertIn("never promotes its own output", text)

    def test_runtime_config_is_json_with_relative_paths_only(self):
        path = REPO_ROOT / "templates" / "workspace" / "runtime-config.example.json.tpl"
        config = json.loads(path.read_text(encoding="utf-8"))

        path_keys = [
            "model_pack_path",
            "source_event_dir",
            "accepted_context_path",
            "package_output_dir",
            "review_package_output_dir",
            "trace_path",
            "digest_path",
            "state_path",
            "store_path",
            "learnings_path",
            "authorization_checklist_path",
            "observer_protocol_path",
            "live_test_status_path",
            "artifact_root",
            "state_root",
        ]
        for key in path_keys:
            value = config.get(key)
            self.assertIsInstance(value, str, key)
            self.assertFalse(Path(value).is_absolute(), key)
            self.assertNotIn("/Users/", value, key)
            self.assertNotIn("://", value, key)

    def test_env_example_contains_variable_names_only(self):
        path = REPO_ROOT / "templates" / "workspace" / "env.example.tpl"
        lines = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        self.assertTrue(lines)
        for line in lines:
            self.assertRegex(line, r"^[A-Z][A-Z0-9_]*=$")
            self.assertEqual(line.split("=", 1)[1], "")

    def test_template_examples_do_not_contain_secret_values_or_user_paths(self):
        paths = [
            REPO_ROOT / "templates" / "workspace" / "runtime-config.example.json.tpl",
            REPO_ROOT / "templates" / "workspace" / "env.example.tpl",
        ]
        forbidden_patterns = [
            r"sk-[A-Za-z0-9]",
            r"ghp_[A-Za-z0-9]",
            r"xox[baprs]-",
            r"-----BEGIN ",
            r"/Users/",
            r"https?://",
        ]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                self.assertIsNone(re.search(pattern, text), f"{path}: {pattern}")

    def test_readme_has_one_conservative_deployment_pointer(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertEqual(readme.count("openclaw-gbrain-deployment.md"), 1)
        self.assertIn("reference/local setup template", readme)
        self.assertIn("not production deployment", readme)


if __name__ == "__main__":
    unittest.main()

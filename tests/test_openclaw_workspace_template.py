import json
import importlib.util
from pathlib import Path
import re
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = REPO_ROOT / "scripts" / "bootstrap_openclaw_workspace.py"


def load_bootstrap():
    spec = importlib.util.spec_from_file_location("bootstrap_openclaw_workspace", BOOTSTRAP)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class OpenClawWorkspaceTemplateTests(unittest.TestCase):
    def test_workspace_tools_declares_viewer_publication_boundary(self):
        text = (REPO_ROOT / "templates" / "workspace" / "TOOLS.md.tpl").read_text(
            encoding="utf-8"
        )

        self.assertIn("OpenAI Sites", text)
        self.assertIn("viewer_publication", text)
        self.assertIn("text fallback", text)

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
            "  raw/",
            "    telegram/",
            "    meetings/",
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
            "raw_source_root",
            "source_event_dir",
            "accepted_context_path",
            "package_output_dir",
            "review_package_output_dir",
            "source_instances_path",
            "live_proof_ledger_path",
            "model_access_policy_path",
            "viewer_output_path",
            "viewer_publish_report_path",
            "trace_path",
            "digest_path",
            "state_path",
            "store_path",
            "learnings_path",
            "authorization_checklist_path",
            "observer_protocol_path",
            "live_test_status_path",
            "interaction_contract_path",
            "artifact_root",
            "state_root",
        ]
        for key in path_keys:
            value = config.get(key)
            self.assertIsInstance(value, str, key)
            self.assertFalse(Path(value).is_absolute(), key)
            self.assertNotIn("/Users/", value, key)
            self.assertNotIn("://", value, key)
        self.assertEqual(config["state_root"], "agent-state")
        self.assertEqual(config["raw_source_root"], "raw")
        self.assertTrue(config["state_path"].startswith("agent-state/"))
        self.assertTrue(config["store_path"].startswith("agent-state/"))
        self.assertEqual(
            config["viewer_publication"],
            {"mode": "workspace-only", "public_url": ""},
        )

    def test_bootstrap_runtime_config_uses_template_as_base(self):
        bootstrap = load_bootstrap()
        path = REPO_ROOT / "templates" / "workspace" / "runtime-config.example.json.tpl"
        template = json.loads(path.read_text(encoding="utf-8"))

        config = bootstrap.runtime_config(
            "sales",
            "https://github.com/example/company-model",
            "2026-07-05T10:00:00Z",
            "ru",
        )

        for key, value in template.items():
            if key not in {
                "module_id",
                "model_pack_path",
                "generated_at",
                "ontology_revision",
                "company_model_language",
                "company_model_language_source",
            }:
                self.assertEqual(config.get(key), value, key)
        self.assertEqual(config["module_id"], "sales")
        self.assertEqual(config["model_pack_path"], "model-packs/sales.model-pack.json")
        self.assertEqual(config["generated_at"], "2026-07-05T10:00:00Z")
        self.assertEqual(config["accepted_model_repository"], "https://github.com/example/company-model")
        self.assertEqual(config["company_model_language"], "ru")
        self.assertEqual(config["company_model_language_source"], "owner-onboarding")

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
            REPO_ROOT / "templates" / "workspace" / "PACKAGE_VERSION.lock.tpl",
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
        self.assertIn("external deployment work", readme)

    def test_onboarding_requires_company_model_language_question(self):
        playbook = (REPO_ROOT / "agent-os" / "FIRST_SESSION_PLAYBOOK.md").read_text(encoding="utf-8")
        skill = (REPO_ROOT / "skills" / "onboard-contour" / "SKILL.md").read_text(encoding="utf-8")

        for text in [playbook, skill]:
            self.assertIn("company model language", text)
            self.assertIn("model text", text)
            self.assertIn("technical ids", text)
            self.assertIn("human_request", text)


if __name__ == "__main__":
    unittest.main()

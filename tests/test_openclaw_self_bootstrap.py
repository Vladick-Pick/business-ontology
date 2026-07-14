import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_DIR = REPO_ROOT / "adapters" / "openclaw"
CLI_PATH = REPO_ROOT / "scripts" / "bootstrap_openclaw_workspace.py"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def package_version() -> str:
    manifest = (REPO_ROOT / "agent-package.yaml").read_text(encoding="utf-8")
    match = re.search(r'^version:\s*"([^"]+)"', manifest, re.MULTILINE)
    if not match:
        raise AssertionError("agent-package.yaml has no version")
    return match.group(1)


class OpenClawSelfBootstrapTests(unittest.TestCase):
    def test_bootstrap_docs_name_three_storage_layers_and_human_access_gate(self):
        required = {
            "README.md",
            "BOOTSTRAP.md",
            "FIRST_MESSAGE.md",
            "HUMAN_ACCESS.md",
            "REVIEW_PROTOCOL.md",
            "TELEGRAM_COMMANDS.md",
            "source-setup/google-drive.md",
            "source-setup/telegram.md",
            "source-setup/transcripts.md",
            "source-setup/dashboard.md",
        }
        for relative_path in required:
            path = BOOTSTRAP_DIR / relative_path
            self.assertTrue(path.exists(), relative_path)

        joined = "\n".join(
            (BOOTSTRAP_DIR / path).read_text(encoding="utf-8")
            for path in ["README.md", "BOOTSTRAP.md", "HUMAN_ACCESS.md", "REVIEW_PROTOCOL.md"]
        )
        for phrase in [
            "accepted model",
            "agent workspace",
            "raw source layer",
            "user-owned GitHub repository",
            "human must be able to read",
            "the agent must not store raw transcripts",
            "the agent must not promote its own proposals",
        ]:
            self.assertIn(phrase, joined)

    def test_cli_creates_target_workspace_with_no_unresolved_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "agent-workspace"
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "--workspace",
                    str(workspace),
                    "--module",
                    "Acquisition Ops",
                    "--agent-name",
                    "Company Reality Analyst",
                    "--ontology-repo-url",
                    "https://github.com/example/company-ontology",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Ready for first ontology session", result.stdout)

            expected_dirs = [
                ".learnings",
                ".operator/live-test",
                ".operator/setup",
                "agent-state",
                "digests",
                "live-proofs",
                "model-change-packages",
                "model-packs",
                "review-packages",
                "source-events",
                "source-setup",
                "traces",
            ]
            for relative_path in expected_dirs:
                self.assertTrue((workspace / relative_path).is_dir(), relative_path)

            expected_files = [
                "AGENTS.md",
                "SOUL.md",
                "COMMUNICATION_POLICY.md",
                "TOOLS.md",
                "SOURCES.md",
                "RUNBOOK.md",
                "HUMAN_README.md",
                "MODEL_ACCESS.md",
                "MODEL_STORAGE.md",
                "PROCESS_WORKFLOWS.md",
                "REVIEW_PROTOCOL.md",
                "TELEGRAM_COMMANDS.md",
                "INTERACTION_CONTRACT.md",
                "PACKAGE_VERSION.lock",
                "SESSION_STATE.md",
                ".learnings/LEARNINGS.md",
                ".operator/live-test/STATUS.md",
                ".operator/setup/AUTHORIZATION_CHECKLIST.md",
                ".operator/live-test/OBSERVER_PROTOCOL.md",
                "runtime-config.example.json",
                "workspace-state.json",
                "source-instances.json",
                "model-access-policy.json",
                "live-proofs/proofs.json",
                "model-packs/acquisition-ops.model-pack.json",
                "agent-state/bootstrap-manifest.json",
            ]
            for relative_path in expected_files:
                path = workspace / relative_path
                self.assertTrue(path.exists(), relative_path)
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("{{", text, relative_path)
                self.assertNotIn("}}", text, relative_path)

            model_access = (workspace / "MODEL_ACCESS.md").read_text(encoding="utf-8")
            self.assertIn("https://github.com/example/company-ontology", model_access)
            self.assertIn("Only the accepted model belongs in this repository", model_access)
            model_storage = (workspace / "MODEL_STORAGE.md").read_text(encoding="utf-8")
            for phrase in [
                "definitions",
                "attributes",
                "criteria",
                "examples",
                "non-examples",
                "human decision",
            ]:
                self.assertIn(phrase, model_storage)
            process_workflows = (workspace / "PROCESS_WORKFLOWS.md").read_text(encoding="utf-8")
            for phrase in [
                "workflows",
                "steps",
                "transitions",
                "participants",
                "exceptions",
                "metrics",
            ]:
                self.assertIn(phrase, process_workflows)
            self.assertFalse((workspace / "FIRST_SESSION.md").exists())
            self.assertFalse((workspace / "LIVE_TEST_STATUS.md").exists())
            self.assertFalse((workspace / "AUTHORIZATION_CHECKLIST.md").exists())
            self.assertFalse((workspace / "OBSERVER_PROTOCOL.md").exists())
            package_lock = load_json(workspace / "PACKAGE_VERSION.lock")
            self.assertEqual(package_lock["current_version"], package_version())
            self.assertEqual(package_lock["tag"], f"v{package_version()}")
            self.assertNotIn("@github.com", package_lock["remote_url"])
            workspace_state = load_json(workspace / "workspace-state.json")
            self.assertEqual(workspace_state["company_model"]["company_model_language"], "pending-owner-selection")
            self.assertEqual(workspace_state["company_model"]["language_source"], "pending-owner-onboarding")
            self.assertEqual(load_json(workspace / "source-instances.json")["source_instances"], [])
            self.assertEqual(load_json(workspace / "live-proofs" / "proofs.json")["live_proofs"], [])
            model_access = load_json(workspace / "model-access-policy.json")
            self.assertEqual(model_access["access_modes"], ["read-model", "write-staged", "open-review"])
            self.assertNotIn("write-accepted", model_access["access_modes"])

    def test_generated_json_uses_relative_paths_and_separates_model_from_agent_state(self):
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
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            config = load_json(workspace / "runtime-config.example.json")
            workspace_state = load_json(workspace / "workspace-state.json")
            manifest = load_json(workspace / "agent-state" / "bootstrap-manifest.json")
            model_pack = load_json(workspace / "model-packs" / "acquisition.model-pack.json")

        path_keys = [
            "model_pack_path",
            "source_event_dir",
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
            "interaction_contract_path",
            "source_instances_path",
            "live_proof_ledger_path",
            "model_access_policy_path",
            "artifact_root",
            "state_root",
        ]
        for key in path_keys:
            value = config[key]
            self.assertIsInstance(value, str, key)
            self.assertFalse(Path(value).is_absolute(), key)
            self.assertNotIn("/Users/", value, key)

        self.assertEqual(config["accepted_model_repository"], "ask-human")
        self.assertEqual(config["company_model_language"], "pending-owner-selection")
        self.assertEqual(config["company_model_language_source"], "pending-owner-onboarding")
        self.assertEqual(config["raw_source_policy"], "private-configured-raw-root-only")
        self.assertEqual(config["raw_source_root"], "raw")
        self.assertTrue(config["human_review_required"])
        self.assertEqual(workspace_state["agent_identity"]["package_name"], "business-ontology")
        self.assertEqual(workspace_state["company_model"]["model_repo"], "ask-human")
        self.assertEqual(workspace_state["company_model"]["company_model_language"], "pending-owner-selection")
        self.assertEqual(manifest["storageLayers"]["acceptedModel"]["location"], "user-owned GitHub repository")
        self.assertEqual(manifest["companyModelLanguage"], "pending-owner-selection")
        self.assertEqual(manifest["storageLayers"]["agentWorkspace"]["location"], "this workspace")
        self.assertEqual(
            manifest["storageLayers"]["rawSourceLayer"]["location"],
            "configured private workspace raw root",
        )
        self.assertEqual(model_pack["moduleId"], "acquisition")
        self.assertEqual(model_pack["modelPackId"], "mp-acquisition")
        self.assertEqual(model_pack["companyModelLanguage"], "pending-owner-selection")

    def test_company_model_language_argument_is_written_to_all_workspace_state(self):
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
                    "--company-model-language",
                    "ru",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            config = load_json(workspace / "runtime-config.example.json")
            workspace_state = load_json(workspace / "workspace-state.json")
            manifest = load_json(workspace / "agent-state" / "bootstrap-manifest.json")
            model_pack = load_json(workspace / "model-packs" / "acquisition.model-pack.json")

        self.assertEqual(config["company_model_language"], "ru")
        self.assertEqual(config["company_model_language_source"], "owner-onboarding")
        self.assertEqual(workspace_state["company_model"]["company_model_language"], "ru")
        self.assertEqual(workspace_state["company_model"]["language_source"], "owner-onboarding")
        self.assertEqual(workspace_state["company_model"]["language_decided_at"], config["generated_at"])
        self.assertEqual(manifest["companyModelLanguage"], "ru")
        self.assertEqual(model_pack["companyModelLanguage"], "ru")

    def test_generated_model_pack_source_kinds_match_source_event_schema(self):
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
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            model_pack = load_json(workspace / "model-packs" / "acquisition.model-pack.json")
            source_event_schema = load_json(REPO_ROOT / "schemas" / "source-event.schema.json")

        allowed_source_kinds = set(source_event_schema["properties"]["sourceKind"]["enum"])
        generated_source_kinds = {
            rule["sourceKind"] for rule in model_pack["sourceAuthority"]
        }
        self.assertTrue(generated_source_kinds <= allowed_source_kinds)

    def test_generated_model_pack_card_types_match_model_pack_schema(self):
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
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            model_pack = load_json(workspace / "model-packs" / "acquisition.model-pack.json")
            model_pack_schema = load_json(REPO_ROOT / "schemas" / "model-pack.schema.json")

        allowed_card_types = set(
            model_pack_schema["properties"]["objectTypes"]["items"]["properties"]["cardTypes"]["items"]["enum"]
        )
        generated_card_types = {
            card_type
            for object_type in model_pack["objectTypes"]
            for card_type in object_type["cardTypes"]
        }
        self.assertTrue(generated_card_types <= allowed_card_types)

    def test_cli_refuses_to_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            first = subprocess.run(
                [sys.executable, str(CLI_PATH), "--workspace", str(workspace), "--module", "Sales"],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            second = subprocess.run(
                [sys.executable, str(CLI_PATH), "--workspace", str(workspace), "--module", "Sales"],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertNotEqual(second.returncode, 0, second.stdout)
        self.assertIn("already exists", second.stderr)
        self.assertIn("--force", second.stderr)

    def test_cli_refuses_partial_overwrite_before_creating_other_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            (workspace / "MODEL_ACCESS.md").write_text("human draft\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "--workspace", str(workspace), "--module", "Sales"],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("MODEL_ACCESS.md already exists", result.stderr)
            self.assertEqual((workspace / "MODEL_ACCESS.md").read_text(encoding="utf-8"), "human draft\n")
            self.assertFalse((workspace / "AGENTS.md").exists())
            self.assertFalse((workspace / "runtime-config.example.json").exists())

    def test_generated_workspace_does_not_contain_secret_values_or_raw_payload_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "--workspace", str(workspace), "--module", "Ops"],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            joined = "\n".join(
                path.read_text(encoding="utf-8")
                for path in workspace.rglob("*")
                if path.is_file()
            )

        forbidden_patterns = [
            r"\bsk-[A-Za-z0-9]{16,}",
            r"ghp_[A-Za-z0-9]",
            r"xox[baprs]-",
            r"-----BEGIN ",
            r"/Users/",
            r"raw transcript path",
            r"raw telegram export path",
        ]
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, joined), pattern)


if __name__ == "__main__":
    unittest.main()

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(
    os.environ.get("BUSINESS_ONTOLOGY_UPDATE_SELF_TEST") == "1",
    "installed-agent E2E is run outside update self-test to avoid recursion",
)
class InstalledAgentE2ETests(unittest.TestCase):
    def test_fixture_source_copy_excludes_installed_release_metadata(self):
        from scripts import run_installed_agent_e2e as e2e

        with tempfile.TemporaryDirectory(prefix="business-ontology-installed-copy-test-") as tmp:
            root = Path(tmp)
            installed_release = root / "installed-release"
            copied_source = root / "copied-source"
            installed_release.mkdir()
            (installed_release / "agent-package.yaml").write_text(
                'name: business-ontology\nversion: "0.11.10"\n',
                encoding="utf-8",
            )
            (installed_release / e2e.PACKAGE_RELEASE_METADATA).write_text(
                json.dumps({"tag": "v0.11.9", "commit": "production-commit"}) + "\n",
                encoding="utf-8",
            )

            with mock.patch.object(e2e, "REPO_ROOT", installed_release):
                e2e.copy_current_package_source(copied_source)

            self.assertTrue((copied_source / "agent-package.yaml").is_file())
            self.assertFalse((copied_source / e2e.PACKAGE_RELEASE_METADATA).exists())

    def run_e2e(self, *args, work_dir):
        env = os.environ.copy()
        env.pop("BUSINESS_ONTOLOGY_E2E_LIVE", None)
        env.pop("OPENCLAW_WORKSPACE", None)
        return subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "run_installed_agent_e2e.py"),
                *args,
                "--work-dir",
                str(work_dir),
                "--json",
            ],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_live_e2e(self, *args, work_dir, workspace):
        env = os.environ.copy()
        env["BUSINESS_ONTOLOGY_E2E_LIVE"] = "1"
        env["OPENCLAW_WORKSPACE"] = str(workspace)
        return subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "run_installed_agent_e2e.py"),
                "--live",
                *args,
                "--work-dir",
                str(work_dir),
                "--json",
            ],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_raw_body_isolation_accepts_both_raw_branches_and_rejects_workspace_leak(self):
        from scripts.run_installed_agent_e2e import RAW_BODY_SENTINEL, assert_raw_body_isolation

        with tempfile.TemporaryDirectory(prefix="business-ontology-raw-root-test-") as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            model_root = root / "model"
            (workspace / "raw" / "telegram" / "run-1").mkdir(parents=True)
            (workspace / "raw" / "meetings" / "meeting-1").mkdir(parents=True)
            model_root.mkdir()
            (workspace / "runtime-config.example.json").write_text(
                json.dumps({"raw_source_root": "raw"}) + "\n",
                encoding="utf-8",
            )
            (workspace / "raw" / "telegram" / "run-1" / "messages.jsonl").write_text(
                RAW_BODY_SENTINEL + "\n",
                encoding="utf-8",
            )
            (workspace / "raw" / "meetings" / "meeting-1" / "transcript.md").write_text(
                RAW_BODY_SENTINEL + "\n",
                encoding="utf-8",
            )

            self.assertEqual(assert_raw_body_isolation(workspace, model_root), (workspace / "raw").resolve())

            traces = workspace / "traces"
            traces.mkdir()
            (traces / "events.jsonl").write_text(RAW_BODY_SENTINEL + "\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "escaped raw_source_root"):
                assert_raw_body_isolation(workspace, model_root)

    def test_fixture_installed_agent_e2e_proves_update_sources_review_gate_and_viewer(self):
        with tempfile.TemporaryDirectory(prefix="business-ontology-installed-e2e-test-") as tmp:
            work_dir = Path(tmp)
            result = self.run_e2e("--fixture-only", work_dir=work_dir)

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            report = json.loads(result.stdout)
            report_text = json.dumps(report, sort_keys=True)

            self.assertEqual(report["kind"], "installedAgentE2EReport")
            self.assertEqual(report["mode"], "fixture")
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["selected_model_language"], "ru")
            self.assertTrue(Path(report["package_update_proof_path"]).is_file())
            self.assertTrue(Path(report["viewer_publish_report_path"]).is_file())
            self.assertEqual(report["accepted_write_gate_result"]["status"], "pass")
            self.assertEqual(report["human_requests"]["open_count"], 1)
            self.assertEqual(
                {instance["source_instance_id"] for instance in report["source_instances"]},
                {"telegram-mtproto-history", "meeting-recording"},
            )
            self.assertTrue(
                all(instance["status"] == "live-proven" for instance in report["source_instances"])
            )
            self.assertEqual(len(report["live_proofs"]), 2)
            self.assertIn("package_update", {check["name"] for check in report["checks"]})
            self.assertIn("official_viewer_publish", {check["name"] for check in report["checks"]})
            self.assertIn("raw_source_isolation", {check["name"] for check in report["checks"]})
            self.assertNotIn("fixture-secret-not-persisted", report_text)
            self.assertNotIn("raw-body-sentinel-047-do-not-propagate", report_text)
            workspace = Path(report["workspace_state_path"]).parent
            self.assertTrue((workspace / "raw" / "telegram" / "fixture-telegram-run").is_dir())
            self.assertTrue((workspace / "raw" / "meetings" / "mtgrec-20260715-fixture01").is_dir())
            self.assertTrue((work_dir / "INSTALLED_AGENT_E2E_REPORT.json").is_file())
            self.assertTrue((work_dir / "INSTALLED_AGENT_E2E_REPORT.md").is_file())

    def test_live_mode_without_explicit_authorization_writes_blocked_report(self):
        with tempfile.TemporaryDirectory(prefix="business-ontology-installed-live-test-") as tmp:
            work_dir = Path(tmp)
            result = self.run_e2e("--live", work_dir=work_dir)

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report["kind"], "installedAgentE2EReport")
            self.assertEqual(report["mode"], "live")
            self.assertEqual(report["status"], "blocked")
            self.assertEqual(report["checks"][0]["name"], "live_authorization")
            self.assertIn("BUSINESS_ONTOLOGY_E2E_LIVE=1", report["checks"][0]["reason"])
            self.assertTrue((work_dir / "INSTALLED_AGENT_E2E_REPORT.json").is_file())

    def test_live_mode_blocks_when_workspace_readiness_ledgers_are_missing(self):
        with tempfile.TemporaryDirectory(prefix="business-ontology-installed-live-test-") as tmp:
            root = Path(tmp)
            work_dir = root / "report"
            workspace = root / "workspace"
            workspace.mkdir()
            proof = root / "proof.json"
            proof.write_text(
                json.dumps({"accepted_model_write_attempted": False, "event": "read-only-proof"}) + "\n",
                encoding="utf-8",
            )

            result = self.run_live_e2e("--live-proof-file", str(proof), work_dir=work_dir, workspace=workspace)

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "blocked")
            missing_check = next(check for check in report["checks"] if check["name"] == "workspace_readiness_ledgers")
            self.assertEqual(missing_check["status"], "blocked")
            self.assertIn("workspace-state.json", missing_check["reason"])
            self.assertIn("source-instances.json", missing_check["reason"])
            self.assertIn("live-proofs/proofs.json", missing_check["reason"])

    def test_live_mode_does_not_write_bytecode_into_installed_release(self):
        with tempfile.TemporaryDirectory(prefix="business-ontology-installed-live-test-") as tmp:
            root = Path(tmp)
            release = root / "package" / "releases" / "v0.10.2"
            workspace = root / "workspace"
            work_dir = root / "report"
            proof = root / "proof.json"

            def ignore(_: str, names: list[str]) -> set[str]:
                ignored = {
                    ".git",
                    ".data",
                    ".venv",
                    "__pycache__",
                    ".pytest_cache",
                    ".mypy_cache",
                    ".ruff_cache",
                    "dist",
                    "node_modules",
                    "playwright-report",
                    "test-results",
                }
                return {name for name in names if name in ignored or name.endswith(".pyc")}

            shutil.copytree(REPO_ROOT, release, ignore=ignore)
            workspace.mkdir()
            (workspace / "live-proofs").mkdir()
            (workspace / "workspace-state.json").write_text(
                json.dumps(
                    {
                        "agent_identity": {
                            "package_name": "business-ontology",
                            "package_version": "0.10.2",
                            "package_commit": "fixture",
                        },
                        "company_model": {
                            "model_repo": "https://github.com/example/model",
                            "model_repo_revision": "fixture",
                            "company_model_language": "ru",
                            "language_source": "owner-onboarding",
                            "language_decided_at": "2026-07-08T00:00:00Z",
                        },
                        "workspace": {
                            "workspace_id": "fixture",
                            "created_at": "2026-07-08T00:00:00Z",
                            "updated_at": "2026-07-08T00:00:00Z",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            (workspace / "source-instances.json").write_text('{"source_instances": []}\n', encoding="utf-8")
            (workspace / "live-proofs" / "proofs.json").write_text('{"live_proofs": []}\n', encoding="utf-8")
            proof.write_text(
                json.dumps({"accepted_model_write_attempted": False, "event": "read-only-proof"}) + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.pop("PYTHONDONTWRITEBYTECODE", None)
            env.pop("PYTHONPYCACHEPREFIX", None)
            env["BUSINESS_ONTOLOGY_E2E_LIVE"] = "1"
            env["OPENCLAW_WORKSPACE"] = str(workspace)

            result = subprocess.run(
                [
                    sys.executable,
                    str(release / "scripts" / "run_installed_agent_e2e.py"),
                    "--live",
                    "--work-dir",
                    str(work_dir),
                    "--live-proof-file",
                    str(proof),
                    "--json",
                ],
                cwd=release,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertEqual(json.loads(result.stdout)["status"], "passed")
            self.assertEqual([str(path.relative_to(release)) for path in release.rglob("__pycache__")], [])

    def test_e2e_report_schema_locks_fixture_requirements(self):
        schema = json.loads(
            (REPO_ROOT / "schemas" / "installed-agent-e2e-report.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema.get("additionalProperties", True))
        self.assertEqual(schema["properties"]["kind"]["const"], "installedAgentE2EReport")
        self.assertEqual(set(schema["properties"]["mode"]["enum"]), {"fixture", "live"})
        fixture_required = set(schema["allOf"][0]["then"]["required"])
        for field in [
            "package_update_proof_path",
            "workspace_state_path",
            "selected_model_language",
            "source_instances",
            "live_proofs",
            "human_requests",
            "model_change_package_path",
            "accepted_write_gate_result",
            "viewer_publish_report",
        ]:
            self.assertIn(field, fixture_required)

    def test_live_proof_redaction_is_recursive(self):
        from scripts.run_installed_agent_e2e import redact_live_proof

        proof = {
            "event": "meeting-ready",
            "headers": {
                "Authorization": "Bearer live-token",
                "x-api-key": "provider-key",
                "x-request-id": "req-1",
            },
            "payload": [
                {
                    "api_key": "skribby-key",
                    "nested": {"password": "bad", "safe": "ok"},
                }
            ],
        }

        redacted = redact_live_proof(proof)

        text = json.dumps(redacted, sort_keys=True)
        self.assertNotIn("live-token", text)
        self.assertNotIn("provider-key", text)
        self.assertNotIn("skribby-key", text)
        self.assertNotIn("bad", text)
        self.assertEqual(redacted["headers"]["Authorization"], "[redacted]")
        self.assertEqual(redacted["headers"]["x-api-key"], "[redacted]")
        self.assertEqual(redacted["headers"]["x-request-id"], "req-1")
        self.assertEqual(redacted["payload"][0]["nested"]["safe"], "ok")


if __name__ == "__main__":
    unittest.main()

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(
    os.environ.get("BUSINESS_ONTOLOGY_UPDATE_SELF_TEST") == "1",
    "installed-agent E2E is run outside update self-test to avoid recursion",
)
class InstalledAgentE2ETests(unittest.TestCase):
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
            self.assertNotIn("fixture-secret-not-persisted", report_text)
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

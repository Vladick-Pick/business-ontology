import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "publish_viewer.py"
EXAMPLE = REPO_ROOT / "examples" / "acquisition-ontology"
OFFICIAL_VIEWER = REPO_ROOT / "viewer" / "index.html"


def package_version() -> str:
    for line in (REPO_ROOT / "agent-package.yaml").read_text(encoding="utf-8").splitlines():
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip().strip('"')
    raise AssertionError("agent-package.yaml has no version")


def package_commit_for_lock(package_root: Path) -> str:
    metadata = package_root / ".package-release.json"
    if metadata.exists():
        commit = json.loads(metadata.read_text(encoding="utf-8")).get("commit")
        if isinstance(commit, str) and commit:
            return commit
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(package_root),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return "unknown"


class PublishViewerTests(unittest.TestCase):
    def run_publish(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

    def make_workspace(self, root: Path) -> Path:
        workspace = root / "workspace"
        (workspace / "agent-state").mkdir(parents=True)
        (workspace / "runtime-config.json").write_text(
            json.dumps(
                {
                    "module_id": "acquisition",
                    "company_model_language": "ru",
                    "source_instances_path": "source-instances.json",
                    "store_path": "agent-state/operational-store.sqlite",
                }
            ),
            encoding="utf-8",
        )
        (workspace / "workspace-state.json").write_text(
            json.dumps(
                {
                    "company_model": {
                        "company_model_language": "ru",
                        "company_model_language_source": "owner-onboarding",
                    }
                }
            ),
            encoding="utf-8",
        )
        (workspace / "source-instances.json").write_text(
            json.dumps(
                {
                    "source_instances": [
                        {
                            "source_instance_id": "telegram-daily",
                            "status": "live-proven",
                            "last_live_proof_id": "proof-telegram-001",
                        },
                        {
                            "source_instance_id": "meeting-recorder",
                            "status": "failed",
                            "last_live_proof_id": "proof-mtg-001",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        db = workspace / "agent-state" / "operational-store.sqlite"
        with sqlite3.connect(str(db)) as connection:
            connection.execute("create table human_requests (request_id text, status text)")
            connection.execute("insert into human_requests values ('hreq-open', 'open')")
            connection.execute("insert into human_requests values ('hreq-answered', 'answered')")
        return workspace

    def test_official_publish_writes_viewer_bundle_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            out_dir = workspace / "viewer"

            result = self.run_publish(EXAMPLE, "--workspace", workspace, "--out-dir", out_dir, "--as-of", "2026-12-01")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((out_dir / "index.html").read_text(encoding="utf-8"), OFFICIAL_VIEWER.read_text(encoding="utf-8"))
            report = json.loads((out_dir / "VIEWER_PUBLISH_REPORT.json").read_text(encoding="utf-8"))
            bundle = json.loads((out_dir / "ontology.json").read_text(encoding="utf-8"))

            self.assertEqual(report["status"], "published")
            self.assertEqual(report["package_version"], package_version())
            self.assertEqual(report["company_model_language"], "ru")
            self.assertEqual(report["source_readiness"]["live_proven"], 1)
            self.assertEqual(report["source_readiness"]["failed"], 1)
            self.assertEqual(report["open_human_request_count"], 1)
            self.assertEqual(report["validation"]["status"], "passed")
            self.assertTrue(report["viewer_asset_hash"].startswith("sha256:"))
            self.assertTrue(report["bundle_hash"].startswith("sha256:"))

            self.assertEqual(bundle["packageVersion"], report["package_version"])
            self.assertEqual(bundle["packageCommit"], report["package_commit"])
            self.assertEqual(bundle["modelRevision"], report["model_revision"])
            self.assertEqual(bundle["companyModelLanguage"], "ru")
            self.assertEqual(bundle["sourceReadiness"]["liveProvenCount"], 1)
            self.assertEqual(bundle["openHumanRequestCount"], 1)
            self.assertEqual(bundle["validationStatus"], "passed")

    def test_custom_html_is_rejected_without_partial_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            out_dir = workspace / "viewer"
            out_dir.mkdir(parents=True)
            custom = "<html>custom</html>"
            (out_dir / "index.html").write_text(custom, encoding="utf-8")

            result = self.run_publish(EXAMPLE, "--workspace", workspace, "--out-dir", out_dir)

            self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
            self.assertIn("custom-viewer-rejected", result.stdout)
            self.assertEqual((out_dir / "index.html").read_text(encoding="utf-8"), custom)
            self.assertFalse((out_dir / "ontology.json").exists())
            self.assertFalse((out_dir / "VIEWER_PUBLISH_REPORT.json").exists())

    def test_explicit_override_replaces_custom_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            out_dir = workspace / "viewer"
            out_dir.mkdir(parents=True)
            (out_dir / "index.html").write_text("<html>custom</html>", encoding="utf-8")

            result = self.run_publish(EXAMPLE, "--workspace", workspace, "--out-dir", out_dir, "--allow-overwrite-custom")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((out_dir / "index.html").read_text(encoding="utf-8"), OFFICIAL_VIEWER.read_text(encoding="utf-8"))
            self.assertTrue((out_dir / "VIEWER_PUBLISH_REPORT.json").exists())

    def test_publish_prefers_model_repo_validator_wrapper_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = self.make_workspace(root)
            model = root / "model"
            shutil.copytree(EXAMPLE, model)
            (model / "scripts").mkdir()
            (model / "scripts" / "validate_model_repo.py").write_text(
                (REPO_ROOT / "templates" / "model-repo" / "scripts" / "validate_model_repo.py.tpl").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            package_commit = package_commit_for_lock(REPO_ROOT)
            (model / "PACKAGE_CONTRACT.lock").write_text(
                json.dumps(
                    {
                        "package_name": "business-ontology",
                        "package_version": package_version(),
                        "package_commit": package_commit,
                        "validator_contract": "data-model-v2-hard-gate",
                        "validator": "scripts/links_validate.py",
                    }
                ),
                encoding="utf-8",
            )
            out_dir = workspace / "viewer"

            result = self.run_publish(model, "--workspace", workspace, "--out-dir", out_dir, "--json")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((out_dir / "VIEWER_PUBLISH_REPORT.json").read_text(encoding="utf-8"))
            self.assertEqual(report["validation"]["validator"], "model-repo-wrapper")
            self.assertIn("validate_model_repo.py", report["validation"]["command"][1])
            self.assertNotIn("stdout", report["validation"])
            self.assertNotIn("stderr", report["validation"])

    def test_validation_failure_blocks_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = self.make_workspace(root)
            model = root / "bad-model"
            model.mkdir()
            (model / "bad.md").write_text(
                """---
id: deprecated-card
type: concept
status: accepted
source: missing-source
owner: owner
last-reviewed: 2026-07-08
next-audit: 2026-08-08
---
# Deprecated
""",
                encoding="utf-8",
            )
            out_dir = workspace / "viewer"

            result = self.run_publish(model, "--workspace", workspace, "--out-dir", out_dir)

            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertIn("validation-failed", result.stdout)
            self.assertFalse((out_dir / "index.html").exists())
            self.assertFalse((out_dir / "ontology.json").exists())
            self.assertFalse((out_dir / "VIEWER_PUBLISH_REPORT.json").exists())

    def test_absolute_runtime_config_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            config = json.loads((workspace / "runtime-config.json").read_text(encoding="utf-8"))
            config["source_instances_path"] = "/private/source-instances.json"
            (workspace / "runtime-config.json").write_text(json.dumps(config), encoding="utf-8")
            out_dir = workspace / "viewer"

            result = self.run_publish(EXAMPLE, "--workspace", workspace, "--out-dir", out_dir)

            self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
            self.assertIn("config-invalid", result.stdout)
            self.assertFalse((out_dir / "index.html").exists())
            self.assertFalse((out_dir / "ontology.json").exists())
            self.assertFalse((out_dir / "VIEWER_PUBLISH_REPORT.json").exists())


if __name__ == "__main__":
    unittest.main()

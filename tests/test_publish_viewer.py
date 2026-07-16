import json
import hashlib
from contextlib import closing
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from scripts import publish_viewer


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "publish_viewer.py"
EXAMPLE = REPO_ROOT / "examples" / "acquisition-ontology"
EXAMPLE_V2 = REPO_ROOT / "examples" / "business-attraction-v2"
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
        with closing(sqlite3.connect(str(db))) as connection:
            connection.execute(
                """
                create table human_requests (
                    request_id text,
                    kind text,
                    status text,
                    owner text,
                    channel text,
                    message_ref text,
                    prompt text,
                    recommended_answer text,
                    blocks_json text,
                    source_ref text,
                    package_id text,
                    asked_at text,
                    due_at text,
                    answered_at text,
                    answer_summary text,
                    decision_id text,
                    created_at text,
                    updated_at text
                )
                """
            )
            connection.execute(
                """
                insert into human_requests values (
                    'hreq-open', 'review', 'open', 'owner',
                    'telegram:dm-owner', 'tg#42',
                    'Подтвердить владельца handoff?',
                    'Оставить role:acquisition-owner, если нет нового источника.',
                    '{"blocks":["package:mcpkg-handoff"]}',
                    'srcevt-store-telegram-001', 'mcpkg-handoff',
                    '2026-07-08T09:00:00Z', '2026-07-09T09:00:00Z',
                    '', '', '', '2026-07-08T09:00:00Z', '2026-07-08T09:00:00Z'
                )
                """
            )
            connection.execute(
                """
                insert into human_requests values (
                    'hreq-answered', 'review', 'answered', 'owner',
                    'telegram:dm-owner', 'tg#41',
                    'Closed?', 'Closed.',
                    '{"blocks":[]}', '', '',
                    '2026-07-07T09:00:00Z', '', '2026-07-07T10:00:00Z',
                    'Answered.', 'hdec-1', '2026-07-07T09:00:00Z', '2026-07-07T10:00:00Z'
                )
                """
            )
            connection.execute(
                """
                create table model_change_packages (
                    package_id text,
                    module_id text,
                    status text,
                    risk text,
                    review_action text,
                    payload_json text,
                    created_at text,
                    updated_at text
                )
                """
            )
            package = {
                "packageId": "mcpkg-viewer-working-layer",
                "moduleId": "acquisition",
                "generatedAt": "2026-07-15T08:00:00Z",
                "summary": "One structured hypothesis and one unresolved change await review.",
                "changes": [
                    {
                        "changeId": "chg-working-card",
                        "kind": "new-object",
                        "confidence": "medium",
                        "risk": "medium",
                        "claimKind": "agent-inference",
                        "evidenceGrade": "hypothesis",
                        "sourceRisk": ["manual-memory"],
                        "affectedIds": ["candidate-offer"],
                        "evidence": [
                            {
                                "sourceEventId": "srcevt-working-layer",
                                "locator": "private:packet#segment-1",
                                "excerpt": "PRIVATE EVIDENCE MUST NOT ENTER THE VIEWER",
                            }
                        ],
                        "proposedAction": "prepare-staged-proposal",
                        "candidateCard": {
                            "id": "candidate-offer",
                            "type": "artifact",
                            "status": "hypothesis",
                            "source": "src-working-layer",
                            "owner": "owner",
                            "summary": "Offer candidate awaiting human review.",
                            "links": {},
                            "attrs": {
                                "kind": "offer",
                                "unreviewedNote": "PRIVATE CANDIDATE ATTRIBUTE MUST NOT ENTER THE VIEWER",
                            },
                        },
                    },
                    {
                        "changeId": "chg-needs-info",
                        "kind": "new-definition",
                        "confidence": "low",
                        "risk": "medium",
                        "claimKind": "agent-inference",
                        "evidenceGrade": "inference",
                        "sourceRisk": ["manual-memory"],
                        "affectedIds": ["unstructured-question"],
                        "evidence": [
                            {
                                "sourceEventId": "srcevt-working-layer",
                                "locator": "private:packet#segment-2",
                                "excerpt": "ANOTHER PRIVATE EXCERPT",
                            }
                        ],
                        "proposedAction": "needs-info",
                    },
                ],
            }
            connection.execute(
                """
                insert into model_change_packages values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    package["packageId"],
                    package["moduleId"],
                    "pending",
                    "medium",
                    "human-review",
                    json.dumps(package),
                    "2026-07-15T08:00:00Z",
                    "2026-07-15T08:00:00Z",
                ),
            )
            connection.commit()
        return workspace

    def test_official_publish_writes_viewer_bundle_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            out_dir = workspace / "viewer"
            out_dir.mkdir()
            stale_bundle = out_dir / "ontology.0000000000000000.json"
            stale_bundle.write_text('{"private":"stale"}\n', encoding="utf-8")

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
            self.assertEqual(report["privacy"], {"status": "passed", "policy": "public-viewer-v1"})
            self.assertTrue(report["viewer_asset_hash"].startswith("sha256:"))
            self.assertTrue(report["bundle_hash"].startswith("sha256:"))
            self.assertEqual(report["publication"]["mode"], "workspace-only")
            self.assertEqual(report["publication"]["status"], "workspace-only")
            self.assertEqual(report["working_model"]["package_count"], 1)
            self.assertEqual(report["working_model"]["card_count"], 1)
            self.assertRegex(report["bundle"], r"^ontology\.[0-9a-f]{16}\.json$")
            self.assertTrue((out_dir / report["bundle"]).is_file())
            self.assertFalse(stale_bundle.exists())

            self.assertEqual(bundle["packageVersion"], report["package_version"])
            self.assertEqual(bundle["packageCommit"], report["package_commit"])
            self.assertEqual(bundle["modelRevision"], report["model_revision"])
            self.assertEqual(bundle["companyModelLanguage"], "ru")
            self.assertEqual(bundle["sourceReadiness"]["liveProvenCount"], 1)
            self.assertEqual(bundle["openHumanRequestCount"], 1)
            self.assertEqual(bundle["openHumanRequests"][0]["requestId"], "hreq-open")
            self.assertEqual(bundle["openHumanRequests"][0]["prompt"], "Подтвердить владельца handoff?")
            self.assertEqual(bundle["openHumanRequests"][0]["blocks"], ["package:mcpkg-handoff"])
            self.assertTrue(
                any(item.get("requestId") == "hreq-open" for item in bundle["reviewItems"]),
                bundle["reviewItems"],
            )
            self.assertEqual(bundle["workingModel"]["packageCount"], 1)
            self.assertEqual(bundle["workingModel"]["changeCount"], 2)
            self.assertEqual(bundle["workingModel"]["cardCount"], 1)
            self.assertEqual(bundle["workingCards"][0]["id"], "candidate-offer")
            self.assertEqual(bundle["workingCards"][0]["modelLayer"], "working")
            self.assertTrue(
                any(item.get("kind") == "model-change" for item in bundle["reviewItems"]),
                bundle["reviewItems"],
            )
            serialized = json.dumps(bundle, ensure_ascii=False)
            self.assertNotIn("telegram:dm-owner", serialized)
            self.assertNotIn("tg#42", serialized)
            self.assertNotIn("PRIVATE EVIDENCE", serialized)
            self.assertNotIn("private:packet", serialized)
            self.assertNotIn("PRIVATE CANDIDATE ATTRIBUTE", serialized)
            self.assertEqual(bundle["workingCards"][0]["attrs"], {})
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

    def test_package_update_replaces_a_proven_previous_official_viewer(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            out_dir = workspace / "viewer"
            out_dir.mkdir(parents=True)
            old_official = "<html>previous package viewer</html>"
            (out_dir / "index.html").write_text(old_official, encoding="utf-8")
            (out_dir / "VIEWER_PUBLISH_REPORT.json").write_text(
                json.dumps(
                    {
                        "status": "published",
                        "viewer_asset_hash": "sha256:"
                        + hashlib.sha256(old_official.encode("utf-8")).hexdigest(),
                    }
                ),
                encoding="utf-8",
            )

            result = self.run_publish(EXAMPLE, "--workspace", workspace, "--out-dir", out_dir)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(
                (out_dir / "index.html").read_text(encoding="utf-8"),
                OFFICIAL_VIEWER.read_text(encoding="utf-8"),
            )

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

    def test_viewer_projection_failure_blocks_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = self.make_workspace(root)
            model = root / "bad-viewer-projection"
            shutil.copytree(EXAMPLE_V2, model)
            stage_card = model / "production-systems" / "ps-attraction-btx.md"
            stage_card.write_text(
                stage_card.read_text(encoding="utf-8").replace(
                    "processes: [p-handle-delivery]",
                    "processes: [p-missing]",
                    1,
                ),
                encoding="utf-8",
            )
            out_dir = workspace / "viewer"

            result = self.run_publish(model, "--workspace", workspace, "--out-dir", out_dir, "--module", "biz-attraction")

            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertIn("viewer-projection-invalid", result.stdout)
            self.assertIn("p-missing", result.stdout)
            self.assertFalse((out_dir / "index.html").exists())
            self.assertFalse((out_dir / "ontology.json").exists())
            self.assertFalse((out_dir / "VIEWER_PUBLISH_REPORT.json").exists())

    def test_privacy_failure_blocks_publish_without_echoing_private_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            private_value = "owner@example.test"
            database = workspace / "agent-state" / "operational-store.sqlite"
            with closing(sqlite3.connect(str(database))) as connection:
                connection.execute(
                    "update human_requests set prompt = ? where request_id = 'hreq-open'",
                    (f"Contact {private_value} before approval.",),
                )
                connection.commit()
            out_dir = workspace / "viewer"

            result = self.run_publish(EXAMPLE, "--workspace", workspace, "--out-dir", out_dir)

            self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
            self.assertIn("viewer-privacy-invalid", result.stdout)
            self.assertIn("openHumanRequests[0].prompt", result.stdout)
            self.assertNotIn(private_value, result.stdout + result.stderr)
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

    def test_public_verification_checks_named_bundle_and_release_identity(self):
        index = "<html>official viewer</html>"
        bundle = '{"packageVersion":"0.11.12"}\n'
        bundle_name = "ontology.0123456789abcdef.json"
        report = {
            "status": "published",
            "privacy": {"status": "passed", "policy": "public-viewer-v1"},
            "viewer_asset_hash": publish_viewer.sha256_text(index),
            "bundle_hash": publish_viewer.sha256_text(bundle),
            "bundle": bundle_name,
            "package_version": "0.11.12",
            "package_commit": "a" * 40,
            "model_revision": "model-1",
        }
        remote_report = json.dumps(report)
        responses = {
            "https://example.test/model/": index,
            "https://example.test/model/VIEWER_PUBLISH_REPORT.json": remote_report,
            f"https://example.test/model/{bundle_name}": bundle,
        }
        with mock.patch.object(
            publish_viewer,
            "_fetch_public_text",
            side_effect=lambda url: responses[url],
        ):
            proof = publish_viewer.verify_publication(
                "https://example.test/model/",
                report,
            )

        self.assertEqual(proof["status"], "verified")
        self.assertEqual(proof["infrastructure_status"], "verified")
        self.assertEqual(proof["public_url"], "https://example.test/model/")


if __name__ == "__main__":
    unittest.main()

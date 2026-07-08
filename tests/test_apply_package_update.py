import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
APPLY = REPO_ROOT / "scripts" / "apply_package_update.py"
VERIFY = REPO_ROOT / "scripts" / "verify_installed_package.py"


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def commit(repo: Path, message: str) -> str:
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-m", message)
    return run_git(repo, "rev-parse", "HEAD")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def tree_snapshot(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    if not root.exists():
        return snapshot
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        if path.is_symlink():
            snapshot[rel] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            snapshot[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.is_dir():
            snapshot[rel] = "dir"
    return snapshot


def load_lock(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def release_commit(release: Path) -> str:
    metadata = release / ".package-release.json"
    if metadata.exists():
        return load_lock(metadata)["commit"]
    return run_git(release, "rev-parse", "HEAD")


class ApplyPackageUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.remote = self.root / "remote"
        run_git(Path(self.tmp.name), "init", str(self.remote))
        run_git(self.remote, "config", "user.email", "agent@example.com")
        run_git(self.remote, "config", "user.name", "Agent")
        self.shas = self.create_release_tags()
        self.install = self.root / "install"
        self.workspace = self.install / "workspace"
        self.package = self.install / "package"
        self.model_repo = self.install / "model-repo"
        self.setup_install(remote_url=str(self.remote))

    def tearDown(self):
        self.tmp.cleanup()

    def create_release_tags(self) -> dict[str, str]:
        shas: dict[str, str] = {}
        self.write_release("0.9.0", self_test=0, validator=0)
        shas["v0.9.0"] = commit(self.remote, "release 0.9.0")
        run_git(self.remote, "tag", "v0.9.0")

        self.write_release("0.10.0", self_test=0, validator=0, strict_validator=1)
        shas["v0.10.0"] = commit(self.remote, "release 0.10.0")
        run_git(self.remote, "tag", "v0.10.0")

        self.write_release("0.11.0", self_test=1, validator=0)
        shas["v0.11.0"] = commit(self.remote, "release 0.11.0 self-test fail")
        run_git(self.remote, "tag", "v0.11.0")

        self.write_release("0.12.0", self_test=0, validator=1)
        shas["v0.12.0"] = commit(self.remote, "release 0.12.0 validator fail")
        run_git(self.remote, "tag", "v0.12.0")

        self.write_release("0.13.0", self_test=0, validator=0, adversarial=True)
        shas["v0.13.0"] = commit(self.remote, "release 0.13.0 adversarial validator")
        run_git(self.remote, "tag", "v0.13.0")

        self.write_release("0.14.0", self_test=0, validator=0)
        shas["v0.14.0"] = commit(self.remote, "release 0.14.0")
        run_git(self.remote, "tag", "v0.14.0")

        self.write_release("0.15.0", self_test=0, validator=0)
        shas["v0.15.0"] = commit(self.remote, "release 0.15.0")
        run_git(self.remote, "tag", "v0.15.0")
        return shas

    def write_release(
        self,
        version: str,
        *,
        self_test: int,
        validator: int,
        strict_validator: int | None = None,
        adversarial: bool = False,
    ) -> None:
        write(
            self.remote / "scripts" / "package_self_test.py",
            f"#!/usr/bin/env python3\nimport sys\nsys.exit({self_test})\n",
        )
        if adversarial:
            validator_code = (
                "#!/usr/bin/env python3\n"
                "from pathlib import Path\n"
                "import sys\n"
                "Path(sys.argv[1], 'validator-wrote-here.txt').write_text('owned', encoding='utf-8')\n"
                "sys.exit(0)\n"
            )
        else:
            if strict_validator is None:
                validator_code = f"#!/usr/bin/env python3\nimport sys\nsys.exit({validator})\n"
            else:
                validator_code = (
                    "#!/usr/bin/env python3\n"
                    "import sys\n"
                    f"sys.exit({strict_validator} if '--strict-transitional' in sys.argv else {validator})\n"
                )
        write(self.remote / "scripts" / "links_validate.py", validator_code)
        write(self.remote / "CHANGELOG.md", f"# Changelog\n\n## {version} - Test\n\n- Test release.\n")
        write(self.remote / "VERSION.txt", version)

    def setup_install(self, *, remote_url: str) -> None:
        (self.package / "releases").mkdir(parents=True)
        run_git(Path(self.tmp.name), "clone", str(self.remote), str(self.package / "releases" / "v0.9.0"))
        run_git(self.package / "releases" / "v0.9.0", "checkout", "--detach", "v0.9.0")
        os.symlink("releases/v0.9.0", self.package / "current")
        self.workspace.mkdir(parents=True)
        write(self.workspace / "SOURCE_CURSORS.md", "cursor: keep\n")
        write(self.workspace / "INTERACTION_CONTRACT.md", "daily\n")
        write(
            self.workspace / "runtime-config.example.json",
            json.dumps(
                {
                    "accepted_model_repository": "https://github.com/example/model",
                    "company_model_language": "ru",
                    "company_model_language_source": "owner-onboarding",
                    "generated_at": "2026-07-01T00:00:00Z",
                    "module_id": "company-baseline",
                    "ontology_revision": "model-rev-1",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        write(
            self.workspace / "PACKAGE_VERSION.lock",
            json.dumps(
                {
                    "current_version": "0.9.0",
                    "tag": "v0.9.0",
                    "commit": self.shas["v0.9.0"],
                    "installed_at": "2026-07-06T00:00:00Z",
                    "previous_version": None,
                    "previous_commit": None,
                    "remote_url": remote_url,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        run_git(Path(self.tmp.name), "init", str(self.model_repo))
        run_git(self.model_repo, "config", "user.email", "model@example.com")
        run_git(self.model_repo, "config", "user.name", "Model")
        write(self.model_repo / "accepted.md", "accepted model\n")
        commit(self.model_repo, "accepted model")

    def run_apply(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(APPLY), "--install-root", str(self.install), *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_verify(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VERIFY), "--install-root", str(self.install), *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_apply_flips_current_and_updates_lock(self):
        result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.readlink(self.package / "current"), "releases/v0.14.0")
        lock = load_lock(self.workspace / "PACKAGE_VERSION.lock")
        self.assertEqual(lock["tag"], "v0.14.0")
        self.assertEqual(lock["commit"], self.shas["v0.14.0"])
        self.assertEqual(lock["previous_version"], "0.9.0")
        self.assertEqual(lock["previous_commit"], self.shas["v0.9.0"])

    def test_apply_writes_install_proof_and_clean_release_tree(self):
        result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))

        self.assertEqual(result.returncode, 0, result.stderr)
        report_path = self.workspace / "PACKAGE_INSTALL_REPORT.json"
        self.assertTrue(report_path.exists())
        report = load_lock(report_path)
        self.assertEqual(report["status"], "installed")
        self.assertEqual(report["package_tag"], "v0.14.0")
        self.assertEqual(report["package_commit"], self.shas["v0.14.0"])
        self.assertEqual(report["release_dir"], "package/releases/v0.14.0")
        self.assertEqual(report["current_symlink"], "package/current")
        self.assertEqual(report["self_test"]["status"], "passed")
        self.assertEqual(report["model_validation"]["status"], "passed")
        self.assertIs(report["model_validation"]["used_copy"], True)
        self.assertEqual(report["model_support_contract"]["status"], "missing")
        self.assertIs(report["model_support_contract"]["review_required"], True)
        self.assertTrue(report["rollback"]["available_offline"])
        release = self.package / "releases" / "v0.14.0"
        self.assertFalse((release / ".git").exists())
        self.assertFalse(any(path.name == "__pycache__" for path in release.rglob("*")))
        payload = json.loads(result.stdout)
        self.assertEqual(payload["install_report"], str(report_path.resolve()))

    def test_apply_reports_current_model_support_contract_when_lock_matches_release(self):
        write(
            self.model_repo / "PACKAGE_CONTRACT.lock",
            json.dumps(
                {
                    "package_name": "business-ontology",
                    "package_version": "0.14.0",
                    "package_commit": self.shas["v0.14.0"],
                    "validator": "scripts/links_validate.py",
                    "validator_contract": "data-model-v2-hard-gate",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )

        result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))

        self.assertEqual(result.returncode, 0, result.stderr)
        report = load_lock(self.workspace / "PACKAGE_INSTALL_REPORT.json")
        self.assertEqual(report["model_support_contract"]["status"], "current")
        self.assertIs(report["model_support_contract"]["review_required"], False)

    def test_model_support_contract_reads_version_from_manifest_when_release_path_is_not_tag(self):
        release = self.root / "Бизнес онтология"
        run_git(Path(self.tmp.name), "clone", str(self.remote), str(release))
        run_git(release, "checkout", "--detach", "v0.14.0")
        (release / "VERSION.txt").unlink()
        write(release / "agent-package.yaml", 'name: business-ontology\nversion: "0.14.0"\n')
        write(
            self.model_repo / "PACKAGE_CONTRACT.lock",
            json.dumps(
                {
                    "package_name": "business-ontology",
                    "package_version": "0.14.0",
                    "package_commit": self.shas["v0.14.0"],
                    "validator": "scripts/links_validate.py",
                    "validator_contract": "data-model-v2-hard-gate",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )

        from scripts.apply_package_update import model_support_contract_report

        report = model_support_contract_report(release, self.model_repo)

        self.assertEqual(report["status"], "current")
        self.assertEqual(report["expected"]["package_version"], "0.14.0")
        self.assertIs(report["review_required"], False)

    def test_apply_reports_stale_copied_model_validator_as_review_required(self):
        before_model = tree_snapshot(self.model_repo)
        write(self.model_repo / "scripts" / "links_validate.py", "# stale copied validator\n")

        result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))

        self.assertEqual(result.returncode, 0, result.stderr)
        report = load_lock(self.workspace / "PACKAGE_INSTALL_REPORT.json")
        self.assertEqual(report["model_support_contract"]["status"], "unsupported-copied-validator")
        self.assertIs(report["model_support_contract"]["review_required"], True)
        after_without_stale = tree_snapshot(self.model_repo)
        after_without_stale.pop("scripts", None)
        after_without_stale.pop("scripts/links_validate.py", None)
        self.assertEqual(after_without_stale, before_model)

    def test_apply_reports_invalid_model_support_lock_as_review_required(self):
        write(self.model_repo / "PACKAGE_CONTRACT.lock", "{not json")

        result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))

        self.assertEqual(result.returncode, 0, result.stderr)
        report = load_lock(self.workspace / "PACKAGE_INSTALL_REPORT.json")
        self.assertEqual(report["model_support_contract"]["status"], "invalid")
        self.assertIs(report["model_support_contract"]["review_required"], True)

    def test_verify_installed_package_accepts_proven_update(self):
        apply_result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))
        self.assertEqual(apply_result.returncode, 0, apply_result.stderr)

        verify = self.run_verify()

        self.assertEqual(verify.returncode, 0, verify.stderr)
        payload = json.loads(verify.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["package_tag"], "v0.14.0")
        self.assertEqual(payload["package_commit"], self.shas["v0.14.0"])

    def test_apply_materializes_missing_readiness_ledgers_for_existing_workspace(self):
        result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))

        self.assertEqual(result.returncode, 0, result.stderr)
        workspace_state = load_lock(self.workspace / "workspace-state.json")
        self.assertEqual(workspace_state["company_model"]["model_repo"], "https://github.com/example/model")
        self.assertEqual(workspace_state["company_model"]["company_model_language"], "ru")
        self.assertEqual(workspace_state["agent_identity"]["package_version"], "0.14.0")
        self.assertEqual(load_lock(self.workspace / "source-instances.json")["source_instances"], [])
        self.assertEqual(load_lock(self.workspace / "live-proofs" / "proofs.json")["live_proofs"], [])

    def test_apply_refreshes_existing_workspace_state_package_identity(self):
        write(
            self.workspace / "workspace-state.json",
            json.dumps(
                {
                    "agent_identity": {
                        "package_name": "business-ontology",
                        "package_version": "0.9.0",
                        "package_commit": self.shas["v0.9.0"],
                    },
                    "company_model": {
                        "model_repo": "https://github.com/example/model",
                        "model_repo_revision": "model-rev-1",
                        "company_model_language": "ru",
                        "language_source": "owner-onboarding",
                        "language_decided_at": "2026-07-01T00:00:00Z",
                    },
                    "workspace": {
                        "workspace_id": "company-baseline",
                        "created_at": "2026-07-01T00:00:00Z",
                        "updated_at": "2026-07-01T00:00:00Z",
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )

        result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))

        self.assertEqual(result.returncode, 0, result.stderr)
        workspace_state = load_lock(self.workspace / "workspace-state.json")
        self.assertEqual(workspace_state["agent_identity"]["package_version"], "0.14.0")
        self.assertEqual(workspace_state["agent_identity"]["package_commit"], self.shas["v0.14.0"])
        self.assertEqual(workspace_state["company_model"]["company_model_language"], "ru")
        self.assertEqual(workspace_state["company_model"]["model_repo"], "https://github.com/example/model")

    def test_verify_installed_package_rejects_missing_readiness_ledgers(self):
        apply_result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))
        self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
        (self.workspace / "source-instances.json").unlink()

        verify = self.run_verify()

        self.assertEqual(verify.returncode, 12, verify.stderr)
        payload = json.loads(verify.stdout)
        self.assertEqual(payload["status"], "readiness-ledger-missing")
        self.assertIn("source-instances.json", payload["missing"])

    def test_verify_installed_package_rejects_manual_relink_without_report(self):
        os.unlink(self.package / "current")
        os.symlink("releases/v0.9.0", self.package / "current")

        verify = self.run_verify()

        self.assertEqual(verify.returncode, 6, verify.stderr)
        payload = json.loads(verify.stdout)
        self.assertEqual(payload["status"], "manual-or-unproven-install")

    def test_verify_installed_package_rejects_dirty_active_release_tree(self):
        apply_result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))
        self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
        dirty_dir = self.package / "releases" / "v0.14.0" / "__pycache__"
        dirty_dir.mkdir()
        (dirty_dir / "x.pyc").write_bytes(b"dirty")

        verify = self.run_verify()

        self.assertEqual(verify.returncode, 7, verify.stderr)
        payload = json.loads(verify.stdout)
        self.assertEqual(payload["status"], "dirty-release-tree")

    def test_verify_installed_package_requires_model_support_contract_report(self):
        apply_result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))
        self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
        report_path = self.workspace / "PACKAGE_INSTALL_REPORT.json"
        report = load_lock(report_path)
        report.pop("model_support_contract")
        write(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")

        verify = self.run_verify()

        self.assertEqual(verify.returncode, 11, verify.stderr)
        payload = json.loads(verify.stdout)
        self.assertEqual(payload["status"], "model-support-contract-missing")

    def test_verify_installed_package_rejects_report_older_than_current_flip(self):
        apply_result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))
        self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
        current = self.package / "current"
        os.unlink(current)
        os.symlink("releases/v0.14.0", current)

        verify = self.run_verify()

        self.assertEqual(verify.returncode, 6, verify.stderr)
        payload = json.loads(verify.stdout)
        self.assertEqual(payload["status"], "manual-or-unproven-install")
        self.assertEqual(payload["reason"], "install report is older than current symlink")

    def test_apply_preserves_existing_source_and_proof_ledgers(self):
        write(
            self.workspace / "workspace-state.json",
            json.dumps(
                {
                    "agent_identity": {
                        "package_name": "business-ontology",
                        "package_version": "0.9.0",
                        "package_commit": self.shas["v0.9.0"],
                    },
                    "company_model": {
                        "model_repo": "https://github.com/example/model",
                        "model_repo_revision": "model-rev-1",
                        "company_model_language": "ru",
                        "language_source": "owner-onboarding",
                        "language_decided_at": "2026-07-01T00:00:00Z",
                    },
                    "workspace": {
                        "workspace_id": "company-baseline",
                        "created_at": "2026-07-01T00:00:00Z",
                        "updated_at": "2026-07-01T00:00:00Z",
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        write(
            self.workspace / "source-instances.json",
            '{"source_instances": [{"source_instance_id": "existing-source"}]}\n',
        )
        write(
            self.workspace / "live-proofs" / "proofs.json",
            '{"live_proofs": [{"live_proof_id": "existing-proof"}]}\n',
        )
        before = tree_snapshot(self.workspace)
        result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))
        after = tree_snapshot(self.workspace)

        self.assertEqual(result.returncode, 0, result.stderr)
        before.pop("PACKAGE_VERSION.lock")
        before.pop("workspace-state.json")
        after.pop("PACKAGE_VERSION.lock")
        after.pop("PACKAGE_INSTALL_REPORT.json")
        after.pop("workspace-state.json")
        self.assertEqual(after, before)

    def test_model_validation_errors_block_flip(self):
        result = self.run_apply("--to", "v0.12.0", "--model-repo", str(self.model_repo))

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(os.readlink(self.package / "current"), "releases/v0.9.0")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "migration-required")

    def test_v010_strict_transitional_schema_errors_block_flip(self):
        before_model = tree_snapshot(self.model_repo)
        result = self.run_apply("--to", "v0.10.0", "--model-repo", str(self.model_repo))

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(os.readlink(self.package / "current"), "releases/v0.9.0")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "migration-required")
        self.assertEqual(payload["tag"], "v0.10.0")
        self.assertEqual(tree_snapshot(self.model_repo), before_model)

    def test_self_test_failure_blocks_flip_and_removes_fresh_release(self):
        result = self.run_apply("--to", "v0.11.0", "--model-repo", str(self.model_repo))

        self.assertEqual(result.returncode, 4)
        self.assertEqual(os.readlink(self.package / "current"), "releases/v0.9.0")
        self.assertFalse((self.package / "releases" / "v0.11.0").exists())

    def test_rollback_swaps_current_previous_without_model_repo(self):
        apply_result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))
        self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
        before_model = tree_snapshot(self.model_repo)

        rollback = self.run_apply("--rollback")

        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertEqual(os.readlink(self.package / "current"), "releases/v0.9.0")
        self.assertEqual(tree_snapshot(self.model_repo), before_model)
        lock = load_lock(self.workspace / "PACKAGE_VERSION.lock")
        self.assertEqual(lock["tag"], "v0.9.0")
        self.assertEqual(lock["previous_version"], "0.14.0")

    def test_rollback_writes_install_proof_and_verifies(self):
        apply_result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))
        self.assertEqual(apply_result.returncode, 0, apply_result.stderr)

        rollback = self.run_apply("--rollback")
        verify = self.run_verify()

        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertEqual(verify.returncode, 0, verify.stderr)
        report = load_lock(self.workspace / "PACKAGE_INSTALL_REPORT.json")
        self.assertEqual(report["status"], "rolled-back")
        self.assertEqual(report["package_tag"], "v0.9.0")
        self.assertEqual(report["package_commit"], self.shas["v0.9.0"])
        self.assertEqual(report["self_test"]["status"], "passed")
        self.assertEqual(report["model_validation"]["status"], "not_required_for_rollback")

    def test_lock_consistent_after_apply_and_rollback(self):
        self.assertEqual(self.run_apply("--to", "v0.14.0").returncode, 0)
        lock = load_lock(self.workspace / "PACKAGE_VERSION.lock")
        self.assertEqual(release_commit(self.package / "releases" / lock["tag"]), lock["commit"])

        self.assertEqual(self.run_apply("--rollback").returncode, 0)
        lock = load_lock(self.workspace / "PACKAGE_VERSION.lock")
        self.assertEqual(release_commit(self.package / "releases" / lock["tag"]), lock["commit"])

    def test_prune_keeps_current_and_previous(self):
        self.assertEqual(self.run_apply("--to", "v0.14.0").returncode, 0)
        result = self.run_apply("--to", "v0.15.0")

        self.assertEqual(result.returncode, 0, result.stderr)
        releases = {path.name for path in (self.package / "releases").iterdir() if path.is_dir()}
        self.assertIn("v0.15.0", releases)
        self.assertIn("v0.14.0", releases)
        self.assertNotIn("v0.9.0", releases)

    def test_live_update_lock_exit_5_without_changes(self):
        lock_file = self.package / ".update.lock"
        lock_file.write_text(json.dumps({"pid": 1, "timestamp": "2026-07-06T00:00:00Z"}), encoding="utf-8")
        before = tree_snapshot(self.install)

        result = self.run_apply("--to", "v0.10.0")

        self.assertEqual(result.returncode, 5)
        self.assertEqual(tree_snapshot(self.install), before)

    def test_adversarial_validator_receives_copy_not_model_repo(self):
        before_model = tree_snapshot(self.model_repo)
        result = self.run_apply("--to", "v0.13.0", "--model-repo", str(self.model_repo))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(tree_snapshot(self.model_repo), before_model)
        self.assertFalse((self.model_repo / "validator-wrote-here.txt").exists())

    def test_credentialed_remote_is_sanitized_in_lock(self):
        credentialed = f"file://x-token@localhost{self.remote}"
        (self.workspace / "PACKAGE_VERSION.lock").write_text(
            json.dumps(
                {
                    "current_version": "0.9.0",
                    "tag": "v0.9.0",
                    "commit": self.shas["v0.9.0"],
                    "installed_at": "2026-07-06T00:00:00Z",
                    "previous_version": None,
                    "previous_commit": None,
                    "remote_url": credentialed,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = self.run_apply("--to", "v0.14.0")

        self.assertEqual(result.returncode, 0, result.stderr)
        text = (self.workspace / "PACKAGE_VERSION.lock").read_text(encoding="utf-8")
        report_text = (self.workspace / "PACKAGE_INSTALL_REPORT.json").read_text(encoding="utf-8")
        self.assertNotIn("x-token", text)
        self.assertNotIn("x-token", report_text)
        self.assertEqual(load_lock(self.workspace / "PACKAGE_VERSION.lock")["remote_url"], f"file://localhost{self.remote}")
        self.assertEqual(
            load_lock(self.workspace / "PACKAGE_INSTALL_REPORT.json")["source_url"],
            f"file://localhost{self.remote}",
        )

    def test_dry_run_writes_nothing(self):
        before = tree_snapshot(self.install)
        result = self.run_apply("--to", "v0.10.0", "--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(tree_snapshot(self.install), before)
        self.assertIn("dry-run", result.stdout)


if __name__ == "__main__":
    unittest.main()

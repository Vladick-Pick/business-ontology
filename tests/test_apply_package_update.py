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

    def test_apply_flips_current_and_updates_lock(self):
        result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.readlink(self.package / "current"), "releases/v0.14.0")
        lock = load_lock(self.workspace / "PACKAGE_VERSION.lock")
        self.assertEqual(lock["tag"], "v0.14.0")
        self.assertEqual(lock["commit"], self.shas["v0.14.0"])
        self.assertEqual(lock["previous_version"], "0.9.0")
        self.assertEqual(lock["previous_commit"], self.shas["v0.9.0"])

    def test_apply_does_not_change_workspace_except_lock(self):
        before = tree_snapshot(self.workspace)
        result = self.run_apply("--to", "v0.14.0", "--model-repo", str(self.model_repo))
        after = tree_snapshot(self.workspace)

        self.assertEqual(result.returncode, 0, result.stderr)
        before.pop("PACKAGE_VERSION.lock")
        after.pop("PACKAGE_VERSION.lock")
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

    def test_lock_consistent_after_apply_and_rollback(self):
        self.assertEqual(self.run_apply("--to", "v0.14.0").returncode, 0)
        lock = load_lock(self.workspace / "PACKAGE_VERSION.lock")
        self.assertEqual(run_git(self.package / "releases" / lock["tag"], "rev-parse", "HEAD"), lock["commit"])

        self.assertEqual(self.run_apply("--rollback").returncode, 0)
        lock = load_lock(self.workspace / "PACKAGE_VERSION.lock")
        self.assertEqual(run_git(self.package / "releases" / lock["tag"], "rev-parse", "HEAD"), lock["commit"])

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
        self.assertNotIn("x-token", text)
        self.assertEqual(load_lock(self.workspace / "PACKAGE_VERSION.lock")["remote_url"], f"file://localhost{self.remote}")

    def test_dry_run_writes_nothing(self):
        before = tree_snapshot(self.install)
        result = self.run_apply("--to", "v0.10.0", "--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(tree_snapshot(self.install), before)
        self.assertIn("dry-run", result.stdout)


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_package_updates.py"


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


def write_lock(path: Path, *, current_version: str, tag: str, commit_sha: str, remote_url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "current_version": current_version,
                "tag": tag,
                "commit": commit_sha,
                "installed_at": "2026-07-06T00:00:00Z",
                "previous_version": None,
                "previous_commit": None,
                "remote_url": remote_url,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


class CheckPackageUpdatesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.remote = self.root / "remote"
        run_git(Path(self.tmp.name), "init", str(self.remote))
        run_git(self.remote, "config", "user.email", "agent@example.com")
        run_git(self.remote, "config", "user.name", "Agent")

        (self.remote / "CHANGELOG.md").write_text(
            "# Changelog\n\n## 0.9.0 - Base\n\n- Base release.\n",
            encoding="utf-8",
        )
        self.v09_sha = commit(self.remote, "release 0.9.0")
        run_git(self.remote, "tag", "v0.9.0")

        (self.remote / "CHANGELOG.md").write_text(
            "# Changelog\n\n## 0.10.0 - Gate\n\n- Warnings become errors.\n\n## 0.9.0 - Base\n\n- Base release.\n",
            encoding="utf-8",
        )
        self.v10_sha = commit(self.remote, "release 0.10.0")
        run_git(self.remote, "tag", "v0.10.0")
        run_git(self.remote, "tag", "draft")

        self.install_root = self.root / "install"
        self.lock_path = self.install_root / "workspace" / "PACKAGE_VERSION.lock"

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--lock", str(self.lock_path), *extra],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_reports_newer_semver_release_with_changelog_section(self):
        write_lock(
            self.lock_path,
            current_version="0.9.0",
            tag="v0.9.0",
            commit_sha=self.v09_sha,
            remote_url=str(self.remote),
        )

        result = self.run_script()

        self.assertEqual(result.returncode, 10, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["current"], "v0.9.0")
        self.assertEqual(payload["latest"], "v0.10.0")
        self.assertEqual(payload["newer"], ["v0.10.0"])
        self.assertIn("Warnings become errors", payload["changelog_excerpt"])

    def test_returns_zero_when_lock_is_current(self):
        write_lock(
            self.lock_path,
            current_version="0.10.0",
            tag="v0.10.0",
            commit_sha=self.v10_sha,
            remote_url=str(self.remote),
        )

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["newer"])
        self.assertEqual(payload["latest"], "v0.10.0")

    def test_redacts_credentialed_remote_in_stdout(self):
        credentialed = f"file://x-token@localhost{self.remote}"
        write_lock(
            self.lock_path,
            current_version="0.9.0",
            tag="v0.9.0",
            commit_sha=self.v09_sha,
            remote_url=credentialed,
        )

        result = self.run_script()

        self.assertEqual(result.returncode, 10, result.stderr)
        self.assertNotIn("x-token", result.stdout)
        self.assertNotIn("x-token", result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["remote"], f"file://localhost{self.remote}")

    def test_live_update_lock_causes_exit_5_without_creating_cache(self):
        write_lock(
            self.lock_path,
            current_version="0.9.0",
            tag="v0.9.0",
            commit_sha=self.v09_sha,
            remote_url=str(self.remote),
        )
        lock = self.install_root / "package" / ".update.lock"
        lock.parent.mkdir(parents=True)
        lock.write_text(json.dumps({"pid": 1, "timestamp": "2026-07-06T00:00:00Z"}), encoding="utf-8")

        result = self.run_script()

        self.assertEqual(result.returncode, 5)
        self.assertFalse((self.install_root / "package" / ".cache.git").exists())


if __name__ == "__main__":
    unittest.main()

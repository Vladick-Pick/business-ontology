import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_REPO_TEMPLATE = REPO_ROOT / "templates" / "model-repo"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def render_lock(version: str, commit: str) -> str:
    text = (MODEL_REPO_TEMPLATE / "PACKAGE_CONTRACT.lock.tpl").read_text(encoding="utf-8")
    return text.replace("{{PACKAGE_VERSION}}", version).replace("{{PACKAGE_COMMIT}}", commit) + "\n"


class ModelRepoContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.model = self.root / "model-repo"
        self.package = self.root / "package" / "current"
        self.commit = "abc123"
        self.create_model_repo(version="0.10.0", commit=self.commit)
        self.create_package(version="0.10.0", commit=self.commit)

    def tearDown(self):
        self.tmp.cleanup()

    def create_model_repo(self, *, version: str, commit: str) -> None:
        write(self.model / "PACKAGE_CONTRACT.lock", render_lock(version, commit))
        wrapper = (MODEL_REPO_TEMPLATE / "scripts" / "validate_model_repo.py.tpl").read_text(encoding="utf-8")
        write(self.model / "scripts" / "validate_model_repo.py", wrapper)

    def create_package(self, *, version: str, commit: str) -> None:
        write(self.package / "VERSION.txt", version)
        write(
            self.package / ".package-release.json",
            json.dumps({"commit": commit, "tag": f"v{version}"}, indent=2, sort_keys=True) + "\n",
        )
        write(
            self.package / "scripts" / "links_validate.py",
            (
                "#!/usr/bin/env python3\n"
                "import json\n"
                "from pathlib import Path\n"
                "import sys\n"
                "Path(__file__).resolve().parents[1].joinpath('validator-call.json').write_text(\n"
                "    json.dumps(sys.argv[1:], indent=2, sort_keys=True) + '\\n', encoding='utf-8'\n"
                ")\n"
                "sys.exit(0)\n"
            ),
        )

    def run_wrapper(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(self.model / "scripts" / "validate_model_repo.py"),
                "--package",
                str(self.package),
                *args,
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_matching_contract_invokes_package_validator_with_strict_gate(self):
        result = self.run_wrapper("--staged")

        self.assertEqual(result.returncode, 0, result.stderr)
        call = json.loads((self.package / "validator-call.json").read_text(encoding="utf-8"))
        self.assertEqual(call[0], str(self.model.resolve()))
        self.assertIn("--staged", call)
        self.assertIn("--strict-transitional", call)

    def test_package_version_can_come_from_agent_package_manifest(self):
        (self.package / "VERSION.txt").unlink()
        write(self.package / "agent-package.yaml", 'name: business-ontology\nversion: "0.10.0"\n')

        result = self.run_wrapper()

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_package_fails_actionably(self):
        self.package.rename(self.root / "missing-package")

        result = self.run_wrapper()

        self.assertEqual(result.returncode, 2)
        self.assertIn("package version not found", result.stderr)

    def test_mismatched_package_commit_fails_actionably(self):
        write(self.model / "PACKAGE_CONTRACT.lock", render_lock("0.10.0", "different"))

        result = self.run_wrapper()

        self.assertEqual(result.returncode, 2)
        self.assertIn("package_commit mismatch", result.stderr)

    def test_validator_path_override_is_rejected(self):
        lock = json.loads(render_lock("0.10.0", self.commit))
        lock["validator"] = "../../evil.py"
        write(self.model / "PACKAGE_CONTRACT.lock", json.dumps(lock, indent=2, sort_keys=True) + "\n")

        result = self.run_wrapper()

        self.assertEqual(result.returncode, 2)
        self.assertIn("validator must be scripts/links_validate.py", result.stderr)

    def test_stale_copied_validator_is_rejected(self):
        write(self.model / "scripts" / "links_validate.py", "# stale copied validator\n")

        result = self.run_wrapper()

        self.assertEqual(result.returncode, 2)
        self.assertIn("unsupported", result.stderr)


if __name__ == "__main__":
    unittest.main()

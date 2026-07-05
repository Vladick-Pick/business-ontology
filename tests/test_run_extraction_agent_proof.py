import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest

from tests.test_run_extraction_benchmark import file_hash, model_change_package, source_event, write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
PROOF = REPO_ROOT / "scripts" / "run_extraction_agent_proof.py"


def load_proof():
    spec = importlib.util.spec_from_file_location("run_extraction_agent_proof", PROOF)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class RunExtractionAgentProofTests(unittest.TestCase):
    def test_runs_agent_command_and_scores_manifested_packages(self):
        proof = load_proof()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case_dir = root / "golden" / "state-drift"
            event = source_event()
            write_json(case_dir / "source-event.json", event)
            write_json(case_dir / "accepted-context" / "context.json", {"moduleId": "acquisition"})
            write_json(
                case_dir / "expected-changes.json",
                [
                    {
                        "kind": "new-object",
                        "affectedIds": ["lead-lifecycle"],
                        "proposedAction": "prepare-staged-proposal",
                        "matchKey": "kind+affectedIds",
                    }
                ],
            )
            fake_agent = root / "fake_agent.py"
            fake_agent.write_text(
                textwrap.dedent(
                    """
                    import json
                    import os
                    from pathlib import Path
                    from tests.test_run_extraction_benchmark import model_change_package

                    source_event = json.loads(Path(os.environ["BO_SOURCE_EVENT"]).read_text(encoding="utf-8"))
                    output_dir = Path(os.environ["BO_OUTPUT_DIR"])
                    output_dir.mkdir(parents=True, exist_ok=True)
                    package = model_change_package(event_id=source_event["eventId"])
                    (output_dir / "mcpkg-agent.json").write_text(json.dumps(package, indent=2), encoding="utf-8")
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = proof.run_agent_proof(
                root / "golden",
                root / "packages",
                agent_command=[sys.executable, str(fake_agent)],
                agent="fake-agent",
                cli="unit-test",
                model="fake-model",
                prompt_hash="sha256:" + "c" * 64,
                min_f1=0.8,
            )

            self.assertEqual(result.returncode, 0, result.errors)
            manifest = read_json(root / "packages" / "run_manifest.json")
            self.assertEqual(manifest["agent"], "fake-agent")
            self.assertEqual(manifest["cases"][0]["case_id"], "state-drift")
            self.assertEqual(manifest["cases"][0]["source_event_hash"], file_hash(case_dir / "source-event.json"))
            self.assertEqual(manifest["cases"][0]["package_path"], "state-drift/mcpkg-agent.json")
            scorecard = read_json(root / "packages" / "scorecard.json")
            self.assertTrue(scorecard["passed"], scorecard["errors"])

    def test_stale_package_cannot_satisfy_agent_proof(self):
        proof = load_proof()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case_dir = root / "golden" / "state-drift"
            event = source_event()
            write_json(case_dir / "source-event.json", event)
            write_json(case_dir / "accepted-context" / "context.json", {"moduleId": "acquisition"})
            write_json(
                case_dir / "expected-changes.json",
                [
                    {
                        "kind": "new-object",
                        "affectedIds": ["lead-lifecycle"],
                        "proposedAction": "prepare-staged-proposal",
                        "matchKey": "kind+affectedIds",
                    }
                ],
            )
            stale_package = root / "packages" / "state-drift" / "mcpkg-agent.json"
            write_json(stale_package, model_change_package(event_id=event["eventId"]))
            noop_agent = root / "noop_agent.py"
            noop_agent.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

            result = proof.run_agent_proof(
                root / "golden",
                root / "packages",
                agent_command=[sys.executable, str(noop_agent)],
                agent="noop-agent",
                cli="unit-test",
                model="fake-model",
                prompt_hash="sha256:" + "d" * 64,
                min_f1=0.8,
            )

            self.assertEqual(result.returncode, 1)
            self.assertFalse(stale_package.exists())
            self.assertTrue(any("expected exactly one package JSON; found 0" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()

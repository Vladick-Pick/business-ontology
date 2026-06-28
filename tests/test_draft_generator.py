import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PACK_PATH = REPO_ROOT / "examples" / "model-packs" / "acquisition.model-pack.json"
SOURCE_EVENT_DIR = REPO_ROOT / "evals" / "fixtures" / "source-events"
CLI_PATH = REPO_ROOT / "scripts" / "generate_draft_ontology.py"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class DraftGeneratorTests(unittest.TestCase):
    def setUp(self):
        from runtime.draft_generator import generate_draft_ontology

        self.generate_draft_ontology = generate_draft_ontology
        self.model_pack = load_json(MODEL_PACK_PATH)
        self.context = {
            "ontologyRevision": "git:test",
            "generatedAt": "2026-06-29T00:00:00Z",
        }

    def source_event(self, filename):
        return load_json(SOURCE_EVENT_DIR / filename)

    def test_generates_packages_and_binding_suggestions(self):
        draft = self.generate_draft_ontology(
            model_pack=self.model_pack,
            source_events=[
                self.source_event("telegram-export.synthetic.json"),
                self.source_event("crm-export.synthetic.json"),
            ],
            accepted_context=self.context,
        )

        self.assertEqual(draft["kind"], "draftOntology")
        self.assertEqual(draft["status"], "drafted")
        self.assertEqual(draft["summary"]["packageCount"], 2)
        self.assertGreaterEqual(draft["summary"]["bindingSuggestionCount"], 1)
        self.assertTrue(draft["safety"]["noAcceptedMutation"])
        self.assertTrue(all(change["candidateCard"]["status"] != "accepted"
                            for package in draft["packages"]
                            for change in package["changes"]
                            if "candidateCard" in change))

    def test_unsafe_source_event_is_reported_as_refusal(self):
        unsafe = self.source_event("telegram-export.synthetic.json")
        unsafe["redaction"] = {**unsafe["redaction"], "rawPayloadIncluded": True}

        draft = self.generate_draft_ontology(
            model_pack=self.model_pack,
            source_events=[unsafe],
            accepted_context=self.context,
        )

        self.assertEqual(draft["status"], "refused")
        self.assertEqual(draft["summary"]["refusalCount"], 1)
        self.assertIn("raw payload", draft["refusals"][0]["reason"])
        self.assertEqual(draft["packages"], [])

    def test_cli_writes_draft_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "draft.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "--model-pack",
                    str(MODEL_PACK_PATH),
                    "--source-event",
                    str(SOURCE_EVENT_DIR / "telegram-export.synthetic.json"),
                    "--out",
                    str(out_path),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            draft = load_json(out_path)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(draft["kind"], "draftOntology")
        self.assertEqual(draft["summary"]["packageCount"], 1)


if __name__ == "__main__":
    unittest.main()

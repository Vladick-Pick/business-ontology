import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PACK_PATH = REPO_ROOT / "examples" / "model-packs" / "acquisition.model-pack.json"
SOURCE_EVENT_DIR = REPO_ROOT / "evals" / "fixtures" / "source-events"
SCHEMA_PATH = REPO_ROOT / "schemas" / "model-change-package.schema.json"
CLI_PATH = REPO_ROOT / "scripts" / "compile_model_change.py"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class ModelCompilerTests(unittest.TestCase):
    def setUp(self):
        from runtime.model_compiler import CompilerRefusal, compile_model_change

        self.CompilerRefusal = CompilerRefusal
        self.compile_model_change = compile_model_change
        self.model_pack = load_json(MODEL_PACK_PATH)
        self.context = {
            "ontologyRevision": "git:test",
            "generatedAt": "2026-06-22T00:00:00Z",
        }

    def source_event(self, filename):
        return load_json(SOURCE_EVENT_DIR / filename)

    def compile(self, filename, context=None):
        return self.compile_model_change(
            model_pack=self.model_pack,
            source_event=self.source_event(filename),
            accepted_context=context if context is not None else self.context,
        )

    def test_transcript_handoff_produces_reviewable_agreement(self):
        package = self.compile("telegram-export.synthetic.json")
        change = package["changes"][0]

        self.assertEqual(change["kind"], "new-agreement")
        self.assertEqual(change["proposedAction"], "prepare-staged-proposal")
        self.assertEqual(change["candidateCard"]["type"], "interface")
        self.assertEqual(change["candidateCard"]["status"], "hypothesis")
        self.assertEqual(package["review"]["overallAction"], "human-review")
        self.assertIs(package["safety"]["noAcceptedMutation"], True)

    def test_dashboard_snapshot_produces_metric_concern(self):
        package = self.compile("dashboard-snapshot.synthetic.json")
        change = package["changes"][0]

        self.assertEqual(change["kind"], "dashboard-metric-concern")
        self.assertEqual(change["risk"], "high")
        self.assertEqual(change["proposedAction"], "review-dashboard-metric")
        self.assertEqual(package["review"]["owner"], "role:analytics-owner")
        self.assertIn("drift", change)

    def test_duplicate_source_event_produces_noop(self):
        source = self.source_event("meeting-transcript.synthetic.json")
        context = {
            **self.context,
            "processedEventIds": [source["eventId"]],
        }
        package = self.compile("meeting-transcript.synthetic.json", context=context)
        change = package["changes"][0]

        self.assertEqual(change["kind"], "no-op")
        self.assertEqual(change["proposedAction"], "record-no-op")
        self.assertEqual(package["review"]["overallAction"], "no-review-needed")

    def test_processed_source_hash_produces_noop(self):
        source = self.source_event("dashboard-snapshot.synthetic.json")
        context = {
            **self.context,
            "processedHashes": [source["hash"]],
        }
        package = self.compile("dashboard-snapshot.synthetic.json", context=context)

        self.assertEqual(package["changes"][0]["kind"], "no-op")
        self.assertEqual(package["changes"][0]["proposedAction"], "record-no-op")

    def test_conflict_trust_floor_is_not_flattened_to_candidate(self):
        source = self.source_event("crm-export.synthetic.json")
        source["trustFloor"] = "conflict"
        pack = {
            **self.model_pack,
            "sourceAuthority": [
                {
                    **rule,
                    "maxStatus": "conflict" if rule["sourceKind"] == "crm-export" else rule["maxStatus"],
                }
                for rule in self.model_pack["sourceAuthority"]
            ],
        }
        package = self.compile_model_change(
            model_pack=pack,
            source_event=source,
            accepted_context=self.context,
        )

        self.assertEqual(package["changes"][0]["candidateCard"]["status"], "conflict")

    def test_zoom_transcript_handoff_variant_stays_hypothesis(self):
        source = self.source_event("meeting-transcript.synthetic.json")
        source["contentSummary"] = (
            "A redacted meeting summary suggests a handoff interface where "
            "acquisition operations supplies qualification notes to sales operations."
        )

        package = self.compile_model_change(
            model_pack=self.model_pack,
            source_event=source,
            accepted_context=self.context,
        )

        self.assertEqual(package["changes"][0]["kind"], "new-agreement")
        self.assertEqual(package["changes"][0]["candidateCard"]["status"], "hypothesis")

    def test_unsafe_source_event_is_refused(self):
        source = self.source_event("telegram-export.synthetic.json")
        source["redaction"] = {
            **source["redaction"],
            "rawPayloadIncluded": True,
        }

        with self.assertRaises(self.CompilerRefusal):
            self.compile_model_change(
                model_pack=self.model_pack,
                source_event=source,
                accepted_context=self.context,
            )

    def test_source_event_with_pii_like_text_is_refused(self):
        source = self.source_event("telegram-export.synthetic.json")
        source["contentSummary"] = "A redacted chat mentions alice@example.com in the summary."

        with self.assertRaises(self.CompilerRefusal):
            self.compile_model_change(
                model_pack=self.model_pack,
                source_event=source,
                accepted_context=self.context,
            )

    def test_output_has_required_model_change_package_fields(self):
        schema = load_json(SCHEMA_PATH)
        package = self.compile("crm-export.synthetic.json")

        self.assertEqual(set(schema["required"]) - set(package), set())
        self.assertEqual(package["modelPackId"], self.model_pack["modelPackId"])
        self.assertEqual(package["modelPackVersion"], self.model_pack["version"])
        self.assertEqual(package["ontologyRevision"], "git:test")
        self.assertEqual(package["compiler"]["name"], "reference-model-compiler")
        self.assertTrue(package["sourceEventIds"])
        self.assertTrue(package["changes"])

    def test_cli_writes_stdout_and_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "package.json"
            stdout_result = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "--model-pack",
                    str(MODEL_PACK_PATH),
                    "--source-event",
                    str(SOURCE_EVENT_DIR / "dashboard-snapshot.synthetic.json"),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            file_result = subprocess.run(
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

            stdout_payload = json.loads(stdout_result.stdout)
            file_payload = load_json(out_path)

        self.assertEqual(stdout_result.returncode, 0, stdout_result.stderr)
        self.assertEqual(file_result.returncode, 0, file_result.stderr)
        self.assertEqual(stdout_payload["changes"][0]["kind"], "dashboard-metric-concern")
        self.assertEqual(file_payload["changes"][0]["kind"], "new-agreement")

    def test_cli_refuses_unsafe_event_without_writing_out_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = self.source_event("dashboard-snapshot.synthetic.json")
            source["evidence"][0]["excerpt"] = "Metric owner alice@example.com reported a mismatch."
            source_path = tmp_path / "unsafe-source.json"
            out_path = tmp_path / "package.json"
            source_path.write_text(json.dumps(source), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "--model-pack",
                    str(MODEL_PACK_PATH),
                    "--source-event",
                    str(source_path),
                    "--out",
                    str(out_path),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            out_exists = out_path.exists()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused:", result.stderr)
        self.assertFalse(out_exists)


if __name__ == "__main__":
    unittest.main()

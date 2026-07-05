import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from hashlib import sha256


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = REPO_ROOT / "scripts" / "run_extraction_benchmark.py"


def load_benchmark():
    spec = importlib.util.spec_from_file_location("run_extraction_benchmark", BENCHMARK)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def file_hash(path):
    return "sha256:" + sha256(path.read_bytes()).hexdigest()


def source_event(event_id="srcevt-golden-001", excerpt="Partner review appears before sales handoff."):
    return {
        "eventId": event_id,
        "sourceId": "src-golden",
        "sourceKind": "telegram-export",
        "observedAt": "2026-07-05T10:00:00Z",
        "connector": {
            "name": "golden-fixture",
            "version": "test",
            "mode": "manual-export",
            "readOnly": True,
        },
        "authority": {
            "owner": "role:channel-owner",
            "accessMode": "manual-drop",
            "registered": False,
        },
        "trustFloor": "hypothesis",
        "claimKind": "owner-claim",
        "evidenceGrade": "claim",
        "sourceRisk": ["manual-memory"],
        "provenanceActivity": {
            "activityType": "manual-export",
            "actor": "golden-fixture",
            "actorType": "connector",
            "createdAt": "2026-07-05T10:00:00Z",
            "sourceLocator": "telegram:golden#msg-1",
            "method": "Synthetic benchmark fixture.",
        },
        "redaction": {
            "piiExcluded": True,
            "rawPayloadIncluded": False,
            "redactionNotes": "Synthetic fixture.",
        },
        "evidence": [
            {
                "locator": "telegram:golden#msg-1",
                "segmentType": "line-range",
                "start": "1",
                "end": "1",
                "excerpt": excerpt,
                "notes": "Benchmark evidence.",
            }
        ],
        "contentSummary": f"A source event says: {excerpt}",
        "hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    }


def model_change_package(
    *,
    package_id="mcpkg-golden-001",
    event_id="srcevt-golden-001",
    kind="new-object",
    affected_ids=None,
    proposed_action="prepare-staged-proposal",
    excerpt="Partner review appears before sales handoff.",
):
    if affected_ids is None:
        affected_ids = ["lead-lifecycle"]
    return {
        "packageId": package_id,
        "moduleId": "acquisition",
        "modelPackId": "mp-acquisition-reference",
        "modelPackVersion": "2026.06",
        "ontologyRevision": "git:test",
        "compiler": {
            "name": "agent-under-test",
            "version": "test",
            "mode": "manual-review",
        },
        "sourceEventIds": [event_id],
        "generatedAt": "2026-07-05T10:01:00Z",
        "summary": "Synthetic benchmark package.",
        "changes": [
            {
                "changeId": "chg-golden-001",
                "kind": kind,
                "confidence": "medium",
                "risk": "medium",
                "claimKind": "owner-claim",
                "evidenceGrade": "claim",
                "sourceRisk": ["manual-memory"],
                "affectedIds": affected_ids,
                "evidence": [
                    {
                        "sourceEventId": event_id,
                        "locator": "telegram:golden#msg-1",
                        "excerpt": excerpt,
                    }
                ],
                "proposedAction": proposed_action,
            }
        ],
        "review": {
            "overallAction": "human-review"
            if proposed_action != "record-no-op"
            else "no-review-needed",
            "owner": "role:ontology-reviewer",
            "reason": "Synthetic benchmark package.",
        },
        "safety": {
            "noPii": True,
            "noSecrets": True,
            "noRawPayload": True,
            "noAcceptedMutation": True,
        },
    }


def write_golden_case(root, case_id, expected_changes, event=None):
    case_dir = root / "golden" / case_id
    event = event or source_event()
    write_json(case_dir / "source-event.json", event)
    write_json(case_dir / "expected-changes.json", expected_changes)
    return case_dir / "source-event.json"


def write_run(root, case_id, event_path, package):
    packages_dir = root / "packages"
    package_path = packages_dir / case_id / f"{package['packageId']}.json"
    write_json(package_path, package)
    write_json(
        packages_dir / "run_manifest.json",
        {
            "agent": "codex-test",
            "cli": "unit-test",
            "model": "test-model",
            "model_version": "test",
            "prompt_hash": "sha256:" + "a" * 64,
            "started_at": "2026-07-05T10:00:00Z",
            "finished_at": "2026-07-05T10:01:00Z",
            "cases": [
                {
                    "case_id": case_id,
                    "source_event_hash": file_hash(event_path),
                    "package_path": f"{case_id}/{package['packageId']}.json",
                }
            ],
        },
    )
    return packages_dir


class RunExtractionBenchmarkTests(unittest.TestCase):
    def test_ideal_package_scores_one_and_writes_manifest_to_scorecard(self):
        benchmark = load_benchmark()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event_path = write_golden_case(
                root,
                "state-drift",
                [
                    {
                        "kind": "new-object",
                        "affectedIds": ["lead-lifecycle"],
                        "proposedAction": "prepare-staged-proposal",
                        "matchKey": "kind+affectedIds",
                    }
                ],
            )
            packages = write_run(root, "state-drift", event_path, model_change_package())

            result = benchmark.run_benchmark(root / "golden", packages, min_f1=0.8)

            self.assertTrue(result.passed, result.errors)
            self.assertEqual(result.metrics["total"]["f1"], 1.0)
            scorecard = json.loads((packages / "scorecard.json").read_text(encoding="utf-8"))
            self.assertEqual(scorecard["manifest"]["agent"], "codex-test")
            self.assertEqual(scorecard["metrics"]["total"]["f1"], 1.0)

    def test_missing_expected_change_drops_recall_below_threshold(self):
        benchmark = load_benchmark()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event_path = write_golden_case(
                root,
                "missing-change",
                [
                    {
                        "kind": "new-object",
                        "affectedIds": ["lead-lifecycle"],
                        "matchKey": "kind+affectedIds",
                    }
                ],
            )
            package = model_change_package(kind="no-op", affected_ids=[], proposed_action="record-no-op")
            packages = write_run(root, "missing-change", event_path, package)

            result = benchmark.run_benchmark(root / "golden", packages, min_f1=0.8)

            self.assertFalse(result.passed)
            self.assertLess(result.metrics["total"]["recall"], 1.0)
            self.assertTrue(any("below threshold" in error for error in result.errors))

    def test_extra_change_drops_precision_below_perfect(self):
        benchmark = load_benchmark()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event_path = write_golden_case(
                root,
                "extra-change",
                [
                    {
                        "kind": "new-object",
                        "affectedIds": ["lead-lifecycle"],
                        "matchKey": "kind+affectedIds",
                    }
                ],
            )
            package = model_change_package()
            package["changes"].append(
                {
                    **package["changes"][0],
                    "changeId": "chg-extra-001",
                    "kind": "drift",
                    "affectedIds": ["lead-quality"],
                    "proposedAction": "open-drift-review",
                }
            )
            packages = write_run(root, "extra-change", event_path, package)

            result = benchmark.run_benchmark(root / "golden", packages, min_f1=0.0)

            self.assertTrue(result.passed, result.errors)
            self.assertLess(result.metrics["total"]["precision"], 1.0)

    def test_evidence_excerpt_must_appear_in_source_event(self):
        benchmark = load_benchmark()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event_path = write_golden_case(
                root,
                "bad-evidence",
                [
                    {
                        "kind": "new-object",
                        "affectedIds": ["lead-lifecycle"],
                        "matchKey": "kind+affectedIds",
                    }
                ],
            )
            package = model_change_package(excerpt="This sentence is invented by the agent.")
            packages = write_run(root, "bad-evidence", event_path, package)

            result = benchmark.run_benchmark(root / "golden", packages, min_f1=0.0)

            self.assertFalse(result.passed)
            self.assertTrue(any("excerpt is not present" in error for error in result.errors))

    def test_prepare_staged_proposal_with_unknown_affected_id_fails(self):
        benchmark = load_benchmark()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event_path = write_golden_case(
                root,
                "unknown-hallucination",
                [
                    {
                        "kind": "new-object",
                        "affectedIds": [],
                        "proposedAction": "needs-info",
                        "matchKey": "kind+affectedIds",
                    }
                ],
            )
            package = model_change_package(affected_ids=["unknown"])
            packages = write_run(root, "unknown-hallucination", event_path, package)

            result = benchmark.run_benchmark(root / "golden", packages, min_f1=0.0)

            self.assertFalse(result.passed)
            self.assertTrue(any("must degrade to needs-info" in error for error in result.errors))

    def test_missing_run_manifest_fails_by_default(self):
        benchmark = load_benchmark()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_golden_case(
                root,
                "no-manifest",
                [
                    {
                        "kind": "new-object",
                        "affectedIds": ["lead-lifecycle"],
                        "matchKey": "kind+affectedIds",
                    }
                ],
            )
            packages = root / "packages"
            write_json(packages / "no-manifest" / "mcpkg-golden-001.json", model_change_package())

            result = benchmark.run_benchmark(root / "golden", packages, min_f1=0.0)

            self.assertFalse(result.passed)
            self.assertTrue(any("run_manifest.json is required" in error for error in result.errors))

    def test_cli_rejects_manifestless_debug_mode(self):
        benchmark = load_benchmark()
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(stderr), self.assertRaises(
            SystemExit
        ) as raised:
            benchmark.main(["--packages", str(Path(tmp) / "packages"), "--allow-no-manifest"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("unrecognized arguments: --allow-no-manifest", stderr.getvalue())

    def test_manifest_source_event_hash_must_match_golden_case(self):
        benchmark = load_benchmark()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event_path = write_golden_case(
                root,
                "bad-hash",
                [
                    {
                        "kind": "new-object",
                        "affectedIds": ["lead-lifecycle"],
                        "matchKey": "kind+affectedIds",
                    }
                ],
            )
            packages = write_run(root, "bad-hash", event_path, model_change_package())
            manifest = json.loads((packages / "run_manifest.json").read_text(encoding="utf-8"))
            manifest["cases"][0]["source_event_hash"] = "sha256:" + "b" * 64
            write_json(packages / "run_manifest.json", manifest)

            result = benchmark.run_benchmark(root / "golden", packages, min_f1=0.0)

            self.assertFalse(result.passed)
            self.assertTrue(any("source_event_hash mismatch" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "run_evals.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("run_evals", RUNNER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_case(root, case):
    path = Path(root) / "case.json"
    path.write_text(json.dumps(case), encoding="utf-8")
    return path


def write_trace(path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )


def trace_event(event_type, name, result, **overrides):
    event = {
        "timestamp": "2026-06-22T10:00:00Z",
        "actor": "agent",
        "event_type": event_type,
        "name": name,
        "scope": "ontology:propose",
        "summary": "Synthetic trace event.",
        "result": result,
    }
    event.update(overrides)
    return event


def valid_model_change_package():
    return {
        "packageId": "mcpkg-test",
        "moduleId": "acquisition",
        "modelPackId": "mp-acquisition-reference",
        "modelPackVersion": "2026.06",
        "ontologyRevision": "git:test",
        "compiler": {
            "name": "reference-model-compiler",
            "version": "0.1",
            "mode": "automated",
        },
        "sourceEventIds": ["srcevt-test"],
        "generatedAt": "2026-06-22T10:00:00Z",
        "summary": "Synthetic package.",
        "changes": [
            {
                "changeId": "chg-test",
                "kind": "dashboard-metric-concern",
                "confidence": "medium",
                "risk": "high",
                "affectedIds": ["lead-quality"],
                "evidence": [
                    {
                        "sourceEventId": "srcevt-test",
                        "locator": "fixture",
                        "excerpt": "Metric convention differs.",
                    }
                ],
                "proposedAction": "review-dashboard-metric",
            }
        ],
        "review": {
            "overallAction": "human-review",
            "owner": "role:analytics-owner",
            "reason": "Synthetic review.",
        },
        "safety": {
            "noPii": True,
            "noSecrets": True,
            "noRawPayload": True,
            "noAcceptedMutation": True,
        },
    }


class RunEvalsTests(unittest.TestCase):
    def test_passing_case(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "pass"
            fixture.mkdir(parents=True)
            (fixture / "artifact.md").write_text("expected output\n", encoding="utf-8")
            case_path = write_case(
                root,
                {
                    "id": "passing-case",
                    "skill": "fixture",
                    "scenario": "Happy path.",
                    "input_fixture": "fixtures/pass",
                    "expected_artifacts": ["artifact.md"],
                    "checks": [
                        {"type": "contains", "path": "artifact.md", "text": "expected"}
                    ],
                    "risk_invariant": "The runner can pass a valid case.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertTrue(result.passed, result.failed_checks)
        self.assertEqual(result.passed_checks, 1)

    def test_missing_fixture_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case_path = write_case(
                root,
                {
                    "id": "missing-fixture",
                    "skill": "fixture",
                    "scenario": "Missing input fixture.",
                    "input_fixture": "fixtures/missing",
                    "expected_artifacts": [],
                    "checks": [],
                    "risk_invariant": "Fixture roots must exist.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("input fixture does not exist" in e for e in result.failed_checks))

    def test_required_substring_absent_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "absent"
            fixture.mkdir(parents=True)
            (fixture / "artifact.md").write_text("actual output\n", encoding="utf-8")
            case_path = write_case(
                root,
                {
                    "id": "substring-absent",
                    "skill": "fixture",
                    "scenario": "Required substring missing.",
                    "input_fixture": "fixtures/absent",
                    "expected_artifacts": ["artifact.md"],
                    "checks": [
                        {"type": "contains", "path": "artifact.md", "text": "required"}
                    ],
                    "risk_invariant": "Required substrings are enforced.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("required substring missing" in e for e in result.failed_checks))

    def test_forbidden_substring_present_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "forbidden"
            fixture.mkdir(parents=True)
            (fixture / "artifact.md").write_text("bad output\n", encoding="utf-8")
            case_path = write_case(
                root,
                {
                    "id": "forbidden-present",
                    "skill": "fixture",
                    "scenario": "Forbidden substring present.",
                    "input_fixture": "fixtures/forbidden",
                    "expected_artifacts": ["artifact.md"],
                    "checks": [
                        {"type": "not_contains", "path": "artifact.md", "text": "bad"}
                    ],
                    "risk_invariant": "Forbidden substrings are enforced.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("forbidden substring found" in e for e in result.failed_checks))

    def test_validator_expected_failure_case_passes(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "invalid-ontology"
            fixture.mkdir(parents=True)
            (fixture / "card.md").write_text(
                """---
id: c-invalid
type: concept
source: fixture
owner: tester
last-reviewed: 2026-06-22
next-audit: 2026-09-22
---

# Invalid card
""",
                encoding="utf-8",
            )
            case_path = write_case(
                root,
                {
                    "id": "validator-expected-failure",
                    "skill": "fixture",
                    "scenario": "Validator should fail and the case expects failure.",
                    "input_fixture": "fixtures/invalid-ontology",
                    "expected_artifacts": ["card.md"],
                    "checks": [{"type": "validator", "path": ".", "expect": "fail"}],
                    "risk_invariant": "Expected validator failures are testable.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertTrue(result.passed, result.failed_checks)
        self.assertEqual(result.passed_checks, 1)

    def test_model_change_package_check_passes(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "model-package"
            fixture.mkdir(parents=True)
            (fixture / "package.json").write_text(
                json.dumps(
                    {
                        "packageId": "mcpkg-test",
                        "moduleId": "acquisition",
                        "modelPackId": "mp-acquisition-reference",
                        "modelPackVersion": "2026.06",
                        "ontologyRevision": "git:test",
                        "compiler": {
                            "name": "reference-model-compiler",
                            "version": "0.1",
                            "mode": "automated",
                        },
                        "sourceEventIds": ["srcevt-test"],
                        "generatedAt": "2026-06-22T10:00:00Z",
                        "summary": "Synthetic package.",
                        "changes": [
                            {
                                "changeId": "chg-test",
                                "kind": "dashboard-metric-concern",
                                "confidence": "medium",
                                "risk": "high",
                                "affectedIds": ["lead-quality"],
                                "evidence": [
                                    {
                                        "sourceEventId": "srcevt-test",
                                        "locator": "fixture",
                                        "excerpt": "Metric convention differs.",
                                    }
                                ],
                                "proposedAction": "review-dashboard-metric",
                            }
                        ],
                        "review": {
                            "overallAction": "human-review",
                            "owner": "role:analytics-owner",
                            "reason": "Synthetic review.",
                        },
                        "safety": {
                            "noPii": True,
                            "noSecrets": True,
                            "noRawPayload": True,
                            "noAcceptedMutation": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            case_path = write_case(
                root,
                {
                    "id": "model-package-pass",
                    "skill": "fixture",
                    "scenario": "Valid model-change package.",
                    "input_fixture": "fixtures/model-package",
                    "expected_artifacts": ["package.json"],
                    "checks": [
                        {
                            "type": "model_change_package",
                            "path": "package.json",
                            "kind": "dashboard-metric-concern",
                            "proposedAction": "review-dashboard-metric",
                        }
                    ],
                    "risk_invariant": "Package checks accept safe review artifacts.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertTrue(result.passed, result.failed_checks)
        self.assertEqual(result.passed_checks, 1)

    def test_model_change_package_missing_safety_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "unsafe-package"
            fixture.mkdir(parents=True)
            (fixture / "package.json").write_text(
                json.dumps(
                    {
                        "packageId": "mcpkg-test",
                        "moduleId": "acquisition",
                        "modelPackId": "mp-acquisition-reference",
                        "modelPackVersion": "2026.06",
                        "ontologyRevision": "git:test",
                        "compiler": {"name": "reference-model-compiler"},
                        "sourceEventIds": ["srcevt-test"],
                        "generatedAt": "2026-06-22T10:00:00Z",
                        "summary": "Synthetic package.",
                        "changes": [{"kind": "no-op", "proposedAction": "record-no-op"}],
                        "review": {},
                        "safety": {"noPii": True, "noSecrets": True},
                    }
                ),
                encoding="utf-8",
            )
            case_path = write_case(
                root,
                {
                    "id": "model-package-fail",
                    "skill": "fixture",
                    "scenario": "Unsafe model-change package.",
                    "input_fixture": "fixtures/unsafe-package",
                    "expected_artifacts": ["package.json"],
                    "checks": [{"type": "model_change_package", "path": "package.json"}],
                    "risk_invariant": "Package checks fail unsafe review artifacts.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("safety.noRawPayload" in error for error in result.failed_checks))

    def test_model_change_package_extra_payload_field_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "raw-package"
            fixture.mkdir(parents=True)
            package = valid_model_change_package()
            package["rawPayload"] = "not allowed"
            (fixture / "package.json").write_text(json.dumps(package), encoding="utf-8")
            case_path = write_case(
                root,
                {
                    "id": "model-package-extra-payload",
                    "skill": "fixture",
                    "scenario": "Extra raw payload field.",
                    "input_fixture": "fixtures/raw-package",
                    "expected_artifacts": ["package.json"],
                    "checks": [{"type": "model_change_package", "path": "package.json"}],
                    "risk_invariant": "Package checks reject raw payload fields.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("extra package fields: rawPayload" in e for e in result.failed_checks))

    def test_model_change_package_accepted_candidate_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "accepted-candidate"
            fixture.mkdir(parents=True)
            package = valid_model_change_package()
            package["changes"][0]["candidateCard"] = {
                "id": "unsafe-card",
                "type": "concept",
                "status": "accepted",
                "source": "fixture-source",
                "owner": "role:owner",
                "summary": "Unsafe accepted candidate.",
            }
            (fixture / "package.json").write_text(json.dumps(package), encoding="utf-8")
            case_path = write_case(
                root,
                {
                    "id": "model-package-accepted-candidate",
                    "skill": "fixture",
                    "scenario": "Accepted candidate card.",
                    "input_fixture": "fixtures/accepted-candidate",
                    "expected_artifacts": ["package.json"],
                    "checks": [{"type": "model_change_package", "path": "package.json"}],
                    "risk_invariant": "Package checks reject accepted candidate cards.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("claims accepted truth" in e for e in result.failed_checks))

    def test_model_change_package_reviewable_action_needs_review(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "no-review"
            fixture.mkdir(parents=True)
            package = valid_model_change_package()
            package["review"]["overallAction"] = "no-review-needed"
            package["changes"][0]["proposedAction"] = "prepare-staged-proposal"
            (fixture / "package.json").write_text(json.dumps(package), encoding="utf-8")
            case_path = write_case(
                root,
                {
                    "id": "model-package-no-review",
                    "skill": "fixture",
                    "scenario": "Reviewable action marked no-review.",
                    "input_fixture": "fixtures/no-review",
                    "expected_artifacts": ["package.json"],
                    "checks": [{"type": "model_change_package", "path": "package.json"}],
                    "risk_invariant": "Reviewable model-change packages require review.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("requires review" in e for e in result.failed_checks))

    def test_model_change_package_pii_like_text_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "pii-package"
            fixture.mkdir(parents=True)
            package = valid_model_change_package()
            package["changes"][0]["evidence"][0]["excerpt"] = "Owner alice@example.com reported it."
            (fixture / "package.json").write_text(json.dumps(package), encoding="utf-8")
            case_path = write_case(
                root,
                {
                    "id": "model-package-pii",
                    "skill": "fixture",
                    "scenario": "PII-like package text.",
                    "input_fixture": "fixtures/pii-package",
                    "expected_artifacts": ["package.json"],
                    "checks": [{"type": "model_change_package", "path": "package.json"}],
                    "risk_invariant": "Package checks reject PII-like package text.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("possible email address" in e for e in result.failed_checks))

    def test_valid_trace_checks_pass(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "trace-pass"
            fixture.mkdir(parents=True)
            write_trace(
                fixture / "trace" / "events.jsonl",
                [
                    trace_event(
                        "tool_call",
                        "connect-source",
                        "proposed",
                        summary="Registered source entry with read-only policy.",
                    ),
                    trace_event(
                        "tool_call",
                        "mine-materials",
                        "proposed",
                        summary="Distilled structural facts after source registration.",
                    ),
                    trace_event(
                        "validation",
                        "links_validate",
                        "pass",
                        summary="Validator passed before review-ready proposal.",
                    ),
                    trace_event(
                        "artifact_write",
                        "propose_change",
                        "proposal-ready",
                        path="artifacts/ontology/staged/prop-example.md",
                        summary="Proposal staged for human review.",
                    ),
                ],
            )
            case_path = write_case(
                root,
                {
                    "id": "trace-pass",
                    "skill": "fixture",
                    "scenario": "Valid redacted trace.",
                    "input_fixture": "fixtures/trace-pass",
                    "trace_fixture": "trace/events.jsonl",
                    "expected_artifacts": ["trace/events.jsonl"],
                    "checks": [
                        {"type": "trace_source_registered_before_mining"},
                        {"type": "trace_requires_validation_before_proposal_ready"},
                        {"type": "trace_no_accepted_mutation"},
                        {"type": "trace_no_sensitive_content"},
                    ],
                    "risk_invariant": "Trace checks accept a safe proposal sequence.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertTrue(result.passed, result.failed_checks)
        self.assertEqual(result.passed_checks, 4)

    def test_trace_forbidden_tool_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "forbidden-tool"
            fixture.mkdir(parents=True)
            write_trace(
                fixture / "trace" / "events.jsonl",
                [
                    trace_event(
                        "tool_call",
                        "promote_all",
                        "pass",
                        scope="ontology:admin",
                        summary="Forbidden promotion tool ran.",
                    )
                ],
            )
            case_path = write_case(
                root,
                {
                    "id": "forbidden-tool",
                    "skill": "fixture",
                    "scenario": "Forbidden tool was not refused.",
                    "input_fixture": "fixtures/forbidden-tool",
                    "trace_fixture": "trace/events.jsonl",
                    "expected_artifacts": ["trace/events.jsonl"],
                    "checks": [{"type": "trace_no_forbidden_tools"}],
                    "risk_invariant": "Forbidden tools must be absent or refused.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("forbidden tool" in e for e in result.failed_checks))

    def test_trace_accepted_mutation_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "accepted-mutation"
            fixture.mkdir(parents=True)
            write_trace(
                fixture / "trace" / "events.jsonl",
                [
                    trace_event(
                        "artifact_write",
                        "propose_change",
                        "proposed",
                        scope="ontology:accepted",
                        path="concepts/accepted-card.md",
                        summary="Accepted card was edited directly.",
                    )
                ],
            )
            case_path = write_case(
                root,
                {
                    "id": "accepted-mutation",
                    "skill": "fixture",
                    "scenario": "Accepted tree mutation.",
                    "input_fixture": "fixtures/accepted-mutation",
                    "trace_fixture": "trace/events.jsonl",
                    "expected_artifacts": ["trace/events.jsonl"],
                    "checks": [{"type": "trace_no_accepted_mutation"}],
                    "risk_invariant": "Accepted ontology is read-only to the agent.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("forbidden scope" in e for e in result.failed_checks))

    def test_trace_accepted_mutation_under_artifacts_ontology_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "artifact-accepted-mutation"
            fixture.mkdir(parents=True)
            write_trace(
                fixture / "trace" / "events.jsonl",
                [
                    trace_event(
                        "artifact_write",
                        "propose_change",
                        "proposed",
                        path="artifacts/ontology/concepts/accepted-card.md",
                        summary="Accepted ontology card was written outside staged.",
                    )
                ],
            )
            case_path = write_case(
                root,
                {
                    "id": "artifact-accepted-mutation",
                    "skill": "fixture",
                    "scenario": "Accepted ontology mutation under artifacts root.",
                    "input_fixture": "fixtures/artifact-accepted-mutation",
                    "trace_fixture": "trace/events.jsonl",
                    "expected_artifacts": ["trace/events.jsonl"],
                    "checks": [{"type": "trace_no_accepted_mutation"}],
                    "risk_invariant": "Accepted ontology writes must be staged-only.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("outside staged path" in e for e in result.failed_checks))

    def test_trace_promotion_without_human_approval_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "promotion-without-approval"
            fixture.mkdir(parents=True)
            write_trace(
                fixture / "trace" / "events.jsonl",
                [
                    trace_event(
                        "tool_call",
                        "promote",
                        "promoted",
                        scope="ontology:admin",
                        summary="Promotion attempted before a human approval event.",
                    )
                ],
            )
            case_path = write_case(
                root,
                {
                    "id": "promotion-without-approval",
                    "skill": "fixture",
                    "scenario": "Promotion without human approval.",
                    "input_fixture": "fixtures/promotion-without-approval",
                    "trace_fixture": "trace/events.jsonl",
                    "expected_artifacts": ["trace/events.jsonl"],
                    "checks": [{"type": "trace_human_approval_before_promotion"}],
                    "risk_invariant": "Promotion requires human approval first.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("before human approval" in e for e in result.failed_checks))

    def test_trace_sensitive_content_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "sensitive-trace"
            fixture.mkdir(parents=True)
            write_trace(
                fixture / "trace" / "events.jsonl",
                [
                    trace_event(
                        "resource_read",
                        "source_read",
                        "pass",
                        summary="Read private contact jane@example.com from a raw payload.",
                    )
                ],
            )
            case_path = write_case(
                root,
                {
                    "id": "sensitive-trace",
                    "skill": "fixture",
                    "scenario": "Sensitive data in trace.",
                    "input_fixture": "fixtures/sensitive-trace",
                    "trace_fixture": "trace/events.jsonl",
                    "expected_artifacts": ["trace/events.jsonl"],
                    "checks": [{"type": "trace_no_sensitive_content"}],
                    "risk_invariant": "Traces must stay redacted.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("possible email address" in e for e in result.failed_checks))

    def test_trace_nested_raw_payload_field_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "raw-payload-trace"
            fixture.mkdir(parents=True)
            write_trace(
                fixture / "trace" / "events.jsonl",
                [
                    trace_event(
                        "tool_call",
                        "mine-materials",
                        "proposed",
                        arguments={"raw_payload": "[redacted raw export]"},
                        summary="Tool call carried a forbidden raw payload field.",
                    )
                ],
            )
            case_path = write_case(
                root,
                {
                    "id": "raw-payload-trace",
                    "skill": "fixture",
                    "scenario": "Raw payload field in nested trace arguments.",
                    "input_fixture": "fixtures/raw-payload-trace",
                    "trace_fixture": "trace/events.jsonl",
                    "expected_artifacts": ["trace/events.jsonl"],
                    "checks": [{"type": "trace_no_sensitive_content"}],
                    "risk_invariant": "Traces must not contain raw payload fields.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("arguments.raw_payload" in e for e in result.failed_checks))


if __name__ == "__main__":
    unittest.main()

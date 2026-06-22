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


def valid_review_package(status="pending"):
    package = {
        "reviewId": "rev-test",
        "packageId": "mcpkg-test",
        "moduleId": "acquisition",
        "status": status,
        "owner": "role:analytics-owner",
        "risk": "high",
        "summary": "Synthetic review package.",
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
                "highRiskReasons": ["change risk is high"],
            }
        ],
        "requiredActions": [
            {
                "action": "human-review",
                "changeId": "mcpkg-test",
                "reason": "Synthetic owner review.",
            }
        ],
        "decisions": [],
        "audit": [
            {
                "actor": "agent",
                "action": "prepare-review-package",
                "timestamp": "2026-06-22T10:00:00Z",
                "summary": "Prepared synthetic review package.",
                "result": "pending",
            }
        ],
        "safety": {
            "noAcceptedMutation": True,
            "noAutoPromotion": True,
            "noCommit": True,
            "noSourceWriteback": True,
        },
    }
    if status == "staged-proposal-ready":
        package["requiredActions"] = [
            {
                "action": "prepare-staged-proposal",
                "changeId": "mcpkg-test",
                "reason": "Review approved; prepare staged proposal.",
            }
        ]
        package["decisions"] = [
            {
                "decision": "approved",
                "actor": "role:analytics-owner",
                "reason": "Approved for staged proposal.",
                "decidedAt": "2026-06-22T12:00:00Z",
                "resultingStatus": "staged-proposal-ready",
            }
        ]
    return package


def valid_source_event():
    return {
        "eventId": "srcevt-test",
        "sourceId": "src-test",
        "sourceKind": "dashboard-snapshot",
        "observedAt": "2026-06-22T10:00:00Z",
        "connector": {
            "name": "synthetic-dashboard",
            "version": "fixture",
            "mode": "api-read",
            "readOnly": True,
        },
        "authority": {
            "owner": "role:analytics-owner",
            "accessMode": "read-only-api",
            "registered": True,
        },
        "trustFloor": "candidate",
        "redaction": {
            "piiExcluded": True,
            "rawPayloadIncluded": False,
            "redactionNotes": "Synthetic aggregate-only event.",
        },
        "evidence": [
            {
                "locator": "dashboard:acquisition#widget-conversion-rate",
                "segmentType": "widget",
                "excerpt": "Conversion widget excludes one operational class.",
                "notes": "Synthetic metric concern.",
            }
        ],
        "contentSummary": "A synthetic dashboard event suggests a metric concern.",
        "hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
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

    def test_source_event_check_passes(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "source-event"
            fixture.mkdir(parents=True)
            (fixture / "source-event.json").write_text(
                json.dumps(valid_source_event()),
                encoding="utf-8",
            )
            case_path = write_case(
                root,
                {
                    "id": "source-event-pass",
                    "skill": "fixture",
                    "scenario": "Valid redacted source event.",
                    "input_fixture": "fixtures/source-event",
                    "expected_artifacts": ["source-event.json"],
                    "checks": [
                        {
                            "type": "source_event",
                            "path": "source-event.json",
                            "sourceKind": "dashboard-snapshot",
                        }
                    ],
                    "risk_invariant": "Source events are read-only and redacted.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertTrue(result.passed, result.failed_checks)
        self.assertEqual(result.passed_checks, 1)

    def test_source_event_unsafe_redaction_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "unsafe-source-event"
            fixture.mkdir(parents=True)
            event = valid_source_event()
            event["redaction"]["rawPayloadIncluded"] = True
            event["connector"]["readOnly"] = False
            event["contentSummary"] = "Synthetic summary mentions reviewer sam@example.com."
            (fixture / "source-event.json").write_text(json.dumps(event), encoding="utf-8")
            case_path = write_case(
                root,
                {
                    "id": "source-event-fail",
                    "skill": "fixture",
                    "scenario": "Unsafe source event.",
                    "input_fixture": "fixtures/unsafe-source-event",
                    "expected_artifacts": ["source-event.json"],
                    "checks": [{"type": "source_event", "path": "source-event.json"}],
                    "risk_invariant": "Unsafe source events fail deterministic checks.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("connector.readOnly" in e for e in result.failed_checks))
        self.assertTrue(any("rawPayloadIncluded" in e for e in result.failed_checks))
        self.assertTrue(any("possible email address" in e for e in result.failed_checks))

    def test_review_package_staged_ready_passes(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "review-package"
            fixture.mkdir(parents=True)
            (fixture / "review.json").write_text(
                json.dumps(valid_review_package(status="staged-proposal-ready")),
                encoding="utf-8",
            )
            case_path = write_case(
                root,
                {
                    "id": "review-package-pass",
                    "skill": "fixture",
                    "scenario": "Valid staged-ready review package.",
                    "input_fixture": "fixtures/review-package",
                    "expected_artifacts": ["review.json"],
                    "checks": [
                        {
                            "type": "review_package",
                            "path": "review.json",
                            "status": "staged-proposal-ready",
                            "requiredAction": "prepare-staged-proposal",
                        }
                    ],
                    "risk_invariant": "Review approval prepares staged proposals only.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertTrue(result.passed, result.failed_checks)
        self.assertEqual(result.passed_checks, 1)

    def test_review_package_pending_staged_action_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "unsafe-review-package"
            fixture.mkdir(parents=True)
            package = valid_review_package()
            package["requiredActions"].append(
                {
                    "action": "prepare-staged-proposal",
                    "changeId": "mcpkg-test",
                    "reason": "Unsafe pre-approval staged proposal action.",
                }
            )
            (fixture / "review.json").write_text(json.dumps(package), encoding="utf-8")
            case_path = write_case(
                root,
                {
                    "id": "review-package-fail",
                    "skill": "fixture",
                    "scenario": "Pending review package requests staged proposal.",
                    "input_fixture": "fixtures/unsafe-review-package",
                    "expected_artifacts": ["review.json"],
                    "checks": [{"type": "review_package", "path": "review.json"}],
                    "risk_invariant": "Pending review cannot prepare staged proposals.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("only staged-proposal-ready" in e for e in result.failed_checks))

    def test_review_package_staged_ready_requires_owner_approval(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "review-owner-mismatch"
            fixture.mkdir(parents=True)
            package = valid_review_package(status="staged-proposal-ready")
            package["decisions"][0]["actor"] = "role:different-owner"
            (fixture / "review.json").write_text(json.dumps(package), encoding="utf-8")
            case_path = write_case(
                root,
                {
                    "id": "review-owner-mismatch",
                    "skill": "fixture",
                    "scenario": "Staged-ready review package without routed owner approval.",
                    "input_fixture": "fixtures/review-owner-mismatch",
                    "expected_artifacts": ["review.json"],
                    "checks": [
                        {
                            "type": "review_package",
                            "path": "review.json",
                            "status": "staged-proposal-ready",
                        }
                    ],
                    "risk_invariant": "Staged-ready review requires routed owner approval.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("approved decision from routed owner" in e for e in result.failed_checks))

    def test_review_package_malformed_contract_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "malformed-review-package"
            fixture.mkdir(parents=True)
            package = valid_review_package()
            package["reviewId"] = "bad review id"
            package["changes"][0]["kind"] = "unsupported-kind"
            package["requiredActions"] = []
            package["decisions"] = [{}]
            package["audit"] = [{}]
            package["safety"]["extraFlag"] = True
            (fixture / "review.json").write_text(json.dumps(package), encoding="utf-8")
            case_path = write_case(
                root,
                {
                    "id": "review-package-malformed",
                    "skill": "fixture",
                    "scenario": "Malformed review package contract.",
                    "input_fixture": "fixtures/malformed-review-package",
                    "expected_artifacts": ["review.json"],
                    "checks": [{"type": "review_package", "path": "review.json"}],
                    "risk_invariant": "Review package checks reject malformed artifacts.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("reviewId has invalid format" in e for e in result.failed_checks))
        self.assertTrue(any("kind is outside the contract" in e for e in result.failed_checks))
        self.assertTrue(any("pending review package must have required actions" in e for e in result.failed_checks))
        self.assertTrue(any("safety extra fields" in e for e in result.failed_checks))
        self.assertTrue(any("decisions[0].decision" in e for e in result.failed_checks))
        self.assertTrue(any("audit[0].actor" in e for e in result.failed_checks))

    def test_review_package_malformed_field_variants_fail(self):
        runner = load_runner()
        variants = [
            ("bad-package-id", lambda package: package.update({"packageId": "bad package"}), "packageId has invalid format"),
            ("bad-module-id", lambda package: package.update({"moduleId": "Bad Module"}), "moduleId has invalid format"),
            (
                "bad-change-id",
                lambda package: package["changes"][0].update({"changeId": "bad change"}),
                "changeId has invalid format",
            ),
            (
                "bad-confidence",
                lambda package: package["changes"][0].update({"confidence": "certain"}),
                "confidence is outside the contract",
            ),
            (
                "bad-risk",
                lambda package: package["changes"][0].update({"risk": "critical"}),
                "risk is outside the contract",
            ),
            (
                "bad-action",
                lambda package: package["changes"][0].update({"proposedAction": "promote"}),
                "proposedAction is outside the contract",
            ),
            (
                "bad-evidence-id",
                lambda package: package["changes"][0]["evidence"][0].update({"sourceEventId": "source-1"}),
                "sourceEventId has invalid format",
            ),
            (
                "bad-evidence-extra",
                lambda package: package["changes"][0]["evidence"][0].update({"rawPayload": "not allowed"}),
                "evidence[0] extra fields",
            ),
        ]

        for slug, mutate, expected_error in variants:
            with self.subTest(slug=slug):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    fixture = root / "fixtures" / slug
                    fixture.mkdir(parents=True)
                    package = valid_review_package()
                    mutate(package)
                    (fixture / "review.json").write_text(json.dumps(package), encoding="utf-8")
                    case_path = write_case(
                        root,
                        {
                            "id": slug,
                            "skill": "fixture",
                            "scenario": "Malformed review package variant.",
                            "input_fixture": f"fixtures/{slug}",
                            "expected_artifacts": ["review.json"],
                            "checks": [{"type": "review_package", "path": "review.json"}],
                            "risk_invariant": "Review package checks reject malformed variants.",
                        },
                    )

                    result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(
            any(expected_error in error for error in result.failed_checks),
            result.failed_checks,
        )

    def test_digest_artifact_check_passes(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "digest"
            fixture.mkdir(parents=True)
            (fixture / "digest.md").write_text(
                """# Weekly resident digest

Review packages: 2
Refused source events: 0

- mcpkg-one - human-review - Synthetic first review item.
- mcpkg-two - needs-owner - Synthetic owner assignment item.
""",
                encoding="utf-8",
            )
            case_path = write_case(
                root,
                {
                    "id": "digest-pass",
                    "skill": "fixture",
                    "scenario": "Valid bounded digest.",
                    "input_fixture": "fixtures/digest",
                    "expected_artifacts": ["digest.md"],
                    "checks": [
                        {
                            "type": "digest_artifact",
                            "path": "digest.md",
                            "reviewPackageCount": 2,
                            "refusedSourceEvents": 0,
                            "maxEntries": 2,
                            "mustContain": ["mcpkg-one"],
                        }
                    ],
                    "risk_invariant": "Digest artifacts stay bounded and redacted.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertTrue(result.passed, result.failed_checks)
        self.assertEqual(result.passed_checks, 1)

    def test_digest_artifact_unbounded_or_sensitive_fails(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "unsafe-digest"
            fixture.mkdir(parents=True)
            (fixture / "digest.md").write_text(
                """# Weekly resident digest

Review packages: 3
Refused source events: 0

- mcpkg-one - human-review - Synthetic first review item.
- mcpkg-two - human-review - Synthetic second review item.
- mcpkg-three - human-review - Contact sam@example.com leaked here.
""",
                encoding="utf-8",
            )
            case_path = write_case(
                root,
                {
                    "id": "digest-fail",
                    "skill": "fixture",
                    "scenario": "Unsafe digest artifact.",
                    "input_fixture": "fixtures/unsafe-digest",
                    "expected_artifacts": ["digest.md"],
                    "checks": [
                        {
                            "type": "digest_artifact",
                            "path": "digest.md",
                            "reviewPackageCount": 3,
                            "maxEntries": 2,
                        }
                    ],
                    "risk_invariant": "Digest artifacts reject unbounded or sensitive content.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("possible email address" in e for e in result.failed_checks))
        self.assertTrue(any("max is 2" in e for e in result.failed_checks))

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

    def test_trace_proposal_ready_requires_human_approval(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "proposal-before-approval"
            fixture.mkdir(parents=True)
            write_trace(
                fixture / "trace" / "events.jsonl",
                [
                    trace_event(
                        "validation",
                        "links_validate",
                        "pass",
                        summary="Validation passed.",
                    ),
                    trace_event(
                        "artifact_write",
                        "propose_change",
                        "proposal-ready",
                        path="staged/prop-example.md",
                        summary="Staged proposal prepared before a human approval event.",
                    ),
                ],
            )
            case_path = write_case(
                root,
                {
                    "id": "proposal-before-approval",
                    "skill": "fixture",
                    "scenario": "Proposal-ready event before approval.",
                    "input_fixture": "fixtures/proposal-before-approval",
                    "trace_fixture": "trace/events.jsonl",
                    "expected_artifacts": ["trace/events.jsonl"],
                    "checks": [{"type": "trace_human_approval_before_proposal_ready"}],
                    "risk_invariant": "Staged proposal readiness requires human approval.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("before human approval" in e for e in result.failed_checks))

    def test_trace_proposal_ready_rejects_unrelated_human_approval(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "proposal-after-unrelated-approval"
            fixture.mkdir(parents=True)
            write_trace(
                fixture / "trace" / "events.jsonl",
                [
                    trace_event(
                        "approval",
                        "approve_meeting_notes",
                        "approved",
                        actor="human",
                        summary="Unrelated approval that should not unlock staged proposal readiness.",
                    ),
                    trace_event(
                        "validation",
                        "links_validate",
                        "pass",
                        summary="Validation passed.",
                    ),
                    trace_event(
                        "artifact_write",
                        "propose_change",
                        "proposal-ready",
                        path="staged/prop-example.md",
                        summary="Staged proposal prepared after an unrelated approval event.",
                    ),
                ],
            )
            case_path = write_case(
                root,
                {
                    "id": "proposal-after-unrelated-approval",
                    "skill": "fixture",
                    "scenario": "Proposal-ready event after unrelated approval.",
                    "input_fixture": "fixtures/proposal-after-unrelated-approval",
                    "trace_fixture": "trace/events.jsonl",
                    "expected_artifacts": ["trace/events.jsonl"],
                    "checks": [{"type": "trace_human_approval_before_proposal_ready"}],
                    "risk_invariant": "Only review decisions unlock staged proposal readiness.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertFalse(result.passed)
        self.assertTrue(any("before human approval" in e for e in result.failed_checks))

    def test_trace_proposal_ready_after_human_approval_passes(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixtures" / "proposal-after-approval"
            fixture.mkdir(parents=True)
            write_trace(
                fixture / "trace" / "events.jsonl",
                [
                    trace_event(
                        "approval",
                        "record_review_decision",
                        "approved",
                        actor="human",
                        summary="Routed owner approved staged proposal preparation.",
                    ),
                    trace_event(
                        "validation",
                        "links_validate",
                        "pass",
                        summary="Validation passed.",
                    ),
                    trace_event(
                        "artifact_write",
                        "propose_change",
                        "proposal-ready",
                        path="staged/prop-example.md",
                        summary="Staged proposal prepared after approval.",
                    ),
                ],
            )
            case_path = write_case(
                root,
                {
                    "id": "proposal-after-approval",
                    "skill": "fixture",
                    "scenario": "Proposal-ready event after approval.",
                    "input_fixture": "fixtures/proposal-after-approval",
                    "trace_fixture": "trace/events.jsonl",
                    "expected_artifacts": ["trace/events.jsonl"],
                    "checks": [{"type": "trace_human_approval_before_proposal_ready"}],
                    "risk_invariant": "Staged proposal readiness follows human approval.",
                },
            )

            result = runner.run_case(case_path, repo_root=root)

        self.assertTrue(result.passed, result.failed_checks)

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

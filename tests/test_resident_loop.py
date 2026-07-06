import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPO_ROOT / "scripts" / "run_resident_loop.py"


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def trace_events(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class ResidentLoopTests(unittest.TestCase):
    def setUp(self):
        from runtime.resident_loop import run_once

        self.run_once = run_once

    def model_pack(self):
        return {
            "modelPackId": "mp-test-acquisition",
            "moduleId": "acquisition",
            "version": "test",
            "owners": {
                "primary": "role:acquisition-owner",
                "review": "role:ontology-reviewer",
            },
            "sourceAuthority": [
                {
                    "sourceKind": "telegram-export",
                    "maxStatus": "hypothesis",
                    "reviewRequired": True,
                },
                {
                    "sourceKind": "dashboard-snapshot",
                    "maxStatus": "candidate",
                    "reviewRequired": True,
                },
            ],
            "reviewOwners": [
                {
                    "scope": "measurement",
                    "owner": "role:analytics-owner",
                    "appliesTo": ["measurement-convention"],
                    "highRiskOnly": True,
                }
            ],
            "compilerHints": {"maxEvidenceItems": 2},
        }

    def source_event(self, event_id="srcevt-loop-handoff-001", event_hash=None):
        return {
            "eventId": event_id,
            "sourceId": "src-loop-telegram",
            "sourceKind": "telegram-export",
            "observedAt": "2026-06-22T10:00:00Z",
            "connector": {
                "name": "synthetic-test-connector",
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
                "actor": "synthetic-test-connector",
                "actorType": "connector",
                "createdAt": "2026-06-22T10:00:00Z",
                "sourceLocator": "telegram:test#msg-001",
                "method": "Synthetic redacted resident-loop test event.",
            },
            "redaction": {
                "piiExcluded": True,
                "rawPayloadIncluded": False,
                "redactionNotes": "Synthetic redacted event.",
            },
            "evidence": [
                {
                    "locator": "telegram:test#msg-001",
                    "segmentType": "line-range",
                    "excerpt": "Acquisition operations supplies qualification notes to sales operations.",
                }
            ],
            "contentSummary": (
                "A redacted chat export suggests a handoff interface where "
                "acquisition operations supplies qualification notes to sales operations."
            ),
            "hash": event_hash
            or "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        }

    def write_fixture(self, tmp, source_event=None):
        root = Path(tmp)
        model_pack_path = root / "model-pack.json"
        source_dir = root / "source-events"
        source_path = source_dir / "event.json"
        package_dir = root / "artifacts" / "packages"
        trace_path = root / "artifacts" / "trace" / "events.jsonl"
        state_path = root / "state" / "resident-ledger.json"
        digest_path = root / "artifacts" / "digests" / "digest.md"
        write_json(model_pack_path, self.model_pack())
        write_json(source_path, source_event or self.source_event())
        config = {
            "modelPackPath": str(model_pack_path),
            "sourceEventDir": str(source_dir),
            "packageOutputDir": str(package_dir),
            "statePath": str(state_path),
            "tracePath": str(trace_path),
            "artifactRoot": str(root / "artifacts"),
            "digestPath": str(digest_path),
            "digestThreshold": 1,
            "ontologyRevision": "git:test",
            "generatedAt": "2026-06-22T00:00:00Z",
        }
        return config, package_dir, trace_path, state_path, digest_path

    def open_store(self, config):
        from runtime.operational_store import OperationalStore

        store = OperationalStore.connect(Path(config["storePath"]))
        store.initialize()
        self.addCleanup(store.close)
        return store

    def write_many_events(self, source_dir, count):
        source_dir.mkdir(parents=True, exist_ok=True)
        for index in range(count):
            event = self.source_event(
                event_id=f"srcevt-loop-handoff-{index:03d}",
                event_hash=f"sha256:{index + 1:064d}",
            )
            write_json(source_dir / f"event-{index:03d}.json", event)

    def test_one_new_source_event_produces_package_and_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, package_dir, trace_path, state_path, digest_path = self.write_fixture(tmp)

            summary = self.run_once(config)
            package_files = sorted(package_dir.glob("*.json"))
            package = load_json(package_files[0])
            ledger = load_json(state_path)
            events = trace_events(trace_path)

        self.assertEqual(summary["packages_written"], 1, summary)
        self.assertEqual(summary["events_refused"], 0, summary)
        self.assertEqual(summary["digest"]["status"], "written", summary)
        self.assertTrue(package_files)
        self.assertTrue(digest_path.name in summary["digest"]["path"])
        self.assertEqual(package["review"]["overallAction"], "human-review")
        self.assertTrue(package["safety"]["noAcceptedMutation"])
        self.assertIn(package["sourceEventIds"][0], ledger["processedEventIds"])
        self.assertTrue(any(event["name"] == "model_change_package" for event in events))
        self.assertTrue(any(event["event_type"] == "digest" for event in events))
        self.assertFalse(any("raw_payload" in json.dumps(event) for event in events))

    def test_rerun_with_same_hash_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, package_dir, trace_path, _, _ = self.write_fixture(tmp)

            first = self.run_once(config)
            second = self.run_once(config)
            package_files = sorted(package_dir.glob("*.json"))
            events = trace_events(trace_path)

        self.assertEqual(first["packages_written"], 1, first)
        self.assertEqual(second["packages_written"], 0, second)
        self.assertEqual(second["events_skipped"], 1, second)
        self.assertEqual(len(package_files), 1)
        self.assertTrue(any(event["name"] == "resident_loop_skip_duplicate" for event in events))

    def test_store_path_persists_packages_and_run_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, package_dir, _, _, _ = self.write_fixture(tmp)
            config["storePath"] = str(Path(tmp) / "state" / "operational-store.sqlite")

            summary = self.run_once(config)
            package_files = sorted(package_dir.glob("*.json"))
            store = self.open_store(config)
            pending = store.list_pending_packages()
            requests = store.list_open_human_requests()

        self.assertEqual(summary["packages_written"], 1, summary)
        self.assertEqual(summary["store_path"], "operational-store.sqlite")
        self.assertEqual(len(package_files), 1)
        self.assertEqual(store.table_count("source_events"), 1)
        self.assertEqual(store.table_count("model_change_packages"), 1)
        self.assertEqual(store.table_count("runs"), 1)
        self.assertEqual([package["packageId"] for package in pending], [package_files[0].stem])
        self.assertEqual([request["kind"] for request in requests], ["review"])
        self.assertEqual(requests[0]["packageId"], package_files[0].stem)
        self.assertIn("handoff interface", requests[0]["prompt"])

    def test_digest_includes_open_human_requests_from_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, _, _, digest_path = self.write_fixture(tmp)
            config["storePath"] = str(Path(tmp) / "state" / "operational-store.sqlite")
            store = self.open_store(config)
            store.record_human_request(
                {
                    "requestId": "hreq-loop-owner",
                    "kind": "clarification",
                    "owner": "role:acquisition-owner",
                    "channel": "telegram:dm-owner",
                    "prompt": "Is the handoff rule production or draft?",
                    "recommendedAnswer": "Treat it as draft until owner confirms.",
                    "askedAt": "2026-06-22T08:00:00Z",
                    "dueAt": "2026-06-23T09:00:00Z",
                }
            )

            summary = self.run_once(config)
            digest = digest_path.read_text(encoding="utf-8")

        self.assertEqual(summary["digest"]["human_request_count"], 2)
        self.assertIn("Human requests: 2", digest)
        self.assertIn("clarification - Is the handoff rule production or draft?", digest)
        self.assertIn("review - Reference compiler package for telegram-export", digest)

    def test_answered_human_request_disappears_from_next_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, _, _, digest_path = self.write_fixture(tmp)
            config["storePath"] = str(Path(tmp) / "state" / "operational-store.sqlite")
            accepted_context_path = Path(tmp) / "accepted-context.json"
            write_json(
                accepted_context_path,
                {
                    "processedEventIds": ["srcevt-loop-handoff-001"],
                    "processedHashes": [],
                },
            )
            config["acceptedContextPath"] = str(accepted_context_path)
            store = self.open_store(config)
            store.record_human_request(
                {
                    "requestId": "hreq-meeting-review-owner",
                    "kind": "review",
                    "owner": "role:acquisition-owner",
                    "channel": "telegram:dm-owner",
                    "messageRef": "telegram:dm-owner#msg-101",
                    "prompt": "Should the transcript decision become a model-change package?",
                    "recommendedAnswer": "Yes, stage it for review.",
                    "sourceRef": "meeting-transcript:mtgrec-001",
                    "askedAt": "2026-06-22T08:00:00Z",
                }
            )
            store.record_human_request(
                {
                    "requestId": "hreq-meeting-source-access",
                    "kind": "source-access",
                    "owner": "role:acquisition-owner",
                    "channel": "telegram:dm-owner",
                    "messageRef": "telegram:dm-owner#msg-102",
                    "prompt": "May I use the CRM board as the source of truth for this transcript claim?",
                    "recommendedAnswer": "Yes, use the read-only CRM board.",
                    "sourceRef": "meeting-transcript:mtgrec-001",
                    "askedAt": "2026-06-22T08:05:00Z",
                }
            )
            request = store.find_human_request_by_message_ref(
                "telegram:dm-owner",
                "telegram:dm-owner#msg-101",
            )
            store.mark_human_request_answered(
                request["requestId"],
                answer_summary="Owner approved staging the transcript decision for review.",
                decision_id="decision-meeting-review-owner",
                answered_at="2026-06-22T08:30:00Z",
            )

            summary = self.run_once(config)
            digest = digest_path.read_text(encoding="utf-8")

        self.assertEqual(summary["digest"]["human_request_count"], 1)
        self.assertIn("Human requests: 1", digest)
        self.assertIn("source-access - May I use the CRM board", digest)
        self.assertNotIn("Should the transcript decision", digest)

    def test_store_suppresses_duplicate_when_json_ledger_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, package_dir, trace_path, state_path, _ = self.write_fixture(tmp)
            config["storePath"] = str(Path(tmp) / "state" / "operational-store.sqlite")

            first = self.run_once(config)
            state_path.unlink()
            second = self.run_once(config)
            package_files = sorted(package_dir.glob("*.json"))
            events = trace_events(trace_path)
            store = self.open_store(config)

        self.assertEqual(first["packages_written"], 1, first)
        self.assertEqual(second["packages_written"], 0, second)
        self.assertEqual(second["events_skipped"], 1, second)
        self.assertEqual(len(package_files), 1)
        self.assertEqual(store.table_count("source_events"), 1)
        self.assertEqual(store.table_count("model_change_packages"), 1)
        self.assertEqual(store.table_count("runs"), 2)
        self.assertTrue(any(event["name"] == "resident_loop_skip_duplicate" for event in events))

    def test_noop_package_written_to_store_is_not_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, _, _, _ = self.write_fixture(tmp)
            config["storePath"] = str(Path(tmp) / "state" / "operational-store.sqlite")
            accepted_context_path = Path(tmp) / "accepted-context.json"
            write_json(
                accepted_context_path,
                {
                    "processedEventIds": ["srcevt-loop-handoff-001"],
                    "processedHashes": [],
                },
            )
            config["acceptedContextPath"] = str(accepted_context_path)

            summary = self.run_once(config)
            store = self.open_store(config)

        self.assertEqual(summary["packages_written"], 1, summary)
        self.assertEqual(store.table_count("model_change_packages"), 1)
        self.assertEqual(store.list_pending_packages(), [])
        self.assertEqual(store.list_open_human_requests(), [])

    def test_unsafe_source_event_is_refused_and_traced(self):
        source = self.source_event()
        source["connector"] = {**source["connector"], "readOnly": False}
        with tempfile.TemporaryDirectory() as tmp:
            config, package_dir, trace_path, state_path, _ = self.write_fixture(tmp, source_event=source)

            summary = self.run_once(config)
            ledger = load_json(state_path)
            events = trace_events(trace_path)

        self.assertEqual(summary["packages_written"], 0, summary)
        self.assertEqual(summary["events_refused"], 1, summary)
        self.assertFalse(list(package_dir.glob("*.json")))
        self.assertIn(source["eventId"], ledger["refusedEventIds"])
        self.assertTrue(any(event["event_type"] == "refusal" for event in events))
        self.assertTrue(any("connector is not read-only" in event["summary"] for event in events))

    def test_schema_invalid_source_event_is_refused_before_compilation(self):
        source = self.source_event()
        source["evidence"] = [
            {
                "locator": "telegram:test#msg-001",
                "excerpt": "Missing segment type should fail intake validation.",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            config, package_dir, trace_path, state_path, _ = self.write_fixture(tmp, source_event=source)

            summary = self.run_once(config)
            ledger = load_json(state_path)
            events = trace_events(trace_path)

        self.assertEqual(summary["packages_written"], 0, summary)
        self.assertEqual(summary["events_refused"], 1, summary)
        self.assertFalse(list(package_dir.glob("*.json")))
        self.assertIn(source["eventId"], ledger["refusedEventIds"])
        self.assertTrue(any("segmentType" in event["summary"] for event in events))

    def test_failed_run_is_recorded_and_store_reopens_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, package_dir, _, _, _ = self.write_fixture(tmp)
            config["storePath"] = str(Path(tmp) / "state" / "operational-store.sqlite")
            package_dir.parent.mkdir(parents=True, exist_ok=True)
            package_dir.write_text("not a directory\n", encoding="utf-8")

            with self.assertRaises(OSError):
                self.run_once(config)

            store = self.open_store(config)
            row = store._connection.execute(
                "SELECT status, finished_at, summary_json FROM runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            summary = json.loads(row["summary_json"])

        self.assertEqual(str(row["status"]), "failed")
        self.assertTrue(str(row["finished_at"]))
        self.assertIn("error", summary)

    def test_refused_source_event_is_idempotent_on_rerun(self):
        source = self.source_event()
        source["redaction"] = {**source["redaction"], "rawPayloadIncluded": True}
        with tempfile.TemporaryDirectory() as tmp:
            config, package_dir, trace_path, _, _ = self.write_fixture(tmp, source_event=source)

            first = self.run_once(config)
            second = self.run_once(config)
            events = trace_events(trace_path)

        self.assertEqual(first["events_refused"], 1, first)
        self.assertEqual(second["events_refused"], 0, second)
        self.assertEqual(second["events_skipped"], 1, second)
        self.assertFalse(list(package_dir.glob("*.json")))
        self.assertEqual(sum(1 for event in events if event["event_type"] == "refusal"), 1)

    def test_malformed_source_event_is_refused_and_does_not_block_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, package_dir, trace_path, state_path, _ = self.write_fixture(tmp)
            source_dir = Path(config["sourceEventDir"])
            (source_dir / "bad.json").write_text('{"eventId": ""}', encoding="utf-8")

            first = self.run_once(config)
            package_count_after_first = len(list(package_dir.glob("*.json")))
            second = self.run_once(config)
            ledger = load_json(state_path)
            events = trace_events(trace_path)

        self.assertEqual(first["packages_written"], 1, first)
        self.assertEqual(first["events_refused"], 1, first)
        self.assertEqual(package_count_after_first, 1)
        self.assertEqual(second["packages_written"], 0, second)
        self.assertEqual(second["events_skipped"], 2, second)
        self.assertTrue(ledger["refusedEventIds"])
        self.assertEqual(sum(1 for event in events if event["name"] == "source_event_intake"), 1)

    def test_changed_malformed_source_event_at_same_path_is_refused_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, trace_path, state_path, _ = self.write_fixture(tmp)
            source_dir = Path(config["sourceEventDir"])
            for path in source_dir.glob("*.json"):
                path.unlink()
            bad_path = source_dir / "bad.json"
            bad_path.write_text('{"eventId": ""}', encoding="utf-8")

            first = self.run_once(config)
            bad_path.write_text('{"hash": ""}', encoding="utf-8")
            second = self.run_once(config)
            ledger = load_json(state_path)
            events = trace_events(trace_path)

        self.assertEqual(first["events_refused"], 1, first)
        self.assertEqual(second["events_refused"], 1, second)
        self.assertEqual(second["events_skipped"], 0, second)
        self.assertEqual(len(ledger["refusedEventIds"]), 2)
        self.assertEqual(sum(1 for event in events if event["name"] == "source_event_intake"), 2)

    def test_misconfigured_write_path_into_accepted_tree_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, _, _, _ = self.write_fixture(tmp)
            forbidden_dir = Path(tmp) / "ontology" / "concepts"
            config["packageOutputDir"] = str(forbidden_dir)
            config["artifactRoot"] = str(Path(tmp) / "ontology")

            with self.assertRaisesRegex(ValueError, "forbidden ontology path"):
                self.run_once(config)

            self.assertFalse(forbidden_dir.exists())

    def test_misconfigured_store_path_outside_state_root_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, _, _, _ = self.write_fixture(tmp)
            config["storePath"] = str(Path(tmp) / "outside.sqlite")

            with self.assertRaisesRegex(ValueError, "storePath must stay within"):
                self.run_once(config)

            self.assertFalse((Path(tmp) / "outside.sqlite").exists())

    def test_default_digest_path_stays_inside_artifact_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, _, _, _ = self.write_fixture(tmp)
            artifact_root = Path(tmp) / "artifacts-root"
            config["packageOutputDir"] = str(artifact_root)
            config["artifactRoot"] = str(artifact_root)
            config["tracePath"] = str(artifact_root / "trace" / "events.jsonl")
            config.pop("digestPath")

            summary = self.run_once(config)
            digest_path = artifact_root / "digests" / "digest-resident-loop.md"
            digest_exists = digest_path.exists()
            escaped_digest_exists = (
                artifact_root.parent / "digests" / "digest-resident-loop.md"
            ).exists()

        self.assertEqual(summary["digest"]["path"], "digests/digest-resident-loop.md")
        self.assertTrue(digest_exists)
        self.assertFalse(escaped_digest_exists)

    def test_large_batch_summary_and_digest_are_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, package_dir, _, _, digest_path = self.write_fixture(tmp)
            source_dir = Path(config["sourceEventDir"])
            for path in source_dir.glob("*.json"):
                path.unlink()
            self.write_many_events(source_dir, 3)
            config["summaryPackageLimit"] = 2
            config["digestPackageLimit"] = 2

            summary = self.run_once(config)
            digest = digest_path.read_text(encoding="utf-8")
            package_file_count = len(list(package_dir.glob("*.json")))

        self.assertEqual(summary["packages_written"], 3, summary)
        self.assertEqual(len(summary["package_paths"]), 2, summary)
        self.assertEqual(summary["package_paths_total"], 3, summary)
        self.assertEqual(summary["package_paths_truncated"], 1, summary)
        self.assertEqual(summary["digest"]["entries_written"], 2, summary)
        self.assertEqual(summary["digest"]["entries_truncated"], 1, summary)
        self.assertIn("1 more package(s) omitted", digest)
        self.assertEqual(package_file_count, 3)

    def test_digest_skips_when_threshold_is_not_met(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, trace_path, _, digest_path = self.write_fixture(tmp)
            config["digestThreshold"] = 2

            summary = self.run_once(config)
            events = trace_events(trace_path)

        self.assertEqual(summary["packages_written"], 1, summary)
        self.assertEqual(summary["digest"]["status"], "skipped", summary)
        self.assertFalse(digest_path.exists())
        self.assertTrue(any(event["event_type"] == "digest" and event["result"] == "skipped" for event in events))

    def test_cli_runs_once_and_rejects_continuous_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, _, _, _ = self.write_fixture(tmp)
            config_path = Path(tmp) / "runtime-config.json"
            write_json(config_path, config)

            once = subprocess.run(
                [sys.executable, str(CLI_PATH), "--config", str(config_path), "--once"],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            continuous = subprocess.run(
                [sys.executable, str(CLI_PATH), "--config", str(config_path)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(once.returncode, 0, once.stderr)
        self.assertEqual(json.loads(once.stdout)["status"], "ok")
        self.assertEqual(continuous.returncode, 2)
        self.assertIn("Continuous scheduling is not implemented", continuous.stderr)


if __name__ == "__main__":
    unittest.main()

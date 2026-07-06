import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "run_meeting_recording_live_proof.py"
FIXTURE = REPO_ROOT / "evals" / "fixtures" / "meeting-transcript-ingest" / "decision-and-fixation"


def load_script():
    spec = importlib.util.spec_from_file_location("run_meeting_recording_live_proof", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_matching_agent_artifacts(root: Path, packet_id: str) -> tuple[Path, Path, Path]:
    artifact_root = root / "agent-artifacts"
    source_event = json.loads((FIXTURE / "source-event.json").read_text(encoding="utf-8"))
    package = json.loads((FIXTURE / "packages" / "mcpkg-meeting-decision-fixation.json").read_text(encoding="utf-8"))

    source_event["provenanceActivity"]["sourceLocator"] = f"packet:{packet_id}#segments-12-25"
    for evidence in source_event["evidence"]:
        evidence["locator"] = f"packet:{packet_id}#segment-12-18"
    for change in package["changes"]:
        for evidence in change["evidence"]:
            evidence["locator"] = f"packet:{packet_id}#segment-12-18"

    source_event_path = artifact_root / "source-events" / "source-event.json"
    package_path = artifact_root / "packages" / "mcpkg-meeting-decision-fixation.json"
    digest_path = artifact_root / "digest.md"
    write_json(source_event_path, source_event)
    write_json(package_path, package)
    digest_path.write_text(
        """# Meeting Digest

Review packages: 1
Source events processed: 1
Source events skipped: 0
Refused source events: 0

- Packet: packet:{packet_id}
- Source event: srcevt-meeting-decision-fixation.
- Model-change package: mcpkg-meeting-decision-fixation.
- Source-of-truth fixation needs: acquisition handoff CRM claim requires owner review.
- Review owner: role:acquisition-owner.
- Result: owner review required; no model update.
""".format(packet_id=packet_id),
        encoding="utf-8",
    )
    return source_event_path, package_path.parent, digest_path


def make_packet_ready_job(
    root: Path,
    *,
    job_id: str = "mtgrec-20260706-liveproof",
    wakeup_pending: bool = True,
    completion_source: str = "webhook",
) -> tuple[Path, Path]:
    from runtime.meeting_recording_service import hash_meeting_url, hash_secret, sanitize_url
    from runtime.meeting_recording_store import MeetingRecordingStore
    from runtime.meeting_transcript_capture import capture_finished_bot

    workspace = root / "workspace"
    db_path = root / "recordings.sqlite3"
    meeting_url = "https://zoom.us/j/123456789?pwd=raw-secret"
    with MeetingRecordingStore.connect(db_path) as store:
        store.initialize()
        store.create_requested_job(
            {
                "job_id": job_id,
                "provider": "skribby",
                "meeting_url_hash": hash_meeting_url(meeting_url),
                "meeting_url_display": sanitize_url(meeting_url),
                "service": "zoom",
                "business_id": "biz-acquisition",
                "source_id": "src-meeting-skribby",
                "chat_ref": "dm-owner",
                "requested_by": "owner",
                "webhook_nonce_hash": hash_secret("nonce"),
                "provider_payload": {"meeting_url": sanitize_url(meeting_url)},
            }
        )
        store.mark_bot_created(job_id, bot_id="bot_live", provider_payload={"id": "bot_live"})
        if completion_source == "webhook":
            store.mark_finished_received(
                job_id,
                webhook_payload={
                    "bot_id": "bot_live",
                    "type": "status_update",
                    "data": {"new_status": "finished"},
                    "custom_metadata": {"job_id": job_id, "webhook_nonce": "[redacted]"},
                },
            )
            store.mark_transcript_fetched(
                job_id,
                provider_payload={"id": "bot_live"},
                provider_finished_at="2026-07-06T12:31:00Z",
            )
        elif completion_source == "recovery":
            store.mark_transcript_recovered(
                job_id,
                provider_payload={"id": "bot_live", "status": "finished"},
                provider_finished_at="2026-07-06T12:31:00Z",
            )
        else:
            raise AssertionError(f"unsupported completion_source: {completion_source}")
        capture = capture_finished_bot(
            store.get_job(job_id),
            {
                "id": "bot_live",
                "finished_at": "2026-07-06T12:31:00Z",
                "participants": [{"name": "Owner"}],
                "transcript": [
                    {
                        "start": 0,
                        "end": 4,
                        "speaker": "1",
                        "speaker_name": "Owner",
                        "confidence": 0.91,
                        "transcript": "The CRM remains the source of truth for acquisition handoff.",
                    }
                ],
            },
            workspace,
        )
        store.mark_packet_ready(
            job_id,
            packet_path=str(capture.packet_path),
            transcript_hash=capture.transcript_hash,
            wakeup_pending=wakeup_pending,
        )
    return db_path, workspace


class MeetingRecordingLiveProofTests(unittest.TestCase):
    def run_script(self, argv: list[str]) -> tuple[int, Path]:
        script = load_script()
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = script.main(argv)
        return code, Path(stdout.getvalue().strip())

    def test_packet_only_proof_writes_source_connected_report_without_raw_meeting_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path, workspace = make_packet_ready_job(root, wakeup_pending=True)
            code, proof_path = self.run_script(
                [
                    "--job-id",
                    "mtgrec-20260706-liveproof",
                    "--db",
                    str(db_path),
                    "--workspace",
                    str(workspace),
                    "--proof-root",
                    str(root / "proofs"),
                    "--packet-only",
                    "--timeout-seconds",
                    "0",
                ]
            )

            self.assertEqual(code, 0)
            proof = proof_path.read_text(encoding="utf-8")
            self.assertIn("- result: pass", proof)
            self.assertIn("- maturity: source-connected", proof)
            self.assertIn("- completion_source: webhook", proof)
            self.assertIn("- wakeup_pending: 1", proof)
            self.assertRegex(proof, r"webhook_received_at: 20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ")
            self.assertIn("packet_validated: pass", proof)
            self.assertNotIn("raw-secret", proof)

    def test_packet_only_recovery_proof_is_not_marked_source_connected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path, workspace = make_packet_ready_job(root, wakeup_pending=True, completion_source="recovery")
            code, proof_path = self.run_script(
                [
                    "--job-id",
                    "mtgrec-20260706-liveproof",
                    "--db",
                    str(db_path),
                    "--workspace",
                    str(workspace),
                    "--proof-root",
                    str(root / "proofs"),
                    "--packet-only",
                    "--timeout-seconds",
                    "0",
                ]
            )

            self.assertEqual(code, 0)
            proof = proof_path.read_text(encoding="utf-8")
            self.assertIn("- result: pass", proof)
            self.assertIn("- maturity: provider-recovered", proof)
            self.assertIn("- completion_source: recovery", proof)
            self.assertIn("- webhook_received_at: ", proof)

    def test_full_proof_requires_agent_artifacts_unless_packet_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path, workspace = make_packet_ready_job(root, wakeup_pending=False)
            code, proof_path = self.run_script(
                [
                    "--job-id",
                    "mtgrec-20260706-liveproof",
                    "--db",
                    str(db_path),
                    "--workspace",
                    str(workspace),
                    "--proof-root",
                    str(root / "proofs"),
                    "--timeout-seconds",
                    "0",
                ]
            )

            self.assertEqual(code, 1)
            proof = proof_path.read_text(encoding="utf-8")
            self.assertIn("- result: fail", proof)
            self.assertIn("full live proof requires", proof)

    def test_full_proof_validates_agent_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path, workspace = make_packet_ready_job(root, wakeup_pending=False)
            source_event_path, package_dir, digest_path = write_matching_agent_artifacts(
                root,
                "mtgpk-20260706-liveproof",
            )
            code, proof_path = self.run_script(
                [
                    "--job-id",
                    "mtgrec-20260706-liveproof",
                    "--db",
                    str(db_path),
                    "--workspace",
                    str(workspace),
                    "--proof-root",
                    str(root / "proofs"),
                    "--source-events-dir",
                    str(source_event_path),
                    "--model-change-packages-dir",
                    str(package_dir),
                    "--digest-or-review-handoff-path",
                    str(digest_path),
                    "--timeout-seconds",
                    "0",
                ]
            )

            self.assertEqual(code, 0)
            proof = proof_path.read_text(encoding="utf-8")
            self.assertIn("- maturity: live-proven", proof)
            self.assertIn("- completion_source: webhook", proof)
            self.assertIn("- wakeup_pending: 0", proof)
            self.assertIn("agent_artifacts_validated: pass", proof)
            self.assertIn("source-event.json", proof)
            self.assertIn("mcpkg-meeting-decision-fixation.json", proof)

    def test_full_proof_refuses_recovered_packet_even_with_agent_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path, workspace = make_packet_ready_job(root, wakeup_pending=False, completion_source="recovery")
            source_event_path, package_dir, digest_path = write_matching_agent_artifacts(
                root,
                "mtgpk-20260706-liveproof",
            )
            code, proof_path = self.run_script(
                [
                    "--job-id",
                    "mtgrec-20260706-liveproof",
                    "--db",
                    str(db_path),
                    "--workspace",
                    str(workspace),
                    "--proof-root",
                    str(root / "proofs"),
                    "--source-events-dir",
                    str(source_event_path),
                    "--model-change-packages-dir",
                    str(package_dir),
                    "--digest-or-review-handoff-path",
                    str(digest_path),
                    "--timeout-seconds",
                    "0",
                ]
            )

            self.assertEqual(code, 1)
            proof = proof_path.read_text(encoding="utf-8")
            self.assertIn("- result: fail", proof)
            self.assertIn("full live proof requires webhook completion_source", proof)

    def test_full_proof_rejects_agent_artifacts_from_different_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path, workspace = make_packet_ready_job(root, wakeup_pending=False)
            code, proof_path = self.run_script(
                [
                    "--job-id",
                    "mtgrec-20260706-liveproof",
                    "--db",
                    str(db_path),
                    "--workspace",
                    str(workspace),
                    "--proof-root",
                    str(root / "proofs"),
                    "--source-events-dir",
                    str(FIXTURE / "source-event.json"),
                    "--model-change-packages-dir",
                    str(FIXTURE / "packages"),
                    "--digest-or-review-handoff-path",
                    str(FIXTURE / "digest.md"),
                    "--timeout-seconds",
                    "0",
                ]
            )

            self.assertEqual(code, 1)
            proof = proof_path.read_text(encoding="utf-8")
            self.assertIn("- result: fail", proof)
            self.assertIn("does not reference packet mtgpk-20260706-liveproof", proof)

    def test_full_proof_refuses_pending_openclaw_wakeup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path, workspace = make_packet_ready_job(root, wakeup_pending=True)
            source_event_path, package_dir, digest_path = write_matching_agent_artifacts(
                root,
                "mtgpk-20260706-liveproof",
            )
            code, proof_path = self.run_script(
                [
                    "--job-id",
                    "mtgrec-20260706-liveproof",
                    "--db",
                    str(db_path),
                    "--workspace",
                    str(workspace),
                    "--proof-root",
                    str(root / "proofs"),
                    "--source-events-dir",
                    str(source_event_path),
                    "--model-change-packages-dir",
                    str(package_dir),
                    "--digest-or-review-handoff-path",
                    str(digest_path),
                    "--timeout-seconds",
                    "0",
                ]
            )

            self.assertEqual(code, 1)
            proof = proof_path.read_text(encoding="utf-8")
            self.assertIn("- result: fail", proof)
            self.assertIn("OpenClaw wakeup is still pending", proof)

    def test_order_path_calls_runtime_then_waits_for_packet_ready_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path, workspace = make_packet_ready_job(root)
            captured = {}

            def fake_urlopen(request, timeout):
                captured.setdefault("urls", []).append(request.full_url)
                if request.get_method() == "GET":
                    return FakeResponse({"status": "ok"})
                captured["body"] = json.loads(request.data.decode("utf-8"))
                return FakeResponse(
                    {
                        "job_id": "mtgrec-20260706-liveproof",
                        "bot_id": "bot_live",
                        "status": "bot_created",
                    }
                )

            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                code, proof_path = self.run_script(
                    [
                        "--service-url",
                        "https://recorder.example",
                        "--public-base-url",
                        "https://public-recorder.example",
                        "--meeting-url",
                        "https://zoom.us/j/123456789?pwd=raw-secret",
                        "--business-id",
                        "biz-acquisition",
                        "--source-id",
                        "src-meeting-skribby",
                        "--chat-ref",
                        "dm-owner",
                        "--requested-by",
                        "owner",
                        "--db",
                        str(db_path),
                        "--workspace",
                        str(workspace),
                        "--proof-root",
                        str(root / "proofs"),
                        "--packet-only",
                        "--timeout-seconds",
                        "0",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(captured["body"]["meeting_url"], "https://zoom.us/j/123456789?pwd=raw-secret")
            proof = proof_path.read_text(encoding="utf-8")
            self.assertIn("service_health: pass", proof)
            self.assertIn("public_health: pass", proof)
            self.assertIn("recording_ordered: pass", proof)
            self.assertIn("meeting_url_display: https://zoom.us/j/123456789?pwd=[redacted]", proof)
            self.assertNotIn("raw-secret", proof)

    def test_preflight_fails_when_public_endpoint_is_offline(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ", {"SKRIBBY_API_KEY": "sk_test_secret"}, clear=True):
            root = Path(tmp)

            def fake_urlopen(request, timeout):
                if request.full_url.startswith("https://public-recorder.example"):
                    raise OSError("offline")
                return FakeResponse({"status": "ok"})

            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                code, proof_path = self.run_script(
                    [
                        "--preflight",
                        "--packet-only",
                        "--service-url",
                        "https://recorder.example",
                        "--public-base-url",
                        "https://public-recorder.example",
                        "--meeting-url",
                        "https://zoom.us/j/123456789?pwd=raw-secret",
                        "--business-id",
                        "biz-acquisition",
                        "--source-id",
                        "src-meeting-skribby",
                        "--chat-ref",
                        "dm-owner",
                        "--requested-by",
                        "owner",
                        "--db",
                        str(root / "recordings.sqlite3"),
                        "--workspace",
                        str(root / "workspace"),
                        "--proof-root",
                        str(root / "proofs"),
                    ]
                )

            self.assertEqual(code, 1)
            proof = proof_path.read_text(encoding="utf-8")
            self.assertIn("- result: fail", proof)
            self.assertIn("public endpoint health check failed", proof)

    def test_preflight_reports_missing_inputs_without_values(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ", {}, clear=True):
            code, proof_path = self.run_script(
                [
                    "--preflight",
                    "--proof-root",
                    tmp,
                ]
            )

            self.assertEqual(code, 1)
            proof = proof_path.read_text(encoding="utf-8")
            self.assertIn("- result: fail", proof)
            self.assertIn("SKRIBBY_API_KEY", proof)
            self.assertIn("MEETING_RECORDING_SERVICE_URL", proof)
            self.assertNotIn("sk_", proof)
            self.assertNotIn("Bearer", proof)

    def test_preflight_passes_with_packet_inputs_and_health_without_ordering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            captured = {}

            def fake_urlopen(request, timeout):
                captured["url"] = request.full_url
                captured["method"] = request.get_method()
                return FakeResponse({"status": "ok"})

            with mock.patch.dict("os.environ", {"SKRIBBY_API_KEY": "sk_test_secret"}, clear=True), mock.patch(
                "urllib.request.urlopen",
                side_effect=fake_urlopen,
            ):
                code, proof_path = self.run_script(
                    [
                        "--preflight",
                        "--packet-only",
                        "--service-url",
                        "https://recorder.example",
                        "--public-base-url",
                        "https://public-recorder.example",
                        "--meeting-url",
                        "https://zoom.us/j/123456789?pwd=raw-secret",
                        "--business-id",
                        "biz-acquisition",
                        "--source-id",
                        "src-meeting-skribby",
                        "--chat-ref",
                        "dm-owner",
                        "--requested-by",
                        "owner",
                        "--db",
                        str(root / "recordings.sqlite3"),
                        "--workspace",
                        str(root / "workspace"),
                        "--proof-root",
                        str(root / "proofs"),
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(captured["method"], "GET")
            self.assertTrue(captured["url"].endswith("/health"))
            proof = proof_path.read_text(encoding="utf-8")
            self.assertIn("- result: pass", proof)
            self.assertIn("- maturity: setup-only", proof)
            self.assertIn("preflight_inputs: pass", proof)
            self.assertIn("service_health: pass", proof)
            self.assertIn("public_health: pass", proof)
            self.assertIn("meeting_url_display: https://zoom.us/j/123456789?pwd=[redacted]", proof)
            self.assertNotIn("raw-secret", proof)
            self.assertNotIn("sk_test_secret", proof)


if __name__ == "__main__":
    unittest.main()

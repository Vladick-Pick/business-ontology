from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
OPENCLAW = REPO_ROOT / "adapters" / "openclaw"
LIVE_TEST = OPENCLAW / "live-test"
TEMPLATES = REPO_ROOT / "templates" / "workspace"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class MeetingRecordingLiveReadinessTests(unittest.TestCase):
    def test_service_runbook_pins_single_runtime_and_live_proof_report(self):
        path = OPENCLAW / "MEETING_RECORDING_SERVICE.md"
        text = read(path)

        required = [
            "python3 scripts/run_meeting_recording_service.py",
            "python3 scripts/run_meeting_recording_live_proof.py",
            "--preflight",
            "GET /health",
            "POST /recordings",
            "POST /webhooks/skribby",
            "SKRIBBY_API_KEY",
            "MEETING_RECORDING_PUBLIC_BASE_URL",
            "OPENCLAW_MEETING_PROCESS_HOOK_URL",
            "workspace/live-proofs/meeting-recording",
            "result: pass | fail",
            "job_id",
            "bot_id",
            "webhook_received_at",
            "wakeup_pending",
            "transcript_hash",
            "source_event_path",
            "model_change_package_path",
            "digest_or_review_handoff_path",
            "--packet-only",
            "The runner never polls Skribby",
        ]
        for phrase in required:
            self.assertIn(phrase, text)

        forbidden = [
            "requires n8n",
            "polling loop",
            "SKRIBBY_API_KEY=",
            "store raw transcript in git",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, text)

    def test_live_gates_require_real_skribby_bot_e2e_not_fixture_success(self):
        joined = "\n".join(
            read(LIVE_TEST / filename)
            for filename in [
                "README.md",
                "PASS_FAIL_GATES.md",
                "OPERATOR_CHECKLIST.md",
                "OBSERVER_PROTOCOL.md",
            ]
        )

        required = [
            "real Skribby bot",
            "Zoom",
            "webhook_received_at",
            "transcript_hash",
            "source_event_path",
            "model_change_package_path",
            "digest_or_review_handoff_path",
            "live-proven",
        ]
        for phrase in required:
            self.assertIn(phrase, joined)

        self.assertRegex(joined, r"(?is)unit tests?.{0,80}not live-proven|not live-proven.{0,80}unit tests?")
        self.assertRegex(joined, r"(?is)n8n.{0,80}not")

    def test_workspace_templates_default_to_skribby_meeting_recording(self):
        sources = read(TEMPLATES / "SOURCES.md.tpl")
        cursors = read(TEMPLATES / "SOURCE_CURSORS.md.tpl")
        status = read(TEMPLATES / "LIVE_TEST_STATUS.md.tpl")
        auth = read(TEMPLATES / "AUTHORIZATION_CHECKLIST.md.tpl")
        joined = "\n".join([sources, cursors, status, auth])

        required = [
            "Meeting recording",
            "Skribby",
            "MEETING_RECORDING_PUBLIC_BASE_URL",
            "MEETING_RECORDING_SERVICE_URL",
            "REAL_ZOOM_URL",
            "MEETING_SOURCE_EVENTS_PATH",
            "MEETING_MODEL_CHANGE_PACKAGES_PATH",
            "MEETING_DIGEST_OR_REVIEW_PATH",
            "live-proofs/meeting-recording",
            "setup-only",
            "source-connected",
            "live-proven",
        ]
        for phrase in required:
            self.assertIn(phrase, joined)

        self.assertNotIn("T5 Fireflies enablement requested", status)
        self.assertNotIn("## Fireflies", cursors)
        self.assertNotIn("## Fireflies", auth)

    def test_package_docs_name_live_proof_as_remaining_external_work(self):
        readme = read(REPO_ROOT / "README.md")
        manifest = read(REPO_ROOT / "agent-package.yaml")
        bootstrap = read(OPENCLAW / "BOOTSTRAP.md")
        scheduling = read(OPENCLAW / "SCHEDULING.md")

        self.assertIn("Meeting transcript skills", readme)
        self.assertIn("Meeting recording live proof", readme)
        self.assertIn("live meeting recording/transcript E2E proof", manifest)
        self.assertIn("MEETING_RECORDING_SERVICE.md", bootstrap)
        self.assertIn("meeting recording runtime is event-driven", scheduling)
        self.assertNotIn("Meeting transcript ingest/live proof", readme)


if __name__ == "__main__":
    unittest.main()

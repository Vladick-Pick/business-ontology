import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPO_ROOT / "scripts" / "render_workflow.py"


class RenderWorkflowTests(unittest.TestCase):
    def workflow(self):
        return {
            "workflow_id": "wf-lead-ready-to-meeting-booked",
            "name": "Lead ready to meeting booked",
            "status": "accepted",
            "owner": "module-leadgen",
            "source_id": "src-sales-meeting",
            "evidence_id": "ev-workflow-ready-meeting-001",
            "decision_id": "hdec-workflow-ready-meeting-001",
            "start_state_id": "state-lead-ready-for-meeting",
            "end_state_id": "state-meeting-booked",
            "valid_from": "2026-06-27",
            "valid_to": None,
            "last_verified_at": "2026-06-27",
            "confidence": "high",
            "participants": [
                {
                    "participant_id": "wfp-leadgen-operator",
                    "role_id": "role-leadgen-operator",
                    "participant_type": "actor",
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-workflow-ready-meeting-001",
                    "decision_id": "hdec-workflow-ready-meeting-001",
                }
            ],
            "steps": [
                {
                    "step_id": "step-check-readiness",
                    "ordinal": 1,
                    "actor_id": "role-leadgen-operator",
                    "action": "Check readiness criteria.",
                    "input_ids": ["state-lead-candidate"],
                    "output_ids": ["state-lead-ready-for-meeting"],
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-workflow-ready-meeting-001",
                    "decision_id": "hdec-workflow-ready-meeting-001",
                }
            ],
            "transitions": [
                {
                    "transition_id": "wft-ready-to-handoff",
                    "from_state_id": "state-lead-ready-for-meeting",
                    "to_state_id": "state-sales-handoff-created",
                    "trigger": "readiness-confirmed",
                    "evidence_rule": "CRM status changed by leadgen operator.",
                    "authority_id": "role-leadgen-operator",
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-workflow-ready-meeting-001",
                    "decision_id": "hdec-workflow-ready-meeting-001",
                },
                {
                    "transition_id": "wft-handoff-to-booked",
                    "from_state_id": "state-sales-handoff-created",
                    "to_state_id": "state-meeting-booked",
                    "trigger": "meeting-time-confirmed",
                    "evidence_rule": "Calendar event exists.",
                    "authority_id": "role-sales-manager",
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-workflow-ready-meeting-001",
                    "decision_id": "hdec-workflow-ready-meeting-001",
                },
            ],
            "exceptions": [
                {
                    "exception_id": "wfe-sales-no-acceptance",
                    "condition": "Sales does not accept the handoff within SLA.",
                    "handling": "Escalate to acquisition owner.",
                    "severity": "medium",
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-workflow-ready-meeting-001",
                    "decision_id": "hdec-workflow-ready-meeting-001",
                }
            ],
            "metrics": [
                {
                    "metric_id": "metric-time-to-sales-acceptance",
                    "role": "sla",
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-workflow-ready-meeting-001",
                    "decision_id": "hdec-workflow-ready-meeting-001",
                }
            ],
        }

    def test_cli_renders_workflow_as_mermaid_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            from runtime.operational_store import OperationalStore

            store_path = Path(tmp) / "state" / "operational.sqlite3"
            store = OperationalStore.connect(store_path)
            store.initialize()
            store.record_accepted_workflow(self.workflow())
            store.close()

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "--store",
                    str(store_path),
                    "--workflow-id",
                    "wf-lead-ready-to-meeting-booked",
                    "--format",
                    "mermaid",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# Lead ready to meeting booked", result.stdout)
        self.assertIn("```mermaid", result.stdout)
        self.assertIn("readiness-confirmed / role-leadgen-operator", result.stdout)
        self.assertIn("meeting-time-confirmed / role-sales-manager", result.stdout)
        self.assertIn("| role-leadgen-operator | actor |", result.stdout)
        self.assertIn("Sales does not accept the handoff within SLA.", result.stdout)
        self.assertIn("| metric-time-to-sales-acceptance | sla |", result.stdout)


if __name__ == "__main__":
    unittest.main()

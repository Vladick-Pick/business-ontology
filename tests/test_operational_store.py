import json
from pathlib import Path
import tempfile
import unittest


class OperationalStoreTests(unittest.TestCase):
    def make_store(self, tmp):
        from runtime.operational_store import OperationalStore

        store = OperationalStore.connect(Path(tmp) / "state" / "operational.sqlite3")
        store.initialize()
        self.addCleanup(store.close)
        return store

    def source_event(self, event_id="srcevt-store-telegram-001", event_hash=None):
        return {
            "eventId": event_id,
            "sourceId": "src-telegram-acquisition",
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
            "redaction": {
                "piiExcluded": True,
                "rawPayloadIncluded": False,
            },
            "evidence": [
                {
                    "locator": "telegram:test#msg-001",
                    "segmentType": "line-range",
                    "excerpt": "Qualification notes move to sales operations.",
                }
            ],
            "contentSummary": "A redacted chat export suggests a handoff interface.",
            "hash": event_hash
            or "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        }

    def package(self, package_id="mcpkg-store-handoff-001", action="human-review"):
        return {
            "packageId": package_id,
            "moduleId": "acquisition",
            "modelPackId": "mp-test-acquisition",
            "modelPackVersion": "test",
            "ontologyRevision": "store:test",
            "compiler": {
                "name": "synthetic-model-change-compiler",
                "version": "test",
                "mode": "synthetic-fixture",
            },
            "sourceEventIds": ["srcevt-store-telegram-001"],
            "generatedAt": "2026-06-22T10:01:00Z",
            "summary": "A redacted chat export suggests a handoff interface.",
            "changes": [
                {
                    "changeId": "chg-store-handoff-001",
                    "kind": "new-agreement",
                    "confidence": "medium",
                    "risk": "medium",
                    "affectedIds": ["if-acquisition-sales-handoff", "unknown"],
                    "evidence": [
                        {
                            "sourceEventId": "srcevt-store-telegram-001",
                            "locator": "telegram:test#msg-001",
                            "excerpt": "Qualification notes move to sales operations.",
                        }
                    ],
                    "proposedAction": "prepare-staged-proposal",
                }
            ],
            "review": {
                "overallAction": action,
                "owner": "role:acquisition-owner",
                "reason": "A handoff change affects ownership.",
            },
            "safety": {
                "noPii": True,
                "noSecrets": True,
                "noRawPayload": True,
                "noAcceptedMutation": True,
            },
        }

    def accepted_item(self, item_id, kind="entity", name=None):
        return {
            "id": item_id,
            "kind": kind,
            "status": "accepted",
            "name": name or item_id.replace("-", " "),
            "source_id": "src-sales-meeting",
            "evidence_id": "ev-workflow-ready-meeting-001",
            "decision_id": "hdec-workflow-ready-meeting-001",
            "valid_from": "2026-06-27",
            "valid_to": None,
            "supersedes": [],
            "superseded_by": [],
            "last_verified_at": "2026-06-27",
            "confidence": "high",
        }

    def accepted_workflow(self):
        return {
            "workflow": {
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
            },
            "participants": [
                {
                    "participant_id": "wfp-leadgen-operator",
                    "workflow_id": "wf-lead-ready-to-meeting-booked",
                    "role_id": "role-leadgen-operator",
                    "participant_type": "actor",
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-workflow-ready-meeting-001",
                    "decision_id": "hdec-workflow-ready-meeting-001",
                },
                {
                    "participant_id": "wfp-sales-manager",
                    "workflow_id": "wf-lead-ready-to-meeting-booked",
                    "role_id": "role-sales-manager",
                    "participant_type": "actor",
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-workflow-ready-meeting-001",
                    "decision_id": "hdec-workflow-ready-meeting-001",
                },
            ],
            "steps": [
                {
                    "step_id": "step-check-readiness",
                    "workflow_id": "wf-lead-ready-to-meeting-booked",
                    "ordinal": 1,
                    "actor_id": "role-leadgen-operator",
                    "action": "Check readiness criteria.",
                    "input_ids": ["state-lead-candidate"],
                    "output_ids": ["state-lead-ready-for-meeting"],
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-workflow-ready-meeting-001",
                    "decision_id": "hdec-workflow-ready-meeting-001",
                },
                {
                    "step_id": "step-book-meeting",
                    "workflow_id": "wf-lead-ready-to-meeting-booked",
                    "ordinal": 2,
                    "actor_id": "role-sales-manager",
                    "action": "Book the meeting.",
                    "input_ids": ["state-sales-handoff-created"],
                    "output_ids": ["state-meeting-booked"],
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-workflow-ready-meeting-001",
                    "decision_id": "hdec-workflow-ready-meeting-001",
                },
            ],
            "transitions": [
                {
                    "transition_id": "wft-ready-to-handoff",
                    "workflow_id": "wf-lead-ready-to-meeting-booked",
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
                    "workflow_id": "wf-lead-ready-to-meeting-booked",
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
                    "workflow_id": "wf-lead-ready-to-meeting-booked",
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
                    "workflow_id": "wf-lead-ready-to-meeting-booked",
                    "metric_id": "metric-time-to-sales-acceptance",
                    "role": "sla",
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-workflow-ready-meeting-001",
                    "decision_id": "hdec-workflow-ready-meeting-001",
                },
                {
                    "workflow_id": "wf-lead-ready-to-meeting-booked",
                    "metric_id": "metric-meeting-booking-conversion",
                    "role": "outcome",
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-workflow-ready-meeting-001",
                    "decision_id": "hdec-workflow-ready-meeting-001",
                },
            ],
        }

    def approved_package_with_workflow(self):
        item_specs = [
            ("state-lead-candidate", "state"),
            ("state-lead-ready-for-meeting", "state"),
            ("state-sales-handoff-created", "state"),
            ("state-meeting-booked", "state"),
            ("role-leadgen-operator", "entity"),
            ("role-sales-manager", "entity"),
            ("metric-time-to-sales-acceptance", "metric"),
            ("metric-meeting-booking-conversion", "metric"),
        ]
        changes = []
        for item_id, kind in item_specs:
            changes.append(
                {
                    "changeId": f"chg-accept-{item_id}",
                    "kind": "new-object",
                    "confidence": "high",
                    "risk": "medium",
                    "affectedIds": [item_id],
                    "evidence": [
                        {
                            "sourceEventId": "srcevt-store-telegram-001",
                            "locator": "telegram:test#msg-001",
                            "excerpt": "Qualification notes move to sales operations.",
                        }
                    ],
                    "proposedAction": "prepare-staged-proposal",
                    "acceptedItem": {"item": self.accepted_item(item_id, kind=kind)},
                }
            )
        changes.append(
            {
                "changeId": "chg-accept-workflow",
                "kind": "new-agreement",
                "confidence": "high",
                "risk": "medium",
                "affectedIds": ["wf-lead-ready-to-meeting-booked"],
                "evidence": [
                    {
                        "sourceEventId": "srcevt-store-telegram-001",
                        "locator": "telegram:test#msg-001",
                        "excerpt": "Qualification notes move to sales operations.",
                    }
                ],
                "proposedAction": "prepare-staged-proposal",
                "acceptedWorkflow": self.accepted_workflow(),
            }
        )
        package = self.package(package_id="mcpkg-store-approved-workflow-001")
        package["changes"] = changes
        return package

    def test_initializes_empty_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            for table in [
                "accepted_items",
                "accepted_definitions",
                "accepted_attributes",
                "accepted_criteria",
                "accepted_examples",
                "accepted_workflows",
                "accepted_workflow_participants",
                "accepted_workflow_steps",
                "accepted_workflow_transitions",
                "accepted_workflow_exceptions",
                "accepted_workflow_metrics",
                "source_events",
                "model_change_packages",
                "package_source_events",
                "package_evidence",
                "package_affected_ids",
                "review_questions",
                "human_decisions",
                "source_cursors",
                "runs",
            ]:
                self.assertEqual(store.table_count(table), 0, table)

    def test_accepted_state_persists_definition_attributes_criteria_and_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            item_id = store.record_accepted_item(
                {
                    "id": "state-lead-ready-for-meeting",
                    "kind": "state",
                    "status": "accepted",
                    "name": "Ready for meeting",
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-ready-for-meeting-001",
                    "decision_id": "hdec-ready-for-meeting-001",
                    "valid_from": "2026-06-27",
                    "valid_to": None,
                    "supersedes": [],
                    "superseded_by": [],
                    "last_verified_at": "2026-06-27",
                    "confidence": "high",
                    "definitions": [
                        {
                            "definition_id": "def-ready-for-meeting",
                            "text": (
                                "A lead is ready for a meeting when interest is "
                                "confirmed, segment fit is known, and the next "
                                "contact is agreed."
                            ),
                            "source_id": "src-sales-meeting",
                            "evidence_id": "ev-ready-for-meeting-001",
                            "decision_id": "hdec-ready-for-meeting-001",
                            "status": "accepted",
                            "valid_from": "2026-06-27",
                            "valid_to": None,
                            "last_verified_at": "2026-06-27",
                            "confidence": "high",
                        }
                    ],
                    "attributes": [
                        {
                            "attribute_id": "attr-interest-confirmed",
                            "name": "interest_confirmed",
                            "value_type": "boolean",
                            "required": True,
                            "allowed_values": [],
                            "source_id": "src-sales-meeting",
                            "evidence_id": "ev-ready-for-meeting-001",
                            "decision_id": "hdec-ready-for-meeting-001",
                        },
                        {
                            "attribute_id": "attr-segment-fit",
                            "name": "segment_fit",
                            "value_type": "enum",
                            "required": True,
                            "allowed_values": ["fit", "not-fit", "unknown"],
                            "source_id": "src-sales-meeting",
                            "evidence_id": "ev-ready-for-meeting-001",
                            "decision_id": "hdec-ready-for-meeting-001",
                        },
                    ],
                    "criteria": [
                        {
                            "criterion_id": "crit-ready-interest",
                            "criterion_type": "acceptance",
                            "ordinal": 1,
                            "text": "The lead explicitly confirmed interest.",
                            "source_id": "src-sales-meeting",
                            "evidence_id": "ev-ready-for-meeting-001",
                            "decision_id": "hdec-ready-for-meeting-001",
                        },
                        {
                            "criterion_id": "crit-ready-next-contact",
                            "criterion_type": "acceptance",
                            "ordinal": 2,
                            "text": "A next contact or meeting time is agreed.",
                            "source_id": "src-sales-meeting",
                            "evidence_id": "ev-ready-for-meeting-001",
                            "decision_id": "hdec-ready-for-meeting-001",
                        },
                    ],
                    "examples": [
                        {
                            "example_id": "ex-ready-confirmed-time",
                            "example_type": "example",
                            "text": "Lead confirmed interest and agreed a meeting time.",
                            "source_id": "src-sales-meeting",
                            "evidence_id": "ev-ready-for-meeting-001",
                            "decision_id": "hdec-ready-for-meeting-001",
                        },
                        {
                            "example_id": "ex-ready-interest-only",
                            "example_type": "non_example",
                            "text": "Lead replied that it is interesting but did not agree a next step.",
                            "source_id": "src-sales-meeting",
                            "evidence_id": "ev-ready-for-meeting-001",
                            "decision_id": "hdec-ready-for-meeting-001",
                        },
                    ],
                }
            )
            item = store.get_accepted_item(item_id)

            self.assertEqual(item["id"], "state-lead-ready-for-meeting")
            self.assertEqual(item["kind"], "state")
            self.assertEqual(item["definitions"][0]["definition_id"], "def-ready-for-meeting")
            self.assertEqual(
                [attribute["name"] for attribute in item["attributes"]],
                ["interest_confirmed", "segment_fit"],
            )
            self.assertEqual(item["attributes"][1]["allowed_values"], ["fit", "not-fit", "unknown"])
            self.assertEqual(
                [criterion["criterion_id"] for criterion in item["criteria"]],
                ["crit-ready-interest", "crit-ready-next-contact"],
            )
            self.assertEqual(
                [example["example_type"] for example in item["examples"]],
                ["example", "non_example"],
            )
            self.assertEqual(store.table_count("accepted_items"), 1)
            self.assertEqual(store.table_count("accepted_definitions"), 1)
            self.assertEqual(store.table_count("accepted_attributes"), 2)
            self.assertEqual(store.table_count("accepted_criteria"), 2)
            self.assertEqual(store.table_count("accepted_examples"), 2)

    def test_accepted_workflow_persists_steps_transitions_exceptions_and_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            workflow_id = store.record_accepted_workflow(
                {
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
                        },
                        {
                            "participant_id": "wfp-sales-manager",
                            "role_id": "role-sales-manager",
                            "participant_type": "actor",
                            "source_id": "src-sales-meeting",
                            "evidence_id": "ev-workflow-ready-meeting-001",
                            "decision_id": "hdec-workflow-ready-meeting-001",
                        },
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
                        },
                        {
                            "step_id": "step-book-meeting",
                            "ordinal": 2,
                            "actor_id": "role-sales-manager",
                            "action": "Book the meeting.",
                            "input_ids": ["state-sales-handoff-created"],
                            "output_ids": ["state-meeting-booked"],
                            "source_id": "src-sales-meeting",
                            "evidence_id": "ev-workflow-ready-meeting-001",
                            "decision_id": "hdec-workflow-ready-meeting-001",
                        },
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
                        },
                        {
                            "metric_id": "metric-meeting-booking-conversion",
                            "role": "outcome",
                            "source_id": "src-sales-meeting",
                            "evidence_id": "ev-workflow-ready-meeting-001",
                            "decision_id": "hdec-workflow-ready-meeting-001",
                        },
                    ],
                }
            )
            workflow = store.get_accepted_workflow(workflow_id)

            self.assertEqual(workflow["workflow_id"], "wf-lead-ready-to-meeting-booked")
            self.assertEqual(workflow["start_state_id"], "state-lead-ready-for-meeting")
            self.assertEqual(
                [participant["role_id"] for participant in workflow["participants"]],
                ["role-leadgen-operator", "role-sales-manager"],
            )
            self.assertEqual(
                [step["step_id"] for step in workflow["steps"]],
                ["step-check-readiness", "step-book-meeting"],
            )
            self.assertEqual(
                [transition["transition_id"] for transition in workflow["transitions"]],
                ["wft-ready-to-handoff", "wft-handoff-to-booked"],
            )
            self.assertEqual(workflow["exceptions"][0]["exception_id"], "wfe-sales-no-acceptance")
            self.assertEqual(
                [metric["metric_id"] for metric in workflow["metrics"]],
                ["metric-time-to-sales-acceptance", "metric-meeting-booking-conversion"],
            )
            self.assertEqual(store.table_count("accepted_workflows"), 1)
            self.assertEqual(store.table_count("accepted_workflow_participants"), 2)
            self.assertEqual(store.table_count("accepted_workflow_steps"), 2)
            self.assertEqual(store.table_count("accepted_workflow_transitions"), 2)
            self.assertEqual(store.table_count("accepted_workflow_exceptions"), 1)
            self.assertEqual(store.table_count("accepted_workflow_metrics"), 2)

    def test_approved_package_applies_items_and_workflow_to_accepted_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            package = self.approved_package_with_workflow()
            store.record_model_change_package(package)
            store.record_human_decision(
                "hdec-workflow-ready-meeting-001",
                {
                    "packageId": package["packageId"],
                    "actor": "role:acquisition-owner",
                    "decision": "approved",
                    "reason": "The workflow is confirmed.",
                    "decidedAt": "2026-06-27T10:05:00Z",
                },
            )

            applied = store.apply_approved_model_change(package)
            workflow = store.get_accepted_workflow("wf-lead-ready-to-meeting-booked")

            self.assertEqual(applied["items"], [
                "state-lead-candidate",
                "state-lead-ready-for-meeting",
                "state-sales-handoff-created",
                "state-meeting-booked",
                "role-leadgen-operator",
                "role-sales-manager",
                "metric-time-to-sales-acceptance",
                "metric-meeting-booking-conversion",
            ])
            self.assertEqual(applied["workflows"], ["wf-lead-ready-to-meeting-booked"])
            self.assertEqual(workflow["workflow_id"], "wf-lead-ready-to-meeting-booked")
            self.assertEqual([step["step_id"] for step in workflow["steps"]], [
                "step-check-readiness",
                "step-book-meeting",
            ])
            self.assertEqual(store.table_count("accepted_items"), 8)
            self.assertEqual(store.table_count("accepted_workflows"), 1)
            self.assertEqual(store.list_pending_packages(), [])

    def test_unapproved_package_cannot_apply_accepted_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            package = self.approved_package_with_workflow()
            store.record_model_change_package(package)

            with self.assertRaisesRegex(ValueError, "not approved"):
                store.apply_approved_model_change(package)

            self.assertEqual(store.table_count("accepted_workflows"), 0)

    def test_workflow_ref_validation_reports_missing_accepted_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            workflow = self.accepted_workflow()
            workflow["workflow"]["end_state_id"] = "state-missing"

            missing = store.validate_workflow_refs(workflow)

            self.assertIn("workflow.end_state_id=state-missing", missing)
            self.assertIn("participant.role_id=role-leadgen-operator", missing)

    def test_apply_refuses_workflow_with_missing_refs(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            package = self.approved_package_with_workflow()
            package["changes"][-1]["acceptedWorkflow"]["workflow"]["end_state_id"] = "state-missing"
            store.record_model_change_package(package)
            store.record_human_decision(
                "hdec-workflow-ready-meeting-001",
                {
                    "packageId": package["packageId"],
                    "actor": "role:acquisition-owner",
                    "decision": "approved",
                    "reason": "The workflow is confirmed.",
                    "decidedAt": "2026-06-27T10:05:00Z",
                },
            )

            with self.assertRaisesRegex(ValueError, "workflow refs do not resolve"):
                store.apply_approved_model_change(package)

            self.assertEqual(store.table_count("accepted_workflows"), 0)

    def test_source_event_insert_is_idempotent_by_event_id_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            event = self.source_event()

            first = store.record_source_event(event)
            second = store.record_source_event({**event, "sourceId": "src-other"})
            by_hash = store.record_source_event(
                self.source_event(
                    event_id="srcevt-store-telegram-duplicate",
                    event_hash=event["hash"],
                )
            )

            self.assertEqual(first, event["eventId"])
            self.assertEqual(second, event["eventId"])
            self.assertEqual(by_hash, event["eventId"])
            self.assertTrue(store.source_event_seen(event["eventId"], event["hash"]))
            self.assertTrue(
                store.source_event_seen("srcevt-store-telegram-missing", event["hash"])
            )
            self.assertEqual(store.table_count("source_events"), 1)

    def test_package_insert_saves_links_and_lists_pending_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            package_id = store.record_model_change_package(self.package())
            pending = store.list_pending_packages()

            self.assertEqual(package_id, "mcpkg-store-handoff-001")
            self.assertEqual([item["packageId"] for item in pending], [package_id])
            self.assertEqual(pending[0]["reviewAction"], "human-review")
            self.assertEqual(pending[0]["affectedIds"], ["if-acquisition-sales-handoff", "unknown"])
            self.assertNotIn("changes", pending[0])
            self.assertEqual(store.table_count("model_change_packages"), 1)
            self.assertEqual(store.table_count("package_source_events"), 1)
            self.assertEqual(store.table_count("package_evidence"), 1)
            self.assertEqual(store.table_count("package_affected_ids"), 2)

    def test_no_review_needed_package_is_not_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            store.record_model_change_package(
                self.package(package_id="mcpkg-store-noop-001", action="no-review-needed")
            )

            self.assertEqual(store.list_pending_packages(), [])
            self.assertEqual(store.table_count("model_change_packages"), 1)

    def test_human_decision_updates_package_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            package = self.package()
            store.record_model_change_package(package)

            decision_id = store.record_human_decision(
                "hdec-store-handoff-001",
                {
                    "packageId": package["packageId"],
                    "actor": "role:acquisition-owner",
                    "decision": "approved",
                    "reason": "The handoff is confirmed.",
                    "decidedAt": "2026-06-22T10:05:00Z",
                },
            )
            pending = store.list_pending_packages()

            self.assertEqual(decision_id, "hdec-store-handoff-001")
            self.assertEqual(store.table_count("human_decisions"), 1)
            self.assertEqual(pending, [])

    def test_duplicate_package_insert_does_not_erase_human_decision_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            package = self.package()
            store.record_model_change_package(package)
            store.record_human_decision(
                "hdec-store-handoff-001",
                {
                    "packageId": package["packageId"],
                    "actor": "role:acquisition-owner",
                    "decision": "approved",
                    "reason": "The handoff is confirmed.",
                    "decidedAt": "2026-06-22T10:05:00Z",
                },
            )

            store.record_model_change_package(package)

            self.assertEqual(store.list_pending_packages(), [])

    def test_open_questions_are_bounded_and_ordered(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            package_id = store.record_model_change_package(self.package())
            store._connection.executemany(
                """
                INSERT INTO review_questions (
                    question_id, package_id, status, prompt, recommendation,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "q-store-002",
                        package_id,
                        "open",
                        "Which owner approves the handoff?",
                        "Use role:acquisition-owner unless source evidence disagrees.",
                        "2026-06-22T10:01:00Z",
                        "2026-06-22T10:03:00Z",
                    ),
                    (
                        "q-store-001",
                        package_id,
                        "resolved",
                        "Resolved question.",
                        "No action.",
                        "2026-06-22T10:01:00Z",
                        "2026-06-22T10:02:00Z",
                    ),
                ],
            )
            store._connection.commit()

            questions = store.list_open_questions(limit=1)

            self.assertEqual(len(questions), 1)
            self.assertEqual(questions[0]["question_id"], "q-store-002")

    def test_cursor_upsert_replaces_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            store.upsert_source_cursor("src-telegram-acquisition", "daily", "msg-001")
            store.upsert_source_cursor("src-telegram-acquisition", "daily", "msg-002")
            cursor = store.get_source_cursor("src-telegram-acquisition", "daily")

            self.assertEqual(store.table_count("source_cursors"), 1)
            self.assertEqual(cursor["cursor_value"], "msg-002")

    def test_run_record_persists_bounded_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            run_id = store.record_run(
                {
                    "runId": "run-store-001",
                    "status": "succeeded",
                    "startedAt": "2026-06-22T10:00:00Z",
                    "finishedAt": "2026-06-22T10:01:00Z",
                    "summary": {"events_seen": 3, "packages_written": 1},
                }
            )
            row = store._connection.execute(
                "SELECT summary_json FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            summary = json.loads(row["summary_json"])

            self.assertEqual(run_id, "run-store-001")
            self.assertEqual(store.table_count("runs"), 1)
            self.assertEqual(summary["packages_written"], 1)

    def test_pending_package_query_is_bounded_and_summary_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            for index in range(125):
                package = self.package(package_id=f"mcpkg-store-bulk-{index:03d}")
                package["summary"] = f"Bulk review package {index:03d}."
                store.record_model_change_package(package)

            default_pending = store.list_pending_packages()
            limited_pending = store.list_pending_packages(limit=7)
            all_pending_count = store.count_pending_packages()
            serialized = json.dumps(default_pending, sort_keys=True)

        self.assertEqual(len(default_pending), 50)
        self.assertEqual(len(limited_pending), 7)
        self.assertEqual(all_pending_count, 125)
        self.assertEqual(
            [item["packageId"] for item in limited_pending],
            [f"mcpkg-store-bulk-{index:03d}" for index in range(7)],
        )
        self.assertNotIn("changes", serialized)
        self.assertNotIn("candidateCard", serialized)
        self.assertNotIn("raw_payload", serialized)
        self.assertNotIn("rawPayload", serialized)
        self.assertTrue(all(item["stale"] is False for item in default_pending))


if __name__ == "__main__":
    unittest.main()

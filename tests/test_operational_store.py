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
            "claimKind": "owner-claim",
            "evidenceGrade": "claim",
            "sourceRisk": ["manual-memory"],
            "provenanceActivity": {
                "activityType": "manual-export",
                "actor": "synthetic-test-connector",
                "actorType": "connector",
                "createdAt": "2026-06-22T10:00:00Z",
                "sourceLocator": "telegram:test#msg-001",
                "method": "Synthetic redacted store test event.",
            },
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

    def change_claim_metadata(self):
        return {
            "claimKind": "owner-claim",
            "evidenceGrade": "claim",
            "sourceRisk": ["manual-memory"],
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
                    **self.change_claim_metadata(),
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
                    **self.change_claim_metadata(),
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
                **self.change_claim_metadata(),
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
                "accepted_data_bindings",
                "accepted_instances",
                "accepted_instance_relations",
                "source_events",
                "model_change_packages",
                "package_source_events",
                "package_evidence",
                "package_affected_ids",
                "human_requests",
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

    def test_recording_a_changed_item_supersedes_the_prior_version_instead_of_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            item_v1 = self.accepted_item("state-lead-ready-for-meeting", kind="state")
            item_v1["name"] = "Ready for meeting (v1)"
            store.record_accepted_item(item_v1)

            item_v2 = self.accepted_item("state-lead-ready-for-meeting", kind="state")
            item_v2["name"] = "Ready for meeting (v2)"
            store.record_accepted_item(item_v2)

            current = store.get_accepted_item("state-lead-ready-for-meeting")
            self.assertEqual(current["name"], "Ready for meeting (v2)")

            history = store.get_item_history("state-lead-ready-for-meeting")
            self.assertEqual(len(history), 2)
            names_oldest_first = [version["name"] for version in history]
            self.assertEqual(names_oldest_first, ["Ready for meeting (v1)", "Ready for meeting (v2)"])

            v1, v2 = history
            self.assertIsNotNone(v1["valid_to"])
            self.assertEqual(v1["superseded_by"], v2["version_id"])
            self.assertEqual(v2["supersedes"], v1["version_id"])
            self.assertIsNone(v2["valid_to"])

    def test_recording_an_identical_item_twice_does_not_create_a_new_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            item = self.accepted_item("state-lead-ready-for-meeting", kind="state")
            store.record_accepted_item(item)
            store.record_accepted_item(dict(item))

            history = store.get_item_history("state-lead-ready-for-meeting")
            self.assertEqual(len(history), 1)

    def test_recording_a_changed_workflow_supersedes_the_prior_version_instead_of_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            workflow_v1 = self.accepted_workflow()["workflow"]
            workflow_v1["owner"] = "module-leadgen"
            store.record_accepted_workflow(workflow_v1)

            workflow_v2 = self.accepted_workflow()["workflow"]
            workflow_v2["owner"] = "module-acquisition"
            store.record_accepted_workflow(workflow_v2)

            current = store.get_accepted_workflow("wf-lead-ready-to-meeting-booked")
            self.assertEqual(current["owner"], "module-acquisition")

            history = store.get_workflow_history("wf-lead-ready-to-meeting-booked")
            self.assertEqual(len(history), 2)
            owners_oldest_first = [version["owner"] for version in history]
            self.assertEqual(owners_oldest_first, ["module-leadgen", "module-acquisition"])

            v1, v2 = history
            self.assertIsNotNone(v1["valid_to"])
            self.assertEqual(v1["superseded_by"], v2["version_id"])
            self.assertEqual(v2["supersedes"], v1["version_id"])
            self.assertIsNone(v2["valid_to"])

    def test_recording_an_identical_workflow_twice_does_not_create_a_new_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            workflow = self.accepted_workflow()["workflow"]
            store.record_accepted_workflow(workflow)
            store.record_accepted_workflow(dict(workflow))

            history = store.get_workflow_history("wf-lead-ready-to-meeting-booked")
            self.assertEqual(len(history), 1)

    def test_child_rows_keep_resolving_to_accepted_items_without_sqlite_fk(self):
        """Guards the integrity the dropped FOREIGN KEY clauses used to promise."""

        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            item = self.accepted_item("state-lead-ready-for-meeting", kind="state")
            item["definitions"] = [
                {
                    "definition_id": "def-ready-for-meeting",
                    "text": "A lead is ready when the next contact is agreed.",
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-workflow-ready-meeting-001",
                    "decision_id": "hdec-workflow-ready-meeting-001",
                    "status": "accepted",
                    "valid_from": "2026-06-27",
                    "valid_to": None,
                    "last_verified_at": "2026-06-27",
                    "confidence": "high",
                }
            ]
            item["attributes"] = [
                {
                    "attribute_id": "attr-interest-confirmed",
                    "name": "interest_confirmed",
                    "value_type": "boolean",
                    "required": True,
                    "allowed_values": [],
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-workflow-ready-meeting-001",
                    "decision_id": "hdec-workflow-ready-meeting-001",
                }
            ]
            item["criteria"] = [
                {
                    "criterion_id": "crit-ready-interest",
                    "criterion_type": "acceptance",
                    "ordinal": 1,
                    "text": "The lead explicitly confirmed interest.",
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-workflow-ready-meeting-001",
                    "decision_id": "hdec-workflow-ready-meeting-001",
                }
            ]
            item["examples"] = [
                {
                    "example_id": "ex-ready-confirmed-time",
                    "example_type": "example",
                    "text": "Lead confirmed interest and agreed a meeting time.",
                    "source_id": "src-sales-meeting",
                    "evidence_id": "ev-workflow-ready-meeting-001",
                    "decision_id": "hdec-workflow-ready-meeting-001",
                }
            ]
            store.record_accepted_item(item)
            changed = json.loads(json.dumps(item))
            changed["name"] = "Ready for meeting (renamed)"
            store.record_accepted_item(changed)

            connection = store._connection
            for table in [
                "accepted_definitions",
                "accepted_attributes",
                "accepted_criteria",
                "accepted_examples",
            ]:
                orphans = connection.execute(
                    f"""
                    SELECT child.item_id
                      FROM {table} AS child
                     WHERE NOT EXISTS (
                            SELECT 1
                              FROM accepted_items AS items
                             WHERE items.item_id = child.item_id
                           )
                    """
                ).fetchall()
                self.assertEqual([dict(row) for row in orphans], [], table)

            binding_orphans = connection.execute(
                """
                SELECT sql FROM sqlite_master
                 WHERE type = 'table' AND name LIKE 'accepted_%' AND sql LIKE '%REFERENCES accepted_items%'
                """
            ).fetchall()
            self.assertEqual([dict(row) for row in binding_orphans], [])

    def test_data_binding_and_instance_reject_unknown_item_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            with self.assertRaisesRegex(ValueError, "unknown accepted item"):
                store.record_data_binding(
                    {
                        "binding_id": "bind-nowhere",
                        "item_id": "state-does-not-exist",
                        "property_name": "status",
                        "source_id": "src-crm",
                        "source_kind": "crm-export",
                        "source_locator": "crm:deals",
                        "source_field": "STATUS_ID",
                        "value_type": "string",
                        "key_field": "ID",
                        "refresh_policy": "manual",
                    }
                )
            with self.assertRaisesRegex(ValueError, "unknown accepted item"):
                store.record_instance(
                    {
                        "instance_id": "inst-nowhere",
                        "item_id": "state-does-not-exist",
                        "label": "Nowhere",
                        "status": "accepted",
                        "source_id": "src-crm",
                        "evidence_id": "ev-inst",
                        "decision_id": "hdec-inst",
                        "attributes": {},
                    }
                )

    def test_legacy_store_layout_migrates_to_versioned_schema(self):
        """A pre-versioning database (id primary keys + child FKs) is rebuilt in place."""

        import sqlite3

        from runtime.operational_store import OperationalStore

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state" / "operational.sqlite3"
            db_path.parent.mkdir(parents=True)
            legacy = sqlite3.connect(db_path)
            legacy.executescript(
                """
                CREATE TABLE accepted_items (
                    item_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    name TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    valid_from TEXT NOT NULL,
                    valid_to TEXT,
                    last_verified_at TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE accepted_definitions (
                    definition_id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    text TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    valid_from TEXT NOT NULL,
                    valid_to TEXT,
                    last_verified_at TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (item_id) REFERENCES accepted_items(item_id)
                        ON DELETE CASCADE
                );
                CREATE TABLE accepted_instances (
                    instance_id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    attributes_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (item_id) REFERENCES accepted_items(item_id)
                        ON DELETE CASCADE
                );
                CREATE TABLE accepted_instance_relations (
                    relation_id TEXT PRIMARY KEY,
                    from_instance_id TEXT NOT NULL,
                    to_instance_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (from_instance_id) REFERENCES accepted_instances(instance_id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (to_instance_id) REFERENCES accepted_instances(instance_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX idx_accepted_items_kind
                    ON accepted_items(kind, status, item_id);
                CREATE INDEX idx_accepted_definitions_item
                    ON accepted_definitions(item_id, definition_id);
                """
            )
            item_payload = json.dumps(
                {
                    "id": "state-lead-ready",
                    "kind": "state",
                    "status": "accepted",
                    "name": "Lead ready",
                    "source_id": "src-crm",
                    "evidence_id": "ev-ready",
                    "decision_id": "hdec-ready",
                    "valid_from": "2026-06-01",
                    "valid_to": None,
                    "last_verified_at": "2026-06-01",
                    "confidence": "high",
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            legacy.execute(
                """
                INSERT INTO accepted_items VALUES
                ('state-lead-ready', 'state', 'accepted', 'Lead ready', 'src-crm',
                 'ev-ready', 'hdec-ready', '2026-06-01', NULL, '2026-06-01', 'high',
                 ?, '2026-06-01T00:00:00Z', '2026-06-01T00:00:00Z')
                """,
                (item_payload,),
            )
            legacy.execute(
                """
                INSERT INTO accepted_definitions VALUES
                ('def-lead-ready', 'state-lead-ready', 'accepted', 'A ready lead.',
                 'src-crm', 'ev-ready', 'hdec-ready', '2026-06-01', NULL,
                 '2026-06-01', 'high', '{"definition_id": "def-lead-ready"}',
                 '2026-06-01T00:00:00Z', '2026-06-01T00:00:00Z')
                """
            )
            legacy.execute(
                """
                INSERT INTO accepted_instances VALUES
                ('inst-deal-1', 'state-lead-ready', 'Deal 1', 'accepted', 'src-crm',
                 'ev-inst', 'hdec-inst', '{}', '{"instance_id": "inst-deal-1"}',
                 '2026-06-01T00:00:00Z', '2026-06-01T00:00:00Z'),
                ('inst-deal-2', 'state-lead-ready', 'Deal 2', 'accepted', 'src-crm',
                 'ev-inst', 'hdec-inst', '{}', '{"instance_id": "inst-deal-2"}',
                 '2026-06-01T00:00:00Z', '2026-06-01T00:00:00Z')
                """
            )
            legacy.execute(
                """
                INSERT INTO accepted_instance_relations VALUES
                ('rel-1', 'inst-deal-1', 'inst-deal-2', 'related-to', 'src-crm',
                 'ev-rel', 'hdec-rel', '{"relation_id": "rel-1"}',
                 '2026-06-01T00:00:00Z', '2026-06-01T00:00:00Z')
                """
            )
            legacy.commit()
            legacy.close()

            store = OperationalStore.connect(db_path)
            store.initialize()
            self.addCleanup(store.close)

            migrated = store.get_accepted_item("state-lead-ready")
            self.assertEqual(migrated["name"], "Lead ready")
            self.assertEqual(migrated["definitions"][0]["definition_id"], "def-lead-ready")
            history = store.get_item_history("state-lead-ready")
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["version_id"], "state-lead-ready#v1")
            self.assertEqual(store.table_count("accepted_instances"), 2)
            self.assertEqual(store.table_count("accepted_instance_relations"), 1)

            connection = store._connection
            legacy_fk_tables = connection.execute(
                """
                SELECT name FROM sqlite_master
                 WHERE type = 'table'
                   AND (sql LIKE '%REFERENCES accepted_items%'
                        OR sql LIKE '%REFERENCES accepted_workflows%')
                """
            ).fetchall()
            self.assertEqual([str(row["name"]) for row in legacy_fk_tables], [])
            leftovers = connection.execute(
                "SELECT name FROM sqlite_master WHERE name LIKE '%__legacy'"
            ).fetchall()
            self.assertEqual([str(row["name"]) for row in leftovers], [])
            index_owner = connection.execute(
                """
                SELECT tbl_name FROM sqlite_master
                 WHERE type = 'index' AND name = 'idx_accepted_items_kind'
                """
            ).fetchone()
            self.assertEqual(str(index_owner["tbl_name"]), "accepted_items")

            updated = json.loads(item_payload)
            updated["name"] = "Lead ready (renamed)"
            store.record_accepted_item(updated)
            history = store.get_item_history("state-lead-ready")
            self.assertEqual(
                [version["version_id"] for version in history],
                ["state-lead-ready#v1", "state-lead-ready#v2"],
            )
            self.assertEqual(history[0]["superseded_by"], "state-lead-ready#v2")

    def test_workflow_value_context_persists_and_validates_refs(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            for item_id, kind in [
                ("state-lead-ready-for-meeting", "state"),
                ("state-meeting-booked", "state"),
                ("vst-sales-ready-handoff", "valueStage"),
                ("bo-prospective-participant", "businessObject"),
            ]:
                store.record_accepted_item(
                    {
                        "id": item_id,
                        "name": item_id,
                        "kind": kind,
                        "status": "accepted",
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
                )
            workflow = {
                "workflow_id": "wf-lead-ready-to-meeting-booked",
                "name": "Lead ready to meeting booked",
                "status": "accepted",
                "owner": "module-leadgen",
                "source_id": "src-sales-meeting",
                "evidence_id": "ev-workflow-ready-meeting-001",
                "decision_id": "hdec-workflow-ready-meeting-001",
                "start_state_id": "state-lead-ready-for-meeting",
                "end_state_id": "state-meeting-booked",
                "value_stage_id": "vst-sales-ready-handoff",
                "business_object_ids": ["bo-prospective-participant"],
                "valid_from": "2026-06-27",
                "valid_to": None,
                "last_verified_at": "2026-06-27",
                "confidence": "high",
            }

            self.assertEqual(store.validate_workflow_refs(workflow), [])
            workflow_id = store.record_accepted_workflow(workflow)
            saved = store.get_accepted_workflow(workflow_id)
            missing_workflow = dict(workflow)
            missing_workflow["value_stage_id"] = "vst-missing"
            missing_workflow["business_object_ids"] = ["bo-missing"]

            self.assertEqual(saved["value_stage_id"], "vst-sales-ready-handoff")
            self.assertEqual(saved["business_object_ids"], ["bo-prospective-participant"])
            missing = store.validate_workflow_refs(missing_workflow)
            self.assertIn("workflow.value_stage_id=vst-missing", missing)
            self.assertIn("workflow.business_object_ids=bo-missing", missing)

    def test_data_binding_records_are_queryable_without_raw_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            store.record_accepted_item(self.accepted_item("state-lead-ready-for-meeting", kind="state"))

            binding_id = store.record_data_binding(
                {
                    "binding_id": "bind-lead-ready-status",
                    "item_id": "state-lead-ready-for-meeting",
                    "property_name": "status",
                    "source_id": "src-crm",
                    "source_kind": "crm-export",
                    "source_locator": "crm:deals",
                    "source_field": "STATUS_ID",
                    "value_type": "string",
                    "key_field": "ID",
                    "refresh_policy": "manual",
                }
            )
            bindings = store.list_data_bindings()

            self.assertEqual(binding_id, "bind-lead-ready-status")
            self.assertEqual(bindings[0]["item_id"], "state-lead-ready-for-meeting")
            self.assertEqual(bindings[0]["source_field"], "STATUS_ID")
            self.assertNotIn("raw_value", bindings[0])
            self.assertEqual(store.table_count("accepted_data_bindings"), 1)

            unsafe = dict(bindings[0])
            unsafe["binding_id"] = "bind-unsafe"
            unsafe["raw_value"] = "private source row"
            with self.assertRaisesRegex(ValueError, "raw"):
                store.record_data_binding(unsafe)

    def test_instance_graph_records_and_queries_bounded_neighborhood(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            store.record_accepted_item(self.accepted_item("deal", kind="entity"))

            store.record_instance(
                {
                    "instance_id": "inst-deal-1",
                    "item_id": "deal",
                    "label": "Deal 1",
                    "status": "accepted",
                    "source_id": "src-crm",
                    "evidence_id": "ev-deal-1",
                    "decision_id": "hdec-deal-1",
                    "attributes": {"stage": "ready"},
                }
            )
            store.record_instance(
                {
                    "instance_id": "inst-deal-2",
                    "item_id": "deal",
                    "label": "Deal 2",
                    "status": "accepted",
                    "source_id": "src-crm",
                    "evidence_id": "ev-deal-2",
                    "decision_id": "hdec-deal-2",
                    "attributes": {"stage": "booked", "raw_payload": "must be dropped"},
                }
            )
            relation_id = store.record_instance_relation(
                {
                    "relation_id": "irel-deal-1-next",
                    "from_instance_id": "inst-deal-1",
                    "to_instance_id": "inst-deal-2",
                    "relation_type": "next-state",
                    "source_id": "src-crm",
                    "evidence_id": "ev-rel",
                    "decision_id": "hdec-rel",
                }
            )

            graph = store.query_instance_graph(root_id="inst-deal-1", limit=10)

            self.assertEqual(relation_id, "irel-deal-1-next")
            self.assertEqual([node["instance_id"] for node in graph["instances"]], [
                "inst-deal-1",
                "inst-deal-2",
            ])
            self.assertEqual(graph["relations"][0]["relation_id"], "irel-deal-1-next")
            self.assertNotIn("raw_payload", graph["instances"][1]["attributes"])
            self.assertFalse(graph["truncated"])
            self.assertEqual(store.table_count("accepted_instances"), 2)
            self.assertEqual(store.table_count("accepted_instance_relations"), 1)

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

    def test_pending_package_summary_computes_stale_from_current_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            store.record_model_change_package(self.package())

            against_other = store.list_pending_packages(current_revision="store:other")
            against_same = store.list_pending_packages(current_revision="store:test")
            without_revision = store.list_pending_packages()

            self.assertIs(against_other[0]["stale"], True)
            self.assertIs(against_same[0]["stale"], False)
            self.assertIs(without_revision[0]["stale"], False)

    def test_apply_refuses_approved_but_stale_package_unless_allowed(self):
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

            with self.assertRaisesRegex(ValueError, "stale"):
                store.apply_approved_model_change(package, current_revision="store:other")
            self.assertEqual(store.table_count("accepted_workflows"), 0)

            applied = store.apply_approved_model_change(
                package, current_revision="store:other", allow_stale=True
            )

            self.assertEqual(applied["workflows"], ["wf-lead-ready-to-meeting-booked"])

    def test_apply_accepts_package_matching_current_revision(self):
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

            applied = store.apply_approved_model_change(
                package, current_revision="store:test"
            )

            self.assertEqual(applied["workflows"], ["wf-lead-ready-to-meeting-booked"])

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

    def test_source_event_rejects_schema_invalid_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            missing_segment = self.source_event()
            missing_segment["evidence"] = [
                {
                    "locator": "telegram:test#msg-001",
                    "excerpt": "Qualification notes move to sales operations.",
                }
            ]
            with_raw_payload = {
                **self.source_event(
                    event_id="srcevt-store-telegram-raw-payload",
                    event_hash="sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                ),
                "rawPayload": {"message": "raw source body must not be stored"},
            }

            with self.assertRaisesRegex(ValueError, "segmentType"):
                store.record_source_event(missing_segment)
            with self.assertRaisesRegex(ValueError, "unexpected field"):
                store.record_source_event(with_raw_payload)

            self.assertEqual(store.table_count("source_events"), 0)

    def test_package_insert_saves_links_and_lists_pending_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)

            package_id = store.record_model_change_package(self.package())
            pending = store.list_pending_packages()

            self.assertEqual(package_id, "mcpkg-store-handoff-001")
            self.assertEqual([item["packageId"] for item in pending], [package_id])
            self.assertEqual(pending[0]["reviewAction"], "human-review")
            self.assertEqual(pending[0]["status"], "pending")
            self.assertEqual(pending[0]["owner"], "role:acquisition-owner")
            self.assertIn("createdAt", pending[0])
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

            row = store._connection.execute(
                "SELECT status FROM model_change_packages WHERE package_id = ?",
                ("mcpkg-store-noop-001",),
            ).fetchone()

            self.assertEqual(str(row["status"]), "no-op")
            self.assertEqual(store.list_pending_packages(), [])
            self.assertEqual(store.table_count("model_change_packages"), 1)

    def test_legacy_no_review_needed_status_migrates_to_no_op_on_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            package = self.package(package_id="mcpkg-store-legacy-noop-001", action="no-review-needed")
            store.record_model_change_package(package)
            store._connection.execute(
                "UPDATE model_change_packages SET status = ? WHERE package_id = ?",
                ("no-review-needed", package["packageId"]),
            )
            store._connection.commit()

            store.record_model_change_package(package)
            rewritten = self.package(
                package_id="mcpkg-store-legacy-noop-001",
                action="no-review-needed",
            )
            rewritten["summary"] = "Changed legacy no-op package."
            row = store._connection.execute(
                "SELECT status FROM model_change_packages WHERE package_id = ?",
                (package["packageId"],),
            ).fetchone()

            self.assertEqual(str(row["status"]), "no-op")
            with self.assertRaisesRegex(ValueError, "cannot rewrite reviewed model change package"):
                store.record_model_change_package(rewritten)

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

    def test_reviewed_package_payload_cannot_be_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            package = self.package()
            store.record_model_change_package(package)
            store.record_human_decision(
                "hdec-store-handoff-immutable",
                {
                    "packageId": package["packageId"],
                    "actor": "role:acquisition-owner",
                    "decision": "approved",
                    "reason": "The handoff is confirmed.",
                    "decidedAt": "2026-06-22T10:05:00Z",
                },
            )
            rewritten = self.package()
            rewritten["summary"] = "Rewritten after approval."
            rewritten["changes"][0]["evidence"][0]["excerpt"] = "Different evidence."

            with self.assertRaisesRegex(ValueError, "cannot rewrite reviewed model change package"):
                store.record_model_change_package(rewritten)

            row = store._connection.execute(
                "SELECT payload_json, status FROM model_change_packages WHERE package_id = ?",
                (package["packageId"],),
            ).fetchone()
            stored_payload = json.loads(row["payload_json"])

            self.assertEqual(str(row["status"]), "approved")
            self.assertEqual(stored_payload["summary"], package["summary"])
            self.assertEqual(store.table_count("package_evidence"), 1)

    def test_human_decision_id_cannot_be_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            package = self.package()
            store.record_model_change_package(package)
            store.record_human_decision(
                "hdec-store-handoff-immutable",
                {
                    "packageId": package["packageId"],
                    "actor": "role:acquisition-owner",
                    "decision": "approved",
                    "reason": "The handoff is confirmed.",
                    "decidedAt": "2026-06-22T10:05:00Z",
                },
            )

            with self.assertRaisesRegex(ValueError, "cannot rewrite human decision"):
                store.record_human_decision(
                    "hdec-store-handoff-immutable",
                    {
                        "packageId": package["packageId"],
                        "actor": "role:acquisition-owner",
                        "decision": "rejected",
                        "reason": "Changed after the fact.",
                        "decidedAt": "2026-06-22T10:06:00Z",
                    },
                )

            row = store._connection.execute(
                "SELECT decision, reason FROM human_decisions WHERE decision_id = ?",
                ("hdec-store-handoff-immutable",),
            ).fetchone()

            self.assertEqual(str(row["decision"]), "approved")
            self.assertEqual(str(row["reason"]), "The handoff is confirmed.")

    def test_human_requests_are_recorded_listed_and_answered(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            package_id = store.record_model_change_package(self.package())

            request_id = store.record_human_request(
                {
                    "requestId": "hreq-store-owner-002",
                    "kind": "review",
                    "owner": "role:acquisition-owner",
                    "channel": "telegram:dm-owner",
                    "messageRef": "telegram:dm-owner#msg-42",
                    "prompt": "Which owner approves the handoff?",
                    "recommendedAnswer": "Use role:acquisition-owner unless source evidence disagrees.",
                    "blocks": ["promotion:mcpkg-store-handoff-001"],
                    "sourceRef": "srcevt-store-telegram-001",
                    "packageId": package_id,
                    "askedAt": "2026-06-22T10:03:00Z",
                    "dueAt": "2026-06-23T09:00:00Z",
                }
            )

            self.assertEqual(request_id, "hreq-store-owner-002")
            requests = store.list_open_human_requests(limit=1)

            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0]["requestId"], "hreq-store-owner-002")
            self.assertEqual(requests[0]["recommendedAnswer"], "Use role:acquisition-owner unless source evidence disagrees.")
            self.assertEqual(requests[0]["blocks"], ["promotion:mcpkg-store-handoff-001"])
            self.assertEqual(requests[0]["messageRef"], "telegram:dm-owner#msg-42")

            by_message = store.find_human_request_by_message_ref(
                "telegram:dm-owner",
                "telegram:dm-owner#msg-42",
            )
            self.assertEqual(by_message["requestId"], "hreq-store-owner-002")

            store.mark_human_request_answered(
                "hreq-store-owner-002",
                answer_summary="Owner confirmed acquisition owner.",
                decision_id="hdec-store-owner-002",
                answered_at="2026-06-22T10:05:00Z",
            )
            self.assertEqual(store.list_open_human_requests(), [])
            closed = store.get_human_request("hreq-store-owner-002")
            self.assertEqual(closed["status"], "answered")
            self.assertEqual(closed["answerSummary"], "Owner confirmed acquisition owner.")

    def test_human_requests_filter_by_kind_and_owner_and_are_due_ordered(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            store.record_human_request(
                {
                    "requestId": "hreq-store-setup",
                    "kind": "setup",
                    "owner": "owner",
                    "channel": "telegram:dm-owner",
                    "prompt": "Connect the model repo?",
                    "recommendedAnswer": "Use a separate private repo.",
                    "askedAt": "2026-06-22T10:00:00Z",
                    "dueAt": "2026-06-24T09:00:00Z",
                }
            )
            store.record_human_request(
                {
                    "requestId": "hreq-store-live-proof",
                    "kind": "live-proof",
                    "owner": "owner",
                    "channel": "telegram:dm-owner",
                    "prompt": "Approve live proof run?",
                    "recommendedAnswer": "Run after public webhook is configured.",
                    "askedAt": "2026-06-22T10:01:00Z",
                    "dueAt": "2026-06-23T09:00:00Z",
                }
            )

            requests = store.list_open_human_requests(owner="owner", kind="live-proof")

            self.assertEqual([item["requestId"] for item in requests], ["hreq-store-live-proof"])
            ordered = store.list_open_human_requests()
            self.assertEqual(
                [item["requestId"] for item in ordered],
                ["hreq-store-live-proof", "hreq-store-setup"],
            )

    def test_human_request_payload_is_immutable_until_status_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            request = {
                "requestId": "hreq-store-immutable",
                "kind": "clarification",
                "owner": "owner",
                "channel": "telegram:group",
                "prompt": "Is this a production rule?",
                "recommendedAnswer": "Treat it as candidate until owner confirms.",
            }
            store.record_human_request(request)
            self.assertEqual(store.record_human_request(request), "hreq-store-immutable")

            changed = {**request, "prompt": "Different question?"}
            with self.assertRaisesRegex(ValueError, "cannot rewrite human request"):
                store.record_human_request(changed)

    def test_provisional_human_request_reference_binds_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            store.record_human_request(
                {
                    "requestId": "hreq-store-pending",
                    "kind": "review",
                    "owner": "owner",
                    "channel": "telegram:dm-owner",
                    "messageRef": "pending:hreq-store-pending",
                    "prompt": "Apply the current recommendation?",
                    "recommendedAnswer": "Apply this one recommendation.",
                }
            )

            store.bind_human_request_message_ref(
                "hreq-store-pending",
                message_ref="telegram:dm-owner:139",
            )

            request = store.get_human_request("hreq-store-pending")
            self.assertEqual(request["messageRef"], "telegram:dm-owner:139")
            with self.assertRaisesRegex(ValueError, "no provisional message ref"):
                store.bind_human_request_message_ref(
                    "hreq-store-pending",
                    message_ref="telegram:dm-owner:141",
                )

    def test_cancel_human_request_closes_only_an_open_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(tmp)
            store.record_human_request(
                {
                    "requestId": "hreq-store-obsolete",
                    "kind": "clarification",
                    "owner": "owner",
                    "channel": "telegram:dm-owner",
                    "prompt": "Obsolete clarification?",
                    "recommendedAnswer": "No longer needed.",
                }
            )

            store.cancel_human_request(
                "hreq-store-obsolete",
                reason="Superseded after deterministic reply correlation was repaired.",
            )

            request = store.get_human_request("hreq-store-obsolete")
            self.assertEqual(request["status"], "cancelled")
            self.assertIn("correlation", request["answerSummary"])
            with self.assertRaisesRegex(ValueError, "cannot cancel closed"):
                store.cancel_human_request("hreq-store-obsolete", reason="Replay")

    def test_legacy_review_questions_are_migrated_and_removed(self):
        import sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state" / "operational.sqlite3"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(db_path)
            try:
                connection.executescript(
                    """
                    CREATE TABLE model_change_packages (
                        package_id TEXT PRIMARY KEY,
                        module_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        risk TEXT NOT NULL,
                        review_action TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE review_questions (
                        question_id TEXT PRIMARY KEY,
                        package_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        prompt TEXT NOT NULL,
                        recommendation TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    INSERT INTO model_change_packages VALUES (
                        'mcpkg-legacy', 'acquisition', 'pending', 'medium',
                        'human-review', '{}',
                        '2026-06-22T10:00:00Z', '2026-06-22T10:00:00Z'
                    );
                    INSERT INTO review_questions VALUES (
                        'q-legacy-owner', 'mcpkg-legacy', 'open',
                        'Which owner approves it?',
                        'Use role:acquisition-owner unless source evidence disagrees.',
                        '2026-06-22T10:01:00Z', '2026-06-22T10:03:00Z'
                    );
                    """
                )
                connection.commit()
            finally:
                connection.close()

            from runtime.operational_store import OperationalStore

            store = OperationalStore.connect(db_path)
            self.addCleanup(store.close)
            store.initialize()

            tables = {
                str(row["name"])
                for row in store._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            self.assertNotIn("review_questions", tables)
            requests = store.list_open_human_requests()
            self.assertEqual([item["requestId"] for item in requests], ["hreq-q-legacy-owner"])
            self.assertEqual(requests[0]["packageId"], "mcpkg-legacy")

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

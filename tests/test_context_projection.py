import unittest


class ContextProjectionTests(unittest.TestCase):
    def test_configuration_canvas_marks_missing_bindings_and_review_summary(self):
        from runtime.context_projection import build_configuration_canvas

        canvas = build_configuration_canvas(
            module_id="acquisition",
            revision="store:test",
            items=[
                {
                    "id": "state-lead-ready",
                    "kind": "state",
                    "status": "accepted",
                    "name": "Lead ready",
                    "source_id": "src-crm",
                    "confidence": "high",
                },
                {
                    "id": "metric-lead-quality",
                    "kind": "metric",
                    "status": "accepted",
                    "name": "Lead quality",
                    "source_id": "src-dashboard",
                    "confidence": "medium",
                },
            ],
            workflows=[
                {
                    "workflow_id": "wf-lead-ready-to-meeting",
                    "name": "Lead ready to meeting",
                    "status": "accepted",
                    "start_state_id": "state-lead-ready",
                    "end_state_id": "state-meeting-booked",
                    "participants": [
                        {
                            "participant_id": "wfp-operator",
                            "role_id": "role-operator",
                            "participant_type": "actor",
                        }
                    ],
                    "steps": [],
                    "transitions": [
                        {
                            "transition_id": "wft-ready-booked",
                            "from_state_id": "state-lead-ready",
                            "to_state_id": "state-meeting-booked",
                            "trigger": "meeting-time-confirmed",
                        }
                    ],
                    "metrics": [
                        {"metric_id": "metric-lead-quality", "role": "quality"}
                    ],
                }
            ],
            data_bindings=[
                {
                    "binding_id": "bind-lead-ready-status",
                    "item_id": "state-lead-ready",
                    "property_name": "status",
                    "source_id": "src-crm",
                    "source_kind": "crm-export",
                    "source_locator": "crm:deals",
                    "source_field": "STATUS_ID",
                    "value_type": "string",
                    "key_field": "ID",
                    "refresh_policy": "manual",
                }
            ],
            pending_packages=[
                {
                    "packageId": "mcpkg-lead-quality",
                    "risk": "high",
                    "reviewAction": "human-review",
                }
            ],
            open_questions=[
                {
                    "question_id": "q-loss-reason",
                    "package_id": "mcpkg-lead-quality",
                    "prompt": "Which loss reason routes to warming?",
                }
            ],
        )

        self.assertEqual(canvas["kind"], "configurationCanvas")
        self.assertEqual(canvas["moduleId"], "acquisition")
        self.assertEqual(canvas["revision"], "store:test")
        self.assertEqual(canvas["reviewSummary"]["pendingPackageCount"], 1)
        self.assertEqual(canvas["openQuestionSummary"]["openQuestionCount"], 1)
        self.assertTrue(any(edge["kind"] == "workflow-transition" for edge in canvas["edges"]))

        nodes = {node["id"]: node for node in canvas["nodes"]}
        self.assertEqual(nodes["state-lead-ready"]["bindingCount"], 1)
        self.assertIn("missing-data-binding", nodes["metric-lead-quality"]["warnings"])

    def test_data_binding_projection_is_bounded_and_has_no_raw_values(self):
        from runtime.context_projection import build_data_binding_projection

        projection = build_data_binding_projection(
            module_id="acquisition",
            revision="store:test",
            bindings=[
                {
                    "binding_id": "bind-lead-ready-status",
                    "item_id": "state-lead-ready",
                    "property_name": "status",
                    "source_id": "src-crm",
                    "source_kind": "crm-export",
                    "source_locator": "crm:deals",
                    "source_field": "STATUS_ID",
                    "value_type": "string",
                    "key_field": "ID",
                    "refresh_policy": "manual",
                    "raw_value": "must not be returned",
                }
            ],
        )

        self.assertEqual(projection["kind"], "dataBindingProjection")
        self.assertEqual(projection["coverage"]["boundItemCount"], 1)
        dumped = str(projection)
        self.assertNotIn("raw_value", dumped)
        self.assertNotIn("must not be returned", dumped)

    def test_instance_graph_projection_limits_results(self):
        from runtime.context_projection import build_instance_graph_projection

        projection = build_instance_graph_projection(
            module_id="acquisition",
            revision="store:test",
            instances=[
                {
                    "instance_id": "inst-deal-1",
                    "item_id": "deal",
                    "label": "Deal 1",
                    "status": "accepted",
                    "source_id": "src-crm",
                    "evidence_id": "ev-1",
                    "decision_id": "hdec-1",
                    "attributes": {"stage": "ready"},
                },
                {
                    "instance_id": "inst-deal-2",
                    "item_id": "deal",
                    "label": "Deal 2",
                    "status": "accepted",
                    "source_id": "src-crm",
                    "evidence_id": "ev-2",
                    "decision_id": "hdec-2",
                    "attributes": {"stage": "booked"},
                },
            ],
            relations=[
                {
                    "relation_id": "irel-deal-1-next",
                    "from_instance_id": "inst-deal-1",
                    "to_instance_id": "inst-deal-2",
                    "relation_type": "next-state",
                    "source_id": "src-crm",
                    "evidence_id": "ev-rel",
                    "decision_id": "hdec-rel",
                }
            ],
            limit=1,
        )

        self.assertEqual(projection["kind"], "instanceGraph")
        self.assertEqual(len(projection["nodes"]), 1)
        self.assertEqual(projection["edges"], [])
        self.assertTrue(projection["truncated"])

    def test_instance_graph_projection_strips_all_raw_attribute_spellings(self):
        from runtime.context_projection import build_instance_graph_projection

        projection = build_instance_graph_projection(
            module_id="acquisition",
            revision="store:test",
            instances=[
                {
                    "instance_id": "inst-deal-1",
                    "item_id": "deal",
                    "label": "Deal 1",
                    "status": "accepted",
                    "source_id": "src-crm",
                    "evidence_id": "ev-1",
                    "decision_id": "hdec-1",
                    "attributes": {
                        "stage": "ready",
                        "raw_payload": "private",
                        "rawPayload": "private",
                        "raw_value": "private",
                        "rawValue": "private",
                    },
                }
            ],
            relations=[],
        )

        attributes = projection["nodes"][0]["attributes"]
        self.assertEqual(attributes, {"stage": "ready"})

    def test_configuration_canvas_does_not_emit_edges_to_missing_nodes(self):
        from runtime.context_projection import build_configuration_canvas

        canvas = build_configuration_canvas(
            module_id="acquisition",
            revision="store:test",
            items=[
                {
                    "id": "deal",
                    "kind": "entity",
                    "status": "accepted",
                    "name": "Deal",
                    "source_id": "src-crm",
                }
            ],
            instance_graph={
                "edges": [
                    {
                        "id": "irel-deal-1-next",
                        "from": "inst-deal-1",
                        "to": "inst-deal-2",
                        "relationType": "next-state",
                    }
                ]
            },
        )

        node_ids = {node["id"] for node in canvas["nodes"]}
        for edge in canvas["edges"]:
            self.assertIn(edge["from"], node_ids)
            self.assertIn(edge["to"], node_ids)


if __name__ == "__main__":
    unittest.main()

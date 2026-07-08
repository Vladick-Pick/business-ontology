import unittest


class ContextProjectionTests(unittest.TestCase):
    def test_configuration_canvas_marks_missing_bindings_and_human_request_summary(self):
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
            human_requests=[
                {
                    "requestId": "hreq-loss-reason",
                    "kind": "review",
                    "packageId": "mcpkg-lead-quality",
                    "prompt": "Which loss reason routes to warming?",
                    "dueAt": "2026-06-23T09:00:00Z",
                }
            ],
        )

        self.assertEqual(canvas["kind"], "configurationCanvas")
        self.assertEqual(canvas["moduleId"], "acquisition")
        self.assertEqual(canvas["revision"], "store:test")
        self.assertEqual(canvas["reviewSummary"]["pendingPackageCount"], 1)
        self.assertEqual(canvas["openHumanRequestSummary"]["openRequestCount"], 1)
        self.assertEqual(canvas["openHumanRequestSummary"]["requestIds"], ["hreq-loss-reason"])
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

    def test_system_analysis_projection_is_bounded_and_source_backed(self):
        from runtime.context_projection import build_system_analysis_projection

        projection = build_system_analysis_projection(
            module_id="acquisition",
            revision="store:test",
            objective="Increase meeting booking throughput without lowering lead quality.",
            analysis_intent="constraint-finder",
            items=[
                {
                    "id": "state-lead-ready",
                    "kind": "state",
                    "status": "accepted",
                    "name": "Lead ready",
                    "source_id": "src-crm",
                    "evidence_id": "ev-state",
                    "decision_id": "hdec-state",
                    "confidence": "high",
                    "attrs": {"raw_payload": "private transcript text"},
                },
                {
                    "id": "metric-lead-quality",
                    "kind": "metric",
                    "status": "accepted",
                    "name": "Lead quality",
                    "source_id": "src-dashboard",
                    "evidence_id": "ev-metric",
                    "decision_id": "hdec-metric",
                    "confidence": "medium",
                },
            ],
            definitions=[
                {
                    "definition_id": "def-lead-ready",
                    "item_id": "state-lead-ready",
                    "text": "Lead is ready when fit and next contact are known.",
                    "source_id": "src-crm",
                    "evidence_id": "ev-state",
                    "decision_id": "hdec-state",
                    "confidence": "high",
                }
            ],
            workflows=[
                {
                    "workflow_id": "wf-lead-ready-to-meeting",
                    "name": "Lead ready to meeting",
                    "status": "accepted",
                    "source_id": "src-crm",
                    "evidence_id": "ev-workflow",
                    "decision_id": "hdec-workflow",
                    "start_state_id": "state-lead-ready",
                    "end_state_id": "state-meeting-booked",
                    "value_stage_id": "vst-sales-ready-handoff",
                    "business_object_ids": ["bo-prospective-participant"],
                    "transitions": [
                        {
                            "transition_id": "wft-ready-booked",
                            "from_state_id": "state-lead-ready",
                            "to_state_id": "state-meeting-booked",
                            "trigger": "sales accepts handoff",
                            "evidence_rule": "CRM status and owner confirmation agree.",
                            "authority_id": "role-sales-owner",
                            "source_id": "src-crm",
                        }
                    ],
                    "metrics": [{"metric_id": "metric-lead-quality", "role": "quality"}],
                }
            ],
            constraints=[
                {
                    "id": "constraint-sales-acceptance",
                    "summary": "Sales acceptance queue is suspected but not measured.",
                    "source_id": "src-review",
                    "evidence_id": "ev-review",
                }
            ],
            metrics=[
                {
                    "id": "metric-throughput",
                    "name": "Meeting booking throughput",
                    "status": "accepted",
                    "source_id": "src-analytics",
                    "evidence_id": "ev-throughput",
                    "decision_id": "hdec-throughput",
                    "confidence": "medium",
                    "formula": "booked_meetings / week",
                }
            ],
            rules=[
                {
                    "id": "rule-handoff-cap",
                    "summary": "Sales accepts only leads with complete readiness evidence.",
                    "source_id": "src-policy",
                    "evidence_id": "ev-rule",
                }
            ],
            delays=[
                {
                    "id": "delay-sales-review",
                    "summary": "Sales review can wait one business day.",
                    "source_id": "src-meeting",
                    "evidence_id": "ev-delay",
                }
            ],
            drift_items=[
                {
                    "item_id": "drift-readiness-rule",
                    "status": "open",
                    "affected_ids": ["state-lead-ready"],
                    "summary": "Readiness rule changed in meeting notes.",
                    "owner": "role:acquisition-owner",
                }
            ],
            unknowns=[
                {"id": "unknown-wip", "field": "wip_by_stage", "reason": "WIP by stage is not in accepted model."}
            ],
            competency_questions=[
                {
                    "questionId": "cq-handoff-workflow-breakage",
                    "scopeId": "if-attraction-sales",
                    "question": "Which workflow breaks if the handoff rule changes?",
                    "decisionUse": "Routes interface drift to workflow review.",
                    "answerStatus": "partially-answered",
                    "answeredByIds": ["if-attraction-sales"],
                    "missingFields": ["affected-workflow-owner"],
                    "owner": "role:acquisition-owner",
                    "lastReviewedAt": "2026-06-29",
                }
            ],
            review_packages=[
                {
                    "packageId": "mcpkg-dashboard-metric-002",
                    "risk": "high",
                    "reviewEvidenceMode": "not-checked",
                    "sourceAdequacy": "partial",
                    "slaBand": "high-risk-48h",
                }
            ],
            limit=25,
        )

        self.assertEqual(projection["kind"], "systemAnalysisProjection")
        self.assertEqual(projection["moduleId"], "acquisition")
        self.assertEqual(projection["analysisIntent"], "constraint-finder")
        self.assertIn("state-lead-ready", projection["modelIds"])
        self.assertIn("vst-sales-ready-handoff", projection["modelIds"])
        self.assertIn("bo-prospective-participant", projection["modelIds"])
        self.assertIn("metric-throughput", projection["modelIds"])
        self.assertIn("rule-handoff-cap", projection["modelIds"])
        self.assertEqual(projection["definitions"][0]["sourceId"], "src-crm")
        self.assertEqual(projection["workflow"]["workflows"][0]["workflowId"], "wf-lead-ready-to-meeting")
        self.assertEqual(projection["workflow"]["workflows"][0]["valueStageId"], "vst-sales-ready-handoff")
        self.assertEqual(
            projection["workflow"]["workflows"][0]["businessObjectIds"],
            ["bo-prospective-participant"],
        )
        self.assertEqual(projection["states"][0]["id"], "state-lead-ready")
        self.assertEqual(projection["metrics"][0]["id"], "metric-lead-quality")
        self.assertEqual(projection["evidenceQuality"]["highestReviewRisk"], "high")
        self.assertIn("partial", projection["evidenceQuality"]["sourceAdequacy"])
        self.assertEqual(projection["competencyQuestions"][0]["questionId"], "cq-handoff-workflow-breakage")
        self.assertTrue(
            {"src-crm", "src-dashboard", "src-meeting", "src-review", "src-analytics", "src-policy"}
            <= set(projection["sourceSummary"]["sourceIds"])
        )
        dumped = str(projection)
        self.assertNotIn("private transcript text", dumped)
        self.assertNotIn("raw_payload", dumped)

    def test_system_analysis_readiness_gates_fail_closed_by_kind(self):
        from runtime.context_projection import evaluate_system_analysis_readiness

        projection = {
            "kind": "systemAnalysisProjection",
            "moduleId": "acquisition",
            "revision": "store:test",
            "objective": "Improve handoff performance.",
            "analysisIntent": "unknown",
            "modelIds": [],
            "definitions": [],
            "workflow": {"workflowIds": [], "workflows": []},
            "states": [],
            "metrics": [],
            "rules": [],
            "constraints": [],
            "delays": [],
            "drift": [],
            "unknowns": [],
            "evidenceQuality": {
                "highestReviewRisk": "none",
                "reviewEvidenceModes": [],
                "sourceAdequacy": [],
                "slaBands": [],
                "notes": [],
            },
            "competencyQuestions": [],
            "sourceSummary": {
                "sourceIds": [],
                "evidenceIds": [],
                "reviewPackageIds": [],
                "sourceEventIds": [],
            },
        }

        for analysis_kind in [
            "system-diagram-coach",
            "stock-flow-builder",
            "leverage-finder",
            "constraint-finder",
            "triz-dissolve",
            "why-tree",
        ]:
            with self.subTest(analysis_kind=analysis_kind):
                result = evaluate_system_analysis_readiness(projection, analysis_kind)

                self.assertFalse(result["ready"])
                self.assertGreater(len(result["missingFields"]), 0)
                self.assertTrue(result["recommendedQuestion"])

    def test_system_analysis_readiness_gates_pass_when_required_fields_are_explicit(self):
        from runtime.context_projection import evaluate_system_analysis_readiness

        projection = {
            "kind": "systemAnalysisProjection",
            "moduleId": "acquisition",
            "revision": "store:test",
            "objective": "Close the gap from 10 to 15 booked meetings per week.",
            "analysisIntent": "constraint-finder",
            "modelIds": ["wf-lead-handoff", "state-ready", "metric-throughput"],
            "definitions": [{"definitionId": "def-ready", "itemId": "state-ready", "text": "Ready lead."}],
            "workflow": {
                "workflowIds": ["wf-lead-handoff"],
                "workflows": [
                    {
                        "workflowId": "wf-lead-handoff",
                        "transitions": [
                            {
                                "transitionId": "wft-ready-booked",
                                "fromStateId": "state-ready",
                                "toStateId": "state-booked",
                                "trigger": "handoff accepted",
                                "evidenceRule": "CRM transition exists.",
                                "authorityId": "role-sales-owner",
                            }
                        ],
                    }
                ],
            },
            "states": [{"id": "state-ready", "name": "Ready", "sourceId": "src-crm"}],
            "metrics": [
                {
                    "id": "metric-throughput",
                    "name": "Throughput booked meetings per week",
                    "formula": "booked_meetings / week",
                    "owner": "role:analytics-owner",
                    "sourceOfTruth": "crm-dashboard",
                }
            ],
            "rules": [
                {"id": "rule-policy", "summary": "Policy sets sales acceptance rate and capacity."},
                {"id": "stock-active-leads", "summary": "Stock active leads."},
                {"id": "flow-new-leads", "summary": "Flow new leads."},
                {"id": "equation-booking", "summary": "Equation booked_meetings = accepted_leads * conversion."},
                {"id": "parameter-capacity", "summary": "Parameter capacity is 20 reviews per day."},
                {"id": "time-step-week", "summary": "Time step one week."},
                {"id": "reference-mode", "summary": "Reference mode baseline trend is last 8 weeks."},
                {"id": "stated-vs-enacted-goal", "summary": "Stated goal matches enacted goal check."},
                {"id": "feedback-loop", "summary": "Balancing feedback loop from quality review."},
                {"id": "why-branch", "summary": "Refutable branch: queue growth causes delay."},
            ],
            "constraints": [
                {"id": "queue-wip", "summary": "WIP queue evidence shows 40 leads waiting."},
                {"id": "triz-contradiction", "summary": "Improving speed worsens lead quality."},
            ],
            "delays": [{"id": "delay-review", "summary": "Sales review delay is one business day."}],
            "drift": [],
            "unknowns": [{"id": "unknown-loop", "field": "loops", "reason": "Explicit unknown loop is accepted."}],
            "evidenceQuality": {
                "highestReviewRisk": "high",
                "reviewEvidenceModes": ["source-locator-checked"],
                "sourceAdequacy": ["partial"],
                "slaBands": ["high-risk-48h"],
                "notes": [],
            },
            "competencyQuestions": [],
            "sourceSummary": {
                "sourceIds": ["src-crm"],
                "evidenceIds": ["ev-crm"],
                "reviewPackageIds": ["mcpkg-review"],
                "sourceEventIds": ["srcevt-crm"],
            },
        }

        for analysis_kind in [
            "system-diagram-coach",
            "stock-flow-builder",
            "leverage-finder",
            "constraint-finder",
            "triz-dissolve",
            "why-tree",
        ]:
            with self.subTest(analysis_kind=analysis_kind):
                result = evaluate_system_analysis_readiness(projection, analysis_kind)

                self.assertTrue(result["ready"], result)
                self.assertEqual(result["missingFields"], [])

    def test_readiness_unknown_fields_do_not_satisfy_stock_flow_gate(self):
        from runtime.context_projection import evaluate_system_analysis_readiness

        projection = {
            "kind": "systemAnalysisProjection",
            "moduleId": "acquisition",
            "revision": "store:test",
            "objective": "Improve throughput by 10 percent.",
            "analysisIntent": "stock-flow-builder",
            "modelIds": ["wf-lead-handoff"],
            "definitions": [],
            "workflow": {"workflowIds": ["wf-lead-handoff"], "workflows": []},
            "states": [],
            "metrics": [],
            "rules": [],
            "constraints": [],
            "delays": [],
            "drift": [],
            "unknowns": [
                {"id": "missing-stocks", "field": "stocks", "reason": "Stocks are unknown."},
                {"id": "missing-flows", "field": "flows", "reason": "Flows are unknown."},
                {"id": "missing-equations", "field": "equations", "reason": "Equations are unknown."},
                {"id": "missing-parameters", "field": "parameters", "reason": "Parameters are unknown."},
                {"id": "missing-time-step", "field": "time-step", "reason": "Time step is unknown."},
                {"id": "missing-reference-mode", "field": "reference-mode", "reason": "Reference mode is unknown."},
            ],
            "evidenceQuality": {
                "highestReviewRisk": "high",
                "reviewEvidenceModes": ["not-checked"],
                "sourceAdequacy": ["partial"],
                "slaBands": ["high-risk-48h"],
                "notes": [],
            },
            "competencyQuestions": [],
            "sourceSummary": {
                "sourceIds": [],
                "evidenceIds": [],
                "reviewPackageIds": [],
                "sourceEventIds": [],
            },
        }

        result = evaluate_system_analysis_readiness(projection, "stock-flow-builder")

        self.assertFalse(result["ready"])
        self.assertIn("stocks", result["missingFields"])
        self.assertIn("flows", result["missingFields"])
        self.assertIn("equations", result["missingFields"])

    def test_readiness_model_ids_do_not_satisfy_stock_flow_gate(self):
        from runtime.context_projection import evaluate_system_analysis_readiness

        projection = {
            "kind": "systemAnalysisProjection",
            "moduleId": "acquisition",
            "revision": "store:test",
            "objective": "Increase throughput from 10 to 15 per week.",
            "analysisIntent": "stock-flow-builder",
            "modelIds": [
                "stock-active-leads",
                "flow-new-leads",
                "equation-throughput",
                "parameter-capacity",
                "time-step-weekly",
                "reference-mode-baseline",
            ],
            "definitions": [],
            "workflow": {"workflowIds": [], "workflows": []},
            "states": [],
            "metrics": [],
            "rules": [],
            "constraints": [],
            "delays": [],
            "drift": [],
            "unknowns": [],
            "evidenceQuality": {
                "highestReviewRisk": "low",
                "reviewEvidenceModes": [],
                "sourceAdequacy": [],
                "slaBands": [],
                "notes": [],
            },
            "competencyQuestions": [],
            "sourceSummary": {
                "sourceIds": [],
                "evidenceIds": [],
                "reviewPackageIds": [],
                "sourceEventIds": [],
            },
        }

        result = evaluate_system_analysis_readiness(projection, "stock-flow-builder")

        self.assertFalse(result["ready"])
        self.assertIn("stocks", result["missingFields"])
        self.assertIn("flows", result["missingFields"])
        self.assertIn("equations", result["missingFields"])

    def test_readiness_questions_do_not_satisfy_constraint_gate(self):
        from runtime.context_projection import evaluate_system_analysis_readiness

        projection = {
            "kind": "systemAnalysisProjection",
            "moduleId": "acquisition",
            "revision": "store:test",
            "objective": "Increase throughput from 10 to 15 per week.",
            "analysisIntent": "constraint-finder",
            "modelIds": ["wf-lead-handoff"],
            "definitions": [],
            "workflow": {
                "workflowIds": ["wf-lead-handoff"],
                "workflows": [
                    {
                        "workflowId": "wf-lead-handoff",
                        "transitions": [
                            {
                                "transitionId": "wft-ready-booked",
                                "fromStateId": "state-ready",
                                "toStateId": "state-booked",
                                "trigger": "handoff accepted",
                            }
                        ],
                    }
                ],
            },
            "states": [],
            "metrics": [{"id": "metric-output", "name": "Booked meetings"}],
            "rules": [{"id": "rule-policy", "summary": "Policy exists."}],
            "constraints": [],
            "delays": [],
            "drift": [],
            "unknowns": [],
            "evidenceQuality": {
                "highestReviewRisk": "low",
                "reviewEvidenceModes": ["source-locator-checked"],
                "sourceAdequacy": ["sufficient"],
                "slaBands": ["normal"],
                "notes": [],
            },
            "competencyQuestions": [
                {"questionId": "cq-throughput", "question": "What is the throughput unit?"},
                {"questionId": "cq-wip", "question": "Where are WIP and queue measured?"},
                {"questionId": "cq-capacity", "question": "Who owns capacity or rate?"},
            ],
            "sourceSummary": {
                "sourceIds": ["src-crm"],
                "evidenceIds": ["ev-crm"],
                "reviewPackageIds": [],
                "sourceEventIds": ["srcevt-crm-export-001"],
            },
        }

        result = evaluate_system_analysis_readiness(projection, "constraint-finder")

        self.assertFalse(result["ready"])
        self.assertIn("throughput-unit", result["missingFields"])
        self.assertIn("wip-or-queue-evidence", result["missingFields"])
        self.assertIn("capacity-or-rate", result["missingFields"])

    def test_why_tree_requires_review_evidence_not_only_default_risk(self):
        from runtime.context_projection import evaluate_system_analysis_readiness

        projection = {
            "kind": "systemAnalysisProjection",
            "moduleId": "acquisition",
            "revision": "store:test",
            "objective": "Close the gap from baseline 10 to target 15 meetings per week.",
            "analysisIntent": "why-tree",
            "modelIds": ["metric-throughput"],
            "definitions": [],
            "workflow": {"workflowIds": [], "workflows": []},
            "states": [],
            "metrics": [{"id": "metric-throughput", "formula": "meetings / week"}],
            "rules": [{"id": "why-branch", "summary": "Refutable branch: queue growth causes delay."}],
            "constraints": [],
            "delays": [],
            "drift": [],
            "unknowns": [],
            "evidenceQuality": {
                "highestReviewRisk": "low",
                "reviewEvidenceModes": [],
                "sourceAdequacy": [],
                "slaBands": [],
                "notes": ["no review packages supplied"],
            },
            "competencyQuestions": [],
            "sourceSummary": {
                "sourceIds": [],
                "evidenceIds": [],
                "reviewPackageIds": [],
                "sourceEventIds": [],
            },
        }

        result = evaluate_system_analysis_readiness(projection, "why-tree")

        self.assertFalse(result["ready"])
        self.assertIn("evidence-quality", result["missingFields"])

    def test_system_analysis_result_classification_contracts_review_path(self):
        from runtime.context_projection import build_system_analysis_result

        projection = {
            "kind": "systemAnalysisProjection",
            "moduleId": "acquisition",
            "revision": "store:rev-1",
            "objective": "Close the gap from 10 to 15 booked meetings per week.",
            "analysisIntent": "constraint-finder",
            "modelIds": ["wf-lead-handoff", "metric-throughput"],
            "definitions": [],
            "workflow": {"workflowIds": ["wf-lead-handoff"], "workflows": []},
            "states": [],
            "metrics": [{"id": "metric-throughput", "formula": "booked_meetings / week"}],
            "rules": [],
            "constraints": [],
            "delays": [],
            "drift": [],
            "unknowns": [],
            "evidenceQuality": {
                "highestReviewRisk": "high",
                "reviewEvidenceModes": ["source-locator-checked"],
                "sourceAdequacy": ["partial"],
                "slaBands": ["high-risk-48h"],
                "notes": [],
            },
            "competencyQuestions": [],
            "sourceSummary": {
                "sourceIds": ["src-crm"],
                "evidenceIds": ["ev-crm"],
                "reviewPackageIds": ["rev-crm"],
                "sourceEventIds": ["srcevt-crm-export-001"],
            },
        }
        expected = {
            "recommendation-only": (False, "none"),
            "experiment": (True, "review-system-analysis-result"),
            "model-change-candidate": (True, "review-system-analysis-result"),
            "drift-item": (True, "open-drift-review"),
            "decision-candidate": (True, "review-system-analysis-result"),
            "no-op": (False, "record-no-op"),
        }

        for classification, (review_required, next_action) in expected.items():
            with self.subTest(classification=classification):
                result = build_system_analysis_result(
                    result_id=f"sysres-{classification}",
                    projection=projection,
                    analysis_kind="constraint-finder",
                    classification=classification,
                    summary=f"System analysis returned {classification}.",
                    affected_ids=["wf-lead-handoff", "metric-throughput"],
                )

                self.assertEqual(result["kind"], "systemAnalysisResult")
                self.assertEqual(result["projectionId"], "store:rev-1")
                self.assertEqual(result["classification"], classification)
                self.assertIs(result["reviewRequired"], review_required)
                self.assertEqual(result["nextAction"], next_action)
                self.assertEqual(result["sourceEventIds"], ["srcevt-crm-export-001"])
                self.assertIs(result["safety"]["noAcceptedMutation"], True)
                self.assertIs(result["safety"]["noAutoPromotion"], True)

    def test_system_analysis_result_refuses_unlinked_projection(self):
        from runtime.context_projection import build_system_analysis_result

        projection = {
            "kind": "wrongProjection",
            "objective": "Improve handoff performance.",
            "analysisIntent": "constraint-finder",
            "sourceSummary": {"sourceEventIds": []},
        }

        with self.assertRaises(ValueError):
            build_system_analysis_result(
                result_id="sysres-unlinked",
                projection=projection,
                analysis_kind="constraint-finder",
                classification="recommendation-only",
                summary="Recommendation without projection linkage.",
                affected_ids=[],
            )

    def test_system_analysis_result_requires_projection_revision(self):
        from runtime.context_projection import build_system_analysis_result

        projection = {
            "kind": "systemAnalysisProjection",
            "moduleId": "acquisition",
            "objective": "Improve handoff performance.",
            "analysisIntent": "constraint-finder",
            "sourceSummary": {"sourceEventIds": []},
        }

        with self.assertRaises(ValueError):
            build_system_analysis_result(
                result_id="sysres-missing-revision",
                projection=projection,
                analysis_kind="constraint-finder",
                classification="recommendation-only",
                summary="Recommendation without projection revision.",
                affected_ids=[],
            )

    def test_system_analysis_result_requires_projection_module_id(self):
        from runtime.context_projection import build_system_analysis_result

        projection = {
            "kind": "systemAnalysisProjection",
            "revision": "store:rev-1",
            "objective": "Improve handoff performance.",
            "analysisIntent": "constraint-finder",
            "sourceSummary": {"sourceEventIds": []},
        }

        with self.assertRaises(ValueError):
            build_system_analysis_result(
                result_id="sysres-missing-module",
                projection=projection,
                analysis_kind="constraint-finder",
                classification="recommendation-only",
                summary="Recommendation without projection module.",
                affected_ids=[],
            )

    def test_review_required_system_analysis_result_returns_model_change_package(self):
        from runtime.context_projection import (
            build_system_analysis_result,
            model_change_package_from_system_analysis_result,
        )

        projection = {
            "kind": "systemAnalysisProjection",
            "moduleId": "acquisition",
            "revision": "store:rev-1",
            "objective": "Close the gap from 10 to 15 booked meetings per week.",
            "analysisIntent": "constraint-finder",
            "modelIds": ["wf-lead-handoff"],
            "definitions": [],
            "workflow": {"workflowIds": ["wf-lead-handoff"], "workflows": []},
            "states": [],
            "metrics": [],
            "rules": [],
            "constraints": [],
            "delays": [],
            "drift": [],
            "unknowns": [],
            "evidenceQuality": {
                "highestReviewRisk": "high",
                "reviewEvidenceModes": ["source-locator-checked"],
                "sourceAdequacy": ["partial"],
                "slaBands": ["high-risk-48h"],
                "notes": [],
            },
            "competencyQuestions": [],
            "sourceSummary": {
                "sourceIds": ["src-crm"],
                "evidenceIds": ["ev-crm"],
                "reviewPackageIds": [],
                "sourceEventIds": ["srcevt-crm-export-001"],
            },
        }
        result = build_system_analysis_result(
            result_id="sysres-constraint-candidate",
            projection=projection,
            analysis_kind="constraint-finder",
            classification="model-change-candidate",
            summary="Capacity policy may need review before accepted model changes.",
            affected_ids=["wf-lead-handoff"],
        )

        package = model_change_package_from_system_analysis_result(
            result,
            model_pack_id="mp-acquisition",
            model_pack_version="0.1.0",
            ontology_revision="store:rev-1",
            generated_at="2026-06-30T00:00:00Z",
            owner="role:acquisition-owner",
        )

        self.assertEqual(package["packageId"], "mcpkg-constraint-candidate")
        self.assertEqual(package["review"]["overallAction"], "human-review")
        self.assertIs(package["safety"]["noAcceptedMutation"], True)
        self.assertEqual(package["changes"][0]["kind"], "system-analysis-result")
        self.assertEqual(package["changes"][0]["proposedAction"], "review-system-analysis-result")
        self.assertEqual(package["changes"][0]["sourceRisk"], ["partial-export"])
        self.assertEqual(package["changes"][0]["systemAnalysisResultId"], "sysres-constraint-candidate")
        self.assertEqual(package["changes"][0]["systemAnalysisClassification"], "model-change-candidate")

    def test_sufficient_system_analysis_result_uses_no_known_source_risk(self):
        from runtime.context_projection import (
            build_system_analysis_result,
            model_change_package_from_system_analysis_result,
        )

        projection = {
            "kind": "systemAnalysisProjection",
            "moduleId": "acquisition",
            "revision": "store:rev-1",
            "objective": "Close the gap from 10 to 15 booked meetings per week.",
            "analysisIntent": "constraint-finder",
            "modelIds": ["wf-lead-handoff"],
            "definitions": [],
            "workflow": {"workflowIds": ["wf-lead-handoff"], "workflows": []},
            "states": [],
            "metrics": [],
            "rules": [],
            "constraints": [],
            "delays": [],
            "drift": [],
            "unknowns": [],
            "evidenceQuality": {
                "highestReviewRisk": "medium",
                "reviewEvidenceModes": ["source-locator-checked"],
                "sourceAdequacy": ["sufficient"],
                "slaBands": ["normal"],
                "notes": [],
            },
            "competencyQuestions": [],
            "sourceSummary": {
                "sourceIds": ["src-crm"],
                "evidenceIds": ["ev-crm"],
                "reviewPackageIds": [],
                "sourceEventIds": ["srcevt-crm-export-001"],
            },
        }
        result = build_system_analysis_result(
            result_id="sysres-sufficient-source",
            projection=projection,
            analysis_kind="constraint-finder",
            classification="model-change-candidate",
            summary="Source-backed candidate requires owner review.",
            affected_ids=["wf-lead-handoff"],
        )

        package = model_change_package_from_system_analysis_result(
            result,
            model_pack_id="mp-acquisition",
            model_pack_version="0.1.0",
            ontology_revision="store:rev-1",
            generated_at="2026-06-30T00:00:00Z",
            owner="role:acquisition-owner",
        )

        self.assertEqual(package["changes"][0]["sourceRisk"], ["no-known-risk"])

    def test_non_review_system_analysis_result_does_not_create_model_change_package(self):
        from runtime.context_projection import (
            build_system_analysis_result,
            model_change_package_from_system_analysis_result,
        )

        projection = {
            "kind": "systemAnalysisProjection",
            "moduleId": "acquisition",
            "revision": "store:rev-1",
            "objective": "Improve handoff performance.",
            "analysisIntent": "leverage-finder",
            "modelIds": [],
            "definitions": [],
            "workflow": {"workflowIds": [], "workflows": []},
            "states": [],
            "metrics": [],
            "rules": [],
            "constraints": [],
            "delays": [],
            "drift": [],
            "unknowns": [],
            "evidenceQuality": {
                "highestReviewRisk": "low",
                "reviewEvidenceModes": ["document-review-only"],
                "sourceAdequacy": ["sufficient"],
                "slaBands": ["normal"],
                "notes": [],
            },
            "competencyQuestions": [],
            "sourceSummary": {
                "sourceIds": [],
                "evidenceIds": [],
                "reviewPackageIds": [],
                "sourceEventIds": [],
            },
        }
        result = build_system_analysis_result(
            result_id="sysres-recommendation",
            projection=projection,
            analysis_kind="leverage-finder",
            classification="recommendation-only",
            summary="Recommendation does not claim a model change.",
            affected_ids=[],
        )

        package = model_change_package_from_system_analysis_result(
            result,
            model_pack_id="mp-acquisition",
            model_pack_version="0.1.0",
            ontology_revision="store:rev-1",
            generated_at="2026-06-30T00:00:00Z",
            owner="role:acquisition-owner",
        )

        self.assertIsNone(package)

    def test_review_required_system_analysis_result_refuses_missing_source_events(self):
        from runtime.context_projection import (
            build_system_analysis_result,
            model_change_package_from_system_analysis_result,
        )

        projection = {
            "kind": "systemAnalysisProjection",
            "moduleId": "acquisition",
            "revision": "store:rev-1",
            "objective": "Improve handoff performance.",
            "analysisIntent": "why-tree",
            "modelIds": ["wf-lead-handoff"],
            "definitions": [],
            "workflow": {"workflowIds": ["wf-lead-handoff"], "workflows": []},
            "states": [],
            "metrics": [],
            "rules": [],
            "constraints": [],
            "delays": [],
            "drift": [],
            "unknowns": [],
            "evidenceQuality": {
                "highestReviewRisk": "high",
                "reviewEvidenceModes": ["not-checked"],
                "sourceAdequacy": ["insufficient"],
                "slaBands": ["high-risk-48h"],
                "notes": [],
            },
            "competencyQuestions": [],
            "sourceSummary": {
                "sourceIds": [],
                "evidenceIds": [],
                "reviewPackageIds": [],
                "sourceEventIds": [],
            },
        }
        result = build_system_analysis_result(
            result_id="sysres-drift-without-source",
            projection=projection,
            analysis_kind="why-tree",
            classification="drift-item",
            summary="Analysis suspects drift but has no source event reference.",
            affected_ids=["wf-lead-handoff"],
        )

        with self.assertRaises(ValueError):
            model_change_package_from_system_analysis_result(
                result,
                model_pack_id="mp-acquisition",
                model_pack_version="0.1.0",
                ontology_revision="store:rev-1",
                generated_at="2026-06-30T00:00:00Z",
                owner="role:acquisition-owner",
            )

    def test_system_analysis_result_adapter_refuses_invalid_external_result(self):
        from runtime.context_projection import model_change_package_from_system_analysis_result

        result = {
            "kind": "systemAnalysisResult",
            "resultId": "sysres-bad",
            "projectionId": "store:rev-1",
            "moduleId": "bad module id",
            "analysisKind": "constraint-finder",
            "classification": "model-change-candidate",
            "summary": "Bad external result.",
            "affectedIds": ["wf-lead-handoff"],
            "sourceEventIds": ["srcevt-crm-export-001"],
            "evidenceQuality": {
                "highestReviewRisk": "medium",
                "reviewEvidenceModes": ["source-locator-checked"],
                "sourceAdequacy": ["partial"],
                "slaBands": ["normal"],
                "notes": [],
            },
            "reviewRequired": True,
            "nextAction": "review-system-analysis-result",
            "safety": {
                "noAcceptedMutation": True,
                "noAutoPromotion": True,
                "noSourceWriteback": True,
                "noRawPayload": True,
            },
        }

        with self.assertRaises(ValueError):
            model_change_package_from_system_analysis_result(
                result,
                model_pack_id="mp-acquisition",
                model_pack_version="0.1.0",
                ontology_revision="store:rev-1",
                generated_at="2026-06-30T00:00:00Z",
                owner="role:acquisition-owner",
            )

    def test_model_health_projection_counts_review_wip_gaps_and_human_requests(self):
        from runtime.context_projection import build_model_health_projection

        projection = build_model_health_projection(
            module_id="acquisition",
            revision="store:rev-1",
            as_of="2026-06-30",
            items=[
                {
                    "id": "state-ready",
                    "status": "accepted",
                    "owner": "role:ops",
                    "sourceLocator": "crm:deals#status",
                    "nextAudit": "2026-06-01",
                },
                {
                    "id": "metric-throughput",
                    "status": "accepted",
                    "owner": "role:analytics",
                    "sourceLocator": "dashboard:weekly#throughput",
                    "nextAudit": "2026-07-01",
                },
                {"id": "candidate-rule", "status": "candidate", "owner": "unknown"},
                {"id": "hypothesis-delay", "status": "hypothesis", "owner": "role:ops"},
                {"id": "conflict-source", "status": "conflict", "owner": "unknown"},
            ],
            competency_questions=[
                {"questionId": "cq-1", "answerStatus": "answered"},
                {"questionId": "cq-2", "answerStatus": "unanswered"},
                {"questionId": "cq-3", "answerStatus": "blocked"},
            ],
            review_packages=[
                {
                    "packageId": "mcpkg-high-1",
                    "risk": "high",
                    "status": "pending",
                    "owner": "role:ops",
                    "createdAt": "2026-06-28",
                },
                {
                    "packageId": "mcpkg-high-2",
                    "risk": "high",
                    "status": "needs-info",
                    "owner": "unknown",
                    "createdAt": "2026-06-30",
                    "requiredActions": [{"action": "needs-owner"}],
                },
                {
                    "packageId": "mcpkg-low",
                    "risk": "low",
                    "status": "pending",
                    "owner": "role:ops",
                    "createdAt": "2026-06-29",
                },
            ],
            human_requests=[
                {
                    "requestId": "hreq-oldest",
                    "kind": "review",
                    "status": "open",
                    "dueAt": "2026-06-29T09:00:00Z",
                },
                {
                    "requestId": "hreq-answered",
                    "kind": "review",
                    "status": "answered",
                    "dueAt": "2026-06-28T09:00:00Z",
                },
            ],
            source_instances=[
                {
                    "source_instance_id": "tg-main-history",
                    "status": "live-proven",
                    "last_live_proof_id": "proof-tg-001",
                },
                {
                    "source_instance_id": "meeting-recording",
                    "status": "source-connected",
                    "last_live_proof_id": "proof-mtg-001",
                },
            ],
        )

        metrics = projection["metrics"]
        self.assertEqual(projection["kind"], "modelHealth")
        self.assertEqual(metrics["acceptedItemCount"], 2)
        self.assertEqual(metrics["candidateCount"], 1)
        self.assertEqual(metrics["hypothesisCount"], 1)
        self.assertEqual(metrics["conflictCount"], 1)
        self.assertEqual(metrics["stalePastNextAuditCount"], 1)
        self.assertEqual(metrics["unansweredCompetencyQuestionCount"], 2)
        self.assertEqual(projection["openHumanRequestCount"], 1)
        self.assertEqual(metrics["openHumanRequestCount"], 1)
        self.assertEqual(metrics["proposalsBlockedByMissingOwner"], 1)
        self.assertEqual(metrics["highRiskReviewWipCount"], 2)
        self.assertEqual(metrics["averageReviewAgeDays"], 1.0)
        self.assertEqual(metrics["claimsWithOwnerPercent"], 60.0)
        self.assertEqual(metrics["claimsWithSourceLocatorPercent"], 40.0)
        self.assertEqual(projection["reviewWip"]["highRiskStatus"], "within-limit")
        self.assertEqual(projection["humanRequests"]["openRequestIds"], ["hreq-oldest"])
        self.assertEqual(projection["sourceReadiness"]["liveProvenCount"], 1)
        self.assertEqual(projection["sourceReadiness"]["sourceConnectedCount"], 1)
        self.assertEqual(
            projection["sourceReadiness"]["sourceInstanceIdsByStatus"]["live-proven"],
            ["tg-main-history"],
        )
        self.assertEqual(projection["sourceReadiness"]["lastProofIdsBySource"]["meeting-recording"], "proof-mtg-001")

    def test_model_health_projection_names_missing_inputs(self):
        from runtime.context_projection import build_model_health_projection

        projection = build_model_health_projection(
            module_id="acquisition",
            revision="store:rev-1",
            as_of="2026-06-30",
            items=[{"id": "state-ready", "status": "accepted"}],
            competency_questions=[],
            review_packages=[{"packageId": "mcpkg-high", "risk": "high", "status": "pending"}],
        )

        self.assertIn("items.nextAudit", projection["missingInputs"])
        self.assertIn("sourceInstances", projection["missingInputs"])
        self.assertIn("items.sourceLocator", projection["missingInputs"])
        self.assertIn("reviewPackages.createdAt", projection["missingInputs"])
        self.assertIsNone(projection["metrics"]["averageReviewAgeDays"])


if __name__ == "__main__":
    unittest.main()

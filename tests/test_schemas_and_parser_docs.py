import json
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class SchemaAndParserDocsTests(unittest.TestCase):
    def test_json_schemas_exist_and_are_strict_objects(self):
        schema_dir = REPO_ROOT / "schemas"
        expected = {
            "card.schema.json",
            "canonical-model-store.schema.json",
            "human-request.schema.json",
            "installed-agent-e2e-report.schema.json",
            "live-proof.schema.json",
            "model-access-policy.schema.json",
            "model-health.schema.json",
            "model-change-package.schema.json",
            "model-pack.schema.json",
            "review-package.schema.json",
            "source-instance.schema.json",
            "source-event.schema.json",
            "source-map-entry.schema.json",
            "staged-proposal.schema.json",
            "system-analysis-projection.schema.json",
            "system-analysis-result.schema.json",
            "trace-event.schema.json",
            "tool-result.schema.json",
            "workspace-state.schema.json",
        }

        missing = [name for name in expected if not (schema_dir / name).is_file()]
        self.assertEqual(missing, [])

        for name in expected:
            schema = json.loads((schema_dir / name).read_text(encoding="utf-8"))
            self.assertEqual(schema["type"], "object", name)
            self.assertFalse(schema.get("additionalProperties", True), name)
            self.assertIsInstance(schema.get("required"), list, name)

    def test_canonical_store_schema_names_required_operational_state(self):
        schema = json.loads(
            (REPO_ROOT / "schemas" / "canonical-model-store.schema.json").read_text(
                encoding="utf-8"
            )
        )

        for field in [
            "items",
            "definitions",
            "attributes",
            "criteria",
            "examples",
            "workflows",
            "workflowParticipants",
            "workflowSteps",
            "workflowTransitions",
            "workflowExceptions",
            "workflowMetrics",
            "businessArchitectureLinks",
            "evidence",
            "humanDecisions",
            "modelChangePackages",
            "competencyQuestions",
            "openQuestions",
            "driftItems",
            "versions",
            "supersessionLinks",
            "runs",
            "sourceCursors",
        ]:
            self.assertIn(field, schema["required"])

        accepted_item = schema["$defs"]["acceptedItem"]
        self.assertIn("term", accepted_item["properties"]["kind"]["enum"])
        self.assertIn("workflow", accepted_item["properties"]["kind"]["enum"])
        for kind in [
            "valueStream",
            "valueStage",
            "capability",
            "stakeholder",
            "valueItem",
            "businessObject",
        ]:
            self.assertIn(kind, accepted_item["properties"]["kind"]["enum"])
        for field in [
            "valid_from",
            "valid_to",
            "supersedes",
            "superseded_by",
            "last_verified_at",
            "confidence",
        ]:
            self.assertIn(field, accepted_item["required"])

        for definition_name in [
            "definition",
            "attribute",
            "criterion",
            "example",
            "competencyQuestion",
            "workflow",
            "workflowParticipant",
            "workflowStep",
            "workflowTransition",
            "workflowException",
            "workflowMetric",
            "businessArchitectureLink",
        ]:
            self.assertIn(definition_name, schema["$defs"])

        business_link = schema["$defs"]["businessArchitectureLink"]
        self.assertFalse(business_link["additionalProperties"])
        self.assertEqual(
            set(business_link["properties"]["relation"]["enum"]),
            {
                "stakeholder-triggers-value-stream",
                "value-stream-contains-value-stage",
                "capability-enables-value-stage",
                "value-stage-delivers-value-item",
                "workflow-realizes-value-stage",
                "business-object-changes-state-in-workflow",
            },
        )

        package_statuses = set(
            schema["$defs"]["packageSummary"]["properties"]["status"]["enum"]
        )
        self.assertEqual(
            package_statuses,
            {
                "pending",
                "approved",
                "rejected",
                "needs-info",
                "superseded",
                "no-op",
                "applied",
            },
        )

        competency_question = schema["$defs"]["competencyQuestion"]
        self.assertFalse(competency_question["additionalProperties"])
        self.assertEqual(
            set(competency_question["required"]),
            {
                "questionId",
                "scopeId",
                "question",
                "decisionUse",
                "answerStatus",
                "answeredByIds",
                "missingFields",
                "owner",
                "lastReviewedAt",
            },
        )
        self.assertEqual(
            set(competency_question["properties"]["answerStatus"]["enum"]),
            {"answered", "partially-answered", "unanswered", "blocked"},
        )
        self.assertTrue(competency_question["properties"]["answeredByIds"]["uniqueItems"])
        self.assertTrue(competency_question["properties"]["missingFields"]["uniqueItems"])

    def test_canonical_store_competency_question_doc_matches_schema_field_names(self):
        schema = json.loads(
            (REPO_ROOT / "schemas" / "canonical-model-store.schema.json").read_text(
                encoding="utf-8"
            )
        )
        doc = (REPO_ROOT / "references" / "canonical-model-store.md").read_text(
            encoding="utf-8"
        )

        for field in schema["$defs"]["competencyQuestion"]["required"]:
            self.assertIn(f"`{field}`", doc)

    def test_system_analysis_result_schema_locks_return_path_contract(self):
        schema = json.loads(
            (REPO_ROOT / "schemas" / "system-analysis-result.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            set(schema["required"]),
            {
                "kind",
                "resultId",
                "projectionId",
                "moduleId",
                "analysisKind",
                "classification",
                "summary",
                "affectedIds",
                "sourceEventIds",
                "evidenceQuality",
                "reviewRequired",
                "nextAction",
                "safety",
            },
        )
        self.assertEqual(
            set(schema["properties"]["classification"]["enum"]),
            {
                "recommendation-only",
                "experiment",
                "model-change-candidate",
                "drift-item",
                "decision-candidate",
                "no-op",
            },
        )
        self.assertTrue(schema["properties"]["affectedIds"]["uniqueItems"])
        self.assertTrue(schema["properties"]["sourceEventIds"]["uniqueItems"])
        self.assertFalse(schema["properties"]["evidenceQuality"]["additionalProperties"])
        self.assertFalse(schema["properties"]["safety"]["additionalProperties"])
        for flag in [
            "noAcceptedMutation",
            "noAutoPromotion",
            "noSourceWriteback",
            "noRawPayload",
        ]:
            self.assertTrue(schema["properties"]["safety"]["properties"][flag]["const"])
        review_required_gate = schema["allOf"][2]["then"]["properties"]
        self.assertEqual(review_required_gate["reviewRequired"]["const"], True)
        self.assertEqual(review_required_gate["sourceEventIds"]["minItems"], 1)
        drift_gate = schema["allOf"][3]["then"]["properties"]
        self.assertEqual(drift_gate["sourceEventIds"]["minItems"], 1)

    def test_model_health_schema_locks_metric_names(self):
        schema = json.loads(
            (REPO_ROOT / "schemas" / "model-health.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(schema["properties"]["kind"]["const"], "modelHealth")
        self.assertIn("openHumanRequestCount", schema["properties"])
        metrics = schema["properties"]["metrics"]["properties"]
        for field in [
            "acceptedItemCount",
            "candidateCount",
            "hypothesisCount",
            "conflictCount",
            "stalePastNextAuditCount",
            "averageReviewAgeDays",
            "claimsWithOwnerPercent",
            "claimsWithSourceLocatorPercent",
            "unansweredCompetencyQuestionCount",
            "openHumanRequestCount",
            "proposalsBlockedByMissingOwner",
            "highRiskReviewWipCount",
        ]:
            self.assertIn(field, metrics)
        wip = schema["properties"]["reviewWip"]
        self.assertEqual(wip["properties"]["highRiskLimit"]["const"], 5)
        self.assertIn("humanRequests", schema["properties"])
        self.assertIn("sourceReadiness", schema["properties"])
        readiness = schema["properties"]["sourceReadiness"]["properties"]
        self.assertIn("liveProvenCount", readiness)
        self.assertIn("sourceInstanceIdsByStatus", readiness)
        self.assertIn("missingInputs", schema["properties"])

    def test_parser_subset_doc_names_supported_and_unsupported_yaml(self):
        doc = REPO_ROOT / "references" / "parser-subset.md"

        text = doc.read_text(encoding="utf-8")

        self.assertIn("Supported frontmatter subset", text)
        self.assertIn("Unsupported YAML features", text)
        self.assertIn("inline lists", text)
        self.assertIn("escaped pipes", text)
        self.assertIn("source-map table", text)

    def test_agent_os_definitions_and_attributes_instruction_exists(self):
        doc = REPO_ROOT / "agent-os" / "DEFINITIONS_AND_ATTRIBUTES.md"

        text = doc.read_text(encoding="utf-8")

        for phrase in [
            "definitions",
            "attributes",
            "criteria",
            "examples",
            "non-examples",
            "human review",
        ]:
            self.assertIn(phrase, text)

    def test_agent_os_processes_and_workflows_instruction_exists(self):
        doc = REPO_ROOT / "agent-os" / "PROCESSES_AND_WORKFLOWS.md"

        text = doc.read_text(encoding="utf-8")

        for phrase in [
            "workflows",
            "steps",
            "transitions",
            "participants",
            "exceptions",
            "metrics",
            "human review",
        ]:
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()

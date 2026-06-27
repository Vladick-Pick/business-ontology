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
            "model-change-package.schema.json",
            "model-pack.schema.json",
            "review-package.schema.json",
            "source-event.schema.json",
            "source-map-entry.schema.json",
            "staged-proposal.schema.json",
            "trace-event.schema.json",
            "tool-result.schema.json",
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
            "evidence",
            "humanDecisions",
            "modelChangePackages",
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
            "workflow",
            "workflowParticipant",
            "workflowStep",
            "workflowTransition",
            "workflowException",
            "workflowMetric",
        ]:
            self.assertIn(definition_name, schema["$defs"])

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

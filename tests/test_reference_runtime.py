import json
from pathlib import Path
import shutil
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class ReferenceRuntimeTests(unittest.TestCase):
    def setUp(self):
        from runtime.reference_runtime import BusinessOntologyRuntime, RuntimeConfig

        self.RuntimeConfig = RuntimeConfig
        self.BusinessOntologyRuntime = BusinessOntologyRuntime

    def make_runtime(self, tmp, scopes=None):
        root = Path(tmp) / "ontology"
        shutil.copytree(REPO_ROOT / "examples" / "acquisition-ontology", root)
        trace_path = Path(tmp) / "trace" / "events.jsonl"
        config = self.RuntimeConfig(
            module_id="acquisition",
            ontology_root=root,
            trace_path=trace_path,
            scopes=set(scopes or {"ontology:read", "ontology:propose", "ontology:admin-review"}),
        )
        return self.BusinessOntologyRuntime(config), root, trace_path

    def test_exposes_mcp_style_resources_and_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, _ = self.make_runtime(tmp)

            templates = runtime.list_resource_templates()
            tools = runtime.list_tools()

        template_names = {item["name"] for item in templates["resourceTemplates"]}
        self.assertIn("current-model", template_names)
        self.assertIn("model-entities", template_names)
        self.assertIn("model-relations", template_names)
        self.assertIn("model-decisions", template_names)
        self.assertIn("model-drift", template_names)
        self.assertIn("pending-review-packages", template_names)
        self.assertIn("source-event", template_names)
        self.assertIn("accepted-card", template_names)
        self.assertIn("source-map", template_names)

        tool_map = {tool["name"]: tool for tool in tools["tools"]}
        self.assertIn("propose_change", tool_map)
        self.assertIn("validate_proposal", tool_map)
        self.assertIn("prepare_promote_digest", tool_map)
        self.assertEqual(tool_map["propose_change"]["inputSchema"]["type"], "object")
        self.assertFalse(tool_map["propose_change"]["inputSchema"]["additionalProperties"])
        self.assertEqual(tool_map["propose_change"]["outputSchema"]["type"], "object")

    def test_reads_accepted_resources_without_including_staged(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, root, _ = self.make_runtime(tmp)
            staged = root / "staged"
            staged.mkdir()
            (staged / "prop-private.md").write_text("staged proposal", encoding="utf-8")

            result = runtime.read_resource("ontology://acquisition/cards/lead-quality")
            source_map = runtime.read_resource("ontology://acquisition/sources")

        self.assertEqual(result["contents"][0]["mimeType"], "text/markdown")
        self.assertIn("Lead quality", result["contents"][0]["text"])
        self.assertNotIn("staged proposal", result["contents"][0]["text"])
        self.assertIn("example-acquisition-source", source_map["contents"][0]["text"])

    def test_reads_current_model_projection_with_revision_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, _ = self.make_runtime(tmp)

            result = runtime.read_resource("ontology://acquisition/model/current")
            payload = json.loads(result["contents"][0]["text"])
            entities = runtime.read_resource("ontology://acquisition/model/entities")
            decisions = runtime.read_resource("ontology://acquisition/model/decisions")
            drift = runtime.read_resource("ontology://acquisition/model/drift")

        self.assertEqual(payload["moduleId"], "acquisition")
        self.assertEqual(payload["source"], "accepted-export")
        self.assertIn("revision", payload)
        self.assertFalse(payload["stale"])
        self.assertIn("lead-quality", entities["contents"][0]["text"])
        self.assertIn("d-handoff-quality", decisions["contents"][0]["text"])
        self.assertEqual(json.loads(drift["contents"][0]["text"])["items"], [])

    def test_review_and_source_event_resources_require_configured_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, _ = self.make_runtime(tmp)

            packages = runtime.read_resource("ontology://acquisition/review/packages")
            event = runtime.read_resource("ontology://acquisition/sources/events/srcevt-example")

        self.assertEqual(packages["status"], "refused")
        self.assertIn("no package store", packages["refusal_reason"])
        self.assertEqual(event["status"], "refused")
        self.assertIn("no source-event store", event["refusal_reason"])

    def test_review_and_source_event_resources_require_admin_review_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, _ = self.make_runtime(tmp, scopes={"ontology:read"})

            packages = runtime.read_resource("ontology://acquisition/review/packages")
            event = runtime.read_resource("ontology://acquisition/sources/events/srcevt-example")

        self.assertEqual(packages["status"], "refused")
        self.assertIn("missing required scope ontology:admin-review", packages["refusal_reason"])
        self.assertEqual(event["status"], "refused")
        self.assertIn("missing required scope ontology:admin-review", event["refusal_reason"])

    def test_propose_change_writes_staged_file_validates_and_traces(self):
        candidate_card = """---
id: c-runtime-smoke
type: concept
status: candidate
source: example-acquisition-source
owner: ontology-operator
last-reviewed: 2026-06-22
next-audit: 2026-09-22
attrs:
  subtype: criterion
---

# Runtime smoke criterion

Candidate criterion proposed by the reference runtime smoke test.
"""
        with tempfile.TemporaryDirectory() as tmp:
            runtime, root, trace_path = self.make_runtime(tmp)

            result = runtime.call_tool(
                "propose_change",
                {
                    "module_id": "acquisition",
                    "proposal_id": "prop-runtime-smoke",
                    "target": "new",
                    "diff": {"was": "(none)", "now": "runtime smoke criterion"},
                    "basis": "Exercise the reference runtime proposal gate.",
                    "source_id": "example-acquisition-source",
                    "source_locator": "tests/test_reference_runtime.py",
                    "confidence": "medium",
                    "input": "agent-inference",
                    "originating_skill": "reference-runtime",
                    "candidate_card_markdown": candidate_card,
                },
            )

            proposal = root / result["proposal_path"]
            trace_lines = trace_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(result["status"], "proposed", result)
            self.assertEqual(result["validator"]["status"], "pass", result)
            self.assertTrue(proposal.is_file())
            self.assertIn("validator-result: pass", proposal.read_text(encoding="utf-8"))
            self.assertEqual(proposal.parent.name, "staged")
            self.assertFalse((root / "concepts" / "c-runtime-smoke.md").exists())
            self.assertTrue(trace_lines)
            events = [json.loads(line) for line in trace_lines]
            self.assertTrue(any(event["name"] == "propose_change" for event in events))
            self.assertFalse(any("raw_payload" in event for event in events))

    def test_accepted_mutation_tool_is_refused_and_traced(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, trace_path = self.make_runtime(tmp)

            result = runtime.call_tool(
                "promote_all",
                {"module_id": "acquisition", "proposal_id": "prop-runtime-smoke"},
            )
            events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(result["status"], "refused")
        self.assertIn("not exposed", result["refusal_reason"])
        self.assertEqual(events[-1]["event_type"], "refusal")
        self.assertEqual(events[-1]["result"], "refused")

    def test_missing_scope_refuses_write_like_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, _ = self.make_runtime(tmp, scopes={"ontology:read"})

            result = runtime.call_tool(
                "prepare_promote_digest",
                {"module_id": "acquisition", "proposal_ids": []},
            )

        self.assertEqual(result["status"], "refused")
        self.assertIn("missing required scope", result["refusal_reason"])


if __name__ == "__main__":
    unittest.main()

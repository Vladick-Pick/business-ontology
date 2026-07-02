import json
from pathlib import Path
import shutil
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PACK_PATH = REPO_ROOT / "examples" / "model-packs" / "acquisition.model-pack.json"
SOURCE_EVENT_PATH = REPO_ROOT / "evals" / "fixtures" / "source-events" / "telegram-export.synthetic.json"


class ReferenceRuntimeTests(unittest.TestCase):
    def setUp(self):
        from runtime.reference_runtime import BusinessOntologyRuntime, RuntimeConfig

        self.RuntimeConfig = RuntimeConfig
        self.BusinessOntologyRuntime = BusinessOntologyRuntime

    def make_runtime(self, tmp, scopes=None, store_path=None):
        root = Path(tmp) / "ontology"
        shutil.copytree(REPO_ROOT / "examples" / "acquisition-ontology", root)
        trace_path = Path(tmp) / "trace" / "events.jsonl"
        config = self.RuntimeConfig(
            module_id="acquisition",
            ontology_root=root,
            trace_path=trace_path,
            scopes=set(scopes or {"ontology:read", "ontology:propose", "ontology:admin-review"}),
            store_path=store_path,
        )
        return self.BusinessOntologyRuntime(config), root, trace_path

    def make_store(self, tmp):
        from runtime.operational_store import OperationalStore

        store_path = Path(tmp) / "state" / "operational.sqlite3"
        store = OperationalStore.connect(store_path)
        store.initialize()
        self.addCleanup(store.close)
        return store, store_path

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
        self.assertIn("model-canvas", template_names)
        self.assertIn("model-bindings", template_names)
        self.assertIn("model-instance-graph", template_names)
        self.assertIn("model-health", template_names)
        self.assertIn("pending-review-packages", template_names)
        self.assertIn("source-event", template_names)
        self.assertIn("accepted-card", template_names)
        self.assertIn("source-map", template_names)

        tool_map = {tool["name"]: tool for tool in tools["tools"]}
        self.assertIn("propose_change", tool_map)
        self.assertIn("validate_proposal", tool_map)
        self.assertIn("prepare_promote_digest", tool_map)
        self.assertIn("generate_draft_ontology", tool_map)
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

    def test_store_backed_projection_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, store_path = self.make_store(tmp)
            store.record_accepted_item(
                {
                    "id": "state-lead-ready",
                    "kind": "state",
                    "status": "accepted",
                    "name": "Lead ready",
                    "source_id": "src-crm",
                    "evidence_id": "ev-ready",
                    "decision_id": "hdec-ready",
                    "valid_from": "2026-06-29",
                    "valid_to": None,
                    "supersedes": [],
                    "superseded_by": [],
                    "last_verified_at": "2026-06-29",
                    "confidence": "high",
                }
            )
            store.record_data_binding(
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
            )
            store.record_instance(
                {
                    "instance_id": "inst-deal-1",
                    "item_id": "state-lead-ready",
                    "label": "Deal 1",
                    "status": "accepted",
                    "source_id": "src-crm",
                    "evidence_id": "ev-inst",
                    "decision_id": "hdec-inst",
                    "attributes": {"stage": "ready"},
                }
            )
            runtime, _, _ = self.make_runtime(tmp, store_path=store_path)

            canvas = runtime.read_resource("ontology://acquisition/model/canvas")
            bindings = runtime.read_resource("ontology://acquisition/model/bindings")
            graph = runtime.read_resource("ontology://acquisition/model/instance-graph")
            health = runtime.read_resource("ontology://acquisition/model/health")

        canvas_payload = json.loads(canvas["contents"][0]["text"])
        bindings_payload = json.loads(bindings["contents"][0]["text"])
        graph_payload = json.loads(graph["contents"][0]["text"])
        health_payload = json.loads(health["contents"][0]["text"])
        self.assertEqual(canvas_payload["kind"], "configurationCanvas")
        self.assertTrue(any(node["id"] == "state-lead-ready" for node in canvas_payload["nodes"]))
        self.assertEqual(bindings_payload["coverage"]["bindingCount"], 1)
        self.assertEqual(graph_payload["nodes"][0]["instanceId"], "inst-deal-1")
        self.assertEqual(health_payload["kind"], "modelHealth")
        self.assertEqual(health_payload["metrics"]["acceptedItemCount"], 1)
        self.assertEqual(health_payload["metrics"]["claimsWithSourceLocatorPercent"], 100.0)
        self.assertNotIn("items.sourceLocator", health_payload["missingInputs"])

    def test_store_projection_resources_refuse_without_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, _ = self.make_runtime(tmp)

            result = runtime.read_resource("ontology://acquisition/model/canvas")

        self.assertEqual(result["status"], "refused")
        self.assertIn("no operational store", result["refusal_reason"])

    def test_store_projection_resources_do_not_create_missing_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "state" / "missing.sqlite3"
            runtime, _, _ = self.make_runtime(tmp, store_path=store_path)

            result = runtime.read_resource("ontology://acquisition/model/canvas")

        self.assertEqual(result["status"], "refused")
        self.assertIn("operational store does not exist", result["refusal_reason"])
        self.assertFalse(store_path.exists())

    def test_store_backed_review_and_source_event_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, store_path = self.make_store(tmp)
            event = json.loads(SOURCE_EVENT_PATH.read_text(encoding="utf-8"))
            store.record_source_event(event)
            package = {
                "packageId": "mcpkg-runtime-review",
                "moduleId": "acquisition",
                "modelPackId": "mp-test",
                "modelPackVersion": "test",
                "ontologyRevision": "test",
                "compiler": {"name": "test", "version": "test", "mode": "synthetic-fixture"},
                "sourceEventIds": [event["eventId"]],
                "generatedAt": "2026-06-29T00:00:00Z",
                "summary": "Runtime review package.",
                "changes": [
                    {
                        "changeId": "chg-runtime-review",
                        "kind": "new-object",
                        "confidence": "medium",
                        "risk": "medium",
                        "claimKind": "owner-claim",
                        "evidenceGrade": "claim",
                        "sourceRisk": ["manual-memory"],
                        "affectedIds": ["state-lead-ready"],
                        "evidence": [
                            {
                                "sourceEventId": event["eventId"],
                                "locator": "telegram:test#msg-001",
                                "excerpt": "Qualification notes move to sales operations.",
                            }
                        ],
                        "proposedAction": "prepare-staged-proposal",
                    }
                ],
                "review": {
                    "overallAction": "human-review",
                    "owner": "role:owner",
                    "reason": "Needs review.",
                },
                "safety": {
                    "noPii": True,
                    "noSecrets": True,
                    "noRawPayload": True,
                    "noAcceptedMutation": True,
                },
            }
            store.record_model_change_package(package)
            runtime, _, _ = self.make_runtime(tmp, store_path=store_path)

            packages = runtime.read_resource("ontology://acquisition/review/packages")
            one_package = runtime.read_resource("ontology://acquisition/review/packages/mcpkg-runtime-review")
            source_event = runtime.read_resource(f"ontology://acquisition/sources/events/{event['eventId']}")
            health = runtime.read_resource("ontology://acquisition/model/health")

        self.assertIn("mcpkg-runtime-review", packages["contents"][0]["text"])
        self.assertIn("Runtime review package", one_package["contents"][0]["text"])
        self.assertIn(event["eventId"], source_event["contents"][0]["text"])
        health_payload = json.loads(health["contents"][0]["text"])
        self.assertEqual(health_payload["metrics"]["proposalsBlockedByMissingOwner"], 0)
        self.assertIsNotNone(health_payload["metrics"]["averageReviewAgeDays"])
        self.assertNotIn("reviewPackages.createdAt", health_payload["missingInputs"])

    def test_review_packages_summaries_compute_stale_against_current_model_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, store_path = self.make_store(tmp)
            store.record_model_change_package(
                {
                    "packageId": "mcpkg-runtime-stale",
                    "moduleId": "acquisition",
                    "ontologyRevision": "store:compiled-elsewhere",
                    "summary": "Package compiled against an older model revision.",
                    "sourceEventIds": [],
                    "changes": [],
                }
            )
            runtime, _, _ = self.make_runtime(tmp, store_path=store_path)

            packages = runtime.read_resource("ontology://acquisition/review/packages")

        summaries = json.loads(packages["contents"][0]["text"])
        self.assertEqual(
            [summary["packageId"] for summary in summaries], ["mcpkg-runtime-stale"]
        )
        self.assertIs(summaries[0]["stale"], True)

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

    def test_propose_change_rejects_unsafe_proposal_id_without_path_write(self):
        candidate_card = """---
id: c-runtime-unsafe-id
type: concept
status: candidate
source: example-acquisition-source
owner: ontology-operator
last-reviewed: 2026-06-22
next-audit: 2026-09-22
attrs:
  subtype: criterion
---

# Runtime unsafe id

Candidate criterion.
"""
        with tempfile.TemporaryDirectory() as tmp:
            runtime, root, _ = self.make_runtime(tmp)

            result = runtime.call_tool(
                "propose_change",
                {
                    "module_id": "acquisition",
                    "proposal_id": "../prop-escaped",
                    "target": "new",
                    "diff": {"was": "(none)", "now": "runtime unsafe id"},
                    "basis": "Exercise unsafe proposal id refusal.",
                    "source_id": "example-acquisition-source",
                    "source_locator": "tests/test_reference_runtime.py",
                    "confidence": "medium",
                    "input": "agent-inference",
                    "originating_skill": "reference-runtime",
                    "candidate_card_markdown": candidate_card,
                },
            )

            self.assertEqual(result["status"], "refused")
            self.assertIn("proposal_id", result["refusal_reason"])
            self.assertFalse((root / "prop-escaped.md").exists())
            self.assertFalse((root.parent / "prop-escaped.md").exists())
            self.assertEqual(list((root / "staged").glob("*.md")), [])

    def test_propose_change_rejects_sensitive_metadata_before_write(self):
        candidate_card = """---
id: c-runtime-sensitive-metadata
type: concept
status: candidate
source: example-acquisition-source
owner: ontology-operator
last-reviewed: 2026-06-22
next-audit: 2026-09-22
attrs:
  subtype: criterion
---

# Runtime sensitive metadata

Candidate criterion.
"""
        with tempfile.TemporaryDirectory() as tmp:
            runtime, root, _ = self.make_runtime(tmp)

            result = runtime.call_tool(
                "propose_change",
                {
                    "module_id": "acquisition",
                    "proposal_id": "prop-runtime-sensitive-metadata",
                    "target": "new",
                    "diff": {"was": "(none)", "now": "runtime sensitive metadata"},
                    "basis": "Derived from raw_payload in a private export.",
                    "source_id": "example-acquisition-source",
                    "source_locator": "credential_value: do-not-store",
                    "confidence": "medium",
                    "input": "agent-inference",
                    "originating_skill": "reference-runtime",
                    "candidate_card_markdown": candidate_card,
                },
            )

            self.assertEqual(result["status"], "refused")
            self.assertIn("sensitive content", result["refusal_reason"])
            self.assertFalse((root / "staged" / "prop-runtime-sensitive-metadata.md").exists())

    def test_propose_change_schema_constrains_proposal_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, _ = self.make_runtime(tmp)

            tool_map = {tool["name"]: tool for tool in runtime.list_tools()["tools"]}
            proposal_id_schema = tool_map["propose_change"]["inputSchema"]["properties"]["proposal_id"]

        self.assertEqual(proposal_id_schema["pattern"], "^prop-[a-z0-9][a-z0-9-]*$")

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

    def test_generate_draft_ontology_tool_requires_review_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, _ = self.make_runtime(tmp, scopes={"ontology:read"})

            result = runtime.call_tool(
                "generate_draft_ontology",
                {
                    "module_id": "acquisition",
                    "model_pack": json.loads(MODEL_PACK_PATH.read_text(encoding="utf-8")),
                    "source_events": [json.loads(SOURCE_EVENT_PATH.read_text(encoding="utf-8"))],
                },
            )

        self.assertEqual(result["status"], "refused")
        self.assertIn("ontology:admin-review", result["refusal_reason"])
        self.assertEqual(result["draft"], {})

    def test_generate_draft_ontology_tool_refuses_invalid_model_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, _ = self.make_runtime(tmp)

            result = runtime.call_tool(
                "generate_draft_ontology",
                {
                    "module_id": "acquisition",
                    "model_pack": {},
                    "source_events": [json.loads(SOURCE_EVENT_PATH.read_text(encoding="utf-8"))],
                },
            )

        self.assertEqual(result["status"], "refused")
        self.assertIn("moduleId", result["refusal_reason"])
        self.assertEqual(result["draft"], {})

    def test_generate_draft_ontology_tool_refuses_raw_source_event_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, _ = self.make_runtime(tmp)
            source_event = json.loads(SOURCE_EVENT_PATH.read_text(encoding="utf-8"))
            source_event["rawPayload"] = "private source body"

            result = runtime.call_tool(
                "generate_draft_ontology",
                {
                    "module_id": "acquisition",
                    "model_pack": json.loads(MODEL_PACK_PATH.read_text(encoding="utf-8")),
                    "source_events": [source_event],
                },
            )

        self.assertEqual(result["status"], "refused")
        self.assertIn("rawPayload", result["draft"]["refusals"][0]["reason"])

    def test_generate_draft_ontology_tool_returns_reviewable_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, trace_path = self.make_runtime(tmp)

            result = runtime.call_tool(
                "generate_draft_ontology",
                {
                    "module_id": "acquisition",
                    "model_pack": json.loads(MODEL_PACK_PATH.read_text(encoding="utf-8")),
                    "source_events": [json.loads(SOURCE_EVENT_PATH.read_text(encoding="utf-8"))],
                    "accepted_context": {"generatedAt": "2026-06-29T00:00:00Z"},
                },
            )
            events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(result["status"], "drafted")
        self.assertEqual(result["draft"]["kind"], "draftOntology")
        self.assertTrue(result["draft"]["safety"]["noAcceptedMutation"])
        self.assertTrue(any(event["name"] == "generate_draft_ontology" for event in events))


if __name__ == "__main__":
    unittest.main()

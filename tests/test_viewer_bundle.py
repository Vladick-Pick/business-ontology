import json
from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_viewer_bundle as bundle  # noqa: E402
import links_validate  # noqa: E402

EXAMPLE = REPO_ROOT / "examples" / "acquisition-ontology"
EXAMPLE_V2 = REPO_ROOT / "examples" / "business-attraction-v2"
VIEWER_HTML = REPO_ROOT / "viewer" / "index.html"


class ViewerBundleTests(unittest.TestCase):
    def setUp(self):
        self.data = bundle.build_bundle(EXAMPLE, "acquisition", "test", "2026-12-01")

    def test_bundle_is_json_serializable(self):
        json.dumps(self.data, ensure_ascii=False)

    def test_current_bundle_has_no_viewer_projection_diagnostics(self):
        self.assertEqual(self.data["viewerDiagnostics"], [])

    def test_cards_carry_required_fields(self):
        self.assertGreaterEqual(len(self.data["cards"]), 8)
        required = {"id", "type", "status", "links", "title", "sections"}
        for card in self.data["cards"]:
            self.assertTrue(required <= set(card), card.get("id"))
            self.assertIn(card["type"], bundle.CARD_TYPES)
            self.assertIn(card["type"], links_validate.AUTHORING_CARD_TYPES)

    def test_edges_reference_real_cards_or_targets(self):
        self.assertTrue(self.data["edges"])
        ids = {c["id"] for c in self.data["cards"]}
        for edge in self.data["edges"]:
            self.assertIn(edge["from"], ids)
            self.assertIn("type", edge)

    def test_known_card_and_interface_render_inputs(self):
        ql = next((c for c in self.data["cards"] if c["id"] == "qualified-lead"), None)
        self.assertIsNotNone(ql)
        self.assertEqual(ql["type"], "artifact")
        self.assertEqual(ql["status"], "accepted")
        self.assertIn("measured-by", ql["links"])
        self.assertIn("lifecycle", ql["links"])
        self.assertNotIn("in-state", ql["links"])
        iface = next((c for c in self.data["cards"] if c["type"] == "interface"), None)
        self.assertIsNotNone(iface)
        self.assertIn("participants", iface["attrs"])

    def test_current_example_bundle_has_no_deprecated_aliases(self):
        deprecated_types = set(links_validate.DEPRECATED_TYPE_ALIASES)
        deprecated_links = set(links_validate.DEPRECATED_LINK_ALIASES)

        for card in self.data["cards"]:
            self.assertNotIn(card["type"], deprecated_types, card["id"])
            self.assertFalse(deprecated_links.intersection(card.get("links", {})), card["id"])
        for edge in self.data["edges"]:
            self.assertNotIn(edge["type"], deprecated_links, edge)

    def test_viewer_fallback_demo_is_v2_clean(self):
        html = VIEWER_HTML.read_text(encoding="utf-8")

        self.assertNotIn('"type":"concept"', html)
        self.assertNotIn('"type":"module"', html)
        self.assertNotIn('"in-state"', html)
        self.assertIn('"type":"artifact"', html)
        self.assertIn('"lifecycle"', html)

    def test_sources_and_health_present(self):
        self.assertTrue(any(s["id"] == "example-acquisition-source" for s in self.data["sources"]))
        self.assertIn("byStatus", self.data["health"])
        self.assertGreater(self.data["health"]["byStatus"].get("accepted", 0), 0)

    def test_bundle_carries_company_model_language(self):
        self.assertEqual(self.data["companyModelLanguage"], "pending-owner-selection")
        localized = bundle.build_bundle(EXAMPLE, "acquisition", "test", "2026-12-01", company_model_language="ru")
        self.assertEqual(localized["companyModelLanguage"], "ru")

    def test_bundle_carries_publish_metadata(self):
        source_readiness = {
            "configuredCount": 0,
            "sourceConnectedCount": 0,
            "liveProvenCount": 2,
            "scheduledCount": 0,
            "failedCount": 1,
            "sourceInstanceIdsByStatus": {
                "configured": [],
                "source-connected": [],
                "live-proven": ["tg", "meeting"],
                "scheduled": [],
                "failed": ["crm"],
            },
            "lastProofIdsBySource": {"tg": "proof-tg"},
        }
        data = bundle.build_bundle(
            EXAMPLE,
            "acquisition",
            "legacy-revision",
            "2026-12-01",
            company_model_language="ru",
            package_version="0.10.0",
            package_commit="abc123",
            model_revision="model789",
            source_readiness=source_readiness,
            open_human_request_count=3,
            validation_status="passed",
        )

        self.assertEqual(data["asOf"], "2026-12-01")
        self.assertEqual(data["packageVersion"], "0.10.0")
        self.assertEqual(data["packageCommit"], "abc123")
        self.assertEqual(data["modelRevision"], "model789")
        self.assertEqual(data["companyModelLanguage"], "ru")
        self.assertEqual(data["sourceReadiness"]["liveProvenCount"], 2)
        self.assertEqual(data["openHumanRequestCount"], 3)
        self.assertEqual(data["validationStatus"], "passed")

    def test_v2_bundle_preserves_trust_metadata_fields(self):
        data = bundle.build_bundle(EXAMPLE_V2, "biz-attraction", "test", "2026-12-01")
        metric = next(c for c in data["cards"] if c["id"] == "m-sla1")
        role = next(c for c in data["cards"] if c["id"] == "r-ki")

        self.assertEqual(metric["volatility"], "high")
        self.assertEqual(metric["evidence"], ["srcevt-btx-0630"])
        self.assertEqual(role["volatility"], "medium")
        self.assertIn("КИ", role["aliases"])
        self.assertIn("консультант интервьюер", role["aliases"])

    def test_unknown_source_is_unresolved_in_health_and_source_trust(self):
        cards = [
            {"id": "known-card", "status": "accepted", "owner": "owner", "source": "src-known", "nextAudit": ""},
            {"id": "unknown-card", "status": "accepted", "owner": "owner", "source": "unknown", "nextAudit": ""},
            {"id": "missing-card", "status": "accepted", "owner": "owner", "source": "src-missing", "nextAudit": ""},
        ]
        sources = [{"id": "src-known", "trust": "accepted", "owner": "owner", "accessMode": "fixture"}]

        health = bundle._health(cards, sources, None)
        source_trust = bundle._source_trust_projection(cards, sources, bundle.empty_source_readiness())

        self.assertEqual(health["sourceResolvedPct"], 33)
        self.assertEqual(health["unresolvedSourceCardIds"], ["unknown-card", "missing-card"])
        self.assertEqual(health["unknownSourceCardIds"], ["unknown-card"])
        self.assertEqual(source_trust["unresolvedSourceCardIds"], ["unknown-card", "missing-card"])
        self.assertEqual(source_trust["unknownSourceCardIds"], ["unknown-card"])
        self.assertEqual(source_trust["cardsBySource"]["unknown"], ["unknown-card"])

    def test_source_trust_lists_dependents_and_exact_readiness_matches_only(self):
        source_readiness = {
            "configuredCount": 0,
            "sourceConnectedCount": 0,
            "liveProvenCount": 1,
            "scheduledCount": 0,
            "failedCount": 0,
            "sourceInstanceIdsByStatus": {
                "configured": [],
                "source-connected": [],
                "live-proven": ["src-bitrix24-export"],
                "scheduled": [],
                "failed": [],
            },
            "lastProofIdsBySource": {"src-bitrix24-export": "proof-bitrix24-001"},
        }
        data = bundle.build_bundle(
            EXAMPLE_V2,
            "biz-attraction",
            "test",
            "2026-12-01",
            source_readiness=source_readiness,
        )
        sources = {source["id"]: source for source in data["sourceTrust"]["sources"]}

        bitrix = sources["src-bitrix24-export"]
        self.assertIn("m-sla1", bitrix["dependentCardIds"])
        self.assertIn("st-deal", bitrix["dependentCardIds"])
        self.assertEqual(bitrix["dependentCardCount"], len(bitrix["dependentCardIds"]))
        self.assertEqual(bitrix["readinessStatus"], "live-proven")
        self.assertEqual(bitrix["lastProofId"], "proof-bitrix24-001")
        self.assertEqual(sources["src-clubfirst-spec"]["readinessStatus"], "unknown")

    def test_source_readiness_failed_status_wins_over_stale_live_proof(self):
        source_readiness = {
            "sourceInstanceIdsByStatus": {
                "configured": [],
                "source-connected": [],
                "live-proven": ["src-bitrix24-export"],
                "scheduled": [],
                "failed": ["src-bitrix24-export"],
            }
        }

        self.assertEqual(bundle._source_readiness_status("src-bitrix24-export", source_readiness), "failed")

    def test_review_items_include_card_local_questions_and_health_gaps(self):
        source_readiness = {
            "sourceInstanceIdsByStatus": {
                "configured": [],
                "source-connected": [],
                "live-proven": [],
                "scheduled": [],
                "failed": ["src-bitrix24-export"],
            }
        }
        data = bundle.build_bundle(
            EXAMPLE_V2,
            "biz-attraction",
            "test",
            "2026-12-01",
            source_readiness=source_readiness,
            open_human_request_count=2,
        )
        review_items = data["reviewItems"]
        by_card = {(item.get("kind"), item.get("cardId")): item for item in review_items}
        kinds = {item["kind"] for item in review_items}

        self.assertIn(("drift", "d-autopurchase"), by_card)
        self.assertIn(("open-question", "if-lidgen-attraction"), by_card)
        self.assertIn("source-gap", kinds)
        self.assertIn("stale-audit", kinds)
        self.assertIn("human-request", kinds)
        self.assertLessEqual(len(review_items), 80)
        self.assertIn("tariff", by_card[("drift", "d-autopurchase")]["text"])
        self.assertEqual(by_card[("open-question", "if-lidgen-attraction")]["owner"], "r-attraction-lead")

    def test_open_human_requests_are_rendered_as_specific_review_items(self):
        data = bundle.build_bundle(
            EXAMPLE_V2,
            "biz-attraction",
            "test",
            "2026-12-01",
            company_model_language="ru",
            open_human_requests=[
                {
                    "requestId": "hreq-viewer-owner-001",
                    "kind": "migration",
                    "status": "open",
                    "owner": "owner",
                    "channel": "telegram:dm-owner",
                    "messageRef": "tg#42",
                    "prompt": "Подтвердить владельца решения d-autopurchase?",
                    "recommendedAnswer": "Оставить r-attraction-lead, если нет нового приказа.",
                    "blocks": ["package:mcpkg-001"],
                    "sourceRef": "srcevt-btx-0630",
                    "packageId": "mcpkg-001",
                    "askedAt": "2026-07-08T09:00:00Z",
                    "dueAt": "2026-07-09T09:00:00Z",
                }
            ],
        )

        self.assertEqual(data["openHumanRequestCount"], 1)
        self.assertEqual(data["openHumanRequests"][0]["requestId"], "hreq-viewer-owner-001")
        self.assertEqual(data["openHumanRequests"][0]["packageId"], "mcpkg-001")
        self.assertNotIn("answerSummary", data["openHumanRequests"][0])
        human_items = [item for item in data["reviewItems"] if item["kind"] == "human-request"]
        self.assertEqual(len(human_items), 1)
        self.assertEqual(human_items[0]["requestId"], "hreq-viewer-owner-001")
        self.assertIn("Подтвердить владельца", human_items[0]["text"])
        self.assertIn("Ответить", human_items[0]["action"])

    def test_review_item_system_actions_follow_company_model_language(self):
        data = bundle.build_bundle(
            EXAMPLE_V2,
            "biz-attraction",
            "test",
            "2026-12-01",
            company_model_language="ru",
            open_human_request_count=1,
        )
        actions = [item["action"] for item in data["reviewItems"]]

        self.assertTrue(any("Открыть карточку" in action for action in actions), actions)
        self.assertTrue(any("Ответить" in action for action in actions), actions)
        self.assertFalse(any("Open the card" in action for action in actions), actions)
        self.assertFalse(any("Answer, defer" in action for action in actions), actions)

    def test_search_text_indexes_safe_attrs_links_owner_source_aliases_and_evidence(self):
        data = bundle.build_bundle(EXAMPLE_V2, "biz-attraction", "test", "2026-12-01")
        cards = {card["id"]: card for card in data["cards"]}

        metric_text = cards["m-sla1"]["searchText"]
        self.assertIn("SLA таймер", metric_text)
        self.assertIn("srcevt-btx-0630", metric_text)
        self.assertIn("r-attraction-lead", metric_text)
        self.assertIn("src-bitrix24-export", metric_text)

        role_text = cards["r-ki"]["searchText"]
        self.assertIn("КИ", role_text)
        self.assertIn("консультант интервьюер", role_text)

        process_text = cards["p-handle-delivery"]["searchText"]
        self.assertIn("d-autopurchase", process_text)
        self.assertIn("r-ki", process_text)

    def test_no_secret_values_in_bundle(self):
        import re

        blob = json.dumps(self.data, ensure_ascii=False)
        # Policy text may legitimately say "rawPayloadAccess=false"; what must
        # never appear is an actual secret/credential value or a raw key blob.
        for pattern in [r"ghp_[A-Za-z0-9]", r"\bsk-[A-Za-z0-9]{16,}", r"xox[baprs]-", r"-----BEGIN "]:
            self.assertIsNone(re.search(pattern, blob), pattern)

    def test_show_model_skill_requires_official_publish_and_fallback_reason(self):
        skill = (REPO_ROOT / "skills" / "show-model" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("publish_viewer.py", skill)
        self.assertIn("VIEWER_PUBLISH_REPORT.json", skill)
        self.assertIn("Do not present custom HTML as the", skill)
        self.assertIn("Viewer fallback: official publish failed because <reason>.", skill)
        self.assertIn("permanent static URL", skill)
        self.assertIn("after every accepted model change", skill)
        self.assertIn("source-readiness", skill)
        self.assertIn("open human request count", skill)
        self.assertIn("fail closed with a visible official-load", skill)
        self.assertIn("Do not share a link when the page is in explicit demo mode", skill)
        self.assertIn("official-load errors are reported, not hidden by a sample", skill)
        self.assertIn("review cockpit", skill)
        self.assertIn("ontology.json.reviewItems", skill)
        self.assertIn('Do not say "no open', skill)
        self.assertIn("questions\" unless `reviewItems` exists and is empty", skill)

    def test_viewer_readme_documents_review_cockpit_contract(self):
        readme = (REPO_ROOT / "viewer" / "README.md").read_text(encoding="utf-8")

        self.assertIn("review cockpit", readme)
        self.assertIn('"reviewItems"', readme)
        self.assertIn('"searchText"', readme)
        self.assertIn('must not say "no open questions"', readme)
        self.assertIn("unless `reviewItems` is empty", readme)

    def test_v2_business_viewer_derives_production_systems_from_inverse_part_of(self):
        data = bundle.build_bundle(EXAMPLE_V2, "biz-attraction", "test", "2026-12-01")
        business = next(c for c in data["cards"] if c["id"] == "biz-attraction")

        self.assertIn("ps-attraction-btx", business["viewer"]["productionSystems"])
        self.assertEqual(business["viewer"]["inputArtifacts"], ["a-qualified-lead"])
        self.assertEqual(business["viewer"]["outputArtifacts"], ["a-deal"])
        self.assertEqual(business["viewer"]["inboundInterfaces"], ["if-lidgen-attraction"])
        self.assertEqual(business["viewer"]["outboundInterfaces"], [])

    def test_business_viewer_does_not_treat_consumed_tools_as_input_artifacts(self):
        cards = [
            {
                "id": "biz-attraction",
                "type": "business",
                "attrs": {},
                "links": {"consumes": ["a-qualified-lead", "t-bitrix"]},
                "title": "Привлечение",
            },
            {"id": "a-qualified-lead", "type": "artifact", "attrs": {}, "links": {}, "title": "Qualified lead"},
            {"id": "t-bitrix", "type": "tool", "attrs": {}, "links": {}, "title": "Bitrix24"},
        ]

        bundle._attach_viewer_projection(cards)

        self.assertEqual(cards[0]["viewer"]["inputArtifacts"], ["a-qualified-lead"])
        self.assertEqual(bundle.viewer_projection_diagnostics(cards), [])

    def test_v2_production_system_viewer_derives_stage_rows_from_objects(self):
        data = bundle.build_bundle(EXAMPLE_V2, "biz-attraction", "test", "2026-12-01")
        ps = next(c for c in data["cards"] if c["id"] == "ps-attraction-btx")

        self.assertEqual(
            ps["viewer"]["stages"][0],
            {
                "id": "ps-attraction-btx-stage-1",
                "state": "st-deal",
                "label": "Звонок-знакомство",
                "processes": ["p-handle-delivery"],
                "roles": ["r-ki"],
            },
        )

    def test_v2_process_viewer_derives_step_labels_and_edges_from_does(self):
        data = bundle.build_bundle(EXAMPLE_V2, "biz-attraction", "test", "2026-12-01")
        process = next(c for c in data["cards"] if c["id"] == "p-handle-delivery")
        steps = process["viewer"]["processSteps"]

        self.assertEqual(steps[0]["label"], "Звонит новому лиду в течение 24 рабочих часов после назначения (SLA на этом шаге, не на весь SLA-1)")
        self.assertEqual(steps[0]["next"], "step-2-qualify")
        self.assertEqual(steps[1]["shape"], "diamond")
        self.assertEqual(steps[1]["label"], "Лид проходит по критериям сегмента?")
        self.assertEqual(steps[1]["activity"], "Уточняет сегмент и готовность ко встрече по критериям if-lidgen-attraction.attrs.qualities")
        self.assertEqual(steps[1]["yes"], "step-3-book")
        self.assertEqual(steps[1]["no"], "step-2a-reject")
        reject_step = next(step for step in steps if step["id"] == "step-2a-reject")
        self.assertNotIn("next", reject_step)

    def test_process_viewer_does_not_infer_edges_from_step_order(self):
        object_steps = bundle._process_steps(
            {
                "id": "p-no-implicit-flow",
                "attrs": {
                    "steps": [
                        {"id": "step-a", "does": "First action"},
                        {"id": "step-b", "does": "Second action"},
                    ]
                },
            }
        )
        scalar_steps = bundle._process_steps(
            {"id": "p-no-implicit-flow", "attrs": {"steps": ["step-a", "step-b"]}}
        )

        self.assertNotIn("next", object_steps[0])
        self.assertNotIn("next", object_steps[1])
        self.assertNotIn("next", scalar_steps[0])
        self.assertNotIn("next", scalar_steps[1])

    def test_viewer_projection_diagnostics_reject_missing_process_structure_refs(self):
        cards = [
            {
                "id": "ps-bad",
                "type": "production-system",
                "attrs": {
                    "stages": [
                        {
                            "state": "st-missing",
                            "processes": ["p-ok", "p-missing"],
                            "roles": ["r-ok", "a-not-role"],
                        }
                    ]
                },
                "links": {},
                "title": "Bad system",
            },
            {
                "id": "p-ok",
                "type": "process",
                "attrs": {"steps": [{"id": "step-1", "role": "r-missing", "next": "step-2"}]},
                "links": {},
                "title": "Bad process",
            },
            {"id": "r-ok", "type": "role", "attrs": {}, "links": {}, "title": "Role"},
            {"id": "a-not-role", "type": "artifact", "attrs": {}, "links": {}, "title": "Not a role"},
        ]

        bundle._attach_viewer_projection(cards)
        diagnostics = bundle.viewer_projection_diagnostics(cards)

        observed = {
            (item["field"], item["target_id"], item["expected_type"], item["actual_type"])
            for item in diagnostics
        }
        self.assertIn(("viewer.stages[ps-bad-stage-1].state", "st-missing", "state", "missing"), observed)
        self.assertIn(("viewer.stages[ps-bad-stage-1].processes", "p-missing", "process", "missing"), observed)
        self.assertIn(("viewer.stages[ps-bad-stage-1].roles", "a-not-role", "role", "artifact"), observed)
        self.assertIn(("viewer.processSteps[step-1].next", "step-2", "process-step", "missing"), observed)
        self.assertIn(("viewer.processSteps[step-1].role", "r-missing", "role", "missing"), observed)

    def test_viewer_projection_diagnostics_check_state_transition_authority_ids(self):
        cards = [
            {
                "id": "st-bad",
                "type": "state",
                "attrs": {
                    "transitions": [
                        {"from": "new", "to": "done", "authority": "missing-role"},
                        {"from": "done", "to": "closed", "authority": "a-not-authority"},
                        {"from": "closed", "to": "archive", "authority": "owner review"},
                    ]
                },
                "links": {},
                "title": "Bad state",
            },
            {"id": "a-not-authority", "type": "artifact", "attrs": {}, "links": {}, "title": "Artifact"},
        ]

        diagnostics = bundle.viewer_projection_diagnostics(cards)
        observed = {
            (item["field"], item["target_id"], item["expected_type"], item["actual_type"])
            for item in diagnostics
        }

        self.assertIn(("viewer.transitions[0].authority", "missing-role", "role|decision", "missing"), observed)
        self.assertIn(("viewer.transitions[1].authority", "a-not-authority", "role|decision", "artifact"), observed)
        self.assertFalse(any(item["target_id"] == "owner review" for item in diagnostics))

    def test_v2_transition_authorities_accept_roles_and_decisions(self):
        data = bundle.build_bundle(EXAMPLE_V2, "biz-attraction", "test", "2026-12-01")

        self.assertEqual(data["viewerDiagnostics"], [])

    def test_viewer_html_reads_derived_v2_viewer_fields(self):
        html = VIEWER_HTML.read_text(encoding="utf-8")

        self.assertIn("viewer.productionSystems", html)
        self.assertIn("viewer.stages", html)
        self.assertIn("viewer.processSteps", html)
        self.assertIn("VIEWER_PUBLISH_REPORT.json", html)
        self.assertIn("bundle hash mismatch", html)
        self.assertIn("Схема не построилась: не загружен dagre.", html)
        self.assertIn("Этапы производственной системы", html)
        self.assertIn("sourceTrustData", html)
        self.assertIn("sourceResolvedPct", html)
        self.assertIn("волатильность", html)
        self.assertIn("evidence:", html)
        self.assertIn("алиасы", html)
        self.assertIn("readiness/proof", html)
        self.assertIn("зависимых карточек", html)
        self.assertIn("unresolvedSourceCardIds", html)
        self.assertIn("synthetic-fixture", html)
        self.assertIn("source gaps", html)
        self.assertIn("Шаги процесса", html)
        self.assertIn("Матрица переходов", html)
        self.assertIn("Коды причин", html)
        self.assertIn("authority", html)
        self.assertIn("effect", html)
        self.assertIn("warning / missing fields", html)
        self.assertIn("Decision contract", html)
        self.assertIn("measurement-convention", html)
        self.assertIn("override-policy", html)
        self.assertIn("blast-radius", html)
        self.assertIn("Measurement contract", html)
        self.assertIn("baseline.source-event", html)
        self.assertIn("binding.locator", html)
        self.assertIn("refresh cadence", html)
        self.assertIn("Influenced metrics", html)
        self.assertIn("Очередь ревью", html)
        self.assertIn("reviewItems", html)
        self.assertIn("reviewItemHtml", html)
        self.assertIn("reviewData", html)
        self.assertIn("searchText", html)
        self.assertIn("attrs, links, owner/source", html)

    def test_viewer_official_mode_fails_closed_without_demo_fallback(self):
        html = VIEWER_HTML.read_text(encoding="utf-8")

        self.assertNotIn('loadOfficialBundle()\n  .catch(()=>tryFetch("./sample-clubfirst.json"', html)
        self.assertIn("function isExplicitDemoMode()", html)
        self.assertIn('params.get("demo")==="1"', html)
        self.assertIn('hash==="demo"', html)
        self.assertIn("function showOfficialLoadError(error)", html)
        self.assertIn("Официальный viewer не загрузился", html)
        self.assertIn("Демо-данные не подставлены", html)
        self.assertIn("Показан демонстрационный набор", html)
        self.assertIn("Это не текущая модель компании", html)
        self.assertIn("?demo=1", html)
        self.assertIn("#demo", html)


if __name__ == "__main__":
    unittest.main()

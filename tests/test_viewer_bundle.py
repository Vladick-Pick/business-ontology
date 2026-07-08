import json
from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_viewer_bundle as bundle  # noqa: E402
import links_validate  # noqa: E402

EXAMPLE = REPO_ROOT / "examples" / "acquisition-ontology"
VIEWER_HTML = REPO_ROOT / "viewer" / "index.html"


class ViewerBundleTests(unittest.TestCase):
    def setUp(self):
        self.data = bundle.build_bundle(EXAMPLE, "acquisition", "test", "2026-12-01")

    def test_bundle_is_json_serializable(self):
        json.dumps(self.data, ensure_ascii=False)

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

        self.assertEqual(data["packageVersion"], "0.10.0")
        self.assertEqual(data["packageCommit"], "abc123")
        self.assertEqual(data["modelRevision"], "model789")
        self.assertEqual(data["companyModelLanguage"], "ru")
        self.assertEqual(data["sourceReadiness"]["liveProvenCount"], 2)
        self.assertEqual(data["openHumanRequestCount"], 3)
        self.assertEqual(data["validationStatus"], "passed")

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


if __name__ == "__main__":
    unittest.main()

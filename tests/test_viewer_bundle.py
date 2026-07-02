import json
from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_viewer_bundle as bundle  # noqa: E402

EXAMPLE = REPO_ROOT / "examples" / "acquisition-ontology"


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

    def test_edges_reference_real_cards_or_targets(self):
        self.assertTrue(self.data["edges"])
        ids = {c["id"] for c in self.data["cards"]}
        for edge in self.data["edges"]:
            self.assertIn(edge["from"], ids)
            self.assertIn("type", edge)

    def test_known_card_and_interface_render_inputs(self):
        ql = next((c for c in self.data["cards"] if c["id"] == "qualified-lead"), None)
        self.assertIsNotNone(ql)
        self.assertEqual(ql["status"], "accepted")
        self.assertIn("measured-by", ql["links"])
        iface = next((c for c in self.data["cards"] if c["type"] == "interface"), None)
        self.assertIsNotNone(iface)
        self.assertIn("participants", iface["attrs"])

    def test_sources_and_health_present(self):
        self.assertTrue(any(s["id"] == "example-acquisition-source" for s in self.data["sources"]))
        self.assertIn("byStatus", self.data["health"])
        self.assertGreater(self.data["health"]["byStatus"].get("accepted", 0), 0)

    def test_no_secret_values_in_bundle(self):
        import re

        blob = json.dumps(self.data, ensure_ascii=False)
        # Policy text may legitimately say "rawPayloadAccess=false"; what must
        # never appear is an actual secret/credential value or a raw key blob.
        for pattern in [r"ghp_[A-Za-z0-9]", r"\bsk-[A-Za-z0-9]{16,}", r"xox[baprs]-", r"-----BEGIN "]:
            self.assertIsNone(re.search(pattern, blob), pattern)


if __name__ == "__main__":
    unittest.main()

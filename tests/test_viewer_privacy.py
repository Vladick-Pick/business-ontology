import json
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_viewer_bundle  # noqa: E402
import viewer_privacy  # noqa: E402


class ViewerPrivacyTests(unittest.TestCase):
    def test_human_request_projection_removes_private_routing_and_masks_direct_owner(self):
        projected = build_viewer_bundle._human_request_projection(
            {
                "requestId": "hreq-public-1",
                "status": "open",
                "owner": "telegram:718706687",
                "channel": "telegram:718706687",
                "messageRef": "tg#42",
                "prompt": "Confirm the current owner role.",
            }
        )

        self.assertEqual(projected["owner"], "owner")
        self.assertNotIn("channel", projected)
        self.assertNotIn("messageRef", projected)
        self.assertEqual(viewer_privacy.privacy_violations(projected), [])

    def test_privacy_report_names_paths_without_echoing_private_values(self):
        private_value = "telegram:718706687"
        report = viewer_privacy.privacy_report(
            {
                "openHumanRequests": [
                    {
                        "owner": private_value,
                        "channel": private_value,
                        "prompt": "Write to owner@example.test or +90 555 123 45 67",
                    }
                ],
                "reviewItems": [{"messageRef": "tg#42"}],
            }
        )

        self.assertEqual(report["status"], "failed")
        serialized = json.dumps(report, sort_keys=True)
        self.assertNotIn(private_value, serialized)
        self.assertNotIn("owner@example.test", serialized)
        paths = {item["path"] for item in report["violations"]}
        self.assertIn("openHumanRequests[0].owner", paths)
        self.assertIn("openHumanRequests[0].channel", paths)
        self.assertIn("openHumanRequests[0].prompt", paths)
        self.assertIn("reviewItems[0].messageRef", paths)
        self.assertIn("phone-number", {item["kind"] for item in report["violations"]})

    def test_privacy_report_blocks_secret_like_and_raw_working_fields(self):
        secret_like = "sk-" + "a" * 20
        report = viewer_privacy.privacy_report(
            {
                "workingCards": [{"locator": "private:packet#1"}],
                "notes": secret_like,
            }
        )

        self.assertEqual(report["status"], "failed")
        kinds = {item["kind"] for item in report["violations"]}
        self.assertEqual(kinds, {"raw-source-field", "secret-like-value"})


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import viewer_reachability


class ViewerReachabilityTests(unittest.TestCase):
    def make_workspace(self, root: Path, url: str = "https://model.example.test/interlab/") -> Path:
        workspace = root / "workspace"
        viewer = workspace / "viewer"
        viewer.mkdir(parents=True)
        (workspace / "runtime-config.json").write_text(
            json.dumps(
                {
                    "viewer_output_path": "viewer",
                    "viewer_publication": {
                        "mode": "static-url",
                        "public_url": url,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (viewer / "VIEWER_PUBLISH_REPORT.json").write_text(
            json.dumps(
                {
                    "status": "published",
                    "privacy": {"status": "passed", "policy": "public-viewer-v1"},
                    "publication": {
                        "mode": "static-url",
                        "public_url": url,
                        "status": "verified",
                        "infrastructure_status": "verified",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return workspace

    def test_link_can_be_claimed_once_until_owner_responds(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))

            first = viewer_reachability.claim_link(workspace)
            second = viewer_reachability.claim_link(workspace)

            self.assertTrue(first["shareable"])
            self.assertEqual(first["public_url"], "https://model.example.test/interlab/")
            self.assertEqual(first["owner_reachability"], "awaiting-owner")
            self.assertFalse(second["shareable"])
            self.assertEqual(second["public_url"], "")
            self.assertEqual(second["reason"], "awaiting-owner-confirmation")
            report = json.loads(
                (workspace / "viewer" / "VIEWER_PUBLISH_REPORT.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                report["publication"]["owner_reachability"]["status"],
                "awaiting-owner",
            )

    def test_cli_returns_no_url_and_nonzero_when_repeat_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            command = [
                sys.executable,
                str(Path(viewer_reachability.__file__).resolve()),
                "--workspace",
                str(workspace),
                "claim",
            ]

            first = subprocess.run(command, text=True, capture_output=True, check=False)
            second = subprocess.run(command, text=True, capture_output=True, check=False)

            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertEqual(second.returncode, viewer_reachability.SHARE_BLOCKED)
            payload = json.loads(second.stdout)
            self.assertFalse(payload["shareable"])
            self.assertEqual(payload["public_url"], "")

    def test_owner_failure_blocks_same_url_even_when_infrastructure_is_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            viewer_reachability.claim_link(workspace)

            recorded = viewer_reachability.record_feedback(
                workspace,
                status="unreachable",
                reason_code="connection-failed",
            )
            blocked = viewer_reachability.claim_link(workspace)

            self.assertEqual(recorded["owner_reachability"], "unreachable")
            self.assertFalse(blocked["shareable"])
            self.assertEqual(blocked["public_url"], "")
            report = json.loads(
                (workspace / "viewer" / "VIEWER_PUBLISH_REPORT.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(report["publication"]["infrastructure_status"], "verified")
            self.assertEqual(report["publication"]["status"], "owner-unreachable")

    def test_owner_confirmation_allows_repeat_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            viewer_reachability.claim_link(workspace)
            viewer_reachability.record_feedback(workspace, status="confirmed")

            first = viewer_reachability.claim_link(workspace)
            second = viewer_reachability.claim_link(workspace)

            self.assertTrue(first["shareable"])
            self.assertTrue(second["shareable"])
            self.assertFalse(first["requires_owner_confirmation"])
            report = json.loads(
                (workspace / "viewer" / "VIEWER_PUBLISH_REPORT.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(report["publication"]["status"], "verified")
            self.assertEqual(
                report["publication"]["owner_reachability"]["status"],
                "confirmed",
            )

    def test_changed_url_gets_a_new_single_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            viewer_reachability.claim_link(workspace)
            viewer_reachability.record_feedback(
                workspace,
                status="unreachable",
                reason_code="connection-failed",
            )
            new_url = "https://new-model.example.test/interlab/"
            config_path = workspace / "runtime-config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["viewer_publication"]["public_url"] = new_url
            config_path.write_text(json.dumps(config) + "\n", encoding="utf-8")
            report_path = workspace / "viewer" / "VIEWER_PUBLISH_REPORT.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["publication"] = {
                "mode": "static-url",
                "public_url": new_url,
                "status": "verified",
                "infrastructure_status": "verified",
            }
            report_path.write_text(json.dumps(report) + "\n", encoding="utf-8")

            claimed = viewer_reachability.claim_link(workspace)

            self.assertTrue(claimed["shareable"])
            self.assertEqual(claimed["public_url"], new_url)

    def test_feedback_reason_is_a_bounded_code_not_raw_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))

            with self.assertRaises(viewer_reachability.ViewerReachabilityError):
                viewer_reachability.record_feedback(
                    workspace,
                    status="unreachable",
                    reason_code="owner pasted a private browser trace",
                )


if __name__ == "__main__":
    unittest.main()

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from runtime.review_authority import (
    ReviewAuthorityError,
    channels_equivalent,
    is_review_authorized,
    validate_review_authority,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIGURE_SCRIPT = REPO_ROOT / "scripts" / "configure_review_authority.py"


class ReviewAuthorityTests(unittest.TestCase):
    def policy(self) -> dict[str, object]:
        return {
            "policyVersion": 1,
            "businessId": "interlab",
            "channels": [
                {
                    "channel": "telegram:systematization-interlab",
                    "aliases": ["telegram:-1000000000001"],
                    "reviewScopes": ["routine", "high-risk"],
                    "actors": ["telegram:reviewer-a", "telegram:reviewer-b"],
                }
            ],
        }

    def test_channel_aliases_and_scopes_are_explicit(self):
        policy = validate_review_authority(self.policy())

        self.assertTrue(
            channels_equivalent(
                policy,
                "telegram:systematization-interlab",
                "telegram:-1000000000001",
            )
        )
        self.assertTrue(
            is_review_authorized(
                policy,
                actor="telegram:reviewer-b",
                channel="telegram:-1000000000001",
                scope="high-risk",
            )
        )
        self.assertFalse(
            is_review_authorized(
                policy,
                actor="telegram:unknown",
                channel="telegram:-1000000000001",
                scope="routine",
            )
        )

    def test_empty_policy_is_valid_but_grants_nothing(self):
        policy = validate_review_authority(
            {"policyVersion": 1, "businessId": "interlab", "channels": []}
        )

        self.assertFalse(
            is_review_authorized(
                policy,
                actor="telegram:anyone",
                channel="telegram:anywhere",
                scope="routine",
            )
        )

    def test_ambiguous_aliases_are_rejected(self):
        payload = self.policy()
        channels = payload["channels"]
        assert isinstance(channels, list)
        channels.append(
            {
                "channel": "telegram:other",
                "aliases": ["telegram:-1000000000001"],
                "reviewScopes": ["routine"],
                "actors": ["telegram:reviewer-c"],
            }
        )

        with self.assertRaises(ReviewAuthorityError):
            validate_review_authority(payload)

    def test_configure_command_writes_private_policy_without_echoing_actor_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "agent-state").mkdir()
            (workspace / "runtime-config.json").write_text(
                json.dumps(
                    {
                        "module_id": "interlab",
                        "review_authority_policy_path": "agent-state/review-authority.json",
                    }
                ),
                encoding="utf-8",
            )
            policy_json = json.dumps(self.policy())

            result = subprocess.run(
                [sys.executable, str(CONFIGURE_SCRIPT), "--workspace", str(workspace)],
                cwd=REPO_ROOT,
                input=policy_json,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("telegram:reviewer-a", result.stdout)
            output = json.loads(result.stdout)
            self.assertEqual(output["actorGrantCount"], 2)
            policy_path = workspace / "agent-state" / "review-authority.json"
            self.assertEqual(os.stat(policy_path).st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(policy_path.read_text(encoding="utf-8")), self.policy())


if __name__ == "__main__":
    unittest.main()

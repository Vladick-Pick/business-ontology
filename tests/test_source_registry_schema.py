import json
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class SourceRegistrySchemaTests(unittest.TestCase):
    def test_source_instance_schema_locks_live_proof_states(self):
        schema = json.loads((REPO_ROOT / "schemas" / "source-instance.schema.json").read_text(encoding="utf-8"))
        item = schema["properties"]["source_instances"]["items"]

        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema.get("additionalProperties", True))
        self.assertFalse(item.get("additionalProperties", True))
        self.assertIn("telegram-mtproto-history", item["properties"]["kind"]["enum"])
        self.assertIn("meeting-recorder", item["properties"]["kind"]["enum"])
        self.assertIn("google-workspace", item["properties"]["kind"]["enum"])
        self.assertEqual(
            set(item["properties"]["status"]["enum"]),
            {"configured", "source-connected", "live-proven", "failed", "scheduled"},
        )

    def test_live_proof_schema_locks_status_and_hash_contract(self):
        schema = json.loads((REPO_ROOT / "schemas" / "live-proof.schema.json").read_text(encoding="utf-8"))
        item = schema["properties"]["live_proofs"]["items"]

        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema.get("additionalProperties", True))
        self.assertFalse(item.get("additionalProperties", True))
        self.assertEqual(
            set(item["properties"]["status"]["enum"]),
            {"passed", "failed", "source-connected", "setup-only"},
        )
        self.assertEqual(item["properties"]["evidence_hash"]["pattern"], "^sha256:[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()

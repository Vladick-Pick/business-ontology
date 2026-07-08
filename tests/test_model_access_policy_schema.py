import json
from pathlib import Path
import unittest

try:
    from jsonschema import ValidationError, validate as jsonschema_validate
except ModuleNotFoundError:
    class ValidationError(ValueError):
        pass

    jsonschema_validate = None


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((REPO_ROOT / "schemas" / "model-access-policy.schema.json").read_text(encoding="utf-8"))


def validate(payload, schema):
    if jsonschema_validate is not None:
        return jsonschema_validate(payload, schema)
    required = set(schema["required"])
    if set(payload) != required:
        raise ValidationError("policy fields do not match schema")
    for field in ["agent_id", "accepted_branch", "staged_branch_pattern", "generated_at"]:
        if not isinstance(payload.get(field), str) or not payload[field]:
            raise ValidationError(f"{field} must be a non-empty string")
    modes = payload.get("access_modes")
    if not isinstance(modes, list) or len(modes) != len(set(modes)):
        raise ValidationError("access_modes must be a unique array")
    allowed = {"read-model", "write-staged", "open-review"}
    if set(modes) != allowed:
        raise ValidationError("access_modes must be the installed-agent safe set")
    if payload.get("production_model_repo") is not False:
        raise ValidationError("production_model_repo must be false")
    return None


class ModelAccessPolicySchemaTests(unittest.TestCase):
    def test_safe_installed_agent_policy_validates(self):
        validate(
            {
                "agent_id": "business-ontology-resident",
                "access_modes": ["read-model", "write-staged", "open-review"],
                "accepted_branch": "main",
                "staged_branch_pattern": "staged/*",
                "production_model_repo": False,
                "generated_at": "2026-07-08T10:00:00Z",
            },
            SCHEMA,
        )

    def test_write_accepted_is_not_valid_installed_agent_policy(self):
        with self.assertRaises(ValidationError):
            validate(
                {
                    "agent_id": "business-ontology-resident",
                    "access_modes": ["read-model", "write-staged", "open-review", "write-accepted"],
                    "accepted_branch": "main",
                    "staged_branch_pattern": "staged/*",
                    "production_model_repo": False,
                    "generated_at": "2026-07-08T10:00:00Z",
                },
                SCHEMA,
            )

    def test_production_model_repo_policy_is_not_valid_for_probe(self):
        with self.assertRaises(ValidationError):
            validate(
                {
                    "agent_id": "business-ontology-resident",
                    "access_modes": ["read-model", "write-staged", "open-review"],
                    "accepted_branch": "main",
                    "staged_branch_pattern": "staged/*",
                    "production_model_repo": True,
                    "generated_at": "2026-07-08T10:00:00Z",
                },
                SCHEMA,
            )


if __name__ == "__main__":
    unittest.main()

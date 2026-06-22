import json
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class SchemaAndParserDocsTests(unittest.TestCase):
    def test_json_schemas_exist_and_are_strict_objects(self):
        schema_dir = REPO_ROOT / "schemas"
        expected = {
            "card.schema.json",
            "model-pack.schema.json",
            "source-map-entry.schema.json",
            "staged-proposal.schema.json",
            "trace-event.schema.json",
            "tool-result.schema.json",
        }

        missing = [name for name in expected if not (schema_dir / name).is_file()]
        self.assertEqual(missing, [])

        for name in expected:
            schema = json.loads((schema_dir / name).read_text(encoding="utf-8"))
            self.assertEqual(schema["type"], "object", name)
            self.assertFalse(schema.get("additionalProperties", True), name)
            self.assertIsInstance(schema.get("required"), list, name)

    def test_parser_subset_doc_names_supported_and_unsupported_yaml(self):
        doc = REPO_ROOT / "references" / "parser-subset.md"

        text = doc.read_text(encoding="utf-8")

        self.assertIn("Supported frontmatter subset", text)
        self.assertIn("Unsupported YAML features", text)
        self.assertIn("inline lists", text)
        self.assertIn("escaped pipes", text)
        self.assertIn("source-map table", text)


if __name__ == "__main__":
    unittest.main()

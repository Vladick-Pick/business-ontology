import tempfile
import unittest
from pathlib import Path

import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import chat_register_lint as lint  # noqa: E402


class ChatRegisterTests(unittest.TestCase):
    def test_repo_chat_blocks_have_no_technical_markers(self):
        violations = lint.find_violations(REPO_ROOT)
        self.assertEqual(
            violations,
            [],
            "chat blocks must not leak ids/codes/field names:\n"
            + "\n".join(f"{v['file']}:{v['line']}: {v['kind']} -> {v['text']}" for v in violations),
        )

    def test_linter_catches_a_planted_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "leak.md"
            sample.write_text(
                "intro\n\n```text chat\n"
                "Preparing mcpkg-handoff-001 for your decision.\n"
                "```\n",
                encoding="utf-8",
            )
            violations = lint.find_violations(Path(tmp))
        self.assertTrue(violations)
        self.assertEqual(violations[0]["kind"], "machine id")

    def test_linter_scans_markdown_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "workspace.md.tpl"
            sample.write_text(
                "intro\n\n```text chat\n"
                "Preparing mcpkg-template-001 for your decision.\n"
                "```\n",
                encoding="utf-8",
            )
            violations = lint.find_violations(Path(tmp))
        self.assertTrue(violations)
        self.assertEqual(violations[0]["file"], str(sample))

    def test_untagged_block_is_not_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "ok.md"
            sample.write_text(
                "intro\n\n```text\n"
                "This artifact example mentions mcpkg-001 and claimKind on purpose.\n"
                "```\n",
                encoding="utf-8",
            )
            violations = lint.find_violations(Path(tmp))
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_SPEC = REPO_ROOT / "specs/BUSINESS-ONTOLOGY-RESIDENT.md"
AGENT_PACKAGE = REPO_ROOT / "agent-package.yaml"
AGENT_SKILLS = REPO_ROOT / "skills"


def duty_table_skill_names():
    text = AGENT_SPEC.read_text(encoding="utf-8")
    match = re.search(
        r"\| Trigger \| Skill \| Output \|\n\|---\|---\|---\|\n(.*?)(?:\n\n|$)",
        text,
        re.DOTALL,
    )
    if not match:
        raise AssertionError("specs/BUSINESS-ONTOLOGY-RESIDENT.md duty table was not found")

    names = set()
    for line in match.group(1).splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        skill_cell = cells[1]
        names.update(re.findall(r"`([^`]+)`", skill_cell))
    return names


def package_duty_skill_names():
    text = AGENT_PACKAGE.read_text(encoding="utf-8")
    return set(re.findall(r"path: skills/([^/\n]+)/SKILL\.md", text))


def skill_frontmatter(path):
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    data = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


class AgentSkillRegistryTests(unittest.TestCase):
    def test_meeting_transcript_duties_are_registered_in_manifest_and_spec(self):
        required = {"meeting-recorder", "meeting-transcript-ingest"}

        self.assertTrue(required <= package_duty_skill_names())
        self.assertTrue(required <= duty_table_skill_names())

    def test_agent_spec_duties_reference_existing_agent_skills(self):
        missing = []
        for name in sorted(duty_table_skill_names()):
            if not (AGENT_SKILLS / name / "SKILL.md").is_file():
                missing.append(name)

        self.assertEqual(missing, [])

    def test_agent_skill_frontmatter_matches_folder_and_has_eval_cases(self):
        failures = []
        for skill_file in sorted(AGENT_SKILLS.glob("*/SKILL.md")):
            folder_name = skill_file.parent.name
            frontmatter = skill_frontmatter(skill_file)
            text = skill_file.read_text(encoding="utf-8")

            if frontmatter.get("name") != folder_name:
                failures.append(f"{skill_file}: name does not match folder")
            if not frontmatter.get("description"):
                failures.append(f"{skill_file}: missing description")
            if "## Eval cases" not in text:
                failures.append(f"{skill_file}: missing ## Eval cases")

        self.assertEqual(failures, [])

    def test_human_request_rules_cover_owner_ask_entrypoints(self):
        checks = {
            AGENT_SKILLS / "package-update" / "SKILL.md": ["kind=migration", "kind=setup"],
            AGENT_SKILLS / "connect-source" / "SKILL.md": ["kind=source-access", "kind=live-proof"],
            AGENT_SKILLS / "interaction-contract" / "SKILL.md": ["kind=setup"],
            AGENT_SKILLS / "onboard-contour" / "SKILL.md": ["kind=setup"],
            REPO_ROOT / "agent-os" / "COMMUNICATION_POLICY.md": [
                "kind=setup",
                "kind=live-proof",
                "kind=migration",
                "kind=source-access",
            ],
        }
        failures = []
        for path, needles in checks.items():
            text = path.read_text(encoding="utf-8")
            if "human_request" not in text:
                failures.append(f"{path}: missing human_request rule")
            for needle in needles:
                if needle not in text:
                    failures.append(f"{path}: missing {needle}")

        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()

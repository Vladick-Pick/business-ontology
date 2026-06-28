from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_SPEC = REPO_ROOT / "specs/BUSINESS-ONTOLOGY-RESIDENT.md"
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


if __name__ == "__main__":
    unittest.main()

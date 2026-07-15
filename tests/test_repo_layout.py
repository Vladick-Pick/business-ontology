from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class RepoLayoutTests(unittest.TestCase):
    def test_final_agent_package_layout_exists(self):
        required_paths = [
            "BOOTSTRAP.md",
            "agent-package.yaml",
            "AGENTS.md",
            "CLAUDE.md",
            "SKILL.md",
            "specs/BUSINESS-ONTOLOGY-RESIDENT.md",
            "specs/WORKSPACE-SPEC.md",
            "specs/UPDATE-SPEC.md",
            "specs/SOURCE-SPEC.md",
            "specs/REVIEW-SPEC.md",
            "specs/SYSTEM-ANALYSIS-SPEC.md",
            "agent-os/README.md",
            "agent-os/IDENTITY.md",
            "agent-os/OPERATING_LOOP.md",
            "agent-os/MODEL_STORAGE.md",
            "agent-os/DEFINITIONS_AND_ATTRIBUTES.md",
            "agent-os/PROCESSES_AND_WORKFLOWS.md",
            "agent-os/SOURCE_INTAKE.md",
            "agent-os/MODEL_CHANGE_PROTOCOL.md",
            "agent-os/REVIEW_PROTOCOL.md",
            "agent-os/COMMUNICATION_POLICY.md",
            "agent-os/SECURITY.md",
            "agent-os/UPDATE_POLICY.md",
            "agent-os/SYSTEM_ANALYSIS.md",
            "skills/README.md",
            "skills/business-ontology/SKILL.md",
            "skills/connect-source/SKILL.md",
            "skills/mine-materials/SKILL.md",
            "skills/propose-change/SKILL.md",
            "skills/promote-digest/SKILL.md",
            "skills/drift-sweep/SKILL.md",
            "skills/synthesize-digest/SKILL.md",
            "skills/decide-like-module/SKILL.md",
            "skills/system-analysis/SKILL.md",
            "adapters/openclaw/BOOTSTRAP.md",
            "adapters/openclaw/FIRST_MESSAGE.md",
            "adapters/openclaw/WORKSPACE.md",
            "adapters/openclaw/source-setup/telegram.md",
            "adapters/openclaw/source-setup/fireflies.md",
            "adapters/openclaw/source-setup/gog-google-workspace.md",
            "adapters/codex/BOOTSTRAP.md",
            "adapters/codex/AGENTS.template.md",
            "adapters/claude-code/BOOTSTRAP.md",
            "adapters/claude-code/CLAUDE.template.md",
            "templates/workspace/AGENTS.md.tpl",
            "templates/workspace/skills/business-ontology-resident/SKILL.md.tpl",
            "templates/workspace/CLAUDE.md.tpl",
            "templates/workspace/MODEL_STORAGE.md.tpl",
            "templates/workspace/PROCESS_WORKFLOWS.md.tpl",
            "templates/model-repo/README.md.tpl",
            "templates/model-repo/00-source-map.md.tpl",
            "templates/model-repo/PACKAGE_CONTRACT.lock.tpl",
            "templates/model-repo/scripts/validate_model_repo.py.tpl",
            "schemas/workspace-manifest.schema.json",
            "schemas/model-health.schema.json",
            "schemas/installed-agent-e2e-report.schema.json",
            "schemas/system-analysis-projection.schema.json",
            "schemas/system-analysis-result.schema.json",
            "scripts/publish_viewer.py",
            "scripts/serve_viewer.py",
            "scripts/viewer_privacy.py",
            "scripts/configure_viewer_publication.py",
            "scripts/migrate_workspace_v0_11_12.py",
            "scripts/install_openclaw_resident_bridge.py",
            "viewer/index.html",
            "viewer/README.md",
            "deployment/INSTALL.md",
            "deployment/UPDATE.md",
            "deployment/RELEASE_CHECKLIST.md",
            "deployment/MIGRATION_POLICY.md",
        ]
        missing = [path for path in required_paths if not (REPO_ROOT / path).exists()]
        self.assertEqual(missing, [])

    def test_root_skill_is_package_router_not_business_ontology_skill(self):
        root_skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        business_skill = (REPO_ROOT / "skills" / "business-ontology" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("skills/business-ontology/SKILL.md", root_skill)
        self.assertIn("agent-package", root_skill)
        self.assertIn("name: business-ontology", business_skill)
        self.assertIn("capture loop", business_skill)

    def test_no_published_agent_skills_directory_remains(self):
        self.assertFalse((REPO_ROOT / "agent-skills").exists())

    def test_registry_tooling_does_not_call_markdown_operational_truth(self):
        paths = [
            REPO_ROOT / "skills" / "build-brain" / "SKILL.md",
            REPO_ROOT / "scripts" / "build_registry.py",
            REPO_ROOT / "scripts" / "links_validate.py",
        ]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("Cards are the source of truth", text, str(path))
            self.assertNotIn("markdown cards are the source of truth", text.lower(), str(path))
            self.assertIn("Markdown/Git export", text, str(path))


if __name__ == "__main__":
    unittest.main()

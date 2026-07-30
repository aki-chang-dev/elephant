import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "validate-compatibility.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("compatibility_validator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CompatibilityValidatorTests(unittest.TestCase):
    def test_readme_and_smoke_cases_cover_both_hosts(self):
        readme = (ROOT / "README.md").read_text()
        smoke = (ROOT / "docs/testing/dual-runtime-smoke-tests.md").read_text()

        for phrase in (
            "## Claude Code",
            "## Codex",
            ".agents/elephant/delivery-profile.md",
            "Superpowers",
            "manual",
            "claude-design",
            "new session",
        ):
            self.assertIn(phrase, readme)

        for case in (
            "kickoff preflight",
            "neutral profile output",
            "instruction conflict",
            "missing profile",
            "non-UI bypass",
            "manual design resume",
            "claude-design handoff",
            "sequential research fallback",
        ):
            self.assertIn(case, smoke)

    def test_orchestration_uses_runtime_neutral_capabilities(self):
        skills_root = ROOT / "plugins/elephant/skills"
        kickoff = (skills_root / "kickoff/SKILL.md").read_text()
        ship_story = (skills_root / "ship-story/SKILL.md").read_text()
        slice_template = (skills_root / "ship-story/slice-template.md").read_text()
        shared = "\n".join(
            path.read_text() for path in sorted(skills_root.glob("*/SKILL.md"))
        )

        self.assertIn("preflight", kickoff.lower())
        self.assertIn("preflight", ship_story.lower())
        self.assertIn("sequential", ship_story.lower())
        self.assertIn("design-handoff.md", ship_story)
        self.assertIn("manual", ship_story)
        self.assertIn("claude-design", ship_story)
        for phrase in (
            ".claude/delivery-profile.md",
            "via the Skill tool",
            "`Explore`",
            "claudemd_refresh_targets",
        ):
            self.assertNotIn(phrase, shared)
        self.assertNotIn("Claude Code / `ship-story`", slice_template)

    def test_runtime_reference_and_neutral_profile_contract(self):
        init_profile = (
            ROOT / "plugins/elephant/skills/init-profile/SKILL.md"
        ).read_text()
        ship_story = (
            ROOT / "plugins/elephant/skills/ship-story/SKILL.md"
        ).read_text()
        schema = (
            ROOT
            / "plugins/elephant/skills/ship-story/delivery-profile-schema.md"
        ).read_text()
        runtime = (
            ROOT / "plugins/elephant/references/runtime-compatibility.md"
        ).read_text()

        shared_workflow = init_profile + ship_story + schema
        self.assertIn(".agents/elephant/delivery-profile.md", init_profile)
        self.assertIn(".agents/elephant/delivery-profile.md", ship_story)
        self.assertNotIn(".claude/delivery-profile.md", shared_workflow)
        self.assertIn("instruction_refresh_targets", schema)
        self.assertIn("provider", schema)
        self.assertIn("handoff_file", schema)

        for phrase in (
            "canonical skill",
            "sequential",
            "AGENTS.md",
            "CLAUDE.md",
            "manual",
            "claude-design",
        ):
            self.assertIn(phrase, runtime)

    def test_dual_manifests_and_codex_marketplace_match(self):
        codex_manifest = json.loads(
            (ROOT / "plugins/elephant/.codex-plugin/plugin.json").read_text()
        )
        claude_manifest = json.loads(
            (ROOT / "plugins/elephant/.claude-plugin/plugin.json").read_text()
        )
        self.assertEqual("elephant", codex_manifest["name"])
        self.assertEqual(claude_manifest["name"], codex_manifest["name"])
        self.assertEqual(claude_manifest["version"], codex_manifest["version"])
        self.assertEqual("./skills/", codex_manifest["skills"])

        marketplace = json.loads(
            (ROOT / ".agents/plugins/marketplace.json").read_text()
        )
        entry = next(item for item in marketplace["plugins"] if item["name"] == "elephant")
        self.assertEqual(
            {
                "name": "elephant",
                "source": {"source": "local", "path": "./plugins/elephant"},
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Productivity",
            },
            entry,
        )

    def test_current_repository_passes(self):
        validator = load_validator()
        self.assertEqual([], validator.validate_repository(ROOT))

    def test_missing_codex_manifest_is_reported(self):
        validator = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "plugins/elephant/skills/demo/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: demo\ndescription: Use when testing.\n---\n",
                encoding="utf-8",
            )
            errors = validator.validate_repository(root)
            self.assertIn("missing Codex plugin manifest", errors)

    def test_forbidden_core_coupling_is_reported(self):
        validator = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "plugins/elephant/skills/demo/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: demo\ndescription: Use when testing.\n---\n"
                "Dispatch via the Skill tool.\n",
                encoding="utf-8",
            )
            errors = validator.validate_repository(root)
            self.assertTrue(
                any("Claude-only core phrase" in error for error in errors),
                errors,
            )


if __name__ == "__main__":
    unittest.main()

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
    def test_product_first_skill_assets_exist(self):
        root = ROOT / "plugins/elephant/skills"
        required = (
            "shape-story/SKILL.md",
            "shape-story/product-contract-template.md",
            "shape-story/reviewers/product-ux-critic.md",
            "shape-story/reviewers/copy-critic.md",
            "author-technical-contract/SKILL.md",
            "author-technical-contract/technical-contract-template.md",
            "author-technical-contract/reviewers/architecture.md",
            "author-technical-contract/reviewers/domain-data.md",
            "author-technical-contract/reviewers/security-operations.md",
            "author-technical-contract/reviewers/product-conformance.md",
            "author-technical-contract/reviewers/test.md",
            "author-technical-contract/reviewers/technical-adjudicator.md",
        )
        for relative in required:
            self.assertTrue((root / relative).is_file(), relative)

    def test_shape_story_contract(self):
        skills = ROOT / "plugins/elephant/skills"
        product_template = (
            skills / "shape-story/product-contract-template.md"
        ).read_text()
        shape_story = (skills / "shape-story/SKILL.md").read_text()

        for phrase in (
            "schema: elephant.story/v2",
            "kind: product",
            "status: shaping",
            "## 1. User and context",
            "## 2. Problem and current experience",
            "## 3. Desired outcome",
            "## 4. Experience flow",
            "## 5. States and edge cases",
            "## 6. Information and copy",
            "## 7. Product rules and defaults",
            "## 8. Product acceptance criteria",
            "## 9. Out of scope",
            "## 10. Open product questions",
        ):
            self.assertIn(phrase, product_template)

        for phrase in (
            "approved | split | deferred | rejected",
            "main conversation",
            "one question at a time",
            "user, context, and current experience",
            "entry point, primary flow, branches, exit, and recovery",
            "loading, empty, error, disabled, and partial-success states",
            "labels, hints, placeholders, confirmations, feedback, and error copy",
            "Before the Product Contract Recap",
            "reviewers/product-ux-critic.md",
            "reviewers/copy-critic.md",
            "Do not ask the owner to reread the written file",
        ):
            self.assertIn(phrase, shape_story)

    def test_technical_contract(self):
        template = (
            ROOT
            / "plugins/elephant/skills/author-technical-contract"
            / "technical-contract-template.md"
        ).read_text()

        for phrase in (
            "schema: elephant.story/v2",
            "story: <ID>",
            "slug: <slug>",
            "kind: technical",
            "story_kind: <product-facing | engineering-only>",
            "status: draft",
            "product_contract: <path | null>",
            "## 1. Product-contract binding",
            "## 2. Current-system context",
            "## 3. Technical scope",
            "## 4. Domain and data contracts",
            "## 5. Interfaces and data flow",
            "## 6. Product-state implementation",
            "## 7. Security, privacy, and operational behavior",
            "## 8. Compatibility and migration",
            "## 9. Verification strategy",
            "## 10. Risks and open technical questions",
            "## 11. Review evidence",
            "Product contract item",
            "Technical response",
            "Verification",
            "ready | needs-product-decision",
        ):
            self.assertIn(phrase, template)

    def test_v2_contract_vocabulary_is_wired(self):
        skills = ROOT / "plugins/elephant/skills"
        ship = (skills / "ship-story/SKILL.md").read_text()
        profile = (skills / "ship-story/delivery-profile-schema.md").read_text()
        init = (skills / "init-profile/SKILL.md").read_text()

        for phrase in (
            "mode: dual",
            "elephant:shape-story",
            "elephant:author-technical-contract",
            "superpowers:writing-plans",
            "elephant.story/v2",
            "legacy-mixed",
            "needs-product-decision",
            "shaping | approved | split | deferred | rejected",
            "draft | review | ready | needs-product-decision",
        ):
            self.assertIn(phrase, ship)

        for phrase in (
            "story_contracts",
            "mode: dual",
            "product_template",
            "technical_template",
            "shape-story/product-contract-template.md",
            "author-technical-contract/technical-contract-template.md",
            "legacy-mixed",
        ):
            self.assertIn(phrase, profile)

        for phrase in (
            "mode: dual",
            "legacy-mixed",
            "proposed",
            "never auto-rewrite",
        ):
            self.assertIn(phrase, init)

    def test_dual_and_legacy_resume_contract(self):
        ship = (
            ROOT / "plugins/elephant/skills/ship-story/SKILL.md"
        ).read_text()
        runtime = (
            ROOT / "plugins/elephant/references/runtime-compatibility.md"
        ).read_text()

        self.assertIn("## Dual-contract v2 phase detection", ship)
        self.assertIn("## Legacy-mixed phase detection", ship)
        v2_start = ship.index("## Dual-contract v2 phase detection")
        legacy_start = ship.index("## Legacy-mixed phase detection")
        self.assertLess(v2_start, legacy_start)

        dual_section = ship[v2_start:legacy_start]
        for phrase in (
            "<ID>-<slug>-product.md",
            "<ID>-<slug>-technical.md",
            "supersedes",
            "approved",
            "split",
            "deferred",
            "rejected",
            "design_sensitivity",
            "needs-product-decision",
        ):
            self.assertIn(phrase, dual_section)
        self.assertNotIn("superpowers:brainstorming", dual_section)

        legacy_section = ship[legacy_start:]
        self.assertIn("superpowers:brainstorming", legacy_section)
        self.assertIn("slice-template.md", legacy_section)

        for phrase in (
            "canonical Elephant reviewer prompts",
            "optional adapters",
            "sequential",
        ):
            self.assertIn(phrase, runtime)

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

    def test_missing_v2_asset_is_reported(self):
        validator = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            errors = validator.validate_repository(Path(directory))
            self.assertIn(
                "missing required v2 asset: "
                "plugins/elephant/skills/shape-story/SKILL.md",
                errors,
            )

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

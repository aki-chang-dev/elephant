from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "elephant"
VALIDATOR = ROOT / "scripts" / "validate-compatibility.py"
EXPECTED_RUNTIME_EXPORTS = frozenset(
    {
        "WORKSPACE_SCHEMA",
        "PlanningScope",
        "ProductRoute",
        "WorkspaceMapError",
        "planning_scope",
        "resolve_product",
        "validate_workspace_map",
    }
)
EXPECTED_DESCRIPTION = (
    "A product-first coordination workflow for one owner and agents across "
    "Linear planning, Notion knowledge, and GitHub delivery."
)
EXPECTED_VERSION = "0.5.1"
EXPECTED_KEYWORDS = {
    "superpowers",
    "workflow",
    "roadmap",
    "delivery",
    "product-first",
    "linear",
    "notion",
    "github",
}
EXPECTED_SKILLS = {
    "author-product-spec",
    "author-technical-contract",
    "decompose-roadmap",
    "kickoff",
    "setup-workspace",
    "shape-story",
    "ship-story",
}

if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))


def load_validator():
    spec = importlib.util.spec_from_file_location("elephant_compatibility", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompatibilityValidatorTests(unittest.TestCase):
    def test_current_repository_passes(self) -> None:
        self.assertEqual(load_validator().validate_repository(ROOT), [])

    def test_dual_manifests_and_marketplaces_match(self) -> None:
        codex = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
        claude = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())
        codex_marketplace = json.loads(
            (ROOT / ".agents/plugins/marketplace.json").read_text()
        )
        claude_marketplace = json.loads(
            (ROOT / ".claude-plugin/marketplace.json").read_text()
        )
        self.assertEqual(codex["name"], claude["name"])
        self.assertEqual(codex["version"], claude["version"])
        self.assertEqual(codex_marketplace["plugins"][0]["name"], codex["name"])
        self.assertEqual(claude_marketplace["plugins"][0]["name"], codex["name"])

    def test_plugin_metadata_describes_native_coordination(self) -> None:
        codex = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
        claude = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())
        claude_marketplace = json.loads(
            (ROOT / ".claude-plugin/marketplace.json").read_text()
        )

        self.assertEqual(codex["description"], EXPECTED_DESCRIPTION)
        self.assertEqual(claude["description"], EXPECTED_DESCRIPTION)
        self.assertEqual(codex["version"], EXPECTED_VERSION)
        self.assertEqual(claude["version"], EXPECTED_VERSION)
        self.assertEqual(set(codex["keywords"]), EXPECTED_KEYWORDS)
        self.assertEqual(set(claude["keywords"]), EXPECTED_KEYWORDS)
        self.assertEqual(codex["skills"], "./skills/")
        self.assertEqual(codex["interface"]["capabilities"], ["Interactive", "Write"])
        self.assertEqual(
            codex["interface"]["defaultPrompt"],
            [
                "Kick off this product with Elephant.",
                "Set up native Linear, Notion, and GitHub coordination for this repository.",
                "Shape and ship the next Linear Story with Elephant.",
            ],
        )
        marketplace_plugin = claude_marketplace["plugins"][0]
        self.assertEqual(marketplace_plugin["description"], EXPECTED_DESCRIPTION)
        self.assertEqual(set(marketplace_plugin["keywords"]), EXPECTED_KEYWORDS)

        forbidden = ("dual-contract", "delivery profile", "Product Contract")
        rendered = json.dumps(
            [codex, claude, claude_marketplace], ensure_ascii=False
        )
        for phrase in forbidden:
            self.assertNotIn(phrase, rendered)

    def test_installed_skill_inventory_is_exact(self) -> None:
        installed = {
            path.parent.name for path in (PLUGIN / "skills").glob("*/SKILL.md")
        }
        self.assertEqual(installed, EXPECTED_SKILLS)

    def test_minimal_runtime_exports_are_exact(self) -> None:
        from elephant_runtime import workspace_map
        import elephant_runtime

        self.assertEqual(frozenset(workspace_map.__all__), EXPECTED_RUNTIME_EXPORTS)
        self.assertEqual(elephant_runtime.__all__, ["workspace_map"])

    def test_installed_smoke_uses_only_workspace_map(self) -> None:
        from elephant_runtime.installed_smoke import run_installed_smoke

        self.assertEqual(
            run_installed_smoke(),
            {
                "single_product": {
                    "product": "sample",
                    "team_id": "linear-team",
                    "labels": {},
                },
                "multi_product": {
                    "product": "second",
                    "team_id": "linear-team",
                    "labels": {
                        "issue": "issue-label-second",
                        "project": "project-label-second",
                        "initiative": "initiative-label-second",
                    },
                },
            },
        )

    def test_validator_rejects_each_superseded_asset(self) -> None:
        validator = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in validator.FORBIDDEN_SUPERSEDED_ASSETS:
                with self.subTest(relative=relative):
                    target = root / relative
                    if relative.endswith("/"):
                        target.mkdir(parents=True)
                        (target / "fixture").write_text("fixture\n", encoding="utf-8")
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text("fixture\n", encoding="utf-8")
                    errors: list[str] = []
                    validator._validate_forbidden_assets(root, errors)
                    self.assertIn(
                        f"superseded asset remains: {relative.rstrip('/')}",
                        errors,
                    )
                    if target.is_dir():
                        (target / "fixture").unlink()
                        target.rmdir()
                    else:
                        target.unlink()

    def test_validator_requires_each_packaged_asset(self) -> None:
        validator = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in validator.REQUIRED_ASSETS:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("fixture\n", encoding="utf-8")
            for skill in validator.REQUIRED_SKILLS:
                target = root / "plugins/elephant/skills" / skill / "SKILL.md"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("fixture\n", encoding="utf-8")

            errors: list[str] = []
            validator._validate_required_assets(root, errors)
            self.assertEqual(errors, [])

            for relative in validator.REQUIRED_ASSETS:
                with self.subTest(relative=relative):
                    target = root / relative
                    target.unlink()
                    errors = []
                    validator._validate_required_assets(root, errors)
                    self.assertIn(f"missing required asset: {relative}", errors)
                    target.write_text("fixture\n", encoding="utf-8")

    def test_checkout_forwarder_resolves_packaged_workspace_map(self) -> None:
        from scripts import workspace_map as checkout
        from elephant_runtime import workspace_map as packaged

        self.assertEqual(checkout.WORKSPACE_SCHEMA, packaged.WORKSPACE_SCHEMA)
        self.assertIs(checkout.validate_workspace_map, packaged.validate_workspace_map)


if __name__ == "__main__":
    unittest.main()

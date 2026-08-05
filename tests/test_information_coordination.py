from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate-compatibility.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("elephant_compatibility", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeCoordinationPackagingTests(unittest.TestCase):
    def test_validator_requires_each_native_coordination_asset(self) -> None:
        expected = (
            "plugins/elephant/references/information-routing.md",
            "plugins/elephant/references/linear-planning.md",
            "plugins/elephant/references/notion-knowledge.md",
            "plugins/elephant/skills/setup-workspace/SKILL.md",
            "plugins/elephant/skills/shape-story/SKILL.md",
            "plugins/elephant/skills/author-technical-contract/SKILL.md",
            "plugins/elephant/skills/ship-story/SKILL.md",
            "plugins/elephant/skills/kickoff/SKILL.md",
            "plugins/elephant/skills/decompose-roadmap/SKILL.md",
            "plugins/elephant/skills/author-product-spec/SKILL.md",
        )
        forbidden = (
            "plugins/elephant/references/runtime-compatibility.md",
            "plugins/elephant/skills/author-product-spec/spec-system-template.md",
            "plugins/elephant/skills/decompose-roadmap/roadmap-template.md",
            "plugins/elephant/skills/init-profile/SKILL.md",
            "plugins/elephant/skills/ship-story/delivery-profile-schema.md",
            "plugins/elephant/skills/ship-story/slice-template.md",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in expected:
                asset = root / path
                asset.parent.mkdir(parents=True, exist_ok=True)
                asset.write_text("fixture\n", encoding="utf-8")
            validator = load_validator()
            errors: list[str] = []
            validator._validate_native_coordination_assets(root, errors)
            self.assertEqual(errors, [])

            for path in expected:
                with self.subTest(path=path):
                    asset = root / path
                    asset.unlink()
                    errors = []
                    validator._validate_native_coordination_assets(root, errors)
                    self.assertEqual(
                        errors,
                        [f"missing native coordination asset: {path}"],
                    )
                    asset.write_text("fixture\n", encoding="utf-8")

            baseline = validator.validate_repository(root)
            for path in expected:
                with self.subTest(public_validator_path=path):
                    asset = root / path
                    asset.unlink()
                    missing_error = f"missing native coordination asset: {path}"
                    self.assertNotIn(missing_error, baseline)
                    self.assertIn(missing_error, validator.validate_repository(root))
                    asset.write_text("fixture\n", encoding="utf-8")

            for path in forbidden:
                with self.subTest(forbidden_path=path):
                    asset = root / path
                    asset.parent.mkdir(parents=True, exist_ok=True)
                    asset.write_text("fixture\n", encoding="utf-8")
                    errors = []
                    validator._validate_native_coordination_assets(root, errors)
                    self.assertIn(
                        f"superseded native coordination asset remains: {path}",
                        errors,
                    )
                    asset.unlink()

    def test_workspace_map_is_the_executable_coordination_runtime(self) -> None:
        from scripts import workspace_map

        self.assertEqual(
            frozenset(workspace_map.__all__),
            frozenset(
                {
                    "WORKSPACE_SCHEMA",
                    "PlanningScope",
                    "ProductRoute",
                    "WorkspaceMapError",
                    "planning_scope",
                    "resolve_product",
                    "validate_workspace_map",
                }
            ),
        )


if __name__ == "__main__":
    unittest.main()

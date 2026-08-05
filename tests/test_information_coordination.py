from __future__ import annotations

import importlib.util
from pathlib import Path
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
    def test_active_skill_inventory_matches_native_workflow(self) -> None:
        self.assertEqual(
            load_validator().REQUIRED_SKILLS,
            (
                "author-product-spec",
                "author-technical-contract",
                "decompose-roadmap",
                "kickoff",
                "setup-workspace",
                "shape-story",
                "ship-story",
            ),
        )

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

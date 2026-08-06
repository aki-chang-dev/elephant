from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate-compatibility.py"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def markdown_subsection(text: str, heading: str) -> str:
    marker = f"### {heading}\n"
    _, found, remainder = text.partition(marker)
    if not found:
        raise ValueError(f"missing Markdown subsection: {heading}")
    subsection = re.split(r"\n(?=#{1,3} )", remainder, maxsplit=1)[0]
    return " ".join(subsection.split())


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

    def test_ship_story_selects_proportional_assurance(self) -> None:
        text = read("plugins/elephant/skills/ship-story/SKILL.md")
        self.assertIn("delivery-assurance.md", text)
        self.assertIn("Ordinary assurance", text)
        self.assertIn("Elevated assurance", text)
        self.assertIn("one independent", text)
        self.assertIn("exact Linear Issue identifier", text)
        for mandatory_gate in (
            "run `superpowers:writing-plans`",
            "`superpowers:subagent-driven-development` or `superpowers:executing-plans`",
            "Use `superpowers:finishing-a-development-branch`",
        ):
            self.assertNotIn(mandatory_gate, text)

    def test_delivery_assurance_is_risk_and_context_proportional(self) -> None:
        text = read("plugins/elephant/references/delivery-assurance.md")
        for requirement in (
            "Ordinary assurance",
            "Elevated assurance",
            "Uncertain risk",
            "role-scoped",
            "affected requirements",
            "hard token",
            "Parallel",
        ):
            self.assertIn(requirement, text)

    def test_final_delivery_review_supports_both_assurance_depths(self) -> None:
        text = read(
            "plugins/elephant/skills/ship-story/reviewers/implementation-conformance.md"
        )
        self.assertIn("Ordinary inputs", text)
        self.assertIn("Elevated inputs", text)
        self.assertIn("Implementation quality", text)
        self.assertIn("Load-bearing", text)
        self.assertIn("Affected rechecks", text)

    def test_technical_contract_reviewers_are_selected_only_for_named_risk(self) -> None:
        text = read("plugins/elephant/skills/author-technical-contract/SKILL.md")
        self.assertIn("delivery-assurance.md", text)
        self.assertIn("role-scoped", text)
        self.assertNotIn("Always select `test`", text)
        self.assertNotIn("Every product-facing Story", text)
        self.assertNotIn("the same relevant repository evidence", text)

    def test_specialists_receive_role_scoped_context(self) -> None:
        for reviewer in (
            "architecture",
            "domain-data",
            "security-operations",
            "test",
            "technical-adjudicator",
        ):
            with self.subTest(reviewer=reviewer):
                text = read(
                    "plugins/elephant/skills/author-technical-contract/"
                    f"reviewers/{reviewer}.md"
                )
                self.assertIn("role-scoped", text)
                self.assertNotIn("complete current fetched product-source bundle", text)

        product = read(
            "plugins/elephant/skills/author-technical-contract/"
            "reviewers/product-conformance.md"
        )
        self.assertIn("complete current fetched product-source bundle", product)

    def test_copy_critic_is_conditional(self) -> None:
        text = read("plugins/elephant/skills/shape-story/SKILL.md")
        self.assertIn("always run `reviewers/product-ux-critic.md`", text)
        self.assertIn("Run `reviewers/copy-critic.md` only", text)

    def test_routine_native_writes_use_no_git_recovery_note(self) -> None:
        for relative in (
            "plugins/elephant/skills/shape-story/SKILL.md",
            "plugins/elephant/skills/setup-workspace/SKILL.md",
        ):
            with self.subTest(relative=relative):
                text = read(relative)
                self.assertNotIn("pending-application.md", text)
                self.assertNotIn("operation branch", text)
                self.assertIn("approving conversation", text)
                self.assertIn("authoritative", text)

    def test_uncertain_native_writes_do_not_use_consistency_window_retries(self) -> None:
        for relative in (
            "plugins/elephant/references/linear-planning.md",
            "plugins/elephant/references/notion-knowledge.md",
        ):
            with self.subTest(relative=relative):
                text = read(relative)
                self.assertNotIn("normal consistency window", text)
                self.assertNotIn("two fresh", text)
                self.assertIn("pending", text)
                self.assertIn("later explicit resume run", text)
                self.assertNotIn("may be retried after", text)

        setup = read("plugins/elephant/skills/setup-workspace/SKILL.md")
        self.assertNotIn("Retry a definitively rejected operation", setup)
        self.assertIn("later explicit resume run", setup)

    def test_setup_classifies_execution_capability_before_approval(self) -> None:
        text = read("plugins/elephant/skills/setup-workspace/SKILL.md")
        for requirement in (
            "Elephant",
            "Owner setup",
            "Unavailable",
            "required structure",
            "enhancements",
            "before presenting the proposal",
        ):
            self.assertIn(requirement, text)

    def test_setup_allows_verified_owner_provisioning_without_a_ledger(self) -> None:
        setup = read("plugins/elephant/skills/setup-workspace/SKILL.md")
        planning = read("plugins/elephant/references/linear-planning.md")
        for requirement in (
            "one numbered checklist",
            "opaque IDs",
            "semantic read",
            "resume signal",
            "workspace.yaml",
        ):
            self.assertIn(requirement, setup)
        self.assertIn("setup-only", planning)
        self.assertIn("no manual runtime fallback", planning)
        self.assertNotIn(
            "If neither route can create a required Product label, stop before the first setup write",
            setup,
        )

    def test_owner_setup_checklist_keeps_approved_precision(self) -> None:
        for relative in (
            "plugins/elephant/skills/setup-workspace/SKILL.md",
            "docs/superpowers/plans/2026-08-06-capability-adaptive-workspace-setup.md",
        ):
            with self.subTest(relative=relative):
                text = " ".join(read(relative).split())
                self.assertIn(
                    "final human-visible name and applicable color, description, or relation",
                    text,
                )
                self.assertIn(
                    "The checklist contains no implementation explanation, connector "
                    "diagnostics, internal setup state, or request for the owner to copy "
                    "opaque IDs.",
                    text,
                )

    def test_multi_product_label_contract_remains_intact(self) -> None:
        planning = read("plugins/elephant/references/linear-planning.md")
        self.assertIn("Issue, Project, and Initiative", planning)
        self.assertIn("Create and verify all three label types", planning)

    def test_dual_runtime_smoke_covers_setup_capability_profiles(self) -> None:
        text = read("docs/testing/dual-runtime-smoke-tests.md")
        cli = markdown_subsection(text, "Codex CLI profile")
        browser = markdown_subsection(text, "Browser-capable profile")
        unverifiable = markdown_subsection(text, "Unverifiable profile")

        for requirement in (
            "semantic Linear/Notion connectors",
            "no browser",
            "required administrative create unavailable",
            "collection semantically readable",
            "**Owner setup**",
            "execute supported approved writes",
            "one exact checklist",
            "semantic read-back",
            "without requesting opaque IDs",
            "reuse",
            "stable-ID capture",
            "no duplicate",
            "config-last",
        ):
            with self.subTest(profile="Codex CLI", requirement=requirement):
                self.assertIn(requirement, cli)

        for requirement in (
            "authenticated browser",
            "connector gap",
            "same proposal",
            "same Product protocol",
            "same final workspace map",
            "only the executor differs",
        ):
            with self.subTest(profile="browser-capable", requirement=requirement):
                self.assertIn(requirement, browser)

        for requirement in (
            "both the write path and semantic read-back",
            "required Product-label namespace",
            "**Unavailable**",
            "before approval",
            "must not publish a workspace map",
        ):
            with self.subTest(profile="unverifiable", requirement=requirement):
                self.assertIn(requirement, unverifiable)

    def test_release_verification_invokes_installed_smoke_as_package(self) -> None:
        plan = read(
            "docs/superpowers/plans/2026-08-06-capability-adaptive-workspace-setup.md"
        )
        package_aware_command = (
            "PYTHONPATH=plugins/elephant python3 -c \\\n"
            "  'from elephant_runtime.installed_smoke import run_installed_smoke; "
            "print(run_installed_smoke())'"
        )
        self.assertEqual(plan.count(package_aware_command), 2)
        self.assertNotIn(
            "python3 plugins/elephant/elephant_runtime/installed_smoke.py", plan
        )


if __name__ == "__main__":
    unittest.main()

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
            "ship-story/reviewers/implementation-conformance.md",
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
            "draft → ready → implementing → done",
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
            "draft | ready | implementing | done | needs-product-decision",
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

    def test_dual_profile_values_are_injected(self):
        skills = ROOT / "plugins/elephant/skills"
        ship = (skills / "ship-story/SKILL.md").read_text()
        shape = (skills / "shape-story/SKILL.md").read_text()
        technical = (skills / "author-technical-contract/SKILL.md").read_text()
        init_profile = (skills / "init-profile/SKILL.md").read_text()
        normalized_ship = " ".join(ship.split())

        for phrase in (
            "story_contracts.product_template",
            "story_contracts.technical_template",
            "story_contracts.product_filename_rule",
            "story_contracts.technical_filename_rule",
            "render the configured",
            "only when the field is omitted",
            "rendered Product and Technical output paths must be distinct",
            "STOP before artifact mutation",
        ):
            self.assertIn(phrase, normalized_ship)
        self.assertIn("caller-supplied Product Contract template", shape)
        self.assertIn("caller-supplied Product Contract output path", shape)
        self.assertIn("caller-supplied Technical Contract template", technical)
        self.assertIn("caller-supplied Technical Contract output path", technical)
        self.assertIn(
            "`dual` → Product Contract `design_sensitivity` is `High` or `Medium`",
            init_profile,
        )
        self.assertIn(
            "`legacy-mixed` → mixed spec §6 sensitivity is not `Low`",
            init_profile,
        )

    def test_legacy_resume_uses_configured_status_flow(self):
        ship = (
            ROOT / "plugins/elephant/skills/ship-story/SKILL.md"
        ).read_text()
        normalized = " ".join(ship.split())

        for phrase in (
            "Render the preserved legacy `filename_rule`",
            "exactly one `[ID]` and exactly one `[slug]`",
            "four distinct values",
            "authoring-incomplete, ready, implementing, and done",
            "`Seed → Reviewed → Building → Complete`",
            "Resume legacy authoring from the existing mixed spec",
            "status is absent or not in `status_flow`",
            "write the third configured value",
            "writing the fourth configured value",
            "Resolve legacy `spec_template` only when selected legacy authoring will dispatch",
            "bundled `slice-template.md` relative to this `ship-story` skill directory",
            "every other legacy template path from the repository root",
            "do not fall back from an invalid configured legacy template",
        ):
            self.assertIn(phrase, normalized)

        legacy = ship[ship.index("## Legacy-mixed phase detection") :]
        self.assertNotIn("<spec_dir>/<ID>-*.md", legacy)
        self.assertNotIn("advances the mixed spec to `Implementing`", legacy)
        self.assertNotIn("advance the mixed spec to `Done`", legacy)

    def test_invalid_v2_stops_before_dispatch_and_terminal_precedes_pairing(self):
        ship = (
            ROOT / "plugins/elephant/skills/ship-story/SKILL.md"
        ).read_text()
        normalized = " ".join(ship.split())

        for heading in (
            "### V2 artifact validation",
            "### Terminal product dispositions",
            "### Product/technical pairing",
        ):
            self.assertIn(heading, ship)
        validation = ship.index("### V2 artifact validation")
        invariants = ship.index("### Status-dependent artifact invariants")
        terminal = ship.index("### Terminal product dispositions")
        pairing = ship.index("### Product/technical pairing")
        self.assertLess(validation, invariants)
        self.assertLess(invariants, terminal)
        self.assertLess(validation, terminal)
        self.assertLess(terminal, pairing)
        for phrase in (
            "v2-looking",
            "every Markdown artifact directly under `spec_dir`",
            "authoritative exact v2 discriminator",
            "invalid required field",
            "For technical artifacts, `story_kind` or `product_contract`",
            "STOP and list every invalid field",
            "Do not treat an invalid v2-looking artifact as legacy or missing",
        ):
            self.assertIn(phrase, normalized)

    def test_v2_discovery_scopes_catch_all_to_requested_story(self):
        ship = (
            ROOT / "plugins/elephant/skills/ship-story/SKILL.md"
        ).read_text()
        normalized = " ".join(ship.split())

        for phrase in (
            "configured-path candidate",
            "rendered for the requested ID",
            "Inspect it regardless of its frontmatter `story` value",
            "catch-all candidate",
            "frontmatter `story` exactly equals the requested ID",
            "ignore any valid v2 artifact for another story",
        ):
            self.assertIn(phrase, normalized)

    def test_needs_product_decision_has_persisted_return_transition(self):
        ship = (
            ROOT / "plugins/elephant/skills/ship-story/SKILL.md"
        ).read_text()
        shape = (
            ROOT / "plugins/elephant/skills/shape-story/SKILL.md"
        ).read_text()
        normalized = " ".join(ship.split())

        for phrase in (
            "active approved Product Contract supersedes",
            "technical author/fixer",
            "rebind `product_contract`",
            "set `story_kind: product-facing`",
            "set `status: draft`",
            "clear the resolved decision brief",
            "Persist these four field changes atomically",
            "do not present the same bounded question again",
            "implementation-stage decision return",
            "mark every earlier plan, execution, code-review, and conformance record as superseded history",
            "must not count as a current plan or execution-start evidence",
            "new plan bound to the latest Technical Contract revision",
            "transition the latest revision from `ready` to `implementing`",
        ):
            self.assertIn(phrase, normalized)
        for phrase in (
            "Engineering-only decision return",
            "product_contract: null",
            "reclassify the story as product-facing",
            "lowest unused integer starting at 2",
            "`ship-story` owns slug and output-path allocation",
            "passes the exact path",
        ):
            self.assertIn(phrase, normalized)
        self.assertIn(
            "Write exactly that caller-supplied path",
            " ".join(shape.split()),
        )
        self.assertNotIn(
            "Use the repository's normal Product Contract versioned-slug convention",
            shape,
        )

    def test_branch_aware_preflight_follows_selected_artifacts(self):
        ship = (
            ROOT / "plugins/elephant/skills/ship-story/SKILL.md"
        ).read_text()
        runtime = (
            ROOT / "plugins/elephant/references/runtime-compatibility.md"
        ).read_text()
        normalized_ship = " ".join(ship.split())
        normalized_runtime = " ".join(runtime.split())

        self.assertIn("## Step 0 — Load, locate, and select the branch", ship)
        self.assertIn("## Branch-aware dependency preflight", ship)
        detection = ship.index("## Step 0 — Load, locate, and select the branch")
        preflight = ship.index("## Branch-aware dependency preflight")
        self.assertLess(detection, preflight)
        for phrase in (
            "Artifact classification and phase selection happen before dependency checks",
            "Existing v2 artifacts take precedence under a legacy profile",
            "Existing legacy artifacts remain legacy under a dual profile",
            "Resumed legacy after authoring",
            "must not require `superpowers:brainstorming`",
            "only capabilities that the selected branch and remaining phases can dispatch",
        ):
            self.assertIn(phrase, normalized_ship)
        for phrase in (
            "Artifact/type selection",
            "before dependency preflight",
            "resumed legacy after authoring",
        ):
            self.assertIn(phrase, normalized_runtime)
        downstream = ship[ship.index("## Shared downstream detector and delivery") :]
        for phrase in (
            "In the selected dual-v2 branch",
            "In the selected legacy branch",
        ):
            self.assertIn(phrase, downstream)
        for forbidden in (
            "In dual mode",
            "In legacy mode",
            "Dual mode must",
            "Legacy mode must",
        ):
            self.assertNotIn(forbidden, downstream)

    def test_status_dependent_artifact_invariants_hard_stop(self):
        ship = (
            ROOT / "plugins/elephant/skills/ship-story/SKILL.md"
        ).read_text()
        normalized = " ".join(ship.split())

        for phrase in (
            "`design_sensitivity` is exactly `High`, `Medium`, or `Low`",
            "`approved` requires section 10 to contain no unresolved product questions",
            "`split`, `deferred`, and `rejected` require both disposition rationale and next condition",
            "`needs-product-decision` requires exactly one bounded decision brief",
            "`ready` requires no `TBD`, placeholder, open technical question, or blocking finding",
            "`ready` also requires one non-placeholder contract-basis revision marker",
            "every required affected-reviewer recheck",
            "`implementing` retains every `ready` invariant",
            "plan bound to that exact marker",
            "`done` retains every `ready` invariant",
            "STOP with the exact artifact path, field or section, and violated invariant",
        ):
            self.assertIn(phrase, normalized)

    def test_legacy_and_v2_classification_avoid_false_positives(self):
        ship = (
            ROOT / "plugins/elephant/skills/ship-story/SKILL.md"
        ).read_text()
        normalized = " ".join(ship.split())

        for phrase in (
            "authoritative exact v2 discriminator values",
            "`schema: elephant.story/v2`",
            "`kind: product` or `kind: technical`",
            "Render the preserved legacy `filename_rule`",
            "known configured legacy `status_flow` value",
            "legacy slug ends in `-product` or `-technical`",
            "generic `schema` or `kind` key",
            "genuine ambiguous collision",
            "STOP and list every candidate",
            "do not infer recency",
            "malformed current-story v2 artifact",
            "valid v2 artifact for another story",
        ):
            self.assertIn(phrase, normalized)
        self.assertNotIn(
            "contains any v2 discriminator field: `schema`, `kind`, `story_kind`, or "
            "`product_contract`",
            normalized,
        )

    def test_product_contract_reference_is_canonical_and_exact(self):
        skills = ROOT / "plugins/elephant/skills"
        ship = (skills / "ship-story/SKILL.md").read_text()
        schema = (skills / "ship-story/delivery-profile-schema.md").read_text()
        template = (
            skills
            / "author-technical-contract/technical-contract-template.md"
        ).read_text()
        shared = " ".join((ship + schema + template).split())

        for phrase in (
            "`product_contract`",
            "repository-relative POSIX path",
            "case-sensitive",
            "absolute paths",
            "backslashes",
            "`..` segments",
            "existing file",
            "exact active Product Contract",
        ):
            self.assertIn(phrase, shared)

    def test_custom_dual_templates_are_validated_before_authoring(self):
        ship = (
            ROOT / "plugins/elephant/skills/ship-story/SKILL.md"
        ).read_text()
        normalized = " ".join(ship.split())

        for phrase in (
            "Validate a selected custom template immediately before its authoring dispatch",
            "mandatory v2 frontmatter slots",
            "all ten Product Contract sections",
            "all eleven Technical Contract sections",
            "`supersedes` shape",
            "`product_contract` shape",
            "contract-basis marker",
            "superseded-history",
            "current-plan",
            "STOP and list every missing or incompatible slot",
        ):
            self.assertIn(phrase, normalized)

    def test_post_implementation_conformance_gates_integration(self):
        root = ROOT / "plugins/elephant/skills/ship-story"
        ship = (root / "SKILL.md").read_text()
        prompt_path = root / "reviewers/implementation-conformance.md"
        self.assertTrue(prompt_path.is_file(), prompt_path)
        prompt = prompt_path.read_text()

        self.assertIn("### Post-implementation conformance", ship)
        execute = ship.index("### Execute")
        conformance = ship.index("### Post-implementation conformance")
        finish = ship.index("### Finish")
        self.assertLess(execute, conformance)
        self.assertLess(conformance, finish)
        legacy = ship[
            ship.index("## Legacy-mixed phase detection") :
            ship.index("## Shared downstream detector and delivery")
        ]
        self.assertNotIn("conformance", legacy.lower())

        for phrase in (
            "For dual-v2 stories",
            "implementation evidence and diff",
            "both the Product Contract and Technical Contract",
            "behavior-preservation boundary",
            "implementation fixer",
            "affected reviewer",
            "recheck",
            "before integration",
            "no routine owner checkpoint",
            "observable-product ambiguity",
            "post-implementation conformance PASS for dual-v2 stories",
        ):
            self.assertIn(phrase, " ".join(ship.split()))
        for phrase in (
            "Read-only",
            "Verdict: PASS | FINDINGS | NEEDS_PRODUCT_DECISION",
            "Product conformance",
            "Technical conformance",
            "Behavior-preservation conformance",
            "Integration gate",
        ):
            self.assertIn(phrase, prompt)

    def test_technical_contract_lifecycle_is_persisted(self):
        skills = ROOT / "plugins/elephant/skills"
        ship = (skills / "ship-story/SKILL.md").read_text()
        author = (skills / "author-technical-contract/SKILL.md").read_text()
        template = (
            skills
            / "author-technical-contract/technical-contract-template.md"
        ).read_text()
        smoke = (ROOT / "docs/testing/product-first-story-smoke-tests.md").read_text()
        shared = ship + author + template + smoke
        normalized_shared = " ".join(shared.split())

        for phrase in (
            "draft → ready → implementing → done",
            "review is an activity while `status: draft` remains persisted",
            "change `ready` to `implementing` before implementation",
            "change `implementing` to `done` during closeout",
            "capture one non-placeholder contract-basis revision marker",
        ):
            self.assertIn(phrase, normalized_shared)
        for forbidden in (
            "status: review",
            "draft | review | ready",
            "`draft` or `review`",
            "set `status: review`",
        ):
            self.assertNotIn(forbidden, shared)

    def test_supersedes_has_canonical_exact_match_contract(self):
        skills = ROOT / "plugins/elephant/skills"
        ship = (skills / "ship-story/SKILL.md").read_text()
        schema = (
            skills / "ship-story/delivery-profile-schema.md"
        ).read_text()
        product_template = (
            skills / "shape-story/product-contract-template.md"
        ).read_text()
        shared = ship + schema

        self.assertIn("supersedes: []", product_template)
        for phrase in (
            "`null` normalizes to an empty list",
            "scalar string normalizes to a one-item list",
            "list of strings",
            "repository-relative POSIX",
            "case-sensitive",
            "absolute paths",
            "`..` segments",
            "every colliding legacy path",
        ):
            self.assertIn(phrase, shared)

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

    def test_product_first_documentation(self):
        readme = (ROOT / "README.md").read_text()
        smoke_path = ROOT / "docs/testing/product-first-story-smoke-tests.md"
        self.assertTrue(smoke_path.is_file(), smoke_path)
        smoke = smoke_path.read_text().lower()

        for phrase in (
            "shape-story",
            "author-technical-contract",
            "dual-contract",
            "legacy-mixed",
            "Product Contract Recap",
            "technical and code review is agent-owned",
        ):
            self.assertIn(phrase, readme)

        for case in (
            "product-facing triage",
            "engineering-only bypass",
            "approved, split, deferred, and rejected",
            "interrupted shaping resume",
            "existing design-gate compatibility",
            "technical author plus reviewer/fix/re-review",
            "needs-product-decision escalation",
            "sequential fallback without workers",
            "legacy mixed-spec resume",
            "branch-aware dependency preflight",
            "invalid status invariants",
            "legacy suffix and generic metadata classification",
            "custom legacy filename and lifecycle",
            "post-build conformance before integration",
            "exact technical lifecycle",
            "v2/legacy collision without `supersedes`",
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
        self.assertEqual("0.3.0", codex_manifest["version"])
        self.assertEqual("./skills/", codex_manifest["skills"])
        self.assertIn("product-first", codex_manifest["keywords"])
        self.assertIn("dual-contract", codex_manifest["keywords"])

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


class WorkspaceCorePackagingTests(unittest.TestCase):
    ASSETS = (
        "workspace/workspace-schema.md",
        "workspace/profile-schema.md",
        "workspace/provider-contracts.md",
        "workspace/story-state-model.md",
    )

    def test_workspace_core_assets_are_packaged(self):
        root = ROOT / "plugins/elephant/references"
        for relative in self.ASSETS:
            self.assertTrue((root / relative).is_file(), relative)

    def test_missing_workspace_core_asset_is_reported(self):
        validator = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            references = root / "plugins/elephant/references"
            for relative in self.ASSETS[:-1]:
                path = references / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")
            errors = validator.validate_repository(root)
            self.assertIn(
                "missing v3 workspace core asset: "
                "plugins/elephant/references/workspace/story-state-model.md",
                errors,
            )


if __name__ == "__main__":
    unittest.main()

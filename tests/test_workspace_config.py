from copy import deepcopy
import unittest

from scripts.workspace_core import WorkspaceRouteError, resolve_profile, validate_profile, validate_workspace


VALID_WORKSPACE = {
    "schema": "elephant.workspace/v3",
    "repository": {"id": "repo-maio"},
    "providers": {
        "story_store": "linear",
        "product_knowledge_store": "notion",
        "product_contract_store": "notion",
        "delivery_workspace": "git",
    },
    "bindings": {
        "linear": {"workspace_id": "lin-ws", "team_id": "lin-team"},
        "notion": {
            "workspace_id": "notion-ws",
            "products_database_id": "db-products",
            "knowledge_database_id": "db-knowledge",
            "contracts_database_id": "db-contracts",
        },
    },
    "products": {
        "clickfalcon": {
            "profile": ".agents/elephant/profiles/clickfalcon.yaml",
            "story_ref": "linear-label-clickfalcon",
            "knowledge_ref": "notion-product-clickfalcon",
            "primary_domains": ["clickfalcon"],
        }
    },
    "domains": {
        "clickfalcon": {
            "scopes": ["apps/tracker-web", "apps/tracker-engine"],
            "instruction_paths": ["AGENTS.md"],
            "verification": ["bun run type-check"],
            "products": ["clickfalcon"],
        }
    },
    "engineering_profile": ".agents/elephant/profiles/engineering.yaml",
}


class WorkspaceValidationTests(unittest.TestCase):
    def test_valid_external_workspace_has_no_problems(self):
        self.assertEqual(validate_workspace(VALID_WORKSPACE), ())

    def test_rejects_unknown_schema(self):
        value = deepcopy(VALID_WORKSPACE)
        value["schema"] = "elephant.workspace/v2"
        self.assertIn("schema: expected elephant.workspace/v3", validate_workspace(value))

    def test_selected_external_provider_requires_binding(self):
        value = deepcopy(VALID_WORKSPACE)
        del value["bindings"]["notion"]
        problems = validate_workspace(value)
        self.assertIn("bindings.notion: required by selected provider", problems)

    def test_required_registry_sections_are_mappings(self):
        cases = (
            ("repository", None, "repository: required mapping"),
            ("providers", None, "providers: required mapping"),
            ("bindings", None, "bindings: required mapping"),
            ("products", [], "products: required mapping"),
            ("domains", [], "domains: required mapping"),
        )
        for key, malformed, expected in cases:
            with self.subTest(key=key, malformed=malformed):
                value = deepcopy(VALID_WORKSPACE)
                value[key] = malformed
                self.assertIn(expected, validate_workspace(value))

    def test_repository_requires_nonblank_stable_id(self):
        for repository in ({}, {"id": None}, {"id": ""}, {"id": "   "}):
            with self.subTest(repository=repository):
                value = deepcopy(VALID_WORKSPACE)
                value["repository"] = repository
                self.assertIn(
                    "repository.id: expected nonblank string",
                    validate_workspace(value),
                )

    def test_selected_external_bindings_require_mappings(self):
        for provider in ("linear", "notion"):
            with self.subTest(provider=provider):
                value = deepcopy(VALID_WORKSPACE)
                value["bindings"][provider] = None
                self.assertIn(
                    f"bindings.{provider}: required mapping",
                    validate_workspace(value),
                )

    def test_selected_external_bindings_require_every_opaque_id(self):
        cases = (
            ("linear", "workspace_id"),
            ("linear", "team_id"),
            ("notion", "workspace_id"),
            ("notion", "products_database_id"),
            ("notion", "knowledge_database_id"),
            ("notion", "contracts_database_id"),
        )
        for provider, field in cases:
            for malformed in (None, "", "   "):
                with self.subTest(provider=provider, field=field, malformed=malformed):
                    value = deepcopy(VALID_WORKSPACE)
                    value["bindings"][provider][field] = malformed
                    self.assertIn(
                        f"bindings.{provider}.{field}: expected nonblank string",
                        validate_workspace(value),
                    )

    def test_rejects_story_level_registry_content(self):
        value = deepcopy(VALID_WORKSPACE)
        value["stories"] = {"CF-1": {"status": "Ready"}}
        self.assertIn("stories: story-level registry content is forbidden", validate_workspace(value))

    def test_product_domains_must_exist(self):
        value = deepcopy(VALID_WORKSPACE)
        value["products"]["clickfalcon"]["primary_domains"] = ["missing"]
        self.assertIn(
            "products.clickfalcon.primary_domains[0]: unknown domain missing",
            validate_workspace(value),
        )

    def test_domain_products_must_exist(self):
        value = deepcopy(VALID_WORKSPACE)
        value["domains"]["clickfalcon"]["products"] = ["missing"]
        self.assertIn(
            "domains.clickfalcon.products[0]: unknown product missing",
            validate_workspace(value),
        )

    def test_rejects_unsafe_profile_path(self):
        value = deepcopy(VALID_WORKSPACE)
        value["products"]["clickfalcon"]["profile"] = "../outside.yaml"
        self.assertIn(
            "products.clickfalcon.profile: expected repository-relative POSIX path",
            validate_workspace(value),
        )

    def test_profiles_use_the_canonical_profile_directory_and_yaml_extension(self):
        for path in (
            "README.md",
            "profiles/clickfalcon.yaml",
            ".agents/elephant/clickfalcon.yaml",
            ".agents/elephant/profiles/nested/clickfalcon.yaml",
            ".agents/elephant/profiles/clickfalcon.yml",
            ".agents/elephant/profiles/clickfalcon.json",
            ".agents/elephant/profiles/.yaml",
        ):
            with self.subTest(path=path):
                product_workspace = deepcopy(VALID_WORKSPACE)
                product_workspace["products"]["clickfalcon"]["profile"] = path
                self.assertIn(
                    "products.clickfalcon.profile: expected "
                    ".agents/elephant/profiles/*.yaml",
                    validate_workspace(product_workspace),
                )

                engineering_workspace = deepcopy(VALID_WORKSPACE)
                engineering_workspace["engineering_profile"] = path
                self.assertIn(
                    "engineering_profile: expected .agents/elephant/profiles/*.yaml",
                    validate_workspace(engineering_workspace),
                )

    def test_engineering_profile_rejects_unsafe_repository_paths(self):
        for path in (
            "../engineering.yaml",
            "/tmp/engineering.yaml",
            ".agents/elephant/profiles\\engineering.yaml",
            ".agents/./elephant/profiles/engineering.yaml",
            ".agents//elephant/profiles/engineering.yaml",
        ):
            with self.subTest(path=path):
                value = deepcopy(VALID_WORKSPACE)
                value["engineering_profile"] = path
                self.assertIn(
                    "engineering_profile: expected repository-relative POSIX path",
                    validate_workspace(value),
                )

    def test_rejects_unsafe_and_noncanonical_scope_paths(self):
        for path in (
            "../outside",
            "/tmp/outside",
            "apps\\tracker-web",
            "apps/./tracker-web",
            "apps//tracker-web",
        ):
            with self.subTest(path=path):
                value = deepcopy(VALID_WORKSPACE)
                value["domains"]["clickfalcon"]["scopes"] = [path]
                self.assertIn(
                    "domains.clickfalcon.scopes[0]: "
                    "expected repository-relative POSIX path",
                    validate_workspace(value),
                )

    def test_instruction_paths_are_repository_relative_posix_paths(self):
        for path in (
            "../outside/AGENTS.md",
            "/tmp/AGENTS.md",
            "apps\\AGENTS.md",
            "apps/./AGENTS.md",
            "apps//AGENTS.md",
        ):
            with self.subTest(path=path):
                value = deepcopy(VALID_WORKSPACE)
                value["domains"]["clickfalcon"]["instruction_paths"] = [path]
                self.assertIn(
                    "domains.clickfalcon.instruction_paths[0]: "
                    "expected repository-relative POSIX path",
                    validate_workspace(value),
                )

    def test_product_and_domain_records_are_mappings(self):
        value = deepcopy(VALID_WORKSPACE)
        value["products"]["clickfalcon"] = None
        self.assertIn(
            "products.clickfalcon: required mapping",
            validate_workspace(value),
        )

        value = deepcopy(VALID_WORKSPACE)
        value["domains"]["clickfalcon"] = None
        self.assertIn(
            "domains.clickfalcon: required mapping",
            validate_workspace(value),
        )

    def test_product_records_require_provider_references_and_domain_list(self):
        for field in ("story_ref", "knowledge_ref"):
            for malformed in (None, "", "   "):
                with self.subTest(field=field, malformed=malformed):
                    value = deepcopy(VALID_WORKSPACE)
                    value["products"]["clickfalcon"][field] = malformed
                    self.assertIn(
                        f"products.clickfalcon.{field}: expected nonblank string",
                        validate_workspace(value),
                    )

        value = deepcopy(VALID_WORKSPACE)
        del value["products"]["clickfalcon"]["primary_domains"]
        self.assertIn(
            "products.clickfalcon.primary_domains: expected list",
            validate_workspace(value),
        )

    def test_domain_records_require_all_documented_lists(self):
        for field in ("scopes", "instruction_paths", "verification", "products"):
            with self.subTest(field=field):
                value = deepcopy(VALID_WORKSPACE)
                del value["domains"]["clickfalcon"][field]
                self.assertIn(
                    f"domains.clickfalcon.{field}: expected list",
                    validate_workspace(value),
                )

    def test_domain_verification_commands_are_nonblank_strings(self):
        for malformed in (None, "", "   "):
            with self.subTest(malformed=malformed):
                value = deepcopy(VALID_WORKSPACE)
                value["domains"]["clickfalcon"]["verification"] = [malformed]
                self.assertIn(
                    "domains.clickfalcon.verification[0]: expected nonblank string",
                    validate_workspace(value),
                )

    def test_instruction_paths_must_be_a_list(self):
        for instruction_paths in (None, "AGENTS.md", {"AGENTS.md": True}):
            with self.subTest(instruction_paths=instruction_paths):
                value = deepcopy(VALID_WORKSPACE)
                value["domains"]["clickfalcon"]["instruction_paths"] = instruction_paths
                self.assertIn(
                    "domains.clickfalcon.instruction_paths: expected list",
                    validate_workspace(value),
                )

    def test_verification_commands_must_be_a_list(self):
        for verification in (None, "bun run type-check", {"bun run type-check": True}):
            with self.subTest(verification=verification):
                value = deepcopy(VALID_WORKSPACE)
                value["domains"]["clickfalcon"]["verification"] = verification
                self.assertIn(
                    "domains.clickfalcon.verification: expected list",
                    validate_workspace(value),
                )

    def test_rejects_non_list_product_domains(self):
        for primary_domains in (None, "clickfalcon", {"clickfalcon": True}):
            with self.subTest(primary_domains=primary_domains):
                value = deepcopy(VALID_WORKSPACE)
                value["products"]["clickfalcon"]["primary_domains"] = primary_domains
                self.assertIn(
                    "products.clickfalcon.primary_domains: expected list",
                    validate_workspace(value),
                )

    def test_rejects_non_list_domain_products(self):
        for products in (None, "clickfalcon", {"clickfalcon": True}):
            with self.subTest(products=products):
                value = deepcopy(VALID_WORKSPACE)
                value["domains"]["clickfalcon"]["products"] = products
                self.assertIn(
                    "domains.clickfalcon.products: expected list",
                    validate_workspace(value),
                )

    def test_all_git_workspace_needs_no_external_binding(self):
        value = deepcopy(VALID_WORKSPACE)
        value["providers"] = {
            "story_store": "git",
            "product_knowledge_store": "git",
            "product_contract_store": "git",
            "delivery_workspace": "git",
        }
        value["bindings"] = {}
        self.assertEqual(validate_workspace(value), ())


PRODUCT_PROFILE = {
    "schema": "elephant.profile/v3",
    "kind": "product",
    "product": "clickfalcon",
    "context": {"knowledge_keys": ["product-overview", "glossary"]},
    "design_gate": {"enabled": False},
    "research": {"mode": "auto-assess", "depth": "light"},
    "execution": {"isolation": "git-worktree", "review_cadence": "task"},
    "verification": {"commands": ["bun run type-check"]},
    "finish": {"integration": "github-pr-squash", "auto_merge_on_green": True},
    "language": {"dialogue": "zh-CN", "docs": "en", "commits": "en"},
}

ENGINEERING_PROFILE = {
    **PRODUCT_PROFILE,
    "kind": "engineering",
    "product": None,
    "behavior_preservation_required": True,
}


class ProfileAndRoutingTests(unittest.TestCase):
    def test_valid_product_profile_has_no_problems(self):
        self.assertEqual(validate_profile(PRODUCT_PROFILE), ())

    def test_engineering_profile_requires_behavior_preservation(self):
        value = deepcopy(ENGINEERING_PROFILE)
        value["behavior_preservation_required"] = False
        self.assertIn(
            "behavior_preservation_required: engineering profile requires true",
            validate_profile(value),
        )

    def test_engineering_profile_requires_null_product(self):
        value = deepcopy(ENGINEERING_PROFILE)
        value["product"] = "clickfalcon"
        self.assertIn(
            "product: engineering profile requires null",
            validate_profile(value),
        )

    def test_product_profile_requires_non_blank_product_key(self):
        for product_key in (None, "", "   "):
            with self.subTest(product_key=product_key):
                value = deepcopy(PRODUCT_PROFILE)
                value["product"] = product_key
                self.assertIn(
                    "product: product profile requires a product key",
                    validate_profile(value),
                )

    def test_product_story_resolves_product_profile(self):
        self.assertEqual(
            resolve_profile(VALID_WORKSPACE, story_kind="product-facing", product_key="clickfalcon"),
            ".agents/elephant/profiles/clickfalcon.yaml",
        )

    def test_engineering_story_resolves_engineering_profile(self):
        self.assertEqual(
            resolve_profile(VALID_WORKSPACE, story_kind="engineering-only", product_key=None),
            ".agents/elephant/profiles/engineering.yaml",
        )

    def test_product_story_requires_exactly_one_known_product(self):
        with self.assertRaisesRegex(WorkspaceRouteError, "known product_key"):
            resolve_profile(VALID_WORKSPACE, story_kind="product-facing", product_key=None)

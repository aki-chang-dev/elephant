from copy import deepcopy
import unittest

from scripts.workspace_core import validate_workspace


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

    def test_rejects_unsafe_and_noncanonical_scope_paths(self):
        for path in ("../outside", "apps/./tracker-web", "apps//tracker-web"):
            with self.subTest(path=path):
                value = deepcopy(VALID_WORKSPACE)
                value["domains"]["clickfalcon"]["scopes"] = [path]
                self.assertIn(
                    "domains.clickfalcon.scopes[0]: "
                    "expected repository-relative POSIX path",
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

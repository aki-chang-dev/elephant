from __future__ import annotations

from copy import deepcopy
import unittest

from scripts.workspace_map import (
    WorkspaceMapError,
    planning_scope,
    resolve_product,
    validate_workspace_map,
)


SINGLE = {
    "schema": "elephant.workspace/v4",
    "repository": {
        "id": "sample",
        "github": "https://github.com/acme/sample",
    },
    "linear": {"workspace_id": "linear-workspace", "team_id": "linear-team"},
    "notion": {"root_id": "company-knowledge"},
    "domains": {
        "web": {
            "name": "Web",
            "paths": ["apps/web"],
            "instructions": ["AGENTS.md", "apps/web/AGENTS.md"],
            "verification": ["python3 -m unittest"],
        }
    },
    "products": {
        "sample": {
            "name": "Sample",
            "default": True,
            "domains": ["web"],
            "linear": {
                "planning_ref": "linear-planning",
                "backlog_ref": "linear-backlog",
            },
            "notion": {
                "home_id": "notion-product-home",
                "knowledge_map_id": "notion-knowledge-map",
            },
        }
    },
}


def multi_product() -> dict[str, object]:
    value = deepcopy(SINGLE)
    products = value["products"]
    assert isinstance(products, dict)
    sample = products["sample"]
    assert isinstance(sample, dict)
    sample_linear = sample["linear"]
    assert isinstance(sample_linear, dict)
    sample_linear.update(
        {
            "issue_label_id": "issue-label-sample",
            "project_label_id": "project-label-sample",
            "initiative_label_id": "initiative-label-sample",
        }
    )
    products["second"] = {
        "name": "Second",
        "default": False,
        "domains": ["web"],
        "linear": {
            "planning_ref": "linear-second-planning",
            "backlog_ref": "linear-second-backlog",
            "issue_label_id": "issue-label-second",
            "project_label_id": "project-label-second",
            "initiative_label_id": "initiative-label-second",
        },
        "notion": {
            "home_id": "notion-second-home",
            "knowledge_map_id": "notion-second-map",
        },
    }
    return value


class WorkspaceMapValidationTests(unittest.TestCase):
    def test_single_product_is_implicit_and_label_free(self) -> None:
        self.assertEqual(validate_workspace_map(SINGLE), ())
        route = resolve_product(SINGLE)
        self.assertEqual(route.key, "sample")
        self.assertEqual(route.name, "Sample")
        self.assertEqual(route.domain_keys, ("web",))
        self.assertEqual(planning_scope(SINGLE).product_labels, {})

    def test_multi_product_requires_and_returns_all_label_namespaces(self) -> None:
        value = multi_product()
        self.assertEqual(validate_workspace_map(value), ())
        scope = planning_scope(value, product_key="second")
        self.assertEqual(
            scope.product_labels,
            {
                "issue": "issue-label-second",
                "project": "project-label-second",
                "initiative": "initiative-label-second",
            },
        )

    def test_multi_product_rejects_each_missing_label(self) -> None:
        for field in (
            "issue_label_id",
            "project_label_id",
            "initiative_label_id",
        ):
            with self.subTest(field=field):
                value = multi_product()
                del value["products"]["second"]["linear"][field]
                self.assertIn(
                    f"products.second.linear.{field}: required for multiple Products",
                    validate_workspace_map(value),
                )

    def test_rejects_unknown_schema_and_missing_roots(self) -> None:
        value = deepcopy(SINGLE)
        value["schema"] = "elephant.workspace/v3"
        del value["linear"]
        del value["notion"]
        problems = validate_workspace_map(value)
        self.assertIn("schema: expected elephant.workspace/v4", problems)
        self.assertIn("linear: required mapping", problems)
        self.assertIn("notion: required mapping", problems)

    def test_rejects_unknown_domains_and_unsafe_paths(self) -> None:
        value = deepcopy(SINGLE)
        value["products"]["sample"]["domains"] = ["missing"]
        value["domains"]["web"]["paths"] = ["../outside", "/absolute"]
        problems = validate_workspace_map(value)
        self.assertIn("products.sample.domains[0]: unknown domain missing", problems)
        self.assertIn(
            "domains.web.paths[0]: expected repository-relative POSIX path",
            problems,
        )
        self.assertIn(
            "domains.web.paths[1]: expected repository-relative POSIX path",
            problems,
        )

    def test_product_to_domain_membership_has_one_owner(self) -> None:
        value = deepcopy(SINGLE)
        value["domains"]["web"]["products"] = ["sample"]
        self.assertIn(
            "domains.web.products: Product membership belongs only in Product entries",
            validate_workspace_map(value),
        )

    def test_rejects_story_content_and_secret_material_recursively(self) -> None:
        cases = (
            ("stories", {"CF-1": {}}),
            ("checkpoints", []),
            ("document_bodies", {"overview": "copy"}),
            ("api_token", "secret"),
            ("connector_tool_name", "linear_save_issue"),
            ("approval_hash", "abc"),
        )
        for key, forbidden in cases:
            with self.subTest(key=key):
                value = deepcopy(SINGLE)
                value["products"]["sample"]["extra"] = {key: forbidden}
                self.assertTrue(
                    any(key in problem for problem in validate_workspace_map(value)),
                    validate_workspace_map(value),
                )

    def test_rejects_non_https_urls_and_query_credentials(self) -> None:
        cases = (
            "http://github.com/acme/sample",
            "https://github.com/acme/sample?token=secret",
            "https://user:pass@github.com/acme/sample",
        )
        for github in cases:
            with self.subTest(github=github):
                value = deepcopy(SINGLE)
                value["repository"]["github"] = github
                self.assertIn(
                    "repository.github: expected safe HTTPS URL",
                    validate_workspace_map(value),
                )

    def test_requires_exactly_one_default_product(self) -> None:
        value = multi_product()
        value["products"]["sample"]["default"] = False
        self.assertIn(
            "products: expected exactly one default Product",
            validate_workspace_map(value),
        )
        value["products"]["second"]["default"] = True
        value["products"]["sample"]["default"] = True
        self.assertIn(
            "products: expected exactly one default Product",
            validate_workspace_map(value),
        )

    def test_rejects_blank_product_and_domain_keys(self) -> None:
        for section in ("products", "domains"):
            with self.subTest(section=section):
                value = deepcopy(SINGLE)
                item = next(iter(value[section].values()))
                value[section] = {" ": item}
                self.assertTrue(
                    any(
                        problem == f"{section}: keys must be nonblank stable strings"
                        for problem in validate_workspace_map(value)
                    )
                )

    def test_resolve_requires_known_product_when_multiple(self) -> None:
        value = multi_product()
        with self.assertRaisesRegex(
            WorkspaceMapError, "multiple Products require one known product_key"
        ):
            resolve_product(value)
        with self.assertRaisesRegex(WorkspaceMapError, "unknown Product missing"):
            resolve_product(value, product_key="missing")

    def test_invalid_workspace_never_routes(self) -> None:
        value = deepcopy(SINGLE)
        value["repository"]["id"] = ""
        with self.assertRaisesRegex(WorkspaceMapError, "workspace map is invalid"):
            resolve_product(value)


if __name__ == "__main__":
    unittest.main()

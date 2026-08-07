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
        scope = planning_scope(SINGLE)
        self.assertEqual(scope.team_id, "linear-team")
        self.assertEqual(scope.planning_ref, "linear-planning")
        self.assertEqual(scope.backlog_ref, "linear-backlog")
        self.assertEqual(scope.product_labels, {})
        with self.assertRaises(TypeError):
            route.linear["planning_ref"] = "changed"
        with self.assertRaises(TypeError):
            scope.product_labels["issue"] = "changed"

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

    def test_multi_product_allows_inactive_project_and_initiative_labels(self) -> None:
        value = multi_product()
        for product in value["products"].values():
            del product["linear"]["project_label_id"]
            del product["linear"]["initiative_label_id"]

        self.assertEqual(validate_workspace_map(value), ())
        self.assertEqual(
            planning_scope(value, product_key="second").product_labels,
            {"issue": "issue-label-second"},
        )

    def test_multi_product_still_requires_issue_label(self) -> None:
        value = multi_product()
        del value["products"]["second"]["linear"]["issue_label_id"]
        self.assertIn(
            "products.second.linear.issue_label_id: required for multiple Products",
            validate_workspace_map(value),
        )

    def test_multi_product_rejects_duplicate_present_optional_labels(self) -> None:
        value = multi_product()
        value["products"]["second"]["linear"]["project_label_id"] = value[
            "products"
        ]["sample"]["linear"]["project_label_id"]
        self.assertIn(
            "products.second.linear.project_label_id: duplicate Product label",
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

    def test_rejects_unknown_fields_in_each_fixed_schema_scope(self) -> None:
        cases = (
            ((), "github_token"),
            (("repository",), "access_token"),
            (("linear",), "client_secret"),
            (("notion",), "document_body"),
            (("domains", "web"), "story_registry"),
            (("products", "sample"), "plans"),
            (("products", "sample", "linear"), "connector_tool_name"),
            (("products", "sample", "notion"), "approval_receipt"),
        )
        for path, key in cases:
            with self.subTest(path=path, key=key):
                value = deepcopy(SINGLE)
                target = value
                for segment in path:
                    target = target[segment]
                target[key] = "forbidden"
                field = ".".join((*path, key))
                self.assertIn(
                    f"{field}: unknown workspace-map field",
                    validate_workspace_map(value),
                )

    def test_dynamic_product_and_domain_keys_are_not_schema_fields(self) -> None:
        value = deepcopy(SINGLE)
        value["domains"]["contracts"] = value["domains"].pop("web")
        value["products"]["sample"]["domains"] = ["contracts"]
        self.assertEqual(validate_workspace_map(value), ())

    def test_rejects_non_https_urls_and_query_credentials(self) -> None:
        cases = (
            "http://github.com/acme/sample",
            "https://github.com/acme/sample?token=secret",
            "https://github.com/acme/sample?X-Amz-Signature=secret",
            "https://github.com/acme/sample?X-Goog-Signature=secret",
            "https://github.com/acme/sample?AWSAccessKeyId=secret",
            "https://github.com/acme/sample#access_token=secret",
            "https://user:pass@github.com/acme/sample",
            "https://[bad",
            "https://:443/path",
            "https://github.com:bad/acme/sample",
        )
        for github in cases:
            with self.subTest(github=github):
                value = deepcopy(SINGLE)
                value["repository"]["github"] = github
                self.assertIn(
                    "repository.github: expected safe HTTPS URL",
                    validate_workspace_map(value),
                )

    def test_rejects_unsafe_values_in_every_anchor_field(self) -> None:
        fields = (
            (("linear",), "workspace_id"),
            (("linear",), "team_id"),
            (("linear",), "company_portfolio_ref"),
            (("notion",), "root_id"),
            (("notion",), "shared_knowledge_id"),
            (("products", "sample", "linear"), "planning_ref"),
            (("products", "sample", "linear"), "backlog_ref"),
            (("products", "sample", "linear"), "issue_label_id"),
            (("products", "sample", "linear"), "project_label_id"),
            (("products", "sample", "linear"), "initiative_label_id"),
            (("products", "sample", "notion"), "home_id"),
            (("products", "sample", "notion"), "knowledge_map_id"),
        )
        unsafe = (
            "https:malformed",
            "opaque id with spaces",
            "https://example.com/value?X-Amz-Credential=secret",
            "https://example.com/value?X-Goog-Signature=secret",
            "https://example.com/value?AWSAccessKeyId=secret",
            "https://example.com/value#api_key=secret",
            "https://[bad",
            "https://:443/value",
            "https://example.com:bad/value",
        )
        for path, field in fields:
            for value_text in unsafe:
                with self.subTest(path=path, field=field, value=value_text):
                    value = deepcopy(SINGLE)
                    target = value
                    for segment in path:
                        target = target[segment]
                    target[field] = value_text
                    self.assertTrue(
                        any(
                            problem.startswith(f"{'.'.join((*path, field))}:")
                            for problem in validate_workspace_map(value)
                        ),
                        validate_workspace_map(value),
                    )

    def test_allows_benign_https_query_and_fragment(self) -> None:
        value = deepcopy(SINGLE)
        value["products"]["sample"]["linear"]["planning_ref"] = (
            "https://linear.app/acme/project/sample?view=active#overview"
        )
        self.assertEqual(validate_workspace_map(value), ())

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

"""Self-contained smoke for the installed minimal workspace-map runtime."""

from __future__ import annotations

from copy import deepcopy

from .workspace_map import planning_scope, resolve_product, validate_workspace_map


_SINGLE = {
    "schema": "elephant.workspace/v4",
    "repository": {"id": "sample", "github": "https://github.com/acme/sample"},
    "linear": {"workspace_id": "linear-workspace", "team_id": "linear-team"},
    "notion": {"root_id": "company-knowledge"},
    "domains": {"web": {"paths": ["apps/web"], "instructions": ["AGENTS.md"]}},
    "products": {
        "sample": {
            "name": "Sample",
            "default": True,
            "domains": ["web"],
            "linear": {"planning_ref": "planning", "backlog_ref": "backlog"},
            "notion": {"home_id": "sample-home", "knowledge_map_id": "sample-map"},
        }
    },
}


def _multi_product() -> dict[str, object]:
    document = deepcopy(_SINGLE)
    products = document["products"]
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
            "planning_ref": "second-planning",
            "backlog_ref": "second-backlog",
            "issue_label_id": "issue-label-second",
        },
        "notion": {"home_id": "second-home", "knowledge_map_id": "second-map"},
    }
    return document


def run_installed_smoke() -> dict[str, object]:
    multi = _multi_product()
    for document in (_SINGLE, multi):
        problems = validate_workspace_map(document)
        if problems:
            raise AssertionError(f"installed workspace map is invalid: {problems}")

    single_route = resolve_product(_SINGLE)
    single_scope = planning_scope(_SINGLE)
    multi_route = resolve_product(multi, product_key="second")
    multi_scope = planning_scope(multi, product_key="second")
    return {
        "single_product": {
            "product": single_route.key,
            "team_id": single_scope.team_id,
            "labels": dict(single_scope.product_labels),
        },
        "multi_product": {
            "product": multi_route.key,
            "team_id": multi_scope.team_id,
            "labels": dict(multi_scope.product_labels),
        },
    }


__all__ = ["run_installed_smoke"]

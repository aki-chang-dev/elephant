from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath


WORKSPACE_SCHEMA = "elephant.workspace/v3"
PROVIDER_CHOICES = {
    "story_store": {"linear", "git"},
    "product_knowledge_store": {"notion", "git"},
    "product_contract_store": {"notion", "git"},
    "delivery_workspace": {"git"},
}
FORBIDDEN_STORY_KEYS = {"stories", "story_registry", "checkpoints", "contracts", "plans"}


class WorkspaceRouteError(ValueError):
    pass


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _is_repo_relative_posix_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        return False
    parts = PurePosixPath(value).parts
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def validate_workspace(document: Mapping[str, object]) -> tuple[str, ...]:
    problems: list[str] = []
    if document.get("schema") != WORKSPACE_SCHEMA:
        problems.append(f"schema: expected {WORKSPACE_SCHEMA}")

    for key in sorted(FORBIDDEN_STORY_KEYS & document.keys()):
        problems.append(f"{key}: story-level registry content is forbidden")

    providers = _mapping(document.get("providers"))
    bindings = _mapping(document.get("bindings"))
    for slot, choices in PROVIDER_CHOICES.items():
        selected = providers.get(slot)
        if selected not in choices:
            problems.append(f"providers.{slot}: expected one of {sorted(choices)}")
        if selected in {"linear", "notion"} and selected not in bindings:
            problems.append(f"bindings.{selected}: required by selected provider")

    products = _mapping(document.get("products"))
    domains = _mapping(document.get("domains"))
    for product_key, raw_product in products.items():
        product = _mapping(raw_product)
        if not _is_repo_relative_posix_path(product.get("profile")):
            problems.append(
                f"products.{product_key}.profile: expected repository-relative POSIX path"
            )
        for index, domain in enumerate(product.get("primary_domains", [])):
            if domain not in domains:
                problems.append(
                    f"products.{product_key}.primary_domains[{index}]: unknown domain {domain}"
                )
    for domain_key, raw_domain in domains.items():
        domain = _mapping(raw_domain)
        for index, product in enumerate(domain.get("products", [])):
            if product not in products:
                problems.append(
                    f"domains.{domain_key}.products[{index}]: unknown product {product}"
                )
    if not _is_repo_relative_posix_path(document.get("engineering_profile")):
        problems.append("engineering_profile: expected repository-relative POSIX path")
    return tuple(problems)

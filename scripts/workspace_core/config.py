from __future__ import annotations

from collections.abc import Mapping


WORKSPACE_SCHEMA = "elephant.workspace/v3"
PROFILE_SCHEMA = "elephant.profile/v3"
PROFILE_KINDS = {"product", "engineering"}
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
    parts = value.split("/")
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
        primary_domains = product.get("primary_domains", [])
        if not isinstance(primary_domains, list):
            problems.append(f"products.{product_key}.primary_domains: expected list")
            continue
        for index, domain in enumerate(primary_domains):
            if not isinstance(domain, str) or domain not in domains:
                problems.append(
                    f"products.{product_key}.primary_domains[{index}]: unknown domain {domain}"
                )
    for domain_key, raw_domain in domains.items():
        domain = _mapping(raw_domain)
        scopes = domain.get("scopes", [])
        if not isinstance(scopes, list):
            problems.append(f"domains.{domain_key}.scopes: expected list")
        else:
            for index, scope in enumerate(scopes):
                if not _is_repo_relative_posix_path(scope):
                    problems.append(
                        f"domains.{domain_key}.scopes[{index}]: "
                        "expected repository-relative POSIX path"
                    )
        domain_products = domain.get("products", [])
        if not isinstance(domain_products, list):
            problems.append(f"domains.{domain_key}.products: expected list")
            continue
        for index, product in enumerate(domain_products):
            if not isinstance(product, str) or product not in products:
                problems.append(
                    f"domains.{domain_key}.products[{index}]: unknown product {product}"
                )
    if not _is_repo_relative_posix_path(document.get("engineering_profile")):
        problems.append("engineering_profile: expected repository-relative POSIX path")
    return tuple(problems)


def validate_profile(document: Mapping[str, object]) -> tuple[str, ...]:
    problems: list[str] = []
    if document.get("schema") != PROFILE_SCHEMA:
        problems.append(f"schema: expected {PROFILE_SCHEMA}")
    kind = document.get("kind")
    if kind not in PROFILE_KINDS:
        problems.append(f"kind: expected one of {sorted(PROFILE_KINDS)}")
    product = document.get("product")
    if kind == "product" and (not isinstance(product, str) or not product.strip()):
        problems.append("product: product profile requires a product key")
    if kind == "engineering":
        if product is not None:
            problems.append("product: engineering profile requires null")
        if document.get("behavior_preservation_required") is not True:
            problems.append("behavior_preservation_required: engineering profile requires true")
    for section in (
        "context",
        "design_gate",
        "research",
        "execution",
        "verification",
        "finish",
        "language",
    ):
        if not isinstance(document.get(section), Mapping):
            problems.append(f"{section}: required mapping")
    return tuple(problems)


def resolve_profile(
    workspace: Mapping[str, object], *, story_kind: str, product_key: str | None
) -> str:
    if validate_workspace(workspace):
        raise WorkspaceRouteError("workspace is invalid")
    if story_kind == "engineering-only":
        profile = workspace.get("engineering_profile")
        if not isinstance(profile, str):
            raise WorkspaceRouteError("engineering_profile is required")
        return profile
    if story_kind != "product-facing":
        raise WorkspaceRouteError("story_kind must be product-facing or engineering-only")
    products = _mapping(workspace.get("products"))
    if product_key is None or product_key not in products:
        raise WorkspaceRouteError("product-facing story requires one known product_key")
    profile = _mapping(products[product_key]).get("profile")
    if not isinstance(profile, str):
        raise WorkspaceRouteError(f"product {product_key} has no profile")
    return profile

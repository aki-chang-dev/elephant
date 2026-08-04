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
EXTERNAL_BINDING_FIELDS = {
    "linear": ("workspace_id", "team_id"),
    "notion": (
        "workspace_id",
        "products_database_id",
        "knowledge_database_id",
        "contracts_database_id",
    ),
}
PROFILE_PATH_PREFIX = (".agents", "elephant", "profiles")


class WorkspaceRouteError(ValueError):
    pass


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _is_nonblank_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_repo_relative_posix_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        return False
    parts = value.split("/")
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def _is_profile_path(value: object) -> bool:
    if not _is_repo_relative_posix_path(value):
        return False
    assert isinstance(value, str)
    parts = tuple(value.split("/"))
    return (
        len(parts) == 4
        and parts[:3] == PROFILE_PATH_PREFIX
        and parts[3].endswith(".yaml")
        and parts[3] != ".yaml"
    )


def _validate_profile_path(value: object, field: str, problems: list[str]) -> None:
    if not _is_repo_relative_posix_path(value):
        problems.append(f"{field}: expected repository-relative POSIX path")
    elif not _is_profile_path(value):
        problems.append(f"{field}: expected .agents/elephant/profiles/*.yaml")


def validate_workspace(document: Mapping[str, object]) -> tuple[str, ...]:
    problems: list[str] = []
    if document.get("schema") != WORKSPACE_SCHEMA:
        problems.append(f"schema: expected {WORKSPACE_SCHEMA}")

    for key in sorted(FORBIDDEN_STORY_KEYS & document.keys()):
        problems.append(f"{key}: story-level registry content is forbidden")

    raw_repository = document.get("repository")
    if not isinstance(raw_repository, Mapping):
        problems.append("repository: required mapping")
    elif not _is_nonblank_string(raw_repository.get("id")):
        problems.append("repository.id: expected nonblank string")

    raw_providers = document.get("providers")
    if not isinstance(raw_providers, Mapping):
        problems.append("providers: required mapping")
    providers = _mapping(raw_providers)

    raw_bindings = document.get("bindings")
    if not isinstance(raw_bindings, Mapping):
        problems.append("bindings: required mapping")
    bindings = _mapping(raw_bindings)

    selected_external_providers: set[str] = set()
    for slot, choices in PROVIDER_CHOICES.items():
        selected = providers.get(slot)
        if selected not in choices:
            problems.append(f"providers.{slot}: expected one of {sorted(choices)}")
        if selected in EXTERNAL_BINDING_FIELDS:
            selected_external_providers.add(selected)

    for provider in sorted(selected_external_providers):
        if provider not in bindings:
            problems.append(f"bindings.{provider}: required by selected provider")
            continue
        binding = bindings[provider]
        if not isinstance(binding, Mapping):
            problems.append(f"bindings.{provider}: required mapping")
            continue
        for field in EXTERNAL_BINDING_FIELDS[provider]:
            if not _is_nonblank_string(binding.get(field)):
                problems.append(
                    f"bindings.{provider}.{field}: expected nonblank string"
                )

    raw_products = document.get("products")
    if not isinstance(raw_products, Mapping):
        problems.append("products: required mapping")
    products = _mapping(raw_products)

    raw_domains = document.get("domains")
    if not isinstance(raw_domains, Mapping):
        problems.append("domains: required mapping")
    domains = _mapping(raw_domains)

    for product_key, raw_product in products.items():
        if not isinstance(raw_product, Mapping):
            problems.append(f"products.{product_key}: required mapping")
            continue
        product = raw_product
        _validate_profile_path(
            product.get("profile"), f"products.{product_key}.profile", problems
        )
        for field in ("story_ref", "knowledge_ref"):
            if not _is_nonblank_string(product.get(field)):
                problems.append(
                    f"products.{product_key}.{field}: expected nonblank string"
                )
        primary_domains = product.get("primary_domains")
        if not isinstance(primary_domains, list):
            problems.append(f"products.{product_key}.primary_domains: expected list")
            continue
        for index, domain in enumerate(primary_domains):
            if not _is_nonblank_string(domain):
                problems.append(
                    f"products.{product_key}.primary_domains[{index}]: "
                    "expected nonblank domain key"
                )
            elif domain not in domains:
                problems.append(
                    f"products.{product_key}.primary_domains[{index}]: unknown domain {domain}"
                )
    for domain_key, raw_domain in domains.items():
        if not isinstance(raw_domain, Mapping):
            problems.append(f"domains.{domain_key}: required mapping")
            continue
        domain = raw_domain
        for field in ("scopes", "instruction_paths"):
            paths = domain.get(field)
            if not isinstance(paths, list):
                problems.append(f"domains.{domain_key}.{field}: expected list")
            else:
                for index, path in enumerate(paths):
                    if not _is_repo_relative_posix_path(path):
                        problems.append(
                            f"domains.{domain_key}.{field}[{index}]: "
                            "expected repository-relative POSIX path"
                        )

        verification = domain.get("verification")
        if not isinstance(verification, list):
            problems.append(f"domains.{domain_key}.verification: expected list")
        else:
            for index, command in enumerate(verification):
                if not _is_nonblank_string(command):
                    problems.append(
                        f"domains.{domain_key}.verification[{index}]: "
                        "expected nonblank string"
                    )

        domain_products = domain.get("products")
        if not isinstance(domain_products, list):
            problems.append(f"domains.{domain_key}.products: expected list")
            continue
        for index, product in enumerate(domain_products):
            if not _is_nonblank_string(product):
                problems.append(
                    f"domains.{domain_key}.products[{index}]: "
                    "expected nonblank product key"
                )
            elif product not in products:
                problems.append(
                    f"domains.{domain_key}.products[{index}]: unknown product {product}"
                )
    _validate_profile_path(
        document.get("engineering_profile"), "engineering_profile", problems
    )
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

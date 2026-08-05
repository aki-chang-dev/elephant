from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from urllib.parse import parse_qsl, urlsplit


WORKSPACE_SCHEMA = "elephant.workspace/v4"
_LABEL_FIELDS = {
    "issue": "issue_label_id",
    "project": "project_label_id",
    "initiative": "initiative_label_id",
}
_FORBIDDEN_KEYS = {
    "stories",
    "story_registry",
    "checkpoints",
    "contracts",
    "plans",
    "document_bodies",
    "oauth",
    "oauth_token",
    "token",
    "api_token",
    "password",
    "secret",
    "connector_tool_name",
    "approval_receipt",
    "approval_hash",
    "fingerprint",
    "hash",
}
_CREDENTIAL_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "key",
    "password",
    "secret",
    "signature",
    "token",
}


class WorkspaceMapError(ValueError):
    pass


@dataclass(frozen=True)
class ProductRoute:
    key: str
    name: str
    domain_keys: tuple[str, ...]
    linear: Mapping[str, object]
    notion: Mapping[str, object]


@dataclass(frozen=True)
class PlanningScope:
    team_id: str
    planning_ref: str | None
    backlog_ref: str | None
    product_labels: Mapping[str, str]


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[object] | None:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    return None


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _repo_path(value: object) -> bool:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        return False
    return all(part not in {"", ".", ".."} for part in value.split("/"))


def _safe_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        return False
    query_keys = {key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}
    return not bool(query_keys & _CREDENTIAL_QUERY_KEYS)


def _anchor(value: object) -> bool:
    if not _nonblank(value):
        return False
    assert isinstance(value, str)
    return _safe_https_url(value) if "://" in value else True


def _find_forbidden(value: object, path: str, problems: list[str]) -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key)
            child = f"{path}.{key}" if path else key
            if key.lower() in _FORBIDDEN_KEYS:
                problems.append(f"{child}: forbidden workspace-map content")
            _find_forbidden(item, child, problems)
    elif _sequence(value) is not None:
        assert not isinstance(value, (str, bytes))
        for index, item in enumerate(value):
            _find_forbidden(item, f"{path}[{index}]", problems)


def _validate_string_list(
    value: object,
    field: str,
    problems: list[str],
    *,
    paths: bool = False,
) -> tuple[str, ...]:
    items = _sequence(value)
    if items is None:
        problems.append(f"{field}: expected list")
        return ()
    result: list[str] = []
    for index, item in enumerate(items):
        valid = _repo_path(item) if paths else _nonblank(item)
        if not valid:
            expected = "repository-relative POSIX path" if paths else "nonblank string"
            problems.append(f"{field}[{index}]: expected {expected}")
            continue
        assert isinstance(item, str)
        result.append(item)
    return tuple(result)


def _validate_optional_anchors(
    value: Mapping[str, object],
    field: str,
    names: tuple[str, ...],
    problems: list[str],
) -> None:
    for name in names:
        if name in value and not _anchor(value.get(name)):
            problems.append(f"{field}.{name}: expected HTTPS URL or opaque ID")


def validate_workspace_map(document: Mapping[str, object]) -> tuple[str, ...]:
    problems: list[str] = []
    if document.get("schema") != WORKSPACE_SCHEMA:
        problems.append(f"schema: expected {WORKSPACE_SCHEMA}")
    _find_forbidden(document, "", problems)

    repository = document.get("repository")
    if not isinstance(repository, Mapping):
        problems.append("repository: required mapping")
    else:
        if not _nonblank(repository.get("id")):
            problems.append("repository.id: expected nonblank string")
        if "github" in repository and not _safe_https_url(repository.get("github")):
            problems.append("repository.github: expected safe HTTPS URL")

    linear = document.get("linear")
    if not isinstance(linear, Mapping):
        problems.append("linear: required mapping")
    else:
        for name in ("workspace_id", "team_id"):
            if not _anchor(linear.get(name)):
                problems.append(f"linear.{name}: expected HTTPS URL or opaque ID")
        _validate_optional_anchors(linear, "linear", ("company_portfolio_ref",), problems)

    notion = document.get("notion")
    if not isinstance(notion, Mapping):
        problems.append("notion: required mapping")
    else:
        if not _anchor(notion.get("root_id")):
            problems.append("notion.root_id: expected HTTPS URL or opaque ID")
        _validate_optional_anchors(notion, "notion", ("shared_knowledge_id",), problems)

    raw_domains = document.get("domains")
    if not isinstance(raw_domains, Mapping) or not raw_domains:
        problems.append("domains: required nonempty mapping")
    domains = _mapping(raw_domains)
    if any(not _nonblank(key) for key in domains):
        problems.append("domains: keys must be nonblank stable strings")
    for key, raw_domain in domains.items():
        if not isinstance(raw_domain, Mapping):
            problems.append(f"domains.{key}: required mapping")
            continue
        if "products" in raw_domain:
            problems.append(
                f"domains.{key}.products: Product membership belongs only in Product entries"
            )
        if not _nonblank(raw_domain.get("name")):
            problems.append(f"domains.{key}.name: expected nonblank string")
        _validate_string_list(raw_domain.get("paths"), f"domains.{key}.paths", problems, paths=True)
        _validate_string_list(
            raw_domain.get("instructions"),
            f"domains.{key}.instructions",
            problems,
            paths=True,
        )
        if "verification" in raw_domain:
            _validate_string_list(
                raw_domain.get("verification"),
                f"domains.{key}.verification",
                problems,
            )

    raw_products = document.get("products")
    if not isinstance(raw_products, Mapping) or not raw_products:
        problems.append("products: required nonempty mapping")
    products = _mapping(raw_products)
    if any(not _nonblank(key) for key in products):
        problems.append("products: keys must be nonblank stable strings")
    default_count = 0
    multiple = len(products) > 1
    labels_by_namespace: dict[str, set[str]] = {name: set() for name in _LABEL_FIELDS}
    for key, raw_product in products.items():
        if not isinstance(raw_product, Mapping):
            problems.append(f"products.{key}: required mapping")
            continue
        if raw_product.get("default") is True:
            default_count += 1
        elif raw_product.get("default") is not False:
            problems.append(f"products.{key}.default: expected boolean")
        if not _nonblank(raw_product.get("name")):
            problems.append(f"products.{key}.name: expected nonblank string")
        domain_keys = _validate_string_list(
            raw_product.get("domains"), f"products.{key}.domains", problems
        )
        for index, domain_key in enumerate(domain_keys):
            if domain_key not in domains:
                problems.append(
                    f"products.{key}.domains[{index}]: unknown domain {domain_key}"
                )

        product_linear = raw_product.get("linear")
        if not isinstance(product_linear, Mapping):
            problems.append(f"products.{key}.linear: required mapping")
            product_linear = {}
        _validate_optional_anchors(
            product_linear,
            f"products.{key}.linear",
            ("planning_ref", "backlog_ref") + tuple(_LABEL_FIELDS.values()),
            problems,
        )
        if multiple:
            for namespace, field in _LABEL_FIELDS.items():
                label = product_linear.get(field)
                if not _anchor(label):
                    problems.append(
                        f"products.{key}.linear.{field}: required for multiple Products"
                    )
                elif isinstance(label, str):
                    if label in labels_by_namespace[namespace]:
                        problems.append(
                            f"products.{key}.linear.{field}: duplicate Product label"
                        )
                    labels_by_namespace[namespace].add(label)

        product_notion = raw_product.get("notion")
        if not isinstance(product_notion, Mapping):
            problems.append(f"products.{key}.notion: required mapping")
            product_notion = {}
        _validate_optional_anchors(
            product_notion,
            f"products.{key}.notion",
            ("home_id", "knowledge_map_id"),
            problems,
        )

    if default_count != 1:
        problems.append("products: expected exactly one default Product")
    return tuple(problems)


def resolve_product(
    document: Mapping[str, object], *, product_key: str | None = None
) -> ProductRoute:
    if validate_workspace_map(document):
        raise WorkspaceMapError("workspace map is invalid")
    products = _mapping(document.get("products"))
    if product_key is None:
        if len(products) != 1:
            raise WorkspaceMapError("multiple Products require one known product_key")
        product_key = next(iter(products))
    if product_key not in products:
        raise WorkspaceMapError(f"unknown Product {product_key}")
    product = _mapping(products[product_key])
    domains = _sequence(product.get("domains")) or ()
    return ProductRoute(
        key=product_key,
        name=str(product["name"]),
        domain_keys=tuple(str(item) for item in domains),
        linear=MappingProxyType(dict(_mapping(product.get("linear")))),
        notion=MappingProxyType(dict(_mapping(product.get("notion")))),
    )


def planning_scope(
    document: Mapping[str, object], *, product_key: str | None = None
) -> PlanningScope:
    route = resolve_product(document, product_key=product_key)
    root_linear = _mapping(document.get("linear"))
    products = _mapping(document.get("products"))
    labels: dict[str, str] = {}
    if len(products) > 1:
        labels = {
            namespace: str(route.linear[field])
            for namespace, field in _LABEL_FIELDS.items()
        }
    planning_ref = route.linear.get("planning_ref")
    backlog_ref = route.linear.get("backlog_ref")
    return PlanningScope(
        team_id=str(root_linear["team_id"]),
        planning_ref=str(planning_ref) if planning_ref is not None else None,
        backlog_ref=str(backlog_ref) if backlog_ref is not None else None,
        product_labels=MappingProxyType(labels),
    )


__all__ = [
    "WORKSPACE_SCHEMA",
    "PlanningScope",
    "ProductRoute",
    "WorkspaceMapError",
    "planning_scope",
    "resolve_product",
    "validate_workspace_map",
]

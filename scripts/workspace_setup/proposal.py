from __future__ import annotations

from collections import defaultdict

from .models import (
    Candidate,
    Confidence,
    ConfirmedDomain,
    ConfirmedProduct,
    ConfirmedTopology,
    Evidence,
    ExternalDiscovery,
    OwnerQuestion,
    RepositoryDiscovery,
    TopologyConflict,
    TopologyProposal,
)


def _key(value: str) -> str:
    return value.strip().lower().replace(" ", "-")


def _external_evidence(provider: str, kind: str, external_id: str, display_name: str) -> Evidence:
    return Evidence(provider, f"{kind}:{external_id}", display_name)


def _candidate_confidence(evidence: tuple[Evidence, ...]) -> Confidence:
    return Confidence.MEDIUM if evidence else Confidence.LOW


def _conflict(kind: str, key: str, records: tuple[object, ...]) -> TopologyConflict | None:
    display_names = {record.display_name for record in records}
    external_ids = {record.external_id for record in records}
    if len(display_names) == 1 and len(external_ids) == 1:
        return None
    alternatives = tuple(sorted({f"{record.display_name} ({record.external_id})" for record in records}))
    evidence = tuple(
        sorted(
            (_external_evidence(record.provider, record.kind, record.external_id, record.display_name) for record in records),
            key=lambda item: (item.source, item.ref, item.value),
        )
    )
    return TopologyConflict(f"{kind}.{key}", kind, alternatives, evidence)


def _owner_question(kind: str, candidate: Candidate) -> OwnerQuestion:
    return OwnerQuestion(
        key=f"{kind}.{candidate.key}.confirm",
        prompt=f"Confirm {candidate.display_name} as a {kind} identity",
        evidence=candidate.evidence,
        confidence=candidate.confidence,
    )


def propose_topology(repository: RepositoryDiscovery, external: ExternalDiscovery) -> TopologyProposal:
    if not isinstance(repository, RepositoryDiscovery):
        raise TypeError("repository: expected RepositoryDiscovery")
    if not isinstance(external, ExternalDiscovery):
        raise TypeError("external: expected ExternalDiscovery")

    external_by_identity: dict[tuple[str, str], list[object]] = defaultdict(list)
    for record in external.objects:
        external_by_identity[(_key(record.kind), _key(record.key))].append(record)

    conflicts: list[TopologyConflict] = []
    product_candidates: list[Candidate] = []
    domain_evidence: dict[str, list[Evidence]] = defaultdict(list)
    domain_names: dict[str, set[str]] = defaultdict(set)
    domain_scopes: dict[str, set[str]] = defaultdict(set)
    for unit in repository.workspace_units:
        domain_key = _key(unit.path.rsplit("/", 1)[-1])
        domain_names[domain_key].add(unit.path.rsplit("/", 1)[-1].replace("-", " ").title())
        domain_scopes[domain_key].add(unit.path)
        domain_evidence[domain_key].append(Evidence("repository", unit.manifest_path, unit.package_name))

    for (kind, key), records_list in sorted(external_by_identity.items()):
        records = tuple(records_list)
        conflict = _conflict(kind, key, records)
        if conflict is not None and kind in {"product", "domain"}:
            conflicts.append(conflict)
        evidence = tuple(
            sorted(
                (_external_evidence(record.provider, record.kind, record.external_id, record.display_name) for record in records),
                key=lambda item: (item.source, item.ref, item.value),
            )
        )
        if kind == "product":
            product_candidates.append(Candidate(key, records[0].display_name, evidence, _candidate_confidence(evidence)))
        elif kind == "domain":
            domain_evidence[key].extend(evidence)
            domain_names[key].update(record.display_name for record in records)

    domain_candidates: list[Candidate] = []
    questions: list[OwnerQuestion] = []
    for key in sorted(domain_evidence):
        evidence = tuple(sorted(domain_evidence[key], key=lambda item: (item.source, item.ref, item.value)))
        display_name = sorted(domain_names[key])[0] if domain_names[key] else key
        candidate = Candidate(key, display_name, evidence, _candidate_confidence(evidence))
        domain_candidates.append(candidate)
        if len(domain_names[key]) > 1 or len(domain_scopes[key]) > 1:
            questions.append(_owner_question("domain", candidate))

    for candidate in sorted(product_candidates, key=lambda item: item.key):
        questions.append(_owner_question("product", candidate))
    return TopologyProposal(
        repository_candidate=repository.repository_candidate,
        product_candidates=tuple(sorted(product_candidates, key=lambda item: item.key)),
        domain_candidates=tuple(domain_candidates),
        conflicts=tuple(sorted(conflicts, key=lambda item: item.key)),
        questions=tuple(sorted(questions, key=lambda item: item.key)),
    )


def _require_confirmed_values(values: object, item_type: type[object], field_name: str) -> tuple[object, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name}: expected tuple")
    if not all(isinstance(value, item_type) for value in values):
        raise TypeError(f"{field_name}: expected {item_type.__name__} values")
    return values


def _unique_keys(values: tuple[object, ...], field_name: str) -> set[str]:
    keys = [value.key for value in values]
    if len(keys) != len(set(keys)):
        raise ValueError(f"duplicate {field_name} key")
    return set(keys)


def _reject_duplicate_links(values: tuple[str, ...], field_name: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {field_name} key")


def confirm_topology(
    proposal: TopologyProposal,
    products: tuple[ConfirmedProduct, ...],
    domains: tuple[ConfirmedDomain, ...],
) -> ConfirmedTopology:
    if not isinstance(proposal, TopologyProposal):
        raise TypeError("proposal: expected TopologyProposal")
    confirmed_products = _require_confirmed_values(products, ConfirmedProduct, "products")
    confirmed_domains = _require_confirmed_values(domains, ConfirmedDomain, "domains")
    product_keys = _unique_keys(confirmed_products, "product")
    domain_keys = _unique_keys(confirmed_domains, "domain")
    for product in confirmed_products:
        _reject_duplicate_links(product.domain_keys, "domain")
    for domain in confirmed_domains:
        _reject_duplicate_links(domain.product_keys, "product")
    candidate_products = {candidate.key for candidate in proposal.product_candidates}
    candidate_domains = {candidate.key for candidate in proposal.domain_candidates}
    unknown_products = product_keys - candidate_products
    unknown_domains = domain_keys - candidate_domains
    if unknown_products:
        raise ValueError(f"unknown product key: {sorted(unknown_products)[0]}")
    if unknown_domains:
        raise ValueError(f"unknown domain key: {sorted(unknown_domains)[0]}")
    if not proposal.repository_candidate.key.strip():
        raise ValueError("repository ID must not be empty")
    conflict_keys = {conflict.key for conflict in proposal.conflicts}
    referenced_conflicts = {
        f"product.{key}" for key in product_keys
    } | {
        f"domain.{key}" for key in domain_keys
    }
    if conflict_keys & referenced_conflicts:
        raise ValueError("unresolved conflicts require owner resolution")
    product_links = {(product.key, domain_key) for product in confirmed_products for domain_key in product.domain_keys}
    domain_links = {(product_key, domain.key) for domain in confirmed_domains for product_key in domain.product_keys}
    if product_links != domain_links:
        raise ValueError("product and domain links must be reciprocal")
    if any(domain_key not in domain_keys for _, domain_key in product_links):
        raise ValueError("product and domain links must be reciprocal")
    if any(product_key not in product_keys for product_key, _ in domain_links):
        raise ValueError("product and domain links must be reciprocal")
    return ConfirmedTopology(
        repository_id=proposal.repository_candidate.key,
        products=tuple(sorted(confirmed_products, key=lambda item: item.key)),
        domains=tuple(sorted(confirmed_domains, key=lambda item: item.key)),
    )

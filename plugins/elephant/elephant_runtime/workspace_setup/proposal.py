from __future__ import annotations

from collections import defaultdict

from .models import (
    Candidate,
    Confidence,
    ConfirmedDomain,
    ConfirmedProduct,
    ConfirmedTopology,
    ConflictResolution,
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


_CONFIDENCE_PRIORITY = {
    Confidence.LOW: 0,
    Confidence.MEDIUM: 1,
    Confidence.HIGH: 2,
    Confidence.CONFIRMED: 3,
}


def _merge_product_candidates(
    candidates: list[Candidate],
) -> tuple[Candidate, ...]:
    merged: dict[str, Candidate] = {}
    for candidate in candidates:
        existing = merged.get(candidate.key)
        if existing is None:
            merged[candidate.key] = candidate
            continue
        evidence = tuple(
            sorted(
                set(existing.evidence + candidate.evidence),
                key=lambda item: (item.source, item.ref, item.value),
            )
        )
        confidence = max(
            (existing.confidence, candidate.confidence),
            key=_CONFIDENCE_PRIORITY.__getitem__,
        )
        merged[candidate.key] = Candidate(
            key=candidate.key,
            display_name=existing.display_name,
            evidence=evidence,
            confidence=confidence,
        )
    return tuple(merged[key] for key in sorted(merged))


def _repository_external_product_conflicts(
    candidates: list[Candidate],
    conflicts: list[TopologyConflict],
) -> tuple[TopologyConflict, ...]:
    result = list(conflicts)
    conflict_indexes = {
        conflict.key: index for index, conflict in enumerate(result)
    }
    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.key].append(candidate)
    for key, values in sorted(grouped.items()):
        conflict_key = f"product.{key}"
        existing_index = conflict_indexes.get(conflict_key)
        if (
            existing_index is None
            and len({value.display_name for value in values}) < 2
        ):
            continue
        existing = (
            result[existing_index] if existing_index is not None else None
        )
        alternatives = list(existing.alternatives if existing is not None else ())
        evidence = set(existing.evidence if existing is not None else ())
        represented_names = {
            alternative.rsplit(" (", 1)[0] for alternative in alternatives
        }
        for value in values:
            if value.display_name not in represented_names:
                primary = min(
                    value.evidence,
                    key=lambda item: (item.source, item.ref, item.value),
                    default=None,
                )
                alternatives.append(
                    value.display_name
                    if primary is None
                    else (
                        f"{value.display_name} "
                        f"({primary.source}:{primary.ref})"
                    )
                )
                represented_names.add(value.display_name)
            evidence.update(value.evidence)
        combined = TopologyConflict(
            key=conflict_key,
            subject="product",
            alternatives=tuple(sorted(set(alternatives))),
            evidence=tuple(
                sorted(
                    evidence,
                    key=lambda item: (item.source, item.ref, item.value),
                )
            ),
        )
        if existing_index is None:
            conflict_indexes[conflict_key] = len(result)
            result.append(combined)
        else:
            result[existing_index] = combined
    return tuple(result)


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
    product_candidates: list[Candidate] = list(repository.product_evidence)
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

    conflicts = list(
        _repository_external_product_conflicts(product_candidates, conflicts)
    )
    merged_product_candidates = _merge_product_candidates(product_candidates)
    for candidate in merged_product_candidates:
        questions.append(_owner_question("product", candidate))
    return TopologyProposal(
        repository_candidate=repository.repository_candidate,
        product_candidates=merged_product_candidates,
        domain_candidates=tuple(domain_candidates),
        conflicts=tuple(sorted(conflicts, key=lambda item: item.key)),
        questions=tuple(sorted(questions, key=lambda item: item.key)),
        repository_product_evidence=repository.product_document_evidence,
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
    *,
    repository_id: str | None = None,
    product_additions: tuple[Candidate, ...] = (),
    conflict_resolutions: tuple[ConflictResolution, ...] = (),
) -> ConfirmedTopology:
    if not isinstance(proposal, TopologyProposal):
        raise TypeError("proposal: expected TopologyProposal")
    confirmed_products = _require_confirmed_values(products, ConfirmedProduct, "products")
    confirmed_domains = _require_confirmed_values(domains, ConfirmedDomain, "domains")
    additions = _require_confirmed_values(
        product_additions,
        Candidate,
        "product_additions",
    )
    _unique_keys(additions, "product addition")
    resolutions = _require_confirmed_values(
        conflict_resolutions,
        ConflictResolution,
        "conflict_resolutions",
    )
    resolution_key_values = [resolution.conflict_key for resolution in resolutions]
    if len(resolution_key_values) != len(set(resolution_key_values)):
        raise ValueError("duplicate conflict resolution key")
    resolution_keys = set(resolution_key_values)
    product_keys = _unique_keys(confirmed_products, "product")
    domain_keys = _unique_keys(confirmed_domains, "domain")
    for product in confirmed_products:
        _reject_duplicate_links(product.domain_keys, "domain")
    for domain in confirmed_domains:
        _reject_duplicate_links(domain.product_keys, "product")
    product_evidence_by_key = {
        candidate.key: candidate for candidate in proposal.product_candidates
    }
    allowed_repository_evidence = set(proposal.repository_product_evidence)
    for addition in additions:
        if not addition.evidence or any(
            evidence not in allowed_repository_evidence
            for evidence in addition.evidence
        ):
            raise ValueError(
                f"product addition {addition.key}: discovered product evidence required"
            )
        if addition.key in product_evidence_by_key:
            raise ValueError(f"product addition already proposed: {addition.key}")
        product_evidence_by_key[addition.key] = addition
    candidate_products = set(product_evidence_by_key)
    candidate_domains = {candidate.key for candidate in proposal.domain_candidates}
    unknown_products = product_keys - candidate_products
    unknown_domains = domain_keys - candidate_domains
    if unknown_products:
        raise ValueError(f"unknown product key: {sorted(unknown_products)[0]}")
    if unknown_domains:
        raise ValueError(f"unknown domain key: {sorted(unknown_domains)[0]}")
    if repository_id is None:
        if proposal.repository_candidate.confidence is Confidence.LOW:
            raise ValueError(
                "low-confidence repository identity requires an explicit owner answer"
            )
        confirmed_repository_id = proposal.repository_candidate.key
    elif not isinstance(repository_id, str) or not repository_id.strip():
        raise ValueError("repository identity answer must be a non-empty string")
    else:
        confirmed_repository_id = repository_id.strip()
    if not confirmed_repository_id.strip():
        raise ValueError("repository ID must not be empty")
    conflict_keys = {conflict.key for conflict in proposal.conflicts}
    conflicts_by_key = {conflict.key: conflict for conflict in proposal.conflicts}
    confirmed_displays = {
        **{f"product.{value.key}": value.display_name for value in confirmed_products},
        **{f"domain.{value.key}": value.display_name for value in confirmed_domains},
    }
    unknown_resolutions = resolution_keys - conflict_keys
    if unknown_resolutions:
        raise ValueError(
            f"unknown conflict resolution: {sorted(unknown_resolutions)[0]}"
        )
    for resolution in resolutions:
        if resolution.selected_alternative not in conflicts_by_key[
            resolution.conflict_key
        ].alternatives:
            raise ValueError(
                f"conflict resolution {resolution.conflict_key}: unknown alternative"
            )
        confirmed_display = confirmed_displays.get(resolution.conflict_key)
        selected_display = resolution.selected_alternative.rsplit(" (", 1)[0]
        if (
            confirmed_display is not None
            and selected_display != confirmed_display
        ):
            raise ValueError(
                f"conflict resolution {resolution.conflict_key}: "
                "selected alternative does not match confirmed identity"
            )
    referenced_conflicts = {
        f"product.{key}" for key in product_keys
    } | {
        f"domain.{key}" for key in domain_keys
    }
    if (conflict_keys & referenced_conflicts) - resolution_keys:
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
        repository_id=confirmed_repository_id,
        products=tuple(sorted(confirmed_products, key=lambda item: item.key)),
        domains=tuple(sorted(confirmed_domains, key=lambda item: item.key)),
        repository_evidence=(
            proposal.repository_candidate.evidence
            + (
                (Evidence("owner", "repository.id", confirmed_repository_id),)
                if repository_id is not None
                else ()
            )
        ),
        product_evidence=tuple(
            product_evidence_by_key[key]
            for key in sorted(product_keys)
        ),
        conflict_resolutions=tuple(
            sorted(resolutions, key=lambda value: value.conflict_key)
        ),
    )

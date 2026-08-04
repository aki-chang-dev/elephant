from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import hmac
import json
from typing import Any

from elephant_runtime.workspace_core import DiagnosticCode, ProviderKind, preflight_provider
from elephant_runtime.workspace_core.config import PROVIDER_CHOICES

from .models import (
    ConfirmedTopology,
    DesiredRelationship,
    Evidence,
    ExternalDiscovery,
    FingerprintDomain,
    FrozenList,
    FrozenMap,
    LocalDocumentSlot,
    LocalDocumentTemplate,
    OperationKind,
    ProviderSemantics,
    SETUP_MANIFEST_SCHEMA,
    SetupDiagnostic,
    SetupManifest,
    SetupOperation,
    TopologyConflict,
    semantics_fingerprint,
)


_LOGICAL_PROVIDERS = (
    ("story_store", ProviderKind.STORY),
    ("product_knowledge_store", ProviderKind.PRODUCT_KNOWLEDGE),
    ("product_contract_store", ProviderKind.PRODUCT_CONTRACT),
    ("delivery_workspace", ProviderKind.DELIVERY_WORKSPACE),
)
_LOGICAL_NAMES = frozenset(name for name, _ in _LOGICAL_PROVIDERS)
_LOGICAL_NAME_BY_KIND = {
    provider_kind: logical_name
    for logical_name, provider_kind in _LOGICAL_PROVIDERS
}
_PHASE_ORDER = {
    OperationKind.REUSE: 0,
    OperationKind.CREATE: 1,
    OperationKind.MANUAL: 2,
    OperationKind.VERIFY: 3,
    OperationKind.ROUND_TRIP: 4,
    OperationKind.WRITE_LOCAL: 5,
}


@dataclass(frozen=True)
class CapabilityLayers:
    platform_supported: frozenset[str]
    exposed: frozenset[str]
    permitted: frozenset[str]
    configured: frozenset[str]

    def __post_init__(self) -> None:
        for field_name in ("platform_supported", "exposed", "permitted", "configured"):
            value = getattr(self, field_name)
            if not isinstance(value, frozenset) or not all(isinstance(capability, str) for capability in value):
                raise ValueError(f"capability layers: {field_name} must be a frozenset of strings")


@dataclass(frozen=True)
class DesiredStructure:
    provider: str
    capability: str
    logical_key: str
    desired_fingerprint: str
    administrative: bool
    runtime_required: bool
    logical_provider: ProviderKind | None = None
    semantics: ProviderSemantics | None = None
    manual_instructions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("provider", "capability", "logical_key", "desired_fingerprint"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"desired structure: {field_name} must be a non-empty string")
        for field_name in ("administrative", "runtime_required"):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"desired structure: {field_name} must be a bool")
        if not isinstance(self.logical_provider, ProviderKind):
            raise TypeError("desired structure: logical_provider must be ProviderKind")
        if not isinstance(self.semantics, ProviderSemantics):
            raise TypeError("desired structure: semantics must be ProviderSemantics")
        if self.desired_fingerprint != semantics_fingerprint(self.semantics):
            raise ValueError(
                "desired structure: fingerprint must match typed provider semantics"
            )
        if not isinstance(self.manual_instructions, tuple) or not all(
            isinstance(instruction, str) and instruction.strip()
            for instruction in self.manual_instructions
        ):
            raise ValueError(
                "desired structure: manual_instructions must be nonblank strings"
            )


def _pair_mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, tuple):
        raise ValueError(f"{name}: expected tuple key/value pairs")
    result: dict[str, object] = {}
    for pair in value:
        if not isinstance(pair, tuple) or len(pair) != 2 or not isinstance(pair[0], str):
            raise ValueError(f"{name}: expected tuple key/value pairs")
        if pair[0] in result:
            raise ValueError(f"{name}: duplicate key {pair[0]}")
        result[pair[0]] = pair[1]
    return result


def _sorted_pairs(value: dict[str, object]) -> tuple[tuple[str, object], ...]:
    return tuple((key, value[key]) for key in sorted(value))


def _validate_provider_selection(value: object) -> dict[str, str]:
    selected = _pair_mapping(value, "provider_selection")
    if set(selected) != _LOGICAL_NAMES:
        missing = sorted(_LOGICAL_NAMES - set(selected))
        unknown = sorted(set(selected) - _LOGICAL_NAMES)
        detail = f"missing {missing[0]}" if missing else f"unknown {unknown[0]}"
        raise ValueError(f"provider_selection: expected all logical providers ({detail})")
    if not all(isinstance(provider, str) and provider.strip() for provider in selected.values()):
        raise ValueError("provider_selection: physical providers must be non-empty strings")
    normalized = {logical: physical.strip() for logical, physical in selected.items()}
    for logical, physical in normalized.items():
        if physical not in PROVIDER_CHOICES[logical]:
            choices = ", ".join(sorted(PROVIDER_CHOICES[logical]))
            raise ValueError(f"provider_selection.{logical}: expected one of {choices}")
    return normalized


def _validate_layers(value: object) -> dict[str, CapabilityLayers]:
    layers = _pair_mapping(value, "capability_layers")
    if set(layers) != _LOGICAL_NAMES:
        missing = sorted(_LOGICAL_NAMES - set(layers))
        unknown = sorted(set(layers) - _LOGICAL_NAMES)
        detail = f"missing {missing[0]}" if missing else f"unknown {unknown[0]}"
        raise ValueError(f"capability_layers: expected all logical providers ({detail})")
    if not all(isinstance(layer, CapabilityLayers) for layer in layers.values()):
        raise ValueError("capability_layers: expected CapabilityLayers values")
    return layers  # type: ignore[return-value]


def _operation(
    provider: str,
    capability: str,
    target_key: str,
    desired_fingerprint: str,
    kind: OperationKind,
    runtime_required: bool,
    payload: tuple[tuple[str, object], ...] = (),
    *,
    expected_prior_fingerprint: str | None = None,
    logical_provider: ProviderKind | None = None,
    semantics: ProviderSemantics | None = None,
    desired_fingerprint_domain: FingerprintDomain = (
        FingerprintDomain.PROVIDER_SEMANTICS
    ),
    expected_byte_fingerprint: str | None = None,
    manual_instructions: tuple[str, ...] = (),
    relationships: tuple[DesiredRelationship, ...] = (),
    local_slots: tuple[LocalDocumentSlot, ...] = (),
) -> SetupOperation:
    return SetupOperation(
        operation_id=f"{provider}.{target_key}.{kind.value}",
        provider=provider,
        capability=capability,
        target_key=target_key,
        desired_fingerprint=desired_fingerprint,
        payload=payload,
        kind=kind,
        runtime_required=runtime_required,
        expected_prior_fingerprint=expected_prior_fingerprint,
        logical_provider=logical_provider,
        semantics=semantics,
        desired_fingerprint_domain=desired_fingerprint_domain,
        expected_byte_fingerprint=expected_byte_fingerprint,
        manual_instructions=manual_instructions,
        relationships=relationships,
        local_slots=local_slots,
    )


def _conflict(
    key: str,
    alternatives: tuple[str, ...],
    evidence: tuple[Evidence, ...],
) -> TopologyConflict:
    return TopologyConflict(
        key=f"setup_structure.{key}",
        subject="setup_structure",
        alternatives=tuple(sorted(alternatives)),
        evidence=tuple(sorted(evidence, key=lambda item: (item.source, item.ref, item.value))),
    )


def _canonical_value(value: object) -> Any:
    if isinstance(value, Enum):
        return _canonical_value(value.value)
    if isinstance(value, FrozenMap):
        return {
            key: _canonical_value(item_value)
            for key, item_value in sorted(value.entries)
        }
    if isinstance(value, FrozenList):
        return [_canonical_value(item) for item in value.values]
    if isinstance(value, tuple):
        if all(isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) for item in value):
            return {key: _canonical_value(item_value) for key, item_value in sorted(value)}
        return [_canonical_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError(f"local payload: unsupported immutable value {type(value).__name__}")


def _payload_fingerprint(value: object) -> str:
    body = json.dumps(_canonical_value(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _require_local_mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ValueError(f"{field}: expected canonical mapping")
    return value


def _validate_local_projection(
    topology: ConfirmedTopology,
    selection: dict[str, str],
    workspace: dict[str, object],
    profiles: dict[str, dict[str, object]],
) -> None:
    repository = _require_local_mapping(
        workspace.get("repository"), "workspace repository"
    )
    if repository.get("id") != topology.repository_id:
        raise ValueError(
            "workspace repository does not match confirmed topology"
        )
    if workspace.get("providers") != selection:
        raise ValueError(
            "workspace providers do not match approved provider selection"
        )
    if workspace.get("engineering_profile") != (
        ".agents/elephant/profiles/engineering.yaml"
    ):
        raise ValueError("workspace engineering profile is not canonical")

    product_values = _require_local_mapping(
        workspace.get("products"), "workspace products"
    )
    expected_products = {product.key: product for product in topology.products}
    if set(product_values) != set(expected_products):
        raise ValueError("workspace products do not match confirmed topology")
    for key, product in expected_products.items():
        value = _require_local_mapping(
            product_values[key], f"workspace product {key}"
        )
        if value.get("profile") != f".agents/elephant/profiles/{key}.yaml":
            raise ValueError(f"workspace product {key} profile is not canonical")
        if value.get("primary_domains") != list(product.domain_keys):
            raise ValueError(
                f"workspace product {key} domains do not match confirmed topology"
            )
        for logical_provider, field, kind in (
            ("story_store", "story_ref", "story"),
            ("product_knowledge_store", "knowledge_ref", "knowledge"),
        ):
            reference = value.get(field)
            provider = selection[logical_provider]
            if provider == "git" and reference != f"git:{kind}:{key}":
                raise ValueError(
                    f"workspace product {key} {field} is not canonical"
                )
            if provider != "git" and (
                not isinstance(reference, str) or not reference.strip()
            ):
                raise ValueError(
                    f"workspace product {key} {field} is missing"
                )

    domain_values = _require_local_mapping(
        workspace.get("domains"), "workspace domains"
    )
    expected_domains = {domain.key: domain for domain in topology.domains}
    if set(domain_values) != set(expected_domains):
        raise ValueError("workspace domains do not match confirmed topology")
    for key, domain in expected_domains.items():
        value = _require_local_mapping(
            domain_values[key], f"workspace domain {key}"
        )
        expected = {
            "scopes": list(domain.scopes),
            "instruction_paths": list(domain.instruction_paths),
            "verification": list(domain.verification),
            "products": list(domain.product_keys),
        }
        if value != expected:
            raise ValueError(
                f"workspace domain {key} does not match confirmed topology"
            )

    expected_profile_keys = set(expected_products) | {"engineering"}
    if set(profiles) != expected_profile_keys:
        raise ValueError("local profiles do not match confirmed topology")
    for key in expected_products:
        profile = profiles[key]
        if profile.get("kind") != "product" or profile.get("product") != key:
            raise ValueError(
                f"product profile {key} does not match confirmed topology"
            )
    engineering = profiles["engineering"]
    if (
        engineering.get("kind") != "engineering"
        or engineering.get("product") is not None
        or engineering.get("behavior_preservation_required") is not True
    ):
        raise ValueError("engineering profile is not canonical")


def _canonical_local_documents(
    topology: ConfirmedTopology,
    selection: dict[str, str],
    registry: tuple[tuple[str, object], ...],
    profiles: dict[str, object],
) -> dict[str, str]:
    from .files import WORKSPACE_PATH, _validate_local_body, render_yaml

    workspace = _require_local_mapping(
        _canonical_value(registry), "registry"
    )
    profile_documents = {
        key: _require_local_mapping(
            _canonical_value(value), f"profiles.{key}"
        )
        for key, value in profiles.items()
    }
    _validate_local_projection(
        topology,
        selection,
        workspace,
        profile_documents,
    )
    documents = {WORKSPACE_PATH: render_yaml(workspace)}
    documents.update(
        {
            f".agents/elephant/profiles/{key}.yaml": render_yaml(value)
            for key, value in profile_documents.items()
        }
    )
    for path, body in documents.items():
        _validate_local_body(path, body)
    return documents


def _replace_local_placeholders(
    value: object,
    replacements: dict[str, str],
) -> object:
    if isinstance(value, dict):
        return {
            key: _replace_local_placeholders(item, replacements)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _replace_local_placeholders(item, replacements)
            for item in value
        ]
    if isinstance(value, str) and value in replacements:
        return replacements[value]
    return value


def _documents_match_observed_state(
    documents: dict[str, str | LocalDocumentTemplate],
    observed_fingerprints: dict[str, object],
    external_by_key: dict[tuple[str, str], list[object]],
    operations: list[SetupOperation],
) -> dict[str, str] | None:
    if not observed_fingerprints or any(
        operation.kind in {OperationKind.CREATE, OperationKind.MANUAL}
        for operation in operations
    ):
        return None
    from .files import load_rendered_yaml, render_yaml

    readable_sources = {
        (operation.provider, operation.target_key)
        for operation in operations
        if operation.kind in {OperationKind.REUSE, OperationKind.VERIFY}
    }
    materialized_documents: dict[str, str] = {}
    for path, value in documents.items():
        body = value.body if isinstance(value, LocalDocumentTemplate) else value
        if isinstance(value, LocalDocumentTemplate):
            replacements: dict[str, str] = {}
            for slot in value.slots:
                key = (slot.provider, slot.stable_key)
                records = external_by_key.get(key, ())
                if key not in readable_sources or len(records) != 1:
                    return None
                external_id = getattr(records[0], "external_id", None)
                if not isinstance(external_id, str) or not external_id.strip():
                    return None
                replacements[slot.placeholder] = external_id
            body = render_yaml(
                _replace_local_placeholders(
                    load_rendered_yaml(body),
                    replacements,
                )
            )
        observed = observed_fingerprints.get(path)
        if not isinstance(observed, str) or not hmac.compare_digest(
            observed,
            hashlib.sha256(body.encode("utf-8")).hexdigest(),
        ):
            return None
        materialized_documents[path] = body
    return materialized_documents


_CAPABILITY_LAYER_PRECEDENCE = (
    ("platform_supported", DiagnosticCode.PLATFORM_UNSUPPORTED),
    ("exposed", DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
    ("permitted", DiagnosticCode.PERMISSION_MISSING),
    ("configured", DiagnosticCode.CONFIGURATION_MISSING),
)
_DIAGNOSTIC_PRIORITY = {
    code: index for index, (_, code) in enumerate(_CAPABILITY_LAYER_PRECEDENCE)
}


def _missing_capability_layers(
    provider: str,
    capability: str,
    layers: dict[str, CapabilityLayers],
    selection: dict[str, str],
    logical_provider: ProviderKind | None,
) -> tuple[tuple[ProviderKind, DiagnosticCode], ...]:
    missing: list[tuple[ProviderKind, DiagnosticCode]] = []
    for logical, provider_kind in _LOGICAL_PROVIDERS:
        if logical_provider is not None and provider_kind is not logical_provider:
            continue
        if selection[logical] != provider:
            continue
        layer = layers[logical]
        for field_name, code in _CAPABILITY_LAYER_PRECEDENCE:
            if capability not in getattr(layer, field_name):
                missing.append((provider_kind, code))
                break
    return tuple(missing)


def build_setup_manifest(
    topology: ConfirmedTopology,
    provider_selection: tuple[tuple[str, str], ...],
    desired_structures: tuple[DesiredStructure, ...],
    external: ExternalDiscovery,
    capability_layers: tuple[tuple[str, CapabilityLayers], ...],
    registry: tuple[tuple[str, object], ...],
    profiles: tuple[tuple[str, object], ...],
    *,
    expected_local_container_fingerprint: str,
    expected_prior_fingerprints: tuple[tuple[str, str], ...] = (),
    observed_local_fingerprints: tuple[
        tuple[str, str | None], ...
    ] = (),
    rendered_local_documents: tuple[
        tuple[str, str | LocalDocumentTemplate], ...
    ] = (),
) -> SetupManifest:
    """Create a deterministic, read-only setup plan from confirmed evidence."""
    if not isinstance(topology, ConfirmedTopology):
        raise TypeError("topology: expected ConfirmedTopology")
    if not isinstance(external, ExternalDiscovery):
        raise TypeError("external: expected ExternalDiscovery")
    if not isinstance(desired_structures, tuple) or not all(isinstance(item, DesiredStructure) for item in desired_structures):
        raise ValueError("desired_structures: expected DesiredStructure tuple")
    selection = _validate_provider_selection(provider_selection)
    layers = _validate_layers(capability_layers)
    _pair_mapping(registry, "registry")
    profile_documents = _pair_mapping(profiles, "profiles")
    expected_priors = _pair_mapping(
        expected_prior_fingerprints, "expected prior fingerprints"
    )
    observed_local = _pair_mapping(
        observed_local_fingerprints,
        "observed local fingerprints",
    )
    local_paths = {".agents/elephant/workspace.yaml"} | {
        f".agents/elephant/profiles/{key}.yaml" for key in profile_documents
    }
    rendered_documents = _pair_mapping(
        rendered_local_documents, "rendered local documents"
    )
    if rendered_documents and set(rendered_documents) != local_paths:
        raise ValueError("rendered local documents: expected exact setup output paths")
    if not all(
        isinstance(body, (str, LocalDocumentTemplate))
        for body in rendered_documents.values()
    ):
        raise ValueError(
            "rendered local documents: expected canonical strings or typed templates"
        )
    canonical_documents = _canonical_local_documents(
        topology,
        selection,
        registry,
        profile_documents,
    )
    if rendered_documents:
        for path, value in rendered_documents.items():
            body = value.body if isinstance(value, LocalDocumentTemplate) else value
            if body != canonical_documents[path]:
                raise ValueError(
                    f"canonical local document mismatch for {path}"
                )
        approved_documents: dict[str, str | LocalDocumentTemplate] = (
            rendered_documents
        )
    else:
        approved_documents = canonical_documents
    unknown_prior_paths = set(expected_priors) - local_paths
    if unknown_prior_paths:
        raise ValueError(
            "expected prior fingerprint has unknown setup output path "
            f"{sorted(unknown_prior_paths)[0]}"
        )
    if observed_local and set(observed_local) != local_paths:
        raise ValueError(
            "observed local fingerprints: expected exact setup output paths"
        )
    for path, fingerprint in observed_local.items():
        if fingerprint is not None and (
            not isinstance(fingerprint, str)
            or len(fingerprint) != 64
            or any(
                character not in "0123456789abcdef"
                for character in fingerprint
            )
        ):
            raise ValueError(
                f"observed local fingerprint for {path} must be lowercase SHA-256 or null"
            )
    if observed_local and any(
        observed_local.get(path) != fingerprint
        for path, fingerprint in expected_priors.items()
    ):
        raise ValueError(
            "expected prior fingerprints must match observed local fingerprints"
        )

    diagnostics: list[SetupDiagnostic] = []
    for logical, provider_kind in _LOGICAL_PROVIDERS:
        layer = layers[logical]
        preflight = preflight_provider(
            provider_kind,
            platform_supported=layer.platform_supported,
            exposed=layer.exposed,
            permitted=layer.permitted,
            configured=layer.configured,
        )
        diagnostics.extend(
            SetupDiagnostic(
                logical_provider=provider_kind,
                physical_provider=selection[logical],
                capability=diagnostic.capability,
                code=diagnostic.code,
                blocking=True,
            )
            for diagnostic in preflight.diagnostics
        )

    selected_physical = frozenset(selection.values())
    if any(structure.provider not in selected_physical for structure in desired_structures):
        provider = sorted({structure.provider for structure in desired_structures} - selected_physical)[0]
        raise ValueError(f"desired structure: provider {provider} is not selected")
    for structure in desired_structures:
        logical_name = _LOGICAL_NAME_BY_KIND[structure.logical_provider]
        selected_provider = selection[logical_name]
        if structure.provider != selected_provider:
            raise ValueError(
                "desired structure: logical provider "
                f"{structure.logical_provider.value} requires selected physical "
                f"provider {selected_provider}"
            )

    desired_by_key: dict[tuple[str, str], list[DesiredStructure]] = {}
    for structure in desired_structures:
        desired_by_key.setdefault((structure.provider, structure.logical_key), []).append(structure)
    external_by_key: dict[tuple[str, str], list[object]] = {}
    for record in external.objects:
        if record.kind == "setup_structure":
            external_by_key.setdefault((record.provider, record.key), []).append(record)

    conflicts: list[TopologyConflict] = []
    operations: list[SetupOperation] = []
    for (provider, logical_key), structures in sorted(desired_by_key.items()):
        if len(structures) != 1:
            conflicts.append(_conflict(
                logical_key,
                tuple(f"{value.capability} ({value.desired_fingerprint})" for value in structures),
                tuple(Evidence("desired", value.logical_key, value.desired_fingerprint) for value in structures),
            ))
            continue
        desired = structures[0]
        matches = tuple(sorted(external_by_key.get((provider, logical_key), ()), key=lambda record: record.external_id))
        if len(matches) > 1:
            conflicts.append(_conflict(
                logical_key,
                tuple(f"{record.external_id} ({record.fingerprint})" for record in matches),
                tuple(Evidence(record.provider, record.external_id, record.fingerprint) for record in matches),
            ))
            continue

        if matches and matches[0].fingerprint != desired.desired_fingerprint:
            existing = matches[0]
            conflicts.append(_conflict(
                logical_key,
                (f"desired ({desired.desired_fingerprint})", f"{existing.external_id} ({existing.fingerprint})"),
                (Evidence("desired", logical_key, desired.desired_fingerprint), Evidence(existing.provider, existing.external_id, existing.fingerprint)),
            ))
            continue

        if matches:
            existing = matches[0]
            payload = (("external_id", existing.external_id), ("read_back_required", True))
            for kind in (OperationKind.REUSE, OperationKind.VERIFY):
                operations.append(_operation(
                    provider,
                    desired.capability,
                    logical_key,
                    desired.desired_fingerprint,
                    kind,
                    desired.runtime_required,
                    payload,
                    logical_provider=desired.logical_provider,
                    semantics=desired.semantics,
                ))
            continue

        missing_layers = _missing_capability_layers(
            provider,
            desired.capability,
            layers,
            selection,
            desired.logical_provider,
        )
        if desired.runtime_required:
            diagnostics.extend(
                SetupDiagnostic(
                    logical_provider=logical_provider,
                    physical_provider=provider,
                    capability=desired.capability,
                    code=code,
                    blocking=True,
                )
                for logical_provider, code in missing_layers
            )
            if missing_layers:
                continue
        if desired.administrative:
            diagnostics.extend(
                SetupDiagnostic(
                    logical_provider=logical_provider,
                    physical_provider=provider,
                    capability=desired.capability,
                    code=code,
                    blocking=False,
                )
                for logical_provider, code in missing_layers
            )
        administrative_code = min(
            (
                code
                for _, code in missing_layers
                if code is not DiagnosticCode.CONFIGURATION_MISSING
            ),
            key=_DIAGNOSTIC_PRIORITY.__getitem__,
            default=None,
        ) if desired.administrative else None
        if administrative_code is not None:
            if not desired.manual_instructions:
                raise ValueError(
                    f"desired structure {logical_key}: exact manual instructions required"
                )
            operations.append(_operation(
                provider, desired.capability, logical_key, desired.desired_fingerprint,
                OperationKind.MANUAL, desired.runtime_required,
                (("diagnostic_code", administrative_code.value), ("read_back_required", True)),
                logical_provider=desired.logical_provider,
                semantics=desired.semantics,
                manual_instructions=desired.manual_instructions,
            ))
            continue
        if desired.runtime_required and missing_layers:
            continue
        if not matches:
            operations.append(_operation(
                provider, desired.capability, logical_key, desired.desired_fingerprint,
                OperationKind.CREATE, desired.runtime_required,
                (("administrative", desired.administrative),),
                logical_provider=desired.logical_provider,
                semantics=desired.semantics,
            ))
            continue

    unchanged_documents = _documents_match_observed_state(
        approved_documents,
        observed_local,
        external_by_key,
        operations,
    )
    unchanged_rerun = unchanged_documents is not None
    for provider in (
        () if unchanged_rerun else sorted(selected_physical - {"git"})
    ):
        round_trip_semantics = ProviderSemantics(
            resource_type="elephant_setup_round_trip",
            fields=FrozenMap((("provider", provider),)),
        )
        operations.append(_operation(
            provider, "round_trip", f"setup.round_trip.{provider}",
            semantics_fingerprint(round_trip_semantics), OperationKind.ROUND_TRIP, False,
            (("disposable", True), ("read_back_required", True)),
            semantics=round_trip_semantics,
            relationships=(
                DesiredRelationship(
                    relationship_type="elephant_setup_binding",
                    fields=FrozenMap((("purpose", "capability_probe"),)),
                ),
            ),
        ))

    slot_source_priority = {
        OperationKind.VERIFY: 0,
        OperationKind.CREATE: 1,
        OperationKind.MANUAL: 2,
        OperationKind.REUSE: 3,
    }

    def approved_local_value(path: str, value: object) -> tuple[str, tuple[LocalDocumentSlot, ...]]:
        if isinstance(value, LocalDocumentTemplate):
            body = value.body
            slots: list[LocalDocumentSlot] = []
            for slot in value.slots:
                candidates = tuple(
                    operation
                    for operation in operations
                    if operation.provider == slot.provider
                    and operation.target_key == slot.stable_key
                    and operation.kind in slot_source_priority
                )
                if slot.source_operation_id:
                    candidates = tuple(
                        operation
                        for operation in candidates
                        if operation.operation_id == slot.source_operation_id
                    )
                if not candidates:
                    raise ValueError(
                        f"local document slot {slot.slot_id}: no approved stable-key operation"
                    )
                source = min(
                    candidates,
                    key=lambda operation: slot_source_priority[operation.kind],
                )
                slots.append(
                    replace(slot, source_operation_id=source.operation_id)
                )
            bound_slots = tuple(sorted(slots, key=lambda item: item.slot_id))
        elif isinstance(value, str):
            body = value
            bound_slots = ()
        else:
            raise ValueError(f"rendered local document {path}: unsupported value")
        from .files import _validate_local_body

        _validate_local_body(path, body)
        return body, bound_slots

    workspace_path = ".agents/elephant/workspace.yaml"
    workspace_document, workspace_slots = approved_local_value(
        workspace_path,
        approved_documents[workspace_path],
    )
    workspace_payload = (("document", workspace_document),)
    workspace_expected_bytes = None
    if unchanged_rerun:
        assert unchanged_documents is not None
        workspace_materialized = unchanged_documents[workspace_path]
        workspace_payload = (
            ("document", workspace_materialized),
            ("template_document", workspace_document),
            ("unchanged_rerun", True),
        )
        workspace_expected_bytes = hashlib.sha256(
            workspace_materialized.encode("utf-8")
        ).hexdigest()
    operations.append(_operation(
        "local", "write_registry", workspace_path, _payload_fingerprint(workspace_document),
        OperationKind.WRITE_LOCAL, False, workspace_payload,
        expected_prior_fingerprint=expected_priors.get(
            workspace_path
        ),
        desired_fingerprint_domain=FingerprintDomain.LOCAL_TEMPLATE,
        expected_byte_fingerprint=workspace_expected_bytes,
        local_slots=workspace_slots,
    ))
    for key, profile in sorted(profile_documents.items()):
        path = f".agents/elephant/profiles/{key}.yaml"
        profile_document, profile_slots = approved_local_value(
            path,
            approved_documents[path],
        )
        profile_payload = (("document", profile_document),)
        profile_expected_bytes = None
        if unchanged_rerun:
            assert unchanged_documents is not None
            profile_materialized = unchanged_documents[path]
            profile_payload = (
                ("document", profile_materialized),
                ("template_document", profile_document),
                ("unchanged_rerun", True),
            )
            profile_expected_bytes = hashlib.sha256(
                profile_materialized.encode("utf-8")
            ).hexdigest()
        operations.append(_operation(
            "local", "write_profile", path, _payload_fingerprint(profile_document),
            OperationKind.WRITE_LOCAL, False, profile_payload,
            expected_prior_fingerprint=expected_priors.get(path),
            desired_fingerprint_domain=FingerprintDomain.LOCAL_TEMPLATE,
            expected_byte_fingerprint=profile_expected_bytes,
            local_slots=profile_slots,
        ))

    operations.sort(key=lambda item: (_PHASE_ORDER[item.kind], item.provider, item.capability, item.target_key))
    diagnostics = sorted(
        set(diagnostics),
        key=lambda item: (item.logical_provider.value, item.physical_provider, item.capability, item.code.value),
    )
    conflicts.sort(key=lambda item: (item.key, item.subject, item.alternatives))
    return SetupManifest(
        schema=SETUP_MANIFEST_SCHEMA,
        repository_id=topology.repository_id,
        provider_selection=_sorted_pairs(selection),
        products=tuple(sorted(topology.products, key=lambda product: product.key)),
        domains=tuple(sorted(topology.domains, key=lambda domain: domain.key)),
        operations=tuple(operations),
        diagnostics=tuple(diagnostics),
        conflicts=tuple(conflicts),
        questions=(),
        repository_evidence=topology.repository_evidence,
        product_evidence=topology.product_evidence,
        conflict_resolutions=topology.conflict_resolutions,
        expected_local_container_fingerprint=expected_local_container_fingerprint,
        registry=tuple(sorted(registry)),
        profiles=tuple(sorted(profiles)),
    )

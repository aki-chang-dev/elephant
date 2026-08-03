from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Any

from scripts.workspace_core import DiagnosticCode, ProviderKind, preflight_provider
from scripts.workspace_core.config import PROVIDER_CHOICES

from .models import (
    ConfirmedTopology,
    Evidence,
    ExternalDiscovery,
    OperationKind,
    SETUP_MANIFEST_SCHEMA,
    SetupDiagnostic,
    SetupManifest,
    SetupOperation,
    TopologyConflict,
)


_LOGICAL_PROVIDERS = (
    ("story_store", ProviderKind.STORY),
    ("product_knowledge_store", ProviderKind.PRODUCT_KNOWLEDGE),
    ("product_contract_store", ProviderKind.PRODUCT_CONTRACT),
    ("delivery_workspace", ProviderKind.DELIVERY_WORKSPACE),
)
_LOGICAL_NAMES = frozenset(name for name, _ in _LOGICAL_PROVIDERS)
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

    def __post_init__(self) -> None:
        for field_name in ("provider", "capability", "logical_key", "desired_fingerprint"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"desired structure: {field_name} must be a non-empty string")
        for field_name in ("administrative", "runtime_required"):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"desired structure: {field_name} must be a bool")


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


def _administrative_diagnostic(
    provider: str,
    preflights: dict[str, object],
    selection: dict[str, str],
) -> DiagnosticCode | None:
    codes = []
    for logical, _ in _LOGICAL_PROVIDERS:
        if selection[logical] != provider:
            continue
        preflight = preflights[logical]
        codes.extend(diagnostic.code for diagnostic in preflight.diagnostics)
    return min(codes, key=lambda code: (
        DiagnosticCode.PLATFORM_UNSUPPORTED,
        DiagnosticCode.CONNECTOR_CAPABILITY_MISSING,
        DiagnosticCode.PERMISSION_MISSING,
        DiagnosticCode.CONFIGURATION_MISSING,
    ).index(code), default=None)


def _runtime_is_available(
    desired: DesiredStructure,
    layers: dict[str, CapabilityLayers],
    selection: dict[str, str],
) -> bool:
    selected_layers = [layers[logical] for logical, _ in _LOGICAL_PROVIDERS if selection[logical] == desired.provider]
    return bool(selected_layers) and all(
        desired.capability in layer.platform_supported
        and desired.capability in layer.exposed
        and desired.capability in layer.permitted
        and desired.capability in layer.configured
        for layer in selected_layers
    )


def build_setup_manifest(
    topology: ConfirmedTopology,
    provider_selection: tuple[tuple[str, str], ...],
    desired_structures: tuple[DesiredStructure, ...],
    external: ExternalDiscovery,
    capability_layers: tuple[tuple[str, CapabilityLayers], ...],
    registry: tuple[tuple[str, object], ...],
    profiles: tuple[tuple[str, object], ...],
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
    _pair_mapping(profiles, "profiles")

    preflights = {}
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
        preflights[logical] = preflight
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

        if desired.runtime_required and not _runtime_is_available(desired, layers, selection):
            continue
        administrative_code = _administrative_diagnostic(provider, preflights, selection) if desired.administrative else None
        if administrative_code is not None:
            operations.append(_operation(
                provider, desired.capability, logical_key, desired.desired_fingerprint,
                OperationKind.MANUAL, desired.runtime_required,
                (("diagnostic_code", administrative_code.value), ("read_back_required", True)),
            ))
            continue
        if not matches:
            operations.append(_operation(
                provider, desired.capability, logical_key, desired.desired_fingerprint,
                OperationKind.CREATE, desired.runtime_required,
                (("administrative", desired.administrative),),
            ))
            continue
        existing = matches[0]
        payload = (("external_id", existing.external_id), ("read_back_required", True))
        operations.append(_operation(provider, desired.capability, logical_key, desired.desired_fingerprint, OperationKind.REUSE, desired.runtime_required, payload))
        operations.append(_operation(provider, desired.capability, logical_key, desired.desired_fingerprint, OperationKind.VERIFY, desired.runtime_required, payload))

    for provider in sorted(selected_physical - {"git"}):
        operations.append(_operation(
            provider, "round_trip", f"setup.round_trip.{provider}",
            _payload_fingerprint((("provider", provider),)), OperationKind.ROUND_TRIP, False,
            (("disposable", True), ("read_back_required", True)),
        ))
    operations.append(_operation(
        "local", "write_registry", ".agents/elephant/workspace.yaml", _payload_fingerprint(registry),
        OperationKind.WRITE_LOCAL, False, (("document", registry),),
    ))
    for key, profile in sorted(_pair_mapping(profiles, "profiles").items()):
        operations.append(_operation(
            "local", "write_profile", f".agents/elephant/profiles/{key}.yaml", _payload_fingerprint(profile),
            OperationKind.WRITE_LOCAL, False, (("document", profile),),
        ))

    operations.sort(key=lambda item: (_PHASE_ORDER[item.kind], item.provider, item.capability, item.target_key))
    diagnostics.sort(key=lambda item: (item.logical_provider.value, item.physical_provider, item.capability, item.code.value))
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
        registry=tuple(sorted(registry)),
        profiles=tuple(sorted(profiles)),
    )

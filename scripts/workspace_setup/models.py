from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import hashlib
import hmac
import json
import math
from typing import Any

from scripts.workspace_core import DiagnosticCode, ProviderKind


SETUP_MANIFEST_SCHEMA = "elephant.setup-manifest/v1"


class Confidence(str, Enum):
    CONFIRMED = "confirmed"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OperationKind(str, Enum):
    REUSE = "reuse"
    CREATE = "create"
    MANUAL = "manual"
    VERIFY = "verify"
    ROUND_TRIP = "round_trip"
    WRITE_LOCAL = "write_local"


def _validate_expected_prior_fingerprint(
    kind: OperationKind,
    prior: object,
) -> None:
    if kind is OperationKind.WRITE_LOCAL:
        if prior is not None and (
            not isinstance(prior, str)
            or len(prior) != 64
            or any(character not in "0123456789abcdef" for character in prior)
        ):
            raise ValueError(
                "expected_prior_fingerprint: expected lowercase SHA-256 or null"
            )
    elif prior is not None:
        raise ValueError("expected_prior_fingerprint: allowed only for write_local")


def _validate_local_container_fingerprint(value: object) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(
            "expected_local_container_fingerprint: expected lowercase SHA-256"
        )


def _require_tuple(value: object, field_name: str) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name}: expected tuple")


def _require_tuple_key_value_pairs(value: object, field_name: str) -> None:
    _require_tuple(value, field_name)
    keys: set[str] = set()
    for item in value:
        if not isinstance(item, tuple) or len(item) != 2 or not isinstance(item[0], str):
            raise TypeError(f"{field_name}: expected tuple key/value pairs")
        if item[0] in keys:
            raise TypeError(f"{field_name}: duplicate mapping key {item[0]}")
        keys.add(item[0])


def _require_enum(value: object, enum_type: type[Enum], field_name: str) -> None:
    if not isinstance(value, enum_type):
        raise TypeError(f"{field_name}: expected {enum_type.__name__}")


def _validate_immutable_value(value: object) -> None:
    if isinstance(value, Enum):
        _validate_immutable_value(value.value)
        return
    if is_dataclass(value) and not isinstance(value, type):
        parameters = getattr(type(value), "__dataclass_params__", None)
        if parameters is None or not parameters.frozen:
            raise TypeError("immutable value: expected frozen dataclass")
        for field in fields(value):
            _validate_immutable_value(getattr(value, field.name))
        return
    if isinstance(value, tuple):
        for item in value:
            _validate_immutable_value(item)
        return
    if value is None or isinstance(value, (str, int, bool)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    raise TypeError(f"immutable value: unsupported {type(value).__name__}")


@dataclass(frozen=True)
class Evidence:
    source: str
    ref: str
    value: str

    def __post_init__(self) -> None:
        _validate_immutable_value(self)


@dataclass(frozen=True)
class Candidate:
    key: str
    display_name: str
    evidence: tuple[Evidence, ...]
    confidence: Confidence

    def __post_init__(self) -> None:
        _require_tuple(self.evidence, "evidence")
        _require_enum(self.confidence, Confidence, "confidence")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class TopologyConflict:
    key: str
    subject: str
    alternatives: tuple[str, ...]
    evidence: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.alternatives, "alternatives")
        _require_tuple(self.evidence, "evidence")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class OwnerQuestion:
    key: str
    prompt: str
    evidence: tuple[Evidence, ...]
    confidence: Confidence

    def __post_init__(self) -> None:
        _require_tuple(self.evidence, "evidence")
        _require_enum(self.confidence, Confidence, "confidence")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class ConfirmedProduct:
    key: str
    display_name: str
    domain_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.domain_keys, "domain_keys")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class ConfirmedDomain:
    key: str
    display_name: str
    product_keys: tuple[str, ...]
    scopes: tuple[str, ...]
    instruction_paths: tuple[str, ...]
    verification: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.product_keys, "product_keys")
        _require_tuple(self.scopes, "scopes")
        _require_tuple(self.instruction_paths, "instruction_paths")
        _require_tuple(self.verification, "verification")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class ConfirmedTopology:
    repository_id: str
    products: tuple[ConfirmedProduct, ...]
    domains: tuple[ConfirmedDomain, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.products, "products")
        _require_tuple(self.domains, "domains")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class SetupDiagnostic:
    logical_provider: ProviderKind
    physical_provider: str
    capability: str
    code: DiagnosticCode
    blocking: bool

    def __post_init__(self) -> None:
        _require_enum(self.logical_provider, ProviderKind, "logical_provider")
        _require_enum(self.code, DiagnosticCode, "code")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class SetupOperation:
    operation_id: str
    provider: str
    capability: str
    target_key: str
    desired_fingerprint: str
    payload: tuple[tuple[str, object], ...]
    kind: OperationKind
    runtime_required: bool
    expected_prior_fingerprint: str | None = None

    def __post_init__(self) -> None:
        _require_tuple_key_value_pairs(self.payload, "payload")
        _require_enum(self.kind, OperationKind, "kind")
        _validate_expected_prior_fingerprint(
            self.kind, self.expected_prior_fingerprint
        )
        _validate_immutable_value(self)


@dataclass(frozen=True)
class SetupManifest:
    schema: str
    repository_id: str
    provider_selection: tuple[tuple[str, str], ...]
    products: tuple[ConfirmedProduct, ...]
    domains: tuple[ConfirmedDomain, ...]
    operations: tuple[SetupOperation, ...]
    diagnostics: tuple[SetupDiagnostic, ...]
    conflicts: tuple[TopologyConflict, ...]
    questions: tuple[OwnerQuestion, ...]
    expected_local_container_fingerprint: str
    registry: tuple[tuple[str, object], ...]
    profiles: tuple[tuple[str, object], ...]

    def __post_init__(self) -> None:
        if self.schema != SETUP_MANIFEST_SCHEMA:
            raise ValueError(f"schema: expected {SETUP_MANIFEST_SCHEMA}")
        for field_name in (
            "products",
            "domains",
            "operations",
            "diagnostics",
            "conflicts",
            "questions",
        ):
            _require_tuple(getattr(self, field_name), field_name)
        for field_name in ("provider_selection", "registry", "profiles"):
            _require_tuple_key_value_pairs(getattr(self, field_name), field_name)
        _validate_local_container_fingerprint(
            self.expected_local_container_fingerprint
        )
        _validate_immutable_value(self)


@dataclass(frozen=True)
class ApprovedManifest:
    manifest: SetupManifest
    fingerprint: str

    def __post_init__(self) -> None:
        _validate_immutable_value(self)


@dataclass(frozen=True)
class ApplyEvidence:
    operation_id: str
    target_key: str
    external_id: str
    observed_fingerprint: str
    disposition: str

    def __post_init__(self) -> None:
        _validate_immutable_value(self)


@dataclass(frozen=True)
class ApplyResult:
    ready: bool
    evidence: tuple[ApplyEvidence, ...]
    manual_handoffs: tuple[ApplyEvidence, ...]
    local_writes: tuple[ApplyEvidence, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.evidence, "evidence")
        _require_tuple(self.manual_handoffs, "manual_handoffs")
        _require_tuple(self.local_writes, "local_writes")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class WorkspaceUnit:
    path: str
    package_name: str
    manifest_path: str
    instruction_paths: tuple[str, ...]
    dependency_evidence: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.instruction_paths, "instruction_paths")
        _require_tuple(self.dependency_evidence, "dependency_evidence")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class DependencyEdge:
    source: str
    target: str
    evidence: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.evidence, "evidence")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class RepositoryDiscovery:
    root: str
    repository_candidate: Candidate
    workspace_units: tuple[WorkspaceUnit, ...]
    dependencies: tuple[DependencyEdge, ...]
    instruction_paths: tuple[str, ...]
    product_document_paths: tuple[str, ...]
    deployment_evidence: tuple[str, ...]
    problems: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "workspace_units",
            "dependencies",
            "instruction_paths",
            "product_document_paths",
            "deployment_evidence",
            "problems",
        ):
            _require_tuple(getattr(self, field_name), field_name)
        _validate_immutable_value(self)


@dataclass(frozen=True)
class ExternalObject:
    provider: str
    kind: str
    key: str
    display_name: str
    external_id: str
    fingerprint: str = ""

    def __post_init__(self) -> None:
        for field_name in ("provider", "kind", "key", "display_name", "external_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"external object: {field_name} must be a non-empty string")
        if not isinstance(self.fingerprint, str):
            raise ValueError("external object: fingerprint must be a string")
        if self.kind == "setup_structure" and not self.fingerprint.strip():
            raise ValueError("external object: setup_structure fingerprint must be a non-empty string")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class ExternalDiscovery:
    objects: tuple[ExternalObject, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.objects, "objects")
        if not all(isinstance(value, ExternalObject) for value in self.objects):
            raise TypeError("objects: expected ExternalObject values")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class TopologyProposal:
    repository_candidate: Candidate
    product_candidates: tuple[Candidate, ...]
    domain_candidates: tuple[Candidate, ...]
    conflicts: tuple[TopologyConflict, ...]
    questions: tuple[OwnerQuestion, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "product_candidates",
            "domain_candidates",
            "conflicts",
            "questions",
        ):
            _require_tuple(getattr(self, field_name), field_name)
        _validate_immutable_value(self)


def _validate_manifest(manifest: SetupManifest) -> None:
    if manifest.schema != SETUP_MANIFEST_SCHEMA:
        raise ValueError(f"schema: expected {SETUP_MANIFEST_SCHEMA}")
    _require_tuple_key_value_pairs(manifest.provider_selection, "provider_selection")
    _require_tuple_key_value_pairs(manifest.registry, "registry")
    _require_tuple_key_value_pairs(manifest.profiles, "profiles")
    _validate_local_container_fingerprint(
        manifest.expected_local_container_fingerprint
    )
    for field_name, item_type in (
        ("products", ConfirmedProduct),
        ("domains", ConfirmedDomain),
        ("operations", SetupOperation),
        ("diagnostics", SetupDiagnostic),
        ("conflicts", TopologyConflict),
        ("questions", OwnerQuestion),
    ):
        values = getattr(manifest, field_name)
        _require_tuple(values, field_name)
        if not all(isinstance(value, item_type) for value in values):
            raise TypeError(f"{field_name}: expected {item_type.__name__} values")
    for operation in manifest.operations:
        _require_tuple_key_value_pairs(operation.payload, "payload")
        _require_enum(operation.kind, OperationKind, "kind")
        _validate_expected_prior_fingerprint(
            operation.kind, operation.expected_prior_fingerprint
        )
    for diagnostic in manifest.diagnostics:
        _require_enum(diagnostic.logical_provider, ProviderKind, "logical_provider")
        _require_enum(diagnostic.code, DiagnosticCode, "code")
    for question in manifest.questions:
        _require_enum(question.confidence, Confidence, "confidence")
    _validate_immutable_value(manifest)


def _canonicalize(value: object) -> Any:
    if isinstance(value, Enum):
        return _canonicalize(value.value)
    if is_dataclass(value) and not isinstance(value, type):
        _validate_immutable_value(value)
        return _canonicalize(
            tuple((field.name, getattr(value, field.name)) for field in fields(value))
        )
    if isinstance(value, tuple):
        if value and all(
            isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str)
            for item in value
        ):
            mapping: dict[str, Any] = {}
            for key, item_value in value:
                if key in mapping:
                    raise TypeError(f"duplicate canonical mapping key: {key}")
                mapping[key] = _canonicalize(item_value)
            return {key: mapping[key] for key in sorted(mapping)}
        return [_canonicalize(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def manifest_fingerprint(manifest: SetupManifest) -> str:
    if not isinstance(manifest, SetupManifest):
        raise TypeError("manifest: expected SetupManifest")
    _validate_manifest(manifest)
    canonical_json = json.dumps(
        _canonicalize(manifest),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def approve_manifest(manifest: SetupManifest, supplied_fingerprint: str) -> ApprovedManifest:
    expected_fingerprint = manifest_fingerprint(manifest)
    if not isinstance(supplied_fingerprint, str) or not hmac.compare_digest(
        expected_fingerprint, supplied_fingerprint
    ):
        raise ValueError("approval fingerprint does not match manifest")
    return ApprovedManifest(manifest=manifest, fingerprint=expected_fingerprint)

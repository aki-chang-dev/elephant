from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import hashlib
import hmac
import json
import math
from typing import Any

from elephant_runtime.workspace_core import DiagnosticCode, ProviderKind


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


class FingerprintDomain(str, Enum):
    PROVIDER_SEMANTICS = "provider_semantics"
    RELATIONSHIP_SEMANTICS = "relationship_semantics"
    LOCAL_TEMPLATE = "local_template"
    LOCAL_BYTES = "local_bytes"
    LOCAL_CONTAINER = "local_container"


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
class FrozenMap:
    """An explicit immutable mapping used at fingerprinted value boundaries."""

    entries: tuple[tuple[str, object], ...]

    def __post_init__(self) -> None:
        _require_tuple_key_value_pairs(self.entries, "entries")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class FrozenList:
    """An explicit immutable sequence, distinct from an empty mapping."""

    values: tuple[object, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.values, "values")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class ProviderSemantics:
    """Canonical provider-neutral desired or observed structure semantics."""

    resource_type: str
    fields: FrozenMap

    def __post_init__(self) -> None:
        if not isinstance(self.resource_type, str) or not self.resource_type.strip():
            raise ValueError("provider semantics: resource_type must be nonblank")
        if not isinstance(self.fields, FrozenMap):
            raise TypeError("provider semantics: fields must be FrozenMap")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class DesiredRelationship:
    relationship_type: str
    fields: FrozenMap

    def __post_init__(self) -> None:
        if not isinstance(self.relationship_type, str) or not self.relationship_type.strip():
            raise ValueError("relationship semantics: relationship_type must be nonblank")
        if not isinstance(self.fields, FrozenMap):
            raise TypeError("relationship semantics: fields must be FrozenMap")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class ObservedRelationship:
    stable_key: str
    relationship_id: str
    source_external_id: str
    target_external_id: str
    semantics: DesiredRelationship

    def __post_init__(self) -> None:
        for field_name in (
            "stable_key",
            "relationship_id",
            "source_external_id",
            "target_external_id",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"observed relationship: {field_name} must be nonblank")
        if not isinstance(self.semantics, DesiredRelationship):
            raise TypeError("observed relationship: semantics must be DesiredRelationship")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class LocalDocumentSlot:
    slot_id: str
    provider: str
    stable_key: str
    source_operation_id: str = ""

    def __post_init__(self) -> None:
        for field_name in ("slot_id", "provider", "stable_key"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"local document slot: {field_name} must be nonblank")
        if not isinstance(self.source_operation_id, str):
            raise TypeError("local document slot: source_operation_id must be a string")
        _validate_immutable_value(self)

    @property
    def placeholder(self) -> str:
        authority = "\0".join((self.slot_id, self.provider, self.stable_key))
        digest = hashlib.sha256(authority.encode("utf-8")).hexdigest()
        return f"urn:elephant:setup-slot:{digest}"


@dataclass(frozen=True)
class LocalDocumentTemplate:
    body: str
    slots: tuple[LocalDocumentSlot, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.body, str):
            raise TypeError("local document template: body must be a string")
        _require_tuple(self.slots, "slots")
        if not all(isinstance(slot, LocalDocumentSlot) for slot in self.slots):
            raise TypeError("local document template: expected LocalDocumentSlot values")
        _validate_immutable_value(self)


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
class ConflictResolution:
    conflict_key: str
    selected_alternative: str
    rationale: str

    def __post_init__(self) -> None:
        for field_name in ("conflict_key", "selected_alternative", "rationale"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"conflict resolution: {field_name} must be nonblank")
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
    repository_evidence: tuple[Evidence, ...] = ()
    product_evidence: tuple[Candidate, ...] = ()
    conflict_resolutions: tuple[ConflictResolution, ...] = ()

    def __post_init__(self) -> None:
        _require_tuple(self.products, "products")
        _require_tuple(self.domains, "domains")
        _require_tuple(self.repository_evidence, "repository_evidence")
        _require_tuple(self.product_evidence, "product_evidence")
        _require_tuple(self.conflict_resolutions, "conflict_resolutions")
        if not all(isinstance(value, Candidate) for value in self.product_evidence):
            raise TypeError("product_evidence: expected Candidate values")
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
    logical_provider: ProviderKind | None = None
    semantics: ProviderSemantics | None = None
    desired_fingerprint_domain: FingerprintDomain = (
        FingerprintDomain.PROVIDER_SEMANTICS
    )
    expected_byte_fingerprint: str | None = None
    manual_instructions: tuple[str, ...] = ()
    relationships: tuple[DesiredRelationship, ...] = ()
    local_slots: tuple[LocalDocumentSlot, ...] = ()

    def __post_init__(self) -> None:
        _require_tuple_key_value_pairs(self.payload, "payload")
        _require_enum(self.kind, OperationKind, "kind")
        _require_enum(
            self.desired_fingerprint_domain,
            FingerprintDomain,
            "desired_fingerprint_domain",
        )
        _validate_expected_prior_fingerprint(
            self.kind, self.expected_prior_fingerprint
        )
        if self.logical_provider is not None:
            _require_enum(self.logical_provider, ProviderKind, "logical_provider")
        _require_tuple(self.manual_instructions, "manual_instructions")
        _require_tuple(self.relationships, "relationships")
        _require_tuple(self.local_slots, "local_slots")
        if not all(
            isinstance(relationship, DesiredRelationship)
            for relationship in self.relationships
        ):
            raise TypeError("relationships: expected DesiredRelationship values")
        if not all(isinstance(slot, LocalDocumentSlot) for slot in self.local_slots):
            raise TypeError("local_slots: expected LocalDocumentSlot values")
        if self.local_slots and self.kind is not OperationKind.WRITE_LOCAL:
            raise ValueError("local_slots: allowed only for write_local")
        if not all(
            isinstance(instruction, str) and instruction.strip()
            for instruction in self.manual_instructions
        ):
            raise ValueError("manual_instructions: expected nonblank strings")
        if self.semantics is not None:
            if not isinstance(self.semantics, ProviderSemantics):
                raise TypeError("semantics: expected ProviderSemantics")
            if not hmac.compare_digest(
                self.desired_fingerprint,
                semantics_fingerprint(self.semantics),
            ):
                raise ValueError(
                    "desired_fingerprint does not match typed provider semantics"
                )
        if self.expected_byte_fingerprint is not None and (
            self.kind is not OperationKind.WRITE_LOCAL
            or len(self.expected_byte_fingerprint) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.expected_byte_fingerprint
            )
        ):
            raise ValueError(
                "expected_byte_fingerprint: allowed only as lowercase SHA-256 for write_local"
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
    repository_evidence: tuple[Evidence, ...] = ()
    product_evidence: tuple[Candidate, ...] = ()
    conflict_resolutions: tuple[ConflictResolution, ...] = ()

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
            "repository_evidence",
            "product_evidence",
            "conflict_resolutions",
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
class ManualHandoff:
    operation_id: str
    provider: str
    capability: str
    target_key: str
    diagnostic_code: DiagnosticCode
    expected_fingerprint: str
    semantics: ProviderSemantics
    instructions: tuple[str, ...]
    execution_id: str
    approval_fingerprint: str
    completed_operation_ids: tuple[str, ...] = ()
    disposition: str = "manual_handoff"

    def __post_init__(self) -> None:
        _require_enum(self.diagnostic_code, DiagnosticCode, "diagnostic_code")
        if not isinstance(self.semantics, ProviderSemantics):
            raise TypeError("manual handoff: semantics must be ProviderSemantics")
        _require_tuple(self.instructions, "instructions")
        if not self.instructions or not all(
            isinstance(instruction, str) and instruction.strip()
            for instruction in self.instructions
        ):
            raise ValueError("manual handoff: exact nonblank instructions required")
        if self.disposition != "manual_handoff":
            raise ValueError("manual handoff: invalid disposition")
        _require_tuple(
            self.completed_operation_ids,
            "completed_operation_ids",
        )
        if (
            len(self.completed_operation_ids)
            != len(set(self.completed_operation_ids))
            or not all(
                isinstance(operation_id, str) and operation_id.strip()
                for operation_id in self.completed_operation_ids
            )
        ):
            raise ValueError(
                "manual handoff: completed operation IDs must be unique and nonblank"
            )
        if not isinstance(self.execution_id, str) or not self.execution_id.strip():
            raise ValueError("manual handoff: execution_id must be nonblank")
        if (
            not isinstance(self.approval_fingerprint, str)
            or len(self.approval_fingerprint) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.approval_fingerprint
            )
        ):
            raise ValueError(
                "manual handoff: approval_fingerprint must be lowercase SHA-256"
            )
        _validate_immutable_value(self)


@dataclass(frozen=True)
class BindingReceipt:
    slot_id: str
    source_operation_id: str
    provider: str
    stable_key: str
    external_id: str
    observed_fingerprint: str

    def __post_init__(self) -> None:
        for field_name in (
            "slot_id",
            "source_operation_id",
            "provider",
            "stable_key",
            "external_id",
            "observed_fingerprint",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"binding receipt: {field_name} must be nonblank")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class ApplyResult:
    ready: bool
    evidence: tuple[ApplyEvidence, ...]
    manual_handoffs: tuple[ManualHandoff, ...]
    local_writes: tuple[ApplyEvidence, ...]
    binding_receipts: tuple[BindingReceipt, ...] = ()

    def __post_init__(self) -> None:
        _require_tuple(self.evidence, "evidence")
        _require_tuple(self.manual_handoffs, "manual_handoffs")
        _require_tuple(self.local_writes, "local_writes")
        _require_tuple(self.binding_receipts, "binding_receipts")
        _validate_immutable_value(self)


@dataclass(frozen=True)
class WorkspaceUnit:
    path: str
    package_name: str
    manifest_path: str
    instruction_paths: tuple[str, ...]
    dependency_evidence: tuple[Evidence, ...]
    descendant_instruction_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_tuple(self.instruction_paths, "instruction_paths")
        _require_tuple(self.dependency_evidence, "dependency_evidence")
        _require_tuple(
            self.descendant_instruction_paths,
            "descendant_instruction_paths",
        )
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
    product_evidence: tuple[Candidate, ...] = ()
    product_document_evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "workspace_units",
            "dependencies",
            "instruction_paths",
            "product_document_paths",
            "deployment_evidence",
            "problems",
            "product_evidence",
            "product_document_evidence",
        ):
            _require_tuple(getattr(self, field_name), field_name)
        if not all(isinstance(value, Candidate) for value in self.product_evidence):
            raise TypeError("product_evidence: expected Candidate values")
        if not all(
            isinstance(value, Evidence) for value in self.product_document_evidence
        ):
            raise TypeError("product_document_evidence: expected Evidence values")
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
    repository_product_evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "product_candidates",
            "domain_candidates",
            "conflicts",
            "questions",
            "repository_product_evidence",
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
        ("repository_evidence", Evidence),
        ("product_evidence", Candidate),
        ("conflict_resolutions", ConflictResolution),
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


def semantics_fingerprint(semantics: ProviderSemantics) -> str:
    if not isinstance(semantics, ProviderSemantics):
        raise TypeError("semantics: expected ProviderSemantics")
    canonical_json = json.dumps(
        _canonicalize(semantics),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    framed = b"elephant.provider-semantics/v1\0" + canonical_json.encode("utf-8")
    return hashlib.sha256(framed).hexdigest()


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

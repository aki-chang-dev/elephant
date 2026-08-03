from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import hashlib
import hmac
import json
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


def _require_tuple(value: object, field_name: str) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name}: expected tuple")


@dataclass(frozen=True)
class Evidence:
    source: str
    ref: str
    value: str


@dataclass(frozen=True)
class Candidate:
    key: str
    display_name: str
    evidence: tuple[Evidence, ...]
    confidence: Confidence

    def __post_init__(self) -> None:
        _require_tuple(self.evidence, "evidence")


@dataclass(frozen=True)
class TopologyConflict:
    key: str
    subject: str
    alternatives: tuple[str, ...]
    evidence: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.alternatives, "alternatives")
        _require_tuple(self.evidence, "evidence")


@dataclass(frozen=True)
class OwnerQuestion:
    key: str
    prompt: str
    evidence: tuple[Evidence, ...]
    confidence: Confidence

    def __post_init__(self) -> None:
        _require_tuple(self.evidence, "evidence")


@dataclass(frozen=True)
class ConfirmedProduct:
    key: str
    display_name: str
    domain_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.domain_keys, "domain_keys")


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


@dataclass(frozen=True)
class ConfirmedTopology:
    repository_id: str
    products: tuple[ConfirmedProduct, ...]
    domains: tuple[ConfirmedDomain, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.products, "products")
        _require_tuple(self.domains, "domains")


@dataclass(frozen=True)
class SetupDiagnostic:
    logical_provider: ProviderKind
    physical_provider: str
    capability: str
    code: DiagnosticCode
    blocking: bool


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

    def __post_init__(self) -> None:
        _require_tuple(self.payload, "payload")
        for item in self.payload:
            if not isinstance(item, tuple) or len(item) != 2:
                raise TypeError("payload: expected tuple key/value pairs")


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
    registry: tuple[tuple[str, object], ...]
    profiles: tuple[tuple[str, object], ...]

    def __post_init__(self) -> None:
        for field_name in (
            "provider_selection",
            "products",
            "domains",
            "operations",
            "diagnostics",
            "conflicts",
            "questions",
            "registry",
            "profiles",
        ):
            _require_tuple(getattr(self, field_name), field_name)


@dataclass(frozen=True)
class ApprovedManifest:
    manifest: SetupManifest
    fingerprint: str


@dataclass(frozen=True)
class ApplyEvidence:
    operation_id: str
    target_key: str
    external_id: str
    observed_fingerprint: str
    disposition: str


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


def _canonicalize(value: object) -> Any:
    if isinstance(value, Enum):
        return _canonicalize(value.value)
    if is_dataclass(value) and not isinstance(value, type):
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

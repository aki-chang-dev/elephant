from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import hmac
import re
from typing import Mapping, Protocol

from elephant_runtime.workspace_core.config import EXTERNAL_BINDING_FIELDS

from .models import (
    ApplyEvidence,
    ApplyResult,
    ApprovedManifest,
    BindingReceipt,
    DesiredRelationship,
    ManualHandoff,
    ObservedRelationship,
    OperationKind,
    ProviderSemantics,
    FingerprintDomain,
    LocalDocumentSlot,
    SetupOperation,
    manifest_fingerprint,
)
from .files import (
    LocalContainerOutcome,
    LocalTransactionError,
    LocalTransactionResult,
    LocalWriteOutcome,
    _validate_local_body,
    load_rendered_yaml,
    render_yaml,
)


@dataclass(frozen=True)
class ExternalRecord:
    stable_key: str
    external_id: str
    semantics: ProviderSemantics

    def __post_init__(self) -> None:
        for field_name in ("stable_key", "external_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"external record: {field_name} must be nonblank"
                )
        if not isinstance(self.semantics, ProviderSemantics):
            raise TypeError("external record: semantics must be ProviderSemantics")

    @property
    def fingerprint(self) -> str:
        from .models import semantics_fingerprint

        return semantics_fingerprint(self.semantics)


@dataclass(frozen=True)
class MutationReceipt:
    external_id: str


@dataclass(frozen=True)
class DeletionReceipt:
    external_id: str
    stable_key: str
    deleted: bool = True


@dataclass(frozen=True)
class RelationshipReceipt:
    stable_key: str
    relationship_id: str
    source_external_id: str
    target_external_id: str


@dataclass(frozen=True)
class RelationshipDeletionReceipt:
    stable_key: str
    relationship_id: str
    source_external_id: str
    target_external_id: str
    deleted: bool = True


class SetupAdapter(Protocol):
    """Provider adapter contract for setup execution.

    Phase 3/4 adapters must implement ``create`` as a linearizable, atomic
    stable-key get-or-create. Concurrent calls for one stable key and desired
    fingerprint must return receipts for the same unique semantic record;
    conflicting semantics or duplicate records must fail rather than create or
    select another record. The apply engine performs read-back and a second
    uniqueness query as a conformance guard, not as a replacement for this
    provider-side atomicity requirement.
    """

    provider: str

    def find(self, stable_key: str) -> tuple[ExternalRecord, ...]:
        raise NotImplementedError

    def create(self, operation: SetupOperation) -> MutationReceipt:
        """Atomically get or create the unique semantic stable-key record."""
        raise NotImplementedError

    def read(self, external_id: str) -> ExternalRecord | None:
        raise NotImplementedError

    def bind_relationship(
        self,
        stable_key: str,
        source: ExternalRecord,
        target: ExternalRecord,
        desired: DesiredRelationship,
    ) -> RelationshipReceipt:
        raise NotImplementedError

    def find_relationship(
        self,
        stable_key: str,
    ) -> tuple[ObservedRelationship, ...]:
        raise NotImplementedError

    def read_relationship(
        self,
        relationship_id: str,
    ) -> ObservedRelationship | None:
        raise NotImplementedError

    def unbind_relationship(
        self,
        receipt: RelationshipReceipt,
    ) -> RelationshipDeletionReceipt:
        raise NotImplementedError

    def delete_disposable(
        self,
        external_id: str,
        stable_key: str,
    ) -> DeletionReceipt:
        """Delete only the disposable record owned by the exact stable key."""
        raise NotImplementedError


class _LocalWriter(Protocol):
    def preflight(
        self,
        operations: tuple[SetupOperation, ...],
        expected_container_fingerprint: str,
        owner_id: str,
    ) -> bool | None:
        raise NotImplementedError

    def __call__(
        self,
        operations: tuple[SetupOperation, ...],
        expected_container_fingerprint: str,
        owner_id: str,
    ) -> LocalTransactionResult:
        raise NotImplementedError


class SetupApplyError(RuntimeError):
    """Apply failure with the failing operation and verified prior effects."""

    def __init__(
        self,
        message: str,
        *,
        operation: SetupOperation | None = None,
        cause: BaseException | None = None,
        partial_evidence: tuple[ApplyEvidence, ...] = (),
        observed_snapshot: ExternalRecord | None = None,
    ) -> None:
        self.detail = message
        self.operation = operation
        self.operation_id = operation.operation_id if operation is not None else ""
        self.provider = operation.provider if operation is not None else ""
        self.target_key = operation.target_key if operation is not None else ""
        self.cause = cause
        self.partial_evidence = tuple(partial_evidence)
        self.observed_snapshot = observed_snapshot
        context = f"{self.operation_id}: " if self.operation_id else ""
        super().__init__(f"{context}{message}")


_ADAPTER_OPERATION_KINDS = frozenset(
    {
        OperationKind.REUSE,
        OperationKind.CREATE,
        OperationKind.MANUAL,
        OperationKind.VERIFY,
        OperationKind.ROUND_TRIP,
    }
)


def _preflight(
    approved: object,
    adapters: Mapping[str, SetupAdapter],
) -> ApprovedManifest:
    if not isinstance(approved, ApprovedManifest):
        raise TypeError("approved: expected ApprovedManifest")
    observed_fingerprint = manifest_fingerprint(approved.manifest)
    if not hmac.compare_digest(approved.fingerprint, observed_fingerprint):
        raise SetupApplyError("stale approval fingerprint")
    if approved.manifest.conflicts:
        raise SetupApplyError("manifest has unresolved conflicts")
    if approved.manifest.questions:
        raise SetupApplyError("manifest has unresolved owner questions")
    if any(diagnostic.blocking for diagnostic in approved.manifest.diagnostics):
        raise SetupApplyError("manifest has blocking runtime diagnostics")

    for operation in approved.manifest.operations:
        if (
            operation.kind is OperationKind.WRITE_LOCAL
            and operation.desired_fingerprint_domain
            is not FingerprintDomain.LOCAL_TEMPLATE
        ):
            raise SetupApplyError(
                f"local write {operation.operation_id} lacks local template fingerprint domain"
            )
        if operation.kind not in _ADAPTER_OPERATION_KINDS:
            continue
        if (
            operation.semantics is None
            or operation.desired_fingerprint_domain
            is not FingerprintDomain.PROVIDER_SEMANTICS
        ):
            raise SetupApplyError(
                f"external operation {operation.operation_id} lacks typed provider semantics"
            )

    required_providers = tuple(
        sorted(
            {
                operation.provider
                for operation in approved.manifest.operations
                if operation.kind in _ADAPTER_OPERATION_KINDS
            }
        )
    )
    for provider in required_providers:
        adapter = adapters.get(provider)
        if adapter is None:
            raise SetupApplyError(f"missing setup adapter for {provider}")
        if getattr(adapter, "provider", None) != provider:
            raise SetupApplyError(f"setup adapter provider mismatch for {provider}")
        missing_methods = tuple(
            method
            for method in (
                "find",
                "create",
                "read",
                "bind_relationship",
                "find_relationship",
                "read_relationship",
                "unbind_relationship",
                "delete_disposable",
            )
            if not callable(getattr(adapter, method, None))
        )
        if missing_methods:
            raise SetupApplyError(
                f"setup adapter for {provider} lacks {missing_methods[0]}"
            )
    return approved


def _find_records(
    adapter: SetupAdapter,
    operation: SetupOperation,
    stable_key: str,
) -> tuple[ExternalRecord, ...]:
    records = adapter.find(stable_key)
    if not isinstance(records, tuple) or not all(
        isinstance(record, ExternalRecord) for record in records
    ):
        raise SetupApplyError(
            f"adapter {operation.provider} returned invalid find records for {stable_key}"
        )
    if len(records) > 1:
        raise SetupApplyError(f"duplicate stable-key records for {stable_key}")
    return records


def _require_semantic_match(
    operation: SetupOperation,
    stable_key: str,
    record: ExternalRecord,
    *,
    context: str,
) -> None:
    if (
        record.stable_key != stable_key
        or record.fingerprint != operation.desired_fingerprint
        or operation.semantics is None
        or record.semantics != operation.semantics
    ):
        raise SetupApplyError(
            f"{context} semantic fingerprint mismatch for {stable_key}",
            observed_snapshot=record,
        )


def _read_back(
    adapter: SetupAdapter,
    operation: SetupOperation,
    stable_key: str,
    external_id: str,
) -> ExternalRecord:
    record = adapter.read(external_id)
    if not isinstance(record, ExternalRecord):
        raise SetupApplyError(f"read-back missing for {stable_key}")
    if record.external_id != external_id:
        raise SetupApplyError(
            f"read-back external ID mismatch for {stable_key}",
            observed_snapshot=record,
        )
    _require_semantic_match(
        operation,
        stable_key,
        record,
        context="read-back",
    )
    return record


def _verify_unique_read_back(
    adapter: SetupAdapter,
    operation: SetupOperation,
    stable_key: str,
    record: ExternalRecord,
) -> None:
    records = _find_records(adapter, operation, stable_key)
    if not records:
        raise SetupApplyError(f"post-create record missing for {stable_key}")
    if records[0].external_id != record.external_id:
        raise SetupApplyError(
            f"post-create receipt does not own unique record for {stable_key}"
        )
    _require_semantic_match(
        operation,
        stable_key,
        records[0],
        context="post-create",
    )


def _apply_external_operation(
    operation: SetupOperation,
    adapter: SetupAdapter,
) -> ApplyEvidence:
    records = _find_records(adapter, operation, operation.target_key)
    if operation.kind in (OperationKind.REUSE, OperationKind.VERIFY):
        if not records:
            raise SetupApplyError(
                f"expected exactly one stable-key record for {operation.target_key}"
            )
        _require_semantic_match(
            operation,
            operation.target_key,
            records[0],
            context="existing",
        )
        record = _read_back(
            adapter,
            operation,
            operation.target_key,
            records[0].external_id,
        )
        _verify_unique_read_back(
            adapter,
            operation,
            operation.target_key,
            record,
        )
        disposition = (
            "reused" if operation.kind is OperationKind.REUSE else "verified"
        )
    elif operation.kind is OperationKind.CREATE:
        if records:
            _require_semantic_match(
                operation,
                operation.target_key,
                records[0],
                context="existing",
            )
            external_id = records[0].external_id
            disposition = "reused"
        else:
            receipt = adapter.create(operation)
            if not isinstance(receipt, MutationReceipt) or not receipt.external_id:
                raise SetupApplyError(
                    f"invalid mutation receipt for {operation.target_key}"
                )
            external_id = receipt.external_id
            disposition = "created"
        record = _read_back(
            adapter,
            operation,
            operation.target_key,
            external_id,
        )
        _verify_unique_read_back(
            adapter,
            operation,
            operation.target_key,
            record,
        )
    else:
        raise SetupApplyError(
            f"unsupported external operation kind {operation.kind.value}"
        )
    return ApplyEvidence(
        operation_id=operation.operation_id,
        target_key=operation.target_key,
        external_id=record.external_id,
        observed_fingerprint=record.fingerprint,
        disposition=disposition,
    )


def _manual_handoff(
    operation: SetupOperation,
    execution_id: str,
    approval_fingerprint: str,
    completed_operation_ids: tuple[str, ...],
) -> ManualHandoff:
    payload = dict(operation.payload)
    try:
        from elephant_runtime.workspace_core import DiagnosticCode

        diagnostic_code = DiagnosticCode(payload["diagnostic_code"])
    except (KeyError, TypeError, ValueError) as error:
        raise SetupApplyError(
            f"manual handoff {operation.operation_id} lacks exact diagnostic"
        ) from error
    if operation.semantics is None or not operation.manual_instructions:
        raise SetupApplyError(
            f"manual handoff {operation.operation_id} lacks desired fields or instructions"
        )
    return ManualHandoff(
        operation_id=operation.operation_id,
        provider=operation.provider,
        capability=operation.capability,
        target_key=operation.target_key,
        diagnostic_code=diagnostic_code,
        expected_fingerprint=operation.desired_fingerprint,
        semantics=operation.semantics,
        instructions=operation.manual_instructions,
        execution_id=execution_id,
        approval_fingerprint=approval_fingerprint,
        completed_operation_ids=completed_operation_ids,
    )


def _apply_manual_operation(
    operation: SetupOperation,
    adapter: SetupAdapter,
    execution_id: str,
    approval_fingerprint: str,
    resume_handoff: ManualHandoff | None,
    *,
    previously_completed: bool,
    completed_operation_ids: tuple[str, ...],
) -> ApplyEvidence | ManualHandoff:
    records = _find_records(adapter, operation, operation.target_key)
    if not records:
        if previously_completed:
            raise SetupApplyError(
                f"previously completed manual operation {operation.operation_id} is absent"
            )
        return _manual_handoff(
            operation,
            execution_id,
            approval_fingerprint,
            completed_operation_ids,
        )
    if resume_handoff is None and not previously_completed:
        raise SetupApplyError(
            f"manual completion {operation.operation_id} requires prior manual handoff"
        )
    _require_semantic_match(
        operation,
        operation.target_key,
        records[0],
        context="manual completion",
    )
    record = _read_back(
        adapter,
        operation,
        operation.target_key,
        records[0].external_id,
    )
    _verify_unique_read_back(
        adapter,
        operation,
        operation.target_key,
        record,
    )
    return ApplyEvidence(
        operation_id=operation.operation_id,
        target_key=operation.target_key,
        external_id=record.external_id,
        observed_fingerprint=record.fingerprint,
        disposition="manual_completed",
    )


def _apply_round_trip(
    operation: SetupOperation,
    adapter: SetupAdapter,
    approval_fingerprint: str,
    execution_id: str,
) -> ApplyEvidence:
    payload = dict(operation.payload)
    if payload.get("disposable") is not True:
        raise SetupApplyError(
            f"round-trip {operation.operation_id} lacks disposable authority"
        )
    disposable_key = (
        f"{operation.target_key}.{approval_fingerprint}.{execution_id}"
    )
    disposable_operation = replace(operation, target_key=disposable_key)
    records = _find_records(adapter, disposable_operation, disposable_key)
    created = False
    if records:
        _require_semantic_match(
            disposable_operation,
            disposable_key,
            records[0],
            context="existing disposable",
        )
        external_id = records[0].external_id
    else:
        receipt = adapter.create(disposable_operation)
        if not isinstance(receipt, MutationReceipt) or not receipt.external_id:
            raise SetupApplyError(
                f"invalid mutation receipt for disposable {disposable_key}"
            )
        external_id = receipt.external_id
        created = True

    record = _read_back(
        adapter,
        disposable_operation,
        disposable_key,
        external_id,
    )
    _verify_unique_read_back(
        adapter,
        disposable_operation,
        disposable_key,
        record,
    )
    if len(operation.relationships) != 1:
        raise SetupApplyError(
            f"round-trip {operation.operation_id} requires one approved relationship"
        )
    desired_relationship = operation.relationships[0]
    relationship_key = f"{disposable_key}.relationship.0"
    existing_relationships = adapter.find_relationship(relationship_key)
    if not isinstance(existing_relationships, tuple) or not all(
        isinstance(item, ObservedRelationship)
        for item in existing_relationships
    ):
        raise SetupApplyError(
            f"round-trip relationship query failed for {disposable_key}"
        )
    if len(existing_relationships) > 1:
        raise SetupApplyError(
            f"duplicate round-trip relationships for {disposable_key}"
        )
    if existing_relationships:
        existing_relationship = existing_relationships[0]
        relationship = RelationshipReceipt(
            stable_key=relationship_key,
            relationship_id=existing_relationship.relationship_id,
            source_external_id=existing_relationship.source_external_id,
            target_external_id=existing_relationship.target_external_id,
        )
    else:
        relationship = adapter.bind_relationship(
            relationship_key,
            record,
            record,
            desired_relationship,
        )
    if (
        not isinstance(relationship, RelationshipReceipt)
        or relationship.stable_key != relationship_key
        or not relationship.relationship_id
        or relationship.source_external_id != record.external_id
        or relationship.target_external_id != record.external_id
    ):
        raise SetupApplyError(
            f"round-trip relationship receipt failed for {disposable_key}"
        )
    observed_relationship = adapter.read_relationship(
        relationship.relationship_id
    )
    if (
        not isinstance(observed_relationship, ObservedRelationship)
        or observed_relationship.stable_key != relationship_key
        or observed_relationship.relationship_id != relationship.relationship_id
        or observed_relationship.source_external_id != record.external_id
        or observed_relationship.target_external_id != record.external_id
        or observed_relationship.semantics != desired_relationship
    ):
        raise SetupApplyError(
            f"round-trip relationship read-back failed for {disposable_key}"
        )
    unique_relationships = adapter.find_relationship(relationship_key)
    if (
        not isinstance(unique_relationships, tuple)
        or len(unique_relationships) != 1
        or unique_relationships[0] != observed_relationship
    ):
        raise SetupApplyError(
            f"round-trip relationship uniqueness failed for {disposable_key}"
        )
    unbound = adapter.unbind_relationship(relationship)
    if (
        not isinstance(unbound, RelationshipDeletionReceipt)
        or unbound.stable_key != relationship_key
        or unbound.relationship_id != relationship.relationship_id
        or unbound.source_external_id != record.external_id
        or unbound.target_external_id != record.external_id
        or not unbound.deleted
    ):
        raise SetupApplyError(
            f"round-trip relationship cleanup failed for {disposable_key}"
        )
    if adapter.read_relationship(relationship.relationship_id) is not None:
        raise SetupApplyError(
            f"round-trip relationship cleanup left binding for {disposable_key}"
        )
    remaining_relationships = adapter.find_relationship(relationship_key)
    if not isinstance(remaining_relationships, tuple) or remaining_relationships:
        raise SetupApplyError(
            f"round-trip relationship stable-key cleanup left binding for {disposable_key}"
        )
    deletion = adapter.delete_disposable(record.external_id, disposable_key)
    if (
        not isinstance(deletion, DeletionReceipt)
        or deletion.external_id != record.external_id
        or deletion.stable_key != disposable_key
        or not deletion.deleted
    ):
        raise SetupApplyError(f"disposable cleanup receipt failed for {disposable_key}")
    if adapter.read(record.external_id) is not None:
        raise SetupApplyError(f"disposable cleanup left record {disposable_key}")
    if _find_records(adapter, disposable_operation, disposable_key):
        raise SetupApplyError(
            f"disposable stable-key cleanup left record {disposable_key}"
        )
    return ApplyEvidence(
        operation_id=operation.operation_id,
        target_key=disposable_key,
        external_id=record.external_id,
        observed_fingerprint=record.fingerprint,
        disposition="round_trip_cleaned",
    )


def _local_document(operation: SetupOperation) -> object:
    payload = dict(operation.payload)
    if "document" not in payload:
        raise SetupApplyError(
            f"local write {operation.operation_id} has no document payload"
        )
    return payload["document"]


_SLOT_PREFIX = "urn:elephant:setup-slot:"


def _collect_strings(value: object) -> tuple[str, ...]:
    if isinstance(value, dict):
        return tuple(
            item
            for child in value.values()
            for item in _collect_strings(child)
        )
    if isinstance(value, list):
        return tuple(item for child in value for item in _collect_strings(child))
    return (value,) if isinstance(value, str) else ()


def _validate_external_workspace_slots(
    document: Mapping[str, object],
    slots: tuple[LocalDocumentSlot, ...],
) -> None:
    slot_by_placeholder = {
        slot.placeholder: slot
        for slot in slots
    }

    def require_slot(value: object, provider: str) -> None:
        slot = slot_by_placeholder.get(value) if isinstance(value, str) else None
        if slot is None or slot.provider != provider:
            raise SetupApplyError(
                "external opaque IDs require typed local document slots"
            )

    providers = document.get("providers")
    bindings = document.get("bindings")
    products = document.get("products")
    if not isinstance(providers, Mapping) or not isinstance(bindings, Mapping):
        return
    for provider in sorted(set(providers.values()) - {"git"}):
        provider_bindings = bindings.get(provider)
        if not isinstance(provider, str) or not isinstance(
            provider_bindings, Mapping
        ):
            continue
        for field in EXTERNAL_BINDING_FIELDS.get(provider, ()):
            require_slot(provider_bindings.get(field), provider)
    if not isinstance(products, Mapping):
        return
    reference_roles = (
        ("story_store", "story_ref"),
        ("product_knowledge_store", "knowledge_ref"),
    )
    for product in products.values():
        if not isinstance(product, Mapping):
            continue
        for logical_provider, field in reference_roles:
            provider = providers.get(logical_provider)
            if isinstance(provider, str) and provider != "git":
                require_slot(product.get(field), provider)


def _validate_local_templates(
    operations: tuple[SetupOperation, ...],
    all_operations: tuple[SetupOperation, ...],
) -> None:
    operation_by_id = {operation.operation_id: operation for operation in all_operations}
    if len(operation_by_id) != len(all_operations):
        raise SetupApplyError("manifest has duplicate operation IDs")
    seen_slots: set[str] = set()
    for operation in operations:
        payload = dict(operation.payload)
        document = _local_document(operation)
        template_document = payload.get("template_document", document)
        unchanged_rerun = payload.get("unchanged_rerun") is True
        if "template_document" in payload and not unchanged_rerun:
            raise SetupApplyError(
                f"local write {operation.operation_id} has unauthorized template payload"
            )
        if not isinstance(document, str) or not isinstance(
            template_document,
            str,
        ):
            raise SetupApplyError(
                f"local write {operation.operation_id} requires canonical string bytes"
            )
        _validate_local_body(operation.target_key, template_document)
        if unchanged_rerun:
            _validate_local_body(operation.target_key, document)
            expected_bytes = hashlib.sha256(
                document.encode("utf-8")
            ).hexdigest()
            if (
                operation.expected_byte_fingerprint is None
                or not hmac.compare_digest(
                    operation.expected_byte_fingerprint,
                    expected_bytes,
                )
            ):
                raise SetupApplyError(
                    f"unchanged rerun {operation.operation_id} lacks exact local bytes"
                )
        loaded_document = load_rendered_yaml(template_document)
        strings = _collect_strings(loaded_document)
        approved_placeholders = {slot.placeholder for slot in operation.local_slots}
        observed_placeholders = {
            value for value in strings if value.startswith(_SLOT_PREFIX)
        }
        if observed_placeholders != approved_placeholders:
            raise SetupApplyError(
                f"local write {operation.operation_id} has unauthorized or missing slots"
            )
        if operation.target_key == ".agents/elephant/workspace.yaml":
            _validate_external_workspace_slots(
                loaded_document,
                operation.local_slots,
            )
        for slot in operation.local_slots:
            if slot.slot_id in seen_slots:
                raise SetupApplyError(f"duplicate local document slot {slot.slot_id}")
            seen_slots.add(slot.slot_id)
            if strings.count(slot.placeholder) < 1:
                raise SetupApplyError(f"local document slot {slot.slot_id} is unused")
            source = operation_by_id.get(slot.source_operation_id)
            if (
                source is None
                or source.provider != slot.provider
                or source.target_key != slot.stable_key
                or source.kind not in {
                    OperationKind.REUSE,
                    OperationKind.CREATE,
                    OperationKind.MANUAL,
                    OperationKind.VERIFY,
                }
            ):
                raise SetupApplyError(
                    f"local document slot {slot.slot_id} lacks approved stable-key authority"
                )


def _replace_slots(value: object, replacements: Mapping[str, str]) -> object:
    if isinstance(value, dict):
        return {key: _replace_slots(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_slots(item, replacements) for item in value]
    if isinstance(value, str) and value in replacements:
        return replacements[value]
    return value


def _materialize_local_operations(
    operations: tuple[SetupOperation, ...],
    evidence: tuple[ApplyEvidence, ...],
) -> tuple[tuple[SetupOperation, ...], tuple[BindingReceipt, ...]]:
    evidence_by_id = {item.operation_id: item for item in evidence}
    materialized: list[SetupOperation] = []
    receipts: list[BindingReceipt] = []
    for operation in operations:
        replacements: dict[str, str] = {}
        for slot in operation.local_slots:
            source = evidence_by_id.get(slot.source_operation_id)
            if (
                source is None
                or source.target_key != slot.stable_key
                or not source.external_id
                or source.disposition
                not in {"created", "reused", "verified", "manual_completed"}
            ):
                raise SetupApplyError(
                    f"local document slot {slot.slot_id} lacks verified read-back"
                )
            if source.external_id.strip().startswith(_SLOT_PREFIX):
                raise SetupApplyError(
                    f"local document slot {slot.slot_id} read back a reserved slot ID"
                )
            receipt = BindingReceipt(
                slot_id=slot.slot_id,
                source_operation_id=slot.source_operation_id,
                provider=slot.provider,
                stable_key=slot.stable_key,
                external_id=source.external_id,
                observed_fingerprint=source.observed_fingerprint,
            )
            receipts.append(receipt)
            replacements[slot.placeholder] = receipt.external_id
        body = _local_document(operation)
        assert isinstance(body, str)
        payload_values = dict(operation.payload)
        template_body = payload_values.get("template_document", body)
        if not isinstance(template_body, str):
            raise SetupApplyError(
                f"local write {operation.operation_id} has invalid template bytes"
            )
        materialized_body = template_body
        if replacements:
            materialized_body = render_yaml(
                _replace_slots(
                    load_rendered_yaml(template_body),
                    replacements,
                )
            )
        if payload_values.get("unchanged_rerun") is True:
            if not hmac.compare_digest(body, materialized_body):
                raise SetupApplyError(
                    f"unchanged rerun external bindings changed for {operation.target_key}"
                )
        else:
            body = materialized_body
        _validate_local_body(operation.target_key, body)
        expected_bytes = hashlib.sha256(body.encode("utf-8")).hexdigest()
        if (
            operation.expected_byte_fingerprint is not None
            and not hmac.compare_digest(
                operation.expected_byte_fingerprint,
                expected_bytes,
            )
        ):
            raise SetupApplyError(
                f"approved local byte fingerprint changed for {operation.target_key}"
            )
        payload = tuple(
            (key, body if key == "document" else value)
            for key, value in operation.payload
        )
        materialized.append(
            replace(
                operation,
                payload=payload,
                expected_byte_fingerprint=expected_bytes,
            )
        )
    return tuple(materialized), tuple(receipts)


def _read_existing_slot_source(
    operation: SetupOperation,
    adapter: SetupAdapter,
) -> ApplyEvidence | None:
    records = _find_records(adapter, operation, operation.target_key)
    if not records:
        return None
    _require_semantic_match(
        operation,
        operation.target_key,
        records[0],
        context="local slot preflight",
    )
    record = _read_back(
        adapter,
        operation,
        operation.target_key,
        records[0].external_id,
    )
    _verify_unique_read_back(
        adapter,
        operation,
        operation.target_key,
        record,
    )
    disposition = {
        OperationKind.REUSE: "reused",
        OperationKind.CREATE: "reused",
        OperationKind.MANUAL: "manual_completed",
        OperationKind.VERIFY: "verified",
    }.get(operation.kind)
    if disposition is None:
        raise SetupApplyError(
            f"local slot source {operation.operation_id} is not read-only"
        )
    return ApplyEvidence(
        operation_id=operation.operation_id,
        target_key=operation.target_key,
        external_id=record.external_id,
        observed_fingerprint=record.fingerprint,
        disposition=disposition,
    )


def _prepare_local_preflight(
    local_operations: tuple[SetupOperation, ...],
    all_operations: tuple[SetupOperation, ...],
    adapters: Mapping[str, SetupAdapter],
    resume_handoff: ManualHandoff | None,
) -> tuple[tuple[SetupOperation, ...], dict[str, ApplyEvidence]]:
    source_ids = {
        slot.source_operation_id
        for operation in local_operations
        for slot in operation.local_slots
    }
    if not source_ids:
        return local_operations, {}
    source_operations = tuple(
        operation
        for operation in all_operations
        if operation.operation_id in source_ids
    )
    if len(source_operations) != len(source_ids):
        raise SetupApplyError("local slot preflight lacks source operation")
    evidence_by_id: dict[str, ApplyEvidence] = {}
    for operation in source_operations:
        if operation.kind is OperationKind.MANUAL and (
            resume_handoff is None
            or operation.operation_id
            not in (
                resume_handoff.completed_operation_ids
                + (resume_handoff.operation_id,)
            )
        ):
            return local_operations, {}
        try:
            evidence = _read_existing_slot_source(
                operation,
                adapters[operation.provider],
            )
        except Exception as error:
            raise _contextual_error(error, operation, ()) from error
        if evidence is None:
            return local_operations, {}
        evidence_by_id[operation.operation_id] = evidence
    materialized, _ = _materialize_local_operations(
        local_operations,
        tuple(evidence_by_id.values()),
    )
    return materialized, evidence_by_id


def _contextual_error(
    error: BaseException,
    operation: SetupOperation,
    partial_evidence: tuple[ApplyEvidence, ...],
) -> SetupApplyError:
    if isinstance(error, SetupApplyError):
        detail = error.detail
        cause = error.cause if error.cause is not None else error
        operation_context = error.operation or operation
        nested_evidence = error.partial_evidence
        observed_snapshot = error.observed_snapshot
    else:
        detail = str(error) or type(error).__name__
        cause = error
        operation_context = operation
        nested_evidence = ()
        observed_snapshot = None
    return SetupApplyError(
        detail,
        operation=operation_context,
        cause=cause,
        partial_evidence=partial_evidence + nested_evidence,
        observed_snapshot=observed_snapshot,
    )


def _local_evidence(
    operations: tuple[SetupOperation, ...],
    outcomes: tuple[LocalWriteOutcome, ...],
    *,
    require_durable: bool,
) -> tuple[ApplyEvidence, ...]:
    operation_by_id = {operation.operation_id: operation for operation in operations}
    if len(operation_by_id) != len(operations) or len(outcomes) != len(operations):
        raise SetupApplyError("local transaction returned incomplete outcomes")
    evidence: list[ApplyEvidence] = []
    seen: set[str] = set()
    for outcome in outcomes:
        operation = operation_by_id.get(outcome.operation_id)
        if operation is None or outcome.operation_id in seen:
            raise SetupApplyError("local transaction returned unknown outcome")
        if outcome.path != operation.target_key or not outcome.states:
            raise SetupApplyError("local transaction outcome does not match operation")
        disposition = outcome.states[-1]
        if require_durable and disposition != "durable":
            raise SetupApplyError(
                f"local transaction did not make {operation.target_key} durable"
            )
        expected_bytes = operation.expected_byte_fingerprint
        if require_durable and (
            expected_bytes is None
            or not hmac.compare_digest(
                expected_bytes,
                outcome.observed_fingerprint,
            )
        ):
            raise SetupApplyError(
                f"local byte fingerprint mismatch for {operation.target_key}"
            )
        seen.add(outcome.operation_id)
        evidence.append(
            ApplyEvidence(
                operation_id=operation.operation_id,
                target_key=operation.target_key,
                external_id=operation.target_key,
                observed_fingerprint=outcome.observed_fingerprint,
                disposition=disposition,
            )
        )
    return tuple(evidence)


def _container_evidence(
    container: LocalContainerOutcome,
    *,
    expected_owner: str,
    expected_prior: str,
    require_committed: bool,
) -> ApplyEvidence:
    if not isinstance(container, LocalContainerOutcome):
        raise SetupApplyError("local transaction returned invalid container outcome")
    if container.owner_id != expected_owner:
        raise SetupApplyError("local container owner does not match this execution")
    if not hmac.compare_digest(container.prior_fingerprint, expected_prior):
        raise SetupApplyError("local container prior evidence does not match approval")
    if require_committed and (
        len(container.desired_fingerprint) != 64
        or not hmac.compare_digest(
            container.desired_fingerprint, container.observed_fingerprint
        )
    ):
        raise SetupApplyError("local container committed evidence is inconsistent")
    return ApplyEvidence(
        operation_id="local.container",
        target_key=".agents",
        external_id=container.owner_id,
        observed_fingerprint=container.observed_fingerprint,
        disposition=container.disposition,
    )


def _retained_stage_evidence(
    container: LocalContainerOutcome,
    *,
    require_observed: bool,
) -> tuple[ApplyEvidence, ...]:
    stage_name = container.retained_stage_name
    fingerprint = container.retained_stage_fingerprint
    device = container.retained_stage_device
    inode = container.retained_stage_inode
    path_attested = container.retained_stage_path_attested
    if stage_name is None:
        if path_attested is False:
            if (
                not isinstance(device, int)
                or isinstance(device, bool)
                or not isinstance(inode, int)
                or isinstance(inode, bool)
            ):
                raise SetupApplyError(
                    "local recovery stage identity evidence is incomplete"
                )
            if require_observed and len(fingerprint) != 64:
                raise SetupApplyError("local recovery stage evidence is incomplete")
            return (
                ApplyEvidence(
                    operation_id="local.container.recovery",
                    target_key="",
                    external_id=container.owner_id,
                    observed_fingerprint=fingerprint,
                    disposition="path_identity_lost",
                ),
            )
        if (
            fingerprint
            or device is not None
            or inode is not None
            or path_attested is not None
        ):
            raise SetupApplyError("local recovery stage evidence has no stage name")
        return ()
    if (
        not stage_name.startswith(".agents.setup-stage-")
        or "/" in stage_name
        or stage_name in {".", ".."}
    ):
        raise SetupApplyError("local recovery stage evidence has an invalid stage name")
    if (
        path_attested is not True
        or not isinstance(device, int)
        or isinstance(device, bool)
        or not isinstance(inode, int)
        or isinstance(inode, bool)
    ):
        raise SetupApplyError("local recovery stage identity evidence is incomplete")
    if require_observed and len(fingerprint) != 64:
        raise SetupApplyError("local recovery stage evidence is incomplete")
    return (
        ApplyEvidence(
            operation_id="local.container.recovery",
            target_key=stage_name,
            external_id=container.owner_id,
            observed_fingerprint=fingerprint,
            disposition="cleanup_pending",
        ),
    )


def _cancel_local_preflight(write_local: object, owner_id: str) -> None:
    cancel = getattr(write_local, "cancel_preflight", None)
    if callable(cancel):
        cancel(owner_id)


def _validated_resume_handoff(
    authority: ApprovedManifest,
    execution_id: str,
    resume_handoff: object,
) -> ManualHandoff | None:
    if resume_handoff is None:
        return None
    if not isinstance(resume_handoff, ManualHandoff):
        raise TypeError("resume_handoff: expected ManualHandoff")
    if not hmac.compare_digest(
        resume_handoff.approval_fingerprint,
        authority.fingerprint,
    ):
        raise SetupApplyError(
            "manual continuation handoff belongs to a different approval"
        )
    if hmac.compare_digest(resume_handoff.execution_id, execution_id):
        raise SetupApplyError(
            "manual continuation requires a distinct execution ID"
        )
    matches = tuple(
        operation
        for operation in authority.manifest.operations
        if operation.kind is OperationKind.MANUAL
        and operation.operation_id == resume_handoff.operation_id
    )
    if len(matches) != 1:
        raise SetupApplyError(
            "manual continuation handoff has no unique approved operation"
        )
    operation = matches[0]
    if (
        operation.provider != resume_handoff.provider
        or operation.capability != resume_handoff.capability
        or operation.target_key != resume_handoff.target_key
        or operation.desired_fingerprint
        != resume_handoff.expected_fingerprint
        or operation.semantics != resume_handoff.semantics
        or operation.manual_instructions != resume_handoff.instructions
    ):
        raise SetupApplyError(
            "manual continuation handoff does not match approved operation"
        )
    manual_operation_ids = tuple(
        item.operation_id
        for item in authority.manifest.operations
        if item.kind is OperationKind.MANUAL
    )
    operation_index = manual_operation_ids.index(operation.operation_id)
    if resume_handoff.completed_operation_ids != manual_operation_ids[
        :operation_index
    ]:
        raise SetupApplyError(
            "manual continuation handoff lacks the approved completion chain"
        )
    return resume_handoff


def apply_setup(
    approved: ApprovedManifest,
    adapters: Mapping[str, SetupAdapter],
    write_local: _LocalWriter,
    *,
    execution_id: str,
    resume_handoff: ManualHandoff | None = None,
) -> ApplyResult:
    """Apply one approval under an execution-owned mutation authority.

    ``execution_id`` identifies this apply attempt. It scopes disposable stable
    keys and local transaction ownership, but it is not durable approval
    authority and does not need to match an earlier manual-handoff attempt.
    """
    if not isinstance(execution_id, str) or not execution_id.strip():
        raise SetupApplyError("execution_id must be a nonblank string")
    execution_token = execution_id.strip()
    authority = _preflight(approved, adapters)
    validated_handoff = _validated_resume_handoff(
        authority,
        execution_token,
        resume_handoff,
    )
    operations = authority.manifest.operations
    local_operations = tuple(
        operation
        for operation in operations
        if operation.kind is OperationKind.WRITE_LOCAL
    )
    evidence: list[ApplyEvidence] = []
    preflight_evidence: dict[str, ApplyEvidence] = {}
    try:
        _validate_local_templates(local_operations, operations)
        preflight_local = getattr(write_local, "preflight", None)
        if not callable(preflight_local):
            raise SetupApplyError("local writer lacks preflight")
        rerun_markers = tuple(
            dict(operation.payload).get("unchanged_rerun") is True
            for operation in local_operations
        )
        if any(rerun_markers) and not all(rerun_markers):
            raise SetupApplyError(
                "unchanged rerun marker must cover every local operation"
            )
        unchanged_rerun = bool(rerun_markers) and all(rerun_markers)
        preflight_unchanged = preflight_local(
            local_operations,
            authority.manifest.expected_local_container_fingerprint,
            execution_token,
        )
        if unchanged_rerun and preflight_unchanged is not True:
            raise SetupApplyError(
                "approved unchanged rerun no longer matches local state"
            )
        _, preflight_evidence = _prepare_local_preflight(
            local_operations,
            operations,
            adapters,
            validated_handoff,
        )
    except BaseException as error:
        _cancel_local_preflight(write_local, execution_token)
        if not isinstance(error, Exception):
            raise
        operation = local_operations[0] if local_operations else None
        if operation is None:
            raise SetupApplyError(str(error) or type(error).__name__, cause=error) from error
        raise _contextual_error(error, operation, ()) from error

    for operation in operations:
        if operation.kind is OperationKind.WRITE_LOCAL:
            continue
        if operation.operation_id in preflight_evidence:
            evidence.append(preflight_evidence[operation.operation_id])
            continue
        try:
            if operation.kind is OperationKind.MANUAL:
                completed_operation_ids = tuple(
                    item.operation_id
                    for item in evidence
                    if item.disposition == "manual_completed"
                )
                manual_evidence = _apply_manual_operation(
                    operation,
                    adapters[operation.provider],
                    execution_token,
                    authority.fingerprint,
                    (
                        validated_handoff
                        if validated_handoff is not None
                        and validated_handoff.operation_id
                        == operation.operation_id
                        else None
                    ),
                    previously_completed=(
                        validated_handoff is not None
                        and operation.operation_id
                        in validated_handoff.completed_operation_ids
                    ),
                    completed_operation_ids=completed_operation_ids,
                )
                if isinstance(manual_evidence, ManualHandoff):
                    _cancel_local_preflight(write_local, execution_token)
                    return ApplyResult(
                        ready=False,
                        evidence=tuple(evidence),
                        manual_handoffs=(manual_evidence,),
                        local_writes=(),
                    )
                evidence.append(manual_evidence)
                continue
            if operation.kind is OperationKind.ROUND_TRIP:
                evidence.append(
                    _apply_round_trip(
                        operation,
                        adapters[operation.provider],
                        authority.fingerprint,
                        execution_token,
                    )
                )
                continue
            evidence.append(
                _apply_external_operation(operation, adapters[operation.provider])
            )
        except BaseException as error:
            _cancel_local_preflight(write_local, execution_token)
            if not isinstance(error, Exception):
                raise
            raise _contextual_error(error, operation, tuple(evidence)) from error

    try:
        local_operations, binding_receipts = _materialize_local_operations(
            local_operations,
            tuple(evidence),
        )
        transaction = write_local(
            local_operations,
            authority.manifest.expected_local_container_fingerprint,
            execution_token,
        )
        if not isinstance(transaction, LocalTransactionResult):
            raise SetupApplyError("local writer returned invalid transaction result")
        local_writes = _local_evidence(
            local_operations,
            transaction.outcomes,
            require_durable=True,
        )
        container_evidence = _container_evidence(
            transaction.container,
            expected_owner=execution_token,
            expected_prior=authority.manifest.expected_local_container_fingerprint,
            require_committed=True,
        )
        recovery_evidence = _retained_stage_evidence(
            transaction.container,
            require_observed=True,
        )
        if transaction.container.retained_stage_path_attested is False:
            raise SetupApplyError(
                "local recovery stage path identity was lost",
                partial_evidence=(
                    local_writes + recovery_evidence + (container_evidence,)
                ),
            )
        if container_evidence.disposition not in {"created", "replaced", "unchanged"}:
            raise SetupApplyError("local container did not commit successfully")
    except LocalTransactionError as error:
        _cancel_local_preflight(write_local, execution_token)
        try:
            local_outcomes = _local_evidence(
                local_operations,
                error.outcomes,
                require_durable=False,
            )
            container_evidence = _container_evidence(
                error.container,
                expected_owner=execution_token,
                expected_prior=authority.manifest.expected_local_container_fingerprint,
                require_committed=False,
            )
            recovery_evidence = _retained_stage_evidence(
                error.container,
                require_observed=False,
            )
        except SetupApplyError as invalid_outcomes:
            raise _contextual_error(
                invalid_outcomes,
                error.operation or local_operations[0],
                tuple(evidence),
            ) from error
        raise SetupApplyError(
            error.detail,
            operation=error.operation or local_operations[0],
            cause=error.cause,
            partial_evidence=(
                tuple(evidence)
                + local_outcomes
                + recovery_evidence
                + (container_evidence,)
            ),
        ) from error
    except BaseException as error:
        _cancel_local_preflight(write_local, execution_token)
        if not isinstance(error, Exception):
            raise
        operation = local_operations[0] if local_operations else None
        if operation is None:
            raise SetupApplyError(str(error) or type(error).__name__, cause=error) from error
        raise _contextual_error(error, operation, tuple(evidence)) from error
    local_writes = local_writes + recovery_evidence + (container_evidence,)
    evidence.extend(local_writes)
    return ApplyResult(
        ready=True,
        evidence=tuple(evidence),
        manual_handoffs=(),
        local_writes=local_writes,
        binding_receipts=binding_receipts,
    )

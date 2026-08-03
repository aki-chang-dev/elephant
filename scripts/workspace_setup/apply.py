from __future__ import annotations

from dataclasses import dataclass, replace
import hmac
from typing import Mapping, Protocol

from .models import (
    ApplyEvidence,
    ApplyResult,
    ApprovedManifest,
    OperationKind,
    SetupOperation,
    manifest_fingerprint,
)


@dataclass(frozen=True)
class ExternalRecord:
    stable_key: str
    external_id: str
    fingerprint: str


@dataclass(frozen=True)
class MutationReceipt:
    external_id: str


@dataclass(frozen=True)
class DeletionReceipt:
    external_id: str
    deleted: bool = True


class SetupAdapter(Protocol):
    provider: str

    def find(self, stable_key: str) -> tuple[ExternalRecord, ...]:
        raise NotImplementedError

    def create(self, operation: SetupOperation) -> MutationReceipt:
        raise NotImplementedError

    def read(self, external_id: str) -> ExternalRecord | None:
        raise NotImplementedError

    def delete_disposable(self, external_id: str) -> DeletionReceipt:
        raise NotImplementedError


class _LocalWriter(Protocol):
    def __call__(self, path: str, body: object) -> None:
        raise NotImplementedError


class SetupApplyError(RuntimeError):
    pass


_ADAPTER_OPERATION_KINDS = frozenset(
    {
        OperationKind.REUSE,
        OperationKind.CREATE,
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
            for method in ("find", "create", "read", "delete_disposable")
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
    ):
        raise SetupApplyError(
            f"{context} semantic fingerprint mismatch for {stable_key}"
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
        raise SetupApplyError(f"read-back external ID mismatch for {stable_key}")
    _require_semantic_match(
        operation,
        stable_key,
        record,
        context="read-back",
    )
    return record


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


def _manual_handoff(operation: SetupOperation) -> ApplyEvidence:
    return ApplyEvidence(
        operation_id=operation.operation_id,
        target_key=operation.target_key,
        external_id="",
        observed_fingerprint=operation.desired_fingerprint,
        disposition="manual_handoff",
    )


def _apply_round_trip(
    operation: SetupOperation,
    adapter: SetupAdapter,
    approval_fingerprint: str,
) -> ApplyEvidence:
    payload = dict(operation.payload)
    if payload.get("disposable") is not True:
        raise SetupApplyError(
            f"round-trip {operation.operation_id} lacks disposable authority"
        )
    disposable_key = f"{operation.target_key}.{approval_fingerprint}"
    disposable_operation = replace(operation, target_key=disposable_key)
    records = _find_records(adapter, disposable_operation, disposable_key)
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

    record = _read_back(
        adapter,
        disposable_operation,
        disposable_key,
        external_id,
    )
    deletion = adapter.delete_disposable(record.external_id)
    if (
        not isinstance(deletion, DeletionReceipt)
        or deletion.external_id != record.external_id
        or not deletion.deleted
    ):
        raise SetupApplyError(f"disposable cleanup receipt failed for {disposable_key}")
    if adapter.read(record.external_id) is not None:
        raise SetupApplyError(f"disposable cleanup left record {disposable_key}")
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


def apply_setup(
    approved: ApprovedManifest,
    adapters: Mapping[str, SetupAdapter],
    write_local: _LocalWriter,
) -> ApplyResult:
    authority = _preflight(approved, adapters)
    operations = authority.manifest.operations
    local_operations = tuple(
        operation
        for operation in operations
        if operation.kind is OperationKind.WRITE_LOCAL
    )
    local_documents = tuple(
        (operation, _local_document(operation)) for operation in local_operations
    )

    evidence: list[ApplyEvidence] = []
    manual_handoffs: list[ApplyEvidence] = []
    for operation in operations:
        if operation.kind is OperationKind.WRITE_LOCAL:
            continue
        if operation.kind is OperationKind.MANUAL:
            handoff = _manual_handoff(operation)
            evidence.append(handoff)
            manual_handoffs.append(handoff)
            continue
        if operation.kind is OperationKind.ROUND_TRIP:
            evidence.append(
                _apply_round_trip(
                    operation,
                    adapters[operation.provider],
                    authority.fingerprint,
                )
            )
            continue
        evidence.append(
            _apply_external_operation(operation, adapters[operation.provider])
        )

    if manual_handoffs:
        return ApplyResult(
            ready=False,
            evidence=tuple(evidence),
            manual_handoffs=tuple(manual_handoffs),
            local_writes=(),
        )

    local_writes: list[ApplyEvidence] = []
    for operation, document in local_documents:
        write_local(operation.target_key, document)
        local_evidence = ApplyEvidence(
            operation_id=operation.operation_id,
            target_key=operation.target_key,
            external_id=operation.target_key,
            observed_fingerprint=operation.desired_fingerprint,
            disposition="written",
        )
        evidence.append(local_evidence)
        local_writes.append(local_evidence)
    return ApplyResult(
        ready=True,
        evidence=tuple(evidence),
        manual_handoffs=(),
        local_writes=tuple(local_writes),
    )

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
from .files import (
    LocalContainerOutcome,
    LocalTransactionError,
    LocalTransactionResult,
    LocalWriteOutcome,
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
    stable_key: str
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

    def delete_disposable(
        self,
        external_id: str,
        stable_key: str,
    ) -> DeletionReceipt:
        """Delete only the disposable record owned by the exact stable key."""
        raise NotImplementedError


class _LocalWriter(Protocol):
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
    ) -> None:
        self.detail = message
        self.operation = operation
        self.operation_id = operation.operation_id if operation is not None else ""
        self.provider = operation.provider if operation is not None else ""
        self.target_key = operation.target_key if operation is not None else ""
        self.cause = cause
        self.partial_evidence = tuple(partial_evidence)
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


def _manual_handoff(operation: SetupOperation) -> ApplyEvidence:
    return ApplyEvidence(
        operation_id=operation.operation_id,
        target_key=operation.target_key,
        external_id="",
        observed_fingerprint=operation.desired_fingerprint,
        disposition="manual_handoff",
    )


def _apply_manual_operation(
    operation: SetupOperation,
    adapter: SetupAdapter,
) -> ApplyEvidence:
    records = _find_records(adapter, operation, operation.target_key)
    if not records:
        return _manual_handoff(operation)
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
    if created:
        _verify_unique_read_back(
            adapter,
            disposable_operation,
            disposable_key,
            record,
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
    else:
        detail = str(error) or type(error).__name__
        cause = error
        operation_context = operation
        nested_evidence = ()
    return SetupApplyError(
        detail,
        operation=operation_context,
        cause=cause,
        partial_evidence=partial_evidence + nested_evidence,
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


def apply_setup(
    approved: ApprovedManifest,
    adapters: Mapping[str, SetupAdapter],
    write_local: _LocalWriter,
    *,
    execution_id: str,
) -> ApplyResult:
    """Apply one approval under an execution-owned mutation authority.

    Callers must reuse ``execution_id`` when retrying the same logical apply and
    must choose a distinct value for every independently concurrent execution.
    The token becomes part of disposable stable keys and deletion ownership.
    """
    if not isinstance(execution_id, str) or not execution_id.strip():
        raise SetupApplyError("execution_id must be a nonblank string")
    execution_token = execution_id.strip()
    authority = _preflight(approved, adapters)
    operations = authority.manifest.operations
    local_operations = tuple(
        operation
        for operation in operations
        if operation.kind is OperationKind.WRITE_LOCAL
    )
    evidence: list[ApplyEvidence] = []
    for operation in local_operations:
        try:
            _local_document(operation)
        except Exception as error:
            raise _contextual_error(error, operation, ()) from error

    for operation in operations:
        if operation.kind is OperationKind.WRITE_LOCAL:
            continue
        try:
            if operation.kind is OperationKind.MANUAL:
                manual_evidence = _apply_manual_operation(
                    operation,
                    adapters[operation.provider],
                )
                evidence.append(manual_evidence)
                if manual_evidence.disposition == "manual_handoff":
                    return ApplyResult(
                        ready=False,
                        evidence=tuple(evidence),
                        manual_handoffs=(manual_evidence,),
                        local_writes=(),
                    )
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
        except Exception as error:
            raise _contextual_error(error, operation, tuple(evidence)) from error

    try:
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
    except Exception as error:
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
    )

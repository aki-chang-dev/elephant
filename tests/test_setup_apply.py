from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

import scripts.workspace_setup.files as setup_files
from scripts.workspace_setup.atomic_switch import AtomicRenameUnavailable

from scripts.workspace_core import (
    CONTRACT_RUNTIME_CAPABILITIES,
    DELIVERY_RUNTIME_CAPABILITIES,
    KNOWLEDGE_RUNTIME_CAPABILITIES,
    STORY_RUNTIME_CAPABILITIES,
    DiagnosticCode,
    ProviderKind,
)
from scripts.workspace_setup import (
    ApprovedManifest,
    BindingReceipt,
    CapabilityLayers,
    Confidence,
    DeletionReceipt,
    DesiredRelationship,
    DesiredStructure,
    Evidence,
    ExternalDiscovery,
    ExternalObject,
    ExternalRecord,
    FingerprintDomain,
    FrozenList,
    FrozenMap,
    ManualHandoff,
    LocalDocumentSlot,
    LocalDocumentTemplate,
    MutationReceipt,
    OperationKind,
    OwnerQuestion,
    ObservedRelationship,
    ProviderSemantics,
    RelationshipDeletionReceipt,
    RelationshipReceipt,
    RepositoryLocalWriter,
    SetupApplyError,
    SetupDiagnostic,
    SetupManifest,
    SetupOperation,
    TopologyConflict,
    apply_setup,
    approve_manifest,
    build_local_documents,
    build_setup_manifest,
    manifest_fingerprint,
    semantics_fingerprint,
)
from scripts.workspace_setup.models import SETUP_MANIFEST_SCHEMA
from scripts.workspace_core import validate_profile, validate_workspace
from scripts.workspace_setup import (
    WORKSPACE_PATH,
    apply_local_write,
    load_rendered_yaml,
    plan_local_writes,
)
from tests.test_setup_files import (
    body_fingerprint,
    build_documents,
    build_git_documents,
    confirmed_topology,
    engineering_settings,
    external_provider_selection,
    product_settings,
)
from scripts.workspace_setup.files import (
    ABSENT_LOCAL_CONTAINER_FINGERPRINT,
    LocalContainerOutcome,
    LocalTransactionResult,
    LocalWriteOutcome,
    fingerprint_local_container,
)


def operation(
    kind: OperationKind,
    *,
    provider: str = "linear",
    target_key: str = "label.product.sample",
    desired_fingerprint: str = "label-v1",
    payload: tuple[tuple[str, object], ...] = (),
    manual_instructions: tuple[str, ...] = (),
) -> SetupOperation:
    if kind is OperationKind.WRITE_LOCAL:
        document = dict(payload).get("document") if payload else None
        if not isinstance(document, str):
            payload = (("document", build_git_documents()[WORKSPACE_PATH]),)
    semantics = ProviderSemantics(
        resource_type=(
            "elephant_setup_round_trip"
            if kind is OperationKind.ROUND_TRIP
            else "setup_structure"
        ),
        fields=FrozenMap((("revision", desired_fingerprint),)),
    )
    logical_provider = (
        ProviderKind.STORY
        if provider == "linear"
        else ProviderKind.PRODUCT_KNOWLEDGE
        if provider == "notion"
        else None
    )
    return SetupOperation(
        operation_id=f"{provider}.{target_key}.{kind.value}",
        provider=provider,
        capability="ensure_label",
        target_key=target_key,
        desired_fingerprint=(
            desired_fingerprint
            if kind is OperationKind.WRITE_LOCAL
            else semantics_fingerprint(semantics)
        ),
        payload=payload,
        kind=kind,
        runtime_required=False,
        logical_provider=logical_provider,
        semantics=None if kind is OperationKind.WRITE_LOCAL else semantics,
        desired_fingerprint_domain=(
            FingerprintDomain.LOCAL_TEMPLATE
            if kind is OperationKind.WRITE_LOCAL
            else FingerprintDomain.PROVIDER_SEMANTICS
        ),
        relationships=(
            DesiredRelationship(
                relationship_type="elephant_setup_binding",
                fields=FrozenMap((("purpose", "capability_probe"),)),
            ),
        ) if kind is OperationKind.ROUND_TRIP else (),
        manual_instructions=(
            manual_instructions
            if manual_instructions
            else ("Complete the exact approved setup structure.",)
            if kind is OperationKind.MANUAL
            else ()
        ),
    )


def observed(
    stable_key: str,
    external_id: str,
    revision: str,
    *,
    resource_type: str = "setup_structure",
) -> ExternalRecord:
    return ExternalRecord(
        stable_key,
        external_id,
        ProviderSemantics(
            resource_type=resource_type,
            fields=FrozenMap((("revision", revision),)),
        ),
    )


def manifest(*operations: SetupOperation) -> SetupManifest:
    return SetupManifest(
        schema=SETUP_MANIFEST_SCHEMA,
        repository_id="repo-sample",
        provider_selection=(
            ("delivery_workspace", "git"),
            ("product_contract_store", "notion"),
            ("product_knowledge_store", "notion"),
            ("story_store", "linear"),
        ),
        products=(),
        domains=(),
        operations=operations,
        diagnostics=(),
        conflicts=(),
        questions=(),
        expected_local_container_fingerprint=ABSENT_LOCAL_CONTAINER_FINGERPRINT,
        registry=(),
        profiles=(),
    )


def approved(value: SetupManifest) -> ApprovedManifest:
    return approve_manifest(value, manifest_fingerprint(value))


def run_apply(
    value: object,
    adapters: dict[str, object],
    writer: object,
    *,
    execution_id: str = "execution-primary",
    resume_handoff: ManualHandoff | None = None,
):
    arguments = {"execution_id": execution_id}
    if resume_handoff is not None:
        arguments["resume_handoff"] = resume_handoff
    return apply_setup(value, adapters, writer, **arguments)


def manual_handoff_for(
    value: ApprovedManifest,
    manual: SetupOperation,
    *,
    execution_id: str = "manual-prior-attempt",
) -> ManualHandoff:
    return ManualHandoff(
        operation_id=manual.operation_id,
        provider=manual.provider,
        capability=manual.capability,
        target_key=manual.target_key,
        diagnostic_code=DiagnosticCode(dict(manual.payload)["diagnostic_code"]),
        expected_fingerprint=manual.desired_fingerprint,
        semantics=manual.semantics,
        instructions=manual.manual_instructions,
        execution_id=execution_id,
        approval_fingerprint=value.fingerprint,
    )


class RecordingAdapter:
    def __init__(
        self,
        provider: str,
        *,
        records: tuple[ExternalRecord, ...] = (),
        corrupt_read_back: bool = False,
        retain_deleted: bool = False,
        events: list[str] | None = None,
    ) -> None:
        self.provider = provider
        self.calls: list[tuple[str, object]] = []
        self.created_keys: list[str] = []
        self.deleted_keys: list[str] = []
        self.corrupt_read_back = corrupt_read_back
        self.retain_deleted = retain_deleted
        self.events = events
        self.records_by_key: dict[str, list[ExternalRecord]] = {}
        self.records_by_id: dict[str, ExternalRecord] = {}
        self.relationships_by_id: dict[str, ObservedRelationship] = {}
        self.relationships_by_key: dict[str, list[ObservedRelationship]] = {}
        for record in records:
            self.records_by_key.setdefault(record.stable_key, []).append(record)
            self.records_by_id[record.external_id] = record

    def _record_call(self, kind: str, value: object) -> None:
        self.calls.append((kind, value))
        if self.events is not None:
            self.events.append(f"adapter:{kind}")

    @property
    def call_kinds(self) -> tuple[str, ...]:
        return tuple(kind for kind, _ in self.calls)

    @property
    def read_count(self) -> int:
        return self.call_kinds.count("read")

    def find(self, stable_key: str) -> tuple[ExternalRecord, ...]:
        self._record_call("find", stable_key)
        return tuple(self.records_by_key.get(stable_key, ()))

    def create(self, setup_operation: SetupOperation) -> MutationReceipt:
        self._record_call("create", setup_operation)
        external_id = f"{self.provider}-{len(self.records_by_id) + 1}"
        record = ExternalRecord(
            setup_operation.target_key,
            external_id,
            setup_operation.semantics,
        )
        self.records_by_key.setdefault(record.stable_key, []).append(record)
        self.records_by_id[record.external_id] = record
        self.created_keys.append(record.stable_key)
        return MutationReceipt(record.external_id)

    def read(self, external_id: str) -> ExternalRecord | None:
        self._record_call("read", external_id)
        record = self.records_by_id.get(external_id)
        if record is not None and self.corrupt_read_back:
            return replace(
                record,
                semantics=ProviderSemantics(
                    "corrupt",
                    FrozenMap((("revision", "corrupt"),)),
                ),
            )
        return record

    def bind_relationship(
        self,
        stable_key: str,
        source: ExternalRecord,
        target: ExternalRecord,
        desired: DesiredRelationship,
    ) -> RelationshipReceipt:
        self._record_call(
            "bind_relationship",
            (stable_key, source.external_id, target.external_id, desired),
        )
        relationship_id = f"{self.provider}-relationship-{len(self.relationships_by_id) + 1}"
        observed_relationship = ObservedRelationship(
            stable_key=stable_key,
            relationship_id=relationship_id,
            source_external_id=source.external_id,
            target_external_id=target.external_id,
            semantics=desired,
        )
        self.relationships_by_id[relationship_id] = observed_relationship
        self.relationships_by_key.setdefault(stable_key, []).append(
            observed_relationship
        )
        return RelationshipReceipt(
            stable_key,
            relationship_id,
            source.external_id,
            target.external_id,
        )

    def find_relationship(
        self,
        stable_key: str,
    ) -> tuple[ObservedRelationship, ...]:
        self._record_call("find_relationship", stable_key)
        return tuple(self.relationships_by_key.get(stable_key, ()))

    def read_relationship(
        self,
        relationship_id: str,
    ) -> ObservedRelationship | None:
        self._record_call("read_relationship", relationship_id)
        return self.relationships_by_id.get(relationship_id)

    def unbind_relationship(
        self,
        receipt: RelationshipReceipt,
    ) -> RelationshipDeletionReceipt:
        self._record_call("unbind_relationship", receipt)
        relationship = self.relationships_by_id.pop(receipt.relationship_id, None)
        if relationship is not None:
            records = self.relationships_by_key.get(relationship.stable_key, [])
            self.relationships_by_key[relationship.stable_key] = [
                item
                for item in records
                if item.relationship_id != relationship.relationship_id
            ]
            if not self.relationships_by_key[relationship.stable_key]:
                self.relationships_by_key.pop(relationship.stable_key)
        return RelationshipDeletionReceipt(
            stable_key=receipt.stable_key,
            relationship_id=receipt.relationship_id,
            source_external_id=receipt.source_external_id,
            target_external_id=receipt.target_external_id,
            deleted=relationship is not None,
        )

    def delete_disposable(
        self,
        external_id: str,
        stable_key: str,
    ) -> DeletionReceipt:
        self._record_call("delete_disposable", (external_id, stable_key))
        record = self.records_by_id.get(external_id)
        if record is None or record.stable_key != stable_key:
            raise RuntimeError("disposable ownership mismatch")
        if record is not None and not self.retain_deleted:
            del self.records_by_id[external_id]
            self.records_by_key[record.stable_key].remove(record)
        self.deleted_keys.append(stable_key)
        return DeletionReceipt(external_id, stable_key)


class InterleavingCreateAdapter(RecordingAdapter):
    """Forces two executions to observe absence before either create returns."""

    def __init__(self, provider: str, *, atomic: bool) -> None:
        super().__init__(provider)
        self.atomic = atomic
        self.initial_find_barrier = threading.Barrier(2)
        self.create_barrier = threading.Barrier(2)
        self.create_lock = threading.Lock()
        self.initial_find_threads: set[int] = set()

    def find(self, stable_key: str) -> tuple[ExternalRecord, ...]:
        records = super().find(stable_key)
        thread_id = threading.get_ident()
        if thread_id not in self.initial_find_threads:
            self.initial_find_threads.add(thread_id)
            self.initial_find_barrier.wait(timeout=5)
        return records

    def create(self, setup_operation: SetupOperation) -> MutationReceipt:
        if self.atomic:
            self._record_call("create", setup_operation)
            with self.create_lock:
                records = self.records_by_key.get(setup_operation.target_key, ())
                if records:
                    receipt = MutationReceipt(records[0].external_id)
                else:
                    receipt = self._insert_created_record(setup_operation)
        else:
            receipt = super().create(setup_operation)
        self.create_barrier.wait(timeout=5)
        return receipt

    def _insert_created_record(
        self,
        setup_operation: SetupOperation,
    ) -> MutationReceipt:
        external_id = f"{self.provider}-{len(self.records_by_id) + 1}"
        record = ExternalRecord(
            setup_operation.target_key,
            external_id,
            setup_operation.semantics,
        )
        self.records_by_key.setdefault(record.stable_key, []).append(record)
        self.records_by_id[record.external_id] = record
        self.created_keys.append(record.stable_key)
        return MutationReceipt(record.external_id)


class DuplicateDuringReadAdapter(RecordingAdapter):
    """Inserts a competing stable-key record after returning read-back."""

    def read(self, external_id: str) -> ExternalRecord | None:
        record = super().read(external_id)
        if record is not None and len(self.records_by_key[record.stable_key]) == 1:
            duplicate = replace(record, external_id=f"{external_id}-duplicate")
            self.records_by_key[record.stable_key].append(duplicate)
            self.records_by_id[duplicate.external_id] = duplicate
        return record


class GhostAfterDeleteAdapter(RecordingAdapter):
    """Deletes the owned ID but leaves a competing record at the stable key."""

    def delete_disposable(
        self,
        external_id: str,
        stable_key: str,
    ) -> DeletionReceipt:
        record = self.records_by_id[external_id]
        receipt = super().delete_disposable(external_id, stable_key)
        ghost = replace(record, external_id=f"{external_id}-ghost")
        self.records_by_key.setdefault(stable_key, []).append(ghost)
        self.records_by_id[ghost.external_id] = ghost
        return receipt


class FailFirstRelationshipReadAdapter(RecordingAdapter):
    def __init__(self, provider: str) -> None:
        super().__init__(provider)
        self.fail_next_relationship_read = True

    def read_relationship(
        self,
        relationship_id: str,
    ) -> ObservedRelationship | None:
        observed = super().read_relationship(relationship_id)
        if self.fail_next_relationship_read:
            self.fail_next_relationship_read = False
            return None
        return observed


class WrongExternalIdReadAdapter(RecordingAdapter):
    def read(self, external_id: str) -> ExternalRecord | None:
        record = super().read(external_id)
        if record is None:
            return None
        return replace(record, external_id=f"{external_id}-different")


class RecordingWriter:
    def __init__(self, events: list[str] | None = None) -> None:
        self.calls: list[tuple[str, object]] = []
        self.container_authorities: list[str] = []
        self.owner_ids: list[str] = []
        self.events = events
        self.preflight_calls: list[tuple[SetupOperation, ...]] = []
        self.cancelled_owner_ids: list[str] = []

    def preflight(
        self,
        operations: tuple[SetupOperation, ...],
        expected_container_fingerprint: str,
        owner_id: str,
    ) -> None:
        self.preflight_calls.append(operations)

    def cancel_preflight(self, owner_id: str) -> None:
        self.cancelled_owner_ids.append(owner_id)

    def __call__(
        self,
        operations: tuple[SetupOperation, ...],
        expected_container_fingerprint: str,
        owner_id: str,
    ) -> LocalTransactionResult:
        self.calls.append(operations)
        self.container_authorities.append(expected_container_fingerprint)
        self.owner_ids.append(owner_id)
        if self.events is not None:
            self.events.append("local:batch")
        return LocalTransactionResult(
            tuple(
                LocalWriteOutcome(
                    operation.operation_id,
                    operation.target_key,
                    ("durable",),
                    operation.expected_byte_fingerprint
                    or operation.desired_fingerprint,
                )
                for operation in operations
            ),
            LocalContainerOutcome(
                "unchanged",
                expected_container_fingerprint,
                expected_container_fingerprint,
                expected_container_fingerprint,
                owner_id,
            ),
        )


class FailingFindAdapter(RecordingAdapter):
    def __init__(self, provider: str, failure: BaseException) -> None:
        super().__init__(provider)
        self.failure = failure

    def find(self, stable_key: str) -> tuple[ExternalRecord, ...]:
        self._record_call("find", stable_key)
        raise self.failure


class FailingWriter(RecordingWriter):
    def __init__(self, failure: BaseException) -> None:
        super().__init__()
        self.failure = failure

    def __call__(
        self,
        operations: tuple[SetupOperation, ...],
        expected_container_fingerprint: str,
        owner_id: str,
    ) -> LocalTransactionResult:
        super().__call__(operations, expected_container_fingerprint, owner_id)
        raise self.failure


class FailingPreflightWriter(RecordingWriter):
    def preflight(
        self,
        operations: tuple[SetupOperation, ...],
        expected_container_fingerprint: str,
        owner_id: str,
    ) -> None:
        super().preflight(operations, expected_container_fingerprint, owner_id)
        raise RuntimeError("platform_unsupported: atomic_local_container_switch")


class WrongFingerprintWriter(RecordingWriter):
    def __call__(
        self,
        operations: tuple[SetupOperation, ...],
        expected_container_fingerprint: str,
        owner_id: str,
    ) -> LocalTransactionResult:
        result = super().__call__(
            operations,
            expected_container_fingerprint,
            owner_id,
        )
        if not result.outcomes:
            return result
        return replace(
            result,
            outcomes=(
                replace(result.outcomes[0], observed_fingerprint="0" * 64),
            ) + result.outcomes[1:],
        )


class WrongOwnerWriter(RecordingWriter):
    def __call__(
        self,
        operations: tuple[SetupOperation, ...],
        expected_container_fingerprint: str,
        owner_id: str,
    ) -> LocalTransactionResult:
        result = super().__call__(
            operations,
            expected_container_fingerprint,
            owner_id,
        )
        return replace(
            result,
            container=replace(result.container, owner_id="different-execution"),
        )


class SetupApplyAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mutation_manifest = manifest(
            operation(OperationKind.CREATE),
            operation(
                OperationKind.WRITE_LOCAL,
                provider="local",
                target_key=".agents/elephant/workspace.yaml",
                payload=(("document", (("schema", "elephant.workspace/v3"),)),),
            ),
        )

    def assert_rejected_without_calls(
        self,
        value: object,
        message: str,
    ) -> None:
        adapter = RecordingAdapter("linear")
        writer = RecordingWriter()
        with self.assertRaisesRegex((TypeError, SetupApplyError), message):
            run_apply(value, {"linear": adapter}, writer)
        self.assertEqual(adapter.calls, [])
        self.assertEqual(writer.calls, [])

    def test_raw_manifest_cannot_mutate_any_authority(self):
        self.assert_rejected_without_calls(self.mutation_manifest, "ApprovedManifest")

    def test_external_record_rejects_blank_stable_key_and_external_id(self):
        semantics = ProviderSemantics(
            "setup_structure",
            FrozenMap((("revision", "v1"),)),
        )
        for stable_key, external_id in (("", "external-1"), ("stable-key", "  ")):
            with self.subTest(stable_key=stable_key, external_id=external_id):
                with self.assertRaisesRegex(ValueError, "stable_key|external_id"):
                    ExternalRecord(stable_key, external_id, semantics)

    def test_local_write_with_provider_fingerprint_domain_cannot_mutate_any_authority(self):
        local_operation = operation(
            OperationKind.WRITE_LOCAL,
            provider="local",
            target_key=".agents/elephant/workspace.yaml",
            payload=(("document", build_git_documents()[WORKSPACE_PATH]),),
        )
        invalid_manifest = manifest(
            replace(
                local_operation,
                desired_fingerprint_domain=FingerprintDomain.PROVIDER_SEMANTICS,
            )
        )

        self.assert_rejected_without_calls(
            approved(invalid_manifest),
            "local template fingerprint domain",
        )

    def test_raw_external_workspace_ids_without_slots_cannot_mutate_any_authority(self):
        raw_local = operation(
            OperationKind.WRITE_LOCAL,
            provider="local",
            target_key=WORKSPACE_PATH,
            payload=(("document", build_documents()[WORKSPACE_PATH]),),
        )

        self.assert_rejected_without_calls(
            approved(manifest(operation(OperationKind.CREATE), raw_local)),
            "external opaque IDs require typed local document slots",
        )

    def test_stale_approval_cannot_mutate_any_authority(self):
        stale = ApprovedManifest(self.mutation_manifest, "0" * 64)
        self.assert_rejected_without_calls(stale, "stale|fingerprint")

    def test_execution_id_is_explicit_and_nonblank_before_any_authority_call(self):
        for execution_id in ("", "   "):
            with self.subTest(execution_id=execution_id):
                adapter = RecordingAdapter("linear")
                writer = RecordingWriter()
                with self.assertRaisesRegex(SetupApplyError, "execution_id"):
                    run_apply(
                        approved(self.mutation_manifest),
                        {"linear": adapter},
                        writer,
                        execution_id=execution_id,
                    )
                self.assertEqual(adapter.calls, [])
                self.assertEqual(writer.calls, [])

    def test_local_container_evidence_must_belong_to_the_execution_owner(self):
        adapter = RecordingAdapter("linear")
        with self.assertRaisesRegex(SetupApplyError, "container.*owner"):
            run_apply(
                approved_create_manifest(),
                {"linear": adapter},
                WrongOwnerWriter(),
                execution_id="execution-primary",
            )

    def test_conflicts_or_questions_cannot_mutate_any_authority(self):
        cases = (
            replace(
                self.mutation_manifest,
                conflicts=(
                    TopologyConflict(
                        "setup_structure.label.product.sample",
                        "setup_structure",
                        ("existing", "desired"),
                        (Evidence("desired", "label.product.sample", "label-v1"),),
                    ),
                ),
            ),
            replace(
                self.mutation_manifest,
                questions=(
                    OwnerQuestion(
                        "product.sample.confirm",
                        "Confirm product",
                        (),
                        Confidence.MEDIUM,
                    ),
                ),
            ),
        )
        for value in cases:
            with self.subTest(blocker="conflict" if value.conflicts else "question"):
                self.assert_rejected_without_calls(approved(value), "conflict|question")

    def test_blocking_runtime_diagnostic_stops_before_first_mutation(self):
        blocked = replace(
            self.mutation_manifest,
            diagnostics=(
                SetupDiagnostic(
                    ProviderKind.STORY,
                    "linear",
                    "create_story",
                    DiagnosticCode.PERMISSION_MISSING,
                    True,
                ),
            ),
        )
        self.assert_rejected_without_calls(approved(blocked), "blocking")

    def test_all_required_adapters_are_resolved_before_first_mutation(self):
        two_provider_manifest = replace(
            self.mutation_manifest,
            operations=(
                operation(OperationKind.CREATE),
                operation(OperationKind.CREATE, provider="notion", target_key="database.sample"),
            ),
        )
        linear = RecordingAdapter("linear")
        writer = RecordingWriter()
        with self.assertRaisesRegex(SetupApplyError, "adapter.*notion|notion.*adapter"):
            run_apply(approved(two_provider_manifest), {"linear": linear}, writer)
        self.assertEqual(linear.calls, [])
        self.assertEqual(writer.calls, [])

    def test_manual_adapter_is_resolved_before_prior_external_work(self):
        value = approved(manifest(
            operation(
                OperationKind.REUSE,
                provider="linear",
                target_key="team.delivery",
                desired_fingerprint="team-v1",
            ),
            operation(
                OperationKind.MANUAL,
                provider="notion",
                target_key="view.sample",
                desired_fingerprint="view-v1",
                payload=(
                    ("diagnostic_code", "platform_unsupported"),
                    ("read_back_required", True),
                ),
            ),
        ))
        linear = RecordingAdapter(
            "linear",
            records=(observed("team.delivery", "linear-1", "team-v1"),),
        )

        with self.assertRaisesRegex(SetupApplyError, "adapter.*notion|notion.*adapter"):
            run_apply(value, {"linear": linear}, RecordingWriter())

        self.assertEqual(linear.calls, [])

    def test_all_adapter_protocols_are_validated_before_first_mutation(self):
        class IncompleteAdapter:
            provider = "notion"

        two_provider_manifest = manifest(
            operation(OperationKind.CREATE),
            operation(
                OperationKind.CREATE,
                provider="notion",
                target_key="database.sample",
            ),
        )
        linear = RecordingAdapter("linear")
        writer = RecordingWriter()

        with self.assertRaisesRegex(SetupApplyError, "adapter.*notion|notion.*adapter"):
            run_apply(
                approved(two_provider_manifest),
                {"linear": linear, "notion": IncompleteAdapter()},
                writer,
            )

        self.assertEqual(linear.calls, [])
        self.assertEqual(writer.calls, [])

    def test_untyped_external_operation_is_rejected_before_adapter_calls(self):
        untyped = SetupOperation(
            operation_id="linear.label.product.sample.create",
            provider="linear",
            capability="ensure_label",
            target_key="label.product.sample",
            desired_fingerprint="opaque-fingerprint",
            payload=(),
            kind=OperationKind.CREATE,
            runtime_required=False,
        )
        value = approved(manifest(
            untyped,
            operation(
                OperationKind.WRITE_LOCAL,
                provider="local",
                target_key=WORKSPACE_PATH,
            ),
        ))
        adapter = RecordingAdapter("linear")
        writer = RecordingWriter()

        with self.assertRaisesRegex(SetupApplyError, "typed provider semantics"):
            run_apply(value, {"linear": adapter}, writer)

        self.assertEqual(adapter.calls, [])
        self.assertEqual(writer.calls, [])

    def test_invalid_local_schema_stops_before_first_adapter_call(self):
        adapter = RecordingAdapter("linear")
        writer = RecordingWriter()
        value = approved(manifest(
            operation(OperationKind.CREATE),
            operation(
                OperationKind.WRITE_LOCAL,
                provider="local",
                target_key=".agents/elephant/workspace.yaml",
                payload=(("document", "{}\n"),),
            ),
        ))

        with self.assertRaisesRegex(SetupApplyError, "invalid document|schema"):
            run_apply(value, {"linear": adapter}, writer)

        self.assertEqual(adapter.calls, [])
        self.assertEqual(writer.calls, [])

    def test_local_backend_preflight_failure_stops_before_first_adapter_call(self):
        adapter = RecordingAdapter("linear")
        writer = FailingPreflightWriter()

        with self.assertRaisesRegex(SetupApplyError, "platform_unsupported"):
            run_apply(approved_create_manifest(), {"linear": adapter}, writer)

        self.assertEqual(adapter.calls, [])
        self.assertEqual(writer.calls, [])

    def test_repository_writer_rejects_unsupported_filesystem_before_adapter_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = tuple(sorted(path.name for path in root.iterdir()))
            adapter = RecordingAdapter("linear")
            writer = RepositoryLocalWriter(root)

            with mock.patch(
                "scripts.workspace_setup.atomic_switch.atomic_exchange",
                side_effect=AtomicRenameUnavailable("filesystem unsupported"),
            ), self.assertRaisesRegex(SetupApplyError, "platform_unsupported"):
                run_apply(approved_create_manifest(), {"linear": adapter}, writer)

            self.assertEqual(adapter.calls, [])
            self.assertEqual(tuple(sorted(path.name for path in root.iterdir())), before)

    def test_repository_writer_commits_to_the_preflight_root_identity_after_path_swap(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "repository"
            approved_root = base / "approved-repository"
            root.mkdir()

            class RootSwappingAdapter(RecordingAdapter):
                def create(self, setup_operation: SetupOperation) -> MutationReceipt:
                    root.rename(approved_root)
                    root.mkdir()
                    return super().create(setup_operation)

            result = run_apply(
                approved_create_manifest(),
                {"linear": RootSwappingAdapter("linear")},
                RepositoryLocalWriter(root),
                execution_id="root-identity-swap",
            )

            self.assertTrue(result.ready)
            self.assertTrue((approved_root / ".agents").is_dir())
            self.assertFalse((root / ".agents").exists())

    def test_repository_writer_preflight_binds_the_approved_local_body(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = RepositoryLocalWriter(root)
            owner_id = "preflight-body-authority"
            original = operation(
                OperationKind.WRITE_LOCAL,
                provider="local",
                target_key=WORKSPACE_PATH,
                payload=(("document", build_git_documents()[WORKSPACE_PATH]),),
            )
            changed_body = dict(original.payload)["document"].replace(
                '"repo-sample"',
                '"repo-substituted"',
            )
            changed = replace(
                original,
                payload=(("document", changed_body),),
                expected_byte_fingerprint=hashlib.sha256(
                    changed_body.encode("utf-8")
                ).hexdigest(),
            )

            writer.preflight(
                (original,),
                ABSENT_LOCAL_CONTAINER_FINGERPRINT,
                owner_id,
            )
            with self.assertRaisesRegex(
                ValueError,
                "does not match preflight authority",
            ):
                writer(
                    (changed,),
                    ABSENT_LOCAL_CONTAINER_FINGERPRINT,
                    owner_id,
                )

            self.assertFalse((root / ".agents").exists())

    def test_cancellation_closes_and_discards_local_preflight_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = RepositoryLocalWriter(root)
            execution_id = "cancelled-after-preflight"
            captured_descriptors: list[int] = []

            class InterruptingAdapter(RecordingAdapter):
                def create(
                    self,
                    setup_operation: SetupOperation,
                ) -> MutationReceipt:
                    captured_descriptors.append(
                        writer._preflights[execution_id].descriptor
                    )
                    raise KeyboardInterrupt("cancel setup")

            try:
                with self.assertRaises(KeyboardInterrupt):
                    run_apply(
                        approved_create_manifest(),
                        {"linear": InterruptingAdapter("linear")},
                        writer,
                        execution_id=execution_id,
                    )

                self.assertEqual(writer._preflights, {})
                self.assertEqual(len(captured_descriptors), 1)
                with self.assertRaises(OSError):
                    os.fstat(captured_descriptors[0])
            finally:
                writer.cancel_preflight(execution_id)

    def test_preflight_publication_interruption_preserves_exception_and_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = RepositoryLocalWriter(root)
            adapter = RecordingAdapter("linear")
            execution_id = "preflight-publication-interrupted"
            original_replace = writer._replace_preflight

            def interrupt_after_publication(owner_id, receipt):
                original_replace(owner_id, receipt)
                raise KeyboardInterrupt("interrupt after preflight publication")

            with mock.patch.object(
                writer,
                "_replace_preflight",
                side_effect=interrupt_after_publication,
            ), self.assertRaisesRegex(
                KeyboardInterrupt,
                "after preflight publication",
            ):
                run_apply(
                    approved_create_manifest(),
                    {"linear": adapter},
                    writer,
                    execution_id=execution_id,
                )

            self.assertEqual(writer._preflights, {})
            self.assertEqual(adapter.calls, [])

            retried = run_apply(
                approved_create_manifest(),
                {"linear": adapter},
                writer,
                execution_id=execution_id,
            )

            self.assertTrue(retried.ready)
            self.assertEqual(writer._preflights, {})

    def test_same_owner_preflight_replacement_interruption_closes_prior_descriptor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = RepositoryLocalWriter(root)
            execution_id = "same-owner-preflight-replacement-interrupted"
            value = approved_create_manifest()
            local_operations = tuple(
                operation
                for operation in value.manifest.operations
                if operation.kind is OperationKind.WRITE_LOCAL
            )
            writer.preflight(
                local_operations,
                value.manifest.expected_local_container_fingerprint,
                execution_id,
            )
            prior_receipt = writer._preflights[execution_id]
            prior_descriptor = prior_receipt.descriptor
            original_detach = writer._detach_descriptor

            def interrupt_after_prior_detach(receipt):
                descriptor = original_detach(receipt)
                if receipt is prior_receipt:
                    raise KeyboardInterrupt("interrupt after prior descriptor detach")
                return descriptor

            try:
                with mock.patch.object(
                    writer,
                    "_detach_descriptor",
                    side_effect=interrupt_after_prior_detach,
                ), self.assertRaisesRegex(
                    KeyboardInterrupt,
                    "after prior descriptor detach",
                ):
                    writer.preflight(
                        local_operations,
                        value.manifest.expected_local_container_fingerprint,
                        execution_id,
                    )

                self.assertEqual(writer._preflights, {})
                with self.assertRaises(OSError):
                    os.fstat(prior_descriptor)
            finally:
                writer.cancel_preflight(execution_id)
                try:
                    os.close(prior_descriptor)
                except OSError:
                    pass

    def test_commit_stage_cancellation_propagates_after_preflight_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = RepositoryLocalWriter(root)

            with mock.patch(
                "scripts.workspace_setup.files._stage_write",
                side_effect=KeyboardInterrupt("cancel during local commit"),
            ), self.assertRaisesRegex(
                KeyboardInterrupt,
                "during local commit",
            ):
                run_apply(
                    approved_create_manifest(),
                    {"linear": RecordingAdapter("linear")},
                    writer,
                    execution_id="commit-stage-cancelled",
                )

            self.assertEqual(writer._preflights, {})
            self.assertFalse((root / ".agents").exists())


def approved_create_manifest() -> ApprovedManifest:
    return approved(
        manifest(
            operation(OperationKind.CREATE),
            operation(
                OperationKind.WRITE_LOCAL,
                provider="local",
                target_key=".agents/elephant/workspace.yaml",
                desired_fingerprint="workspace-v1",
                payload=(("document", build_git_documents()[WORKSPACE_PATH]),),
            ),
        )
    )


class SetupApplyMutationTests(unittest.TestCase):
    def test_verified_read_back_materializes_approved_local_slot_and_byte_hash(self):
        source = operation(
            OperationKind.CREATE,
            target_key="binding.linear.workspace",
            desired_fingerprint="binding-v1",
        )
        slot = LocalDocumentSlot(
            slot_id="linear.workspace_id",
            provider="linear",
            stable_key=source.target_key,
            source_operation_id=source.operation_id,
        )
        body = build_git_documents()[WORKSPACE_PATH].replace(
            json.dumps("repo-sample"),
            json.dumps(slot.placeholder),
        )
        local = replace(
            operation(
                OperationKind.WRITE_LOCAL,
                provider="local",
                target_key=WORKSPACE_PATH,
                payload=(("document", body),),
            ),
            local_slots=(slot,),
        )
        value = approved(manifest(source, local))
        adapter = RecordingAdapter("linear")
        writer = RecordingWriter()

        result = run_apply(value, {"linear": adapter}, writer)

        materialized = writer.calls[0][0]
        materialized_body = dict(materialized.payload)["document"]
        expected_bytes = hashlib.sha256(materialized_body.encode("utf-8")).hexdigest()
        self.assertIn('"id": "linear-1"', materialized_body)
        self.assertNotIn(slot.placeholder, materialized_body)
        self.assertEqual(materialized.expected_byte_fingerprint, expected_bytes)
        self.assertEqual(
            result.binding_receipts,
            (
                BindingReceipt(
                    slot_id=slot.slot_id,
                    source_operation_id=source.operation_id,
                    provider="linear",
                    stable_key=source.target_key,
                    external_id="linear-1",
                    observed_fingerprint=source.desired_fingerprint,
                ),
            ),
        )
        self.assertEqual(result.local_writes[0].observed_fingerprint, expected_bytes)

    def test_reserved_slot_external_id_cannot_satisfy_local_materialization(self):
        source = operation(
            OperationKind.REUSE,
            target_key="binding.linear.workspace",
            desired_fingerprint="binding-v1",
        )
        slot = LocalDocumentSlot(
            slot_id="linear.workspace_id",
            provider="linear",
            stable_key=source.target_key,
            source_operation_id=source.operation_id,
        )
        body = build_git_documents()[WORKSPACE_PATH].replace(
            json.dumps("repo-sample"),
            json.dumps(slot.placeholder),
        )
        local = replace(
            operation(
                OperationKind.WRITE_LOCAL,
                provider="local",
                target_key=WORKSPACE_PATH,
                payload=(("document", body),),
            ),
            local_slots=(slot,),
        )
        value = approved(manifest(source, local))
        adapter = RecordingAdapter(
            "linear",
            records=(
                ExternalRecord(
                    source.target_key,
                    slot.placeholder,
                    source.semantics,
                ),
            ),
        )
        writer = RecordingWriter()

        with self.assertRaisesRegex(SetupApplyError, "reserved|slot"):
            run_apply(value, {"linear": adapter}, writer)

        self.assertEqual(writer.calls, [])

    def test_identical_preflight_body_cannot_authorize_unresolved_local_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = RepositoryLocalWriter(root)
            slot = LocalDocumentSlot(
                slot_id="linear.workspace_id",
                provider="linear",
                stable_key="binding.linear.workspace",
                source_operation_id="linear.binding.linear.workspace.reuse",
            )
            body = build_git_documents()[WORKSPACE_PATH].replace(
                json.dumps("repo-sample"),
                json.dumps(slot.placeholder),
            )
            local = replace(
                operation(
                    OperationKind.WRITE_LOCAL,
                    provider="local",
                    target_key=WORKSPACE_PATH,
                    payload=(("document", body),),
                ),
                local_slots=(slot,),
            )
            committed = replace(
                local,
                expected_byte_fingerprint=hashlib.sha256(
                    body.encode("utf-8")
                ).hexdigest(),
            )
            owner_id = "unresolved-identical-slot"

            try:
                writer.preflight(
                    (local,),
                    ABSENT_LOCAL_CONTAINER_FINGERPRINT,
                    owner_id,
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "preflight authority",
                ):
                    writer(
                        (committed,),
                        ABSENT_LOCAL_CONTAINER_FINGERPRINT,
                        owner_id,
                    )
            finally:
                writer.cancel_preflight(owner_id)

            self.assertFalse((root / ".agents").exists())

    def test_mismatched_local_byte_evidence_blocks_readiness(self):
        writer = WrongFingerprintWriter()

        with self.assertRaisesRegex(SetupApplyError, "byte fingerprint"):
            run_apply(
                approved_create_manifest(),
                {"linear": RecordingAdapter("linear")},
                writer,
            )
    def run_concurrent_creates(
        self,
        adapter: RecordingAdapter,
    ) -> tuple[list[object], list[BaseException], list[RecordingWriter]]:
        value = approved_create_manifest()
        results: list[object] = []
        errors: list[BaseException] = []
        writers = [RecordingWriter(), RecordingWriter()]

        def execute(index: int) -> None:
            try:
                results.append(run_apply(
                    value,
                    {"linear": adapter},
                    writers[index],
                    execution_id=f"concurrent-{index}",
                ))
            except BaseException as error:
                errors.append(error)

        threads = tuple(
            threading.Thread(target=execute, args=(index,)) for index in range(2)
        )
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive(), "interleaving test deadlocked")
        return results, errors, writers

    def test_atomic_get_or_create_conforms_under_an_absent_snapshot_race(self):
        adapter = InterleavingCreateAdapter("linear", atomic=True)

        results, errors, writers = self.run_concurrent_creates(adapter)

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result.ready for result in results))
        self.assertEqual(len(adapter.records_by_key["label.product.sample"]), 1)
        self.assertEqual(adapter.created_keys, ["label.product.sample"])
        self.assertTrue(all(len(writer.calls) == 1 for writer in writers))

    def test_non_atomic_interleaving_is_detected_before_readiness_or_local_write(self):
        adapter = InterleavingCreateAdapter("linear", atomic=False)

        results, errors, writers = self.run_concurrent_creates(adapter)

        self.assertEqual(results, [])
        self.assertEqual(len(errors), 2)
        self.assertTrue(all(isinstance(error, SetupApplyError) for error in errors))
        self.assertTrue(all("duplicate" in str(error) for error in errors))
        self.assertEqual(len(adapter.records_by_key["label.product.sample"]), 2)
        self.assertTrue(all(writer.calls == [] for writer in writers))

    def test_create_is_stable_key_idempotent_and_read_back_verified(self):
        adapter = RecordingAdapter("linear")
        value = approved_create_manifest()

        first = run_apply(value, {"linear": adapter}, RecordingWriter())
        second = run_apply(value, {"linear": adapter}, RecordingWriter())

        self.assertTrue(first.ready)
        self.assertTrue(second.ready)
        self.assertEqual(adapter.created_keys.count("label.product.sample"), 1)
        self.assertGreaterEqual(adapter.read_count, 2)
        self.assertEqual(
            first.evidence[0].observed_fingerprint,
            value.manifest.operations[0].desired_fingerprint,
        )
        self.assertEqual(second.evidence[0].disposition, "reused")

    def test_mismatched_read_back_stops_before_local_write(self):
        adapter = RecordingAdapter("linear", corrupt_read_back=True)
        writer = RecordingWriter()

        with self.assertRaisesRegex(SetupApplyError, "read-back"):
            run_apply(approved_create_manifest(), {"linear": adapter}, writer)

        self.assertEqual(writer.calls, [])

    def test_reuse_and_verify_require_unique_semantic_read_back(self):
        for kind in (OperationKind.REUSE, OperationKind.VERIFY):
            with self.subTest(kind=kind):
                record = observed("team.delivery", "linear-1", "team-v1")
                adapter = DuplicateDuringReadAdapter("linear", records=(record,))
                writer = RecordingWriter()
                value = approved(manifest(operation(
                    kind,
                    target_key="team.delivery",
                    desired_fingerprint="team-v1",
                )))

                with self.assertRaisesRegex(SetupApplyError, "duplicate"):
                    run_apply(value, {"linear": adapter}, writer)

                self.assertEqual(adapter.call_kinds, ("find", "read", "find"))
                self.assertEqual(writer.calls, [])

    def test_duplicate_or_semantically_mismatched_records_stop_before_local_write(self):
        cases = (
            (
                "duplicate",
                (
                    observed("team.delivery", "linear-1", "team-v1"),
                    observed("team.delivery", "linear-2", "team-v1"),
                ),
                "duplicate|exactly one",
            ),
            (
                "mismatch",
                (observed("team.delivery", "linear-1", "team-old"),),
                "semantic|fingerprint",
            ),
        )
        for name, records, message in cases:
            with self.subTest(name=name):
                adapter = RecordingAdapter("linear", records=records)
                writer = RecordingWriter()
                value = approved(manifest(
                    operation(
                        OperationKind.REUSE,
                        target_key="team.delivery",
                        desired_fingerprint="team-v1",
                    ),
                    operation(
                        OperationKind.WRITE_LOCAL,
                        provider="local",
                        target_key=".agents/elephant/workspace.yaml",
                        payload=(("document", ()),),
                    ),
                ))

                with self.assertRaisesRegex(SetupApplyError, message):
                    run_apply(value, {"linear": adapter}, writer)

                self.assertEqual(writer.calls, [])
                self.assertNotIn("delete_disposable", adapter.call_kinds)

    def test_manual_handoff_resumes_with_same_approval_and_new_execution_id(self):
        manual = operation(
            OperationKind.MANUAL,
            provider="notion",
            target_key="view.sample",
            desired_fingerprint="view-v1",
            payload=(
                ("diagnostic_code", "platform_unsupported"),
                ("read_back_required", True),
            ),
        )
        value = approved(manifest(
            manual,
            operation(
                OperationKind.WRITE_LOCAL,
                provider="local",
                target_key=".agents/elephant/workspace.yaml",
                payload=(("document", ()),),
            ),
        ))
        adapter = RecordingAdapter("notion")
        writer = RecordingWriter()

        first = run_apply(
            value,
            {"notion": adapter},
            writer,
            execution_id="manual-first-attempt",
        )

        self.assertFalse(first.ready)
        self.assertEqual(len(first.manual_handoffs), 1)
        self.assertIsInstance(first.manual_handoffs[0], ManualHandoff)
        self.assertEqual(first.manual_handoffs[0].disposition, "manual_handoff")
        self.assertEqual(
            first.manual_handoffs[0].expected_fingerprint,
            manual.desired_fingerprint,
        )
        self.assertEqual(first.manual_handoffs[0].semantics, manual.semantics)
        self.assertEqual(
            first.manual_handoffs[0].execution_id,
            "manual-first-attempt",
        )
        self.assertEqual(
            first.manual_handoffs[0].approval_fingerprint,
            value.fingerprint,
        )
        self.assertEqual(
            first.manual_handoffs[0].instructions,
            manual.manual_instructions,
        )
        self.assertEqual(adapter.call_kinds, ("find",))
        self.assertFalse(
            any(item.operation_id == manual.operation_id for item in first.evidence)
        )
        self.assertEqual(writer.calls, [])
        self.assertEqual(writer.cancelled_owner_ids, ["manual-first-attempt"])

        completed = observed("view.sample", "notion-view-1", "view-v1")
        adapter.records_by_key[completed.stable_key] = [completed]
        adapter.records_by_id[completed.external_id] = completed
        continued_writer = RecordingWriter()

        with self.assertRaisesRegex(SetupApplyError, "prior manual handoff"):
            run_apply(
                value,
                {"notion": adapter},
                RecordingWriter(),
                execution_id="manual-resumed-without-handoff",
            )

        with self.assertRaisesRegex(SetupApplyError, "distinct.*execution"):
            run_apply(
                value,
                {"notion": adapter},
                RecordingWriter(),
                execution_id="manual-first-attempt",
                resume_handoff=first.manual_handoffs[0],
            )

        second = run_apply(
            value,
            {"notion": adapter},
            continued_writer,
            execution_id="manual-resumed-attempt",
            resume_handoff=first.manual_handoffs[0],
        )

        self.assertTrue(second.ready)
        self.assertEqual(second.manual_handoffs, ())
        self.assertEqual(second.evidence[0].operation_id, manual.operation_id)
        self.assertEqual(second.evidence[0].disposition, "manual_completed")
        self.assertEqual(second.evidence[0].external_id, completed.external_id)
        self.assertEqual(
            second.evidence[0].observed_fingerprint,
            manual.desired_fingerprint,
        )
        self.assertEqual(
            adapter.call_kinds,
            ("find", "find", "find", "read", "find"),
        )
        self.assertEqual(len(continued_writer.calls), 1)
        self.assertEqual(continued_writer.owner_ids, ["manual-resumed-attempt"])

    def test_sequential_manual_prerequisites_complete_across_three_attempts(self):
        first_manual = operation(
            OperationKind.MANUAL,
            provider="notion",
            target_key="view.alpha",
            desired_fingerprint="view-alpha-v1",
            payload=(
                ("diagnostic_code", "platform_unsupported"),
                ("read_back_required", True),
            ),
        )
        second_manual = operation(
            OperationKind.MANUAL,
            provider="notion",
            target_key="view.beta",
            desired_fingerprint="view-beta-v1",
            payload=(
                ("diagnostic_code", "platform_unsupported"),
                ("read_back_required", True),
            ),
        )
        value = approved(manifest(
            first_manual,
            second_manual,
            operation(
                OperationKind.WRITE_LOCAL,
                provider="local",
                target_key=WORKSPACE_PATH,
                payload=(("document", build_git_documents()[WORKSPACE_PATH]),),
            ),
        ))
        adapter = RecordingAdapter("notion")

        first = run_apply(
            value,
            {"notion": adapter},
            RecordingWriter(),
            execution_id="manual-alpha-handoff",
        )
        self.assertEqual(
            first.manual_handoffs[0].operation_id,
            first_manual.operation_id,
        )
        alpha = observed("view.alpha", "notion-alpha", "view-alpha-v1")
        adapter.records_by_key[alpha.stable_key] = [alpha]
        adapter.records_by_id[alpha.external_id] = alpha

        second = run_apply(
            value,
            {"notion": adapter},
            RecordingWriter(),
            execution_id="manual-beta-handoff",
            resume_handoff=first.manual_handoffs[0],
        )
        self.assertEqual(
            second.manual_handoffs[0].operation_id,
            second_manual.operation_id,
        )
        self.assertEqual(
            second.manual_handoffs[0].completed_operation_ids,
            (first_manual.operation_id,),
        )
        beta = observed("view.beta", "notion-beta", "view-beta-v1")
        adapter.records_by_key[beta.stable_key] = [beta]
        adapter.records_by_id[beta.external_id] = beta

        third = run_apply(
            value,
            {"notion": adapter},
            RecordingWriter(),
            execution_id="manual-all-complete",
            resume_handoff=second.manual_handoffs[0],
        )

        self.assertTrue(third.ready)
        self.assertEqual(third.manual_handoffs, ())
        self.assertEqual(
            tuple(
                item.operation_id
                for item in third.evidence
                if item.disposition == "manual_completed"
            ),
            (first_manual.operation_id, second_manual.operation_id),
        )

    def test_manual_completion_duplicate_inserted_during_read_stops_before_local_write(self):
        prior = observed("team.delivery", "linear-team-1", "team-v1")
        completed = observed("view.sample", "notion-view-1", "view-v1")
        manual = operation(
            OperationKind.MANUAL,
            provider="notion",
            target_key="view.sample",
            desired_fingerprint="view-v1",
            payload=(("diagnostic_code", "platform_unsupported"),),
        )
        value = approved(manifest(
            operation(
                OperationKind.REUSE,
                provider="linear",
                target_key="team.delivery",
                desired_fingerprint="team-v1",
            ),
            manual,
            operation(
                OperationKind.WRITE_LOCAL,
                provider="local",
                target_key=".agents/elephant/workspace.yaml",
                payload=(("document", ()),),
            ),
        ))
        notion = DuplicateDuringReadAdapter("notion", records=(completed,))
        writer = RecordingWriter()

        with self.assertRaisesRegex(SetupApplyError, "duplicate") as raised:
            run_apply(
                value,
                {
                    "linear": RecordingAdapter("linear", records=(prior,)),
                    "notion": notion,
                },
                writer,
                execution_id="manual-race",
                resume_handoff=manual_handoff_for(value, manual),
            )

        self.assertEqual(raised.exception.operation, manual)
        self.assertEqual(raised.exception.provider, "notion")
        self.assertEqual(raised.exception.target_key, "view.sample")
        self.assertEqual(len(raised.exception.partial_evidence), 1)
        self.assertEqual(
            raised.exception.partial_evidence[0].disposition,
            "reused",
        )
        self.assertEqual(notion.call_kinds, ("find", "read", "find"))
        self.assertEqual(writer.calls, [])

    def test_invalid_manual_completion_stops_with_contextual_partial_evidence(self):
        prior = observed("team.delivery", "linear-team-1", "team-v1")
        manual = operation(
            OperationKind.MANUAL,
            provider="notion",
            target_key="view.sample",
            desired_fingerprint="view-v1",
            payload=(
                ("diagnostic_code", "platform_unsupported"),
                ("read_back_required", True),
            ),
        )
        value = approved(manifest(
            operation(
                OperationKind.REUSE,
                provider="linear",
                target_key="team.delivery",
                desired_fingerprint="team-v1",
            ),
            manual,
            operation(
                OperationKind.WRITE_LOCAL,
                provider="local",
                target_key=".agents/elephant/workspace.yaml",
                payload=(("document", ()),),
            ),
        ))
        cases = (
            (
                "duplicate",
                RecordingAdapter(
                    "notion",
                    records=(
                        observed("view.sample", "notion-view-1", "view-v1"),
                        observed("view.sample", "notion-view-2", "view-v1"),
                    ),
                ),
                "duplicate",
            ),
            (
                "mismatch",
                RecordingAdapter(
                    "notion",
                    records=(
                        observed("view.sample", "notion-view-1", "view-old"),
                    ),
                ),
                "fingerprint",
            ),
            (
                "read-back fingerprint mismatch",
                RecordingAdapter(
                    "notion",
                    records=(
                        observed("view.sample", "notion-view-1", "view-v1"),
                    ),
                    corrupt_read_back=True,
                ),
                "read-back.*fingerprint",
            ),
            (
                "read-back external ID mismatch",
                WrongExternalIdReadAdapter(
                    "notion",
                    records=(
                        observed("view.sample", "notion-view-1", "view-v1"),
                    ),
                ),
                "external ID",
            ),
            (
                "read failure",
                RecordingAdapter(
                    "notion",
                    records=(
                        observed("view.sample", "notion-view-1", "view-v1"),
                    ),
                ),
                "read-back",
            ),
        )
        cases[-1][1].records_by_id.clear()

        for name, notion, message in cases:
            with self.subTest(name=name):
                writer = RecordingWriter()
                linear = RecordingAdapter("linear", records=(prior,))

                with self.assertRaisesRegex(SetupApplyError, message) as raised:
                    run_apply(
                        value,
                        {"linear": linear, "notion": notion},
                        writer,
                        execution_id="manual-invalid",
                        resume_handoff=manual_handoff_for(value, manual),
                    )

                self.assertEqual(raised.exception.operation, manual)
                self.assertEqual(raised.exception.provider, "notion")
                self.assertEqual(raised.exception.target_key, "view.sample")
                self.assertEqual(len(raised.exception.partial_evidence), 1)
                self.assertEqual(
                    raised.exception.partial_evidence[0].disposition,
                    "reused",
                )
                if name == "mismatch":
                    self.assertEqual(
                        raised.exception.observed_snapshot,
                        notion.records_by_key[manual.target_key][0],
                    )
                self.assertEqual(writer.calls, [])

    def test_local_writes_receive_exact_documents_after_external_read_back(self):
        events: list[str] = []
        adapter = RecordingAdapter("linear", events=events)
        writer = RecordingWriter(events)

        result = run_apply(approved_create_manifest(), {"linear": adapter}, writer)

        local_operation = approved_create_manifest().manifest.operations[-1]
        self.assertEqual(writer.calls[0][0].operation_id, local_operation.operation_id)
        self.assertEqual(
            dict(writer.calls[0][0].payload)["document"],
            dict(local_operation.payload)["document"],
        )
        self.assertEqual(
            writer.calls[0][0].expected_byte_fingerprint,
            hashlib.sha256(
                dict(local_operation.payload)["document"].encode("utf-8")
            ).hexdigest(),
        )
        self.assertEqual(
            writer.container_authorities,
            [ABSENT_LOCAL_CONTAINER_FINGERPRINT],
        )
        self.assertEqual(writer.owner_ids, ["execution-primary"])
        self.assertEqual(events[-1], "local:batch")
        self.assertLess(events.index("adapter:read"), events.index("local:batch"))
        self.assertEqual(result.local_writes[0].target_key, ".agents/elephant/workspace.yaml")
        self.assertEqual(result.local_writes[0].disposition, "durable")
        self.assertEqual(result.local_writes[-1].target_key, ".agents")
        self.assertEqual(result.local_writes[-1].disposition, "unchanged")
        self.assertEqual(result.local_writes[-1].external_id, "execution-primary")


def approved_round_trip_manifest() -> ApprovedManifest:
    return approved(
        manifest(
            operation(
                OperationKind.ROUND_TRIP,
                provider="notion",
                target_key="setup.round_trip.notion",
                desired_fingerprint="round-trip-v1",
                payload=(("disposable", True), ("read_back_required", True)),
            ),
            operation(
                OperationKind.WRITE_LOCAL,
                provider="local",
                target_key=".agents/elephant/workspace.yaml",
                desired_fingerprint="workspace-v1",
                payload=(("document", (("schema", "elephant.workspace/v3"),)),),
            ),
        )
    )


class SetupRoundTripTests(unittest.TestCase):
    def test_round_trip_retry_reuses_and_cleans_interrupted_relationship(self):
        adapter = FailFirstRelationshipReadAdapter("notion")
        value = approved_round_trip_manifest()
        execution_id = "round-trip-relationship-retry"

        with self.assertRaisesRegex(
            SetupApplyError,
            "relationship read-back",
        ):
            run_apply(
                value,
                {"notion": adapter},
                RecordingWriter(),
                execution_id=execution_id,
            )
        self.assertEqual(len(adapter.relationships_by_id), 1)

        result = run_apply(
            value,
            {"notion": adapter},
            RecordingWriter(),
            execution_id=execution_id,
        )

        self.assertTrue(result.ready)
        self.assertEqual(adapter.relationships_by_id, {})

    def test_round_trip_creates_reads_deletes_and_verifies_absence(self):
        adapter = RecordingAdapter("notion")
        value = approved_round_trip_manifest()
        execution_id = "round-trip-primary"

        result = run_apply(
            value,
            {"notion": adapter},
            RecordingWriter(),
            execution_id=execution_id,
        )

        self.assertTrue(result.ready)
        self.assertEqual(
            adapter.call_kinds,
            (
                "find",
                "create",
                "read",
                "find",
                "find_relationship",
                "bind_relationship",
                "read_relationship",
                "find_relationship",
                "unbind_relationship",
                "read_relationship",
                "find_relationship",
                "delete_disposable",
                "read",
                "find",
            ),
        )
        disposable_key = (
            f"setup.round_trip.notion.{value.fingerprint}.{execution_id}"
        )
        self.assertEqual(adapter.created_keys, [disposable_key])
        self.assertEqual(adapter.deleted_keys, [disposable_key])
        self.assertEqual(result.evidence[0].target_key, disposable_key)
        self.assertEqual(result.evidence[0].disposition, "round_trip_cleaned")

    def test_cleanup_rejects_a_same_key_ghost_without_deleting_it(self):
        adapter = GhostAfterDeleteAdapter("notion")
        writer = RecordingWriter()

        with self.assertRaisesRegex(SetupApplyError, "stable-key.*cleanup|cleanup.*stable-key"):
            run_apply(
                approved_round_trip_manifest(),
                {"notion": adapter},
                writer,
                execution_id="round-trip-ghost",
            )

        self.assertEqual(len(adapter.deleted_keys), 1)
        ghost_key = adapter.deleted_keys[0]
        self.assertEqual(len(adapter.records_by_key[ghost_key]), 1)
        self.assertTrue(adapter.records_by_key[ghost_key][0].external_id.endswith("-ghost"))
        self.assertEqual(writer.calls, [])

    def test_distinct_concurrent_executions_delete_only_their_owned_round_trip(self):
        adapter = InterleavingCreateAdapter("notion", atomic=True)
        value = approved_round_trip_manifest()
        execution_ids = ("execution-alpha", "execution-beta")
        results: list[object] = []
        errors: list[BaseException] = []

        def execute(execution_id: str) -> None:
            try:
                results.append(run_apply(
                    value,
                    {"notion": adapter},
                    RecordingWriter(),
                    execution_id=execution_id,
                ))
            except BaseException as error:
                errors.append(error)

        threads = tuple(
            threading.Thread(target=execute, args=(execution_id,))
            for execution_id in execution_ids
        )
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive(), "round-trip test deadlocked")

        expected_keys = {
            f"setup.round_trip.notion.{value.fingerprint}.{execution_id}"
            for execution_id in execution_ids
        }
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result.ready for result in results))
        self.assertEqual(set(adapter.created_keys), expected_keys)
        self.assertEqual(set(adapter.deleted_keys), expected_keys)
        self.assertEqual(
            {result.evidence[0].target_key for result in results},
            expected_keys,
        )
        self.assertEqual(adapter.records_by_id, {})

    def test_retry_of_same_execution_reuses_and_cleans_owned_round_trip(self):
        value = approved_round_trip_manifest()
        execution_id = "execution-retry"
        disposable_key = (
            f"setup.round_trip.notion.{value.fingerprint}.{execution_id}"
        )
        adapter = RecordingAdapter(
            "notion",
            records=(
                observed(
                    disposable_key,
                    "notion-interrupted",
                    "round-trip-v1",
                    resource_type="elephant_setup_round_trip",
                ),
            ),
        )

        result = run_apply(
            value,
            {"notion": adapter},
            RecordingWriter(),
            execution_id=execution_id,
        )

        self.assertTrue(result.ready)
        self.assertEqual(adapter.created_keys, [])
        self.assertEqual(adapter.deleted_keys, [disposable_key])
        self.assertEqual(
            adapter.call_kinds,
            (
                "find",
                "read",
                "find",
                "find_relationship",
                "bind_relationship",
                "read_relationship",
                "find_relationship",
                "unbind_relationship",
                "read_relationship",
                "find_relationship",
                "delete_disposable",
                "read",
                "find",
            ),
        )
        self.assertEqual(result.evidence[0].external_id, "notion-interrupted")

    def test_cleanup_failure_blocks_readiness_and_local_write(self):
        adapter = RecordingAdapter("notion", retain_deleted=True)
        writer = RecordingWriter()

        with self.assertRaisesRegex(SetupApplyError, "disposable cleanup"):
            run_apply(approved_round_trip_manifest(), {"notion": adapter}, writer)

        self.assertEqual(writer.calls, [])

    def test_failed_disposable_read_back_never_grants_delete_authority(self):
        adapter = RecordingAdapter("notion", corrupt_read_back=True)
        writer = RecordingWriter()

        with self.assertRaisesRegex(SetupApplyError, "read-back"):
            run_apply(approved_round_trip_manifest(), {"notion": adapter}, writer)

        self.assertNotIn("delete_disposable", adapter.call_kinds)
        self.assertEqual(writer.calls, [])

    def test_duplicate_disposable_key_never_grants_delete_authority(self):
        value = approved_round_trip_manifest()
        execution_id = "execution-duplicate"
        disposable_key = (
            f"setup.round_trip.notion.{value.fingerprint}.{execution_id}"
        )
        adapter = RecordingAdapter(
            "notion",
            records=(
                observed(disposable_key, "notion-1", "round-trip-v1", resource_type="elephant_setup_round_trip"),
                observed(disposable_key, "notion-2", "round-trip-v1", resource_type="elephant_setup_round_trip"),
            ),
        )

        with self.assertRaisesRegex(SetupApplyError, "duplicate"):
            run_apply(
                value,
                {"notion": adapter},
                RecordingWriter(),
                execution_id=execution_id,
            )

        self.assertNotIn("delete_disposable", adapter.call_kinds)


class SetupApplyFailureEvidenceTests(unittest.TestCase):
    def test_later_transport_failure_preserves_verified_create_evidence(self):
        first_operation = operation(OperationKind.CREATE)
        failing_operation = operation(
            OperationKind.CREATE,
            provider="notion",
            target_key="database.sample",
            desired_fingerprint="database-v1",
        )
        local_operation = operation(
            OperationKind.WRITE_LOCAL,
            provider="local",
            target_key=".agents/elephant/workspace.yaml",
            payload=(("document", ()),),
        )
        value = approved(manifest(
            first_operation,
            failing_operation,
            local_operation,
        ))
        linear = RecordingAdapter("linear")
        failure = RuntimeError("notion transport unavailable")
        notion = FailingFindAdapter("notion", failure)
        writer = RecordingWriter()

        with self.assertRaises(SetupApplyError) as raised:
            run_apply(
                value,
                {"linear": linear, "notion": notion},
                writer,
                execution_id="transport-failure",
            )

        error = raised.exception
        self.assertIs(error.operation, failing_operation)
        self.assertEqual(error.operation_id, failing_operation.operation_id)
        self.assertEqual(error.provider, "notion")
        self.assertIs(error.cause, failure)
        self.assertEqual(
            tuple(item.operation_id for item in error.partial_evidence),
            (first_operation.operation_id,),
        )
        self.assertIn("notion transport unavailable", str(error))
        self.assertIn("linear-1", linear.records_by_id)
        self.assertEqual(writer.calls, [])

    def test_local_writer_failure_preserves_all_external_evidence(self):
        value = approved_create_manifest()
        adapter = RecordingAdapter("linear")
        failure = OSError("local disk unavailable")
        writer = FailingWriter(failure)
        local_operation = value.manifest.operations[-1]

        with self.assertRaises(SetupApplyError) as raised:
            run_apply(
                value,
                {"linear": adapter},
                writer,
                execution_id="writer-failure",
            )

        error = raised.exception
        self.assertEqual(error.operation_id, local_operation.operation_id)
        self.assertEqual(error.target_key, ".agents/elephant/workspace.yaml")
        self.assertIs(error.cause, failure)
        self.assertEqual(len(error.partial_evidence), 1)
        self.assertEqual(
            error.partial_evidence[0].operation_id,
            value.manifest.operations[0].operation_id,
        )
        self.assertIn("local disk unavailable", str(error))
        self.assertEqual(len(writer.calls), 1)


class AtomicLocalWriter:
    def __init__(self, root: Path, events: list[str]) -> None:
        self.root = root
        self.events = events

    def preflight(
        self,
        operations: tuple[SetupOperation, ...],
        expected_container_fingerprint: str,
        owner_id: str,
    ) -> None:
        plan_local_writes(
            self.root,
            operations,
            expected_container_fingerprint,
        )

    def __call__(
        self,
        operations: tuple[SetupOperation, ...],
        expected_container_fingerprint: str,
        owner_id: str,
    ) -> LocalTransactionResult:
        self.events.append("local:batch")
        writes = plan_local_writes(
            self.root,
            operations,
            expected_container_fingerprint,
        )
        return apply_local_write(self.root, writes, owner_id=owner_id)


def complete_layers(capabilities: frozenset[str]) -> CapabilityLayers:
    return CapabilityLayers(capabilities, capabilities, capabilities, capabilities)


def freeze_document(value: object, *, top_level: bool = True) -> object:
    if isinstance(value, dict):
        entries = tuple(
            (key, freeze_document(item, top_level=False))
            for key, item in sorted(value.items())
        )
        return entries if top_level else FrozenMap(entries)
    if isinstance(value, list):
        return FrozenList(
            tuple(freeze_document(item, top_level=False) for item in value)
        )
    return value


def binding_record(provider: str, key: str, external_id: str) -> ExternalRecord:
    return observed(key, external_id, f"verified-{key}")


def integrated_adapters(events: list[str]) -> dict[str, RecordingAdapter]:
    linear_records = (
        binding_record("linear", "binding.linear.workspace", "linear-workspace"),
        binding_record("linear", "binding.linear.team", "linear-team"),
        observed("label.product.sample", "linear-label-sample", "label-v1"),
    )
    notion_records = (
        binding_record("notion", "binding.notion.workspace", "notion-workspace"),
        binding_record("notion", "binding.notion.products", "notion-products"),
        binding_record("notion", "binding.notion.knowledge", "notion-knowledge"),
        binding_record("notion", "binding.notion.contracts", "notion-contracts"),
        binding_record("notion", "binding.notion.product.sample", "notion-product-sample"),
    )
    return {
        "linear": RecordingAdapter("linear", records=linear_records, events=events),
        "notion": RecordingAdapter("notion", records=notion_records, events=events),
    }


INTEGRATED_SLOT_SPECS = {
    "linear.workspace_id": ("linear", "binding.linear.workspace"),
    "linear.team_id": ("linear", "binding.linear.team"),
    "linear.story.sample": ("linear", "label.product.sample"),
    "notion.workspace_id": ("notion", "binding.notion.workspace"),
    "notion.products_database_id": ("notion", "binding.notion.products"),
    "notion.knowledge_database_id": ("notion", "binding.notion.knowledge"),
    "notion.contracts_database_id": ("notion", "binding.notion.contracts"),
    "notion.knowledge.sample": ("notion", "binding.notion.product.sample"),
}


def integrated_slot_bindings() -> dict[str, object]:
    slots = {
        slot_id: LocalDocumentSlot(slot_id, provider, stable_key)
        for slot_id, (provider, stable_key) in INTEGRATED_SLOT_SPECS.items()
    }
    return {
        "linear": {
            "planned": True,
            "values": {
                "workspace_id": slots["linear.workspace_id"],
                "team_id": slots["linear.team_id"],
            },
            "story_refs": {"sample": slots["linear.story.sample"]},
        },
        "notion": {
            "planned": True,
            "values": {
                "workspace_id": slots["notion.workspace_id"],
                "products_database_id": slots["notion.products_database_id"],
                "knowledge_database_id": slots["notion.knowledge_database_id"],
                "contracts_database_id": slots["notion.contracts_database_id"],
            },
            "knowledge_refs": {"sample": slots["notion.knowledge.sample"]},
        },
    }


def materialize_integrated_documents(
    documents: dict[str, str | LocalDocumentTemplate],
    adapters: dict[str, RecordingAdapter],
) -> dict[str, str]:
    replacements: dict[str, str] = {}
    for slot_id, (provider, stable_key) in INTEGRATED_SLOT_SPECS.items():
        records = adapters[provider].find(stable_key)
        if len(records) != 1:
            raise AssertionError(f"expected one adapter binding record for {stable_key}")
        record = adapters[provider].read(records[0].external_id)
        if record != records[0]:
            raise AssertionError(f"binding read-back mismatch for {stable_key}")
        replacements[
            LocalDocumentSlot(slot_id, provider, stable_key).placeholder
        ] = record.external_id
    materialized: dict[str, str] = {}
    for path, value in documents.items():
        body = value.body if isinstance(value, LocalDocumentTemplate) else value
        for placeholder, external_id in replacements.items():
            body = body.replace(placeholder, external_id)
        materialized[path] = body
    return materialized


def approved_integrated_manifest(
    root: Path,
    adapters: dict[str, RecordingAdapter],
    *,
    repository_id: str,
):
    topology = replace(confirmed_topology(), repository_id=repository_id)
    profile_settings = product_settings()
    if repository_id == "repo-updated":
        profile_settings["sample"]["language"] = {
            "dialogue": "zh-CN",
            "docs": "fr",
        }
    document_templates = build_local_documents(
        topology,
        external_provider_selection(),
        integrated_slot_bindings(),
        profile_settings,
        engineering_settings(),
    )
    rendered = {
        path: value.body if isinstance(value, LocalDocumentTemplate) else value
        for path, value in document_templates.items()
    }
    documents = materialize_integrated_documents(document_templates, adapters)
    normalized = {path: load_rendered_yaml(body) for path, body in rendered.items()}
    expected_priors = tuple(
        (path, body_fingerprint(target.read_text(encoding="utf-8")))
        for path in sorted(documents)
        if (target := root / path).is_file()
        and target.read_text(encoding="utf-8") != documents[path]
    )
    desired_structures: list[DesiredStructure] = []
    external_objects: list[ExternalObject] = []
    for slot_id, (provider, stable_key) in sorted(INTEGRATED_SLOT_SPECS.items()):
        record = adapters[provider].records_by_key[stable_key][0]
        logical_provider = (
            ProviderKind.STORY
            if provider == "linear"
            else ProviderKind.PRODUCT_CONTRACT
            if stable_key == "binding.notion.contracts"
            else ProviderKind.PRODUCT_KNOWLEDGE
        )
        desired_structures.append(
            DesiredStructure(
                provider,
                "ensure_label" if stable_key == "label.product.sample" else "ensure_binding",
                stable_key,
                record.fingerprint,
                True,
                False,
                logical_provider=logical_provider,
                semantics=record.semantics,
            )
        )
        external_objects.append(
            ExternalObject(
                provider,
                "setup_structure",
                stable_key,
                slot_id,
                record.external_id,
                record.fingerprint,
            )
        )
    setup_manifest = build_setup_manifest(
        topology,
        tuple(sorted(external_provider_selection().items())),
        tuple(desired_structures),
        ExternalDiscovery(objects=tuple(external_objects)),
        (
            (
                "story_store",
                complete_layers(
                    STORY_RUNTIME_CAPABILITIES | {"ensure_binding", "ensure_label"}
                ),
            ),
            (
                "product_knowledge_store",
                complete_layers(KNOWLEDGE_RUNTIME_CAPABILITIES | {"ensure_binding"}),
            ),
            (
                "product_contract_store",
                complete_layers(CONTRACT_RUNTIME_CAPABILITIES | {"ensure_binding"}),
            ),
            ("delivery_workspace", complete_layers(DELIVERY_RUNTIME_CAPABILITIES)),
        ),
        freeze_document(normalized[WORKSPACE_PATH]),
        tuple(
            (
                Path(path).stem,
                freeze_document(document),
            )
            for path, document in sorted(normalized.items())
            if path != WORKSPACE_PATH
        ),
        expected_local_container_fingerprint=fingerprint_local_container(root),
        expected_prior_fingerprints=expected_priors,
        observed_local_fingerprints=tuple(
            (
                path,
                hashlib.sha256((root / path).read_bytes()).hexdigest()
                if (root / path).is_file()
                else None,
            )
            for path in sorted(documents)
        ),
        rendered_local_documents=tuple(sorted(document_templates.items())),
    )
    return approved(setup_manifest), documents


def commit_integrated_local(root: Path, value: ApprovedManifest) -> None:
    operation_by_id = {
        operation.operation_id: operation
        for operation in value.manifest.operations
    }
    operations = tuple(
        operation
        for operation in value.manifest.operations
        if operation.kind is OperationKind.WRITE_LOCAL
    )
    materialized: list[SetupOperation] = []
    for operation in operations:
        body = dict(operation.payload)["document"]
        for slot in operation.local_slots:
            source = operation_by_id[slot.source_operation_id]
            external_id = dict(source.payload).get("external_id")
            if not isinstance(external_id, str) or not external_id:
                raise AssertionError(
                    f"bootstrap source {source.operation_id} lacks external ID"
                )
            body = body.replace(slot.placeholder, external_id)
        materialized.append(
            replace(
                operation,
                payload=(("document", body),),
                expected_byte_fingerprint=hashlib.sha256(
                    body.encode("utf-8")
                ).hexdigest(),
            )
        )
    AtomicLocalWriter(root, [])(
        tuple(materialized),
        value.manifest.expected_local_container_fingerprint,
        "integration-bootstrap",
    )


class SetupApplyLocalFileIntegrationTests(unittest.TestCase):
    def test_slot_backed_rerun_is_a_true_noop_without_atomic_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapters = integrated_adapters([])
            first, _ = approved_integrated_manifest(
                root,
                adapters,
                repository_id="repo-sample",
            )
            first_result = run_apply(
                first,
                adapters,
                RepositoryLocalWriter(root),
                execution_id="slot-noop-bootstrap",
            )
            self.assertTrue(first_result.ready)
            second, _ = approved_integrated_manifest(
                root,
                adapters,
                repository_id="repo-sample",
            )
            self.assertNotIn(
                OperationKind.ROUND_TRIP,
                tuple(operation.kind for operation in second.manifest.operations),
            )
            mutation_counts = {
                provider: (
                    len(adapter.created_keys),
                    len(adapter.deleted_keys),
                    sum(
                        kind in {
                            "create",
                            "bind_relationship",
                            "unbind_relationship",
                            "delete_disposable",
                        }
                        for kind in adapter.call_kinds
                    ),
                )
                for provider, adapter in adapters.items()
            }
            before_root = os.stat(root, follow_symlinks=False)
            before_entries = {
                path.name: (
                    os.stat(path, follow_symlinks=False).st_dev,
                    os.stat(path, follow_symlinks=False).st_ino,
                )
                for path in root.iterdir()
            }

            with mock.patch(
                "scripts.workspace_setup.files.probe_atomic_switch",
                wraps=setup_files.probe_atomic_switch,
            ) as atomic_probe:
                second_result = run_apply(
                    second,
                    adapters,
                    RepositoryLocalWriter(root),
                    execution_id="slot-noop-rerun",
                )

            after_root = os.stat(root, follow_symlinks=False)
            after_entries = {
                path.name: (
                    os.stat(path, follow_symlinks=False).st_dev,
                    os.stat(path, follow_symlinks=False).st_ino,
                )
                for path in root.iterdir()
            }
            container = next(
                item
                for item in second_result.evidence
                if item.operation_id == "local.container"
            )
            self.assertTrue(second_result.ready)
            self.assertEqual(container.disposition, "unchanged")
            self.assertEqual(atomic_probe.call_count, 0)
            self.assertEqual(before_entries, after_entries)
            self.assertEqual(before_root.st_mtime_ns, after_root.st_mtime_ns)
            self.assertEqual(
                {
                    provider: (
                        len(adapter.created_keys),
                        len(adapter.deleted_keys),
                        sum(
                            kind in {
                                "create",
                                "bind_relationship",
                                "unbind_relationship",
                                "delete_disposable",
                            }
                            for kind in adapter.call_kinds
                        ),
                    )
                    for provider, adapter in adapters.items()
                },
                mutation_counts,
            )

    def test_stale_unchanged_rerun_stops_before_adapter_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapters = integrated_adapters([])
            first, _ = approved_integrated_manifest(
                root,
                adapters,
                repository_id="repo-sample",
            )
            self.assertTrue(run_apply(
                first,
                adapters,
                RepositoryLocalWriter(root),
                execution_id="stale-noop-bootstrap",
            ).ready)
            unchanged, _ = approved_integrated_manifest(
                root,
                adapters,
                repository_id="repo-sample",
            )
            self.assertNotIn(
                OperationKind.ROUND_TRIP,
                tuple(
                    operation.kind
                    for operation in unchanged.manifest.operations
                ),
            )
            workspace = root / WORKSPACE_PATH
            workspace.write_text(
                workspace.read_text(encoding="utf-8").replace(
                    '"repo-sample"',
                    '"repo-stale-after-approval"',
                ),
                encoding="utf-8",
            )
            calls_before = {
                provider: tuple(adapter.calls)
                for provider, adapter in adapters.items()
            }

            with self.assertRaisesRegex(
                SetupApplyError,
                "stale|unchanged rerun",
            ):
                run_apply(
                    unchanged,
                    adapters,
                    RepositoryLocalWriter(root),
                    execution_id="stale-noop-rejected",
                )

            self.assertEqual(
                {
                    provider: tuple(adapter.calls)
                    for provider, adapter in adapters.items()
                },
                calls_before,
            )

    def test_existing_external_reference_is_materialized_from_current_verified_read_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapters = integrated_adapters([])
            authority, _ = approved_integrated_manifest(
                root,
                adapters,
                repository_id="repo-sample",
            )
            old = adapters["linear"].records_by_key["label.product.sample"][0]
            current = replace(old, external_id="linear-label-current")
            adapters["linear"].records_by_key[current.stable_key] = [current]
            adapters["linear"].records_by_id.pop(old.external_id)
            adapters["linear"].records_by_id[current.external_id] = current

            result = run_apply(
                authority,
                adapters,
                RepositoryLocalWriter(root),
                execution_id="existing-reference-refresh",
            )

            self.assertTrue(result.ready)
            workspace = load_rendered_yaml(
                (root / WORKSPACE_PATH).read_text(encoding="utf-8")
            )
            self.assertEqual(
                workspace["products"]["sample"]["story_ref"],
                current.external_id,
            )

    def test_greenfield_slots_materialize_after_manual_resume_under_same_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events: list[str] = []
            adapters = {
                "linear": RecordingAdapter("linear", events=events),
                "notion": RecordingAdapter("notion", events=events),
            }
            slot_specs = {
                "linear.workspace_id": ("linear", "binding.linear.workspace"),
                "linear.team_id": ("linear", "binding.linear.team"),
                "linear.story.sample": ("linear", "label.product.sample"),
                "notion.workspace_id": ("notion", "binding.notion.workspace"),
                "notion.products_database_id": ("notion", "binding.notion.products"),
                "notion.knowledge_database_id": ("notion", "binding.notion.knowledge"),
                "notion.contracts_database_id": ("notion", "binding.notion.contracts"),
                "notion.knowledge.sample": ("notion", "binding.notion.product.sample"),
            }
            slots = {
                slot_id: LocalDocumentSlot(slot_id, provider, stable_key)
                for slot_id, (provider, stable_key) in slot_specs.items()
            }
            documents = build_local_documents(
                confirmed_topology(),
                external_provider_selection(),
                {
                    "linear": {
                        "planned": True,
                        "values": {
                            "workspace_id": slots["linear.workspace_id"],
                            "team_id": slots["linear.team_id"],
                        },
                        "story_refs": {
                            "sample": slots["linear.story.sample"],
                        },
                    },
                    "notion": {
                        "planned": True,
                        "values": {
                            "workspace_id": slots["notion.workspace_id"],
                            "products_database_id": slots[
                                "notion.products_database_id"
                            ],
                            "knowledge_database_id": slots[
                                "notion.knowledge_database_id"
                            ],
                            "contracts_database_id": slots[
                                "notion.contracts_database_id"
                            ],
                        },
                        "knowledge_refs": {
                            "sample": slots["notion.knowledge.sample"],
                        },
                    },
                },
                product_settings(),
                engineering_settings(),
            )
            workspace_template = documents[WORKSPACE_PATH]
            self.assertIsInstance(workspace_template, LocalDocumentTemplate)
            rendered = {
                path: value.body if isinstance(value, LocalDocumentTemplate) else value
                for path, value in documents.items()
            }
            desired: list[DesiredStructure] = []
            for index, (slot_id, (provider, stable_key)) in enumerate(
                sorted(slot_specs.items())
            ):
                semantics = ProviderSemantics(
                    "setup_structure",
                    FrozenMap((("slot_id", slot_id),)),
                )
                is_manual = slot_id == "notion.knowledge.sample"
                desired.append(
                    DesiredStructure(
                        provider,
                        "ensure_manual_view" if is_manual else "ensure_binding",
                        stable_key,
                        semantics_fingerprint(semantics),
                        True,
                        False,
                        logical_provider=(
                            ProviderKind.STORY
                            if provider == "linear"
                            else ProviderKind.PRODUCT_KNOWLEDGE
                        ),
                        semantics=semantics,
                        manual_instructions=(
                            "Create the approved Sample knowledge record with the exact fields."
                            if is_manual
                            else ""
                        ,) if is_manual else (),
                    )
                )
            setup_manifest = build_setup_manifest(
                confirmed_topology(),
                tuple(sorted(external_provider_selection().items())),
                tuple(desired),
                ExternalDiscovery(objects=()),
                (
                    (
                        "story_store",
                        complete_layers(
                            STORY_RUNTIME_CAPABILITIES | {"ensure_binding"}
                        ),
                    ),
                    (
                        "product_knowledge_store",
                        complete_layers(
                            KNOWLEDGE_RUNTIME_CAPABILITIES | {"ensure_binding"}
                        ),
                    ),
                    (
                        "product_contract_store",
                        complete_layers(CONTRACT_RUNTIME_CAPABILITIES),
                    ),
                    (
                        "delivery_workspace",
                        complete_layers(DELIVERY_RUNTIME_CAPABILITIES),
                    ),
                ),
                freeze_document(load_rendered_yaml(rendered[WORKSPACE_PATH])),
                tuple(
                    (Path(path).stem, freeze_document(load_rendered_yaml(body)))
                    for path, body in sorted(rendered.items())
                    if path != WORKSPACE_PATH
                ),
                expected_local_container_fingerprint=fingerprint_local_container(root),
                rendered_local_documents=tuple(sorted(documents.items())),
            )
            authority = approved(setup_manifest)
            fingerprint_before = authority.fingerprint
            self.assertTrue(all(not adapter.calls for adapter in adapters.values()))

            first = run_apply(
                authority,
                adapters,
                RepositoryLocalWriter(root),
                execution_id="greenfield-manual-handoff",
            )

            self.assertFalse(first.ready)
            self.assertEqual(len(first.manual_handoffs), 1)
            self.assertFalse((root / ".agents").exists())
            self.assertEqual(
                {
                    key
                    for adapter in adapters.values()
                    for key in adapter.created_keys
                },
                {
                    stable_key
                    for slot_id, (_, stable_key) in slot_specs.items()
                    if slot_id != "notion.knowledge.sample"
                },
            )
            manual = next(
                operation
                for operation in authority.manifest.operations
                if operation.kind is OperationKind.MANUAL
            )
            completed = ExternalRecord(
                manual.target_key,
                "notion-manual-sample",
                manual.semantics,
            )
            adapters["notion"].records_by_key[completed.stable_key] = [completed]
            adapters["notion"].records_by_id[completed.external_id] = completed

            second = run_apply(
                authority,
                adapters,
                RepositoryLocalWriter(root),
                execution_id="greenfield-manual-resume",
                resume_handoff=first.manual_handoffs[0],
            )

            self.assertTrue(second.ready)
            self.assertEqual(authority.fingerprint, fingerprint_before)
            self.assertEqual(len(second.binding_receipts), len(slot_specs))
            workspace_body = (root / WORKSPACE_PATH).read_text(encoding="utf-8")
            workspace = load_rendered_yaml(workspace_body)
            self.assertEqual(validate_workspace(workspace), ())
            self.assertNotIn("urn:elephant:setup-slot:", workspace_body)
            for path in sorted((root / ".agents/elephant/profiles").glob("*.yaml")):
                self.assertEqual(
                    validate_profile(load_rendered_yaml(path.read_text(encoding="utf-8"))),
                    (),
                )
            self.assertEqual(
                {
                    receipt.stable_key: receipt.external_id
                    for receipt in second.binding_receipts
                },
                {
                    stable_key: adapters[provider].records_by_key[stable_key][0].external_id
                    for provider, stable_key in slot_specs.values()
                },
            )
            self.assertTrue(
                all(
                    key.endswith(".greenfield-manual-resume")
                    for adapter in adapters.values()
                    for key in adapter.deleted_keys
                )
            )
            container = next(
                evidence
                for evidence in second.local_writes
                if evidence.operation_id == "local.container"
            )
            self.assertEqual(container.external_id, "greenfield-manual-resume")

    def test_same_approved_manual_completion_replaces_local_and_retains_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events: list[str] = []
            adapters = integrated_adapters(events)
            original, original_documents = approved_integrated_manifest(
                root, adapters, repository_id="repo-sample"
            )
            commit_integrated_local(root, original)
            changed, changed_documents = approved_integrated_manifest(
                root, adapters, repository_id="repo-updated"
            )
            manual = operation(
                OperationKind.MANUAL,
                provider="notion",
                target_key="view.sample",
                desired_fingerprint="view-v1",
                payload=(
                    ("diagnostic_code", "platform_unsupported"),
                    ("read_back_required", True),
                ),
            )
            value = approved(replace(
                changed.manifest,
                operations=(manual,) + changed.manifest.operations,
            ))
            first_execution_id = "integrated-manual-handoff"
            resumed_execution_id = "integrated-manual-resume"

            first = run_apply(
                value,
                adapters,
                AtomicLocalWriter(root, events),
                execution_id=first_execution_id,
            )

            self.assertFalse(first.ready)
            self.assertEqual(first.manual_handoffs[0].disposition, "manual_handoff")
            self.assertEqual(
                {
                    path: (root / path).read_text(encoding="utf-8")
                    for path in original_documents
                },
                original_documents,
            )
            completed = observed("view.sample", "notion-view-1", "view-v1")
            adapters["notion"].records_by_key[completed.stable_key] = [completed]
            adapters["notion"].records_by_id[completed.external_id] = completed

            second = run_apply(
                value,
                adapters,
                AtomicLocalWriter(root, events),
                execution_id=resumed_execution_id,
                resume_handoff=first.manual_handoffs[0],
            )

            recovery = next(
                evidence
                for evidence in second.local_writes
                if evidence.operation_id == "local.container.recovery"
            )
            active = next(
                evidence
                for evidence in second.local_writes
                if evidence.operation_id == "local.container"
            )
            self.assertTrue(second.ready)
            self.assertEqual(second.evidence[0].disposition, "manual_completed")
            self.assertEqual(recovery.disposition, "cleanup_pending")
            self.assertTrue(recovery.target_key.startswith(".agents.setup-stage-"))
            self.assertTrue((root / recovery.target_key).is_dir())
            self.assertEqual(active.target_key, ".agents")
            self.assertEqual(active.disposition, "replaced")
            self.assertEqual(active.external_id, resumed_execution_id)
            self.assertEqual(
                {
                    path: (root / path).read_text(encoding="utf-8")
                    for path in changed_documents
                },
                changed_documents,
            )

    def test_verified_external_apply_writes_schema_valid_local_documents_last(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events: list[str] = []
            adapters = integrated_adapters(events)
            original, _ = approved_integrated_manifest(
                root, adapters, repository_id="repo-sample"
            )
            commit_integrated_local(root, original)
            value, documents = approved_integrated_manifest(
                root, adapters, repository_id="repo-updated"
            )
            local_operations = tuple(
                operation
                for operation in value.manifest.operations
                if operation.kind is OperationKind.WRITE_LOCAL
            )
            self.assertEqual(local_operations[-1].target_key, WORKSPACE_PATH)
            self.assertEqual(
                local_operations[-1].expected_prior_fingerprint,
                body_fingerprint((root / WORKSPACE_PATH).read_text(encoding="utf-8")),
            )
            events.clear()

            result = run_apply(
                value,
                adapters,
                AtomicLocalWriter(root, events),
                execution_id="integrated-success",
            )

            self.assertTrue(result.ready)
            self.assertEqual(events[-1], "local:batch")
            workspace = load_rendered_yaml((root / WORKSPACE_PATH).read_text(encoding="utf-8"))
            self.assertEqual(validate_workspace(workspace), ())
            self.assertEqual(workspace["repository"]["id"], "repo-updated")
            for path in sorted((root / ".agents/elephant/profiles").glob("*.yaml")):
                self.assertEqual(
                    validate_profile(load_rendered_yaml(path.read_text(encoding="utf-8"))),
                    (),
                )
            self.assertEqual(
                {path: (root / path).read_text(encoding="utf-8") for path in documents},
                documents,
            )

    def test_external_read_back_failure_leaves_no_local_setup_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = AtomicLocalWriter(root, [])
            adapters = integrated_adapters([])
            value, _ = approved_integrated_manifest(
                root, adapters, repository_id="repo-sample"
            )
            adapters["linear"].corrupt_read_back = True

            with self.assertRaisesRegex(SetupApplyError, "read-back"):
                run_apply(
                    value,
                    adapters,
                    writer,
                    execution_id="integrated-read-failure",
                )

            self.assertFalse((root / ".agents/elephant").exists())

    def test_unsupported_atomic_primitive_reports_not_applied_and_preserves_prior(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapters = integrated_adapters([])
            original, original_documents = approved_integrated_manifest(
                root, adapters, repository_id="repo-sample"
            )
            commit_integrated_local(root, original)
            value, _ = approved_integrated_manifest(
                root, adapters, repository_id="repo-updated"
            )

            with mock.patch(
                "scripts.workspace_setup.files.atomic_exchange",
                side_effect=AtomicRenameUnavailable("unsupported"),
            ):
                with self.assertRaises(SetupApplyError) as raised:
                    run_apply(
                        value,
                        adapters,
                        AtomicLocalWriter(root, []),
                        execution_id="integrated-local-failure",
                    )

            local_evidence = tuple(
                evidence
                for evidence in raised.exception.partial_evidence
                if evidence.operation_id.startswith("local.")
            )
            self.assertTrue(local_evidence)
            self.assertEqual(local_evidence[-1].target_key, ".agents")
            self.assertEqual(local_evidence[-1].disposition, "not_applied")
            self.assertEqual(
                {
                    path: (root / path).read_text(encoding="utf-8")
                    for path in original_documents
                },
                original_documents,
            )

    def test_committed_container_reports_retained_recovery_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapters = integrated_adapters([])
            original, original_documents = approved_integrated_manifest(
                root, adapters, repository_id="repo-sample"
            )
            commit_integrated_local(root, original)
            value, changed_documents = approved_integrated_manifest(
                root, adapters, repository_id="repo-updated"
            )

            result = run_apply(
                value,
                adapters,
                AtomicLocalWriter(root, []),
                execution_id="integrated-retained-stage",
            )

            local_evidence = tuple(
                evidence
                for evidence in result.local_writes
                if evidence.operation_id.startswith("local.")
            )
            recovery = next(
                evidence
                for evidence in local_evidence
                if evidence.operation_id == "local.container.recovery"
            )
            self.assertTrue(result.ready)
            self.assertEqual(recovery.disposition, "cleanup_pending")
            self.assertNotEqual(recovery.target_key, ".agents")
            self.assertTrue((root / recovery.target_key).is_dir())
            root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                self.assertEqual(
                    setup_files.fingerprint_container_at(
                        root_fd,
                        recovery.target_key,
                    ),
                    recovery.observed_fingerprint,
                )
            finally:
                os.close(root_fd)
            self.assertEqual(local_evidence[-1].operation_id, "local.container")
            self.assertEqual(
                {path: (root / path).read_text(encoding="utf-8") for path in changed_documents},
                changed_documents,
            )

    def test_recovery_stage_name_swap_during_final_attestation_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapters = integrated_adapters([])
            original, _ = approved_integrated_manifest(
                root, adapters, repository_id="repo-sample"
            )
            commit_integrated_local(root, original)
            prior_fingerprint = fingerprint_local_container(root)
            value, changed_documents = approved_integrated_manifest(
                root, adapters, repository_id="repo-updated"
            )
            native_active_observation = setup_files._observe_active_container
            stale_stage_name = ""
            held_stage: Path | None = None
            replacement_stage: Path | None = None
            name_swapped = False

            def swap_name_before_final_attestation(root_fd):
                nonlocal stale_stage_name, held_stage, replacement_stage, name_swapped
                if name_swapped:
                    return native_active_observation(root_fd)
                name_swapped = True
                retained_paths = tuple(
                    path
                    for path in root.iterdir()
                    if path.name.startswith(".agents.setup-stage-")
                    and not path.name.endswith(".held")
                )
                self.assertEqual(len(retained_paths), 1)
                retained_path = retained_paths[0]
                stale_stage_name = retained_path.name
                held_stage = root / f"{stale_stage_name}.held"
                retained_path.rename(held_stage)
                (held_stage / "attestation-marker.txt").write_text(
                    "retained-tree-owner",
                    encoding="utf-8",
                )
                replacement_stage = retained_path
                replacement_stage.mkdir()
                (replacement_stage / "unrelated.txt").write_text(
                    "replacement-owner",
                    encoding="utf-8",
                )
                return native_active_observation(root_fd)

            with mock.patch(
                "scripts.workspace_setup.files._observe_active_container",
                side_effect=swap_name_before_final_attestation,
            ):
                with self.assertRaisesRegex(
                    SetupApplyError,
                    "recovery stage path identity",
                ) as raised:
                    run_apply(
                        value,
                        adapters,
                        AtomicLocalWriter(root, []),
                        execution_id="integrated-recovery-name-race",
                    )

            self.assertTrue(stale_stage_name)
            self.assertIsNotNone(held_stage)
            self.assertIsNotNone(replacement_stage)
            recovery = next(
                evidence
                for evidence in raised.exception.partial_evidence
                if evidence.operation_id == "local.container.recovery"
            )
            active = next(
                evidence
                for evidence in raised.exception.partial_evidence
                if evidence.operation_id == "local.container"
            )
            local_evidence = tuple(
                evidence
                for evidence in raised.exception.partial_evidence
                if evidence.operation_id.startswith("local.")
            )
            held_root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                held_fingerprint = setup_files.fingerprint_container_at(
                    held_root_fd,
                    held_stage.name,
                )
            finally:
                os.close(held_root_fd)
            self.assertEqual(recovery.target_key, "")
            self.assertEqual(recovery.disposition, "path_identity_lost")
            self.assertEqual(recovery.observed_fingerprint, held_fingerprint)
            self.assertNotEqual(recovery.observed_fingerprint, prior_fingerprint)
            self.assertNotIn(
                stale_stage_name,
                {evidence.target_key for evidence in raised.exception.partial_evidence},
            )
            self.assertEqual(active.target_key, ".agents")
            self.assertEqual(active.disposition, "replaced")
            self.assertIs(local_evidence[-1], active)
            self.assertEqual(
                active.observed_fingerprint,
                fingerprint_local_container(root),
            )
            self.assertEqual(
                {
                    path: (root / path).read_text(encoding="utf-8")
                    for path in changed_documents
                },
                changed_documents,
            )
            self.assertEqual(
                (held_stage / "attestation-marker.txt").read_text(encoding="utf-8"),
                "retained-tree-owner",
            )
            self.assertEqual(
                (replacement_stage / "unrelated.txt").read_text(encoding="utf-8"),
                "replacement-owner",
            )

    def test_identity_loss_during_final_path_attestation_refreshes_error_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapters = integrated_adapters([])
            original, _ = approved_integrated_manifest(
                root, adapters, repository_id="repo-sample"
            )
            commit_integrated_local(root, original)
            value, changed_documents = approved_integrated_manifest(
                root, adapters, repository_id="repo-updated"
            )
            native_stage_path_matches = setup_files._stage_path_matches
            final_attestation_calls = 0
            stale_stage_name = ""
            held_stage: Path | None = None
            replacement_stage: Path | None = None
            active_workspace_body = "post-loss-active-owner"

            def mutate_during_final_attestation(root_fd, stage, *, name=None):
                nonlocal final_attestation_calls
                nonlocal stale_stage_name, held_stage, replacement_stage
                if name is None:
                    final_attestation_calls += 1
                    if final_attestation_calls == 2:
                        retained_path = root / stage.name
                        self.assertTrue(retained_path.is_dir())
                        stale_stage_name = stage.name
                        held_stage = root / f"{stale_stage_name}.held"
                        retained_path.rename(held_stage)
                        (held_stage / "post-loss-retained.txt").write_text(
                            "retained-tree-owner",
                            encoding="utf-8",
                        )
                        replacement_stage = retained_path
                        replacement_stage.mkdir()
                        (replacement_stage / "unrelated.txt").write_text(
                            "replacement-owner",
                            encoding="utf-8",
                        )
                        (root / WORKSPACE_PATH).write_text(
                            active_workspace_body,
                            encoding="utf-8",
                        )
                return native_stage_path_matches(root_fd, stage, name=name)

            with mock.patch(
                "scripts.workspace_setup.files._stage_path_matches",
                side_effect=mutate_during_final_attestation,
            ):
                with self.assertRaisesRegex(
                    SetupApplyError,
                    "recovery stage path identity",
                ) as raised:
                    run_apply(
                        value,
                        adapters,
                        AtomicLocalWriter(root, []),
                        execution_id="integrated-final-attestation-race",
                    )

            self.assertGreaterEqual(final_attestation_calls, 2)
            self.assertTrue(stale_stage_name)
            self.assertIsNotNone(held_stage)
            self.assertIsNotNone(replacement_stage)
            recovery = next(
                evidence
                for evidence in raised.exception.partial_evidence
                if evidence.operation_id == "local.container.recovery"
            )
            active = next(
                evidence
                for evidence in raised.exception.partial_evidence
                if evidence.operation_id == "local.container"
            )
            per_file = {
                evidence.target_key: evidence.observed_fingerprint
                for evidence in raised.exception.partial_evidence
                if evidence.target_key in changed_documents
            }
            held_root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                held_fingerprint = setup_files.fingerprint_container_at(
                    held_root_fd,
                    held_stage.name,
                )
            finally:
                os.close(held_root_fd)
            self.assertEqual(recovery.target_key, "")
            self.assertEqual(recovery.disposition, "path_identity_lost")
            self.assertEqual(recovery.observed_fingerprint, held_fingerprint)
            self.assertNotIn(
                stale_stage_name,
                {evidence.target_key for evidence in raised.exception.partial_evidence},
            )
            self.assertEqual(active.target_key, ".agents")
            self.assertEqual(
                active.observed_fingerprint,
                fingerprint_local_container(root),
            )
            self.assertEqual(
                per_file,
                {
                    path: body_fingerprint(
                        (root / path).read_text(encoding="utf-8")
                    )
                    for path in changed_documents
                },
            )
            self.assertEqual(
                (root / WORKSPACE_PATH).read_text(encoding="utf-8"),
                active_workspace_body,
            )
            self.assertEqual(
                (held_stage / "post-loss-retained.txt").read_text(encoding="utf-8"),
                "retained-tree-owner",
            )
            self.assertEqual(
                (replacement_stage / "unrelated.txt").read_text(encoding="utf-8"),
                "replacement-owner",
            )

    def test_concurrent_rollback_owner_is_preserved_in_container_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapters = integrated_adapters([])
            original, _ = approved_integrated_manifest(
                root, adapters, repository_id="repo-sample"
            )
            commit_integrated_local(root, original)
            unrelated = root / ".agents/unrelated.txt"
            unrelated.write_text("approved", encoding="utf-8")
            value, _ = approved_integrated_manifest(
                root, adapters, repository_id="repo-updated"
            )
            native_exchange = setup_files.atomic_exchange
            exchanges = 0

            def mutate_commit_and_rollback(parent_fd, first, second):
                nonlocal exchanges
                exchanges += 1
                if exchanges == 1:
                    unrelated.write_text("prior-race", encoding="utf-8")
                elif exchanges == 2:
                    (root / WORKSPACE_PATH).write_text(
                        "concurrent-active-owner", encoding="utf-8"
                    )
                return native_exchange(parent_fd, first, second)

            with mock.patch(
                "scripts.workspace_setup.files.atomic_exchange",
                side_effect=mutate_commit_and_rollback,
            ):
                with self.assertRaises(SetupApplyError) as raised:
                    run_apply(
                        value,
                        adapters,
                        AtomicLocalWriter(root, []),
                        execution_id="integrated-rollback-failure",
                    )

            failed_evidence = next(
                evidence
                for evidence in raised.exception.partial_evidence
                if evidence.target_key == ".agents"
            )
            self.assertEqual(failed_evidence.disposition, "rollback_failed")
            self.assertEqual(
                failed_evidence.observed_fingerprint,
                fingerprint_local_container(root),
            )
            self.assertEqual(
                (root / WORKSPACE_PATH).read_text(encoding="utf-8"),
                "concurrent-active-owner",
            )


if __name__ == "__main__":
    unittest.main()

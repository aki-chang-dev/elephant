from __future__ import annotations

from dataclasses import replace
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
    CapabilityLayers,
    Confidence,
    DeletionReceipt,
    DesiredStructure,
    Evidence,
    ExternalDiscovery,
    ExternalObject,
    ExternalRecord,
    MutationReceipt,
    OperationKind,
    OwnerQuestion,
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
) -> SetupOperation:
    return SetupOperation(
        operation_id=f"{provider}.{target_key}.{kind.value}",
        provider=provider,
        capability="ensure_label",
        target_key=target_key,
        desired_fingerprint=desired_fingerprint,
        payload=payload,
        kind=kind,
        runtime_required=False,
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
):
    return apply_setup(
        value,
        adapters,
        writer,
        execution_id=execution_id,
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
            setup_operation.desired_fingerprint,
        )
        self.records_by_key.setdefault(record.stable_key, []).append(record)
        self.records_by_id[record.external_id] = record
        self.created_keys.append(record.stable_key)
        return MutationReceipt(record.external_id)

    def read(self, external_id: str) -> ExternalRecord | None:
        self._record_call("read", external_id)
        record = self.records_by_id.get(external_id)
        if record is not None and self.corrupt_read_back:
            return replace(record, fingerprint="corrupt")
        return record

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
            setup_operation.desired_fingerprint,
        )
        self.records_by_key.setdefault(record.stable_key, []).append(record)
        self.records_by_id[record.external_id] = record
        self.created_keys.append(record.stable_key)
        return MutationReceipt(record.external_id)


class RecordingWriter:
    def __init__(self, events: list[str] | None = None) -> None:
        self.calls: list[tuple[str, object]] = []
        self.container_authorities: list[str] = []
        self.owner_ids: list[str] = []
        self.events = events

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
                    operation.desired_fingerprint,
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


def approved_create_manifest() -> ApprovedManifest:
    return approved(
        manifest(
            operation(OperationKind.CREATE),
            operation(
                OperationKind.WRITE_LOCAL,
                provider="local",
                target_key=".agents/elephant/workspace.yaml",
                desired_fingerprint="workspace-v1",
                payload=(("document", (("schema", "elephant.workspace/v3"),)),),
            ),
        )
    )


class SetupApplyMutationTests(unittest.TestCase):
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
        self.assertEqual(first.evidence[0].observed_fingerprint, "label-v1")
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
                record = ExternalRecord("team.delivery", "linear-1", "team-v1")
                adapter = RecordingAdapter("linear", records=(record,))
                value = approved(manifest(operation(
                    kind,
                    target_key="team.delivery",
                    desired_fingerprint="team-v1",
                )))

                result = run_apply(value, {"linear": adapter}, RecordingWriter())

                self.assertTrue(result.ready)
                self.assertEqual(adapter.call_kinds, ("find", "read"))
                self.assertEqual(result.evidence[0].external_id, "linear-1")

    def test_duplicate_or_semantically_mismatched_records_stop_before_local_write(self):
        cases = (
            (
                "duplicate",
                (
                    ExternalRecord("team.delivery", "linear-1", "team-v1"),
                    ExternalRecord("team.delivery", "linear-2", "team-v1"),
                ),
                "duplicate|exactly one",
            ),
            (
                "mismatch",
                (ExternalRecord("team.delivery", "linear-1", "team-old"),),
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

    def test_manual_handoff_is_not_ready_and_never_writes_local_state(self):
        value = approved(manifest(
            operation(
                OperationKind.MANUAL,
                provider="notion",
                target_key="view.sample",
                payload=(
                    ("diagnostic_code", "platform_unsupported"),
                    ("read_back_required", True),
                ),
            ),
            operation(
                OperationKind.WRITE_LOCAL,
                provider="local",
                target_key=".agents/elephant/workspace.yaml",
                payload=(("document", ()),),
            ),
        ))
        writer = RecordingWriter()

        result = run_apply(value, {}, writer)

        self.assertFalse(result.ready)
        self.assertEqual(len(result.manual_handoffs), 1)
        self.assertEqual(result.manual_handoffs[0].disposition, "manual_handoff")
        self.assertEqual(writer.calls, [])

    def test_local_writes_receive_exact_documents_after_external_read_back(self):
        events: list[str] = []
        adapter = RecordingAdapter("linear", events=events)
        writer = RecordingWriter(events)

        result = run_apply(approved_create_manifest(), {"linear": adapter}, writer)

        local_operation = approved_create_manifest().manifest.operations[-1]
        self.assertEqual(writer.calls, [(local_operation,)])
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
            ("find", "create", "read", "find", "delete_disposable", "read"),
        )
        disposable_key = (
            f"setup.round_trip.notion.{value.fingerprint}.{execution_id}"
        )
        self.assertEqual(adapter.created_keys, [disposable_key])
        self.assertEqual(adapter.deleted_keys, [disposable_key])
        self.assertEqual(result.evidence[0].target_key, disposable_key)
        self.assertEqual(result.evidence[0].disposition, "round_trip_cleaned")

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
                ExternalRecord(disposable_key, "notion-interrupted", "round-trip-v1"),
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
            ("find", "read", "delete_disposable", "read"),
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
                ExternalRecord(disposable_key, "notion-1", "round-trip-v1"),
                ExternalRecord(disposable_key, "notion-2", "round-trip-v1"),
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
        self.assertIs(error.operation, local_operation)
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


def freeze_document(value: object) -> object:
    if isinstance(value, dict):
        return tuple((key, freeze_document(item)) for key, item in sorted(value.items()))
    if isinstance(value, list):
        return tuple(freeze_document(item) for item in value)
    return value


def binding_record(provider: str, key: str, external_id: str) -> ExternalRecord:
    return ExternalRecord(key, external_id, f"verified-{key}")


def integrated_adapters(events: list[str]) -> dict[str, RecordingAdapter]:
    linear_records = (
        binding_record("linear", "binding.linear.workspace", "linear-workspace"),
        binding_record("linear", "binding.linear.team", "linear-team"),
        ExternalRecord("label.product.sample", "linear-label-sample", "label-v1"),
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


def verified_bindings_from_adapters(
    adapters: dict[str, RecordingAdapter],
) -> dict[str, object]:
    def verified_id(provider: str, stable_key: str) -> str:
        adapter = adapters[provider]
        records = adapter.find(stable_key)
        if len(records) != 1:
            raise AssertionError(f"expected one adapter binding record for {stable_key}")
        record = adapter.read(records[0].external_id)
        if record != records[0]:
            raise AssertionError(f"binding read-back mismatch for {stable_key}")
        return record.external_id

    return {
        "linear": {
            "verified": True,
            "values": {
                "workspace_id": verified_id("linear", "binding.linear.workspace"),
                "team_id": verified_id("linear", "binding.linear.team"),
            },
            "story_refs": {
                "sample": verified_id("linear", "label.product.sample")
            },
        },
        "notion": {
            "verified": True,
            "values": {
                "workspace_id": verified_id("notion", "binding.notion.workspace"),
                "products_database_id": verified_id("notion", "binding.notion.products"),
                "knowledge_database_id": verified_id("notion", "binding.notion.knowledge"),
                "contracts_database_id": verified_id("notion", "binding.notion.contracts"),
            },
            "knowledge_refs": {
                "sample": verified_id("notion", "binding.notion.product.sample")
            },
        },
    }


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
    documents = build_local_documents(
        topology,
        external_provider_selection(),
        verified_bindings_from_adapters(adapters),
        profile_settings,
        engineering_settings(),
    )
    normalized = {path: load_rendered_yaml(body) for path, body in documents.items()}
    expected_priors = tuple(
        (path, body_fingerprint(target.read_text(encoding="utf-8")))
        for path in sorted(documents)
        if (target := root / path).is_file()
        and target.read_text(encoding="utf-8") != documents[path]
    )
    setup_manifest = build_setup_manifest(
        topology,
        tuple(sorted(external_provider_selection().items())),
        (
            DesiredStructure(
                "linear", "ensure_label", "label.product.sample", "label-v1", True, False
            ),
        ),
        ExternalDiscovery(
            objects=(
                ExternalObject(
                    "linear",
                    "setup_structure",
                    "label.product.sample",
                    "Sample label",
                    "linear-label-sample",
                    "label-v1",
                ),
            )
        ),
        (
            ("story_store", complete_layers(STORY_RUNTIME_CAPABILITIES | {"ensure_label"})),
            ("product_knowledge_store", complete_layers(KNOWLEDGE_RUNTIME_CAPABILITIES)),
            ("product_contract_store", complete_layers(CONTRACT_RUNTIME_CAPABILITIES)),
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
        rendered_local_documents=tuple(sorted(documents.items())),
    )
    return approved(setup_manifest), documents


def commit_integrated_local(root: Path, value: ApprovedManifest) -> None:
    operations = tuple(
        operation
        for operation in value.manifest.operations
        if operation.kind is OperationKind.WRITE_LOCAL
    )
    AtomicLocalWriter(root, [])(
        operations,
        value.manifest.expected_local_container_fingerprint,
        "integration-bootstrap",
    )


class SetupApplyLocalFileIntegrationTests(unittest.TestCase):
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

            self.assertEqual(final_attestation_calls, 2)
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

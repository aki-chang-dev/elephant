"""Self-contained fake-adapter smoke for the installed setup-workspace runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .workspace_core import (
    CONTRACT_RUNTIME_CAPABILITIES,
    DELIVERY_RUNTIME_CAPABILITIES,
    KNOWLEDGE_RUNTIME_CAPABILITIES,
    STORY_RUNTIME_CAPABILITIES,
    ProviderKind,
    validate_workspace,
)
from .workspace_setup import (
    CapabilityLayers,
    ConfirmedDomain,
    ConfirmedProduct,
    ConfirmedTopology,
    DeletionReceipt,
    DesiredRelationship,
    DesiredStructure,
    ExternalDiscovery,
    ExternalRecord,
    FrozenList,
    FrozenMap,
    LocalDocumentSlot,
    LocalDocumentTemplate,
    MutationReceipt,
    ObservedRelationship,
    OperationKind,
    ProviderSemantics,
    RelationshipDeletionReceipt,
    RelationshipReceipt,
    RepositoryLocalWriter,
    WORKSPACE_PATH,
    apply_setup,
    approve_manifest,
    build_local_documents,
    build_setup_manifest,
    fingerprint_local_container,
    load_rendered_yaml,
    manifest_fingerprint,
    semantics_fingerprint,
)


class _FakeAdapter:
    provider = "linear"

    def __init__(self) -> None:
        self.records_by_key: dict[str, list[ExternalRecord]] = {}
        self.records_by_id: dict[str, ExternalRecord] = {}
        self.relationships: dict[str, ObservedRelationship] = {}
        self.deleted_keys: list[str] = []

    def find(self, stable_key: str) -> tuple[ExternalRecord, ...]:
        return tuple(self.records_by_key.get(stable_key, ()))

    def create(self, operation: object) -> MutationReceipt:
        external_id = f"linear-{len(self.records_by_id) + 1}"
        record = ExternalRecord(
            operation.target_key,
            external_id,
            operation.semantics,
        )
        self.records_by_key.setdefault(record.stable_key, []).append(record)
        self.records_by_id[external_id] = record
        return MutationReceipt(external_id)

    def read(self, external_id: str) -> ExternalRecord | None:
        return self.records_by_id.get(external_id)

    def bind_relationship(
        self,
        stable_key: str,
        source: ExternalRecord,
        target: ExternalRecord,
        desired: DesiredRelationship,
    ) -> RelationshipReceipt:
        relationship_id = f"relationship-{len(self.relationships) + 1}"
        self.relationships[relationship_id] = ObservedRelationship(
            stable_key=stable_key,
            relationship_id=relationship_id,
            source_external_id=source.external_id,
            target_external_id=target.external_id,
            semantics=desired,
        )
        return RelationshipReceipt(
            stable_key=stable_key,
            relationship_id=relationship_id,
            source_external_id=source.external_id,
            target_external_id=target.external_id,
        )

    def find_relationship(
        self,
        stable_key: str,
    ) -> tuple[ObservedRelationship, ...]:
        return tuple(
            relationship
            for relationship in self.relationships.values()
            if relationship.stable_key == stable_key
        )

    def read_relationship(
        self,
        relationship_id: str,
    ) -> ObservedRelationship | None:
        return self.relationships.get(relationship_id)

    def unbind_relationship(
        self,
        receipt: RelationshipReceipt,
    ) -> RelationshipDeletionReceipt:
        self.relationships.pop(receipt.relationship_id, None)
        return RelationshipDeletionReceipt(
            stable_key=receipt.stable_key,
            relationship_id=receipt.relationship_id,
            source_external_id=receipt.source_external_id,
            target_external_id=receipt.target_external_id,
        )

    def delete_disposable(
        self,
        external_id: str,
        stable_key: str,
    ) -> DeletionReceipt:
        record = self.records_by_id.pop(external_id)
        self.records_by_key[stable_key].remove(record)
        if not self.records_by_key[stable_key]:
            del self.records_by_key[stable_key]
        self.deleted_keys.append(stable_key)
        return DeletionReceipt(external_id, stable_key)


def _complete(capabilities: frozenset[str]) -> CapabilityLayers:
    return CapabilityLayers(capabilities, capabilities, capabilities, capabilities)


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return FrozenMap(
            tuple((key, _freeze(item)) for key, item in sorted(value.items()))
        )
    if isinstance(value, list):
        return FrozenList(tuple(_freeze(item) for item in value))
    return value


def _profile_settings(commands: list[str]) -> dict[str, object]:
    return {
        "context": {"knowledge_keys": []},
        "design_gate": {"enabled": False},
        "research": {"mode": "auto-assess"},
        "execution": {"isolation": "git-worktree"},
        "verification": {"commands": commands},
        "finish": {"integration": "github-pr-squash"},
        "language": {"dialogue": "en", "docs": "en"},
    }


def run_installed_smoke(repository_root: object) -> dict[str, object]:
    root = Path(repository_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    topology = ConfirmedTopology(
        repository_id="artifact-smoke",
        products=(ConfirmedProduct("sample", "Sample", ("web",)),),
        domains=(
            ConfirmedDomain(
                "web",
                "Web",
                ("sample",),
                ("apps/web",),
                ("AGENTS.md",),
                ("python3 -m unittest",),
            ),
        ),
    )
    providers = {
        "story_store": "linear",
        "product_knowledge_store": "git",
        "product_contract_store": "git",
        "delivery_workspace": "git",
    }
    slot_specs = {
        "linear.workspace_id": "binding.linear.workspace",
        "linear.team_id": "binding.linear.team",
        "linear.story.sample": "label.product.sample",
    }
    slots = {
        slot_id: LocalDocumentSlot(slot_id, "linear", stable_key)
        for slot_id, stable_key in slot_specs.items()
    }
    documents = build_local_documents(
        topology,
        providers,
        {
            "linear": {
                "planned": True,
                "values": {
                    "workspace_id": slots["linear.workspace_id"],
                    "team_id": slots["linear.team_id"],
                },
                "story_refs": {"sample": slots["linear.story.sample"]},
            },
        },
        {"sample": _profile_settings(["python3 -m unittest"])},
        _profile_settings(["python3 -m unittest discover -s tests"]),
    )
    rendered = {
        path: value.body if isinstance(value, LocalDocumentTemplate) else value
        for path, value in documents.items()
    }
    desired: list[DesiredStructure] = []
    for slot_id, stable_key in sorted(slot_specs.items()):
        semantics = ProviderSemantics(
            "setup_structure",
            FrozenMap((("slot_id", slot_id),)),
        )
        manual = slot_id == "linear.story.sample"
        desired.append(
            DesiredStructure(
                "linear",
                "ensure_manual_label" if manual else "ensure_binding",
                stable_key,
                semantics_fingerprint(semantics),
                True,
                False,
                logical_provider=ProviderKind.STORY,
                semantics=semantics,
                manual_instructions=(
                    "Create the approved Sample label with the exact fields.",
                ) if manual else (),
            )
        )
    workspace = load_rendered_yaml(rendered[WORKSPACE_PATH])
    frozen_workspace = _freeze(workspace)
    if not isinstance(frozen_workspace, FrozenMap):
        raise AssertionError("installed smoke workspace did not freeze as a mapping")
    profiles = tuple(
        (Path(path).stem, _freeze(load_rendered_yaml(body)))
        for path, body in sorted(rendered.items())
        if path != WORKSPACE_PATH
    )
    setup_manifest = build_setup_manifest(
        topology,
        tuple(sorted(providers.items())),
        tuple(desired),
        ExternalDiscovery(objects=()),
        (
            (
                "story_store",
                _complete(STORY_RUNTIME_CAPABILITIES | {"ensure_binding"}),
            ),
            ("product_knowledge_store", _complete(KNOWLEDGE_RUNTIME_CAPABILITIES)),
            ("product_contract_store", _complete(CONTRACT_RUNTIME_CAPABILITIES)),
            ("delivery_workspace", _complete(DELIVERY_RUNTIME_CAPABILITIES)),
        ),
        frozen_workspace.entries,
        profiles,
        expected_local_container_fingerprint=fingerprint_local_container(root),
        rendered_local_documents=tuple(sorted(documents.items())),
    )
    authority = approve_manifest(setup_manifest, manifest_fingerprint(setup_manifest))
    authority_identity = id(authority)
    approved_fingerprint = authority.fingerprint
    adapter = _FakeAdapter()
    writer = RepositoryLocalWriter(root)
    first_attempt = "artifact-manual-handoff"
    second_attempt = "artifact-manual-resume"

    first = apply_setup(
        authority,
        {"linear": adapter},
        writer,
        execution_id=first_attempt,
    )
    if first.ready or len(first.manual_handoffs) != 1:
        raise AssertionError("installed smoke did not stop at the manual handoff")
    manual = next(
        operation
        for operation in authority.manifest.operations
        if operation.kind is OperationKind.MANUAL
    )
    completed = ExternalRecord(
        manual.target_key,
        "linear-manual-sample",
        manual.semantics,
    )
    adapter.records_by_key[completed.stable_key] = [completed]
    adapter.records_by_id[completed.external_id] = completed

    second = apply_setup(
        authority,
        {"linear": adapter},
        writer,
        execution_id=second_attempt,
        resume_handoff=first.manual_handoffs[0],
    )
    workspace_body = (root / WORKSPACE_PATH).read_text(encoding="utf-8")
    observed_workspace = load_rendered_yaml(workspace_body)
    container = next(
        evidence
        for evidence in second.local_writes
        if evidence.operation_id == "local.container"
    )
    return {
        "status": "ok" if second.ready else "not_ready",
        "attempt_ids": [first_attempt, second_attempt],
        "same_approval": (
            id(authority) == authority_identity
            and authority.fingerprint == approved_fingerprint
        ),
        "schema_valid": validate_workspace(observed_workspace) == (),
        "placeholder_absent": "urn:elephant:setup-slot:" not in workspace_body,
        "binding_count": len(second.binding_receipts),
        "local_owner": container.external_id,
        "round_trip_keys": adapter.deleted_keys,
        "manifest_fingerprint": approved_fingerprint,
        "runtime_origin": str(Path(__file__).resolve()),
    }

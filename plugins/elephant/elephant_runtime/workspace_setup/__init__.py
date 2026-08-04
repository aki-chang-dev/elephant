"""Lazy public API for the canonical setup-workspace runtime."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "ApplyEvidence": ".models",
    "ApplyResult": ".models",
    "ApprovedManifest": ".models",
    "BindingReceipt": ".models",
    "Candidate": ".models",
    "CapabilityLayers": ".dry_run",
    "Confidence": ".models",
    "ConfirmedDomain": ".models",
    "ConfirmedProduct": ".models",
    "ConfirmedTopology": ".models",
    "ConflictResolution": ".models",
    "DeletionReceipt": ".apply",
    "DependencyEdge": ".models",
    "DesiredRelationship": ".models",
    "DesiredStructure": ".dry_run",
    "Evidence": ".models",
    "ExternalDiscovery": ".models",
    "ExternalObject": ".models",
    "ExternalRecord": ".apply",
    "FingerprintDomain": ".models",
    "FrozenList": ".models",
    "FrozenMap": ".models",
    "LocalBackendUnavailable": ".files",
    "LocalDocumentSlot": ".models",
    "LocalDocumentTemplate": ".models",
    "LocalWrite": ".files",
    "ManualHandoff": ".models",
    "MutationReceipt": ".apply",
    "ObservedRelationship": ".models",
    "OperationKind": ".models",
    "OwnerQuestion": ".models",
    "ProviderSemantics": ".models",
    "RelationshipDeletionReceipt": ".apply",
    "RelationshipReceipt": ".apply",
    "RepositoryDiscovery": ".discovery",
    "RepositoryLocalWriter": ".files",
    "SETUP_MANIFEST_SCHEMA": ".models",
    "SetupAdapter": ".apply",
    "SetupApplyError": ".apply",
    "SetupDiagnostic": ".models",
    "SetupManifest": ".models",
    "SetupOperation": ".models",
    "TopologyConflict": ".models",
    "TopologyProposal": ".models",
    "WORKSPACE_PATH": ".files",
    "WorkspaceUnit": ".models",
    "apply_local_write": ".files",
    "apply_setup": ".apply",
    "approve_manifest": ".models",
    "build_local_documents": ".files",
    "build_setup_manifest": ".dry_run",
    "confirm_topology": ".proposal",
    "discover_repository": ".discovery",
    "fingerprint_local_container": ".files",
    "load_rendered_yaml": ".files",
    "manifest_fingerprint": ".models",
    "normalize_external_discovery": ".discovery",
    "plan_local_writes": ".files",
    "propose_topology": ".proposal",
    "render_yaml": ".files",
    "semantics_fingerprint": ".models",
}

__all__ = tuple(sorted(_EXPORTS))


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))

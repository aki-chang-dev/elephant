from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass
from enum import Enum


STORY_RUNTIME_CAPABILITIES = frozenset({
    "create_story", "read_story", "update_story_status", "write_product_recap",
    "create_child_story", "link_story_relation", "bind_product_contract",
    "read_checkpoint", "write_checkpoint", "attach_delivery_evidence",
})
KNOWLEDGE_RUNTIME_CAPABILITIES = frozenset({
    "read_knowledge", "query_knowledge", "create_knowledge", "update_knowledge",
    "supersede_knowledge", "link_knowledge_relation",
})
CONTRACT_RUNTIME_CAPABILITIES = frozenset({
    "create_contract_draft", "read_contract", "update_contract_draft",
    "approve_contract", "create_contract_successor", "resolve_active_contract",
    "verify_contract_fingerprint", "verify_story_binding",
})
DELIVERY_RUNTIME_CAPABILITIES = frozenset({
    "persist_technical_contract", "persist_plan", "bind_delivery_branch",
    "record_conformance", "promote_knowledge", "remove_transient_artifacts",
})


class ProviderKind(str, Enum):
    STORY = "story"
    PRODUCT_KNOWLEDGE = "product_knowledge"
    PRODUCT_CONTRACT = "product_contract"
    DELIVERY_WORKSPACE = "delivery_workspace"


class DiagnosticCode(str, Enum):
    PLATFORM_UNSUPPORTED = "platform_unsupported"
    CONNECTOR_CAPABILITY_MISSING = "connector_capability_missing"
    PERMISSION_MISSING = "permission_missing"
    CONFIGURATION_MISSING = "configuration_missing"


@dataclass(frozen=True)
class CapabilityDiagnostic:
    capability: str
    code: DiagnosticCode


@dataclass(frozen=True)
class ProviderPreflight:
    ready: bool
    diagnostics: tuple[CapabilityDiagnostic, ...]


_CAPABILITIES_BY_PROVIDER = {
    ProviderKind.STORY: STORY_RUNTIME_CAPABILITIES,
    ProviderKind.PRODUCT_KNOWLEDGE: KNOWLEDGE_RUNTIME_CAPABILITIES,
    ProviderKind.PRODUCT_CONTRACT: CONTRACT_RUNTIME_CAPABILITIES,
    ProviderKind.DELIVERY_WORKSPACE: DELIVERY_RUNTIME_CAPABILITIES,
}


def preflight_provider(
    provider: ProviderKind,
    *,
    exposed: Set[str],
    permitted: Set[str],
    configured: Set[str],
    platform_supported: Set[str],
) -> ProviderPreflight:
    """Report the first unavailable layer for every required capability."""
    diagnostics: list[CapabilityDiagnostic] = []
    for capability in sorted(_CAPABILITIES_BY_PROVIDER[provider]):
        for available, code in (
            (platform_supported, DiagnosticCode.PLATFORM_UNSUPPORTED),
            (exposed, DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
            (permitted, DiagnosticCode.PERMISSION_MISSING),
            (configured, DiagnosticCode.CONFIGURATION_MISSING),
        ):
            if capability not in available:
                diagnostics.append(CapabilityDiagnostic(capability, code))
                break
    return ProviderPreflight(ready=not diagnostics, diagnostics=tuple(diagnostics))

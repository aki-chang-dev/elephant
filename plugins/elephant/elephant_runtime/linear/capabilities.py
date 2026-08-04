"""Exact capability inventory and preflight for the selected Linear provider."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from elephant_runtime.workspace_core import DiagnosticCode, STORY_RUNTIME_CAPABILITIES

from .models import LinearTool


HOST_RAW_SIGNED_PUT = "host_raw_signed_put"
TEAM_CREATION_CAPABILITY = "create_team"
WORKFLOW_STATUS_CREATION_CAPABILITY = "create_workflow_status"
WORKSPACE_LOCATOR_CAPABILITY = "workspace_locator"
PRODUCT_KIND_LABELS_CAPABILITY = "product_kind_labels"
CHECKPOINT_UPLOAD_CAPABILITY = "checkpoint_upload"
NATIVE_GITHUB_DIFF_CAPABILITY = "native_github_diff"
SANDBOX_CLEANUP_CAPABILITY = "sandbox_cleanup"


STORY_CAPABILITY_TOOLS = MappingProxyType({
    "create_story": frozenset({
        LinearTool.LIST_ISSUES, LinearTool.SAVE_ISSUE, LinearTool.GET_ISSUE,
    }),
    "read_story": frozenset({LinearTool.GET_ISSUE}),
    "update_story_status": frozenset({
        LinearTool.LIST_ISSUE_STATUSES, LinearTool.SAVE_ISSUE, LinearTool.GET_ISSUE,
    }),
    "write_product_recap": frozenset({LinearTool.SAVE_ISSUE, LinearTool.GET_ISSUE}),
    "create_child_story": frozenset({
        LinearTool.LIST_ISSUES, LinearTool.SAVE_ISSUE, LinearTool.GET_ISSUE,
    }),
    "link_story_relation": frozenset({LinearTool.SAVE_ISSUE, LinearTool.GET_ISSUE}),
    "bind_product_contract": frozenset({LinearTool.SAVE_ISSUE, LinearTool.GET_ISSUE}),
    "read_checkpoint": frozenset({LinearTool.GET_ISSUE, LinearTool.GET_ATTACHMENT}),
    "write_checkpoint": frozenset({
        LinearTool.PREPARE_ATTACHMENT_UPLOAD,
        LinearTool.CREATE_ATTACHMENT_FROM_UPLOAD,
        LinearTool.GET_ATTACHMENT,
        LinearTool.GET_ISSUE,
        LinearTool.DELETE_ATTACHMENT,
    }),
    "attach_delivery_evidence": frozenset({
        LinearTool.LIST_COMMENTS, LinearTool.SAVE_COMMENT, LinearTool.GET_ISSUE,
    }),
})

STORY_CAPABILITY_PLATFORM_REQUIREMENTS = MappingProxyType({
    capability: frozenset({HOST_RAW_SIGNED_PUT}) if capability == "write_checkpoint" else frozenset()
    for capability in STORY_RUNTIME_CAPABILITIES
})

READ_ONLY_DISCOVERY_TOOLS = frozenset({
    LinearTool.LIST_TEAMS,
    LinearTool.GET_TEAM,
    LinearTool.GET_USER,
    LinearTool.LIST_ISSUE_STATUSES,
    LinearTool.LIST_ISSUE_LABELS,
    LinearTool.LIST_ISSUES,
    LinearTool.GET_ISSUE,
})

ADMIN_CAPABILITY_TOOLS = MappingProxyType({
    TEAM_CREATION_CAPABILITY: frozenset(),
    WORKFLOW_STATUS_CREATION_CAPABILITY: frozenset(),
    WORKSPACE_LOCATOR_CAPABILITY: frozenset(),
    PRODUCT_KIND_LABELS_CAPABILITY: frozenset({
        LinearTool.CREATE_ISSUE_LABEL, LinearTool.LIST_ISSUE_LABELS,
    }),
    CHECKPOINT_UPLOAD_CAPABILITY: STORY_CAPABILITY_TOOLS["write_checkpoint"],
    NATIVE_GITHUB_DIFF_CAPABILITY: frozenset({LinearTool.LIST_DIFFS, LinearTool.GET_DIFF}),
    SANDBOX_CLEANUP_CAPABILITY: frozenset({
        LinearTool.LIST_ISSUES,
        LinearTool.SAVE_ISSUE,
        LinearTool.GET_ISSUE,
        LinearTool.LIST_COMMENTS,
        LinearTool.DELETE_COMMENT,
        LinearTool.GET_ATTACHMENT,
        LinearTool.DELETE_ATTACHMENT,
    }),
})

_ADMIN_PLATFORM_REQUIREMENTS = MappingProxyType({
    capability: frozenset({HOST_RAW_SIGNED_PUT})
    if capability == CHECKPOINT_UPLOAD_CAPABILITY
    else frozenset()
    for capability in ADMIN_CAPABILITY_TOOLS
})

_UNEXPOSED_CAPABILITIES = frozenset({
    TEAM_CREATION_CAPABILITY,
    WORKFLOW_STATUS_CREATION_CAPABILITY,
    WORKSPACE_LOCATOR_CAPABILITY,
})

_CAPABILITY_TOOLS = MappingProxyType({**STORY_CAPABILITY_TOOLS, **ADMIN_CAPABILITY_TOOLS})
_CAPABILITY_PLATFORM_REQUIREMENTS = MappingProxyType({
    **STORY_CAPABILITY_PLATFORM_REQUIREMENTS,
    **_ADMIN_PLATFORM_REQUIREMENTS,
})


def _as_frozenset(name: str, values: object) -> frozenset[str]:
    if not isinstance(values, (set, frozenset)) or not all(isinstance(value, str) for value in values):
        raise TypeError(f"{name}: expected set-like string collection")
    return frozenset(values)


@dataclass(frozen=True)
class LinearCapabilityInventory:
    platform_supported: frozenset[str]
    exposed: frozenset[str]
    permitted: frozenset[str]
    configured: frozenset[str]

    def __post_init__(self) -> None:
        for name in ("platform_supported", "exposed", "permitted", "configured"):
            object.__setattr__(self, name, _as_frozenset(name, getattr(self, name)))


@dataclass(frozen=True)
class LinearProviderDiagnostic:
    capability: str
    code: DiagnosticCode
    blocking: bool
    instructions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.capability, str) or not self.capability:
            raise ValueError("capability: expected non-empty string")
        if not isinstance(self.code, DiagnosticCode):
            raise TypeError("code: expected DiagnosticCode")
        if not isinstance(self.blocking, bool):
            raise TypeError("blocking: expected bool")
        if not isinstance(self.instructions, tuple) or not all(
            isinstance(instruction, str) and instruction for instruction in self.instructions
        ):
            raise TypeError("instructions: expected tuple of non-empty strings")


@dataclass(frozen=True)
class LinearCapabilityPreflight:
    ready: bool
    diagnostics: tuple[LinearProviderDiagnostic, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.ready, bool):
            raise TypeError("ready: expected bool")
        if not isinstance(self.diagnostics, (list, tuple)) or not all(
            isinstance(diagnostic, LinearProviderDiagnostic)
            for diagnostic in self.diagnostics
        ):
            raise TypeError("diagnostics: expected LinearProviderDiagnostic sequence")
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


def _first_missing_code(
    inventory: LinearCapabilityInventory,
    capability: str,
) -> DiagnosticCode | None:
    tools = frozenset(tool.value for tool in _CAPABILITY_TOOLS[capability])
    platform_requirements = tools | _CAPABILITY_PLATFORM_REQUIREMENTS[capability]
    if not platform_requirements <= inventory.platform_supported:
        return DiagnosticCode.PLATFORM_UNSUPPORTED
    if capability in _UNEXPOSED_CAPABILITIES or not tools <= inventory.exposed:
        return DiagnosticCode.CONNECTOR_CAPABILITY_MISSING
    if not platform_requirements <= inventory.permitted:
        return DiagnosticCode.PERMISSION_MISSING
    if capability not in inventory.configured:
        return DiagnosticCode.CONFIGURATION_MISSING
    return None


def preflight_story_capabilities(
    inventory: LinearCapabilityInventory,
    *,
    capabilities: tuple[str, ...] | frozenset[str] = STORY_RUNTIME_CAPABILITIES,
) -> LinearCapabilityPreflight:
    """Report first-unavailable layers for the explicitly selected Linear provider."""
    if not isinstance(inventory, LinearCapabilityInventory):
        raise TypeError("inventory: expected LinearCapabilityInventory")
    if not isinstance(capabilities, (tuple, frozenset)) or not all(
        isinstance(capability, str) for capability in capabilities
    ):
        raise TypeError("capabilities: expected immutable capability collection")
    unknown = sorted(set(capabilities) - set(_CAPABILITY_TOOLS))
    if unknown:
        raise ValueError(f"capabilities: unknown Linear capability {unknown[0]!r}")
    diagnostics = tuple(
        LinearProviderDiagnostic(capability, code, True)
        for capability in sorted(capabilities)
        if (code := _first_missing_code(inventory, capability)) is not None
    )
    return LinearCapabilityPreflight(ready=not diagnostics, diagnostics=diagnostics)

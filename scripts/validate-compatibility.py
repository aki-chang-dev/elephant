#!/usr/bin/env python3
"""Validate Elephant's shared Claude Code and Codex plugin contract."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys


PLUGIN = Path("plugins/elephant")
CODEX_MANIFEST = PLUGIN / ".codex-plugin/plugin.json"
CLAUDE_MANIFEST = PLUGIN / ".claude-plugin/plugin.json"
CODEX_MARKETPLACE = Path(".agents/plugins/marketplace.json")
CLAUDE_MARKETPLACE = Path(".claude-plugin/marketplace.json")

FORBIDDEN_CORE_PHRASES = (
    ".claude/delivery-profile.md",
    "via the Skill tool",
    "`Explore`",
    "claudemd_refresh_targets",
)

REQUIRED_V2_ASSETS = (
    "shape-story/SKILL.md",
    "shape-story/product-contract-template.md",
    "shape-story/reviewers/product-ux-critic.md",
    "shape-story/reviewers/copy-critic.md",
    "author-technical-contract/SKILL.md",
    "author-technical-contract/technical-contract-template.md",
    "author-technical-contract/reviewers/architecture.md",
    "author-technical-contract/reviewers/domain-data.md",
    "author-technical-contract/reviewers/security-operations.md",
    "author-technical-contract/reviewers/product-conformance.md",
    "author-technical-contract/reviewers/test.md",
    "author-technical-contract/reviewers/technical-adjudicator.md",
    "ship-story/reviewers/implementation-conformance.md",
)

REQUIRED_V3_CORE_ASSETS = (
    "workspace/workspace-schema.md",
    "workspace/profile-schema.md",
    "workspace/provider-contracts.md",
    "workspace/story-state-model.md",
)

REQUIRED_V3_SETUP_ASSETS = (
    "skills/setup-workspace/SKILL.md",
    "references/workspace/setup-workspace.md",
)

REQUIRED_V3_CORE_EXPORTS = frozenset({
    "CONTRACT_RUNTIME_CAPABILITIES",
    "DELIVERY_RUNTIME_CAPABILITIES",
    "KNOWLEDGE_RUNTIME_CAPABILITIES",
    "STORY_RUNTIME_CAPABILITIES",
    "CapabilityDiagnostic",
    "CheckpointPhase",
    "DiagnosticCode",
    "DriftKind",
    "HumanStatus",
    "ProductDisposition",
    "ProviderKind",
    "ProviderPreflight",
    "RepairAction",
    "WorkspaceRouteError",
    "can_transition_human_status",
    "preflight_provider",
    "repair_action",
    "resolve_profile",
    "terminal_status_for_disposition",
    "validate_profile",
    "validate_workspace",
})

REQUIRED_V3_SETUP_EXPORTS = frozenset({
    "ApplyEvidence", "ApplyResult", "ApprovedManifest", "Candidate",
    "CapabilityLayers", "Confidence", "ConfirmedDomain", "ConfirmedProduct",
    "ConfirmedTopology", "DeletionReceipt", "DependencyEdge", "DesiredStructure",
    "Evidence", "ExternalDiscovery", "ExternalObject", "ExternalRecord",
    "LocalWrite", "MutationReceipt", "OperationKind", "OwnerQuestion",
    "RepositoryDiscovery", "SETUP_MANIFEST_SCHEMA", "SetupAdapter",
    "SetupApplyError", "SetupDiagnostic", "SetupManifest", "SetupOperation",
    "TopologyConflict", "TopologyProposal", "WORKSPACE_PATH", "WorkspaceUnit",
    "apply_local_write", "apply_setup", "approve_manifest", "build_local_documents",
    "build_setup_manifest", "confirm_topology", "discover_repository",
    "load_rendered_yaml", "manifest_fingerprint", "normalize_external_discovery",
    "plan_local_writes", "propose_topology", "render_yaml",
})

V3_SETUP_ENUM_VALUES = {
    "Confidence": ("confirmed", "high", "medium", "low"),
    "OperationKind": (
        "reuse",
        "create",
        "manual",
        "verify",
        "round_trip",
        "write_local",
    ),
}

V3_SETUP_MANIFEST_SCHEMA = "elephant.setup-manifest/v1"

V3_CORE_ENUM_VALUES = {
    "ProviderKind": (
        "story",
        "product_knowledge",
        "product_contract",
        "delivery_workspace",
    ),
    "DiagnosticCode": (
        "platform_unsupported",
        "connector_capability_missing",
        "permission_missing",
        "configuration_missing",
    ),
    "HumanStatus": ("Backlog", "Shaping", "Ready", "In Progress", "Done", "Canceled"),
    "ProductDisposition": ("approved", "split", "deferred", "rejected"),
    "CheckpointPhase": (
        "contract_pending",
        "shaping",
        "ready",
        "technical",
        "implementing",
        "conformance",
        "closeout",
        "done",
        "needs_product_decision",
    ),
    "DriftKind": (
        "stale_recap",
        "missing_reciprocal_link",
        "verified_checkpoint_lag",
        "timed_out_write",
        "approved_contract_changed",
        "product_assignment_changed",
        "human_status_advanced",
        "duplicate_authority",
    ),
    "RepairAction": ("auto_repair", "stop"),
}

V3_CORE_CAPABILITY_SETS = {
    "STORY_RUNTIME_CAPABILITIES": frozenset({
        "create_story",
        "read_story",
        "update_story_status",
        "write_product_recap",
        "create_child_story",
        "link_story_relation",
        "bind_product_contract",
        "read_checkpoint",
        "write_checkpoint",
        "attach_delivery_evidence",
    }),
    "KNOWLEDGE_RUNTIME_CAPABILITIES": frozenset({
        "read_knowledge",
        "query_knowledge",
        "create_knowledge",
        "update_knowledge",
        "supersede_knowledge",
        "link_knowledge_relation",
    }),
    "CONTRACT_RUNTIME_CAPABILITIES": frozenset({
        "create_contract_draft",
        "read_contract",
        "update_contract_draft",
        "approve_contract",
        "create_contract_successor",
        "resolve_active_contract",
        "verify_contract_fingerprint",
        "verify_story_binding",
    }),
    "DELIVERY_RUNTIME_CAPABILITIES": frozenset({
        "persist_technical_contract",
        "persist_plan",
        "bind_delivery_branch",
        "record_conformance",
        "promote_knowledge",
        "remove_transient_artifacts",
    }),
}

V3_CORE_HUMAN_TRANSITIONS = frozenset({
    ("Backlog", "Shaping"),
    ("Shaping", "Ready"),
    ("Shaping", "Backlog"),
    ("Shaping", "Canceled"),
    ("Ready", "In Progress"),
    ("Ready", "Shaping"),
    ("Ready", "Backlog"),
    ("Ready", "Canceled"),
    ("In Progress", "Shaping"),
    ("In Progress", "Done"),
    ("In Progress", "Canceled"),
})

V3_CORE_DISPOSITION_STATUSES = {
    "approved": "Ready",
    "split": "Canceled",
    "deferred": "Backlog",
    "rejected": "Canceled",
}

V3_CORE_REPAIR_ACTIONS = {
    "stale_recap": "auto_repair",
    "missing_reciprocal_link": "auto_repair",
    "verified_checkpoint_lag": "auto_repair",
    "timed_out_write": "auto_repair",
    "approved_contract_changed": "stop",
    "product_assignment_changed": "stop",
    "human_status_advanced": "stop",
    "duplicate_authority": "stop",
}


def _load_json(path: Path, label: str, errors: list[str]) -> dict | None:
    if not path.is_file():
        errors.append(f"missing {label}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid {label}: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"invalid {label}: root must be an object")
        return None
    return value


def _validate_frontmatter(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---(?:\n|\Z)", text, re.DOTALL)
    if not match:
        errors.append(f"{path}: missing YAML frontmatter")
        return
    frontmatter = match.group(1)
    for field in ("name", "description"):
        field_match = re.search(rf"(?m)^{field}:\s*(.+?)\s*$", frontmatter)
        if not field_match or not field_match.group(1).strip("\"' "):
            errors.append(f"{path}: missing frontmatter field {field}")


def _validate_manifests(root: Path, errors: list[str]) -> None:
    codex = _load_json(root / CODEX_MANIFEST, "Codex plugin manifest", errors)
    claude = _load_json(root / CLAUDE_MANIFEST, "Claude plugin manifest", errors)
    if codex is None or claude is None:
        return
    if codex.get("name") != claude.get("name"):
        errors.append("plugin manifest names differ")
    if codex.get("version") != claude.get("version"):
        errors.append("plugin manifest versions differ")
    if codex.get("skills") != "./skills/":
        errors.append('Codex plugin manifest must set skills to "./skills/"')


def _validate_marketplaces(root: Path, errors: list[str]) -> None:
    codex = _load_json(root / CODEX_MARKETPLACE, "Codex marketplace", errors)
    _load_json(root / CLAUDE_MARKETPLACE, "Claude marketplace", errors)
    if codex is None:
        return
    entries = codex.get("plugins")
    if not isinstance(entries, list):
        errors.append("Codex marketplace plugins must be an array")
        return
    elephant = next(
        (entry for entry in entries if isinstance(entry, dict) and entry.get("name") == "elephant"),
        None,
    )
    if elephant is None:
        errors.append("Codex marketplace is missing the elephant entry")
        return
    expected_source = {"source": "local", "path": "./plugins/elephant"}
    if elephant.get("source") != expected_source:
        errors.append("Codex marketplace elephant source is invalid")
    source_path = elephant.get("source", {}).get("path")
    if isinstance(source_path, str):
        resolved = (root / source_path).resolve()
        if resolved != (root / PLUGIN).resolve():
            errors.append("Codex marketplace source does not resolve to plugins/elephant")
    expected_policy = {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
    if elephant.get("policy") != expected_policy:
        errors.append("Codex marketplace elephant policy is invalid")
    if elephant.get("category") != "Productivity":
        errors.append("Codex marketplace elephant category must be Productivity")


def _validate_skills(root: Path, errors: list[str]) -> None:
    skills_root = root / PLUGIN / "skills"
    if not skills_root.is_dir():
        errors.append("missing shared skills directory")
        return
    skill_files = sorted(skills_root.glob("*/SKILL.md"))
    if not skill_files:
        errors.append("shared skills directory contains no skills")
        return
    for path in skill_files:
        _validate_frontmatter(path, errors)
        text = path.read_text(encoding="utf-8")
        for phrase in FORBIDDEN_CORE_PHRASES:
            if phrase in text:
                relative = path.relative_to(root)
                errors.append(
                    f"{relative}: Claude-only core phrase is forbidden: {phrase}"
                )


def _validate_v2_assets(root: Path, errors: list[str]) -> None:
    skills_root = root / PLUGIN / "skills"
    for relative in REQUIRED_V2_ASSETS:
        path = skills_root / relative
        if not path.is_file():
            errors.append(
                f"missing required v2 asset: {(PLUGIN / 'skills' / relative).as_posix()}"
            )


def _validate_v3_core_assets(root: Path, errors: list[str]) -> None:
    references_root = root / PLUGIN / "references"
    for relative in REQUIRED_V3_CORE_ASSETS:
        path = references_root / relative
        if not path.is_file():
            errors.append(f"missing v3 workspace core asset: {path.relative_to(root)}")


def _validate_v3_setup_assets(root: Path, errors: list[str]) -> None:
    plugin_root = root / PLUGIN
    for relative in REQUIRED_V3_SETUP_ASSETS:
        path = plugin_root / relative
        if not path.is_file():
            errors.append(f"missing v3 setup asset: {path.relative_to(root)}")


def _load_v3_core_oracle(root: Path, errors: list[str]):
    package_path = root / "scripts/workspace_core/__init__.py"
    if not package_path.is_file():
        errors.append(
            "missing v3 workspace core oracle: scripts/workspace_core/__init__.py"
        )
        return None

    package_name = f"_elephant_workspace_core_{abs(hash(root.resolve()))}"
    spec = importlib.util.spec_from_file_location(
        package_name,
        package_path,
        submodule_search_locations=[str(package_path.parent)],
    )
    if spec is None or spec.loader is None:
        errors.append("invalid v3 workspace core oracle: package cannot be loaded")
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        errors.append(
            "invalid v3 workspace core oracle: import failed: "
            f"{type(exc).__name__}: {exc}"
        )
        return None
    finally:
        for name in tuple(sys.modules):
            if name == package_name or name.startswith(f"{package_name}."):
                del sys.modules[name]
    return module


def _validate_v3_core_oracle(root: Path, errors: list[str]) -> None:
    core = _load_v3_core_oracle(root, errors)
    if core is None:
        return

    try:
        exports = frozenset(core.__all__)
    except (AttributeError, TypeError):
        exports = frozenset()
    if exports != REQUIRED_V3_CORE_EXPORTS:
        errors.append("invalid v3 workspace core oracle: public exports differ")

    for name, expected in V3_CORE_ENUM_VALUES.items():
        try:
            actual = tuple(member.value for member in getattr(core, name))
        except (AttributeError, TypeError):
            actual = None
        if actual != expected:
            errors.append(f"invalid v3 workspace core oracle: {name} values differ")

    for name, expected in V3_CORE_CAPABILITY_SETS.items():
        try:
            actual = frozenset(getattr(core, name))
        except (AttributeError, TypeError):
            actual = None
        if actual != expected:
            errors.append(f"invalid v3 workspace core oracle: {name} differs")

    try:
        actual_transitions = frozenset(
            (current.value, target.value)
            for current in core.HumanStatus
            for target in core.HumanStatus
            if core.can_transition_human_status(current, target)
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        actual_transitions = None
    if actual_transitions != V3_CORE_HUMAN_TRANSITIONS:
        errors.append("invalid v3 workspace core oracle: human transition matrix differs")

    try:
        actual_dispositions = {
            disposition.value: core.terminal_status_for_disposition(disposition).value
            for disposition in core.ProductDisposition
        }
    except (AttributeError, KeyError, TypeError, ValueError):
        actual_dispositions = None
    if actual_dispositions != V3_CORE_DISPOSITION_STATUSES:
        errors.append("invalid v3 workspace core oracle: disposition mapping differs")

    try:
        actual_repairs = {
            drift_kind.value: core.repair_action(drift_kind).value
            for drift_kind in core.DriftKind
        }
    except (AttributeError, KeyError, TypeError, ValueError):
        actual_repairs = None
    if actual_repairs != V3_CORE_REPAIR_ACTIONS:
        errors.append("invalid v3 workspace core oracle: repair mapping differs")

    provider_capabilities = (
        (
            "story",
            "STORY_RUNTIME_CAPABILITIES",
            "attach_delivery_evidence",
            "bind_product_contract",
        ),
        (
            "product_knowledge",
            "KNOWLEDGE_RUNTIME_CAPABILITIES",
            "create_knowledge",
            "link_knowledge_relation",
        ),
        (
            "product_contract",
            "CONTRACT_RUNTIME_CAPABILITIES",
            "approve_contract",
            "create_contract_draft",
        ),
        (
            "delivery_workspace",
            "DELIVERY_RUNTIME_CAPABILITIES",
            "bind_delivery_branch",
            "persist_plan",
        ),
    )
    cumulative_failures = (
        (
            ("platform_supported", "exposed", "permitted", "configured"),
            "platform_unsupported",
        ),
        (
            ("exposed", "permitted", "configured"),
            "connector_capability_missing",
        ),
        (("permitted", "configured"), "permission_missing"),
        (("configured",), "configuration_missing"),
    )
    try:
        precedence_matches = True
        for (
            provider_value,
            capabilities_name,
            platform_capability,
            connector_capability,
        ) in provider_capabilities:
            required = getattr(core, capabilities_name)
            for missing_layers, expected_code in cumulative_failures:
                available = {
                    "platform_supported": required,
                    "exposed": required,
                    "permitted": required,
                    "configured": required,
                }
                for missing_layer in missing_layers:
                    available[missing_layer] = required - {platform_capability}
                result = core.preflight_provider(provider_value, **available)
                observed = tuple(
                    (diagnostic.capability, diagnostic.code.value)
                    for diagnostic in result.diagnostics
                )
                if result.ready or observed != ((platform_capability, expected_code),):
                    precedence_matches = False

            both = {platform_capability, connector_capability}
            result = core.preflight_provider(
                provider_value,
                platform_supported=required - {platform_capability},
                exposed=required - both,
                permitted=required - both,
                configured=required - both,
            )
            observed = tuple(
                (diagnostic.capability, diagnostic.code.value)
                for diagnostic in result.diagnostics
            )
            if result.ready or observed != (
                (platform_capability, "platform_unsupported"),
                (connector_capability, "connector_capability_missing"),
            ):
                precedence_matches = False
    except (AttributeError, KeyError, TypeError, ValueError):
        precedence_matches = False
    if not precedence_matches:
        errors.append("invalid v3 workspace core oracle: diagnostic precedence differs")


def _load_v3_setup_oracle(root: Path, errors: list[str]):
    package_path = root / "scripts/workspace_setup/__init__.py"
    if not package_path.is_file():
        errors.append("missing v3 setup oracle: scripts/workspace_setup/__init__.py")
        return None

    package_name = f"_elephant_workspace_setup_{abs(hash(root.resolve()))}"
    spec = importlib.util.spec_from_file_location(
        package_name,
        package_path,
        submodule_search_locations=[str(package_path.parent)],
    )
    if spec is None or spec.loader is None:
        errors.append("invalid v3 setup oracle: package cannot be loaded")
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    root_string = str(root)
    inserted_root = root_string not in sys.path
    if inserted_root:
        sys.path.insert(0, root_string)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        errors.append(
            "invalid v3 setup oracle: import failed: "
            f"{type(exc).__name__}: {exc}"
        )
        return None
    finally:
        for name in tuple(sys.modules):
            if name == package_name or name.startswith(f"{package_name}."):
                del sys.modules[name]
        if inserted_root:
            sys.path.remove(root_string)
    return module


def _setup_fingerprint_fixture(setup):
    return setup.SetupManifest(
        schema=V3_SETUP_MANIFEST_SCHEMA,
        repository_id="repo-compatibility",
        provider_selection=(
            ("delivery_workspace", "git"),
            ("product_contract_store", "git"),
            ("product_knowledge_store", "git"),
            ("story_store", "git"),
        ),
        products=(),
        domains=(),
        operations=(),
        diagnostics=(),
        conflicts=(),
        questions=(),
        expected_local_container_fingerprint="0" * 64,
        registry=(("schema", "elephant.workspace/v3"),),
        profiles=(),
    )


def _expected_setup_fingerprint() -> str:
    payload = {
        "conflicts": [],
        "diagnostics": [],
        "domains": [],
        "expected_local_container_fingerprint": "0" * 64,
        "operations": [],
        "products": [],
        "profiles": [],
        "provider_selection": {
            "delivery_workspace": "git",
            "product_contract_store": "git",
            "product_knowledge_store": "git",
            "story_store": "git",
        },
        "questions": [],
        "registry": {"schema": "elephant.workspace/v3"},
        "repository_id": "repo-compatibility",
        "schema": V3_SETUP_MANIFEST_SCHEMA,
    }
    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _validate_v3_setup_oracle(root: Path, errors: list[str]) -> None:
    setup = _load_v3_setup_oracle(root, errors)
    if setup is None:
        return

    try:
        exports = frozenset(setup.__all__)
    except (AttributeError, TypeError):
        exports = frozenset()
    if exports != REQUIRED_V3_SETUP_EXPORTS:
        errors.append("invalid v3 setup oracle: public exports differ")

    for name, expected in V3_SETUP_ENUM_VALUES.items():
        try:
            actual = tuple(member.value for member in getattr(setup, name))
        except (AttributeError, TypeError):
            actual = None
        if actual != expected:
            errors.append(f"invalid v3 setup oracle: {name} values differ")

    if getattr(setup, "SETUP_MANIFEST_SCHEMA", None) != V3_SETUP_MANIFEST_SCHEMA:
        errors.append("invalid v3 setup oracle: manifest schema differs")

    fingerprint_matches = False
    try:
        manifest = _setup_fingerprint_fixture(setup)
        expected_fingerprint = _expected_setup_fingerprint()
        observed_fingerprint = setup.manifest_fingerprint(manifest)
        approved = setup.approve_manifest(manifest, expected_fingerprint)
        try:
            setup.approve_manifest(manifest, "f" * 64)
        except ValueError:
            stale_rejected = True
        else:
            stale_rejected = False
        fingerprint_matches = (
            observed_fingerprint == expected_fingerprint
            and approved.manifest is manifest
            and approved.fingerprint == expected_fingerprint
            and stale_rejected
        )
    except (AttributeError, TypeError, ValueError):
        pass
    if not fingerprint_matches:
        errors.append(
            "invalid v3 setup oracle: approval fingerprint behavior differs"
        )


def validate_repository(root: Path) -> list[str]:
    """Return every compatibility error found below *root*."""
    errors: list[str] = []
    _validate_manifests(root, errors)
    _validate_marketplaces(root, errors)
    _validate_skills(root, errors)
    _validate_v2_assets(root, errors)
    _validate_v3_core_assets(root, errors)
    _validate_v3_core_oracle(root, errors)
    _validate_v3_setup_assets(root, errors)
    _validate_v3_setup_oracle(root, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    errors = validate_repository(args.root.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Elephant compatibility validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from dataclasses import replace
import json
from pathlib import Path
import unittest

from scripts.workspace_core import (
    CONTRACT_RUNTIME_CAPABILITIES,
    DELIVERY_RUNTIME_CAPABILITIES,
    KNOWLEDGE_RUNTIME_CAPABILITIES,
    STORY_RUNTIME_CAPABILITIES,
    DiagnosticCode,
    ProviderKind,
)
from scripts.workspace_setup import (
    Candidate,
    CapabilityLayers,
    Confidence,
    ConfirmedDomain,
    ConfirmedProduct,
    ConfirmedTopology,
    ConflictResolution,
    DesiredStructure,
    Evidence,
    ExternalDiscovery,
    ExternalObject,
    FrozenMap,
    FrozenList,
    LocalDocumentSlot,
    LocalDocumentTemplate,
    OperationKind,
    ProviderSemantics,
    build_setup_manifest,
    manifest_fingerprint,
    normalize_external_discovery,
    semantics_fingerprint,
)
from tests.test_setup_files import (
    build_documents,
    build_git_documents,
    build_local_documents,
    engineering_settings,
    planned_bindings,
    product_settings,
)


FIXTURES = Path(__file__).parent / "fixtures" / "setup-workspace"


def freeze_canonical_document(value, *, top_level=True):
    if isinstance(value, dict):
        entries = tuple(
            (key, freeze_canonical_document(item, top_level=False))
            for key, item in sorted(value.items())
        )
        return entries if top_level else FrozenMap(entries)
    if isinstance(value, list):
        return FrozenList(
            tuple(
                freeze_canonical_document(item, top_level=False)
                for item in value
            )
        )
    return value


def canonical_git_inputs():
    documents = build_git_documents()
    loaded = {
        path: json.loads(body)
        for path, body in documents.items()
    }
    registry = freeze_canonical_document(
        loaded[".agents/elephant/workspace.yaml"]
    )
    profiles = tuple(
        (
            Path(path).stem,
            freeze_canonical_document(document),
        )
        for path, document in sorted(loaded.items())
        if path != ".agents/elephant/workspace.yaml"
    )
    return registry, profiles, documents


def complete_layers(capabilities):
    return CapabilityLayers(
        platform_supported=capabilities,
        exposed=capabilities,
        permitted=capabilities,
        configured=capabilities,
    )


def layers_with(capabilities, *additional):
    return complete_layers(capabilities | frozenset(additional))


def topology() -> ConfirmedTopology:
    return ConfirmedTopology(
        repository_id="fixture-single",
        products=(ConfirmedProduct("sample", "Sample", ("web",)),),
        domains=(ConfirmedDomain("web", "Web", ("sample",), ("apps/web",), ("AGENTS.md",), ("bun run type-check",)),),
    )


def external_object(stable_key: str, fingerprint: str, provider: str = "linear") -> ExternalObject:
    return ExternalObject(
        provider=provider,
        kind="setup_structure",
        key=stable_key,
        display_name=stable_key,
        external_id=f"id-{stable_key}",
        fingerprint=fingerprint,
    )


def desired_semantics(revision: str) -> ProviderSemantics:
    return ProviderSemantics(
        resource_type="setup_structure",
        fields=FrozenMap((("revision", revision),)),
    )


def typed_structure(
    logical_provider: ProviderKind,
    provider: str,
    capability: str,
    stable_key: str,
    revision: str,
    *,
    administrative: bool,
    runtime_required: bool,
    manual_instructions: tuple[str, ...] = (),
) -> DesiredStructure:
    semantics = desired_semantics(revision)
    return DesiredStructure(
        logical_provider=logical_provider,
        provider=provider,
        capability=capability,
        logical_key=stable_key,
        desired_fingerprint=semantics_fingerprint(semantics),
        semantics=semantics,
        administrative=administrative,
        runtime_required=runtime_required,
        manual_instructions=manual_instructions,
    )


def build_manifest_with(
    *,
    topology_value=None,
    story_store="linear",
    product_knowledge_store="notion",
    product_contract_store="notion",
    delivery_workspace="git",
    story_layers=None,
    knowledge_layers=None,
    contract_layers=None,
    delivery_layers=None,
    desired_structures=(),
    external_objects=(),
    registry=None,
    profiles=None,
    expected_local_container_fingerprint="a" * 64,
    expected_prior_fingerprints=(),
    observed_local_fingerprints=(),
    rendered_local_documents=(),
):
    selected_topology = topology() if topology_value is None else topology_value
    providers = {
        "story_store": story_store,
        "product_knowledge_store": product_knowledge_store,
        "product_contract_store": product_contract_store,
        "delivery_workspace": delivery_workspace,
    }
    if registry is None or profiles is None:
        valid_choices = {
            "story_store": {"git", "linear"},
            "product_knowledge_store": {"git", "notion"},
            "product_contract_store": {"git", "notion"},
            "delivery_workspace": {"git", "linear"},
        }
        if any(
            provider not in valid_choices[logical]
            for logical, provider in providers.items()
        ):
            fallback_registry, fallback_profiles, _ = canonical_git_inputs()
            loaded_documents = {}
            if registry is None:
                registry = fallback_registry
            if profiles is None:
                profiles = fallback_profiles
        else:
            external_providers = set(providers.values()) - {"git"}
            bindings = {
                provider: value
                for provider, value in planned_bindings().items()
                if provider in external_providers
            }
            base_product_settings = product_settings()["sample"]
            local_documents = build_local_documents(
                selected_topology,
                providers,
                bindings,
                {
                    product.key: base_product_settings
                    for product in selected_topology.products
                },
                engineering_settings(),
            )
            loaded_documents = {
                path: json.loads(
                    value.body
                    if isinstance(value, LocalDocumentTemplate)
                    else value
                )
                for path, value in local_documents.items()
            }
        if registry is None:
            registry = freeze_canonical_document(
                loaded_documents[".agents/elephant/workspace.yaml"]
            )
        if profiles is None:
            profiles = tuple(
                (Path(path).stem, freeze_canonical_document(document))
                for path, document in sorted(loaded_documents.items())
                if path != ".agents/elephant/workspace.yaml"
            )
    return build_setup_manifest(
        selected_topology,
        tuple(providers.items()),
        desired_structures,
        ExternalDiscovery(objects=external_objects),
        (
            ("story_store", story_layers or complete_layers(STORY_RUNTIME_CAPABILITIES)),
            ("product_knowledge_store", knowledge_layers or complete_layers(KNOWLEDGE_RUNTIME_CAPABILITIES)),
            ("product_contract_store", contract_layers or complete_layers(CONTRACT_RUNTIME_CAPABILITIES)),
            ("delivery_workspace", delivery_layers or complete_layers(DELIVERY_RUNTIME_CAPABILITIES)),
        ),
        registry,
        profiles,
        expected_local_container_fingerprint=expected_local_container_fingerprint,
        expected_prior_fingerprints=expected_prior_fingerprints,
        observed_local_fingerprints=observed_local_fingerprints,
        rendered_local_documents=rendered_local_documents,
    )


class DryRunDiagnosticTests(unittest.TestCase):
    def test_desired_structure_requires_logical_owner_and_typed_semantics(self):
        with self.assertRaisesRegex(TypeError, "logical_provider"):
            DesiredStructure(
                "linear",
                "ensure_label",
                "label.product.sample",
                "opaque-fingerprint",
                True,
                False,
            )

    def test_structure_capability_is_scoped_to_its_logical_provider(self):
        capability = "ensure_view"
        value = build_manifest_with(
            desired_structures=(
                typed_structure(
                    ProviderKind.PRODUCT_KNOWLEDGE,
                    "notion",
                    capability,
                    "view.sample",
                    "v1",
                    administrative=True,
                    runtime_required=False,
                    manual_instructions=("Create the Sample product view.",),
                ),
            ),
            knowledge_layers=layers_with(
                KNOWLEDGE_RUNTIME_CAPABILITIES,
                capability,
            ),
            contract_layers=complete_layers(CONTRACT_RUNTIME_CAPABILITIES),
        )

        target = tuple(
            operation
            for operation in value.operations
            if operation.target_key == "view.sample"
        )
        self.assertEqual(tuple(operation.kind for operation in target), (OperationKind.CREATE,))
        self.assertFalse(
            any(diagnostic.capability == capability for diagnostic in value.diagnostics)
        )

    def test_structure_provider_must_match_its_selected_logical_provider(self):
        with self.assertRaisesRegex(
            ValueError,
            "logical provider story.*selected physical provider linear",
        ):
            build_manifest_with(
                desired_structures=(
                    typed_structure(
                        ProviderKind.STORY,
                        "notion",
                        "ensure_label",
                        "label.product.sample",
                        "v1",
                        administrative=True,
                        runtime_required=False,
                    ),
                ),
            )

    def test_exact_existing_structure_is_reused_without_create_capability(self):
        semantics = desired_semantics("v1")
        value = build_manifest_with(
            desired_structures=(
                typed_structure(
                    ProviderKind.PRODUCT_KNOWLEDGE,
                    "notion",
                    "ensure_view",
                    "view.sample",
                    "v1",
                    administrative=True,
                    runtime_required=False,
                    manual_instructions=("Create the Sample product view.",),
                ),
            ),
            external_objects=(
                external_object(
                    "view.sample",
                    semantics_fingerprint(semantics),
                    provider="notion",
                ),
            ),
        )

        target = tuple(
            operation.kind
            for operation in value.operations
            if operation.target_key == "view.sample"
        )
        self.assertEqual(target, (OperationKind.REUSE, OperationKind.VERIFY))
        self.assertFalse(
            any(diagnostic.capability == "ensure_view" for diagnostic in value.diagnostics)
        )

    def test_runtime_gap_is_blocking_and_never_emits_manual_fallback(self):
        capability = "ensure_runtime_binding"
        value = build_manifest_with(
            desired_structures=(
                typed_structure(
                    ProviderKind.STORY,
                    "linear",
                    capability,
                    "runtime.binding",
                    "v1",
                    administrative=True,
                    runtime_required=True,
                    manual_instructions=("Configure the runtime binding.",),
                ),
            ),
        )

        diagnostic = next(
            diagnostic
            for diagnostic in value.diagnostics
            if diagnostic.capability == capability
        )
        self.assertTrue(diagnostic.blocking)
        self.assertFalse(
            any(
                operation.kind is OperationKind.MANUAL
                and operation.target_key == "runtime.binding"
                for operation in value.operations
            )
        )

    def test_administrative_gap_has_one_nonblocking_diagnostic_and_exact_handoff(self):
        capability = "ensure_view"
        value = build_manifest_with(
            desired_structures=(
                typed_structure(
                    ProviderKind.PRODUCT_KNOWLEDGE,
                    "notion",
                    capability,
                    "view.sample",
                    "v1",
                    administrative=True,
                    runtime_required=False,
                    manual_instructions=(
                        "Create view Sample in the Products database.",
                        "Set filter product_key = sample.",
                    ),
                ),
            ),
        )

        diagnostic = next(
            diagnostic
            for diagnostic in value.diagnostics
            if diagnostic.capability == capability
        )
        handoff = next(
            operation
            for operation in value.operations
            if operation.target_key == "view.sample"
        )
        self.assertFalse(diagnostic.blocking)
        self.assertEqual(handoff.kind, OperationKind.MANUAL)
        self.assertEqual(
            handoff.manual_instructions,
            (
                "Create view Sample in the Products database.",
                "Set filter product_key = sample.",
            ),
        )
        self.assertEqual(handoff.semantics, desired_semantics("v1"))

    def test_selected_provider_failure_keeps_logical_and_physical_context_without_git_fallback(self):
        value = build_manifest_with(
            story_layers=CapabilityLayers(
                platform_supported=STORY_RUNTIME_CAPABILITIES,
                exposed=frozenset(),
                permitted=STORY_RUNTIME_CAPABILITIES,
                configured=STORY_RUNTIME_CAPABILITIES,
            ),
        )
        self.assertTrue(value.diagnostics)
        self.assertEqual(
            {diagnostic.code for diagnostic in value.diagnostics},
            {DiagnosticCode.CONNECTOR_CAPABILITY_MISSING},
        )
        self.assertEqual(
            {(diagnostic.logical_provider, diagnostic.physical_provider) for diagnostic in value.diagnostics},
            {(ProviderKind.STORY, "linear")},
        )
        self.assertNotIn("git", tuple(operation.provider for operation in value.operations))

    def test_malformed_or_incomplete_capability_evidence_stops_before_manifest_creation(self):
        layers = (
            ("story_store", complete_layers(STORY_RUNTIME_CAPABILITIES)),
            ("product_knowledge_store", complete_layers(KNOWLEDGE_RUNTIME_CAPABILITIES)),
            ("product_contract_store", complete_layers(CONTRACT_RUNTIME_CAPABILITIES)),
        )
        with self.assertRaisesRegex(ValueError, "capability_layers.*delivery_workspace"):
            build_setup_manifest(
                topology(),
                (("story_store", "linear"), ("product_knowledge_store", "notion"), ("product_contract_store", "notion"), ("delivery_workspace", "git")),
                (), ExternalDiscovery(objects=()), layers, (), (),
                expected_local_container_fingerprint="a" * 64,
            )

    def test_phase_one_provider_selection_rejects_an_unavailable_logical_provider_binding(self):
        with self.assertRaisesRegex(ValueError, "story_store.*linear"):
            build_manifest_with(story_store="notion")

    def test_runtime_preflight_diagnostics_are_blocking_for_every_failure_layer(self):
        cases = (
            ("platform_supported", DiagnosticCode.PLATFORM_UNSUPPORTED),
            ("exposed", DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
            ("permitted", DiagnosticCode.PERMISSION_MISSING),
            ("configured", DiagnosticCode.CONFIGURATION_MISSING),
        )
        for field, code in cases:
            with self.subTest(field=field):
                values = {
                    "platform_supported": STORY_RUNTIME_CAPABILITIES,
                    "exposed": STORY_RUNTIME_CAPABILITIES,
                    "permitted": STORY_RUNTIME_CAPABILITIES,
                    "configured": STORY_RUNTIME_CAPABILITIES,
                }
                values[field] = frozenset()
                value = build_manifest_with(story_layers=CapabilityLayers(**values))
                self.assertEqual({diagnostic.code for diagnostic in value.diagnostics}, {code})
                self.assertTrue(all(diagnostic.blocking for diagnostic in value.diagnostics))

    def test_runtime_required_custom_capability_reports_its_first_missing_layer(self):
        custom_capability = "ensure_runtime_workspace"
        cases = (
            ("platform_supported", DiagnosticCode.PLATFORM_UNSUPPORTED),
            ("exposed", DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
            ("permitted", DiagnosticCode.PERMISSION_MISSING),
            ("configured", DiagnosticCode.CONFIGURATION_MISSING),
        )
        for field, code in cases:
            with self.subTest(field=field):
                values = {
                    "platform_supported": STORY_RUNTIME_CAPABILITIES | {custom_capability},
                    "exposed": STORY_RUNTIME_CAPABILITIES | {custom_capability},
                    "permitted": STORY_RUNTIME_CAPABILITIES | {custom_capability},
                    "configured": STORY_RUNTIME_CAPABILITIES | {custom_capability},
                }
                values[field] = STORY_RUNTIME_CAPABILITIES
                value = build_manifest_with(
                    desired_structures=(typed_structure(
                        ProviderKind.STORY,
                        "linear",
                        custom_capability,
                        "runtime.workspace",
                        "new",
                        administrative=False,
                        runtime_required=True,
                    ),),
                    story_layers=CapabilityLayers(**values),
                )
                self.assertTrue(any(
                    diagnostic.logical_provider is ProviderKind.STORY
                    and diagnostic.physical_provider == "linear"
                    and diagnostic.capability == custom_capability
                    and diagnostic.code is code
                    and diagnostic.blocking
                    for diagnostic in value.diagnostics
                ))
                self.assertFalse(any(operation.target_key == "runtime.workspace" for operation in value.operations))


class DryRunDiffTests(unittest.TestCase):
    def test_matching_structure_is_reused_and_missing_structure_is_created(self):
        value = build_manifest_with(
            desired_structures=(
                typed_structure(
                    ProviderKind.STORY, "linear", "ensure_team", "team.delivery",
                    "same", administrative=True, runtime_required=False,
                ),
                typed_structure(
                    ProviderKind.STORY, "linear", "ensure_label",
                    "label.product.sample", "new", administrative=True,
                    runtime_required=False,
                ),
            ),
            external_objects=(external_object(
                "team.delivery", semantics_fingerprint(desired_semantics("same"))
            ),),
            story_layers=layers_with(STORY_RUNTIME_CAPABILITIES, "ensure_team", "ensure_label"),
        )
        self.assertEqual(
            tuple(operation.kind for operation in value.operations[:2]),
            (OperationKind.REUSE, OperationKind.CREATE),
        )
        self.assertEqual(
            tuple(operation.target_key for operation in value.operations[:2]),
            ("team.delivery", "label.product.sample"),
        )

    def test_semantic_difference_is_a_conflict_not_an_update(self):
        value = build_manifest_with(
            desired_structures=(typed_structure(
                ProviderKind.STORY, "linear", "ensure_team", "team.delivery",
                "desired", administrative=True, runtime_required=False,
            ),),
            external_objects=(external_object("team.delivery", "existing"),),
        )
        self.assertTrue(value.conflicts)
        self.assertNotIn(OperationKind.CREATE, tuple(operation.kind for operation in value.operations))
        self.assertNotIn("update", tuple(operation.kind.value for operation in value.operations))

    def test_semantic_difference_remains_a_conflict_when_administrative_access_is_missing(self):
        value = build_manifest_with(
            desired_structures=(typed_structure(
                ProviderKind.STORY, "linear", "ensure_team", "team.delivery",
                "desired", administrative=True, runtime_required=False,
            ),),
            external_objects=(external_object("team.delivery", "existing"),),
            story_layers=CapabilityLayers(
                platform_supported=frozenset(),
                exposed=STORY_RUNTIME_CAPABILITIES,
                permitted=STORY_RUNTIME_CAPABILITIES,
                configured=STORY_RUNTIME_CAPABILITIES,
            ),
        )
        self.assertEqual(tuple(conflict.key for conflict in value.conflicts), ("setup_structure.team.delivery",))
        self.assertFalse(any(operation.target_key == "team.delivery" for operation in value.operations))

    def test_duplicate_external_stable_keys_are_conflicts_not_writes(self):
        value = build_manifest_with(
            desired_structures=(typed_structure(
                ProviderKind.STORY, "linear", "ensure_team", "team.delivery",
                "same", administrative=True, runtime_required=False,
            ),),
            external_objects=(
                external_object(
                    "team.delivery", semantics_fingerprint(desired_semantics("same"))
                ),
                replace(
                    external_object(
                        "team.delivery", semantics_fingerprint(desired_semantics("same"))
                    ),
                    external_id="second",
                ),
            ),
        )
        self.assertEqual(tuple(conflict.key for conflict in value.conflicts), ("setup_structure.team.delivery",))
        self.assertFalse(any(operation.target_key == "team.delivery" for operation in value.operations))

    def test_duplicate_desired_stable_keys_are_conflicts_not_writes(self):
        value = build_manifest_with(
            desired_structures=(
                typed_structure(
                    ProviderKind.STORY, "linear", "ensure_team", "team.delivery",
                    "same", administrative=True, runtime_required=False,
                ),
                typed_structure(
                    ProviderKind.STORY, "linear", "ensure_label", "team.delivery",
                    "same", administrative=True, runtime_required=False,
                ),
            ),
        )
        self.assertEqual(tuple(conflict.key for conflict in value.conflicts), ("setup_structure.team.delivery",))
        self.assertFalse(any(operation.target_key == "team.delivery" for operation in value.operations))

    def test_administrative_platform_gap_is_a_manual_read_back_handoff(self):
        value = build_manifest_with(
            desired_structures=(typed_structure(
                ProviderKind.PRODUCT_KNOWLEDGE,
                "notion",
                "ensure_view",
                "view.sample",
                "new",
                administrative=True,
                runtime_required=False,
                manual_instructions=("Create the approved Sample view.",),
            ),),
            knowledge_layers=CapabilityLayers(
                platform_supported=frozenset(),
                exposed=KNOWLEDGE_RUNTIME_CAPABILITIES,
                permitted=KNOWLEDGE_RUNTIME_CAPABILITIES,
                configured=KNOWLEDGE_RUNTIME_CAPABILITIES,
            ),
        )
        operation = next(operation for operation in value.operations if operation.target_key == "view.sample")
        self.assertEqual(operation.kind, OperationKind.MANUAL)
        self.assertEqual(dict(operation.payload)["diagnostic_code"], DiagnosticCode.PLATFORM_UNSUPPORTED.value)
        self.assertTrue(dict(operation.payload)["read_back_required"])

    def test_administrative_custom_capability_gap_uses_manual_precedence(self):
        custom_capability = "ensure_view"
        cases = (
            ("platform_supported", DiagnosticCode.PLATFORM_UNSUPPORTED),
            ("exposed", DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
            ("permitted", DiagnosticCode.PERMISSION_MISSING),
        )
        for field, code in cases:
            with self.subTest(field=field):
                values = {
                    "platform_supported": KNOWLEDGE_RUNTIME_CAPABILITIES | {custom_capability},
                    "exposed": KNOWLEDGE_RUNTIME_CAPABILITIES | {custom_capability},
                    "permitted": KNOWLEDGE_RUNTIME_CAPABILITIES | {custom_capability},
                    "configured": KNOWLEDGE_RUNTIME_CAPABILITIES | {custom_capability},
                }
                values[field] = KNOWLEDGE_RUNTIME_CAPABILITIES
                value = build_manifest_with(
                    desired_structures=(typed_structure(
                        ProviderKind.PRODUCT_KNOWLEDGE,
                        "notion",
                        custom_capability,
                        "view.sample",
                        "new",
                        administrative=True,
                        runtime_required=False,
                        manual_instructions=("Create the approved Sample view.",),
                    ),),
                    knowledge_layers=CapabilityLayers(**values),
                    contract_layers=layers_with(CONTRACT_RUNTIME_CAPABILITIES, custom_capability),
                )
                operation = next(operation for operation in value.operations if operation.target_key == "view.sample")
                self.assertEqual(operation.kind, OperationKind.MANUAL)
                self.assertEqual(dict(operation.payload)["diagnostic_code"], code.value)
                self.assertTrue(dict(operation.payload)["read_back_required"])

    def test_administrative_configuration_absence_is_provisioned_by_create(self):
        custom_capability = "ensure_view"
        value = build_manifest_with(
            desired_structures=(typed_structure(
                ProviderKind.PRODUCT_KNOWLEDGE,
                "notion",
                custom_capability,
                "view.sample",
                "new",
                administrative=True,
                runtime_required=False,
                manual_instructions=("Create the approved Sample view.",),
            ),),
            knowledge_layers=CapabilityLayers(
                platform_supported=KNOWLEDGE_RUNTIME_CAPABILITIES | {custom_capability},
                exposed=KNOWLEDGE_RUNTIME_CAPABILITIES | {custom_capability},
                permitted=KNOWLEDGE_RUNTIME_CAPABILITIES | {custom_capability},
                configured=KNOWLEDGE_RUNTIME_CAPABILITIES,
            ),
            contract_layers=CapabilityLayers(
                platform_supported=CONTRACT_RUNTIME_CAPABILITIES | {custom_capability},
                exposed=CONTRACT_RUNTIME_CAPABILITIES | {custom_capability},
                permitted=CONTRACT_RUNTIME_CAPABILITIES | {custom_capability},
                configured=CONTRACT_RUNTIME_CAPABILITIES,
            ),
        )
        operation = next(operation for operation in value.operations if operation.target_key == "view.sample")
        self.assertEqual(operation.kind, OperationKind.CREATE)

    def test_missing_runtime_configuration_emits_a_blocking_diagnostic_without_create(self):
        value = build_manifest_with(
            desired_structures=(typed_structure(
                ProviderKind.STORY, "linear", "create_story", "story.sample",
                "new", administrative=False, runtime_required=True,
            ),),
            story_layers=CapabilityLayers(
                platform_supported=STORY_RUNTIME_CAPABILITIES,
                exposed=STORY_RUNTIME_CAPABILITIES,
                permitted=STORY_RUNTIME_CAPABILITIES,
                configured=STORY_RUNTIME_CAPABILITIES - {"create_story"},
            ),
        )
        self.assertTrue(any(
            diagnostic.capability == "create_story"
            and diagnostic.code is DiagnosticCode.CONFIGURATION_MISSING
            and diagnostic.blocking
            for diagnostic in value.diagnostics
        ))
        self.assertFalse(any(operation.target_key == "story.sample" for operation in value.operations))

    def test_administrative_structure_can_be_runtime_required(self):
        value = build_manifest_with(
            desired_structures=(typed_structure(
                ProviderKind.STORY, "linear", "create_story", "story.sample",
                "new", administrative=True, runtime_required=True,
            ),),
        )
        operation = next(operation for operation in value.operations if operation.target_key == "story.sample")
        self.assertEqual(operation.kind, OperationKind.CREATE)
        self.assertTrue(operation.runtime_required)


class DryRunFixtureTests(unittest.TestCase):
    def test_default_local_documents_are_canonical_apply_ready_strings(self):
        registry, profiles, documents = canonical_git_inputs()
        canonical_topology = replace(topology(), repository_id="repo-sample")

        value = build_setup_manifest(
            canonical_topology,
            tuple(
                (logical, "git")
                for logical in (
                    "story_store",
                    "product_knowledge_store",
                    "product_contract_store",
                    "delivery_workspace",
                )
            ),
            (),
            ExternalDiscovery(objects=()),
            (
                ("story_store", complete_layers(STORY_RUNTIME_CAPABILITIES)),
                (
                    "product_knowledge_store",
                    complete_layers(KNOWLEDGE_RUNTIME_CAPABILITIES),
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
            registry,
            profiles,
            expected_local_container_fingerprint="a" * 64,
        )

        local_payloads = {
            operation.target_key: dict(operation.payload)["document"]
            for operation in value.operations
            if operation.kind is OperationKind.WRITE_LOCAL
        }
        self.assertEqual(local_payloads, documents)
        self.assertTrue(all(isinstance(body, str) for body in local_payloads.values()))

    def test_local_documents_must_match_the_confirmed_topology_projection(self):
        registry, profiles, documents = canonical_git_inputs()
        canonical_topology = replace(topology(), repository_id="repo-sample")
        changed_documents = dict(documents)
        changed_workspace = json.loads(
            changed_documents[".agents/elephant/workspace.yaml"]
        )
        changed_workspace["repository"]["id"] = "repo-other"
        changed_documents[".agents/elephant/workspace.yaml"] = (
            json.dumps(
                changed_workspace,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                separators=(",", ": "),
            )
            + "\n"
        )
        common = (
            tuple(
                (logical, "git")
                for logical in (
                    "story_store",
                    "product_knowledge_store",
                    "product_contract_store",
                    "delivery_workspace",
                )
            ),
            (),
            ExternalDiscovery(objects=()),
            (
                ("story_store", complete_layers(STORY_RUNTIME_CAPABILITIES)),
                (
                    "product_knowledge_store",
                    complete_layers(KNOWLEDGE_RUNTIME_CAPABILITIES),
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
        )

        with self.assertRaisesRegex(ValueError, "canonical local document"):
            build_setup_manifest(
                canonical_topology,
                *common,
                registry,
                profiles,
                expected_local_container_fingerprint="a" * 64,
                rendered_local_documents=tuple(sorted(changed_documents.items())),
            )

        changed_registry = freeze_canonical_document(changed_workspace)
        with self.assertRaisesRegex(ValueError, "repository.*topology"):
            build_setup_manifest(
                canonical_topology,
                *common,
                changed_registry,
                profiles,
                expected_local_container_fingerprint="a" * 64,
                rendered_local_documents=tuple(sorted(changed_documents.items())),
            )

    def test_owner_conflict_resolution_is_bound_into_manifest_fingerprint(self):
        first_resolution = ConflictResolution(
            "product.sample",
            "Sample (product-1)",
            "Owner selected the existing product authority.",
        )
        repository_evidence = (
            Evidence("owner", "repository.id", "fixture-single"),
        )
        product_evidence = (
            Candidate(
                "sample",
                "Sample",
                (Evidence("repository_document", "docs/products/sample.md", "Sample"),),
                Confidence.MEDIUM,
            ),
        )
        first = build_manifest_with(
            topology_value=replace(
                topology(),
                repository_evidence=repository_evidence,
                product_evidence=product_evidence,
                conflict_resolutions=(first_resolution,),
            ),
        )
        second_resolution = replace(
            first_resolution,
            rationale="Owner selected the same authority after explicit review.",
        )
        second = replace(first, conflict_resolutions=(second_resolution,))

        self.assertEqual(first.conflict_resolutions, (first_resolution,))
        self.assertEqual(first.repository_evidence, repository_evidence)
        self.assertEqual(first.product_evidence, product_evidence)
        self.assertNotEqual(manifest_fingerprint(first), manifest_fingerprint(second))
        self.assertNotEqual(
            manifest_fingerprint(first),
            manifest_fingerprint(
                replace(
                    first,
                    repository_evidence=(
                        Evidence("owner", "repository.id", "different-answer"),
                    ),
                )
            ),
        )

    def test_local_slot_is_bound_to_the_classified_stable_key_operation(self):
        source = typed_structure(
            ProviderKind.STORY,
            "linear",
            "ensure_workspace",
            "binding.linear.workspace",
            "v1",
            administrative=True,
            runtime_required=False,
            manual_instructions=("Create the approved Linear workspace.",),
        )
        slot = LocalDocumentSlot(
            "linear.workspace_id",
            "linear",
            source.logical_key,
        )
        documents = build_documents()
        workspace = documents[".agents/elephant/workspace.yaml"].replace(
            '"repo-sample"',
            '"fixture-single"',
        ).replace(
            '"linear-workspace"',
            f'"{slot.placeholder}"',
        )
        approved_bodies = {
            ".agents/elephant/workspace.yaml": workspace,
            ".agents/elephant/profiles/sample.yaml": documents[
                ".agents/elephant/profiles/sample.yaml"
            ],
            ".agents/elephant/profiles/engineering.yaml": documents[
                ".agents/elephant/profiles/engineering.yaml"
            ],
        }
        approved_values = {
            path: json.loads(body) for path, body in approved_bodies.items()
        }
        value = build_manifest_with(
            desired_structures=(source,),
            story_layers=layers_with(
                STORY_RUNTIME_CAPABILITIES,
                "ensure_workspace",
            ),
            registry=freeze_canonical_document(
                approved_values[".agents/elephant/workspace.yaml"]
            ),
            profiles=tuple(
                (Path(path).stem, freeze_canonical_document(document))
                for path, document in sorted(approved_values.items())
                if path != ".agents/elephant/workspace.yaml"
            ),
            rendered_local_documents=(
                (
                    ".agents/elephant/workspace.yaml",
                    LocalDocumentTemplate(workspace, (slot,)),
                ),
                (
                    ".agents/elephant/profiles/sample.yaml",
                    documents[".agents/elephant/profiles/sample.yaml"],
                ),
                (
                    ".agents/elephant/profiles/engineering.yaml",
                    documents[".agents/elephant/profiles/engineering.yaml"],
                ),
            ),
        )

        source_operation = next(
            operation
            for operation in value.operations
            if operation.target_key == source.logical_key
        )
        local = next(
            operation
            for operation in value.operations
            if operation.target_key == ".agents/elephant/workspace.yaml"
        )
        self.assertEqual(local.local_slots[0].source_operation_id, source_operation.operation_id)
        self.assertEqual(local.local_slots[0].stable_key, source.logical_key)

    def test_local_container_cas_authority_is_exact_and_approved(self):
        value = build_manifest_with(expected_local_container_fingerprint="b" * 64)

        self.assertEqual(value.expected_local_container_fingerprint, "b" * 64)
        self.assertNotEqual(value, build_manifest_with())

    def test_local_expected_prior_fingerprints_are_carried_by_exact_operations(self):
        prior = "a" * 64

        value = build_manifest_with(
            expected_prior_fingerprints=((".agents/elephant/workspace.yaml", prior),)
        )
        local = {
            operation.target_key: operation
            for operation in value.operations
            if operation.kind is OperationKind.WRITE_LOCAL
        }

        self.assertEqual(
            local[".agents/elephant/workspace.yaml"].expected_prior_fingerprint,
            prior,
        )
        self.assertIsNone(
            local[".agents/elephant/profiles/sample.yaml"].expected_prior_fingerprint
        )
        with self.assertRaisesRegex(ValueError, "expected prior fingerprint.*unknown"):
            build_manifest_with(
                expected_prior_fingerprints=(("README.md", "b" * 64),)
            )

    def test_rendered_local_documents_are_the_exact_approved_write_payloads(self):
        documents = build_documents()
        workspace_body = documents[".agents/elephant/workspace.yaml"].replace(
            '"repo-sample"',
            '"fixture-single"',
        )
        profile_body = documents[".agents/elephant/profiles/sample.yaml"]
        engineering_body = documents[
            ".agents/elephant/profiles/engineering.yaml"
        ]
        approved_values = {
            ".agents/elephant/workspace.yaml": json.loads(workspace_body),
            ".agents/elephant/profiles/sample.yaml": json.loads(profile_body),
            ".agents/elephant/profiles/engineering.yaml": json.loads(
                engineering_body
            ),
        }

        value = build_manifest_with(
            registry=freeze_canonical_document(
                approved_values[".agents/elephant/workspace.yaml"]
            ),
            profiles=tuple(
                (Path(path).stem, freeze_canonical_document(document))
                for path, document in sorted(approved_values.items())
                if path != ".agents/elephant/workspace.yaml"
            ),
            rendered_local_documents=(
                (".agents/elephant/workspace.yaml", workspace_body),
                (".agents/elephant/profiles/sample.yaml", profile_body),
                (
                    ".agents/elephant/profiles/engineering.yaml",
                    engineering_body,
                ),
            )
        )
        local = {
            operation.target_key: dict(operation.payload)["document"]
            for operation in value.operations
            if operation.kind is OperationKind.WRITE_LOCAL
        }

        self.assertEqual(
            local,
            {
                ".agents/elephant/workspace.yaml": workspace_body,
                ".agents/elephant/profiles/sample.yaml": profile_body,
                ".agents/elephant/profiles/engineering.yaml": engineering_body,
            },
        )

    def test_partial_existing_workspace_fixture_reuses_known_structure_and_creates_omission(self):
        records = json.loads((FIXTURES / "existing-workspace.json").read_text(encoding="utf-8"))
        discovered = normalize_external_discovery(tuple(records)).objects
        value = build_manifest_with(
            desired_structures=(
                typed_structure(
                    ProviderKind.STORY, "linear", "ensure_team", "team.delivery",
                    "team-v1", administrative=True, runtime_required=False,
                ),
                typed_structure(
                    ProviderKind.STORY, "linear", "ensure_label",
                    "label.product.sample", "label-v1", administrative=True,
                    runtime_required=False,
                ),
            ),
            external_objects=tuple(
                replace(
                    item,
                    fingerprint=semantics_fingerprint(desired_semantics("team-v1")),
                )
                if item.key == "team.delivery"
                else item
                for item in discovered
            ),
            story_layers=layers_with(STORY_RUNTIME_CAPABILITIES, "ensure_team", "ensure_label"),
        )
        self.assertEqual(
            tuple((operation.kind, operation.target_key) for operation in value.operations[:2]),
            ((OperationKind.REUSE, "team.delivery"), (OperationKind.CREATE, "label.product.sample")),
        )

    def test_confirmed_multi_product_topology_is_preserved_without_deriving_products_from_code_units(self):
        multi = ConfirmedTopology(
            repository_id="fixture-multi",
            products=(
                ConfirmedProduct("commerce", "Commerce", ("alpha",)),
                ConfirmedProduct("identity", "Identity", ("beta",)),
            ),
            domains=(
                ConfirmedDomain("alpha", "Alpha", ("commerce",), ("apps/alpha",), (), ()),
                ConfirmedDomain("beta", "Beta", ("identity",), ("apps/beta",), (), ()),
            ),
        )
        value = build_manifest_with(
            topology_value=multi,
            story_store="git",
            product_knowledge_store="git",
            product_contract_store="git",
            delivery_workspace="git",
        )
        self.assertEqual(tuple(product.key for product in value.products), ("commerce", "identity"))
        self.assertEqual(tuple(domain.key for domain in value.domains), ("alpha", "beta"))

    def test_rerun_with_identical_inputs_is_deterministic_and_has_no_creates_or_deletes(self):
        desired = (typed_structure(
            ProviderKind.STORY, "linear", "ensure_team", "team.delivery",
            "same", administrative=True, runtime_required=False,
        ),)
        first = build_manifest_with(
            desired_structures=desired,
            external_objects=(external_object(
                "team.delivery", semantics_fingerprint(desired_semantics("same"))
            ),),
            story_layers=layers_with(STORY_RUNTIME_CAPABILITIES, "ensure_team"),
        )
        second = build_manifest_with(
            desired_structures=tuple(reversed(desired)),
            external_objects=(external_object(
                "team.delivery", semantics_fingerprint(desired_semantics("same"))
            ),),
            story_layers=layers_with(STORY_RUNTIME_CAPABILITIES, "ensure_team"),
        )
        self.assertEqual(manifest_fingerprint(first), manifest_fingerprint(second))
        self.assertNotIn(OperationKind.CREATE, tuple(operation.kind for operation in first.operations))
        self.assertNotIn("delete", tuple(operation.kind.value for operation in first.operations))

    def test_operations_are_phase_sorted_and_local_writes_are_last(self):
        value = build_manifest_with(
            desired_structures=(
                typed_structure(
                    ProviderKind.STORY, "linear", "ensure_team", "team.delivery",
                    "same", administrative=True, runtime_required=False,
                ),
                typed_structure(
                    ProviderKind.STORY, "linear", "ensure_label",
                    "label.product.sample", "new", administrative=True,
                    runtime_required=False,
                ),
            ),
            external_objects=(external_object(
                "team.delivery", semantics_fingerprint(desired_semantics("same"))
            ),),
            story_layers=layers_with(STORY_RUNTIME_CAPABILITIES, "ensure_team", "ensure_label"),
        )
        phase = {kind: index for index, kind in enumerate(OperationKind)}
        self.assertEqual(tuple(phase[operation.kind] for operation in value.operations), tuple(sorted(phase[operation.kind] for operation in value.operations)))
        self.assertTrue(all(operation.kind is OperationKind.WRITE_LOCAL for operation in value.operations[-2:]))

    def test_setup_structure_discovery_requires_a_fingerprint_but_other_discovery_remains_compatible(self):
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            ExternalObject("linear", "setup_structure", "team.delivery", "Team", "id-team")
        self.assertEqual(
            ExternalObject("linear", "product", "sample", "Sample", "id-product").fingerprint,
            "",
        )

    def test_public_operation_vocabulary_has_no_delete(self):
        self.assertNotIn("delete", tuple(kind.value for kind in OperationKind))


if __name__ == "__main__":
    unittest.main()

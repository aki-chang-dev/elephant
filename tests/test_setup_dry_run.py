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
    CapabilityLayers,
    ConfirmedDomain,
    ConfirmedProduct,
    ConfirmedTopology,
    DesiredStructure,
    ExternalDiscovery,
    ExternalObject,
    OperationKind,
    build_setup_manifest,
    manifest_fingerprint,
    normalize_external_discovery,
)


FIXTURES = Path(__file__).parent / "fixtures" / "setup-workspace"


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


def build_manifest_with(
    *,
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
    registry=(("schema", "elephant.workspace/v3"),),
    profiles=(("sample", (("schema", "elephant.profile/v3"), ("kind", "product"))),),
    expected_prior_fingerprints=(),
    rendered_local_documents=(),
):
    return build_setup_manifest(
        topology(),
        (
            ("story_store", story_store),
            ("product_knowledge_store", product_knowledge_store),
            ("product_contract_store", product_contract_store),
            ("delivery_workspace", delivery_workspace),
        ),
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
        expected_prior_fingerprints=expected_prior_fingerprints,
        rendered_local_documents=rendered_local_documents,
    )


class DryRunDiagnosticTests(unittest.TestCase):
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
                    desired_structures=(DesiredStructure("linear", custom_capability, "runtime.workspace", "new", False, True),),
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
                DesiredStructure("linear", "ensure_team", "team.delivery", "same", True, False),
                DesiredStructure("linear", "ensure_label", "label.product.sample", "new", True, False),
            ),
            external_objects=(external_object("team.delivery", "same"),),
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
            desired_structures=(DesiredStructure("linear", "ensure_team", "team.delivery", "desired", True, False),),
            external_objects=(external_object("team.delivery", "existing"),),
        )
        self.assertTrue(value.conflicts)
        self.assertNotIn(OperationKind.CREATE, tuple(operation.kind for operation in value.operations))
        self.assertNotIn("update", tuple(operation.kind.value for operation in value.operations))

    def test_semantic_difference_remains_a_conflict_when_administrative_access_is_missing(self):
        value = build_manifest_with(
            desired_structures=(DesiredStructure("linear", "ensure_team", "team.delivery", "desired", True, False),),
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
            desired_structures=(DesiredStructure("linear", "ensure_team", "team.delivery", "same", True, False),),
            external_objects=(
                external_object("team.delivery", "same"),
                replace(external_object("team.delivery", "same"), external_id="second"),
            ),
        )
        self.assertEqual(tuple(conflict.key for conflict in value.conflicts), ("setup_structure.team.delivery",))
        self.assertFalse(any(operation.target_key == "team.delivery" for operation in value.operations))

    def test_duplicate_desired_stable_keys_are_conflicts_not_writes(self):
        value = build_manifest_with(
            desired_structures=(
                DesiredStructure("linear", "ensure_team", "team.delivery", "same", True, False),
                DesiredStructure("linear", "ensure_label", "team.delivery", "same", True, False),
            ),
        )
        self.assertEqual(tuple(conflict.key for conflict in value.conflicts), ("setup_structure.team.delivery",))
        self.assertFalse(any(operation.target_key == "team.delivery" for operation in value.operations))

    def test_administrative_platform_gap_is_a_manual_read_back_handoff(self):
        value = build_manifest_with(
            desired_structures=(DesiredStructure("notion", "ensure_view", "view.sample", "new", True, False),),
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
                    desired_structures=(DesiredStructure("notion", custom_capability, "view.sample", "new", True, False),),
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
            desired_structures=(DesiredStructure("notion", custom_capability, "view.sample", "new", True, False),),
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
            desired_structures=(DesiredStructure("linear", "create_story", "story.sample", "new", False, True),),
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
            desired_structures=(DesiredStructure("linear", "create_story", "story.sample", "new", True, True),),
        )
        operation = next(operation for operation in value.operations if operation.target_key == "story.sample")
        self.assertEqual(operation.kind, OperationKind.CREATE)
        self.assertTrue(operation.runtime_required)


class DryRunFixtureTests(unittest.TestCase):
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
        workspace_body = '{"schema":"elephant.workspace/v3"}\n'
        profile_body = '{"schema":"elephant.profile/v3"}\n'

        value = build_manifest_with(
            rendered_local_documents=(
                (".agents/elephant/workspace.yaml", workspace_body),
                (".agents/elephant/profiles/sample.yaml", profile_body),
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
            },
        )

    def test_partial_existing_workspace_fixture_reuses_known_structure_and_creates_omission(self):
        records = json.loads((FIXTURES / "existing-workspace.json").read_text(encoding="utf-8"))
        value = build_manifest_with(
            desired_structures=(
                DesiredStructure("linear", "ensure_team", "team.delivery", "team-v1", True, False),
                DesiredStructure("linear", "ensure_label", "label.product.sample", "label-v1", True, False),
            ),
            external_objects=normalize_external_discovery(tuple(records)).objects,
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
        value = build_setup_manifest(
            multi,
            (("story_store", "linear"), ("product_knowledge_store", "notion"), ("product_contract_store", "notion"), ("delivery_workspace", "git")),
            (), ExternalDiscovery(objects=()),
            (("story_store", complete_layers(STORY_RUNTIME_CAPABILITIES)), ("product_knowledge_store", complete_layers(KNOWLEDGE_RUNTIME_CAPABILITIES)), ("product_contract_store", complete_layers(CONTRACT_RUNTIME_CAPABILITIES)), ("delivery_workspace", complete_layers(DELIVERY_RUNTIME_CAPABILITIES))),
            (("schema", "elephant.workspace/v3"),), (),
        )
        self.assertEqual(tuple(product.key for product in value.products), ("commerce", "identity"))
        self.assertEqual(tuple(domain.key for domain in value.domains), ("alpha", "beta"))

    def test_rerun_with_identical_inputs_is_deterministic_and_has_no_creates_or_deletes(self):
        desired = (DesiredStructure("linear", "ensure_team", "team.delivery", "same", True, False),)
        first = build_manifest_with(
            desired_structures=desired,
            external_objects=(external_object("team.delivery", "same"),),
            story_layers=layers_with(STORY_RUNTIME_CAPABILITIES, "ensure_team"),
        )
        second = build_manifest_with(
            desired_structures=tuple(reversed(desired)),
            external_objects=(external_object("team.delivery", "same"),),
            story_layers=layers_with(STORY_RUNTIME_CAPABILITIES, "ensure_team"),
        )
        self.assertEqual(manifest_fingerprint(first), manifest_fingerprint(second))
        self.assertNotIn(OperationKind.CREATE, tuple(operation.kind for operation in first.operations))
        self.assertNotIn("delete", tuple(operation.kind.value for operation in first.operations))

    def test_operations_are_phase_sorted_and_local_writes_are_last(self):
        value = build_manifest_with(
            desired_structures=(
                DesiredStructure("linear", "ensure_team", "team.delivery", "same", True, False),
                DesiredStructure("linear", "ensure_label", "label.product.sample", "new", True, False),
            ),
            external_objects=(external_object("team.delivery", "same"),),
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

from dataclasses import FrozenInstanceError, dataclass, replace
from enum import Enum
import unittest

import scripts.workspace_setup as workspace_setup
from scripts.workspace_core import DiagnosticCode, ProviderKind
from scripts.workspace_setup import (
    ApplyEvidence,
    ApplyResult,
    ApprovedManifest,
    Candidate,
    Confidence,
    ConfirmedDomain,
    ConfirmedProduct,
    ConfirmedTopology,
    Evidence,
    OperationKind,
    OwnerQuestion,
    SetupDiagnostic,
    SetupManifest,
    SetupOperation,
    TopologyConflict,
    approve_manifest,
    manifest_fingerprint,
)
from scripts.workspace_setup.models import SETUP_MANIFEST_SCHEMA


@dataclass
class MutableValue:
    value: str


def manifest() -> SetupManifest:
    return SetupManifest(
        schema=SETUP_MANIFEST_SCHEMA,
        repository_id="repo-sample",
        provider_selection=(
            ("delivery_workspace", "git"),
            ("product_contract_store", "git"),
            ("product_knowledge_store", "git"),
            ("story_store", "git"),
        ),
        products=(
            ConfirmedProduct(
                key="sample",
                display_name="Sample",
                domain_keys=("web",),
            ),
        ),
        domains=(
            ConfirmedDomain(
                key="web",
                display_name="Web",
                product_keys=("sample",),
                scopes=("apps/web",),
                instruction_paths=("AGENTS.md",),
                verification=("bun run type-check",),
            ),
        ),
        operations=(
            SetupOperation(
                operation_id="story.sample.create",
                provider="linear",
                capability="create_story",
                target_key="story.sample",
                desired_fingerprint="desired",
                payload=(("name", "Sample"),),
                kind=OperationKind.CREATE,
                runtime_required=True,
            ),
        ),
        diagnostics=(
            SetupDiagnostic(
                logical_provider=ProviderKind.STORY,
                physical_provider="linear",
                capability="create_story",
                code=DiagnosticCode.PERMISSION_MISSING,
                blocking=True,
            ),
        ),
        conflicts=(
            TopologyConflict(
                key="product.sample",
                subject="product",
                alternatives=("Sample", "Example"),
                evidence=(Evidence("linear", "label-sample", "Sample"),),
            ),
        ),
        questions=(
            OwnerQuestion(
                key="product.sample.confirm",
                prompt="Confirm sample as a product identity",
                evidence=(Evidence("docs", "docs/sample", "sample"),),
                confidence=Confidence.MEDIUM,
            ),
        ),
        expected_local_container_fingerprint="a" * 64,
        registry=(("schema", "elephant.workspace/v3"),),
        profiles=(("sample", (("kind", "product"),)),),
    )


class SetupManifestTests(unittest.TestCase):
    def test_fingerprint_is_stable_for_equivalent_mapping_order(self):
        first = manifest()
        second = replace(
            first,
            provider_selection=tuple(reversed(first.provider_selection)),
            registry=tuple(reversed(first.registry)),
        )
        self.assertEqual(manifest_fingerprint(first), manifest_fingerprint(second))

    def test_every_semantic_manifest_component_changes_fingerprint(self):
        first = manifest()
        candidates = {
            "product": replace(first, products=()),
            "domain": replace(first, domains=()),
            "provider": replace(first, provider_selection=(("story_store", "linear"),)),
            "operation": replace(first, operations=()),
            "question": replace(first, questions=()),
            "conflict": replace(first, conflicts=()),
            "diagnostic": replace(first, diagnostics=()),
            "local container": replace(
                first, expected_local_container_fingerprint="b" * 64
            ),
            "registry": replace(first, registry=(("schema", "elephant.workspace/v4"),)),
            "profile": replace(first, profiles=(("sample", (("kind", "engineering"),)),)),
        }
        fingerprint = manifest_fingerprint(first)
        for name, changed in candidates.items():
            with self.subTest(name=name):
                self.assertNotEqual(manifest_fingerprint(changed), fingerprint)

    def test_local_expected_prior_fingerprint_is_approved_manifest_authority(self):
        value = manifest()
        local = SetupOperation(
            operation_id="local.workspace.replace",
            provider="local",
            capability="write_registry",
            target_key=".agents/elephant/workspace.yaml",
            desired_fingerprint="desired",
            payload=(("document", (("schema", "elephant.workspace/v3"),)),),
            kind=OperationKind.WRITE_LOCAL,
            runtime_required=False,
        )
        without_prior = replace(value, operations=(local,))
        with_prior = replace(
            value,
            operations=(replace(local, expected_prior_fingerprint="a" * 64),),
        )

        self.assertIsNone(local.expected_prior_fingerprint)
        self.assertNotEqual(
            manifest_fingerprint(without_prior), manifest_fingerprint(with_prior)
        )

    def test_expected_prior_fingerprint_is_valid_only_for_local_writes(self):
        with self.assertRaisesRegex(ValueError, "expected_prior_fingerprint"):
            replace(
                manifest().operations[0],
                expected_prior_fingerprint="a" * 64,
            )
        local = replace(
            manifest().operations[0],
            kind=OperationKind.WRITE_LOCAL,
            provider="local",
        )
        with self.assertRaisesRegex(ValueError, "expected_prior_fingerprint"):
            replace(local, expected_prior_fingerprint="not-a-sha256")

        bypassed = manifest().operations[0]
        object.__setattr__(bypassed, "expected_prior_fingerprint", "a" * 64)
        with self.assertRaisesRegex(ValueError, "expected_prior_fingerprint"):
            manifest_fingerprint(replace(manifest(), operations=(bypassed,)))

    def test_local_container_fingerprint_requires_approved_lowercase_sha256(self):
        for invalid in ("", "A" * 64, "not-a-sha256", None):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(
                    (TypeError, ValueError), "expected_local_container_fingerprint"
                ):
                    replace(
                        manifest(),
                        expected_local_container_fingerprint=invalid,
                    )

    def test_unsupported_values_are_rejected(self):
        with self.assertRaisesRegex(TypeError, "immutable value: unsupported object"):
            value = replace(
                manifest(),
                operations=(
                    replace(manifest().operations[0], payload=(("invalid", object()),)),
                ),
            )
            manifest_fingerprint(value)

    def test_rejects_unknown_schema_and_non_enum_vocabulary_before_fingerprinting(self):
        first = manifest()
        cases = {
            "schema": lambda: replace(first, schema="elephant.setup-manifest/v2"),
            "operation kind": lambda: replace(
                first, operations=(replace(first.operations[0], kind="delete"),)
            ),
            "diagnostic provider": lambda: replace(
                first, diagnostics=(replace(first.diagnostics[0], logical_provider="story"),)
            ),
            "diagnostic code": lambda: replace(
                first, diagnostics=(replace(first.diagnostics[0], code="permission_missing"),)
            ),
            "question confidence": lambda: replace(
                first, questions=(replace(first.questions[0], confidence="medium"),)
            ),
        }
        for name, build_changed in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex((TypeError, ValueError), "schema|expected"):
                    manifest_fingerprint(build_changed())

    def test_mapping_fields_reject_arrays_and_non_string_keys(self):
        first = manifest()
        cases = {
            "provider selection array": lambda: replace(first, provider_selection=("story_store",)),
            "registry non-string key": lambda: replace(first, registry=((1, "value"),)),
            "profile array": lambda: replace(first, profiles=("sample",)),
            "operation payload non-string key": lambda: replace(
                first, operations=(replace(first.operations[0], payload=((1, "Sample"),)),)
            ),
        }
        for name, build_changed in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(TypeError, "tuple key/value pairs"):
                    manifest_fingerprint(build_changed())

    def test_recursively_rejects_mutable_nested_values_before_approval(self):
        first = manifest()
        cases = {
            "mutable dataclass": lambda: replace(
                first, registry=(("mutable", MutableValue("before")),)
            ),
            "nested list": lambda: replace(
                first, profiles=(("sample", (("items", ["mutable"]),)),)),
        }
        for name, build_changed in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(TypeError, "immutable"):
                    changed = build_changed()
                    supplied = manifest_fingerprint(changed)
                    approve_manifest(changed, supplied)


class SetupApprovalTests(unittest.TestCase):
    def test_only_exact_manifest_fingerprint_can_be_approved(self):
        value = manifest()
        approved = approve_manifest(value, manifest_fingerprint(value))
        self.assertEqual(approved.fingerprint, manifest_fingerprint(value))
        self.assertIs(approved.manifest, value)

    def test_stale_or_blank_fingerprint_is_rejected(self):
        value = manifest()
        for supplied in ("", "0" * 64):
            with self.subTest(supplied=supplied):
                with self.assertRaisesRegex(ValueError, "approval fingerprint"):
                    approve_manifest(value, supplied)


class SetupValueContractTests(unittest.TestCase):
    def test_serialized_vocabulary_is_exact(self):
        self.assertEqual(SETUP_MANIFEST_SCHEMA, "elephant.setup-manifest/v1")
        self.assertEqual(
            tuple(value.value for value in Confidence),
            ("confirmed", "high", "medium", "low"),
        )
        self.assertEqual(
            tuple(value.value for value in OperationKind),
            ("reuse", "create", "manual", "verify", "round_trip", "write_local"),
        )

    def test_public_exports_match_completed_setup_interfaces(self):
        self.assertEqual(
            frozenset(workspace_setup.__all__),
            {
                "ApplyEvidence",
                "ApplyResult",
                "ApprovedManifest",
                "CapabilityLayers",
                "Candidate",
                "Confidence",
                "ConfirmedDomain",
                "ConfirmedProduct",
                "ConfirmedTopology",
                "DeletionReceipt",
                "DependencyEdge",
                "DesiredStructure",
                "Evidence",
                "ExternalDiscovery",
                "ExternalObject",
                "ExternalRecord",
                "LocalWrite",
                "MutationReceipt",
                "OperationKind",
                "OwnerQuestion",
                "SetupAdapter",
                "SetupApplyError",
                "SetupDiagnostic",
                "SetupManifest",
                "SetupOperation",
                "TopologyConflict",
                "TopologyProposal",
                "WORKSPACE_PATH",
                "WorkspaceUnit",
                "apply_local_write",
                "apply_setup",
                "approve_manifest",
                "build_local_documents",
                "build_setup_manifest",
                "confirm_topology",
                "discover_repository",
                "fingerprint_local_container",
                "load_rendered_yaml",
                "manifest_fingerprint",
                "normalize_external_discovery",
                "plan_local_writes",
                "propose_topology",
                "render_yaml",
            },
        )

    def test_values_are_immutable_and_preserve_ordered_apply_results(self):
        value = Evidence("docs", "docs/sample", "sample")
        with self.assertRaises(FrozenInstanceError):
            value.value = "other"

        evidence = ApplyEvidence(
            operation_id="story.sample.create",
            target_key="story.sample",
            external_id="story-1",
            observed_fingerprint="desired",
            disposition="verified",
        )
        result = ApplyResult(
            ready=False,
            evidence=(evidence,),
            manual_handoffs=(evidence,),
            local_writes=(evidence,),
        )
        self.assertEqual(result.evidence, (evidence,))
        self.assertEqual(result.manual_handoffs, (evidence,))
        self.assertEqual(result.local_writes, (evidence,))

    def test_all_public_value_types_are_frozen_dataclasses(self):
        topology = ConfirmedTopology(
            repository_id="repo-sample",
            products=manifest().products,
            domains=manifest().domains,
        )
        values = (
            Evidence("docs", "docs/sample", "sample"),
            Candidate("sample", "Sample", (), Confidence.CONFIRMED),
            TopologyConflict("sample", "product", (), ()),
            OwnerQuestion("sample.confirm", "Confirm", (), Confidence.LOW),
            manifest().products[0],
            manifest().domains[0],
            topology,
            manifest().diagnostics[0],
            manifest().operations[0],
            manifest(),
            ApprovedManifest(manifest(), manifest_fingerprint(manifest())),
            ApplyEvidence("op", "target", "external", "fingerprint", "verified"),
            ApplyResult(False, (), (), ()),
        )
        for value in values:
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, next(iter(value.__dataclass_fields__)), None)


if __name__ == "__main__":
    unittest.main()

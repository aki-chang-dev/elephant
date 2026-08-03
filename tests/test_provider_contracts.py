import unittest

from scripts.workspace_core import (
    CONTRACT_RUNTIME_CAPABILITIES,
    DELIVERY_RUNTIME_CAPABILITIES,
    KNOWLEDGE_RUNTIME_CAPABILITIES,
    STORY_RUNTIME_CAPABILITIES,
    DiagnosticCode,
    ProviderKind,
    preflight_provider,
)


PROVIDER_FAILURE_CASES = (
    (
        ProviderKind.STORY,
        STORY_RUNTIME_CAPABILITIES,
        "attach_delivery_evidence",
        "bind_product_contract",
    ),
    (
        ProviderKind.PRODUCT_KNOWLEDGE,
        KNOWLEDGE_RUNTIME_CAPABILITIES,
        "create_knowledge",
        "link_knowledge_relation",
    ),
    (
        ProviderKind.PRODUCT_CONTRACT,
        CONTRACT_RUNTIME_CAPABILITIES,
        "approve_contract",
        "create_contract_draft",
    ),
    (
        ProviderKind.DELIVERY_WORKSPACE,
        DELIVERY_RUNTIME_CAPABILITIES,
        "bind_delivery_branch",
        "persist_plan",
    ),
)


class ProviderContractTests(unittest.TestCase):
    def test_provider_kinds_and_capability_sets_match_the_exact_contract(self):
        cases = (
            (
                ProviderKind.STORY,
                "story",
                STORY_RUNTIME_CAPABILITIES,
                frozenset({
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
            ),
            (
                ProviderKind.PRODUCT_KNOWLEDGE,
                "product_knowledge",
                KNOWLEDGE_RUNTIME_CAPABILITIES,
                frozenset({
                    "read_knowledge",
                    "query_knowledge",
                    "create_knowledge",
                    "update_knowledge",
                    "supersede_knowledge",
                    "link_knowledge_relation",
                }),
            ),
            (
                ProviderKind.PRODUCT_CONTRACT,
                "product_contract",
                CONTRACT_RUNTIME_CAPABILITIES,
                frozenset({
                    "create_contract_draft",
                    "read_contract",
                    "update_contract_draft",
                    "approve_contract",
                    "create_contract_successor",
                    "resolve_active_contract",
                    "verify_contract_fingerprint",
                    "verify_story_binding",
                }),
            ),
            (
                ProviderKind.DELIVERY_WORKSPACE,
                "delivery_workspace",
                DELIVERY_RUNTIME_CAPABILITIES,
                frozenset({
                    "persist_technical_contract",
                    "persist_plan",
                    "bind_delivery_branch",
                    "record_conformance",
                    "promote_knowledge",
                    "remove_transient_artifacts",
                }),
            ),
        )
        self.assertEqual(tuple(ProviderKind), tuple(case[0] for case in cases))
        for provider, serialized, actual, expected in cases:
            with self.subTest(provider=provider):
                self.assertEqual(provider.value, serialized)
                self.assertIsInstance(actual, frozenset)
                self.assertEqual(actual, expected)

    def test_diagnostic_codes_match_the_exact_serialized_contract(self):
        self.assertEqual(
            tuple((member.name, member.value) for member in DiagnosticCode),
            (
                ("PLATFORM_UNSUPPORTED", "platform_unsupported"),
                ("CONNECTOR_CAPABILITY_MISSING", "connector_capability_missing"),
                ("PERMISSION_MISSING", "permission_missing"),
                ("CONFIGURATION_MISSING", "configuration_missing"),
            ),
        )

    def test_diagnostic_precedence_is_exact_for_every_logical_provider(self):
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
        for provider, required, capability, _ in PROVIDER_FAILURE_CASES:
            for missing_layers, expected_code in cumulative_failures:
                with self.subTest(provider=provider, missing_layers=missing_layers):
                    arguments = {
                        "platform_supported": required,
                        "exposed": required,
                        "permitted": required,
                        "configured": required,
                    }
                    for layer in missing_layers:
                        arguments[layer] = required - {capability}
                    result = preflight_provider(provider, **arguments)
                    self.assertFalse(result.ready)
                    self.assertEqual(
                        tuple(
                            (diagnostic.capability, diagnostic.code.value)
                            for diagnostic in result.diagnostics
                        ),
                        ((capability, expected_code),),
                    )

    def test_overlapping_failures_emit_one_sorted_diagnostic_per_capability(self):
        for (
            provider,
            required,
            platform_capability,
            connector_capability,
        ) in PROVIDER_FAILURE_CASES:
            with self.subTest(provider=provider):
                both = {platform_capability, connector_capability}
                result = preflight_provider(
                    provider,
                    platform_supported=required - {platform_capability},
                    exposed=required - both,
                    permitted=required - both,
                    configured=required - both,
                )
                self.assertFalse(result.ready)
                self.assertEqual(
                    tuple(
                        (diagnostic.capability, diagnostic.code.value)
                        for diagnostic in result.diagnostics
                    ),
                    (
                        (platform_capability, "platform_unsupported"),
                        (connector_capability, "connector_capability_missing"),
                    ),
                )

    def test_complete_contract_provider_is_ready(self):
        result = preflight_provider(
            ProviderKind.PRODUCT_CONTRACT,
            exposed=CONTRACT_RUNTIME_CAPABILITIES,
            permitted=CONTRACT_RUNTIME_CAPABILITIES,
            configured=CONTRACT_RUNTIME_CAPABILITIES,
            platform_supported=CONTRACT_RUNTIME_CAPABILITIES,
        )
        self.assertTrue(result.ready)
        self.assertEqual(result.diagnostics, ())

    def test_diagnostic_precedence_is_platform_connector_permission_configuration(self):
        required = set(CONTRACT_RUNTIME_CAPABILITIES)
        capability = "approve_contract"
        cases = (
            (required - {capability}, required, required, DiagnosticCode.PLATFORM_UNSUPPORTED),
            (required, required - {capability}, required, DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
            (required, required, required - {capability}, DiagnosticCode.PERMISSION_MISSING),
        )
        for platform, exposed, permitted, expected in cases:
            with self.subTest(expected=expected):
                result = preflight_provider(
                    ProviderKind.PRODUCT_CONTRACT,
                    platform_supported=platform,
                    exposed=exposed,
                    permitted=permitted,
                    configured=required,
                )
                self.assertEqual(result.diagnostics[0].code, expected)

    def test_configuration_missing_is_distinct(self):
        required = set(CONTRACT_RUNTIME_CAPABILITIES)
        result = preflight_provider(
            ProviderKind.PRODUCT_CONTRACT,
            platform_supported=required,
            exposed=required,
            permitted=required,
            configured=required - {"resolve_active_contract"},
        )
        self.assertEqual(result.diagnostics[0].code, DiagnosticCode.CONFIGURATION_MISSING)

    def test_matching_serialized_provider_name_is_accepted(self):
        result = preflight_provider(
            "product_contract",
            exposed=CONTRACT_RUNTIME_CAPABILITIES,
            permitted=CONTRACT_RUNTIME_CAPABILITIES,
            configured=CONTRACT_RUNTIME_CAPABILITIES,
            platform_supported=CONTRACT_RUNTIME_CAPABILITIES,
        )
        self.assertTrue(result.ready)

    def test_unknown_provider_raises_deliberate_value_error(self):
        with self.assertRaisesRegex(
            ValueError,
            "provider: expected one of delivery_workspace, product_contract, "
            "product_knowledge, story",
        ):
            preflight_provider(
                "warehouse",
                exposed=set(),
                permitted=set(),
                configured=set(),
                platform_supported=set(),
            )

    def test_capability_layers_require_set_like_collections(self):
        required = CONTRACT_RUNTIME_CAPABILITIES
        for layer in ("platform_supported", "exposed", "permitted", "configured"):
            for malformed in (None, [], "approve_contract"):
                with self.subTest(layer=layer, malformed=malformed):
                    arguments = {
                        "platform_supported": required,
                        "exposed": required,
                        "permitted": required,
                        "configured": required,
                    }
                    arguments[layer] = malformed
                    with self.assertRaisesRegex(
                        TypeError,
                        f"{layer}: expected set-like capability collection",
                    ):
                        preflight_provider(ProviderKind.PRODUCT_CONTRACT, **arguments)

import unittest

from scripts.workspace_core import (
    CONTRACT_RUNTIME_CAPABILITIES,
    DiagnosticCode,
    ProviderKind,
    preflight_provider,
)


class ProviderContractTests(unittest.TestCase):
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

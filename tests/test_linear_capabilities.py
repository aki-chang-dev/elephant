from dataclasses import FrozenInstanceError
import unittest

from scripts._elephant_runtime_forward import canonical_module


canonical_module("elephant_runtime.linear")

from elephant_runtime.linear import (
    CHECKPOINT_UPLOAD_CAPABILITY,
    ADMIN_CAPABILITY_TOOLS,
    NATIVE_GITHUB_DIFF_CAPABILITY,
    PRODUCT_KIND_LABELS_CAPABILITY,
    READ_ONLY_DISCOVERY_TOOLS,
    STORY_CAPABILITY_TOOLS,
    STORY_CAPABILITY_PLATFORM_REQUIREMENTS,
    TEAM_CREATION_CAPABILITY,
    WORKFLOW_STATUS_CREATION_CAPABILITY,
    WORKSPACE_LOCATOR_CAPABILITY,
    ContractBinding,
    DeliveryEvidence,
    LinearCapabilityInventory,
    LinearCapabilityPreflight,
    LinearProviderDiagnostic,
    LinearProviderError,
    LinearTool,
    LinearLabel,
    ProductRecap,
    StoryCreateRequest,
    StoryKey,
    StorySnapshot,
    preflight_story_capabilities,
)
from elephant_runtime.workspace_core import (
    CheckpointPhase,
    DiagnosticCode,
    DriftKind,
    HumanStatus,
    ProductDisposition,
    STORY_RUNTIME_CAPABILITIES,
)


LINEAR_ENTITY_ID = "123e4567-e89b-12d3-a456-426614174000"
ERROR_OPERATION_KEY = "elephant-linear/v1/" + "b" * 64


class LinearValueContractTests(unittest.TestCase):
    def test_tool_vocabulary_and_story_capability_mapping_are_exact(self):
        self.assertEqual(
            LinearTool.SAVE_ISSUE.value,
            "mcp__codex_apps__linear_save_issue",
        )
        expected = {
            "create_story": {
                "mcp__codex_apps__linear_list_issues",
                "mcp__codex_apps__linear_save_issue",
                "mcp__codex_apps__linear_get_issue",
            },
            "read_story": {"mcp__codex_apps__linear_get_issue"},
            "update_story_status": {
                "mcp__codex_apps__linear_list_issue_statuses",
                "mcp__codex_apps__linear_save_issue",
                "mcp__codex_apps__linear_get_issue",
            },
            "write_product_recap": {
                "mcp__codex_apps__linear_save_issue",
                "mcp__codex_apps__linear_get_issue",
            },
            "create_child_story": {
                "mcp__codex_apps__linear_list_issues",
                "mcp__codex_apps__linear_save_issue",
                "mcp__codex_apps__linear_get_issue",
            },
            "link_story_relation": {
                "mcp__codex_apps__linear_save_issue",
                "mcp__codex_apps__linear_get_issue",
            },
            "bind_product_contract": {
                "mcp__codex_apps__linear_save_issue",
                "mcp__codex_apps__linear_get_issue",
            },
            "read_checkpoint": {
                "mcp__codex_apps__linear_get_issue",
                "mcp__codex_apps__linear_get_attachment",
            },
            "write_checkpoint": {
                "mcp__codex_apps__linear_prepare_attachment_upload",
                "mcp__codex_apps__linear_create_attachment_from_upload",
                "mcp__codex_apps__linear_get_attachment",
                "mcp__codex_apps__linear_get_issue",
                "mcp__codex_apps__linear_delete_attachment",
            },
            "attach_delivery_evidence": {
                "mcp__codex_apps__linear_list_comments",
                "mcp__codex_apps__linear_save_comment",
                "mcp__codex_apps__linear_get_issue",
            },
        }
        self.assertEqual(set(STORY_CAPABILITY_TOOLS), set(STORY_RUNTIME_CAPABILITIES))
        self.assertEqual(
            {name: {tool.value for tool in tools} for name, tools in STORY_CAPABILITY_TOOLS.items()},
            expected,
        )
        self.assertEqual(
            STORY_CAPABILITY_PLATFORM_REQUIREMENTS["write_checkpoint"],
            frozenset({"host_raw_signed_put"}),
        )

    def test_administrative_and_read_only_inventory_is_exact(self):
        self.assertEqual(
            {tool.value for tool in READ_ONLY_DISCOVERY_TOOLS},
            {
                "mcp__codex_apps__linear_list_teams",
                "mcp__codex_apps__linear_get_team",
                "mcp__codex_apps__linear_get_user",
                "mcp__codex_apps__linear_list_issue_statuses",
                "mcp__codex_apps__linear_list_issue_labels",
                "mcp__codex_apps__linear_list_issues",
                "mcp__codex_apps__linear_get_issue",
            },
        )
        self.assertEqual(
            {
                capability: {tool.value for tool in tools}
                for capability, tools in ADMIN_CAPABILITY_TOOLS.items()
            },
            {
                TEAM_CREATION_CAPABILITY: set(),
                WORKFLOW_STATUS_CREATION_CAPABILITY: set(),
                WORKSPACE_LOCATOR_CAPABILITY: set(),
                PRODUCT_KIND_LABELS_CAPABILITY: {
                    "mcp__codex_apps__linear_create_issue_label",
                    "mcp__codex_apps__linear_list_issue_labels",
                },
                CHECKPOINT_UPLOAD_CAPABILITY: {
                    "mcp__codex_apps__linear_prepare_attachment_upload",
                    "mcp__codex_apps__linear_create_attachment_from_upload",
                    "mcp__codex_apps__linear_get_attachment",
                    "mcp__codex_apps__linear_get_issue",
                    "mcp__codex_apps__linear_delete_attachment",
                },
                NATIVE_GITHUB_DIFF_CAPABILITY: {
                    "mcp__codex_apps__linear_list_diffs",
                    "mcp__codex_apps__linear_get_diff",
                },
            },
        )

    def test_story_key_has_a_stable_canonical_marker_and_rejects_empty_parts(self):
        key = StoryKey("repo", "intent")

        self.assertEqual(
            key.marker,
            "elephant-story/v1/232c7752e52990b58e5b1b43ceeb48e2c83aa4fc0eb6b610fe6d6a29bf7c38a4",
        )
        self.assertRaises(ValueError, StoryKey, "", "intent")
        self.assertRaises(ValueError, StoryKey, "repo", "")

    def test_story_create_request_requires_task_three_authority_at_construction(self):
        with self.assertRaises(TypeError):
            StoryCreateRequest(
                key=StoryKey("repo", "intent"),
                title="Story",
                description="Recap",
                team_id="team-1",
                human_status=HumanStatus.BACKLOG,
            )

    def test_all_public_values_are_frozen(self):
        snapshot = StorySnapshot(
            key=StoryKey("repo", "intent"),
            issue_id="issue-1",
            title="Story",
            human_status=HumanStatus.BACKLOG,
            checkpoint_phase=CheckpointPhase.SHAPING,
        )
        values = (
            snapshot,
            StoryCreateRequest(
                key=snapshot.key,
                title="Story",
                description="Description",
                team_id="team-1",
                human_status=HumanStatus.BACKLOG,
                story_kind="engineering-only",
                product_label_id=None,
                product_label_name=None,
                kind_label_id="kind",
                kind_label_name="engineering-only",
                priority=3,
                project_id=None,
                parent_id=None,
                label_inventory=(LinearLabel("kind", "engineering-only", None, "Kind"),),
                product_group_label_ids=frozenset(),
                kind_group_label_ids=frozenset({"kind"}),
            ),
            ProductRecap(
                product_key="product",
                disposition=ProductDisposition.APPROVED,
                body="Approved",
            ),
            ContractBinding(contract_id="contract-1", fingerprint="a" * 64),
            DeliveryEvidence(
                kind=DriftKind.STALE_RECAP,
                reference="comment-1",
                summary="Delivered",
            ),
            LinearCapabilityInventory(
                platform_supported=frozenset(),
                exposed=frozenset(),
                permitted=frozenset(),
                configured=frozenset(),
            ),
            LinearProviderDiagnostic(
                capability="create_story",
                code=DiagnosticCode.PERMISSION_MISSING,
                blocking=True,
            ),
        )

        self.assertRaises(FrozenInstanceError, setattr, snapshot, "title", "changed")
        for value in values:
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, next(iter(value.__dataclass_fields__)), None)

    def test_error_only_retains_verified_receipt_identifiers(self):
        error = LinearProviderError(
            capability="write_checkpoint",
            tool=LinearTool.CREATE_ATTACHMENT_FROM_UPLOAD,
            diagnostic_code=DiagnosticCode.PERMISSION_MISSING,
            operation_key=ERROR_OPERATION_KEY,
            verified_prior_receipts=(
                ("attachment_id", LINEAR_ENTITY_ID),
                ("observed_fingerprint", "a" * 64),
            ),
        )

        self.assertEqual(
            error.verified_prior_receipts,
            (("attachment_id", LINEAR_ENTITY_ID), ("observed_fingerprint", "a" * 64)),
        )
        with self.assertRaisesRegex(ValueError, "safe receipt"):
            LinearProviderError(
                capability="write_checkpoint",
                tool=LinearTool.CREATE_ATTACHMENT_FROM_UPLOAD,
                diagnostic_code=DiagnosticCode.PERMISSION_MISSING,
                operation_key=ERROR_OPERATION_KEY,
                verified_prior_receipts=(("upload_url", "https://example.invalid/signed"),),
            )

    def test_error_allows_only_the_closed_linear_issue_identifier_receipt_format(self):
        error = LinearProviderError(
            capability="read_story",
            tool=LinearTool.GET_ISSUE,
            diagnostic_code=DiagnosticCode.PERMISSION_MISSING,
            operation_key=ERROR_OPERATION_KEY,
            verified_prior_receipts=(("issue_identifier", "MAI-2"),),
        )
        self.assertEqual(error.verified_prior_receipts, (("issue_identifier", "MAI-2"),))
        for invalid in ("MAI-0", "mai-2", "MAI-two", "MAI-2/token=secret"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "safe receipt"):
                    LinearProviderError(
                        capability="read_story",
                        tool=LinearTool.GET_ISSUE,
                        diagnostic_code=DiagnosticCode.PERMISSION_MISSING,
                        operation_key=ERROR_OPERATION_KEY,
                        verified_prior_receipts=(("issue_identifier", invalid),),
                    )

    def test_error_rejects_secret_content_even_under_benign_receipt_names_or_operation_key(self):
        secrets = (
            "token=super-secret",
            "Bearer super-secret",
            "data:image/png;base64,QUJDRA==",
        )
        for secret in secrets:
            with self.subTest(secret=secret):
                with self.assertRaisesRegex(ValueError, "safe") as receipt_error:
                    LinearProviderError(
                        capability="write_checkpoint",
                        tool=LinearTool.CREATE_ATTACHMENT_FROM_UPLOAD,
                        diagnostic_code=DiagnosticCode.PERMISSION_MISSING,
                        operation_key=ERROR_OPERATION_KEY,
                        verified_prior_receipts=(("attachment_id", secret),),
                    )
                self.assertNotIn(secret, str(receipt_error.exception))
                with self.assertRaisesRegex(ValueError, "safe") as operation_error:
                    LinearProviderError(
                        capability="write_checkpoint",
                        tool=LinearTool.CREATE_ATTACHMENT_FROM_UPLOAD,
                        diagnostic_code=DiagnosticCode.PERMISSION_MISSING,
                        operation_key=secret,
                    )
                self.assertNotIn(secret, str(operation_error.exception))

    def test_error_rejects_reviewer_bypasses_under_typed_receipt_and_operation_fields(self):
        probes = ("token_supersecret", "base64_QUJDRA", "base64_qujdra")
        for probe in probes:
            with self.subTest(probe=probe):
                with self.assertRaisesRegex(ValueError, "safe receipt"):
                    LinearProviderError(
                        capability="write_checkpoint",
                        tool=LinearTool.CREATE_ATTACHMENT_FROM_UPLOAD,
                        diagnostic_code=DiagnosticCode.PERMISSION_MISSING,
                        operation_key=ERROR_OPERATION_KEY,
                        verified_prior_receipts=(("attachment_id", probe),),
                    )
                with self.assertRaisesRegex(ValueError, "safe"):
                    LinearProviderError(
                        capability="write_checkpoint",
                        tool=LinearTool.CREATE_ATTACHMENT_FROM_UPLOAD,
                        diagnostic_code=DiagnosticCode.PERMISSION_MISSING,
                        operation_key=probe,
                    )


class LinearCapabilityInventoryTests(unittest.TestCase):
    def test_preflight_freezes_caller_diagnostics_and_validates_its_public_fields(self):
        diagnostic = LinearProviderDiagnostic(
            capability="create_story",
            code=DiagnosticCode.PERMISSION_MISSING,
            blocking=True,
        )
        supplied = [diagnostic]
        preflight = LinearCapabilityPreflight(ready=False, diagnostics=supplied)
        supplied.append(diagnostic)

        self.assertEqual(preflight.diagnostics, (diagnostic,))
        with self.assertRaisesRegex(TypeError, "ready"):
            LinearCapabilityPreflight(ready="false", diagnostics=())
        with self.assertRaisesRegex(TypeError, "diagnostics"):
            LinearCapabilityPreflight(ready=False, diagnostics=(object(),))

    def test_preflight_requires_every_mapped_tool_and_reports_the_first_missing_layer(self):
        all_tools = frozenset(tool.value for tool in LinearTool)
        inventory = LinearCapabilityInventory(
            platform_supported=all_tools | {"host_raw_signed_put"},
            exposed=all_tools - {LinearTool.SAVE_ISSUE.value},
            permitted=all_tools | {"host_raw_signed_put"},
            configured=STORY_RUNTIME_CAPABILITIES,
        )

        result = preflight_story_capabilities(inventory)

        self.assertFalse(result.ready)
        self.assertEqual(
            tuple((item.capability, item.code) for item in result.diagnostics),
            (
                ("bind_product_contract", DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
                ("create_child_story", DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
                ("create_story", DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
                ("link_story_relation", DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
                ("update_story_status", DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
                ("write_product_recap", DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
            ),
        )

    def test_absent_administrative_tools_and_configuration_have_exact_diagnostics(self):
        complete_tools = frozenset(tool.value for tool in LinearTool)
        inventory = LinearCapabilityInventory(
            platform_supported=complete_tools | {"host_raw_signed_put"},
            exposed=complete_tools,
            permitted=complete_tools | {"host_raw_signed_put"},
            configured=STORY_RUNTIME_CAPABILITIES - {"update_story_status"},
        )

        result = preflight_story_capabilities(
            inventory,
            capabilities=(
                TEAM_CREATION_CAPABILITY,
                WORKFLOW_STATUS_CREATION_CAPABILITY,
                WORKSPACE_LOCATOR_CAPABILITY,
                PRODUCT_KIND_LABELS_CAPABILITY,
                CHECKPOINT_UPLOAD_CAPABILITY,
                NATIVE_GITHUB_DIFF_CAPABILITY,
                "update_story_status",
            ),
        )

        self.assertEqual(
            tuple((item.capability, item.code) for item in result.diagnostics),
            (
                (CHECKPOINT_UPLOAD_CAPABILITY, DiagnosticCode.CONFIGURATION_MISSING),
                (TEAM_CREATION_CAPABILITY, DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
                (WORKFLOW_STATUS_CREATION_CAPABILITY, DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
                (NATIVE_GITHUB_DIFF_CAPABILITY, DiagnosticCode.CONFIGURATION_MISSING),
                (PRODUCT_KIND_LABELS_CAPABILITY, DiagnosticCode.CONFIGURATION_MISSING),
                ("update_story_status", DiagnosticCode.CONFIGURATION_MISSING),
                (WORKSPACE_LOCATOR_CAPABILITY, DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
            ),
        )

    def test_authorization_failure_on_an_exposed_tool_is_permission_missing(self):
        all_tools = frozenset(tool.value for tool in LinearTool)
        inventory = LinearCapabilityInventory(
            platform_supported=all_tools | {"host_raw_signed_put"},
            exposed=all_tools,
            permitted=(all_tools | {"host_raw_signed_put"}) - {LinearTool.SAVE_ISSUE.value},
            configured=STORY_RUNTIME_CAPABILITIES,
        )

        result = preflight_story_capabilities(inventory, capabilities=("create_story",))

        self.assertEqual(
            tuple((item.capability, item.code) for item in result.diagnostics),
            (("create_story", DiagnosticCode.PERMISSION_MISSING),),
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
import unittest

from scripts._elephant_runtime_forward import canonical_module


canonical_module("elephant_runtime.linear")

from elephant_runtime.linear import (
    Checkpoint,
    CheckpointDelivery,
    ContractBinding,
    DeliveryRecord,
    LinearLabel,
    LinearProviderError,
    LinearDrift,
    LinearStoryProvider,
    LinearStoryProviderConfig,
    LinearTool,
    StoryCreateRequest,
    StoryKey,
    StorySnapshot,
)
from elephant_runtime.workspace_core import CheckpointPhase, DiagnosticCode, HumanStatus


def _story_payload(request: StoryCreateRequest) -> dict[str, object]:
    recap = request.description.strip()
    return {
        "id": "ISS-1",
        "identifier": "ELE-1",
        "title": request.title,
        "description": (
            f"{recap}\n\n---\nElephant story key: `{request.key.marker}`\n"
            f"Elephant recap SHA-256: `{sha256(recap.encode('utf-8')).hexdigest()}`"
        ),
        "teamId": request.team_id,
        "team": "Elephant",
        "status": "Backlog",
        "statusType": "backlog",
        "labels": (
            ([] if request.product_label_name is None else [request.product_label_name])
            + [request.kind_label_name]
        ),
        "priority": {"value": request.priority, "name": "Medium"},
        "parentId": request.parent_id,
        "projectId": request.project_id,
        "attachments": [],
        "stateHistory": [
            {
                "state": {"id": "status-backlog", "name": "Backlog", "type": "backlog"},
                "startedAt": "2026-08-04T00:00:00Z",
                "endedAt": None,
            }
        ],
        "relations": {"blocks": [], "blockedBy": [], "relatedTo": [], "duplicateOf": None},
    }


class StrictEvidenceConnector:
    """Strict fake Linear connector; it has no external behavior."""

    def __init__(self, request: StoryCreateRequest) -> None:
        self.issue = _story_payload(request)
        self.calls: list[tuple[LinearTool, tuple[tuple[str, object], ...]]] = []
        self.attachments: dict[str, dict[str, object]] = {}
        self.uploads: dict[str, bytes | None] = {}
        self.comments: dict[str, str] = {}
        self.comment_pages: dict[str | None, dict[str, object]] = {}
        self.diff: dict[str, object] | None = None
        self.fail_after_finalize = False
        self.fail_next_attachment_get = False
        self.next_attachment = 1
        self.next_comment = 1

    def call(self, tool: LinearTool, arguments: tuple[tuple[str, object], ...]) -> dict[str, object]:
        self.calls.append((tool, arguments))
        values = dict(arguments)
        if tool is LinearTool.LIST_ISSUES:
            return {"issues": [deepcopy(self.issue)], "hasNextPage": False}
        if tool is LinearTool.GET_ISSUE:
            if values != {"id": "ISS-1", "includeRelations": True}:
                raise AssertionError(f"unexpected get_issue arguments: {arguments!r}")
            issue = deepcopy(self.issue)
            issue["attachments"] = [
                {key: row[key] for key in ("id", "url", "title")}
                for row in self.attachments.values()
            ]
            return issue
        if tool is LinearTool.SAVE_ISSUE:
            if values.get("id") != "ISS-1" or set(values) - {"id", "description", "links"}:
                raise AssertionError(f"unexpected save_issue arguments: {arguments!r}")
            if "description" in values:
                self.issue["description"] = values["description"]
            if "links" in values:
                if not isinstance(values["links"], tuple):
                    raise TypeError("links: expected immutable array")
                for link in values["links"]:
                    if not isinstance(link, dict) or set(link) != {"title", "url"}:
                        raise TypeError("links: expected exact connector objects")
                    attachment_id = f"00000000-0000-0000-0000-{self.next_attachment:012d}"
                    self.next_attachment += 1
                    self.attachments[attachment_id] = {
                        "id": attachment_id,
                        "title": link["title"],
                        "url": link["url"],
                        "data": None,
                    }
            return {"id": "ISS-1"}
        if tool is LinearTool.PREPARE_ATTACHMENT_UPLOAD:
            required = {"issue", "filename", "contentType", "size", "title"}
            if set(values) != required or values["issue"] != "ISS-1" or values["contentType"] != "application/json":
                raise AssertionError(f"unexpected prepare arguments: {arguments!r}")
            asset = f"linear-asset://{values['filename']}"
            self.uploads[asset] = None
            return {
                "assetUrl": asset,
                "uploadRequest": {
                    "url": "https://upload.invalid/opaque-sentinel",
                    "headers": {
                        "content-type": "application/json",
                        "x-upload-auth": "opaque-sentinel",
                    },
                },
            }
        if tool is LinearTool.CREATE_ATTACHMENT_FROM_UPLOAD:
            if set(values) != {"assetUrl", "issue", "title"} or values["issue"] != "ISS-1":
                raise AssertionError(f"unexpected finalize arguments: {arguments!r}")
            data = self.uploads[values["assetUrl"]]
            if data is None:
                raise AssertionError("finalize before raw upload")
            attachment_id = f"00000000-0000-0000-0000-{self.next_attachment:012d}"
            self.next_attachment += 1
            self.attachments[attachment_id] = {
                "id": attachment_id,
                "title": values["title"],
                "url": values["assetUrl"],
                "data": data,
            }
            if self.fail_after_finalize:
                self.fail_after_finalize = False
                raise TimeoutError("connector timed out after finalize")
            return {"id": attachment_id}
        if tool is LinearTool.GET_ATTACHMENT:
            if self.fail_next_attachment_get:
                self.fail_next_attachment_get = False
                raise TimeoutError("connector timed out before attachment read-back")
            row = self.attachments[values["id"]]
            return {"id": row["id"], "data": row["data"]}
        if tool is LinearTool.DELETE_ATTACHMENT:
            del self.attachments[values["id"]]
            return {"id": values["id"]}
        if tool is LinearTool.LIST_COMMENTS:
            if self.comment_pages:
                return deepcopy(self.comment_pages[values.get("cursor")])
            return {
                "comments": [
                    {"id": identifier, "body": body}
                    for identifier, body in self.comments.items()
                ],
                "hasNextPage": False,
            }
        if tool is LinearTool.SAVE_COMMENT:
            if "id" in values:
                if set(values) != {"id", "body"}:
                    raise AssertionError("comment update must use id and body only")
                self.comments[values["id"]] = values["body"]
                for page in self.comment_pages.values():
                    for comment in page.get("comments", []):
                        if comment["id"] == values["id"]:
                            comment["body"] = values["body"]
                return {"id": values["id"]}
            if set(values) != {"issueId", "body"} or values["issueId"] != "ISS-1":
                raise AssertionError("comment create must use issueId and body")
            identifier = f"00000000-0000-0000-0001-{self.next_comment:012d}"
            self.next_comment += 1
            self.comments[identifier] = values["body"]
            return {"id": identifier}
        if tool is LinearTool.GET_DIFF:
            if set(values) != {"urlOrId"}:
                raise AssertionError("get_diff must use urlOrId")
            if self.diff is None:
                raise LookupError("no configured workspace diff")
            return deepcopy(self.diff)
        raise AssertionError(f"unexpected tool: {tool}")


class StrictRawUploader:
    """Injected host uploader that accepts bytes but performs no network PUT."""

    def __init__(self, connector: StrictEvidenceConnector) -> None:
        self.connector = connector
        self.calls: list[tuple[int, tuple[str, ...]]] = []
        self.fail = False

    def put(self, url: str, headers: tuple[tuple[str, str], ...], data: bytes) -> None:
        self.calls.append((len(data), tuple(name for name, _ in headers)))
        if self.fail:
            self.fail = False
            raise TimeoutError("host raw upload failed")
        if not url.startswith("https://upload.invalid/"):
            raise AssertionError("unexpected signed upload target")
        asset = next(reversed(self.connector.uploads))
        self.connector.uploads[asset] = bytes(data)


class LinearProductRecapTests(unittest.TestCase):
    def setUp(self) -> None:
        labels = (
            LinearLabel("product-tracker", "Tracker", None, "Product"),
            LinearLabel("kind-product", "product-facing", None, "Kind"),
            LinearLabel("kind-engineering", "engineering-only", None, "Kind"),
        )
        self.request = StoryCreateRequest(
            key=StoryKey("repo", "intent"),
            title="Persist Linear evidence",
            description="A concise initial recap.",
            team_id="team-1",
            human_status=HumanStatus.BACKLOG,
            story_kind="product-facing",
            product_label_id="product-tracker",
            product_label_name="Tracker",
            kind_label_id="kind-product",
            kind_label_name="product-facing",
            priority=3,
            project_id=None,
            parent_id=None,
            label_inventory=labels,
            product_group_label_ids=frozenset({"product-tracker"}),
            kind_group_label_ids=frozenset({"kind-product", "kind-engineering"}),
        )
        self.connector = StrictEvidenceConnector(self.request)
        self.provider = LinearStoryProvider(
            self.connector,
            LinearStoryProviderConfig(
                team_id="team-1",
                statuses=(
                    (HumanStatus.BACKLOG, "status-backlog"),
                    (HumanStatus.SHAPING, "status-shaping"),
                    (HumanStatus.READY, "status-ready"),
                    (HumanStatus.IN_PROGRESS, "status-progress"),
                    (HumanStatus.DONE, "status-done"),
                    (HumanStatus.CANCELED, "status-canceled"),
                ),
                label_inventory=labels,
                product_group_label_ids=frozenset({"product-tracker"}),
                kind_group_label_ids=frozenset({"kind-product", "kind-engineering"}),
                product_facing_kind_label_id="kind-product",
                engineering_only_kind_label_id="kind-engineering",
            ),
        )

    def test_writes_exact_canonical_product_recap_after_authority_read(self) -> None:
        problem = "Teams cannot recover verified delivery evidence from the authoritative story."
        outcome = "The story exposes concise verified evidence without internal implementation detail."
        acceptance = ("The canonical Product Recap survives exact Linear read-back.",)
        contract_url = "https://www.notion.so/contract-123"
        canonical_fields = json.dumps(
            {
                "acceptance": list(acceptance),
                "behavior_preservation": None,
                "contract_url": contract_url,
                "outcome": outcome,
                "problem": problem,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        expected = (
            "## Product Recap\n\n"
            f"**Problem:** {problem}\n\n"
            f"**Outcome:** {outcome}\n\n"
            "**Acceptance:**\n\n"
            f"- {acceptance[0]}\n\n"
            f"**Product Contract:** [Open in Notion](<{contract_url}>)\n\n"
            "---\n"
            f"Elephant story key: `{self.request.key.marker}`\n"
            f"Elephant recap SHA-256: `{sha256(canonical_fields).hexdigest()}`"
        )

        issue = self.provider.write_product_recap(
            self.request,
            problem=problem,
            outcome=outcome,
            acceptance=acceptance,
            contract_url=contract_url,
        )

        self.assertEqual(issue.description, expected)
        self.assertEqual(self.connector.issue["description"], expected)
        self.assertEqual(
            tuple(tool for tool, _ in self.connector.calls),
            (LinearTool.LIST_ISSUES, LinearTool.GET_ISSUE, LinearTool.SAVE_ISSUE, LinearTool.GET_ISSUE),
        )

    def test_engineering_only_recap_uses_behavior_preservation_instead_of_contract(self) -> None:
        request = replace_story_kind(self.request)
        connector = StrictEvidenceConnector(request)
        provider = LinearStoryProvider(connector, self.provider._config)

        issue = provider.write_product_recap(
            request,
            problem="The refactor risks changing externally observable behavior.",
            outcome="The internals are simplified while behavior remains stable.",
            acceptance=("Existing observable behavior is preserved.",),
            behavior_preservation="All public behavior and compatibility checks remain unchanged.",
        )

        self.assertIn("**Behavior preservation:** All public behavior", issue.description)
        self.assertNotIn("Product Contract", issue.description)

    def test_rejects_non_recap_payloads_before_any_connector_call(self) -> None:
        forbidden = (
            "## Product Contract\nFull contract text",
            "## Technical Contract\nArchitecture",
            "## Implementation Checklist\n- [ ] mutate",
            '{"schema":"elephant.linear-checkpoint/v1"}',
            "## Internal Progress\nUploading",
        )
        for payload in forbidden:
            with self.subTest(payload=payload):
                self.connector.calls.clear()
                with self.assertRaises(ValueError):
                    self.provider.write_product_recap(
                        self.request,
                        problem=payload,
                        outcome="A concise outcome.",
                        acceptance=("An observable result.",),
                        contract_url="https://www.notion.so/contract-123",
                    )
                self.assertEqual(self.connector.calls, [])


class LinearContractBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        fixture = LinearProductRecapTests()
        fixture.setUp()
        self.request = fixture.request
        self.connector = fixture.connector
        self.provider = fixture.provider

    def test_appends_one_exact_contract_link_and_verifies_issue_attachments(self) -> None:
        issue = self.provider.bind_product_contract(
            self.request, "https://www.notion.so/contract-123"
        )

        self.assertEqual(
            tuple((item.title, item.url) for item in issue.attachments),
            (("Elephant Product Contract", "https://www.notion.so/contract-123"),),
        )
        save = next(args for tool, args in self.connector.calls if tool is LinearTool.SAVE_ISSUE)
        self.assertEqual(
            save,
            (("id", "ISS-1"), ("links", ({"title": "Elephant Product Contract", "url": "https://www.notion.so/contract-123"},))),
        )

    def test_different_existing_contract_url_is_semantic_drift_not_append(self) -> None:
        self.provider.bind_product_contract(self.request, "https://www.notion.so/contract-old")
        self.connector.calls.clear()

        result = self.provider.bind_product_contract(
            self.request, "https://www.notion.so/contract-new"
        )

        self.assertIsInstance(result, LinearDrift)
        self.assertEqual(result.kind.value, "approved_contract_changed")
        self.assertNotIn(LinearTool.SAVE_ISSUE, tuple(tool for tool, _ in self.connector.calls))


class LinearCheckpointLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        fixture = LinearProductRecapTests()
        fixture.setUp()
        self.request = fixture.request
        self.connector = fixture.connector
        self.uploader = StrictRawUploader(self.connector)
        self.provider = LinearStoryProvider(
            self.connector, fixture.provider._config, raw_uploader=self.uploader
        )
        self.snapshot = StorySnapshot(
            key=self.request.key,
            issue_id="ISS-1",
            title=self.request.title,
            human_status=HumanStatus.BACKLOG,
            checkpoint_phase=CheckpointPhase.SHAPING,
        )
        self.binding = ContractBinding("page-1", "a" * 64)
        self.empty_delivery = CheckpointDelivery(None, None, None, None)

    def test_checkpoint_has_exact_canonical_bytes_digest_and_filename(self) -> None:
        checkpoint = Checkpoint(
            story_key=self.request.key.marker,
            issue_id="ISS-1",
            phase=CheckpointPhase.SHAPING,
            sequence=1,
            contract=self.binding,
            delivery=self.empty_delivery,
            previous_sha256=None,
        )
        expected = (
            '{"contract":{"fingerprint":"' + "a" * 64 + '","page_id":"page-1"},'
            '"delivery":{"branch":null,"merge_commit":null,"pull_request_url":null,"verification_sha256":null},'
            '"issue_id":"ISS-1","phase":"shaping","previous_sha256":null,"schema":"elephant.linear-checkpoint/v1",'
            '"sequence":1,"story_key":"' + self.request.key.marker + '"}\n'
        ).encode("utf-8")

        self.assertEqual(checkpoint.canonical_bytes, expected)
        self.assertEqual(checkpoint.sha256, sha256(expected).hexdigest())
        self.assertEqual(
            checkpoint.filename,
            f"elephant-checkpoint-{self.request.key.marker.rsplit('/', 1)[1]}-1.json",
        )
        self.assertEqual(Checkpoint.from_bytes(expected), checkpoint)

    def test_checkpoint_parser_rejects_schema_issue_key_and_noncanonical_bytes(self) -> None:
        valid = Checkpoint(
            self.request.key.marker, "ISS-1", CheckpointPhase.SHAPING, 1,
            self.binding, self.empty_delivery, None,
        ).canonical_bytes
        payload = json.loads(valid)
        cases = (
            {**payload, "schema": "elephant.linear-checkpoint/v2"},
            {**payload, "issue_id": "ISS-2"},
            {**payload, "story_key": StoryKey("repo", "other").marker},
        )
        for changed in cases:
            with self.subTest(changed=changed):
                encoded = json.dumps(changed, separators=(",", ":"), sort_keys=True).encode() + b"\n"
                if changed["schema"].endswith("/v2"):
                    with self.assertRaises(ValueError):
                        Checkpoint.from_bytes(encoded)
                else:
                    checkpoint = Checkpoint.from_bytes(encoded)
                    with self.assertRaises(ValueError):
                        checkpoint.verify_identity(self.snapshot)
        with self.assertRaises(ValueError):
            Checkpoint.from_bytes(valid[:-1])

    def test_write_uses_prepare_host_put_finalize_readback_then_cleans_exact_prior(self) -> None:
        first = self.provider.write_checkpoint(
            self.snapshot, self.binding, delivery=self.empty_delivery
        )
        second_snapshot = replace(self.snapshot, checkpoint_phase=CheckpointPhase.READY)
        second = self.provider.write_checkpoint(
            second_snapshot, self.binding, delivery=self.empty_delivery
        )

        self.assertEqual((first.sequence, second.sequence), (1, 2))
        self.assertEqual(second.previous_sha256, first.sha256)
        self.assertEqual(tuple(row["title"] for row in self.connector.attachments.values()), (second.filename,))
        tools = tuple(tool for tool, _ in self.connector.calls)
        self.assertEqual(tools.count(LinearTool.PREPARE_ATTACHMENT_UPLOAD), 2)
        self.assertEqual(tools.count(LinearTool.CREATE_ATTACHMENT_FROM_UPLOAD), 2)
        self.assertEqual(tools.count(LinearTool.DELETE_ATTACHMENT), 1)
        self.assertEqual(len(self.uploader.calls), 2)

    def test_finalize_timeout_leaves_context_then_replay_adopts_verified_new_checkpoint(self) -> None:
        self.connector.fail_after_finalize = True
        with self.assertRaisesRegex(TimeoutError, "checkpoint finalize failed") as raised:
            self.provider.write_checkpoint(
                self.snapshot, self.binding, delivery=self.empty_delivery
            )
        self.assertNotIn("upload.invalid", str(raised.exception))
        self.assertNotIn("opaque-sentinel", str(raised.exception))
        self.assertEqual(len(self.connector.attachments), 1)

        checkpoint = self.provider.write_checkpoint(
            self.snapshot, self.binding, delivery=self.empty_delivery
        )

        self.assertEqual(checkpoint.sequence, 1)
        self.assertEqual(
            tuple(tool for tool, _ in self.connector.calls).count(LinearTool.CREATE_ATTACHMENT_FROM_UPLOAD),
            1,
        )

    def test_read_stops_for_duplicate_sequence_or_changed_contract_fingerprint(self) -> None:
        checkpoint = self.provider.write_checkpoint(
            self.snapshot, self.binding, delivery=self.empty_delivery
        )
        original = next(iter(self.connector.attachments.values()))
        duplicate = deepcopy(original)
        duplicate["id"] = "00000000-0000-0000-0000-999999999999"
        self.connector.attachments[duplicate["id"]] = duplicate

        duplicate_result = self.provider.read_checkpoint(self.snapshot, self.binding)
        self.assertEqual(duplicate_result.kind.value, "duplicate_authority")
        del self.connector.attachments[duplicate["id"]]

        changed = self.provider.read_checkpoint(
            self.snapshot, ContractBinding("page-1", "b" * 64)
        )
        self.assertEqual(changed.kind.value, "approved_contract_changed")
        self.assertEqual(checkpoint.sequence, 1)

    def test_raw_upload_failure_is_sanitized_and_never_finalized(self) -> None:
        self.uploader.fail = True
        with self.assertRaisesRegex(TimeoutError, "checkpoint raw upload failed") as raised:
            self.provider.write_checkpoint(
                self.snapshot, self.binding, delivery=self.empty_delivery
            )
        self.assertNotIn("opaque-sentinel", str(raised.exception))
        self.assertEqual(self.connector.attachments, {})
        self.assertNotIn(
            LinearTool.CREATE_ATTACHMENT_FROM_UPLOAD,
            tuple(tool for tool, _ in self.connector.calls),
        )


class LinearDeliveryEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        fixture = LinearProductRecapTests()
        fixture.setUp()
        self.request = fixture.request
        self.connector = fixture.connector
        self.provider = fixture.provider
        self.record = DeliveryRecord(
            branch="feature/linear-evidence",
            branch_url="https://github.com/example/elephant/tree/feature/linear-evidence",
            pull_request_url="https://github.com/example/elephant/pull/42",
            merge_commit="1" * 40,
            verification_url="https://github.com/example/elephant/actions/runs/123",
            verification_sha256="b" * 64,
        )

    def test_paginates_marker_comment_updates_by_id_and_appends_exact_links(self) -> None:
        marker = f"Elephant delivery evidence: `{self.request.key.marker}`"
        comment_id = "00000000-0000-0000-0001-000000000001"
        self.connector.comments[comment_id] = f"old\n\n---\n{marker}"
        self.connector.comment_pages = {
            None: {"comments": [], "hasNextPage": True, "cursor": "next"},
            "next": {"comments": [{"id": comment_id, "body": self.connector.comments[comment_id]}], "hasNextPage": False},
        }

        issue = self.provider.attach_delivery_evidence(self.request, self.record)

        comment_save = next(args for tool, args in self.connector.calls if tool is LinearTool.SAVE_COMMENT)
        self.assertEqual(dict(comment_save)["id"], comment_id)
        self.assertNotIn("issueId", dict(comment_save))
        self.assertEqual(
            tuple((item.title, item.url) for item in issue.attachments),
            (
                ("Elephant Delivery Branch", self.record.branch_url),
                ("Elephant Pull Request", self.record.pull_request_url),
                ("Elephant Verification", self.record.verification_url),
            ),
        )
        list_calls = [args for tool, args in self.connector.calls if tool is LinearTool.LIST_COMMENTS]
        self.assertIn((('issueId', 'ISS-1'), ('cursor', 'next')), list_calls)

    def test_duplicate_marker_comments_stop_before_mutation(self) -> None:
        marker = f"Elephant delivery evidence: `{self.request.key.marker}`"
        self.connector.comments = {
            "00000000-0000-0000-0001-000000000001": f"one\n\n---\n{marker}",
            "00000000-0000-0000-0001-000000000002": f"two\n\n---\n{marker}",
        }

        result = self.provider.attach_delivery_evidence(self.request, self.record)

        self.assertEqual(result.kind.value, "duplicate_authority")
        self.assertNotIn(LinearTool.SAVE_COMMENT, tuple(tool for tool, _ in self.connector.calls))

    def test_github_binding_uses_exact_url_or_id_and_requires_same_issue_identifier(self) -> None:
        self.provider.attach_delivery_evidence(self.request, self.record)
        self.connector.diff = {
            "id": "diff-1",
            "url": self.record.pull_request_url,
            "issueIdentifier": "ELE-1",
        }
        self.connector.calls.clear()

        diff = self.provider.verify_github_binding(
            self.request,
            self.record.pull_request_url,
            "ELE-1",
            native_diff_tool_exposed=True,
            native_diff_configured=True,
        )

        self.assertEqual(diff.issue_identifier, "ELE-1")
        self.assertIn(
            (LinearTool.GET_DIFF, (("urlOrId", self.record.pull_request_url),)),
            self.connector.calls,
        )

    def test_github_binding_classifies_missing_tool_and_configuration_without_git_fallback(self) -> None:
        self.provider.attach_delivery_evidence(self.request, self.record)
        cases = (
            (False, False, DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
            (True, False, DiagnosticCode.CONFIGURATION_MISSING),
        )
        for exposed, configured, expected in cases:
            with self.subTest(expected=expected):
                self.connector.calls.clear()
                with self.assertRaises(LinearProviderError) as raised:
                    self.provider.verify_github_binding(
                        self.request,
                        self.record.pull_request_url,
                        "ELE-1",
                        native_diff_tool_exposed=exposed,
                        native_diff_configured=configured,
                    )
                self.assertEqual(raised.exception.diagnostic_code, expected)
                self.assertNotIn(LinearTool.GET_DIFF, tuple(tool for tool, _ in self.connector.calls))

    def test_exposed_diff_without_issue_integration_is_configuration_missing(self) -> None:
        self.provider.attach_delivery_evidence(self.request, self.record)
        self.connector.diff = {
            "id": "diff-1",
            "url": self.record.pull_request_url,
        }

        with self.assertRaises(LinearProviderError) as raised:
            self.provider.verify_github_binding(
                self.request,
                self.record.pull_request_url,
                "ELE-1",
                native_diff_tool_exposed=True,
                native_diff_configured=True,
            )

        self.assertEqual(
            raised.exception.diagnostic_code, DiagnosticCode.CONFIGURATION_MISSING
        )


def replace_story_kind(request: StoryCreateRequest) -> StoryCreateRequest:
    from dataclasses import replace

    return replace(
        request,
        story_kind="engineering-only",
        product_label_id=None,
        product_label_name=None,
        kind_label_id="kind-engineering",
        kind_label_name="engineering-only",
    )


if __name__ == "__main__":
    unittest.main()

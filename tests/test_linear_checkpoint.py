from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
import unittest

from scripts._elephant_runtime_forward import canonical_module


canonical_module("elephant_runtime.linear")

from elephant_runtime.linear import (
    NATIVE_GITHUB_DIFF_CAPABILITY,
    Checkpoint,
    CheckpointDelivery,
    ContractBinding,
    DeliveryRecord,
    LinearLabel,
    LinearCapabilityInventory,
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
        self.hidden_attachments: dict[str, dict[str, object]] = {}
        self.uploads: dict[str, bytes | None] = {}
        self.comments: dict[str, str] = {}
        self.hidden_comments: dict[str, str] = {}
        self.comment_pages: dict[str | None, dict[str, object]] = {}
        self.diff: dict[str, object] | None = None
        self.fail_after_finalize = False
        self.fail_next_attachment_get = False
        self.attachment_get_error: Exception | None = None
        self.after_finalize = None
        self.delay_comment_visibility = False
        self.delay_link_visibility = False
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
                        "content": None,
                    }
                    if self.delay_link_visibility:
                        self.hidden_attachments[attachment_id] = self.attachments.pop(attachment_id)
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
                "content": data,
            }
            if self.after_finalize is not None:
                callback = self.after_finalize
                self.after_finalize = None
                callback(attachment_id)
            if self.fail_after_finalize:
                self.fail_after_finalize = False
                raise TimeoutError("connector timed out after finalize")
            return {"id": attachment_id}
        if tool is LinearTool.GET_ATTACHMENT:
            if self.attachment_get_error is not None:
                error = self.attachment_get_error
                self.attachment_get_error = None
                raise error
            if self.fail_next_attachment_get:
                self.fail_next_attachment_get = False
                raise TimeoutError("connector timed out before attachment read-back")
            row = self.attachments[values["id"]]
            return {"id": row["id"], "contentRef": f"memory:{row['id']}"}
        if tool is LinearTool.DELETE_ATTACHMENT:
            del self.attachments[values["id"]]
            return {"id": values["id"]}
        if tool is LinearTool.LIST_COMMENTS:
            if self.comment_pages:
                return deepcopy(self.comment_pages[values.get("cursor")])
            return {
                "comments": [
                    {"id": identifier, "body": body, "quotedText": None}
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
            target = self.hidden_comments if self.delay_comment_visibility else self.comments
            target[identifier] = values["body"]
            return {"id": identifier}
        if tool is LinearTool.GET_DIFF:
            if set(values) != {"urlOrId"}:
                raise AssertionError("get_diff must use urlOrId")
            if self.diff is None:
                raise LookupError("no configured workspace diff")
            return deepcopy(self.diff)
        raise AssertionError(f"unexpected tool: {tool}")

    def reveal_delayed_evidence(self) -> None:
        self.comments.update(self.hidden_comments)
        self.hidden_comments.clear()
        self.attachments.update(self.hidden_attachments)
        self.hidden_attachments.clear()


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


class StrictAttachmentContentReader:
    """Injected fake adapter for the connector's intentionally opaque response."""

    def __init__(self, connector: StrictEvidenceConnector) -> None:
        self.connector = connector
        self.fail: Exception | None = None

    def read(self, response: object, *, attachment_id: str) -> bytes:
        if self.fail is not None:
            error = self.fail
            self.fail = None
            raise error
        if response != {"id": attachment_id, "contentRef": f"memory:{attachment_id}"}:
            raise ValueError("unexpected opaque attachment response")
        content = self.connector.attachments[attachment_id]["content"]
        if not isinstance(content, bytes):
            raise ValueError("attachment content is unavailable")
        return content


def complete_native_diff_inventory(*, configured: bool = True) -> LinearCapabilityInventory:
    tools = frozenset(tool.value for tool in LinearTool)
    return LinearCapabilityInventory(
        platform_supported=tools,
        exposed=tools,
        permitted=tools,
        configured=(frozenset({NATIVE_GITHUB_DIFF_CAPABILITY}) if configured else frozenset()),
    )


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

    def test_rejects_technical_plans_paths_checklists_and_generic_progress_content(self) -> None:
        cases = (
            ("Technical plan: edit provider.py and checkpoint.py.", ("An observable result.",)),
            ("A concise problem.", ("Implementation plan: modify the provider.",)),
            ("Modify plugins/elephant/elephant_runtime/linear/provider.py.", ("An observable result.",)),
            ("A concise problem.", ("- [ ] finish the checkpoint",)),
            ('{"sequence":1,"phase":"ready"}', ("An observable result.",)),
            ("Progress update: attachment upload is complete.", ("An observable result.",)),
        )
        for problem, acceptance in cases:
            with self.subTest(problem=problem, acceptance=acceptance):
                self.connector.calls.clear()
                with self.assertRaises(ValueError):
                    self.provider.write_product_recap(
                        self.request,
                        problem=problem,
                        outcome="The story exposes an observable outcome.",
                        acceptance=acceptance,
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
        binding = ContractBinding("contract-123", "a" * 64)
        verified, replay = self.provider.bind_product_contract(
            self.request, binding, "https://www.notion.so/contract-123"
        )

        self.assertEqual(verified.binding, binding)
        self.assertIsNotNone(replay)
        self.assertEqual(verified.issue_id, "ISS-1")
        self.assertEqual(
            verified.url,
            "https://www.notion.so/contract-123",
        )
        save = next(args for tool, args in self.connector.calls if tool is LinearTool.SAVE_ISSUE)
        self.assertEqual(
            save,
            (("id", "ISS-1"), ("links", ({"title": "Elephant Product Contract", "url": "https://www.notion.so/contract-123"},))),
        )

    def test_different_existing_contract_url_is_semantic_drift_not_append(self) -> None:
        _verified, _replay = self.provider.bind_product_contract(
            self.request,
            ContractBinding("contract-old", "a" * 64),
            "https://www.notion.so/contract-old",
        )
        self.connector.calls.clear()

        result, _replay = self.provider.bind_product_contract(
            self.request,
            ContractBinding("contract-new", "b" * 64),
            "https://www.notion.so/contract-new",
        )

        self.assertIsInstance(result, LinearDrift)
        self.assertEqual(result.kind.value, "approved_contract_changed")
        self.assertNotIn(LinearTool.SAVE_ISSUE, tuple(tool for tool, _ in self.connector.calls))

    def test_contract_url_must_strictly_resolve_the_bound_page_id(self) -> None:
        with self.assertRaises(ValueError):
            self.provider.bind_product_contract(
                self.request,
                ContractBinding("page-1", "a" * 64),
                "https://www.notion.so/page-2",
            )
        self.assertEqual(self.connector.calls, [])

    def test_unresolved_contract_link_append_uses_token_across_fresh_provider(self) -> None:
        self.connector.delay_link_visibility = True
        binding = ContractBinding("contract-123", "a" * 64)

        first, replay = self.provider.bind_product_contract(
            self.request, binding, "https://www.notion.so/contract-123"
        )
        fresh = LinearStoryProvider(self.connector, self.provider._config)
        second, replay = fresh.bind_product_contract(
            self.request,
            binding,
            "https://www.notion.so/contract-123",
            replay=replay,
        )

        saves = [
            args for tool, args in self.connector.calls
            if tool is LinearTool.SAVE_ISSUE and "links" in dict(args)
        ]
        self.assertEqual(len(saves), 1)
        self.assertEqual(first.kind.value, "timed_out_write")
        self.assertEqual(second.kind.value, "timed_out_write")
        self.connector.reveal_delayed_evidence()
        verified, _replay = fresh.bind_product_contract(
            self.request,
            binding,
            "https://www.notion.so/contract-123",
            replay=replay,
        )
        self.assertEqual(verified.binding, binding)
        self.assertEqual(len(saves), 1)


class LinearCheckpointLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        fixture = LinearProductRecapTests()
        fixture.setUp()
        self.request = fixture.request
        self.connector = fixture.connector
        self.uploader = StrictRawUploader(self.connector)
        self.reader = StrictAttachmentContentReader(self.connector)
        self.provider = LinearStoryProvider(
            self.connector,
            fixture.provider._config,
            raw_uploader=self.uploader,
            attachment_reader=self.reader,
        )
        self.snapshot = StorySnapshot(
            key=self.request.key,
            issue_id="ISS-1",
            title=self.request.title,
            human_status=HumanStatus.BACKLOG,
            checkpoint_phase=CheckpointPhase.SHAPING,
        )
        self.binding = ContractBinding("page-1", "a" * 64)
        self.verified_binding, _replay = self.provider.bind_product_contract(
            self.request, self.binding, "https://www.notion.so/page-1"
        )
        self.connector.calls.clear()
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
            self.request, self.snapshot, self.verified_binding, delivery=self.empty_delivery
        )
        second_snapshot = replace(self.snapshot, checkpoint_phase=CheckpointPhase.READY)
        second = self.provider.write_checkpoint(
            self.request, second_snapshot, self.verified_binding, delivery=self.empty_delivery
        )

        self.assertEqual((first.sequence, second.sequence), (1, 2))
        self.assertEqual(second.previous_sha256, first.sha256)
        self.assertEqual(
            tuple(
                row["title"] for row in self.connector.attachments.values()
                if str(row["title"]).startswith("elephant-checkpoint-")
            ),
            (second.filename,),
        )
        tools = tuple(tool for tool, _ in self.connector.calls)
        self.assertEqual(tools.count(LinearTool.PREPARE_ATTACHMENT_UPLOAD), 2)
        self.assertEqual(tools.count(LinearTool.CREATE_ATTACHMENT_FROM_UPLOAD), 2)
        self.assertEqual(tools.count(LinearTool.DELETE_ATTACHMENT), 1)
        self.assertEqual(len(self.uploader.calls), 2)

    def test_finalize_timeout_leaves_context_then_replay_adopts_verified_new_checkpoint(self) -> None:
        self.connector.fail_after_finalize = True
        with self.assertRaisesRegex(TimeoutError, "checkpoint finalize failed") as raised:
            self.provider.write_checkpoint(
                self.request, self.snapshot, self.verified_binding, delivery=self.empty_delivery
            )
        self.assertNotIn("upload.invalid", str(raised.exception))
        self.assertNotIn("opaque-sentinel", str(raised.exception))
        self.assertEqual(
            len([
                row for row in self.connector.attachments.values()
                if str(row["title"]).startswith("elephant-checkpoint-")
            ]),
            1,
        )

        checkpoint = self.provider.write_checkpoint(
            self.request, self.snapshot, self.verified_binding, delivery=self.empty_delivery
        )

        self.assertEqual(checkpoint.sequence, 1)
        self.assertEqual(
            tuple(tool for tool, _ in self.connector.calls).count(LinearTool.CREATE_ATTACHMENT_FROM_UPLOAD),
            1,
        )

    def test_read_stops_for_duplicate_sequence_or_changed_contract_fingerprint(self) -> None:
        checkpoint = self.provider.write_checkpoint(
            self.request, self.snapshot, self.verified_binding, delivery=self.empty_delivery
        )
        original = next(
            row for row in self.connector.attachments.values()
            if str(row["title"]).startswith("elephant-checkpoint-")
        )
        duplicate = deepcopy(original)
        duplicate["id"] = "00000000-0000-0000-0000-999999999999"
        self.connector.attachments[duplicate["id"]] = duplicate

        duplicate_result = self.provider.read_checkpoint(
            self.request, self.snapshot, self.verified_binding
        )
        self.assertEqual(duplicate_result.kind.value, "duplicate_authority")
        del self.connector.attachments[duplicate["id"]]

        changed = self.provider.read_checkpoint(
            self.request,
            self.snapshot,
            replace(self.verified_binding, binding=ContractBinding("page-1", "b" * 64)),
        )
        self.assertEqual(changed.kind.value, "approved_contract_changed")
        self.assertEqual(checkpoint.sequence, 1)

    def test_raw_upload_failure_is_sanitized_and_never_finalized(self) -> None:
        self.uploader.fail = True
        with self.assertRaisesRegex(TimeoutError, "checkpoint raw upload failed") as raised:
            self.provider.write_checkpoint(
                self.request, self.snapshot, self.verified_binding, delivery=self.empty_delivery
            )
        self.assertNotIn("opaque-sentinel", str(raised.exception))
        self.assertFalse(any(
            str(row["title"]).startswith("elephant-checkpoint-")
            for row in self.connector.attachments.values()
        ))
        self.assertNotIn(
            LinearTool.CREATE_ATTACHMENT_FROM_UPLOAD,
            tuple(tool for tool, _ in self.connector.calls),
        )

    def test_checkpoint_requires_full_request_authority_before_prepare(self) -> None:
        for field, value in (
            ("teamId", "changed-team"),
            ("labels", ["product-facing"]),
            ("title", "Changed title"),
            ("projectId", "changed-project"),
            ("parentId", "changed-parent"),
        ):
            with self.subTest(field=field):
                self.setUp()
                self.connector.issue[field] = value
                self.connector.calls.clear()

                result = self.provider.write_checkpoint(
                    self.request,
                    self.snapshot,
                    self.verified_binding,
                    delivery=self.empty_delivery,
                )

                self.assertNotIsInstance(result, Checkpoint)
                self.assertNotIn(
                    LinearTool.PREPARE_ATTACHMENT_UPLOAD,
                    tuple(tool for tool, _ in self.connector.calls),
                )

    def test_concurrent_newer_checkpoint_stops_and_deletes_nothing(self) -> None:
        first = self.provider.write_checkpoint(
            self.request, self.snapshot, self.verified_binding, delivery=self.empty_delivery
        )
        ready = replace(self.snapshot, checkpoint_phase=CheckpointPhase.READY)

        def add_newer(attachment_id: str) -> None:
            ours = Checkpoint.from_bytes(self.connector.attachments[attachment_id]["content"])
            newer = replace(
                ours,
                sequence=ours.sequence + 1,
                previous_sha256=ours.sha256,
                phase=CheckpointPhase.TECHNICAL,
            )
            identifier = "00000000-0000-0000-0000-999999999998"
            self.connector.attachments[identifier] = {
                "id": identifier,
                "title": newer.filename,
                "url": "linear-asset://concurrent-newer",
                "content": newer.canonical_bytes,
            }

        self.connector.after_finalize = add_newer
        self.connector.calls.clear()

        result = self.provider.write_checkpoint(
            self.request, ready, self.verified_binding, delivery=self.empty_delivery
        )

        self.assertIsInstance(result, LinearDrift)
        self.assertEqual(result.kind.value, "duplicate_authority")
        self.assertEqual(first.sequence, 1)
        self.assertNotIn(LinearTool.DELETE_ATTACHMENT, tuple(tool for tool, _ in self.connector.calls))

    def test_cleanup_revalidates_authority_and_deletes_only_captured_prior_id(self) -> None:
        first = self.provider.write_checkpoint(
            self.request, self.snapshot, self.verified_binding, delivery=self.empty_delivery
        )
        prior_id = next(
            identifier for identifier, row in self.connector.attachments.items()
            if row["title"] == first.filename
        )
        ready = replace(self.snapshot, checkpoint_phase=CheckpointPhase.READY)
        self.connector.after_finalize = lambda _identifier: self.connector.issue.__setitem__(
            "labels", ["engineering-only"]
        )
        self.connector.calls.clear()

        result = self.provider.write_checkpoint(
            self.request, ready, self.verified_binding, delivery=self.empty_delivery
        )

        self.assertNotIsInstance(result, Checkpoint)
        deletes = [args for tool, args in self.connector.calls if tool is LinearTool.DELETE_ATTACHMENT]
        self.assertEqual(deletes, [])
        self.assertIn(prior_id, self.connector.attachments)

    def test_checkpoint_rejects_raw_or_changed_contract_binding(self) -> None:
        with self.assertRaises(TypeError):
            self.provider.write_checkpoint(
                self.request,
                self.snapshot,
                ContractBinding("different-page", "b" * 64),
                delivery=self.empty_delivery,
            )
        self.assertNotIn(
            LinearTool.PREPARE_ATTACHMENT_UPLOAD,
            tuple(tool for tool, _ in self.connector.calls),
        )

    def test_checkpoint_chain_rejects_gaps_and_contract_changes(self) -> None:
        first = self.provider.write_checkpoint(
            self.request, self.snapshot, self.verified_binding, delivery=self.empty_delivery
        )
        bad = Checkpoint(
            story_key=first.story_key,
            issue_id=first.issue_id,
            phase=CheckpointPhase.TECHNICAL,
            sequence=3,
            contract=ContractBinding("other-page", "b" * 64),
            delivery=self.empty_delivery,
            previous_sha256=first.sha256,
        )
        identifier = "00000000-0000-0000-0000-999999999997"
        self.connector.attachments[identifier] = {
            "id": identifier,
            "title": bad.filename,
            "url": "linear-asset://bad-chain",
            "content": bad.canonical_bytes,
        }

        result = self.provider.read_checkpoint(
            self.request, self.snapshot, self.verified_binding
        )

        self.assertIsInstance(result, LinearDrift)
        self.assertEqual(result.kind.value, "approved_contract_changed")

    def test_checkpoint_chain_requires_sequence_one_genesis(self) -> None:
        bad = Checkpoint(
            story_key=self.snapshot.key.marker,
            issue_id=self.snapshot.issue_id,
            phase=self.snapshot.checkpoint_phase,
            sequence=3,
            contract=self.binding,
            delivery=self.empty_delivery,
            previous_sha256=None,
        )
        identifier = "00000000-0000-0000-0000-999999999996"
        self.connector.attachments[identifier] = {
            "id": identifier,
            "title": bad.filename,
            "url": "linear-asset://bad-genesis",
            "content": bad.canonical_bytes,
        }

        result = self.provider.read_checkpoint(
            self.request, self.snapshot, self.verified_binding
        )

        self.assertIsInstance(result, LinearDrift)
        self.assertEqual(result.kind.value, "approved_contract_changed")

    def test_attachment_connector_and_decoder_failures_are_sanitized(self) -> None:
        self.provider.write_checkpoint(
            self.request, self.snapshot, self.verified_binding, delivery=self.empty_delivery
        )
        failures = (
            ("connector", RuntimeError("sensitive upload material")),
            ("decoder", RuntimeError("sensitive attachment material")),
        )
        for source, failure in failures:
            with self.subTest(source=source):
                if source == "connector":
                    self.connector.attachment_get_error = failure
                else:
                    self.reader.fail = failure
                with self.assertRaisesRegex(RuntimeError, "checkpoint attachment read failed") as raised:
                    self.provider.read_checkpoint(
                        self.request, self.snapshot, self.verified_binding
                    )
                self.assertNotIn("sensitive", str(raised.exception))


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
            "next": {"comments": [{"id": comment_id, "body": self.connector.comments[comment_id], "quotedText": None}], "hasNextPage": False},
        }

        issue, _replay = self.provider.attach_delivery_evidence(self.request, self.record)

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

        result, _replay = self.provider.attach_delivery_evidence(self.request, self.record)

        self.assertEqual(result.kind.value, "duplicate_authority")
        self.assertNotIn(LinearTool.SAVE_COMMENT, tuple(tool for tool, _ in self.connector.calls))

    def test_github_binding_uses_exact_url_or_id_and_requires_same_issue_identifier(self) -> None:
        _result, _replay = self.provider.attach_delivery_evidence(self.request, self.record)
        self.connector.diff = {
            "id": "diff-1",
            "url": self.record.pull_request_url,
            "issueIdentifier": "ELE-1",
        }
        self.connector.calls.clear()

        diff = self.provider.verify_github_binding(
            self.request,
            self.record.pull_request_url,
            complete_native_diff_inventory(),
        )

        self.assertEqual(diff.issue_identifier, "ELE-1")
        self.assertIn(
            (LinearTool.GET_DIFF, (("urlOrId", self.record.pull_request_url),)),
            self.connector.calls,
        )

    def test_github_binding_classifies_missing_tool_and_configuration_without_git_fallback(self) -> None:
        _result, _replay = self.provider.attach_delivery_evidence(self.request, self.record)
        all_tools = frozenset(tool.value for tool in LinearTool)
        cases = (
            (
                LinearCapabilityInventory(all_tools, all_tools - {LinearTool.GET_DIFF.value}, all_tools, frozenset({NATIVE_GITHUB_DIFF_CAPABILITY})),
                DiagnosticCode.CONNECTOR_CAPABILITY_MISSING,
            ),
            (complete_native_diff_inventory(configured=False), DiagnosticCode.CONFIGURATION_MISSING),
        )
        for inventory, expected in cases:
            with self.subTest(expected=expected):
                self.connector.calls.clear()
                with self.assertRaises(LinearProviderError) as raised:
                    self.provider.verify_github_binding(
                        self.request,
                        self.record.pull_request_url,
                        inventory,
                    )
                self.assertEqual(raised.exception.diagnostic_code, expected)
                self.assertNotIn(LinearTool.GET_DIFF, tuple(tool for tool, _ in self.connector.calls))

    def test_exposed_diff_without_issue_integration_is_configuration_missing(self) -> None:
        _result, _replay = self.provider.attach_delivery_evidence(self.request, self.record)
        self.connector.diff = {
            "id": "diff-1",
            "url": self.record.pull_request_url,
        }

        with self.assertRaises(LinearProviderError) as raised:
            self.provider.verify_github_binding(
                self.request,
                self.record.pull_request_url,
                complete_native_diff_inventory(),
            )

        self.assertEqual(
            raised.exception.diagnostic_code, DiagnosticCode.CONFIGURATION_MISSING
        )

    def test_github_binding_uses_reverified_current_issue_identifier(self) -> None:
        _result, _replay = self.provider.attach_delivery_evidence(self.request, self.record)
        self.connector.diff = {
            "id": "diff-1",
            "url": self.record.pull_request_url,
            "issueIdentifier": "OTHER-99",
        }

        result = self.provider.verify_github_binding(
            self.request,
            self.record.pull_request_url,
            complete_native_diff_inventory(),
        )

        self.assertIsInstance(result, LinearDrift)
        self.assertEqual(result.kind.value, "approved_contract_changed")

    def test_github_capability_diagnostic_is_attributed_to_native_diff(self) -> None:
        _result, _replay = self.provider.attach_delivery_evidence(self.request, self.record)
        with self.assertRaises(LinearProviderError) as raised:
            self.provider.verify_github_binding(
                self.request,
                self.record.pull_request_url,
                complete_native_diff_inventory(configured=False),
            )

        self.assertEqual(raised.exception.capability, NATIVE_GITHUB_DIFF_CAPABILITY)
        self.assertEqual(
            raised.exception.verified_prior_receipts,
            (("issue_identifier", "ELE-1"),),
        )

    def test_human_marker_mentions_and_inline_comments_are_never_owned_or_overwritten(self) -> None:
        marker = f"Elephant delivery evidence: `{self.request.key.marker}`"
        human_id = "00000000-0000-0000-0001-000000000010"
        human_body = f"Please preserve this human discussion mentioning {marker} in prose."
        self.connector.comments[human_id] = human_body

        _result, _replay = self.provider.attach_delivery_evidence(self.request, self.record)

        self.assertEqual(self.connector.comments[human_id], human_body)
        first_save = next(args for tool, args in self.connector.calls if tool is LinearTool.SAVE_COMMENT)
        self.assertEqual(set(dict(first_save)), {"issueId", "body"})

        self.setUp()
        inline_id = "00000000-0000-0000-0001-000000000011"
        inline_body = f"Inline discussion\n\n---\n{marker}"
        self.connector.comment_pages = {
            None: {
                "comments": [{"id": inline_id, "body": inline_body, "quotedText": "anchored text"}],
                "hasNextPage": False,
            }
        }

        _result, _replay = self.provider.attach_delivery_evidence(self.request, self.record)

        save = next(args for tool, args in self.connector.calls if tool is LinearTool.SAVE_COMMENT)
        self.assertNotIn("id", dict(save))

    def test_unresolved_comment_create_never_creates_again_until_readback_resolves(self) -> None:
        self.connector.delay_comment_visibility = True

        first, replay = self.provider.attach_delivery_evidence(self.request, self.record)
        fresh = LinearStoryProvider(self.connector, self.provider._config)
        second, replay = fresh.attach_delivery_evidence(
            self.request, self.record, replay=replay
        )

        saves = [args for tool, args in self.connector.calls if tool is LinearTool.SAVE_COMMENT]
        self.assertEqual(len(saves), 1)
        self.assertEqual(first.kind.value, "timed_out_write")
        self.assertEqual(second.kind.value, "timed_out_write")
        self.connector.reveal_delayed_evidence()
        resumed, _replay = fresh.attach_delivery_evidence(
            self.request, self.record, replay=replay
        )
        self.assertNotIsInstance(resumed, LinearDrift)
        self.assertEqual(
            len([args for tool, args in self.connector.calls if tool is LinearTool.SAVE_COMMENT]),
            1,
        )

    def test_unresolved_append_only_links_are_not_appended_again(self) -> None:
        self.connector.delay_link_visibility = True

        first, replay = self.provider.attach_delivery_evidence(self.request, self.record)
        fresh = LinearStoryProvider(self.connector, self.provider._config)
        second, replay = fresh.attach_delivery_evidence(
            self.request, self.record, replay=replay
        )

        link_saves = [
            args for tool, args in self.connector.calls
            if tool is LinearTool.SAVE_ISSUE and "links" in dict(args)
        ]
        self.assertEqual(len(link_saves), 1)
        self.assertEqual(first.kind.value, "timed_out_write")
        self.assertEqual(second.kind.value, "timed_out_write")
        self.connector.reveal_delayed_evidence()
        resumed, _replay = fresh.attach_delivery_evidence(
            self.request, self.record, replay=replay
        )
        self.assertNotIsInstance(resumed, LinearDrift)


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

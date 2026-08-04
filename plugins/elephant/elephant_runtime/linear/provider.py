"""Replay-safe Linear story lifecycle over the injected connector port."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import re
from urllib.parse import urlsplit

from elephant_runtime.workspace_core import (
    DiagnosticCode,
    DriftKind,
    HumanStatus,
    ProductDisposition,
    can_transition_human_status,
    terminal_status_for_disposition,
)

from .connector import LinearConnector
from .capabilities import (
    NATIVE_GITHUB_DIFF_CAPABILITY,
    LinearCapabilityInventory,
    preflight_story_capabilities,
)
from .checkpoint import (
    AttachmentContentReader,
    Checkpoint,
    CheckpointDelivery,
    DeliveryRecord,
    HostRawByteUploader,
    LinearEvidenceReplay,
    VerifiedContractBinding,
)
from .models import (
    ContractBinding,
    LinearAuthorityMissing,
    LinearDrift,
    LinearIssue,
    LinearLabel,
    LinearProviderError,
    LinearTool,
    StoryCreateRequest,
    StoryKey,
    StorySnapshot,
)
from .normalize import (
    normalize_comments,
    normalize_diff,
    normalize_issue,
    normalize_issue_statuses,
    normalize_issues,
    parse_story_marker,
)


_STATUS_TYPES = {
    HumanStatus.BACKLOG: "backlog",
    HumanStatus.SHAPING: "unstarted",
    HumanStatus.READY: "unstarted",
    HumanStatus.IN_PROGRESS: "started",
    HumanStatus.DONE: "completed",
    HumanStatus.CANCELED: "canceled",
}
_ADD_RELATIONS = {
    "blockedBy": ("blocked_by", "blocks"),
    "blocks": ("blocks", "blocked_by"),
    "relatedTo": ("related_to", "related_to"),
    "duplicateOf": ("duplicate_of", None),
}
_REMOVE_RELATIONS = {
    "blockedBy": ("removeBlockedBy", "blocked_by", "blocks"),
    "blocks": ("removeBlocks", "blocks", "blocked_by"),
    "relatedTo": ("removeRelatedTo", "related_to", "related_to"),
}
_CONTRACT_TITLE = "Elephant Product Contract"
_DELIVERY_LINKS = (
    ("Elephant Delivery Branch", "branch_url"),
    ("Elephant Pull Request", "pull_request_url"),
    ("Elephant Verification", "verification_url"),
)
_CHECKPOINT_TITLE = re.compile(
    r"elephant-checkpoint-(?P<story>[0-9a-f]{64})-(?P<sequence>[1-9][0-9]*)\.json\Z"
)


@dataclass(frozen=True)
class LinearStoryProviderConfig:
    team_id: str
    statuses: tuple[tuple[HumanStatus, str], ...]
    label_inventory: tuple[LinearLabel, ...]
    product_group_label_ids: frozenset[str]
    kind_group_label_ids: frozenset[str]
    product_facing_kind_label_id: str
    engineering_only_kind_label_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.team_id, str) or not self.team_id.strip():
            raise ValueError("team_id: expected nonblank string")
        if not isinstance(self.statuses, tuple) or {status for status, _ in self.statuses} != set(HumanStatus) or len(self.statuses) != len(HumanStatus):
            raise ValueError("statuses: expected every HumanStatus exactly once")
        if not all(isinstance(status, HumanStatus) and isinstance(identifier, str) and identifier.strip() for status, identifier in self.statuses):
            raise TypeError("statuses: expected (HumanStatus, nonblank ID) tuples")
        if not isinstance(self.label_inventory, tuple) or not all(isinstance(label, LinearLabel) for label in self.label_inventory):
            raise TypeError("label_inventory: expected LinearLabel tuple")
        ids = {label.id for label in self.label_inventory}
        if len(ids) != len(self.label_inventory):
            raise ValueError("label_inventory: duplicate opaque ID")
        for group_name in ("product_group_label_ids", "kind_group_label_ids"):
            group = getattr(self, group_name)
            if not isinstance(group, frozenset) or not group or not group <= ids:
                raise ValueError(f"{group_name}: expected nonempty configured label IDs")
        if (
            self.product_facing_kind_label_id not in self.kind_group_label_ids
            or self.engineering_only_kind_label_id not in self.kind_group_label_ids
            or self.product_facing_kind_label_id == self.engineering_only_kind_label_id
        ):
            raise ValueError("kind authority: expected distinct configured Kind labels")

    @property
    def status_ids(self) -> dict[HumanStatus, str]:
        return dict(self.statuses)


class LinearStoryProvider:
    def __init__(
        self,
        connector: LinearConnector,
        config: LinearStoryProviderConfig,
        *,
        raw_uploader: HostRawByteUploader | None = None,
        attachment_reader: AttachmentContentReader | None = None,
    ) -> None:
        if not isinstance(config, LinearStoryProviderConfig):
            raise TypeError("config: expected LinearStoryProviderConfig")
        self._connector = connector
        self._config = config
        self._raw_uploader = raw_uploader
        self._attachment_reader = attachment_reader

    def create_story(self, request: StoryCreateRequest) -> LinearIssue | LinearDrift:
        self._validate_request(request)
        matches = self._lookup(request.key)
        if len(matches) > 1:
            return _duplicate_authority()
        if matches:
            return self._read_and_verify(matches[0].id, request)
        state_id = self._verified_status_id(request.human_status)
        try:
            receipt = self._connector.call(LinearTool.SAVE_ISSUE, self._create_arguments(request, state_id))
        except Exception:
            return self._resume_create(request)
        if not isinstance(receipt, Mapping) or not isinstance(receipt.get("id"), str) or not receipt["id"].strip():
            raise ValueError("create receipt: expected issue ID")
        try:
            created = self._read_and_verify(receipt["id"], request)
        except Exception:
            return self._resume_create(request)
        if not isinstance(created, LinearIssue):
            return created
        matches = self._lookup(request.key)
        if len(matches) != 1 or matches[0].id != created.id:
            return _duplicate_authority() if len(matches) > 1 else LinearDrift(DriftKind.TIMED_OUT_WRITE, "create_lookup")
        return created

    def write_product_recap(
        self,
        request: StoryCreateRequest,
        *,
        problem: str,
        outcome: str,
        acceptance: tuple[str, ...],
        contract_url: str | None = None,
        behavior_preservation: str | None = None,
    ) -> LinearIssue | LinearAuthorityMissing | LinearDrift:
        desired = _product_recap_description(
            request,
            problem=problem,
            outcome=outcome,
            acceptance=acceptance,
            contract_url=contract_url,
            behavior_preservation=behavior_preservation,
        )
        current = self._read_for_operation(request, exact_body=False)
        if not isinstance(current, LinearIssue):
            return current
        if current.description == desired:
            return current
        try:
            self._connector.call(
                LinearTool.SAVE_ISSUE,
                (("id", current.id), ("description", desired)),
            )
        except Exception:
            resumed = self._read_for_operation(request, exact_body=False)
            if isinstance(resumed, LinearIssue) and resumed.description == desired:
                return resumed
            raise
        return self._read_and_verify(
            current.id,
            request,
            expected_description=desired,
        )

    def bind_product_contract(
        self,
        request: StoryCreateRequest,
        binding: ContractBinding,
        contract_url: str,
        *,
        replay: LinearEvidenceReplay | None = None,
    ) -> tuple[
        VerifiedContractBinding | LinearAuthorityMissing | LinearDrift,
        LinearEvidenceReplay,
    ]:
        if not isinstance(binding, ContractBinding):
            raise TypeError("binding: expected ContractBinding")
        _verify_notion_page_url(contract_url, binding.contract_id)
        replay_value = _replay_value(
            replay, request.key.marker, "bind_product_contract"
        )
        current = self._read_for_operation(request, exact_body=False)
        if not isinstance(current, LinearIssue):
            return current, replay_value
        observed = _one_titled_attachment(current, _CONTRACT_TITLE)
        if isinstance(observed, LinearDrift):
            return observed, replay_value
        if observed is not None:
            if observed.url != contract_url:
                return (
                    LinearDrift(
                        DriftKind.APPROVED_CONTRACT_CHANGED,
                        "product_contract_url",
                    ),
                    replay_value,
                )
            verified = VerifiedContractBinding(
                binding=binding,
                url=contract_url,
                issue_id=current.id,
                attachment_id=observed.id,
            )
            return verified, replace(
                replay_value,
                prior_attachment_ids=tuple(
                    item.id for item in current.attachments or ()
                ),
                pending_links=(),
            )
        desired_link = ((_CONTRACT_TITLE, contract_url),)
        if replay_value.pending_links:
            if replay_value.pending_links != desired_link:
                raise ValueError("replay: pending contract link changed")
            return (
                LinearDrift(DriftKind.TIMED_OUT_WRITE, "product_contract_readback"),
                replay_value,
            )
        link = {"title": _CONTRACT_TITLE, "url": contract_url}
        pending = replace(
            replay_value,
            prior_attachment_ids=tuple(item.id for item in current.attachments or ()),
            pending_links=desired_link,
        )
        try:
            self._connector.call(
                LinearTool.SAVE_ISSUE,
                (("id", current.id), ("links", (link,))),
            )
        except Exception:
            resumed = self._read_for_operation(request, exact_body=False)
            if isinstance(resumed, LinearIssue):
                observed = _one_titled_attachment(resumed, _CONTRACT_TITLE)
                if observed is not None and not isinstance(observed, LinearDrift) and observed.url == contract_url:
                    return (
                        VerifiedContractBinding(
                            binding, contract_url, resumed.id, observed.id
                        ),
                        replace(
                            pending,
                            prior_attachment_ids=tuple(
                                item.id for item in resumed.attachments or ()
                            ),
                            pending_links=(),
                        ),
                    )
            return LinearDrift(DriftKind.TIMED_OUT_WRITE, "product_contract_readback"), pending
        verified = self._read_and_verify(current.id, request, exact_body=False)
        if not isinstance(verified, LinearIssue):
            return verified, pending
        observed = _one_titled_attachment(verified, _CONTRACT_TITLE)
        if observed is None or isinstance(observed, LinearDrift) or observed.url != contract_url:
            return LinearDrift(DriftKind.TIMED_OUT_WRITE, "product_contract_readback"), pending
        return (
            VerifiedContractBinding(binding, contract_url, verified.id, observed.id),
            replace(
                pending,
                prior_attachment_ids=tuple(
                    item.id for item in verified.attachments or ()
                ),
                pending_links=(),
            ),
        )

    def read_checkpoint(
        self,
        request: StoryCreateRequest,
        snapshot: StorySnapshot,
        contract: VerifiedContractBinding,
    ) -> Checkpoint | None | LinearDrift:
        issue = self._verify_checkpoint_authority(request, snapshot, contract)
        if not isinstance(issue, LinearIssue):
            return issue
        checkpoints = self._read_checkpoints(snapshot, issue)
        if isinstance(checkpoints, LinearDrift):
            return checkpoints
        if not checkpoints:
            return None
        current = checkpoints[-1][0]
        if current.contract != contract.binding:
            return LinearDrift(DriftKind.APPROVED_CONTRACT_CHANGED, "checkpoint_contract")
        if current.phase is not snapshot.checkpoint_phase:
            return LinearDrift(DriftKind.VERIFIED_CHECKPOINT_LAG, "checkpoint_phase")
        return current

    def write_checkpoint(
        self,
        request: StoryCreateRequest,
        snapshot: StorySnapshot,
        contract: VerifiedContractBinding,
        *,
        delivery: CheckpointDelivery,
    ) -> Checkpoint | LinearDrift:
        if not isinstance(snapshot, StorySnapshot):
            raise TypeError("snapshot: expected StorySnapshot")
        if not isinstance(contract, VerifiedContractBinding):
            raise TypeError("contract: expected VerifiedContractBinding")
        if not isinstance(delivery, CheckpointDelivery):
            raise TypeError("delivery: expected CheckpointDelivery")
        issue = self._verify_checkpoint_authority(request, snapshot, contract)
        if not isinstance(issue, LinearIssue):
            return issue
        checkpoints = self._read_checkpoints(snapshot, issue)
        if isinstance(checkpoints, LinearDrift):
            return checkpoints
        prior_attachment_ids = _checkpoint_attachment_ids(issue, snapshot)
        current = checkpoints[-1][0] if checkpoints else None
        if current is not None and current.contract != contract.binding:
            return LinearDrift(DriftKind.APPROVED_CONTRACT_CHANGED, "checkpoint_contract")
        if (
            current is not None
            and current.phase is snapshot.checkpoint_phase
            and current.delivery == delivery
        ):
            return current
        desired = Checkpoint(
            story_key=snapshot.key.marker,
            issue_id=snapshot.issue_id,
            phase=snapshot.checkpoint_phase,
            sequence=1 if current is None else current.sequence + 1,
            contract=contract.binding,
            delivery=delivery,
            previous_sha256=None if current is None else current.sha256,
        )
        if self._raw_uploader is None:
            raise RuntimeError("checkpoint raw uploader is not configured")
        try:
            prepared = self._connector.call(
                LinearTool.PREPARE_ATTACHMENT_UPLOAD,
                (
                    ("issue", snapshot.issue_id),
                    ("filename", desired.filename),
                    ("contentType", "application/json"),
                    ("size", len(desired.canonical_bytes)),
                    ("title", desired.filename),
                ),
            )
            asset_url, upload_url, headers = _prepared_upload(prepared)
        except Exception:
            raise RuntimeError("checkpoint upload preparation failed") from None
        try:
            self._raw_uploader.put(upload_url, headers, desired.canonical_bytes)
        except Exception:
            raise TimeoutError("checkpoint raw upload failed") from None
        try:
            receipt = self._connector.call(
                LinearTool.CREATE_ATTACHMENT_FROM_UPLOAD,
                (
                    ("assetUrl", asset_url),
                    ("issue", snapshot.issue_id),
                    ("title", desired.filename),
                ),
            )
        except Exception:
            raise TimeoutError("checkpoint finalize failed") from None
        if not isinstance(receipt, Mapping) or not isinstance(receipt.get("id"), str) or not receipt["id"].strip():
            raise ValueError("checkpoint finalize receipt: expected attachment ID")
        verified_issue = self._verify_checkpoint_authority(request, snapshot, contract)
        if not isinstance(verified_issue, LinearIssue):
            return verified_issue
        verified = self._read_checkpoints(snapshot, verified_issue)
        if isinstance(verified, LinearDrift):
            return verified
        observed_ids = _checkpoint_attachment_ids(verified_issue, snapshot)
        if observed_ids != prior_attachment_ids | {receipt["id"]}:
            return LinearDrift(DriftKind.DUPLICATE_AUTHORITY, "concurrent_checkpoint")
        exact = tuple(
            item for item in verified
            if item[0] == desired and item[1] == receipt["id"]
        )
        if len(exact) != 1:
            return LinearDrift(DriftKind.TIMED_OUT_WRITE, "checkpoint_readback")
        if current is not None:
            before_cleanup = self._verify_checkpoint_authority(request, snapshot, contract)
            if not isinstance(before_cleanup, LinearIssue):
                return before_cleanup
            before_values = self._read_checkpoints(snapshot, before_cleanup)
            if isinstance(before_values, LinearDrift):
                return before_values
            if (
                _checkpoint_attachment_ids(before_cleanup, snapshot) != observed_ids
                or before_values != verified
            ):
                return LinearDrift(DriftKind.DUPLICATE_AUTHORITY, "concurrent_checkpoint")
            self._delete_captured_checkpoint(
                request, snapshot, contract, current_attachment_id=checkpoints[-1][1]
            )
        return desired

    def attach_delivery_evidence(
        self,
        request: StoryCreateRequest,
        record: DeliveryRecord,
        *,
        replay: LinearEvidenceReplay | None = None,
    ) -> tuple[
        LinearIssue | LinearAuthorityMissing | LinearDrift,
        LinearEvidenceReplay,
    ]:
        if not isinstance(record, DeliveryRecord):
            raise TypeError("record: expected DeliveryRecord")
        replay_value = _replay_value(
            replay, request.key.marker, "attach_delivery_evidence"
        )
        current = self._read_for_operation(request, exact_body=False)
        if not isinstance(current, LinearIssue):
            return current, replay_value
        marker = f"Elephant delivery evidence: `{request.key.marker}`"
        comments = self._delivery_comments(current.id, marker)
        if len(comments) > 1:
            return _duplicate_authority(), replay_value
        body = _delivery_comment(record, marker)
        if replay_value.comment_create_pending:
            matching = tuple(
                comment for comment in comments
                if comment.body == body
                and (
                    replay_value.pending_comment_id is None
                    or comment.id == replay_value.pending_comment_id
                )
                and comment.id not in replay_value.prior_comment_ids
            )
            if len(matching) != 1:
                return (
                    LinearDrift(DriftKind.TIMED_OUT_WRITE, "delivery_comment_readback"),
                    replay_value,
                )
            replay_value = replace(
                replay_value,
                comment_create_pending=False,
                pending_comment_id=None,
            )
            comments = matching
        if comments and comments[0].body != body:
            arguments = (("id", comments[0].id), ("body", body))
        elif comments:
            arguments = None
        else:
            replay_value = replace(
                replay_value,
                prior_comment_ids=tuple(
                    comment.id for comment in self._all_comments(current.id)
                ),
                comment_create_pending=True,
            )
            arguments = (("issueId", current.id), ("body", body))
        if arguments is not None:
            try:
                receipt = self._connector.call(LinearTool.SAVE_COMMENT, arguments)
            except Exception:
                resumed = self._delivery_comments(current.id, marker)
                if len(resumed) != 1 or resumed[0].body != body:
                    return (
                        LinearDrift(DriftKind.TIMED_OUT_WRITE, "delivery_comment_readback"),
                        replay_value,
                    )
            else:
                if not isinstance(receipt, Mapping) or not isinstance(receipt.get("id"), str):
                    raise ValueError("comment receipt: expected comment ID")
                if replay_value.comment_create_pending:
                    replay_value = replace(
                        replay_value, pending_comment_id=receipt["id"]
                    )
                resumed = self._delivery_comments(current.id, marker)
                if len(resumed) != 1 or resumed[0].id != receipt["id"] or resumed[0].body != body:
                    return (
                        LinearDrift(DriftKind.TIMED_OUT_WRITE, "delivery_comment_readback"),
                        replay_value,
                    )
            replay_value = replace(
                replay_value,
                comment_create_pending=False,
                pending_comment_id=None,
            )
        links = tuple(
            {"title": title, "url": getattr(record, field)}
            for title, field in _DELIVERY_LINKS
        )
        link_result, replay_value = self._append_exact_links(
            request, current, links, replay_value
        )
        return link_result, replay_value

    def verify_github_binding(
        self,
        request: StoryCreateRequest,
        pull_request_url: str,
        inventory: LinearCapabilityInventory,
    ):
        if not isinstance(pull_request_url, str) or not pull_request_url.startswith("https://"):
            raise ValueError("pull_request_url: expected HTTPS URL")
        current = self._read_for_operation(request, exact_body=False)
        if not isinstance(current, LinearIssue):
            return current
        if current.identifier is None:
            raise ValueError("current issue: expected Linear identifier")
        attachment = _one_titled_attachment(current, "Elephant Pull Request")
        if isinstance(attachment, LinearDrift):
            return attachment
        if attachment is None or attachment.url != pull_request_url:
            return LinearDrift(DriftKind.APPROVED_CONTRACT_CHANGED, "pull_request_attachment")
        preflight = preflight_story_capabilities(
            inventory, capabilities=(NATIVE_GITHUB_DIFF_CAPABILITY,)
        )
        if preflight.diagnostics:
            raise self._github_diagnostic(
                request, current.identifier, preflight.diagnostics[0].code
            )
        try:
            diff = normalize_diff(
                self._connector.call(
                    LinearTool.GET_DIFF, (("urlOrId", pull_request_url),)
                )
            )
        except (LookupError, KeyError, ValueError, TypeError):
            raise self._github_diagnostic(request, current.identifier, DiagnosticCode.CONFIGURATION_MISSING) from None
        if diff.issue_identifier is None:
            raise self._github_diagnostic(
                request, current.identifier, DiagnosticCode.CONFIGURATION_MISSING
            )
        if diff.url != pull_request_url or diff.issue_identifier != current.identifier:
            return LinearDrift(DriftKind.APPROVED_CONTRACT_CHANGED, "github_diff_binding")
        return diff

    def read_story(self, key: StoryKey, *, request: StoryCreateRequest | None = None) -> LinearIssue | LinearAuthorityMissing | LinearDrift:
        if not isinstance(key, StoryKey):
            raise TypeError("key: expected StoryKey")
        if request is not None:
            self._validate_request(request)
            if request.key != key:
                raise ValueError("request.key: must match key")
        matches = self._lookup(key)
        if not matches:
            return LinearAuthorityMissing(key.marker)
        if len(matches) > 1:
            return _duplicate_authority()
        return self._read_and_verify(matches[0].id, request)

    def update_human_status(self, request: StoryCreateRequest, target: HumanStatus, *, expected_description: str | None = None) -> LinearIssue | LinearDrift:
        self._validate_request(request)
        if not isinstance(target, HumanStatus):
            raise TypeError("target: expected HumanStatus")
        current = self._read_for_operation(request, expected_description)
        if not isinstance(current, LinearIssue):
            return current
        if not can_transition_human_status(request.human_status, target):
            raise ValueError("human status transition is not permitted")
        updated = replace(request, human_status=target)
        state_id = self._verified_status_id(target)
        try:
            self._connector.call(LinearTool.SAVE_ISSUE, (("id", current.id), ("state", state_id)))
        except Exception:
            resumed = self._read_for_operation(updated, expected_description)
            if isinstance(resumed, LinearIssue):
                return resumed
            raise
        return self._read_and_verify(current.id, updated, expected_description=expected_description)

    def create_child_story(self, parent_request: StoryCreateRequest, child_request: StoryCreateRequest) -> LinearIssue | LinearDrift:
        parent = self.read_story(parent_request.key, request=parent_request)
        if not isinstance(parent, LinearIssue):
            return parent
        if child_request.key == parent_request.key or child_request.parent_id != parent.id:
            raise ValueError("child request: requires distinct key and verified parent")
        child = self.create_story(child_request)
        if not isinstance(child, LinearIssue):
            return child
        return child if child.parent_id == parent.id else LinearDrift(DriftKind.PRODUCT_ASSIGNMENT_CHANGED, "parent_id")

    def link_relation(self, request: StoryCreateRequest, target_issue_id: str, relation: str) -> LinearIssue | LinearDrift:
        if relation not in _ADD_RELATIONS:
            raise ValueError("relation: expected connector relation field")
        source = self._read_for_operation(request)
        if not isinstance(source, LinearIssue):
            return source
        target = self._read_detail(target_issue_id)
        source_field, reciprocal_field = _ADD_RELATIONS[relation]
        if _has_relation(source, source_field, target_issue_id):
            _verify_relation_target(target, reciprocal_field, source.id)
            return source
        value: object = target_issue_id if relation == "duplicateOf" else (target_issue_id,)
        return self._complete_relation_write(request, source, target_issue_id, relation, value, source_field, reciprocal_field, present=True)

    def remove_relation(self, request: StoryCreateRequest, target_issue_id: str, relation: str) -> LinearIssue | LinearDrift:
        if relation not in _REMOVE_RELATIONS:
            raise ValueError("relation: duplicateOf is one-way and cannot be removed by this connector")
        source = self._read_for_operation(request)
        if not isinstance(source, LinearIssue):
            return source
        target = self._read_detail(target_issue_id)
        field, source_field, reciprocal_field = _REMOVE_RELATIONS[relation]
        if not _has_relation(source, source_field, target_issue_id):
            raise ValueError("relation removal: exact verified relation is absent")
        _verify_relation_target(target, reciprocal_field, source.id)
        return self._complete_relation_write(request, source, target_issue_id, field, (target_issue_id,), source_field, reciprocal_field, present=False)

    def apply_disposition(self, request: StoryCreateRequest, disposition: ProductDisposition, *, child_requests: tuple[StoryCreateRequest, ...] = (), summary: str | None = None) -> LinearIssue | LinearDrift:
        if not isinstance(disposition, ProductDisposition):
            raise TypeError("disposition: expected ProductDisposition")
        current = self._read_for_operation(request, exact_body=False)
        if not isinstance(current, LinearIssue):
            return current
        if disposition is ProductDisposition.SPLIT:
            if not child_requests:
                raise ValueError("split: expected explicitly keyed child requests")
            for child in child_requests:
                created = self.create_child_story(request, child)
                if not isinstance(created, LinearIssue):
                    return created
            return self.update_human_status(request, terminal_status_for_disposition(disposition))
        if disposition is ProductDisposition.APPROVED:
            return self.update_human_status(request, terminal_status_for_disposition(disposition))
        if not isinstance(summary, str) or not summary.strip() or "\n" in summary:
            raise ValueError("disposition summary: expected one concise nonblank line")
        label = "Reconsideration" if disposition is ProductDisposition.DEFERRED else "Disposition"
        canonical = _story_description(request)
        desired = _disposition_body(canonical, label, summary.strip())
        if desired is None or current.description not in {canonical, desired}:
            return LinearDrift(DriftKind.APPROVED_CONTRACT_CHANGED, "disposition_summary")
        if current.description != desired:
            try:
                self._connector.call(LinearTool.SAVE_ISSUE, (("id", current.id), ("description", desired)))
            except Exception:
                resumed = self._read_for_operation(request, exact_body=False)
                if not isinstance(resumed, LinearIssue) or resumed.description != desired:
                    raise
            else:
                verified = self._read_and_verify(current.id, request, expected_description=desired)
                if not isinstance(verified, LinearIssue):
                    return verified
        return self.update_human_status(request, terminal_status_for_disposition(disposition), expected_description=desired)

    def _resume_create(self, request: StoryCreateRequest) -> LinearIssue | LinearDrift:
        matches = self._lookup(request.key)
        if len(matches) > 1:
            return _duplicate_authority()
        if len(matches) == 1:
            return self._read_and_verify(matches[0].id, request)
        raise TimeoutError("create did not yield an authoritative read-back")

    def _lookup(self, key: StoryKey) -> tuple[LinearIssue, ...]:
        cursor = None
        seen: tuple[str, ...] = ()
        found: list[LinearIssue] = []
        while True:
            arguments: tuple[tuple[str, object], ...] = (("team", self._config.team_id), ("query", key.marker))
            if cursor is not None:
                arguments += (("cursor", cursor),)
            raw = self._connector.call(LinearTool.LIST_ISSUES, arguments)
            try:
                page = normalize_issues(raw, seen_cursors=seen)
                values = page.values
                next_cursor = page.next_cursor
            except ValueError as error:
                if "duplicate stable marker" not in str(error) or not isinstance(raw, Mapping) or not isinstance(raw.get("issues"), list):
                    raise
                values = tuple(normalize_issue(item) for item in raw["issues"])
                has_next = raw.get("hasNextPage")
                next_cursor = raw.get("cursor")
                if has_next is not False or next_cursor is not None:
                    raise ValueError("duplicate authority page must be terminal")
            found.extend(issue for issue in values if isinstance(issue, LinearIssue) and issue.team_id == self._config.team_id and (marker := parse_story_marker(issue.description)) is not None and marker[0] == key.marker)
            if next_cursor is None:
                return tuple(found)
            seen += (next_cursor,)
            cursor = next_cursor

    def _read_for_operation(self, request: StoryCreateRequest, expected_description: str | None = None, *, exact_body: bool = True) -> LinearIssue | LinearAuthorityMissing | LinearDrift:
        self._validate_request(request)
        matches = self._lookup(request.key)
        if not matches:
            return LinearAuthorityMissing(request.key.marker)
        if len(matches) > 1:
            return _duplicate_authority()
        return self._read_and_verify(matches[0].id, request, expected_description=expected_description, exact_body=exact_body)

    def _read_and_verify(self, issue_id: str, request: StoryCreateRequest | None, *, expected_description: str | None = None, exact_body: bool = True) -> LinearIssue | LinearDrift:
        issue = self._read_detail(issue_id)
        if request is None:
            return issue
        expected = _story_description(request) if expected_description is None else expected_description
        if issue.team_id != request.team_id or issue.title != request.title or issue.priority is None or issue.priority[0] != request.priority or issue.project_id != request.project_id or issue.parent_id != request.parent_id:
            return LinearDrift(DriftKind.PRODUCT_ASSIGNMENT_CHANGED, "story_fields")
        marker = parse_story_marker(issue.description)
        if marker is None or marker[0] != request.key.marker:
            return LinearDrift(DriftKind.APPROVED_CONTRACT_CHANGED, "story_key")
        if exact_body and issue.description != expected:
            return LinearDrift(DriftKind.APPROVED_CONTRACT_CHANGED, "canonical_body")
        if issue.status_id != self._config.status_ids[request.human_status] or issue.status_name != request.human_status.value or issue.status_type != _STATUS_TYPES[request.human_status]:
            return LinearDrift(DriftKind.HUMAN_STATUS_ADVANCED, "status")
        names = {label.id: label.name for label in self._config.label_inventory}
        if frozenset(issue.labels) != frozenset(names[label] for label in self._label_ids(request)):
            return LinearDrift(DriftKind.PRODUCT_ASSIGNMENT_CHANGED, "label_assignment")
        return issue

    def _read_detail(self, issue_id: str) -> LinearIssue:
        if not isinstance(issue_id, str) or not issue_id.strip():
            raise ValueError("issue_id: expected nonblank string")
        issue = normalize_issue(self._connector.call(LinearTool.GET_ISSUE, (("id", issue_id), ("includeRelations", True))), include_relations=True)
        if issue.id != issue_id:
            raise ValueError("read-back issue ID does not match requested issue")
        return issue

    def _verify_checkpoint_authority(
        self,
        request: StoryCreateRequest,
        snapshot: StorySnapshot,
        contract: VerifiedContractBinding,
    ) -> LinearIssue | LinearAuthorityMissing | LinearDrift:
        if not isinstance(snapshot, StorySnapshot):
            raise TypeError("snapshot: expected StorySnapshot")
        if not isinstance(contract, VerifiedContractBinding):
            raise TypeError("contract: expected VerifiedContractBinding")
        if (
            snapshot.key != request.key
            or snapshot.issue_id != contract.issue_id
            or snapshot.title != request.title
            or snapshot.human_status is not request.human_status
        ):
            return LinearDrift(
                DriftKind.APPROVED_CONTRACT_CHANGED, "checkpoint_story_identity"
            )
        issue = self._read_for_operation(request, exact_body=False)
        if not isinstance(issue, LinearIssue):
            return issue
        if issue.id != snapshot.issue_id:
            return LinearDrift(
                DriftKind.APPROVED_CONTRACT_CHANGED, "checkpoint_story_identity"
            )
        observed = _one_titled_attachment(issue, _CONTRACT_TITLE)
        if (
            observed is None
            or isinstance(observed, LinearDrift)
            or observed.id != contract.attachment_id
            or observed.url != contract.url
        ):
            return LinearDrift(
                DriftKind.APPROVED_CONTRACT_CHANGED, "checkpoint_contract_binding"
            )
        try:
            _verify_notion_page_url(contract.url, contract.binding.contract_id)
        except ValueError:
            return LinearDrift(
                DriftKind.APPROVED_CONTRACT_CHANGED, "checkpoint_contract_binding"
            )
        return issue

    def _read_checkpoints(
        self, snapshot: StorySnapshot, issue: LinearIssue
    ) -> tuple[tuple[Checkpoint, str], ...] | LinearDrift:
        if issue.attachments is None:
            raise ValueError("checkpoint read requires issue attachments")
        if self._attachment_reader is None:
            raise RuntimeError("checkpoint attachment reader is not configured")
        story_digest = snapshot.key.marker.rsplit("/", 1)[1]
        values: list[tuple[Checkpoint, str]] = []
        for attachment in issue.attachments:
            title = _CHECKPOINT_TITLE.fullmatch(attachment.title)
            if title is None or title.group("story") != story_digest:
                continue
            try:
                response = self._connector.call(
                    LinearTool.GET_ATTACHMENT, (("id", attachment.id),)
                )
                raw = self._attachment_reader.read(
                    response, attachment_id=attachment.id
                )
                checkpoint = Checkpoint.from_bytes(raw)
            except Exception:
                raise RuntimeError("checkpoint attachment read failed") from None
            checkpoint.verify_identity(snapshot)
            if (
                checkpoint.filename != attachment.title
                or checkpoint.sequence != int(title.group("sequence"))
            ):
                raise ValueError("checkpoint attachment title does not match content")
            values.append((checkpoint, attachment.id))
        values.sort(key=lambda item: item[0].sequence)
        sequences = tuple(item[0].sequence for item in values)
        if len(set(sequences)) != len(sequences):
            return _duplicate_authority()
        if values and values[0][0].sequence == 1 and values[0][0].previous_sha256 is not None:
            return LinearDrift(DriftKind.APPROVED_CONTRACT_CHANGED, "checkpoint_chain")
        if len({item[0].contract for item in values}) > 1:
            return LinearDrift(DriftKind.APPROVED_CONTRACT_CHANGED, "checkpoint_chain")
        for prior, newer in zip(values, values[1:]):
            if (
                newer[0].sequence != prior[0].sequence + 1
                or newer[0].previous_sha256 != prior[0].sha256
            ):
                return LinearDrift(DriftKind.APPROVED_CONTRACT_CHANGED, "checkpoint_chain")
        return tuple(values)

    def _delete_captured_checkpoint(
        self,
        request: StoryCreateRequest,
        snapshot: StorySnapshot,
        contract: VerifiedContractBinding,
        *,
        current_attachment_id: str,
    ) -> None:
        try:
            self._connector.call(
                LinearTool.DELETE_ATTACHMENT, (("id", current_attachment_id),)
            )
        except Exception:
            issue = self._verify_checkpoint_authority(request, snapshot, contract)
            if (
                isinstance(issue, LinearIssue)
                and issue.attachments is not None
                and all(item.id != current_attachment_id for item in issue.attachments)
            ):
                return
            raise TimeoutError("checkpoint attachment cleanup failed") from None
        issue = self._verify_checkpoint_authority(request, snapshot, contract)
        if not isinstance(issue, LinearIssue):
            raise TimeoutError("checkpoint attachment cleanup failed")
        if issue.attachments is None or any(
            item.id == current_attachment_id for item in issue.attachments
        ):
            raise TimeoutError("checkpoint attachment cleanup failed")

    def _all_comments(self, issue_id: str):
        cursor = None
        seen: tuple[str, ...] = ()
        found = []
        while True:
            arguments: tuple[tuple[str, object], ...] = (("issueId", issue_id),)
            if cursor is not None:
                arguments += (("cursor", cursor),)
            page = normalize_comments(
                self._connector.call(LinearTool.LIST_COMMENTS, arguments),
                seen_cursors=seen,
            )
            found.extend(page.values)
            if page.next_cursor is None:
                return tuple(found)
            seen += (page.next_cursor,)
            cursor = page.next_cursor

    def _delivery_comments(self, issue_id: str, marker: str):
        return tuple(
            comment
            for comment in self._all_comments(issue_id)
            if comment.quoted_text is None
            and _parse_delivery_footer(comment.body) == marker
        )

    def _append_exact_links(
        self,
        request: StoryCreateRequest,
        current: LinearIssue,
        links: tuple[dict[str, str], ...],
        replay: LinearEvidenceReplay,
    ) -> tuple[LinearIssue | LinearDrift, LinearEvidenceReplay]:
        missing: list[dict[str, str]] = []
        for link in links:
            observed = _one_titled_attachment(current, link["title"])
            if isinstance(observed, LinearDrift):
                return observed, replay
            if observed is None:
                missing.append(link)
            elif observed.url != link["url"]:
                return LinearDrift(DriftKind.APPROVED_CONTRACT_CHANGED, "delivery_link_url"), replay
        desired_pending = tuple((link["title"], link["url"]) for link in missing)
        if replay.pending_links:
            requested = tuple(
                (link["title"], link["url"])
                for link in links
                if link["title"] in {title for title, _ in replay.pending_links}
            )
            if requested != replay.pending_links:
                raise ValueError("replay: pending delivery links changed")
            for title, url in replay.pending_links:
                observed = _one_titled_attachment(current, title)
                if isinstance(observed, LinearDrift):
                    return observed, replay
                if observed is None:
                    return LinearDrift(DriftKind.TIMED_OUT_WRITE, "delivery_link_readback"), replay
                if observed.url != url:
                    return LinearDrift(DriftKind.APPROVED_CONTRACT_CHANGED, "delivery_link_url"), replay
            replay = replace(replay, pending_links=())
            missing = []
        if missing:
            replay = replace(
                replay,
                prior_attachment_ids=tuple(
                    item.id for item in current.attachments or ()
                ),
                pending_links=desired_pending,
            )
            try:
                self._connector.call(
                    LinearTool.SAVE_ISSUE,
                    (("id", current.id), ("links", tuple(missing))),
                )
            except Exception:
                verified = self._read_for_operation(request, exact_body=False)
                if not isinstance(verified, LinearIssue):
                    return verified, replay
            else:
                verified = self._read_and_verify(current.id, request, exact_body=False)
                if not isinstance(verified, LinearIssue):
                    return verified, replay
        else:
            verified = current
        for link in links:
            observed = _one_titled_attachment(verified, link["title"])
            if (
                observed is None
                or isinstance(observed, LinearDrift)
                or observed.url != link["url"]
            ):
                return LinearDrift(DriftKind.TIMED_OUT_WRITE, "delivery_link_readback"), replay
        return verified, replace(replay, pending_links=())

    def _github_diagnostic(
        self,
        request: StoryCreateRequest,
        issue_identifier: str,
        diagnostic: DiagnosticCode,
    ) -> LinearProviderError:
        return LinearProviderError(
            capability=NATIVE_GITHUB_DIFF_CAPABILITY,
            tool=LinearTool.GET_DIFF,
            diagnostic_code=diagnostic,
            operation_key=f"elephant-linear/v1/{request.key.marker.rsplit('/', 1)[1]}",
            verified_prior_receipts=(("issue_identifier", issue_identifier),),
        )

    def _complete_relation_write(self, request: StoryCreateRequest, source: LinearIssue, target_id: str, field: str, value: object, source_field: str, reciprocal_field: str | None, *, present: bool) -> LinearIssue | LinearDrift:
        try:
            self._connector.call(LinearTool.SAVE_ISSUE, (("id", source.id), (field, value)))
        except Exception:
            verified = self._read_for_operation(request)
            if not isinstance(verified, LinearIssue) or _has_relation(verified, source_field, target_id) != present:
                raise
        else:
            verified = self._read_and_verify(source.id, request)
            if not isinstance(verified, LinearIssue):
                return verified
            if _has_relation(verified, source_field, target_id) != present:
                return LinearDrift(DriftKind.MISSING_RECIPROCAL_LINK, "source_relation")
        target = self._read_detail(target_id)
        try:
            _verify_relation_target(target, reciprocal_field, source.id, present=present)
        except ValueError:
            return LinearDrift(DriftKind.MISSING_RECIPROCAL_LINK, "reciprocal_relation")
        return verified

    def _verified_status_id(self, target: HumanStatus) -> str:
        statuses = normalize_issue_statuses(self._connector.call(LinearTool.LIST_ISSUE_STATUSES, (("team", self._config.team_id),)))
        by_id = {status.id: status for status in statuses}
        for human, identifier in self._config.status_ids.items():
            status = by_id.get(identifier)
            if status is None or status.name != human.value or status.type != _STATUS_TYPES[human]:
                raise ValueError("configured status authority changed")
        return self._config.status_ids[target]

    def _create_arguments(self, request: StoryCreateRequest, state_id: str) -> tuple[tuple[str, object], ...]:
        result: list[tuple[str, object]] = [("team", request.team_id), ("title", request.title), ("description", _story_description(request)), ("labels", self._label_ids(request)), ("priority", request.priority), ("state", state_id)]
        if request.project_id is not None:
            result.append(("project", request.project_id))
        if request.parent_id is not None:
            result.append(("parentId", request.parent_id))
        return tuple(result)

    def _label_ids(self, request: StoryCreateRequest) -> tuple[str, ...]:
        return (() if request.product_label_id is None else (request.product_label_id,)) + (request.kind_label_id,)

    def _validate_request(self, request: StoryCreateRequest) -> None:
        if not isinstance(request, StoryCreateRequest):
            raise TypeError("request: expected StoryCreateRequest")
        if request.team_id != self._config.team_id or request.label_inventory != self._config.label_inventory or request.product_group_label_ids != self._config.product_group_label_ids or request.kind_group_label_ids != self._config.kind_group_label_ids:
            raise ValueError("request: configured authority changed")
        labels = {label.id: label.name for label in self._config.label_inventory}
        if request.story_kind == "product-facing":
            if (
                request.product_label_id is None
                or request.product_label_id not in self._config.product_group_label_ids
                or request.kind_label_id != self._config.product_facing_kind_label_id
            ):
                raise ValueError("product-facing kind/product authority")
        elif request.story_kind == "engineering-only":
            if request.product_label_id is not None or request.kind_label_id != self._config.engineering_only_kind_label_id:
                raise ValueError("engineering-only kind authority")
        else:
            raise ValueError("story_kind: expected product-facing or engineering-only")
        if labels.get(request.kind_label_id) != request.kind_label_name or (request.product_label_id is not None and labels.get(request.product_label_id) != request.product_label_name):
            raise ValueError("request label name: does not match configured evidence")


def _story_description(request: StoryCreateRequest) -> str:
    recap = request.description.strip()
    if not recap:
        raise ValueError("recap: expected nonblank concise line")
    if "\n" in recap or recap.startswith("#") or "Elephant story key:" in recap:
        raise ValueError("description: expected one concise recap line")
    return f"{recap}\n\n---\nElephant story key: `{request.key.marker}`\nElephant recap SHA-256: `{sha256(recap.encode('utf-8')).hexdigest()}`"


_FORBIDDEN_RECAP_CONTENT = (
    "product contract",
    "technical contract",
    "implementation checklist",
    "elephant.linear-checkpoint/",
    "internal progress",
)

_FORBIDDEN_RECAP_PATTERNS = (
    re.compile(r"\b(?:technical|implementation)\s+(?:plan|checklist)\b", re.I),
    re.compile(r"(?:^|\s)(?:[\w.-]+/)+[\w.-]+\.(?:py|ts|tsx|js|jsx|json|md|sql)\b", re.I),
    re.compile(r"(?:^|\s)-\s*\[[ x]\]", re.I),
    re.compile(r"\b(?:progress|checkpoint)\s+(?:update|status)\b", re.I),
    re.compile(r"\battachment\s+upload\b", re.I),
)


def _recap_field(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: expected concise nonblank text")
    normalized = value.strip()
    lowered = normalized.casefold()
    if (
        "\n" in normalized
        or any(marker in lowered for marker in _FORBIDDEN_RECAP_CONTENT)
        or any(pattern.search(normalized) for pattern in _FORBIDDEN_RECAP_PATTERNS)
        or (normalized.startswith("{") and normalized.endswith("}"))
    ):
        raise ValueError(f"{name}: contains non-recap content")
    return normalized


def _product_recap_description(
    request: StoryCreateRequest,
    *,
    problem: str,
    outcome: str,
    acceptance: tuple[str, ...],
    contract_url: str | None,
    behavior_preservation: str | None,
) -> str:
    if not isinstance(request, StoryCreateRequest):
        raise TypeError("request: expected StoryCreateRequest")
    problem_value = _recap_field("problem", problem)
    outcome_value = _recap_field("outcome", outcome)
    if not isinstance(acceptance, tuple) or not acceptance:
        raise ValueError("acceptance: expected one or more summaries")
    acceptance_values = tuple(
        _recap_field("acceptance", value) for value in acceptance
    )
    if len(set(acceptance_values)) != len(acceptance_values):
        raise ValueError("acceptance: duplicate summary")
    if request.story_kind == "product-facing":
        if behavior_preservation is not None:
            raise ValueError("behavior_preservation: not valid for product-facing recap")
        if (
            not isinstance(contract_url, str)
            or not contract_url.startswith("https://www.notion.so/")
            or any(character.isspace() for character in contract_url)
        ):
            raise ValueError("contract_url: expected canonical Notion HTTPS URL")
        contract_value: str | None = contract_url
        behavior_value: str | None = None
        binding = f"**Product Contract:** [Open in Notion](<{contract_url}>)"
    elif request.story_kind == "engineering-only":
        if contract_url is not None:
            raise ValueError("contract_url: not valid for engineering-only recap")
        behavior_value = _recap_field(
            "behavior_preservation", behavior_preservation
        )
        contract_value = None
        binding = f"**Behavior preservation:** {behavior_value}"
    else:
        raise ValueError("story_kind: expected configured kind")
    fields = json.dumps(
        {
            "acceptance": list(acceptance_values),
            "behavior_preservation": behavior_value,
            "contract_url": contract_value,
            "outcome": outcome_value,
            "problem": problem_value,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    acceptance_body = "\n".join(f"- {value}" for value in acceptance_values)
    return (
        "## Product Recap\n\n"
        f"**Problem:** {problem_value}\n\n"
        f"**Outcome:** {outcome_value}\n\n"
        "**Acceptance:**\n\n"
        f"{acceptance_body}\n\n"
        f"{binding}\n\n"
        "---\n"
        f"Elephant story key: `{request.key.marker}`\n"
        f"Elephant recap SHA-256: `{sha256(fields).hexdigest()}`"
    )


def _disposition_body(description: str, label: str, summary: str) -> str | None:
    marker = parse_story_marker(description)
    if marker is None:
        return None
    recap = description.split("\n\n---\n", 1)[0]
    suffix = f" {label}: {summary}"
    if recap.endswith(suffix):
        return description
    if f" {label}:" in recap:
        return None
    updated = recap + suffix
    return f"{updated}\n\n---\nElephant story key: `{marker[0]}`\nElephant recap SHA-256: `{sha256(updated.encode('utf-8')).hexdigest()}`"


def _duplicate_authority() -> LinearDrift:
    return LinearDrift(DriftKind.DUPLICATE_AUTHORITY, "duplicate_authoritative_story_key")


def _replay_value(
    replay: LinearEvidenceReplay | None,
    story_key: str,
    operation: str,
) -> LinearEvidenceReplay:
    if replay is None:
        return LinearEvidenceReplay.initial(story_key, operation)
    if not isinstance(replay, LinearEvidenceReplay):
        raise TypeError("replay: expected LinearEvidenceReplay or None")
    if replay.story_key != story_key or replay.operation != operation:
        raise ValueError("replay: does not belong to this story operation")
    return replay


def _verify_notion_page_url(url: object, page_id: str) -> None:
    if not isinstance(url, str) or any(character.isspace() for character in url):
        raise ValueError("contract_url: expected canonical Notion HTTPS URL")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise ValueError("contract_url: expected canonical Notion HTTPS URL") from None
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"notion.so", "www.notion.so"}
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith("/")
        or parsed.path.endswith("/")
    ):
        raise ValueError("contract_url: expected canonical Notion HTTPS URL")
    final = parsed.path.rsplit("/", 1)[-1]
    normalized_page = page_id.replace("-", "").casefold()
    normalized_final = final.replace("-", "").casefold()
    if (
        not isinstance(page_id, str)
        or not page_id.strip()
        or (
            final != page_id
            and not (
                re.fullmatch(r"[0-9a-f]{32}", normalized_page)
                and normalized_final.endswith(normalized_page)
            )
        )
    ):
        raise ValueError("contract_url: does not resolve the bound Notion page")


def _checkpoint_attachment_ids(
    issue: LinearIssue, snapshot: StorySnapshot
) -> frozenset[str]:
    if issue.attachments is None:
        raise ValueError("checkpoint read requires issue attachments")
    story_digest = snapshot.key.marker.rsplit("/", 1)[1]
    return frozenset(
        attachment.id
        for attachment in issue.attachments
        if (
            (match := _CHECKPOINT_TITLE.fullmatch(attachment.title)) is not None
            and match.group("story") == story_digest
        )
    )


def _one_titled_attachment(issue: LinearIssue, title: str):
    if issue.attachments is None:
        raise ValueError("issue attachments are required for evidence read-back")
    matches = tuple(item for item in issue.attachments if item.title == title)
    if len(matches) > 1:
        return _duplicate_authority()
    return matches[0] if matches else None


def _prepared_upload(
    raw: object,
) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    if not isinstance(raw, Mapping):
        raise TypeError("prepared upload: expected mapping")
    asset_url = raw.get("assetUrl")
    request = raw.get("uploadRequest")
    if not isinstance(asset_url, str) or not asset_url.strip() or not isinstance(request, Mapping):
        raise ValueError("prepared upload: expected asset and request")
    upload_url = request.get("url")
    headers = request.get("headers")
    if not isinstance(upload_url, str) or not upload_url.strip() or not isinstance(headers, Mapping):
        raise ValueError("prepared upload: expected URL and headers")
    header_values = tuple(headers.items())
    if not header_values or not all(
        isinstance(name, str) and name and isinstance(value, str) and value
        for name, value in header_values
    ):
        raise ValueError("prepared upload: expected signed string headers")
    return asset_url, upload_url, header_values


def _delivery_comment(record: DeliveryRecord, marker: str) -> str:
    return (
        "## Elephant Delivery Evidence\n\n"
        f"**Branch:** `{record.branch}`\n\n"
        f"**Pull request:** {record.pull_request_url}\n\n"
        f"**Merge commit:** `{record.merge_commit}`\n\n"
        f"**Verification SHA-256:** `{record.verification_sha256}`\n\n"
        "---\n"
        f"{marker}"
    )


def _parse_delivery_footer(body: str) -> str | None:
    match = re.search(
        r"(?:\A|\n)---\n(?P<marker>Elephant delivery evidence: `elephant-story/v1/[0-9a-f]{64}`)\Z",
        body,
    )
    return None if match is None else match.group("marker")


def _has_relation(issue: LinearIssue, field: str, target_id: str) -> bool:
    if issue.relations is None:
        raise ValueError("detailed issue relations are required")
    value = getattr(issue.relations, field)
    return value is not None and (value.issue_id == target_id if field == "duplicate_of" else any(item.issue_id == target_id for item in value))


def _verify_relation_target(issue: LinearIssue, reciprocal_field: str | None, source_id: str, *, present: bool = True) -> None:
    if reciprocal_field is None:  # Linear exposes no inverse `duplicatedBy`; only readability is authoritative.
        return
    if _has_relation(issue, reciprocal_field, source_id) != present:
        raise ValueError("missing reciprocal relation")

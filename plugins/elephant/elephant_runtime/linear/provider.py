"""Replay-safe story lifecycle operations over the injected Linear connector."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from hashlib import sha256

from elephant_runtime.workspace_core import (
    DriftKind,
    HumanStatus,
    ProductDisposition,
    terminal_status_for_disposition,
)

from .connector import LinearConnector
from .models import (
    LinearAuthorityMissing,
    LinearDrift,
    LinearIssue,
    LinearLabel,
    LinearStatus,
    LinearTool,
    StoryCreateRequest,
    StoryKey,
)
from .normalize import classify_drift, normalize_issue, normalize_issues, normalize_issue_statuses, parse_story_marker


_STATUS_TYPES = {
    HumanStatus.BACKLOG: "backlog",
    HumanStatus.SHAPING: "unstarted",
    HumanStatus.READY: "unstarted",
    HumanStatus.IN_PROGRESS: "started",
    HumanStatus.DONE: "completed",
    HumanStatus.CANCELED: "canceled",
}


@dataclass(frozen=True)
class LinearStoryProviderConfig:
    """Configured opaque authority required by one Linear team."""

    team_id: str
    statuses: tuple[tuple[HumanStatus, str], ...]
    label_inventory: tuple[LinearLabel, ...]
    product_group_label_ids: frozenset[str]
    kind_group_label_ids: frozenset[str]

    def __post_init__(self) -> None:
        if not isinstance(self.team_id, str) or not self.team_id.strip():
            raise ValueError("team_id: expected nonblank string")
        if not isinstance(self.statuses, tuple) or len(self.statuses) != len(HumanStatus):
            raise ValueError("statuses: expected every HumanStatus exactly once")
        keys: list[HumanStatus] = []
        for status, identifier in self.statuses:
            if not isinstance(status, HumanStatus) or not isinstance(identifier, str) or not identifier.strip():
                raise TypeError("statuses: expected (HumanStatus, nonblank ID) tuples")
            keys.append(status)
        if set(keys) != set(HumanStatus) or len(set(keys)) != len(keys):
            raise ValueError("statuses: expected every HumanStatus exactly once")
        if not isinstance(self.label_inventory, tuple) or not all(
            isinstance(label, LinearLabel) for label in self.label_inventory
        ):
            raise TypeError("label_inventory: expected LinearLabel tuple")
        ids = {label.id for label in self.label_inventory}
        if len(ids) != len(self.label_inventory):
            raise ValueError("label_inventory: duplicate opaque ID")
        for group_name in ("product_group_label_ids", "kind_group_label_ids"):
            group = getattr(self, group_name)
            if not isinstance(group, frozenset) or not group or not group <= ids:
                raise ValueError(f"{group_name}: expected nonempty configured label IDs")

    @property
    def status_ids(self) -> dict[HumanStatus, str]:
        return dict(self.statuses)


class LinearStoryProvider:
    """Strict selected-provider lifecycle; the connector is the only I/O boundary."""

    def __init__(self, connector: LinearConnector, config: LinearStoryProviderConfig) -> None:
        if not isinstance(config, LinearStoryProviderConfig):
            raise TypeError("config: expected LinearStoryProviderConfig")
        self._connector = connector
        self._config = config

    def create_story(self, request: StoryCreateRequest) -> LinearIssue | LinearDrift:
        self._validate_request(request)
        matches = self._lookup(request.key)
        if len(matches) > 1:
            return _duplicate_authority()
        if matches:
            return self._read_and_verify(matches[0].id, request)
        arguments = self._create_arguments(request)
        try:
            self._connector.call(LinearTool.SAVE_ISSUE, arguments)
        except Exception:
            # A mutation receipt never authorizes another creation attempt.
            resumed = self._lookup(request.key)
            if len(resumed) > 1:
                return _duplicate_authority()
            if len(resumed) == 1:
                return self._read_and_verify(resumed[0].id, request)
            raise
        resumed = self._lookup(request.key)
        if len(resumed) > 1:
            return _duplicate_authority()
        if not resumed:
            return LinearDrift(DriftKind.TIMED_OUT_WRITE, "create_read_back_missing")
        return self._read_and_verify(resumed[0].id, request)

    def read_story(
        self, key: StoryKey, *, request: StoryCreateRequest | None = None
    ) -> LinearIssue | LinearAuthorityMissing | LinearDrift:
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

    def update_human_status(
        self, request: StoryCreateRequest, target: HumanStatus
    ) -> LinearIssue | LinearDrift:
        """Advance a verified story through the defined human-state graph."""
        self._validate_request(request)
        if not isinstance(target, HumanStatus):
            raise TypeError("target: expected HumanStatus")
        current = self.read_story(request.key, request=request)
        if not isinstance(current, LinearIssue):
            return current
        from elephant_runtime.workspace_core import can_transition_human_status

        if not can_transition_human_status(request.human_status, target):
            raise ValueError("human status transition is not permitted")
        status_id = self._verified_status_id(target)
        updated_request = replace(request, human_status=target)
        arguments = (("id", current.id), ("state", status_id))
        try:
            self._connector.call(LinearTool.SAVE_ISSUE, arguments)
        except Exception:
            resumed = self.read_story(request.key, request=updated_request)
            if isinstance(resumed, LinearIssue):
                return resumed
            raise
        return self._read_and_verify(current.id, updated_request)

    def create_child_story(
        self, parent_request: StoryCreateRequest, child_request: StoryCreateRequest
    ) -> LinearIssue | LinearDrift:
        """Create an explicitly keyed child only under a reverified parent."""
        parent = self.read_story(parent_request.key, request=parent_request)
        if not isinstance(parent, LinearIssue):
            return parent
        self._validate_request(child_request)
        if child_request.parent_id != parent.id:
            raise ValueError("child_request.parent_id: must be the verified parent issue")
        child = self.create_story(child_request)
        if not isinstance(child, LinearIssue):
            return child
        raw = self._connector.call(
            LinearTool.GET_ISSUE,
            (("id", child.id), ("includeRelations", True)),
        )
        if not isinstance(raw, Mapping) or raw.get("parentId") != parent.id:
            return LinearDrift(DriftKind.PRODUCT_ASSIGNMENT_CHANGED, "parent_id")
        return child

    def apply_disposition(
        self,
        request: StoryCreateRequest,
        disposition: ProductDisposition,
        *,
        child_requests: tuple[StoryCreateRequest, ...] = (),
        summary: str | None = None,
    ) -> LinearIssue | LinearDrift:
        """Apply one product decision without placing implementation progress in Linear."""
        self._validate_request(request)
        if not isinstance(disposition, ProductDisposition):
            raise TypeError("disposition: expected ProductDisposition")
        current = self.read_story(request.key, request=request)
        if not isinstance(current, LinearIssue):
            return current
        if disposition is ProductDisposition.SPLIT:
            if not child_requests:
                raise ValueError("split: expected explicitly keyed child requests")
            for child_request in child_requests:
                child = self.create_child_story(request, child_request)
                if not isinstance(child, LinearIssue):
                    return child
        if disposition in {ProductDisposition.DEFERRED, ProductDisposition.REJECTED}:
            if not isinstance(summary, str) or not summary.strip() or "\n" in summary:
                raise ValueError("disposition summary: expected one concise nonblank line")
            label = "Reconsideration" if disposition is ProductDisposition.DEFERRED else "Disposition"
            description = _with_disposition_summary(current.description, label, summary.strip())
            try:
                self._connector.call(
                    LinearTool.SAVE_ISSUE,
                    (("id", current.id), ("description", description)),
                )
            except Exception:
                resumed = self.read_story(request.key, request=request)
                if not isinstance(resumed, LinearIssue) or resumed.description != description:
                    raise
            else:
                verified = self._read_and_verify(current.id, request)
                if not isinstance(verified, LinearIssue) or verified.description != description:
                    return LinearDrift(DriftKind.TIMED_OUT_WRITE, "disposition_summary")
        return self.update_human_status(request, terminal_status_for_disposition(disposition))

    def link_relation(
        self, request: StoryCreateRequest, target_issue_id: str, relation: str
    ) -> LinearIssue | LinearDrift:
        """Create one exact relation and verify both categorized relation views."""
        self._validate_request(request)
        if not isinstance(target_issue_id, str) or not target_issue_id.strip():
            raise ValueError("target_issue_id: expected nonblank string")
        relation_fields = {
            "blockedBy": ("blocked_by", "blocks"),
            "blocks": ("blocks", "blocked_by"),
            "relatedTo": ("related_to", "related_to"),
            "duplicateOf": ("duplicate_of", None),
        }
        if relation not in relation_fields:
            raise ValueError("relation: expected connector relation field")
        source = self.read_story(request.key, request=request)
        if not isinstance(source, LinearIssue):
            return source
        target = self._read_detail(target_issue_id)
        source_field, reciprocal_field = relation_fields[relation]
        if _has_relation(source, source_field, target_issue_id):
            _verify_reciprocal(target, reciprocal_field, source.id)
            return source
        arguments = (("id", source.id), (relation, target_issue_id))
        try:
            self._connector.call(LinearTool.SAVE_ISSUE, arguments)
        except Exception:
            resumed = self.read_story(request.key, request=request)
            if not isinstance(resumed, LinearIssue) or not _has_relation(
                resumed, source_field, target_issue_id
            ):
                raise
            _verify_reciprocal(self._read_detail(target_issue_id), reciprocal_field, source.id)
            return resumed
        verified = self._read_and_verify(source.id, request)
        if not isinstance(verified, LinearIssue) or not _has_relation(
            verified, source_field, target_issue_id
        ):
            return LinearDrift(DriftKind.MISSING_RECIPROCAL_LINK, "source_relation")
        try:
            _verify_reciprocal(self._read_detail(target_issue_id), reciprocal_field, source.id)
        except ValueError:
            return LinearDrift(DriftKind.MISSING_RECIPROCAL_LINK, "reciprocal_relation")
        return verified

    def _lookup(self, key: StoryKey) -> tuple[LinearIssue, ...]:
        raw = self._connector.call(
            LinearTool.LIST_ISSUES,
            (("team", self._config.team_id), ("query", key.marker)),
        )
        try:
            page = normalize_issues(raw)
            issues = page.values
        except ValueError as error:
            if "duplicate stable marker" not in str(error):
                raise
            if not isinstance(raw, Mapping) or not isinstance(raw.get("issues"), list):
                raise
            issues = tuple(normalize_issue(value) for value in raw["issues"])
        return tuple(
            issue for issue in issues
            if isinstance(issue, LinearIssue)
            and issue.team_id == self._config.team_id
            and (marker := parse_story_marker(issue.description)) is not None
            and marker[0] == key.marker
        )

    def _read_and_verify(
        self, issue_id: str, request: StoryCreateRequest | None
    ) -> LinearIssue | LinearDrift:
        raw = self._connector.call(
            LinearTool.GET_ISSUE,
            (("id", issue_id), ("includeRelations", True)),
        )
        issue = normalize_issue(raw, include_relations=True)
        if issue.id != issue_id:
            raise ValueError("read-back issue ID does not match lookup")
        if request is None:
            return issue
        drift = classify_drift(
            (issue,),
            expected_story_key=request.key.marker,
            expected_team_id=request.team_id,
            label_inventory=self._config.label_inventory,
            product_group_label_ids=self._config.product_group_label_ids,
            kind_group_label_ids=self._config.kind_group_label_ids,
            expected_product_label_id=request.product_label_id,
            expected_kind_label_id=request.kind_label_id,
            verified_status_names=(request.human_status.value,),
        )
        if drift is not None:
            return drift
        if issue.status_type != _STATUS_TYPES[request.human_status]:
            return LinearDrift(DriftKind.HUMAN_STATUS_ADVANCED, "status_type")
        expected_labels = frozenset(self._label_ids(request))
        labels_by_id = {label.id: label.name for label in self._config.label_inventory}
        if frozenset(issue.labels) != frozenset(labels_by_id[label] for label in expected_labels):
            return LinearDrift(DriftKind.PRODUCT_ASSIGNMENT_CHANGED, "label_assignment")
        return issue

    def _read_detail(self, issue_id: str) -> LinearIssue:
        raw = self._connector.call(
            LinearTool.GET_ISSUE,
            (("id", issue_id), ("includeRelations", True)),
        )
        issue = normalize_issue(raw, include_relations=True)
        if issue.id != issue_id:
            raise ValueError("read-back issue ID does not match requested issue")
        return issue

    def _verified_status_id(self, target: HumanStatus) -> str:
        raw = self._connector.call(
            LinearTool.LIST_ISSUE_STATUSES,
            (("team", self._config.team_id),),
        )
        statuses = normalize_issue_statuses(raw)
        by_id = {status.id: status for status in statuses}
        if len(by_id) != len(statuses):
            raise ValueError("status inventory: duplicate opaque ID")
        for human_status, status_id in self._config.status_ids.items():
            status = by_id.get(status_id)
            if status is None or status.name != human_status.value or status.type != _STATUS_TYPES[human_status]:
                raise ValueError("configured status authority changed")
        return self._config.status_ids[target]

    def _create_arguments(self, request: StoryCreateRequest) -> tuple[tuple[str, object], ...]:
        arguments: list[tuple[str, object]] = [
            ("team", request.team_id),
            ("title", request.title),
            ("description", _story_description(request)),
            ("labels", self._label_ids(request)),
            ("priority", request.priority),
        ]
        if request.project_id is not None:
            arguments.append(("project", request.project_id))
        if request.parent_id is not None:
            arguments.append(("parentId", request.parent_id))
        return tuple(arguments)

    def _label_ids(self, request: StoryCreateRequest) -> tuple[str, ...]:
        return (() if request.product_label_id is None else (request.product_label_id,)) + (request.kind_label_id,)

    def _validate_request(self, request: StoryCreateRequest) -> None:
        if not isinstance(request, StoryCreateRequest):
            raise TypeError("request: expected StoryCreateRequest")
        if request.team_id != self._config.team_id:
            raise ValueError("request.team_id: does not match configured team")
        required = (
            request.story_kind,
            request.kind_label_id,
            request.kind_label_name,
            request.priority,
        )
        if any(value is None for value in required):
            raise ValueError("request: explicit story kind, kind label, and priority are required")
        if request.label_inventory != self._config.label_inventory or (
            request.product_group_label_ids != self._config.product_group_label_ids
            or request.kind_group_label_ids != self._config.kind_group_label_ids
        ):
            raise ValueError("request: label authority does not match configured evidence")
        labels = {label.id: label.name for label in self._config.label_inventory}
        if request.story_kind == "product-facing":
            if request.product_label_id is None or request.product_label_name is None:
                raise ValueError("product-facing request requires product label")
            if request.product_label_id not in self._config.product_group_label_ids:
                raise ValueError("product label: not in configured Product group")
        elif request.story_kind == "engineering-only":
            if request.product_label_id is not None:
                raise ValueError("engineering-only request cannot have product label")
        else:
            raise ValueError("story_kind: expected product-facing or engineering-only")
        if request.kind_label_id not in self._config.kind_group_label_ids:
            raise ValueError("kind label: not in configured Kind group")
        if labels.get(request.kind_label_id) != request.kind_label_name or (
            request.product_label_id is not None
            and labels.get(request.product_label_id) != request.product_label_name
        ):
            raise ValueError("request label name: does not match configured evidence")


def _story_description(request: StoryCreateRequest) -> str:
    recap = request.description.strip()
    if "\n" in recap or recap.startswith("#") or "Elephant story key:" in recap:
        raise ValueError("description: expected one concise recap line")
    return (
        f"{recap}\n\n---\n"
        f"Elephant story key: `{request.key.marker}`\n"
        f"Elephant recap SHA-256: `{sha256(recap.encode('utf-8')).hexdigest()}`"
    )


def _duplicate_authority() -> LinearDrift:
    return LinearDrift(DriftKind.DUPLICATE_AUTHORITY, "duplicate_authoritative_story_key")


def _with_disposition_summary(description: str, label: str, summary: str) -> str:
    marker = parse_story_marker(description)
    if marker is None:
        raise ValueError("description: missing exact story marker")
    recap = description.split("\n\n---\n", 1)[0]
    updated_recap = f"{recap} {label}: {summary}"
    return (
        f"{updated_recap}\n\n---\n"
        f"Elephant story key: `{marker[0]}`\n"
        f"Elephant recap SHA-256: `{sha256(updated_recap.encode('utf-8')).hexdigest()}`"
    )


def _has_relation(issue: LinearIssue, field: str, target_issue_id: str) -> bool:
    if issue.relations is None:
        raise ValueError("detailed issue relations are required")
    value = getattr(issue.relations, field)
    if field == "duplicate_of":
        return value is not None and value.issue_id == target_issue_id
    return any(relation.issue_id == target_issue_id for relation in value)


def _verify_reciprocal(issue: LinearIssue, field: str | None, source_issue_id: str) -> None:
    if field is None:
        return
    if not _has_relation(issue, field, source_issue_id):
        raise ValueError("missing reciprocal relation")

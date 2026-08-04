"""Immutable values for the Linear story-provider boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import re

from elephant_runtime.workspace_core import (
    CheckpointPhase,
    DiagnosticCode,
    DriftKind,
    HumanStatus,
    ProductDisposition,
    STORY_RUNTIME_CAPABILITIES,
)


class LinearTool(str, Enum):
    """The complete connected Linear tool vocabulary used by this provider."""

    LIST_ISSUES = "mcp__codex_apps__linear_list_issues"
    SAVE_ISSUE = "mcp__codex_apps__linear_save_issue"
    GET_ISSUE = "mcp__codex_apps__linear_get_issue"
    LIST_ISSUE_STATUSES = "mcp__codex_apps__linear_list_issue_statuses"
    GET_ATTACHMENT = "mcp__codex_apps__linear_get_attachment"
    PREPARE_ATTACHMENT_UPLOAD = "mcp__codex_apps__linear_prepare_attachment_upload"
    CREATE_ATTACHMENT_FROM_UPLOAD = "mcp__codex_apps__linear_create_attachment_from_upload"
    DELETE_ATTACHMENT = "mcp__codex_apps__linear_delete_attachment"
    LIST_COMMENTS = "mcp__codex_apps__linear_list_comments"
    SAVE_COMMENT = "mcp__codex_apps__linear_save_comment"
    LIST_DIFFS = "mcp__codex_apps__linear_list_diffs"
    GET_DIFF = "mcp__codex_apps__linear_get_diff"
    LIST_TEAMS = "mcp__codex_apps__linear_list_teams"
    GET_TEAM = "mcp__codex_apps__linear_get_team"
    GET_USER = "mcp__codex_apps__linear_get_user"
    LIST_ISSUE_LABELS = "mcp__codex_apps__linear_list_issue_labels"
    CREATE_ISSUE_LABEL = "mcp__codex_apps__linear_create_issue_label"


def _require_nonempty_string(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name}: expected non-empty string")
    return value


def _require_enum(name: str, value: object, enum_type: type[Enum]) -> None:
    if not isinstance(value, enum_type):
        raise TypeError(f"{name}: expected {enum_type.__name__}")


@dataclass(frozen=True)
class StoryKey:
    repository_id: str
    intent_id: str

    def __post_init__(self) -> None:
        _require_nonempty_string("repository_id", self.repository_id)
        _require_nonempty_string("intent_id", self.intent_id)

    @property
    def marker(self) -> str:
        payload = json.dumps(
            {"intent_id": self.intent_id, "repository_id": self.repository_id},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return f"elephant-story/v1/{sha256(payload).hexdigest()}"


@dataclass(frozen=True)
class ProductRecap:
    product_key: str
    disposition: ProductDisposition
    body: str

    def __post_init__(self) -> None:
        _require_nonempty_string("product_key", self.product_key)
        _require_enum("disposition", self.disposition, ProductDisposition)
        _require_nonempty_string("body", self.body)


@dataclass(frozen=True)
class ContractBinding:
    contract_id: str
    fingerprint: str

    def __post_init__(self) -> None:
        _require_nonempty_string("contract_id", self.contract_id)
        if (
            not isinstance(self.fingerprint, str)
            or len(self.fingerprint) != 64
            or any(character not in "0123456789abcdef" for character in self.fingerprint)
        ):
            raise ValueError("fingerprint: expected lowercase SHA-256")


@dataclass(frozen=True)
class DeliveryEvidence:
    kind: DriftKind
    reference: str
    summary: str

    def __post_init__(self) -> None:
        _require_enum("kind", self.kind, DriftKind)
        _require_nonempty_string("reference", self.reference)
        _require_nonempty_string("summary", self.summary)


@dataclass(frozen=True)
class StoryCreateRequest:
    key: StoryKey
    title: str
    description: str
    team_id: str
    human_status: HumanStatus

    def __post_init__(self) -> None:
        if not isinstance(self.key, StoryKey):
            raise TypeError("key: expected StoryKey")
        _require_nonempty_string("title", self.title)
        if not isinstance(self.description, str):
            raise TypeError("description: expected string")
        _require_nonempty_string("team_id", self.team_id)
        _require_enum("human_status", self.human_status, HumanStatus)


@dataclass(frozen=True)
class StorySnapshot:
    key: StoryKey
    issue_id: str
    title: str
    human_status: HumanStatus
    checkpoint_phase: CheckpointPhase

    def __post_init__(self) -> None:
        if not isinstance(self.key, StoryKey):
            raise TypeError("key: expected StoryKey")
        _require_nonempty_string("issue_id", self.issue_id)
        _require_nonempty_string("title", self.title)
        _require_enum("human_status", self.human_status, HumanStatus)
        _require_enum("checkpoint_phase", self.checkpoint_phase, CheckpointPhase)


def _require_optional_nonempty_string(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _require_nonempty_string(name, value)


def _require_tuple_of_strings(name: str, value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise TypeError(f"{name}: expected tuple of nonblank strings")
    return value


@dataclass(frozen=True)
class LinearTeam:
    id: str
    name: str
    key: str
    member_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_nonempty_string("id", self.id)
        _require_nonempty_string("name", self.name)
        _require_nonempty_string("key", self.key)
        _require_tuple_of_strings("member_ids", self.member_ids)
        if len(set(self.member_ids)) != len(self.member_ids):
            raise ValueError("member_ids: duplicate opaque ID")


@dataclass(frozen=True)
class LinearStatus:
    id: str
    name: str
    type: str

    def __post_init__(self) -> None:
        _require_nonempty_string("id", self.id)
        _require_nonempty_string("name", self.name)
        _require_nonempty_string("type", self.type)


@dataclass(frozen=True)
class LinearLabel:
    id: str
    name: str
    group_id: str | None
    group_name: str | None

    def __post_init__(self) -> None:
        _require_nonempty_string("id", self.id)
        _require_nonempty_string("name", self.name)
        _require_optional_nonempty_string("group_id", self.group_id)
        _require_optional_nonempty_string("group_name", self.group_name)
        if (self.group_id is None) != (self.group_name is None):
            raise ValueError("label group: expected both ID and name or neither")


@dataclass(frozen=True)
class LinearAttachment:
    id: str
    url: str
    title: str

    def __post_init__(self) -> None:
        _require_nonempty_string("id", self.id)
        _require_nonempty_string("url", self.url)
        _require_nonempty_string("title", self.title)


@dataclass(frozen=True)
class LinearComment:
    id: str
    body: str

    def __post_init__(self) -> None:
        _require_nonempty_string("id", self.id)
        if not isinstance(self.body, str):
            raise TypeError("body: expected string")


@dataclass(frozen=True)
class LinearDiff:
    id: str
    url: str
    issue_id: str | None = None
    issue_identifier: str | None = None

    def __post_init__(self) -> None:
        _require_nonempty_string("id", self.id)
        _require_nonempty_string("url", self.url)
        _require_optional_nonempty_string("issue_id", self.issue_id)
        _require_optional_nonempty_string("issue_identifier", self.issue_identifier)
        if (self.issue_id is None) != (self.issue_identifier is None):
            raise ValueError("diff issue: expected both ID and identifier or neither")


@dataclass(frozen=True)
class LinearRelation:
    id: str
    type: str
    issue_id: str
    issue_identifier: str

    def __post_init__(self) -> None:
        _require_nonempty_string("id", self.id)
        _require_nonempty_string("type", self.type)
        _require_nonempty_string("issue_id", self.issue_id)
        _require_nonempty_string("issue_identifier", self.issue_identifier)


@dataclass(frozen=True)
class LinearIssue:
    id: str
    identifier: str
    title: str
    description: str
    team_id: str
    state: LinearStatus
    labels: tuple[LinearLabel, ...]
    attachments: tuple[LinearAttachment, ...]
    state_history: tuple[tuple[str, str], ...]
    relations: tuple[LinearRelation, ...] | None
    priority: int | None

    def __post_init__(self) -> None:
        for field_name in ("id", "identifier", "title", "team_id"):
            _require_nonempty_string(field_name, getattr(self, field_name))
        if not isinstance(self.description, str):
            raise TypeError("description: expected string")
        if not isinstance(self.state, LinearStatus):
            raise TypeError("state: expected LinearStatus")
        if not isinstance(self.labels, tuple) or not all(
            isinstance(label, LinearLabel) for label in self.labels
        ):
            raise TypeError("labels: expected LinearLabel tuple")
        if not isinstance(self.attachments, tuple) or not all(
            isinstance(attachment, LinearAttachment) for attachment in self.attachments
        ):
            raise TypeError("attachments: expected LinearAttachment tuple")
        if not isinstance(self.state_history, tuple) or not all(
            isinstance(entry, tuple)
            and len(entry) == 2
            and all(isinstance(value, str) and value.strip() for value in entry)
            for entry in self.state_history
        ):
            raise TypeError("state_history: expected (entry ID, state ID) tuple")
        if self.relations is not None and (
            not isinstance(self.relations, tuple)
            or not all(isinstance(relation, LinearRelation) for relation in self.relations)
        ):
            raise TypeError("relations: expected LinearRelation tuple or None")
        if self.priority is not None and (
            not isinstance(self.priority, int) or isinstance(self.priority, bool)
        ):
            raise TypeError("priority: expected int or None")
        for name, values in (
            ("labels", self.labels),
            ("attachments", self.attachments),
            ("state_history", tuple(entry[0] for entry in self.state_history)),
            ("relations", self.relations or ()),
        ):
            ids = tuple(value.id if hasattr(value, "id") else value for value in values)
            if len(set(ids)) != len(ids):
                raise ValueError(f"{name}: duplicate opaque ID")


@dataclass(frozen=True)
class PageCursor:
    values: tuple[object, ...]
    next_cursor: str | None

    def __post_init__(self) -> None:
        public_values = (
            LinearTeam,
            LinearStatus,
            LinearLabel,
            LinearIssue,
            LinearRelation,
            LinearAttachment,
            LinearComment,
            LinearDiff,
        )
        if not isinstance(self.values, tuple) or not all(
            isinstance(value, public_values) for value in self.values
        ):
            raise TypeError("values: expected normalized value tuple")
        _require_optional_nonempty_string("next_cursor", self.next_cursor)


@dataclass(frozen=True)
class LinearDrift:
    kind: DriftKind
    observation: str

    def __post_init__(self) -> None:
        _require_enum("kind", self.kind, DriftKind)
        _require_nonempty_string("observation", self.observation)


_CANONICAL_LINEAR_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_SAFE_OPERATION_KEY = re.compile(r"elephant-linear/v1/[0-9a-f]{64}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_LINEAR_ENTITY_RECEIPT_NAMES = frozenset({
    "issue_id",
    "attachment_id",
    "comment_id",
    "diff_id",
    "label_id",
    "team_id",
    "status_id",
})
_DIGEST_RECEIPT_NAMES = frozenset({
    "observed_fingerprint",
})


def _safe_receipts(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, tuple):
        raise TypeError("verified_prior_receipts: expected tuple")
    receipts: list[tuple[str, str]] = []
    for receipt in value:
        if (
            not isinstance(receipt, tuple)
            or len(receipt) != 2
            or not all(isinstance(part, str) and part for part in receipt)
        ):
            raise ValueError("verified_prior_receipts: expected safe receipt identifiers")
        name, identifier = receipt
        if name in _LINEAR_ENTITY_RECEIPT_NAMES:
            is_safe = _CANONICAL_LINEAR_UUID.fullmatch(identifier) is not None
        elif name in _DIGEST_RECEIPT_NAMES:
            is_safe = _SHA256.fullmatch(identifier) is not None
        else:
            is_safe = False
        if not is_safe:
            raise ValueError("verified_prior_receipts: expected safe receipt identifiers")
        receipts.append((name, identifier))
    return tuple(receipts)


@dataclass(frozen=True)
class LinearProviderError(Exception):
    capability: str
    tool: LinearTool
    diagnostic_code: DiagnosticCode
    operation_key: str
    verified_prior_receipts: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.capability not in STORY_RUNTIME_CAPABILITIES:
            raise ValueError("capability: expected known story capability")
        _require_enum("tool", self.tool, LinearTool)
        _require_enum("diagnostic_code", self.diagnostic_code, DiagnosticCode)
        if (
            not isinstance(self.operation_key, str)
            or _SAFE_OPERATION_KEY.fullmatch(self.operation_key) is None
        ):
            raise ValueError("operation_key: expected safe operation key")
        object.__setattr__(
            self, "verified_prior_receipts", _safe_receipts(self.verified_prior_receipts)
        )
        Exception.__init__(
            self,
            f"Linear capability {self.capability!r} failed for operation {self.operation_key!r} "
            f"with {self.diagnostic_code.value}",
        )

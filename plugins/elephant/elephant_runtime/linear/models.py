"""Immutable values for the Linear story-provider boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json

from elephant_runtime.workspace_core import (
    CheckpointPhase,
    DiagnosticCode,
    DriftKind,
    HumanStatus,
    ProductDisposition,
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


def _safe_receipts(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, tuple):
        raise TypeError("verified_prior_receipts: expected tuple")
    receipts: list[tuple[str, str]] = []
    forbidden_key_parts = ("token", "url", "base64", "bytes", "payload", "content")
    for receipt in value:
        if (
            not isinstance(receipt, tuple)
            or len(receipt) != 2
            or not all(isinstance(part, str) and part for part in receipt)
        ):
            raise ValueError("verified_prior_receipts: expected safe receipt identifiers")
        name, identifier = receipt
        if (
            any(part in name.lower() for part in forbidden_key_parts)
            or "://" in identifier
            or len(identifier) > 512
        ):
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
        _require_nonempty_string("capability", self.capability)
        _require_enum("tool", self.tool, LinearTool)
        _require_enum("diagnostic_code", self.diagnostic_code, DiagnosticCode)
        _require_nonempty_string("operation_key", self.operation_key)
        object.__setattr__(
            self, "verified_prior_receipts", _safe_receipts(self.verified_prior_receipts)
        )
        Exception.__init__(
            self,
            f"Linear capability {self.capability!r} failed for operation {self.operation_key!r} "
            f"with {self.diagnostic_code.value}",
        )

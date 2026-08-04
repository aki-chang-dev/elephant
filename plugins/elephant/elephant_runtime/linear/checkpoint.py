"""Canonical Linear checkpoint and delivery-evidence values."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Protocol

from elephant_runtime.workspace_core import CheckpointPhase

from .models import ContractBinding, StorySnapshot


CHECKPOINT_SCHEMA = "elephant.linear-checkpoint/v1"
_STORY_KEY = re.compile(r"elephant-story/v1/(?P<digest>[0-9a-f]{64})\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


def _optional_nonblank(name: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: expected nonblank string or None")
    return value


def _optional_sha256(name: str, value: object) -> str | None:
    value = _optional_nonblank(name, value)
    if value is not None and _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name}: expected lowercase SHA-256 or None")
    return value


@dataclass(frozen=True)
class CheckpointDelivery:
    branch: str | None
    pull_request_url: str | None
    merge_commit: str | None
    verification_sha256: str | None

    def __post_init__(self) -> None:
        _optional_nonblank("branch", self.branch)
        pull_request_url = _optional_nonblank("pull_request_url", self.pull_request_url)
        if pull_request_url is not None and not pull_request_url.startswith("https://"):
            raise ValueError("pull_request_url: expected HTTPS URL")
        merge_commit = _optional_nonblank("merge_commit", self.merge_commit)
        if merge_commit is not None and _COMMIT.fullmatch(merge_commit) is None:
            raise ValueError("merge_commit: expected lowercase commit SHA")
        _optional_sha256("verification_sha256", self.verification_sha256)

    def canonical_value(self) -> dict[str, str | None]:
        return {
            "branch": self.branch,
            "pull_request_url": self.pull_request_url,
            "merge_commit": self.merge_commit,
            "verification_sha256": self.verification_sha256,
        }


@dataclass(frozen=True)
class Checkpoint:
    story_key: str
    issue_id: str
    phase: CheckpointPhase
    sequence: int
    contract: ContractBinding
    delivery: CheckpointDelivery
    previous_sha256: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.story_key, str) or _STORY_KEY.fullmatch(self.story_key) is None:
            raise ValueError("story_key: expected exact Elephant story marker")
        if not isinstance(self.issue_id, str) or not self.issue_id.strip():
            raise ValueError("issue_id: expected nonblank string")
        if not isinstance(self.phase, CheckpointPhase):
            raise TypeError("phase: expected CheckpointPhase")
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 1:
            raise ValueError("sequence: expected positive integer")
        if not isinstance(self.contract, ContractBinding):
            raise TypeError("contract: expected ContractBinding")
        if not isinstance(self.delivery, CheckpointDelivery):
            raise TypeError("delivery: expected CheckpointDelivery")
        _optional_sha256("previous_sha256", self.previous_sha256)

    @property
    def canonical_bytes(self) -> bytes:
        value = {
            "schema": CHECKPOINT_SCHEMA,
            "story_key": self.story_key,
            "issue_id": self.issue_id,
            "phase": self.phase.value,
            "sequence": self.sequence,
            "contract": {
                "page_id": self.contract.contract_id,
                "fingerprint": self.contract.fingerprint,
            },
            "delivery": self.delivery.canonical_value(),
            "previous_sha256": self.previous_sha256,
        }
        return (
            json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\n"
        ).encode("utf-8")

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes).hexdigest()

    @property
    def filename(self) -> str:
        match = _STORY_KEY.fullmatch(self.story_key)
        assert match is not None
        return f"elephant-checkpoint-{match.group('digest')}-{self.sequence}.json"

    def verify_identity(self, snapshot: StorySnapshot) -> None:
        if not isinstance(snapshot, StorySnapshot):
            raise TypeError("snapshot: expected StorySnapshot")
        if self.story_key != snapshot.key.marker or self.issue_id != snapshot.issue_id:
            raise ValueError("checkpoint identity does not match verified story")

    @classmethod
    def from_bytes(cls, raw: bytes) -> Checkpoint:
        if not isinstance(raw, bytes):
            raise TypeError("raw: expected bytes")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("checkpoint: invalid JSON") from error
        if not isinstance(value, dict) or set(value) != {
            "schema", "story_key", "issue_id", "phase", "sequence",
            "contract", "delivery", "previous_sha256",
        }:
            raise ValueError("checkpoint: expected exact schema fields")
        if value["schema"] != CHECKPOINT_SCHEMA:
            raise ValueError("checkpoint.schema: unsupported")
        contract = value["contract"]
        delivery = value["delivery"]
        if not isinstance(contract, dict) or set(contract) != {"page_id", "fingerprint"}:
            raise ValueError("checkpoint.contract: expected exact fields")
        if not isinstance(delivery, dict) or set(delivery) != {
            "branch", "pull_request_url", "merge_commit", "verification_sha256",
        }:
            raise ValueError("checkpoint.delivery: expected exact fields")
        try:
            phase = CheckpointPhase(value["phase"])
        except (TypeError, ValueError) as error:
            raise ValueError("checkpoint.phase: unsupported") from error
        checkpoint = cls(
            story_key=value["story_key"],
            issue_id=value["issue_id"],
            phase=phase,
            sequence=value["sequence"],
            contract=ContractBinding(contract["page_id"], contract["fingerprint"]),
            delivery=CheckpointDelivery(
                delivery["branch"], delivery["pull_request_url"],
                delivery["merge_commit"], delivery["verification_sha256"],
            ),
            previous_sha256=value["previous_sha256"],
        )
        if checkpoint.canonical_bytes != raw:
            raise ValueError("checkpoint: bytes are not canonical")
        return checkpoint


@dataclass(frozen=True)
class DeliveryRecord:
    branch: str
    branch_url: str
    pull_request_url: str
    merge_commit: str
    verification_url: str
    verification_sha256: str

    def __post_init__(self) -> None:
        for name in ("branch", "branch_url", "pull_request_url", "verification_url"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name}: expected nonblank string")
        for name in ("branch_url", "pull_request_url", "verification_url"):
            if not getattr(self, name).startswith("https://"):
                raise ValueError(f"{name}: expected HTTPS URL")
        if _COMMIT.fullmatch(self.merge_commit) is None:
            raise ValueError("merge_commit: expected lowercase commit SHA")
        if _SHA256.fullmatch(self.verification_sha256) is None:
            raise ValueError("verification_sha256: expected lowercase SHA-256")

    @property
    def checkpoint_delivery(self) -> CheckpointDelivery:
        return CheckpointDelivery(
            self.branch, self.pull_request_url, self.merge_commit,
            self.verification_sha256,
        )


class HostRawByteUploader(Protocol):
    def put(
        self,
        url: str,
        headers: tuple[tuple[str, str], ...],
        data: bytes,
    ) -> None: ...


class AttachmentContentReader(Protocol):
    """Host adapter for decoding an opaque connector attachment response."""

    def read(self, response: object, *, attachment_id: str) -> bytes: ...


@dataclass(frozen=True)
class VerifiedContractBinding:
    binding: ContractBinding
    url: str
    issue_id: str
    attachment_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.binding, ContractBinding):
            raise TypeError("binding: expected ContractBinding")
        for name in ("url", "issue_id", "attachment_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name}: expected nonblank string")
        if not self.url.startswith("https://"):
            raise ValueError("url: expected HTTPS URL")


@dataclass(frozen=True)
class LinearEvidenceReplay:
    """Caller-persistable prior state for unresolved append-only writes."""

    story_key: str
    operation: str
    prior_comment_ids: tuple[str, ...] = ()
    comment_create_pending: bool = False
    pending_comment_id: str | None = None
    prior_attachment_ids: tuple[str, ...] = ()
    pending_links: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if _STORY_KEY.fullmatch(self.story_key) is None:
            raise ValueError("story_key: expected exact Elephant story marker")
        if self.operation not in {"bind_product_contract", "attach_delivery_evidence"}:
            raise ValueError("operation: expected evidence capability")
        for name in ("prior_comment_ids", "prior_attachment_ids"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or not all(
                isinstance(value, str) and value.strip() for value in values
            ):
                raise TypeError(f"{name}: expected nonblank string tuple")
            if len(set(values)) != len(values):
                raise ValueError(f"{name}: duplicate identifier")
        _optional_nonblank("pending_comment_id", self.pending_comment_id)
        if not isinstance(self.comment_create_pending, bool):
            raise TypeError("comment_create_pending: expected bool")
        if self.pending_comment_id is not None and not self.comment_create_pending:
            raise ValueError("pending_comment_id: requires pending create")
        if not isinstance(self.pending_links, tuple) or not all(
            isinstance(link, tuple)
            and len(link) == 2
            and all(isinstance(value, str) and value.strip() for value in link)
            for link in self.pending_links
        ):
            raise TypeError("pending_links: expected (title, URL) tuples")

    @classmethod
    def initial(cls, story_key: str, operation: str) -> LinearEvidenceReplay:
        return cls(story_key=story_key, operation=operation)

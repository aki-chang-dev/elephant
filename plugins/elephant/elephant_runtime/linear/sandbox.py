"""Offline values for certifying a redacted Linear sandbox transcript.

This module never invokes a connector.  It makes the tracked, redacted evidence
shape explicit so the real protocol can be run by a host and then checked both
here and by ``scripts/validate-linear-provider.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping


SANDBOX_TRANSCRIPT_SCHEMA = "elephant.linear-sandbox/v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_REDACTED = re.compile(r"redacted:[a-z0-9-]+\Z")

_DISCOVERY = (
    "mcp__codex_apps__linear_list_teams",
    "mcp__codex_apps__linear_get_team",
    "mcp__codex_apps__linear_get_user",
    "mcp__codex_apps__linear_list_issue_statuses",
    "mcp__codex_apps__linear_list_issue_labels",
)
_CLEANUP = (
    "mcp__codex_apps__linear_delete_comment",
    "mcp__codex_apps__linear_delete_attachment",
)


def _step(tool: str, phase: str, operation: str) -> tuple[str, str, str]:
    return tool, phase, operation


def _issue_operation(name: str) -> tuple[tuple[str, str, str], ...]:
    return (
        _step("mcp__codex_apps__linear_list_issues", "lookup", name),
        _step("mcp__codex_apps__linear_save_issue", "mutation", name),
        _step("mcp__codex_apps__linear_get_issue", "read_back", name),
    )


_EXPECTED = (
    tuple(_step(tool, "discovery", "capability_inventory") for tool in _DISCOVERY)
    + _issue_operation("create_story")
    + tuple(
        step
        for operation in (
            "status", "labels", "parent", "relation_add", "relation_remove", "recap", "contract_link"
        )
        for step in _issue_operation(operation)
    )
    + (
        _step("mcp__codex_apps__linear_list_issues", "lookup", "checkpoint"),
        _step("mcp__codex_apps__linear_prepare_attachment_upload", "prepare", "checkpoint"),
        _step("host_raw_signed_put", "upload", "checkpoint"),
        _step("mcp__codex_apps__linear_create_attachment_from_upload", "mutation", "checkpoint"),
        _step("mcp__codex_apps__linear_get_attachment", "read_back", "checkpoint"),
        _step("mcp__codex_apps__linear_get_issue", "read_back", "checkpoint"),
        _step("mcp__codex_apps__linear_list_comments", "lookup", "comment_create"),
        _step("mcp__codex_apps__linear_save_comment", "mutation", "comment_create"),
        _step("mcp__codex_apps__linear_list_comments", "read_back", "comment_create"),
        _step("mcp__codex_apps__linear_list_comments", "lookup", "comment_update"),
        _step("mcp__codex_apps__linear_save_comment", "mutation", "comment_update"),
        _step("mcp__codex_apps__linear_list_comments", "read_back", "comment_update"),
        _step("mcp__codex_apps__linear_list_comments", "lookup", "comment_delete"),
        _step("mcp__codex_apps__linear_delete_comment", "mutation", "comment_delete"),
        _step("mcp__codex_apps__linear_list_comments", "absence", "comment_delete"),
    )
    + _issue_operation("pr_link")
    + (
        _step("mcp__codex_apps__linear_list_diffs", "diagnostic", "pr_diff"),
        _step("mcp__codex_apps__linear_list_issues", "lookup", "attachment_cleanup"),
        _step("mcp__codex_apps__linear_delete_attachment", "mutation", "attachment_cleanup"),
        _step("mcp__codex_apps__linear_get_issue", "absence", "attachment_cleanup"),
    )
    + _issue_operation("final_cancel")
)


def _nonblank(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: expected nonblank string")
    return value


@dataclass(frozen=True)
class SandboxCheckpoint:
    """Redacted checkpoint identity; its byte digest is the upload authority."""

    id: str
    sha256: str
    size: int

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or _REDACTED.fullmatch(self.id) is None:
            raise ValueError("id: expected redacted attachment identity")
        if not isinstance(self.sha256, str) or _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("sha256: expected lowercase SHA-256")
        if not isinstance(self.size, int) or isinstance(self.size, bool) or self.size < 1:
            raise ValueError("size: expected positive integer")

    def to_value(self) -> dict[str, object]:
        return {"id": self.id, "sha256": self.sha256, "size": self.size}


@dataclass(frozen=True)
class SandboxCall:
    """One redacted, observed host call; no request payloads are retained."""

    tool: str
    phase: str
    operation: str
    result: Mapping[str, object] | None = None
    arguments: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        _nonblank("tool", self.tool)
        _nonblank("phase", self.phase)
        _nonblank("operation", self.operation)
        for name in ("result", "arguments"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, Mapping):
                raise TypeError(f"{name}: expected mapping or None")

    def to_value(self) -> dict[str, object]:
        value: dict[str, object] = {
            "tool": self.tool,
            "phase": self.phase,
            "operation": self.operation,
        }
        if self.result is not None:
            value["result"] = dict(self.result)
        if self.arguments is not None:
            value["arguments"] = dict(self.arguments)
        return value


@dataclass(frozen=True)
class LinearSandboxTranscript:
    """The exact, closed transcript accepted by the offline validator."""

    marker: str
    checkpoint: SandboxCheckpoint
    calls: tuple[SandboxCall, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.marker, str) or not self.marker.startswith("elephant-sandbox/") or _UUID.fullmatch(self.marker.rsplit("/", 1)[-1]) is None:
            raise ValueError("marker: expected sandbox UUID marker")
        if not isinstance(self.checkpoint, SandboxCheckpoint):
            raise TypeError("checkpoint: expected SandboxCheckpoint")
        if not isinstance(self.calls, tuple) or not all(isinstance(call, SandboxCall) for call in self.calls):
            raise TypeError("calls: expected SandboxCall tuple")

    def to_value(self) -> dict[str, object]:
        """Serialize only values permitted by ``validate-linear-provider.py``."""
        return {
            "schema": SANDBOX_TRANSCRIPT_SCHEMA,
            "marker": self.marker,
            "capabilities": {"read_only": list(_DISCOVERY), "sandbox_cleanup": list(_CLEANUP)},
            "checkpoint": self.checkpoint.to_value(),
            "calls": [call.to_value() for call in self.calls],
        }


def verify_linear_sandbox(transcript: LinearSandboxTranscript) -> tuple[str, ...]:
    """Check the offline protocol evidence without connector or network access.

    Cleanup is intentionally not an input field: the verifier derives it from
    the observed delete and absence calls, so a written cleanup claim cannot
    replace a call-derived proof.
    """
    if not isinstance(transcript, LinearSandboxTranscript):
        raise TypeError("transcript: expected LinearSandboxTranscript")
    errors: list[str] = []
    calls = transcript.calls
    if tuple((call.tool, call.phase, call.operation) for call in calls) != _EXPECTED:
        errors.append("calls do not match the certification protocol")
        return tuple(errors)
    _verify_authority(calls, errors)
    _verify_checkpoint(calls, transcript.checkpoint, errors)
    _verify_cleanup(calls, errors)
    _verify_final_issue(calls, errors)
    return tuple(errors)


def _verify_authority(calls: tuple[SandboxCall, ...], errors: list[str]) -> None:
    for index, call in enumerate(calls):
        if call.phase != "lookup":
            continue
        expected = 0 if call.operation in {"create_story", "comment_create"} else 1
        if dict(call.result or {}) != {"matches": expected}:
            errors.append(f"calls[{index}] lacks exact lookup authority")


def _verify_checkpoint(
    calls: tuple[SandboxCall, ...], checkpoint: SandboxCheckpoint, errors: list[str]
) -> None:
    attachment = next(call for call in calls if call.tool == "mcp__codex_apps__linear_get_attachment")
    if dict(attachment.result or {}) != checkpoint.to_value():
        errors.append("checkpoint read-back does not match its observed digest")


def _verify_cleanup(calls: tuple[SandboxCall, ...], errors: list[str]) -> None:
    comment_delete = next(call for call in calls if call.operation == "comment_delete" and call.phase == "mutation")
    comment_absence = next(call for call in calls if call.operation == "comment_delete" and call.phase == "absence")
    if dict(comment_delete.arguments or {}) != {"id": "redacted:comment-1"} or dict(comment_absence.result or {}) != {"matches": 0}:
        errors.append("comment cleanup is not call-derived")
    attachment_delete = next(call for call in calls if call.operation == "attachment_cleanup" and call.phase == "mutation")
    attachment_absence = next(call for call in calls if call.operation == "attachment_cleanup" and call.phase == "absence")
    if attachment_delete.tool != "mcp__codex_apps__linear_delete_attachment" or attachment_absence.tool != "mcp__codex_apps__linear_get_issue" or dict(attachment_absence.result or {}) != {"matches": 0}:
        errors.append("attachment cleanup is not call-derived")


def _verify_final_issue(calls: tuple[SandboxCall, ...], errors: list[str]) -> None:
    final = calls[-1].result
    if not isinstance(final, Mapping) or final.get("status") != "Canceled" or not isinstance(final.get("id"), str) or _REDACTED.fullmatch(final["id"]) is None or not isinstance(final.get("title"), str) or not final["title"].startswith("[Elephant provider certification — cleaned]"):
        errors.append("final issue is not a retained cleaned Canceled issue")

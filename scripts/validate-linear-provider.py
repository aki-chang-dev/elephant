#!/usr/bin/env python3
"""Validate a redacted Linear certification transcript without connector access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Mapping


SCHEMA = "elephant.linear-sandbox/v1"
TOOLS = frozenset({
    "mcp__codex_apps__linear_list_issues",
    "mcp__codex_apps__linear_save_issue",
    "mcp__codex_apps__linear_get_issue",
    "mcp__codex_apps__linear_list_issue_statuses",
    "mcp__codex_apps__linear_get_attachment",
    "mcp__codex_apps__linear_prepare_attachment_upload",
    "mcp__codex_apps__linear_create_attachment_from_upload",
    "mcp__codex_apps__linear_delete_attachment",
    "mcp__codex_apps__linear_list_comments",
    "mcp__codex_apps__linear_save_comment",
    "mcp__codex_apps__linear_list_diffs",
    "mcp__codex_apps__linear_get_diff",
    "mcp__codex_apps__linear_list_teams",
    "mcp__codex_apps__linear_get_team",
    "mcp__codex_apps__linear_get_user",
    "mcp__codex_apps__linear_list_issue_labels",
    "mcp__codex_apps__linear_create_issue_label",
    "host_raw_signed_put",
})
_MUTATIONS = frozenset({
    "mcp__codex_apps__linear_save_issue",
    "mcp__codex_apps__linear_create_attachment_from_upload",
    "mcp__codex_apps__linear_delete_attachment",
    "mcp__codex_apps__linear_save_comment",
})
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_FORBIDDEN_KEYS = frozenset({"token", "authorization", "signed_url", "base64", "blob", "bytes", "data"})
_SECRET_VALUE = re.compile(
    r"(?:data:[^\s]*;base64,|[?&](?:token|signature|x-amz-signature)=|\bbearer\s+|\btoken[=:])",
    re.I,
)
_BASE64_VALUE = re.compile(r"(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)\Z")


def validate_transcript(value: object) -> tuple[str, ...]:
    """Return redaction, ordering, digest, and cleanup errors for one transcript."""
    errors: list[str] = []
    _reject_secret_material(value, errors)
    if not isinstance(value, Mapping):
        return ("transcript must be an object", *errors)
    if value.get("schema") != SCHEMA:
        errors.append("unsupported transcript schema")
    marker = value.get("marker")
    if not isinstance(marker, str) or not marker.startswith("elephant-sandbox/"):
        errors.append("missing sandbox marker")
    elif _UUID.fullmatch(marker.rsplit("/", 1)[-1]) is None:
        errors.append("sandbox marker must end with UUID")
    _validate_issue(value.get("issue"), errors)
    _validate_calls(value.get("calls"), errors)
    _validate_attachments(value.get("attachments"), errors)
    _validate_cleanup(value.get("cleanup"), errors)
    return tuple(errors)


def _reject_secret_material(value: object, errors: list[str], path: str = "transcript") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                errors.append(f"{path}: non-string field name")
                continue
            child_path = f"{path}.{key}"
            if key.lower() in _FORBIDDEN_KEYS:
                errors.append(f"{child_path}: forbidden secret or raw-content field")
            _reject_secret_material(child, errors, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_material(child, errors, f"{path}[{index}]")
    elif isinstance(value, (bytes, bytearray)):
        errors.append(f"{path}: raw bytes are forbidden")
    elif isinstance(value, str):
        if _SECRET_VALUE.search(value) or _BASE64_VALUE.fullmatch(value):
            errors.append(f"{path}: secret-bearing value is forbidden")


def _validate_issue(issue: object, errors: list[str]) -> None:
    if not isinstance(issue, Mapping):
        errors.append("issue must be an object")
        return
    if not isinstance(issue.get("id"), str) or not issue["id"].startswith("redacted:"):
        errors.append("issue ID must be redacted")
    if issue.get("status") != "Canceled":
        errors.append("certification issue must be retained as Canceled")
    title = issue.get("title")
    if not isinstance(title, str) or not title.startswith("[Elephant provider certification — cleaned]"):
        errors.append("certification issue must have cleaned title")


def _validate_calls(calls: object, errors: list[str]) -> None:
    if not isinstance(calls, list) or not calls:
        errors.append("calls must be a nonempty array")
        return
    lookup_seen = False
    awaiting_read_back = False
    for index, call in enumerate(calls):
        if not isinstance(call, Mapping):
            errors.append(f"calls[{index}] must be an object")
            continue
        tool = call.get("tool")
        phase = call.get("phase")
        if tool not in TOOLS:
            errors.append(f"calls[{index}] has unknown tool")
        if phase == "lookup":
            lookup_seen = True
            if call.get("matches") not in (0, 1):
                errors.append(f"calls[{index}] has duplicate or invalid authority")
        if tool in _MUTATIONS:
            if not lookup_seen:
                errors.append(f"calls[{index}] mutates before exact lookup")
            if awaiting_read_back:
                errors.append(f"calls[{index}] mutates before prior read-back")
            awaiting_read_back = True
        elif awaiting_read_back:
            expected = (
                tool == "mcp__codex_apps__linear_get_attachment"
                if calls[index - 1].get("tool") == "mcp__codex_apps__linear_create_attachment_from_upload"
                else tool == "mcp__codex_apps__linear_get_issue"
            )
            if phase != "read_back" or not expected:
                errors.append(f"calls[{index - 1}] lacks exact read-back")
            else:
                awaiting_read_back = False
    if awaiting_read_back:
        errors.append("final mutation lacks exact read-back")


def _validate_attachments(attachments: object, errors: list[str]) -> None:
    if not isinstance(attachments, list):
        errors.append("attachments must be an array")
        return
    for index, attachment in enumerate(attachments):
        if not isinstance(attachment, Mapping):
            errors.append(f"attachments[{index}] must be an object")
            continue
        if not isinstance(attachment.get("id"), str) or not attachment["id"].startswith("redacted:"):
            errors.append(f"attachments[{index}] ID must be redacted")
        declared, observed = attachment.get("sha256"), attachment.get("read_sha256")
        if not isinstance(declared, str) or _SHA256.fullmatch(declared) is None:
            errors.append(f"attachments[{index}] has invalid SHA-256")
        if declared != observed:
            errors.append(f"attachments[{index}] SHA-256 read-back mismatch")


def _validate_cleanup(cleanup: object, errors: list[str]) -> None:
    if not isinstance(cleanup, Mapping):
        errors.append("cleanup must be an object")
        return
    for field in ("relations_absent", "comments_absent", "attachments_absent", "issue_retained_canceled"):
        if cleanup.get(field) is not True:
            errors.append(f"cleanup.{field} must be true")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path)
    args = parser.parse_args()
    try:
        value = json.loads(args.transcript.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Linear provider sandbox certification failed: {type(error).__name__}.")
        return 1
    errors = validate_transcript(value)
    if errors:
        print("Linear provider sandbox certification failed.")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Linear provider sandbox certification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

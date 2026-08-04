#!/usr/bin/env python3
"""Validate the closed, redacted Linear sandbox transcript without network access."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import re
from typing import Mapping


SCHEMA = "elephant.linear-sandbox/v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_REDACTED = re.compile(r"redacted:[a-z0-9-]+\Z")
_FORBIDDEN_KEY = re.compile(r"(?:oauth|token|authorization|signed|signature|base64|blob|bytes|payload|content|data)", re.I)
_SECRET = re.compile(r"(?:data:[^\s]*;base64,|\bbearer\s+|\b(?:oauth|token|authorization)[=:]|[?&](?:token|signature|x-amz-[^=]+)=)", re.I)
_BASE64 = re.compile(r"(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)\Z")
_BASE64_UNPADDED = re.compile(r"[A-Za-z0-9+/]{7,}\Z")

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
    + tuple(step for operation in ("status", "labels", "parent", "relation_add", "relation_remove", "recap", "contract_link") for step in _issue_operation(operation))
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


def validate_transcript(value: object) -> tuple[str, ...]:
    errors: list[str] = []
    _secrets(value, errors)
    if not isinstance(value, Mapping):
        return ("transcript must be an object", *errors)
    _closed_fields(value, {"schema", "marker", "capabilities", "checkpoint", "calls"}, "transcript", errors)
    if value.get("schema") != SCHEMA:
        errors.append("unsupported transcript schema")
    marker = value.get("marker")
    if not isinstance(marker, str) or not marker.startswith("elephant-sandbox/") or _UUID.fullmatch(marker.rsplit("/", 1)[-1]) is None:
        errors.append("invalid sandbox marker")
    _capabilities(value.get("capabilities"), errors)
    checkpoint = _checkpoint(value.get("checkpoint"), errors)
    _calls(value.get("calls"), checkpoint, errors)
    return tuple(errors)


def _closed_fields(value: Mapping[object, object], allowed: set[str], path: str, errors: list[str]) -> None:
    for key in value:
        if not isinstance(key, str) or key not in allowed:
            errors.append(f"{path}: unknown field")


def _secrets(value: object, errors: list[str], path: str = "transcript") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                errors.append(f"{path}: non-string field")
                continue
            if _FORBIDDEN_KEY.search(key):
                errors.append(f"{path}.{key}: forbidden secret/raw-content field")
            _secrets(child, errors, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _secrets(child, errors, f"{path}[{index}]")
    elif isinstance(value, (bytes, bytearray)):
        errors.append(f"{path}: raw bytes forbidden")
    elif isinstance(value, str) and (_SECRET.search(value) or _looks_base64(value)):
        errors.append(f"{path}: secret/base64 value forbidden")


def _looks_base64(value: str) -> bool:
    if _SHA256.fullmatch(value) is not None:
        return False
    if _BASE64.fullmatch(value) is not None:
        return True
    if _BASE64_UNPADDED.fullmatch(value) is None or not any(character.isdigit() or character in "+/" for character in value):
        return False
    try:
        base64.b64decode(value + "=" * (-len(value) % 4), validate=True)
    except ValueError:
        return False
    return True


def _capabilities(value: object, errors: list[str]) -> None:
    if not isinstance(value, Mapping):
        errors.append("capabilities must be an object")
        return
    _closed_fields(value, {"read_only", "sandbox_cleanup"}, "capabilities", errors)
    for field, expected in (("read_only", _DISCOVERY), ("sandbox_cleanup", _CLEANUP)):
        actual = value.get(field)
        if not isinstance(actual, list) or tuple(actual) != expected:
            errors.append(f"capabilities.{field} differs")


def _checkpoint(value: object, errors: list[str]) -> tuple[str, str, int] | None:
    if not isinstance(value, Mapping):
        errors.append("checkpoint must be an object")
        return None
    _closed_fields(value, {"id", "sha256", "size"}, "checkpoint", errors)
    attachment_id, digest, size = value.get("id"), value.get("sha256"), value.get("size")
    if not isinstance(attachment_id, str) or _REDACTED.fullmatch(attachment_id) is None or not isinstance(digest, str) or _SHA256.fullmatch(digest) is None or not isinstance(size, int) or isinstance(size, bool) or size < 1:
        errors.append("checkpoint has invalid identity, digest, or size")
        return None
    return attachment_id, digest, size


def _calls(value: object, checkpoint: tuple[str, str, int] | None, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("calls must be an array")
        return
    if len(value) != len(_EXPECTED):
        errors.append("calls do not contain the complete certification sequence")
    for index, expected in enumerate(_EXPECTED):
        if index >= len(value):
            break
        call = value[index]
        if not isinstance(call, Mapping):
            errors.append(f"calls[{index}] must be an object")
            continue
        allowed = {"tool", "phase", "operation"}
        if expected[2] in {"checkpoint", "comment_create", "comment_update", "comment_delete", "create_story", "attachment_cleanup", "final_cancel"} or expected[1] in {"lookup", "diagnostic", "absence", "read_back"}:
            allowed.add("result")
        if expected == _step("mcp__codex_apps__linear_delete_comment", "mutation", "comment_delete"):
            allowed.add("arguments")
        _closed_fields(call, allowed, f"calls[{index}]", errors)
        if tuple(call.get(field) for field in ("tool", "phase", "operation")) != expected:
            errors.append(f"calls[{index}] violates certification order")
        _result(call.get("result"), expected, index, checkpoint, errors)
        if expected[2] == "comment_delete" and expected[1] == "mutation":
            arguments = call.get("arguments")
            if not isinstance(arguments, Mapping) or set(arguments) != {"id"} or not isinstance(arguments.get("id"), str) or _REDACTED.fullmatch(arguments["id"]) is None:
                errors.append("comment delete requires one redacted id argument")
    if value and len(value) == len(_EXPECTED):
        final = value[-1].get("result") if isinstance(value[-1], Mapping) else None
        if not isinstance(final, Mapping) or final.get("status") != "Canceled" or not isinstance(final.get("title"), str) or not final["title"].startswith("[Elephant provider certification — cleaned]") or not isinstance(final.get("id"), str) or _REDACTED.fullmatch(final["id"]) is None:
            errors.append("final issue read-back is not cleaned and Canceled")


def _result(value: object, expected: tuple[str, str, str], index: int, checkpoint: tuple[str, str, int] | None, errors: list[str]) -> None:
    tool, phase, operation = expected
    if phase == "lookup":
        wanted = 0 if operation in {"create_story", "comment_create"} else 1
        if not isinstance(value, Mapping) or set(value) != {"matches"} or value.get("matches") != wanted:
            errors.append(f"calls[{index}] has invalid authority lookup")
    elif tool == "mcp__codex_apps__linear_get_attachment":
        if not isinstance(value, Mapping) or set(value) != {"id", "sha256", "size"} or checkpoint is None or tuple(value.get(field) for field in ("id", "sha256", "size")) != checkpoint:
            errors.append(f"calls[{index}] has invalid attachment digest/size")
    elif operation.startswith("comment_") and phase in {"read_back", "absence"}:
        wanted = 0 if phase == "absence" else 1
        if not isinstance(value, Mapping) or set(value) != {"matches"} or value.get("matches") != wanted:
            errors.append(f"calls[{index}] has invalid comment read-back")
    elif operation == "pr_diff":
        if not isinstance(value, Mapping) or set(value) != {"code"} or value.get("code") not in {"configuration_missing", "connector_capability_missing"}:
            errors.append(f"calls[{index}] has invalid native diff evidence")


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

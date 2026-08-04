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
_EMPTY_RELATIONS = {
    "blocks": 0,
    "blocked_by": 0,
    "related_to": 0,
    "duplicate_of": 0,
}


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
        _step("mcp__codex_apps__linear_delete_attachment", "mutation", "checkpoint_cleanup"),
        _step("mcp__codex_apps__linear_delete_attachment", "mutation", "contract_link_cleanup"),
        _step("mcp__codex_apps__linear_delete_attachment", "mutation", "pr_link_cleanup"),
        _step("mcp__codex_apps__linear_get_issue", "absence", "attachment_cleanup"),
    )
    + _issue_operation("final_cancel")
)


def validate_transcript(value: object) -> tuple[str, ...]:
    errors: list[str] = []
    _secrets(value, errors)
    if not isinstance(value, Mapping):
        return ("transcript must be an object", *errors)
    _closed_fields(value, {"schema", "marker", "capabilities", "checkpoint", "cleanup", "calls"}, "transcript", errors)
    if value.get("schema") != SCHEMA:
        errors.append("unsupported transcript schema")
    marker = value.get("marker")
    if not isinstance(marker, str) or not marker.startswith("elephant-sandbox/") or _UUID.fullmatch(marker.rsplit("/", 1)[-1]) is None:
        errors.append("invalid sandbox marker")
    _capabilities(value.get("capabilities"), errors)
    checkpoint = _checkpoint(value.get("checkpoint"), errors)
    cleanup = _cleanup(value.get("cleanup"), checkpoint, errors)
    _calls(value.get("calls"), marker, checkpoint, cleanup, errors)
    return tuple(errors)


def _closed_fields(value: Mapping[object, object], allowed: set[str], path: str, errors: list[str]) -> None:
    for key in value:
        if not isinstance(key, str) or key not in allowed:
            errors.append(f"{path}: unknown field")


def _empty_relations(value: object) -> bool:
    return isinstance(value, Mapping) and set(value) == set(_EMPTY_RELATIONS) and all(
        isinstance(value.get(name), int) and not isinstance(value.get(name), bool)
        and value[name] == 0
        for name in _EMPTY_RELATIONS
    )


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


def _cleanup(
    value: object, checkpoint: tuple[str, str, int] | None, errors: list[str]
) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        errors.append("cleanup must be an object")
        return None
    _closed_fields(value, {"anchors", "attachments"}, "cleanup", errors)
    anchors = value.get("anchors")
    attachments = value.get("attachments")
    if not isinstance(anchors, Mapping):
        errors.append("cleanup.anchors must be an object")
    else:
        _closed_fields(anchors, {"anchor_1", "anchor_2"}, "cleanup.anchors", errors)
        for name in ("anchor_1", "anchor_2"):
            anchor = anchors.get(name)
            if not isinstance(anchor, Mapping):
                errors.append(f"cleanup.anchors.{name} must be an object")
                continue
            _closed_fields(anchor, {"id", "relations", "restored"}, f"cleanup.anchors.{name}", errors)
            if not isinstance(anchor.get("id"), str) or _REDACTED.fullmatch(anchor["id"]) is None:
                errors.append(f"cleanup.anchors.{name} has invalid redacted identity")
            if not _empty_relations(anchor.get("relations")) or anchor.get("restored") is not True:
                errors.append(f"cleanup.anchors.{name} is not restored and empty")
        if isinstance(anchors.get("anchor_1"), Mapping) and isinstance(anchors.get("anchor_2"), Mapping) and anchors["anchor_1"].get("id") == anchors["anchor_2"].get("id"):
            errors.append("cleanup anchors must be distinct")
    if not isinstance(attachments, Mapping):
        errors.append("cleanup.attachments must be an object")
        return None
    _closed_fields(attachments, {"checkpoint", "contract_link", "pr_link"}, "cleanup.attachments", errors)
    for name in ("checkpoint", "contract_link", "pr_link"):
        attachment_id = attachments.get(name)
        if not isinstance(attachment_id, str) or _REDACTED.fullmatch(attachment_id) is None:
            errors.append(f"cleanup.attachments.{name} has invalid redacted identity")
    if checkpoint is not None and attachments.get("checkpoint") != checkpoint[0]:
        errors.append("cleanup checkpoint identity does not match checkpoint evidence")
    if len({attachments.get(name) for name in ("checkpoint", "contract_link", "pr_link")}) != 3:
        errors.append("cleanup attachment identities must be distinct")
    return {"anchors": anchors, "attachments": attachments}


def _calls(
    value: object,
    marker: object,
    checkpoint: tuple[str, str, int] | None,
    cleanup: dict[str, object] | None,
    errors: list[str],
) -> None:
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
        if expected[2] in {"checkpoint", "comment_create", "comment_update", "comment_delete", "create_story", "attachment_cleanup", "final_cancel", "relation_remove"} or expected[1] in {"lookup", "diagnostic", "absence", "read_back"}:
            allowed.add("result")
        if expected == _step("mcp__codex_apps__linear_delete_comment", "mutation", "comment_delete") or expected[1] == "mutation" and expected[0] == "mcp__codex_apps__linear_delete_attachment":
            allowed.add("arguments")
        _closed_fields(call, allowed, f"calls[{index}]", errors)
        if tuple(call.get(field) for field in ("tool", "phase", "operation")) != expected:
            errors.append(f"calls[{index}] violates certification order")
        _result(call.get("result"), expected, index, marker, checkpoint, cleanup, errors)
        if expected[2] == "comment_delete" and expected[1] == "mutation":
            arguments = call.get("arguments")
            if not isinstance(arguments, Mapping) or set(arguments) != {"id"} or not isinstance(arguments.get("id"), str) or _REDACTED.fullmatch(arguments["id"]) is None:
                errors.append("comment delete requires one redacted id argument")
        if expected[1] == "mutation" and expected[0] == "mcp__codex_apps__linear_delete_attachment":
            attachment_key = {
                "checkpoint_cleanup": "checkpoint",
                "contract_link_cleanup": "contract_link",
                "pr_link_cleanup": "pr_link",
            }[expected[2]]
            attachments = cleanup.get("attachments") if cleanup is not None else None
            arguments = call.get("arguments")
            if not isinstance(attachments, Mapping) or not isinstance(arguments, Mapping) or set(arguments) != {"id"} or arguments.get("id") != attachments.get(attachment_key):
                errors.append(f"calls[{index}] does not delete its owned {attachment_key} attachment")
    if value and len(value) == len(_EXPECTED):
        final = value[-1].get("result") if isinstance(value[-1], Mapping) else None
        suffix = marker.rsplit("/", 1)[-1][-12:] if isinstance(marker, str) else None
        expected_final = {
            "id": "redacted:issue-1",
            "title": f"[Elephant provider certification — cleaned] {suffix}",
            "status": "Canceled",
            "labels": [],
            "parent": None,
            "attachments": 0,
            "comments": 0,
            "relations": _EMPTY_RELATIONS,
        }
        if final != expected_final or not _exact_final_counts(final):
            errors.append("final issue read-back is not an exact cleaned snapshot")


def _result(
    value: object,
    expected: tuple[str, str, str],
    index: int,
    marker: object,
    checkpoint: tuple[str, str, int] | None,
    cleanup: dict[str, object] | None,
    errors: list[str],
) -> None:
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
    elif operation == "relation_remove" and phase == "read_back":
        anchors = cleanup.get("anchors") if cleanup is not None else None
        expected_result = {"parent": None, "relations": _EMPTY_RELATIONS, "anchors": anchors}
        if value != expected_result or not isinstance(value, Mapping) or not _empty_relations(value.get("relations")):
            errors.append(f"calls[{index}] does not prove restored empty relations")
    elif operation == "attachment_cleanup" and phase == "absence":
        attachments = cleanup.get("attachments") if cleanup is not None else None
        absent = list(attachments.values()) if isinstance(attachments, Mapping) else None
        if value != {"attachments": 0, "absent": absent} or not isinstance(value, Mapping) or not isinstance(value.get("attachments"), int) or isinstance(value.get("attachments"), bool):
            errors.append(f"calls[{index}] does not prove owned attachment absence")


def _exact_final_counts(value: object) -> bool:
    return isinstance(value, Mapping) and all(
        isinstance(value.get(name), int) and not isinstance(value.get(name), bool)
        and value[name] == 0
        for name in ("attachments", "comments")
    ) and _empty_relations(value.get("relations"))


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

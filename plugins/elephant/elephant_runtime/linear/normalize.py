"""Strict conversion of Linear connector evidence into immutable values."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import re

from elephant_runtime.workspace_core import DriftKind

from .models import (
    LinearAttachment,
    LinearComment,
    LinearDiff,
    LinearDrift,
    LinearIssue,
    LinearLabel,
    LinearRelation,
    LinearStatus,
    LinearTeam,
    PageCursor,
)


_STORY_MARKER = re.compile(r"elephant-story/v1/[0-9a-f]{64}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_STORY_FOOTER = re.compile(
    r"(?:^|\n)---\n"
    r"Elephant story key: `(?P<story>elephant-story/v1/[0-9a-f]{64})`\n"
    r"Elephant recap SHA-256: `(?P<recap>[0-9a-f]{64})`(?=\n|$)"
)
_MARKER_LINE = re.compile(r"^Elephant (?:story key|recap SHA-256):", re.MULTILINE)


def _mapping(name: str, value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name}: expected mapping")
    return value


def _list(name: str, value: object) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{name}: expected list")
    return value


def _string(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: expected nonblank string")
    return value


def _optional_string(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _string(name, value)


def _unique_ids(name: str, values: tuple[object, ...]) -> None:
    ids = tuple(getattr(value, "id", None) for value in values)
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate {name} opaque ID")


def normalize_team(raw: object) -> LinearTeam:
    value = _mapping("team", raw)
    members = _list("members", value.get("members", []))
    member_ids: list[str] = []
    for member in members:
        member_ids.append(_string("member.id", _mapping("member", member).get("id")))
    if len(set(member_ids)) != len(member_ids):
        raise ValueError("duplicate member opaque ID")
    return LinearTeam(
        id=_string("team.id", value.get("id")),
        name=_string("team.name", value.get("name")),
        key=_string("team.key", value.get("key")),
        member_ids=tuple(member_ids),
    )


def normalize_status(raw: object) -> LinearStatus:
    value = _mapping("status", raw)
    return LinearStatus(
        id=_string("status.id", value.get("id")),
        name=_string("status.name", value.get("name")),
        type=_string("status.type", value.get("type")),
    )


def normalize_label(raw: object) -> LinearLabel:
    value = _mapping("label", raw)
    parent = value.get("parent")
    if parent is None:
        group_id = group_name = None
    else:
        parent_value = _mapping("label.parent", parent)
        group_id = _string("label.parent.id", parent_value.get("id"))
        group_name = _string("label.parent.name", parent_value.get("name"))
    return LinearLabel(
        id=_string("label.id", value.get("id")),
        name=_string("label.name", value.get("name")),
        group_id=group_id,
        group_name=group_name,
    )


def normalize_attachment(raw: object) -> LinearAttachment:
    value = _mapping("attachment", raw)
    return LinearAttachment(
        id=_string("attachment.id", value.get("id")),
        url=_string("attachment.url", value.get("url")),
        title=_string("attachment.title", value.get("title")),
    )


def normalize_comment(raw: object) -> LinearComment:
    value = _mapping("comment", raw)
    body = value.get("body")
    if not isinstance(body, str):
        raise TypeError("comment.body: expected string")
    return LinearComment(id=_string("comment.id", value.get("id")), body=body)


def _issue_reference(name: str, raw: object) -> tuple[str | None, str | None]:
    if raw is None:
        return None, None
    value = _mapping(name, raw)
    return _string(f"{name}.id", value.get("id")), _string(
        f"{name}.identifier", value.get("identifier")
    )


def normalize_diff(raw: object) -> LinearDiff:
    value = _mapping("diff", raw)
    issue_id, issue_identifier = _issue_reference("diff.issue", value.get("issue"))
    return LinearDiff(
        id=_string("diff.id", value.get("id")),
        url=_string("diff.url", value.get("url")),
        issue_id=issue_id,
        issue_identifier=issue_identifier,
    )


def _normalize_relation(raw: object) -> LinearRelation:
    value = _mapping("relation", raw)
    issue_id, issue_identifier = _issue_reference("relation.issue", value.get("issue"))
    assert issue_id is not None and issue_identifier is not None
    return LinearRelation(
        id=_string("relation.id", value.get("id")),
        type=_string("relation.type", value.get("type")),
        issue_id=issue_id,
        issue_identifier=issue_identifier,
    )


def parse_story_marker(description: object) -> tuple[str, str] | None:
    """Return the unique exact marker footer, rejecting partial or repeated authority."""
    if not isinstance(description, str):
        raise TypeError("description: expected string")
    matches = tuple(_STORY_FOOTER.finditer(description))
    if not matches:
        if _MARKER_LINE.search(description):
            raise ValueError("malformed Elephant story marker footer")
        return None
    if len(matches) != 1:
        raise ValueError("multiple Elephant story marker footers")
    match = matches[0]
    trailing = description[match.end():]
    if trailing not in {"", "\n"}:
        raise ValueError("malformed Elephant story marker footer")
    if len(tuple(_MARKER_LINE.finditer(description))) != 2:
        raise ValueError("malformed Elephant story marker footer")
    story_key = match.group("story")
    recap_digest = match.group("recap")
    if _STORY_MARKER.fullmatch(story_key) is None or _SHA256.fullmatch(recap_digest) is None:
        raise ValueError("malformed Elephant story marker footer")
    return story_key, recap_digest


def normalize_issue(raw: object, *, include_relations: bool = False) -> LinearIssue:
    value = _mapping("issue", raw)
    team = _mapping("issue.team", value.get("team"))
    labels = tuple(normalize_label(item) for item in _list("labels", value.get("labels", [])))
    attachments = tuple(
        normalize_attachment(item) for item in _list("attachments", value.get("attachments", []))
    )
    history: list[tuple[str, str]] = []
    for entry in _list("stateHistory", value.get("stateHistory", [])):
        entry_value = _mapping("stateHistory item", entry)
        history.append(
            (
                _string("stateHistory.id", entry_value.get("id")),
                normalize_status(entry_value.get("state")).id,
            )
        )
    if len({entry_id for entry_id, _ in history}) != len(history):
        raise ValueError("duplicate state history opaque ID")
    if include_relations:
        if "relations" not in value:
            raise ValueError("relations: required when include_relations is true")
        relations = tuple(
            _normalize_relation(item) for item in _list("relations", value.get("relations"))
        )
        _unique_ids("relation", relations)
    elif "relations" in value:
        relations = tuple(_normalize_relation(item) for item in _list("relations", value["relations"]))
        _unique_ids("relation", relations)
    else:
        relations = None
    priority = value.get("priority")
    if priority is not None and (not isinstance(priority, int) or isinstance(priority, bool)):
        raise TypeError("priority: expected int or None")
    description = value.get("description", "")
    if not isinstance(description, str):
        raise TypeError("description: expected string")
    parse_story_marker(description)
    _unique_ids("label", labels)
    _unique_ids("attachment", attachments)
    return LinearIssue(
        id=_string("issue.id", value.get("id")),
        identifier=_string("issue.identifier", value.get("identifier")),
        title=_string("issue.title", value.get("title")),
        description=description,
        team_id=_string("issue.team.id", team.get("id")),
        state=normalize_status(value.get("state")),
        labels=labels,
        attachments=attachments,
        state_history=tuple(history),
        relations=relations,
        priority=priority,
    )


def normalize_page(
    raw: object,
    normalize_value: Callable[[object], object],
    *,
    seen_cursors: tuple[str, ...] = (),
) -> PageCursor:
    value = _mapping("page", raw)
    data = _list("data", value.get("data"))
    page_info = _mapping("pageInfo", value.get("pageInfo"))
    has_next = page_info.get("hasNextPage")
    if not isinstance(has_next, bool):
        raise TypeError("pageInfo.hasNextPage: expected bool")
    next_cursor = _optional_string("pageInfo.endCursor", page_info.get("endCursor"))
    if has_next != (next_cursor is not None):
        raise ValueError("pageInfo: cursor does not match hasNextPage")
    if next_cursor is not None:
        if not isinstance(seen_cursors, tuple) or not all(
            isinstance(cursor, str) and cursor.strip() for cursor in seen_cursors
        ):
            raise TypeError("seen_cursors: expected tuple of nonblank strings")
        if next_cursor in seen_cursors:
            raise ValueError("cursor loop")
    values = tuple(normalize_value(item) for item in data)
    _unique_ids("page", values)
    marker_values = tuple(
        parse_story_marker(item.description)
        for item in values
        if isinstance(item, LinearIssue) and parse_story_marker(item.description) is not None
    )
    if len(set(marker_values)) != len(marker_values):
        raise ValueError("duplicate stable marker")
    return PageCursor(values=values, next_cursor=next_cursor)


def classify_drift(
    matches: tuple[LinearIssue, ...],
    *,
    expected_story_key: str | None = None,
    expected_team_id: str | None = None,
    expected_product_label_id: str | None = None,
    expected_kind_label_id: str | None = None,
    verified_status_ids: tuple[str, ...] = (),
    expected_recap_digest: str | None = None,
    checkpoint_verified: bool = True,
    reciprocal_link_verified: bool = True,
) -> LinearDrift | None:
    """Classify deterministic evidence drift using only existing workspace-core values."""
    if not isinstance(matches, tuple) or not all(isinstance(item, LinearIssue) for item in matches):
        raise TypeError("matches: expected LinearIssue tuple")
    if not matches:
        return LinearDrift(DriftKind.DUPLICATE_AUTHORITY, "missing_authoritative_story_key")
    if len(matches) != 1:
        return LinearDrift(DriftKind.DUPLICATE_AUTHORITY, "duplicate_authoritative_story_key")
    issue = matches[0]
    if expected_story_key is not None:
        if _STORY_MARKER.fullmatch(expected_story_key) is None:
            raise ValueError("expected_story_key: expected exact story marker")
        parsed = parse_story_marker(issue.description)
        if parsed is None or parsed[0] != expected_story_key:
            return LinearDrift(DriftKind.APPROVED_CONTRACT_CHANGED, "story_key")
    if expected_team_id is not None and issue.team_id != _string("expected_team_id", expected_team_id):
        return LinearDrift(DriftKind.PRODUCT_ASSIGNMENT_CHANGED, "team_id")
    expected_labels = (expected_product_label_id, expected_kind_label_id)
    for expected_label in expected_labels:
        if expected_label is not None and _string("expected_label_id", expected_label) not in {
            label.id for label in issue.labels
        }:
            return LinearDrift(DriftKind.PRODUCT_ASSIGNMENT_CHANGED, "label_id")
    if not isinstance(verified_status_ids, tuple) or not all(
        isinstance(status_id, str) and status_id.strip() for status_id in verified_status_ids
    ):
        raise TypeError("verified_status_ids: expected tuple of nonblank strings")
    if verified_status_ids and issue.state.id not in verified_status_ids:
        return LinearDrift(DriftKind.HUMAN_STATUS_ADVANCED, "state_id")
    if expected_recap_digest is not None:
        if _SHA256.fullmatch(expected_recap_digest) is None:
            raise ValueError("expected_recap_digest: expected lowercase SHA-256")
        parsed = parse_story_marker(issue.description)
        if parsed is None or parsed[1] != expected_recap_digest:
            return LinearDrift(DriftKind.STALE_RECAP, "recap_sha256")
    if not isinstance(checkpoint_verified, bool) or not isinstance(reciprocal_link_verified, bool):
        raise TypeError("verification flags: expected bool")
    if not checkpoint_verified:
        return LinearDrift(DriftKind.VERIFIED_CHECKPOINT_LAG, "checkpoint")
    if not reciprocal_link_verified:
        return LinearDrift(DriftKind.MISSING_RECIPROCAL_LINK, "reciprocal_link")
    return None

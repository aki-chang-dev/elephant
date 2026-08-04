"""Strict conversion of decoded Linear connector payloads into frozen evidence."""

from __future__ import annotations

from collections.abc import Mapping
import re

from elephant_runtime.workspace_core import DriftKind

from .models import (
    LinearAttachment,
    LinearAuthorityMissing,
    LinearComment,
    LinearDiff,
    LinearDrift,
    LinearIssue,
    LinearLabel,
    LinearRelation,
    LinearRelations,
    LinearStateHistory,
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


def _cursor(value: Mapping[str, object], *, seen_cursors: tuple[str, ...]) -> str | None:
    has_next = value.get("hasNextPage")
    if not isinstance(has_next, bool):
        raise TypeError("hasNextPage: expected bool")
    cursor = _optional_string("cursor", value.get("cursor"))
    if has_next != (cursor is not None):
        raise ValueError("cursor: must be present exactly when hasNextPage is true")
    if not isinstance(seen_cursors, tuple) or not all(
        isinstance(item, str) and item.strip() for item in seen_cursors
    ):
        raise TypeError("seen_cursors: expected tuple of nonblank strings")
    if cursor is not None and cursor in seen_cursors:
        raise ValueError("cursor loop")
    return cursor


def _collection(
    raw: object,
    *,
    name: str,
    normalizer: object,
    seen_cursors: tuple[str, ...] = (),
) -> PageCursor:
    value = _mapping(name, raw)
    normalizer_callable = normalizer
    if not callable(normalizer_callable):
        raise TypeError("normalizer: expected callable")
    values = tuple(normalizer_callable(item) for item in _list(name, value.get(name)))
    _unique_ids(name, values)
    return PageCursor(values=values, next_cursor=_cursor(value, seen_cursors=seen_cursors))


def normalize_team(raw: object, *, require_key: bool = False) -> LinearTeam:
    value = _mapping("team", raw)
    key = _optional_string("team.key", value.get("key"))
    if require_key and key is None:
        raise ValueError("team.key: required for user membership")
    return LinearTeam(
        id=_string("team.id", value.get("id")),
        name=_string("team.name", value.get("name")),
        key=key,
    )


def normalize_teams(raw: object, *, seen_cursors: tuple[str, ...] = ()) -> PageCursor:
    return _collection(raw, name="teams", normalizer=normalize_team, seen_cursors=seen_cursors)


def normalize_user_teams(raw: object) -> tuple[LinearTeam, ...]:
    value = _mapping("user", raw)
    _string("user.id", value.get("id"))
    teams = tuple(normalize_team(item, require_key=True) for item in _list("user.teams", value.get("teams")))
    _unique_ids("user team", teams)
    return teams


def normalize_status(raw: object) -> LinearStatus:
    value = _mapping("status", raw)
    return LinearStatus(
        id=_string("status.id", value.get("id")),
        name=_string("status.name", value.get("name")),
        type=_string("status.type", value.get("type")),
    )


def normalize_issue_statuses(raw: object) -> tuple[LinearStatus, ...]:
    statuses = tuple(normalize_status(item) for item in _list("statuses", raw))
    _unique_ids("status", statuses)
    return statuses


def normalize_label(raw: object) -> LinearLabel:
    value = _mapping("label", raw)
    return LinearLabel(
        id=_string("label.id", value.get("id")),
        name=_string("label.name", value.get("name")),
        color=_optional_string("label.color", value.get("color")),
        description=_optional_string("label.description", value.get("description")),
    )


def normalize_issue_labels(raw: object, *, seen_cursors: tuple[str, ...] = ()) -> PageCursor:
    return _collection(raw, name="labels", normalizer=normalize_label, seen_cursors=seen_cursors)


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
    return LinearComment(
        id=_string("comment.id", value.get("id")),
        body=body,
        quoted_text=_optional_string("comment.quotedText", value.get("quotedText")),
    )


def normalize_comments(raw: object, *, seen_cursors: tuple[str, ...] = ()) -> PageCursor:
    return _collection(raw, name="comments", normalizer=normalize_comment, seen_cursors=seen_cursors)


def normalize_diff(raw: object) -> LinearDiff:
    value = _mapping("diff", raw)
    return LinearDiff(
        id=_string("diff.id", value.get("id")),
        url=_string("diff.url", value.get("url")),
        issue_identifier=_optional_string(
            "diff.issueIdentifier", value.get("issueIdentifier")
        ),
    )


def normalize_diffs(raw: object, *, seen_cursors: tuple[str, ...] = ()) -> PageCursor:
    return _collection(raw, name="diffs", normalizer=normalize_diff, seen_cursors=seen_cursors)


def parse_story_marker(description: object) -> tuple[str, str] | None:
    """Return the one exact footer authority; reject malformed or repeated footers."""
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
    if description[match.end():] not in {"", "\n"} or len(tuple(_MARKER_LINE.finditer(description))) != 2:
        raise ValueError("malformed Elephant story marker footer")
    return match.group("story"), match.group("recap")


def _normalize_priority(raw: object) -> tuple[int, str] | None:
    if raw is None:
        return None
    value = _mapping("priority", raw)
    priority = value.get("value")
    if not isinstance(priority, int) or isinstance(priority, bool):
        raise TypeError("priority.value: expected int")
    return priority, _string("priority.name", value.get("name"))


def _normalize_history(raw: object) -> LinearStateHistory:
    value = _mapping("stateHistory item", raw)
    return LinearStateHistory(
        state=normalize_status(value.get("state")),
        started_at=_string("stateHistory.startedAt", value.get("startedAt")),
        ended_at=_optional_string("stateHistory.endedAt", value.get("endedAt")),
    )


def _relation_values(name: str, relation_type: str, raw: object) -> tuple[LinearRelation, ...]:
    values = tuple(
        LinearRelation(relation_type, _string(name, item)) for item in _list(name, raw)
    )
    if len({value.issue_id for value in values}) != len(values):
        raise ValueError(f"{name}: duplicate opaque ID")
    return values


def _normalize_relations(raw: object) -> LinearRelations:
    value = _mapping("relations", raw)
    required = {"blocks", "blockedBy", "relatedTo", "duplicateOf"}
    missing = required - set(value)
    if missing:
        raise ValueError(f"relations.{sorted(missing)[0]}: required")
    return LinearRelations(
        blocks=_relation_values("relations.blocks", "blocks", value["blocks"]),
        blocked_by=_relation_values("relations.blockedBy", "blockedBy", value["blockedBy"]),
        related_to=_relation_values("relations.relatedTo", "relatedTo", value["relatedTo"]),
        duplicate_of=(
            None
            if value["duplicateOf"] is None
            else LinearRelation(
                "duplicateOf",
                _string("relations.duplicateOf", value["duplicateOf"]),
            )
        ),
    )


def normalize_issue(raw: object, *, include_relations: bool = False) -> LinearIssue:
    value = _mapping("issue", raw)
    description = value.get("description")
    if not isinstance(description, str):
        raise TypeError("issue.description: expected string")
    parse_story_marker(description)
    labels = tuple(_string("issue.labels", item) for item in _list("issue.labels", value.get("labels")))
    if len(set(labels)) != len(labels):
        raise ValueError("issue.labels: duplicate name")
    attachments = None
    if "attachments" in value:
        attachments = tuple(normalize_attachment(item) for item in _list("issue.attachments", value["attachments"]))
        _unique_ids("attachment", attachments)
    state_history = None
    if "stateHistory" in value:
        state_history = tuple(_normalize_history(item) for item in _list("issue.stateHistory", value["stateHistory"]))
    status_id = None
    if state_history is not None:
        current_states = tuple(item for item in state_history if item.ended_at is None)
        if len(current_states) != 1:
            raise ValueError("stateHistory: expected exactly one current state")
        current = current_states[0].state
        if current.name != _string("issue.status", value.get("status")) or current.type != _string("issue.statusType", value.get("statusType")):
            raise ValueError("stateHistory: current state does not match issue status")
        status_id = current.id
    if include_relations and "relations" not in value:
        raise ValueError("relations: required when include_relations is true")
    if include_relations and state_history is None:
        raise ValueError("stateHistory: required for detailed issue")
    relations = _normalize_relations(value["relations"]) if "relations" in value else None
    return LinearIssue(
        id=_string("issue.id", value.get("id")),
        title=_string("issue.title", value.get("title")),
        description=description,
        team_id=_string("issue.teamId", value.get("teamId")),
        team_name=_string("issue.team", value.get("team")),
        status_name=_string("issue.status", value.get("status")),
        status_type=_string("issue.statusType", value.get("statusType")),
        labels=labels,
        priority=_normalize_priority(value.get("priority")),
        url=_optional_string("issue.url", value.get("url")),
        attachments=attachments,
        state_history=state_history,
        relations=relations,
        status_id=status_id,
        project_id=_optional_string("issue.projectId", value.get("projectId")),
        parent_id=_optional_string("issue.parentId", value.get("parentId")),
        identifier=_optional_string("issue.identifier", value.get("identifier")),
    )


def normalize_issues(raw: object, *, seen_cursors: tuple[str, ...] = ()) -> PageCursor:
    page = _collection(raw, name="issues", normalizer=normalize_issue, seen_cursors=seen_cursors)
    story_keys = tuple(
        marker[0]
        for issue in page.values
        if isinstance(issue, LinearIssue)
        and (marker := parse_story_marker(issue.description)) is not None
    )
    if len(set(story_keys)) != len(story_keys):
        raise ValueError("duplicate stable marker")
    return page


def _configured_label_names(
    inventory: object,
    group_label_ids: object,
    expected_label_id: object,
    *,
    name: str,
) -> tuple[frozenset[str], str | None]:
    if not isinstance(inventory, tuple) or not all(isinstance(item, LinearLabel) for item in inventory):
        raise TypeError("label_inventory: expected LinearLabel tuple")
    if not isinstance(group_label_ids, frozenset) or not all(
        isinstance(item, str) and item.strip() for item in group_label_ids
    ):
        raise TypeError(f"{name}_group_label_ids: expected frozenset of IDs")
    if expected_label_id is not None and not isinstance(expected_label_id, str):
        raise TypeError(f"expected_{name}_label_id: expected string or None")
    by_id = {item.id: item.name for item in inventory}
    if len(by_id) != len(inventory) or len(set(by_id.values())) != len(by_id):
        raise ValueError("label_inventory: duplicate ID or name")
    if not group_label_ids <= by_id.keys():
        raise ValueError(f"{name}_group_label_ids: unknown label ID")
    if expected_label_id is not None and expected_label_id not in group_label_ids:
        raise ValueError(f"expected_{name}_label_id: not in configured group")
    return frozenset(by_id[item] for item in group_label_ids), (
        None if expected_label_id is None else by_id[expected_label_id]
    )


def classify_drift(
    matches: tuple[LinearIssue, ...],
    *,
    expected_story_key: str | None = None,
    expected_team_id: str | None = None,
    label_inventory: tuple[LinearLabel, ...] | None = None,
    product_group_label_ids: frozenset[str] | None = None,
    kind_group_label_ids: frozenset[str] | None = None,
    expected_product_label_id: str | None = None,
    expected_kind_label_id: str | None = None,
    verified_status_names: tuple[str, ...] = (),
    expected_recap_digest: str | None = None,
    checkpoint_verified: bool = True,
    reciprocal_link_verified: bool = True,
) -> LinearAuthorityMissing | LinearDrift | None:
    """Classify only deterministic, safe authority drift from normalized evidence."""
    if not isinstance(matches, tuple) or not all(isinstance(item, LinearIssue) for item in matches):
        raise TypeError("matches: expected LinearIssue tuple")
    if expected_story_key is not None and _STORY_MARKER.fullmatch(expected_story_key) is None:
        raise ValueError("expected_story_key: expected exact story marker")
    if not matches:
        return LinearAuthorityMissing(expected_story_key)
    if len(matches) != 1:
        return LinearDrift(DriftKind.DUPLICATE_AUTHORITY, "duplicate_authoritative_story_key")
    issue = matches[0]
    parsed = parse_story_marker(issue.description)
    if expected_story_key is not None and (parsed is None or parsed[0] != expected_story_key):
        return LinearDrift(DriftKind.APPROVED_CONTRACT_CHANGED, "story_key")
    if expected_team_id is not None and issue.team_id != _string("expected_team_id", expected_team_id):
        return LinearDrift(DriftKind.PRODUCT_ASSIGNMENT_CHANGED, "team_id")
    label_configuration = (
        label_inventory,
        product_group_label_ids,
        kind_group_label_ids,
        expected_kind_label_id,
    )
    if any(item is not None for item in label_configuration):
        if any(item is None for item in label_configuration):
            raise ValueError("label authority: complete inventory, groups, and kind label are required")
        product_names, expected_product_name = _configured_label_names(
            label_inventory, product_group_label_ids, expected_product_label_id, name="product"
        )
        kind_names, expected_kind_name = _configured_label_names(
            label_inventory, kind_group_label_ids, expected_kind_label_id, name="kind"
        )
        assigned_product = frozenset(name for name in issue.labels if name in product_names)
        assigned_kind = frozenset(name for name in issue.labels if name in kind_names)
        if assigned_product != (frozenset() if expected_product_name is None else frozenset({expected_product_name})):
            return LinearDrift(DriftKind.PRODUCT_ASSIGNMENT_CHANGED, "product_label_assignment")
        if assigned_kind != frozenset({expected_kind_name}):
            return LinearDrift(DriftKind.PRODUCT_ASSIGNMENT_CHANGED, "kind_label_assignment")
    if not isinstance(verified_status_names, tuple) or not all(
        isinstance(name, str) and name.strip() for name in verified_status_names
    ):
        raise TypeError("verified_status_names: expected tuple of nonblank strings")
    if verified_status_names and issue.status_name not in verified_status_names:
        return LinearDrift(DriftKind.HUMAN_STATUS_ADVANCED, "status_name")
    if expected_recap_digest is not None:
        if _SHA256.fullmatch(expected_recap_digest) is None:
            raise ValueError("expected_recap_digest: expected lowercase SHA-256")
        if parsed is None or parsed[1] != expected_recap_digest:
            return LinearDrift(DriftKind.STALE_RECAP, "recap_sha256")
    if not isinstance(checkpoint_verified, bool) or not isinstance(reciprocal_link_verified, bool):
        raise TypeError("verification flags: expected bool")
    if not checkpoint_verified:
        return LinearDrift(DriftKind.VERIFIED_CHECKPOINT_LAG, "checkpoint")
    if not reciprocal_link_verified:
        return LinearDrift(DriftKind.MISSING_RECIPROCAL_LINK, "reciprocal_link")
    return None

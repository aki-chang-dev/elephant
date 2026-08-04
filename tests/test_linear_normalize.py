from dataclasses import FrozenInstanceError
import unittest

from scripts._elephant_runtime_forward import canonical_module


canonical_module("elephant_runtime.linear")

from elephant_runtime.linear import (
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
    classify_drift,
    normalize_attachment,
    normalize_comment,
    normalize_diff,
    normalize_issue,
    normalize_label,
    normalize_page,
    normalize_status,
    normalize_team,
    parse_story_marker,
)
from elephant_runtime.workspace_core import DriftKind


STORY_MARKER = "elephant-story/v1/" + "a" * 64
RECAP_DIGEST = "b" * 64
ISSUE_DESCRIPTION = (
    "A concise derived recap.\n\n"
    "---\n"
    f"Elephant story key: `{STORY_MARKER}`\n"
    f"Elephant recap SHA-256: `{RECAP_DIGEST}`\n"
)


def team_payload():
    return {
        "id": "team opaque id",
        "name": "Platform",
        "key": "PLAT",
        "members": [
            {"id": "user opaque id", "name": "Aki"},
        ],
    }


def status_payload():
    return {
        "id": "status opaque id",
        "name": "Ready",
        "type": "unstarted",
    }


def label_payload():
    return {
        "id": "label opaque id",
        "name": "product-facing",
        "parent": {"id": "kind group id", "name": "Kind"},
    }


def attachment_payload():
    return {
        "id": "attachment opaque id",
        "url": "https://linear.app/attachment/opaque",
        "title": "Product Contract",
    }


def relation_payload():
    return {
        "id": "relation opaque id",
        "type": "blocks",
        "issue": {"id": "other issue opaque id", "identifier": "PLAT-2"},
    }


def issue_payload():
    return {
        "id": "issue opaque id",
        "identifier": "PLAT-1",
        "title": "Normalize provider evidence",
        "description": ISSUE_DESCRIPTION,
        "team": {"id": "team opaque id", "name": "Platform"},
        "state": status_payload(),
        "labels": [label_payload()],
        "attachments": [attachment_payload()],
        "stateHistory": [{"id": "state history opaque id", "state": status_payload()}],
        "relations": [relation_payload()],
        "priority": 3,
    }


class LinearNormalizationTests(unittest.TestCase):
    def test_normalizes_connector_entities_without_rewriting_opaque_values(self):
        team = normalize_team(team_payload())
        status = normalize_status(status_payload())
        label = normalize_label(label_payload())
        attachment = normalize_attachment(attachment_payload())
        comment = normalize_comment({"id": "comment opaque id", "body": "Verified."})
        diff = normalize_diff(
            {
                "id": "diff opaque id",
                "url": "https://github.com/maio/elephant/pull/1",
                "issue": {"id": "issue opaque id", "identifier": "PLAT-1"},
            }
        )

        self.assertEqual(
            team,
            LinearTeam(
                id="team opaque id",
                name="Platform",
                key="PLAT",
                member_ids=("user opaque id",),
            ),
        )
        self.assertEqual(status.type, "unstarted")
        self.assertEqual((label.group_id, label.group_name), ("kind group id", "Kind"))
        self.assertEqual(attachment.url, "https://linear.app/attachment/opaque")
        self.assertEqual(comment.body, "Verified.")
        self.assertEqual(diff.url, "https://github.com/maio/elephant/pull/1")
        for value in (team, status, label, attachment, comment, diff):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, "id", "changed")

    def test_normalizes_an_issue_with_complete_evidence_and_required_relations(self):
        issue = normalize_issue(issue_payload(), include_relations=True)

        self.assertEqual(
            issue,
            LinearIssue(
                id="issue opaque id",
                identifier="PLAT-1",
                title="Normalize provider evidence",
                description=ISSUE_DESCRIPTION,
                team_id="team opaque id",
                state=LinearStatus("status opaque id", "Ready", "unstarted"),
                labels=(LinearLabel("label opaque id", "product-facing", "kind group id", "Kind"),),
                attachments=(
                    LinearAttachment(
                        "attachment opaque id",
                        "https://linear.app/attachment/opaque",
                        "Product Contract",
                    ),
                ),
                state_history=(("state history opaque id", "status opaque id"),),
                relations=(
                    LinearRelation(
                        "relation opaque id",
                        "blocks",
                        "other issue opaque id",
                        "PLAT-2",
                    ),
                ),
                priority=3,
            ),
        )
        without_relations = issue_payload()
        without_relations.pop("relations")
        with self.assertRaisesRegex(ValueError, "relations"):
            normalize_issue(without_relations, include_relations=True)
        truncated = normalize_issue(without_relations, include_relations=False)
        self.assertIsNone(truncated.relations)

    def test_preserves_distinct_state_history_entry_ids_when_a_status_reoccurs(self):
        raw = issue_payload()
        raw["stateHistory"] = [
            {"id": "first history opaque id", "state": status_payload()},
            {"id": "second history opaque id", "state": status_payload()},
        ]

        issue = normalize_issue(raw, include_relations=True)

        self.assertEqual(
            issue.state_history,
            (
                ("first history opaque id", "status opaque id"),
                ("second history opaque id", "status opaque id"),
            ),
        )

    def test_rejects_non_mapping_entities_and_bad_collection_shapes(self):
        for normalizer, raw in (
            (normalize_team, []),
            (normalize_status, []),
            (normalize_label, []),
            (normalize_attachment, []),
            (normalize_comment, []),
            (normalize_diff, []),
            (normalize_issue, []),
        ):
            with self.subTest(normalizer=normalizer.__name__):
                with self.assertRaises(TypeError):
                    normalizer(raw)
        bad_members = team_payload()
        bad_members["members"] = {"id": "user opaque id"}
        with self.assertRaisesRegex(TypeError, "members"):
            normalize_team(bad_members)
        bad_attachments = issue_payload()
        bad_attachments["attachments"] = {"id": "attachment opaque id"}
        with self.assertRaisesRegex(TypeError, "attachments"):
            normalize_issue(bad_attachments)

    def test_rejects_missing_or_blank_opaque_ids_for_every_entity(self):
        cases = (
            (normalize_team, team_payload()),
            (normalize_status, status_payload()),
            (normalize_label, label_payload()),
            (normalize_attachment, attachment_payload()),
            (normalize_comment, {"id": "comment opaque id", "body": "Verified."}),
            (normalize_diff, {"id": "diff opaque id", "url": "https://example.invalid"}),
            (normalize_issue, issue_payload()),
        )
        for normalizer, raw in cases:
            for bad_id in (None, "", "   "):
                with self.subTest(normalizer=normalizer.__name__, bad_id=bad_id):
                    malformed = dict(raw)
                    malformed["id"] = bad_id
                    with self.assertRaises(ValueError):
                        normalizer(malformed)

    def test_rejects_duplicate_collection_ids_and_duplicate_stable_markers(self):
        duplicate_attachments = issue_payload()
        duplicate_attachments["attachments"] = [attachment_payload(), attachment_payload()]
        with self.assertRaisesRegex(ValueError, "duplicate attachment"):
            normalize_issue(duplicate_attachments)
        duplicate_relations = issue_payload()
        duplicate_relations["relations"] = [relation_payload(), relation_payload()]
        with self.assertRaisesRegex(ValueError, "duplicate relation"):
            normalize_issue(duplicate_relations, include_relations=True)
        duplicate_marker = issue_payload()
        duplicate_marker["description"] = ISSUE_DESCRIPTION + (
            "\n---\n"
            f"Elephant story key: `{STORY_MARKER}`\n"
            f"Elephant recap SHA-256: `{RECAP_DIGEST}`\n"
        )
        with self.assertRaisesRegex(ValueError, "multiple"):
            normalize_issue(duplicate_marker)

    def test_parses_story_marker_footer_with_no_valid_malformed_and_ambiguous_cases(self):
        self.assertIsNone(parse_story_marker("No Elephant footer."))
        self.assertEqual(parse_story_marker(ISSUE_DESCRIPTION), (STORY_MARKER, RECAP_DIGEST))
        malformed = (
            "---\n"
            "Elephant story key: `elephant-story/v1/" + "A" * 64 + "`\n"
            f"Elephant recap SHA-256: `{RECAP_DIGEST}`\n"
        )
        with self.assertRaisesRegex(ValueError, "malformed"):
            parse_story_marker(malformed)
        two_markers = ISSUE_DESCRIPTION + (
            "\n---\n"
            f"Elephant story key: `{STORY_MARKER}`\n"
            f"Elephant recap SHA-256: `{RECAP_DIGEST}`\n"
        )
        with self.assertRaisesRegex(ValueError, "multiple"):
            parse_story_marker(two_markers)
        with self.assertRaisesRegex(ValueError, "malformed"):
            parse_story_marker(ISSUE_DESCRIPTION + "Implementation notes must not follow authority.\n")

    def test_normalizes_pages_and_rejects_repeated_cursors(self):
        first = normalize_page(
            {"data": [status_payload()], "pageInfo": {"hasNextPage": True, "endCursor": "page-2"}},
            normalize_status,
            seen_cursors=(),
        )
        self.assertEqual(
            first,
            PageCursor(
                values=(LinearStatus("status opaque id", "Ready", "unstarted"),),
                next_cursor="page-2",
            ),
        )
        with self.assertRaisesRegex(ValueError, "cursor loop"):
            normalize_page(
                {"data": [], "pageInfo": {"hasNextPage": True, "endCursor": "page-2"}},
                normalize_status,
                seen_cursors=("page-2",),
            )
        with self.assertRaisesRegex(TypeError, "data"):
            normalize_page({"data": {}, "pageInfo": {"hasNextPage": False, "endCursor": None}}, normalize_status)
        duplicate_marker_issue = issue_payload()
        duplicate_marker_issue["id"] = "another issue opaque id"
        duplicate_marker_issue["identifier"] = "PLAT-2"
        with self.assertRaisesRegex(ValueError, "duplicate stable marker"):
            normalize_page(
                {
                    "data": [issue_payload(), duplicate_marker_issue],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                },
                normalize_issue,
            )

    def test_classifies_deterministic_drift_from_authoritative_evidence(self):
        issue = normalize_issue(issue_payload(), include_relations=True)
        cases = (
            (
                "missing authority",
                (),
                {"expected_team_id": "team opaque id"},
                LinearDrift(DriftKind.DUPLICATE_AUTHORITY, "missing_authoritative_story_key"),
            ),
            (
                "duplicate authority",
                (issue, issue),
                {"expected_team_id": "team opaque id"},
                LinearDrift(DriftKind.DUPLICATE_AUTHORITY, "duplicate_authoritative_story_key"),
            ),
            (
                "changed assignment",
                (issue,),
                {"expected_team_id": "different team"},
                LinearDrift(DriftKind.PRODUCT_ASSIGNMENT_CHANGED, "team_id"),
            ),
            (
                "advanced status",
                (issue,),
                {"verified_status_ids": ("backlog status",)},
                LinearDrift(DriftKind.HUMAN_STATUS_ADVANCED, "state_id"),
            ),
            (
                "stale recap",
                (issue,),
                {"expected_recap_digest": "c" * 64},
                LinearDrift(DriftKind.STALE_RECAP, "recap_sha256"),
            ),
            (
                "checkpoint lag",
                (issue,),
                {"checkpoint_verified": False},
                LinearDrift(DriftKind.VERIFIED_CHECKPOINT_LAG, "checkpoint"),
            ),
            (
                "missing reciprocal relation",
                (issue,),
                {"reciprocal_link_verified": False},
                LinearDrift(DriftKind.MISSING_RECIPROCAL_LINK, "reciprocal_link"),
            ),
            (
                "authoritative key changed",
                (issue,),
                {"expected_story_key": "elephant-story/v1/" + "c" * 64},
                LinearDrift(DriftKind.APPROVED_CONTRACT_CHANGED, "story_key"),
            ),
        )
        for name, matches, evidence, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(classify_drift(matches, **evidence), expected)


if __name__ == "__main__":
    unittest.main()

from dataclasses import FrozenInstanceError
import unittest

from scripts._elephant_runtime_forward import canonical_module


canonical_module("elephant_runtime.linear")

from elephant_runtime.linear import (
    LinearAuthorityMissing,
    LinearAttachment,
    LinearDrift,
    LinearIssue,
    LinearLabel,
    LinearRelation,
    LinearRelations,
    LinearStateHistory,
    LinearStatus,
    LinearTeam,
    PageCursor,
    classify_drift,
    normalize_comments,
    normalize_diffs,
    normalize_issue,
    normalize_issue_labels,
    normalize_issues,
    normalize_issue_statuses,
    normalize_teams,
    normalize_user_teams,
    parse_story_marker,
)
from elephant_runtime.workspace_core import DriftKind


STORY_KEY = "elephant-story/v1/" + "a" * 64
RECAP_DIGEST = "b" * 64
DESCRIPTION = (
    "A concise derived recap.\n\n---\n"
    f"Elephant story key: `{STORY_KEY}`\n"
    f"Elephant recap SHA-256: `{RECAP_DIGEST}`\n"
)


def issue_payload(*, issue_id="MAI-2", description=DESCRIPTION, labels=None):
    return {
        "id": issue_id,
        "title": "Normalize provider evidence",
        "description": description,
        "priority": {"value": 3, "name": "Medium"},
        "url": "https://linear.app/maio/issue/MAI-2/normalize-provider-evidence",
        "status": "Ready",
        "statusType": "unstarted",
        "labels": ["product-facing", "tracker"] if labels is None else labels,
        "team": "Maio",
        "teamId": "team opaque id",
    }


def detailed_issue_payload(**changes):
    payload = issue_payload()
    payload.update({
        "attachments": [{
            "id": "attachment opaque id",
            "url": "https://linear.app/attachment/opaque",
            "title": "Product Contract",
        }],
        "stateHistory": [{
            "state": {"id": "status opaque id", "name": "Ready", "type": "unstarted"},
            "startedAt": "2026-08-04T07:00:00.000Z",
            "endedAt": None,
        }],
        "relations": {
            "blocks": ["MAI-3"],
            "blockedBy": ["MAI-1"],
            "relatedTo": ["MAI-4"],
            "duplicateOf": None,
        },
    })
    payload.update(changes)
    return payload


class ConnectorShapeNormalizationTests(unittest.TestCase):
    def test_normalizes_exact_team_and_user_membership_payloads_without_synthesizing_keys(self):
        teams = normalize_teams({
            "teams": [{"id": "team opaque id", "icon": "Rocket", "name": "Maio", "createdAt": "x", "updatedAt": "y"}],
            "hasNextPage": False,
        })
        memberships = normalize_user_teams({
            "id": "user opaque id",
            "teams": [{"id": "team opaque id", "name": "Maio", "key": "MAI"}],
        })

        self.assertEqual(teams, PageCursor((LinearTeam("team opaque id", "Maio", None),), None))
        self.assertEqual(memberships, (LinearTeam("team opaque id", "Maio", "MAI"),))

    def test_normalizes_bare_statuses_and_exact_label_envelope(self):
        statuses = normalize_issue_statuses([
            {"id": "status opaque id", "type": "unstarted", "name": "Ready"},
        ])
        labels = normalize_issue_labels({
            "labels": [{"id": "label opaque id", "name": "product-facing", "color": "#fff", "description": "Kind"}],
            "hasNextPage": True,
            "cursor": "labels-2",
        })

        self.assertEqual(statuses, (LinearStatus("status opaque id", "Ready", "unstarted"),))
        self.assertEqual(
            labels,
            PageCursor((LinearLabel("label opaque id", "product-facing", "#fff", "Kind"),), "labels-2"),
        )

    def test_normalizes_exact_list_and_detailed_issue_shapes(self):
        listed = normalize_issues({"issues": [issue_payload()], "hasNextPage": False})
        detail = normalize_issue(detailed_issue_payload(), include_relations=True)

        self.assertEqual(listed.values[0].id, "MAI-2")
        self.assertEqual(listed.values[0].team_id, "team opaque id")
        self.assertEqual(listed.values[0].status_name, "Ready")
        self.assertEqual(listed.values[0].priority, (3, "Medium"))
        self.assertIsNone(listed.values[0].attachments)
        self.assertEqual(
            detail,
            LinearIssue(
                id="MAI-2",
                title="Normalize provider evidence",
                description=DESCRIPTION,
                team_id="team opaque id",
                team_name="Maio",
                status_name="Ready",
                status_type="unstarted",
                labels=("product-facing", "tracker"),
                priority=(3, "Medium"),
                url="https://linear.app/maio/issue/MAI-2/normalize-provider-evidence",
                attachments=(LinearAttachment(
                    "attachment opaque id",
                    "https://linear.app/attachment/opaque",
                    "Product Contract",
                ),),
                state_history=(LinearStateHistory(
                    LinearStatus("status opaque id", "Ready", "unstarted"),
                    "2026-08-04T07:00:00.000Z",
                    None,
                ),),
                relations=LinearRelations(
                    blocks=(LinearRelation("blocks", "MAI-3"),),
                    blocked_by=(LinearRelation("blockedBy", "MAI-1"),),
                    related_to=(LinearRelation("relatedTo", "MAI-4"),),
                    duplicate_of=None,
                ),
                status_id="status opaque id",
            ),
        )

    def test_requires_complete_categorized_relations_for_detailed_reads(self):
        missing = detailed_issue_payload()
        missing.pop("relations")
        with self.assertRaisesRegex(ValueError, "relations"):
            normalize_issue(missing, include_relations=True)
        malformed = detailed_issue_payload(relations={"blocks": [], "blockedBy": [], "relatedTo": []})
        with self.assertRaisesRegex(ValueError, "duplicateOf"):
            normalize_issue(malformed, include_relations=True)

    def test_detailed_issue_preserves_current_status_project_and_parent_identity(self):
        issue = normalize_issue(detailed_issue_payload(projectId="project opaque id", parentId="parent opaque id"), include_relations=True)

        self.assertEqual(issue.status_id, "status opaque id")
        self.assertEqual(issue.project_id, "project opaque id")
        self.assertEqual(issue.parent_id, "parent opaque id")

    def test_normalizes_exact_comment_and_diff_envelopes_and_rejects_cursor_loops(self):
        comments = normalize_comments({"comments": [{"id": "comment opaque id", "body": "Verified."}], "hasNextPage": False})
        diffs = normalize_diffs({"diffs": [{"id": "diff opaque id", "url": "https://github.com/maio/elephant/pull/1"}], "hasNextPage": True, "cursor": "diffs-2"})

        self.assertEqual(comments.values[0].body, "Verified.")
        self.assertEqual(diffs.next_cursor, "diffs-2")
        with self.assertRaisesRegex(ValueError, "cursor loop"):
            normalize_issues({"issues": [], "hasNextPage": True, "cursor": "issues-2"}, seen_cursors=("issues-2",))

    def test_rejects_wrong_collections_missing_or_blank_ids_and_duplicate_ids(self):
        cases = (
            (normalize_teams, {"teams": {}, "hasNextPage": False}),
            (normalize_issue_labels, {"labels": {}, "hasNextPage": False}),
            (normalize_issues, {"issues": {}, "hasNextPage": False}),
            (normalize_comments, {"comments": {}, "hasNextPage": False}),
            (normalize_diffs, {"diffs": {}, "hasNextPage": False}),
            (normalize_issue_statuses, {"id": "not a list"}),
        )
        for normalizer, raw in cases:
            with self.subTest(normalizer=normalizer.__name__):
                with self.assertRaises(TypeError):
                    normalizer(raw)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            normalize_issues({"issues": [issue_payload(), issue_payload()], "hasNextPage": False})
        blank = issue_payload(issue_id="   ")
        with self.assertRaises(ValueError):
            normalize_issues({"issues": [blank], "hasNextPage": False})

    def test_rejects_blank_and_duplicate_ids_through_every_real_collection_shape(self):
        blank_cases = (
            (normalize_teams, {"teams": [{"id": " ", "name": "Maio"}], "hasNextPage": False}),
            (normalize_issue_statuses, [{"id": " ", "name": "Ready", "type": "unstarted"}]),
            (normalize_issue_labels, {"labels": [{"id": " ", "name": "tracker"}], "hasNextPage": False}),
            (normalize_comments, {"comments": [{"id": " ", "body": "ok"}], "hasNextPage": False}),
            (normalize_diffs, {"diffs": [{"id": " ", "url": "https://example.invalid"}], "hasNextPage": False}),
        )
        for normalizer, raw in blank_cases:
            with self.subTest(normalizer=normalizer.__name__):
                with self.assertRaises(ValueError):
                    normalizer(raw)
        duplicate_cases = (
            (normalize_teams, {"teams": [{"id": "team", "name": "A"}, {"id": "team", "name": "B"}], "hasNextPage": False}),
            (normalize_issue_statuses, [{"id": "status", "name": "A", "type": "backlog"}, {"id": "status", "name": "B", "type": "started"}]),
            (normalize_issue_labels, {"labels": [{"id": "label", "name": "A"}, {"id": "label", "name": "B"}], "hasNextPage": False}),
            (normalize_comments, {"comments": [{"id": "comment", "body": "A"}, {"id": "comment", "body": "B"}], "hasNextPage": False}),
            (normalize_diffs, {"diffs": [{"id": "diff", "url": "https://a.invalid"}, {"id": "diff", "url": "https://b.invalid"}], "hasNextPage": False}),
        )
        for normalizer, raw in duplicate_cases:
            with self.subTest(normalizer=normalizer.__name__):
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    normalizer(raw)
        with self.assertRaises(ValueError):
            normalize_issue(detailed_issue_payload(attachments=[{"id": " ", "url": "https://example.invalid", "title": "x"}]), include_relations=True)

    def test_rejects_duplicate_story_authority_by_story_key_even_if_recaps_differ(self):
        other_recap = DESCRIPTION.replace(RECAP_DIGEST, "c" * 64)
        with self.assertRaisesRegex(ValueError, "duplicate stable marker"):
            normalize_issues({
                "issues": [issue_payload(), issue_payload(issue_id="MAI-3", description=other_recap)],
                "hasNextPage": False,
            })

    def test_marker_parser_distinguishes_absent_valid_malformed_and_multiple(self):
        self.assertIsNone(parse_story_marker("No footer."))
        self.assertEqual(parse_story_marker(DESCRIPTION), (STORY_KEY, RECAP_DIGEST))
        with self.assertRaisesRegex(ValueError, "malformed"):
            parse_story_marker("---\nElephant story key: `" + STORY_KEY.upper() + "`\n")
        with self.assertRaisesRegex(ValueError, "multiple"):
            parse_story_marker(DESCRIPTION + "\n" + DESCRIPTION)

    def test_classifies_missing_authority_separately_and_enforces_exact_group_assignment(self):
        issue = normalize_issue(detailed_issue_payload(), include_relations=True)
        inventory = (
            LinearLabel("product label", "tracker", "#1", "Product"),
            LinearLabel("other product label", "other-product", "#2", "Product"),
            LinearLabel("kind label", "product-facing", "#3", "Kind"),
            LinearLabel("engineering label", "engineering-only", "#4", "Kind"),
        )
        self.assertEqual(
            classify_drift((), expected_story_key=STORY_KEY),
            LinearAuthorityMissing(STORY_KEY),
        )
        self.assertEqual(
            classify_drift((issue, issue), expected_story_key=STORY_KEY),
            LinearDrift(DriftKind.DUPLICATE_AUTHORITY, "duplicate_authoritative_story_key"),
        )
        conflicting = normalize_issue(detailed_issue_payload(labels=["tracker", "other-product", "product-facing"]), include_relations=True)
        engineering_with_product = normalize_issue(detailed_issue_payload(labels=["tracker", "engineering-only"]), include_relations=True)
        expected = {
            "label_inventory": inventory,
            "product_group_label_ids": frozenset({"product label", "other product label"}),
            "kind_group_label_ids": frozenset({"kind label", "engineering label"}),
            "expected_kind_label_id": "kind label",
            "expected_product_label_id": "product label",
        }
        self.assertEqual(
            classify_drift((conflicting,), **expected),
            LinearDrift(DriftKind.PRODUCT_ASSIGNMENT_CHANGED, "product_label_assignment"),
        )
        self.assertIsNone(classify_drift((issue,), **expected))
        engineering_expected = dict(expected, expected_product_label_id=None, expected_kind_label_id="engineering label")
        engineering = normalize_issue(detailed_issue_payload(labels=["engineering-only"]), include_relations=True)
        self.assertIsNone(classify_drift((engineering,), **engineering_expected))
        self.assertEqual(
            classify_drift((engineering_with_product,), **engineering_expected),
            LinearDrift(DriftKind.PRODUCT_ASSIGNMENT_CHANGED, "product_label_assignment"),
        )

    def test_exported_normalized_models_reject_whitespace_only_values_and_are_frozen(self):
        for value in (
            lambda: LinearTeam("   ", "Maio", None),
            lambda: LinearStatus("status", "   ", "unstarted"),
            lambda: LinearLabel("label", "   ", "#fff", None),
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    value()
        team = LinearTeam("team", "Maio", None)
        with self.assertRaises(FrozenInstanceError):
            team.id = "changed"
        with self.assertRaises(ValueError):
            LinearAuthorityMissing("not-an-elephant-story-key")


if __name__ == "__main__":
    unittest.main()

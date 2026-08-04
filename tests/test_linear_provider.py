from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import unittest

from scripts._elephant_runtime_forward import canonical_module


canonical_module("elephant_runtime.linear")

from elephant_runtime.linear import (
    LinearLabel,
    LinearStatus,
    LinearStoryProvider,
    LinearStoryProviderConfig,
    LinearTool,
    StoryCreateRequest,
    StoryKey,
)
from elephant_runtime.workspace_core import HumanStatus, ProductDisposition


_STATES = {
    "status-backlog": ("Backlog", "backlog"),
    "status-shaping": ("Shaping", "unstarted"),
    "status-ready": ("Ready", "unstarted"),
    "status-progress": ("In Progress", "started"),
    "status-done": ("Done", "completed"),
    "status-canceled": ("Canceled", "canceled"),
}


def _payload(issue_id: str, *, description: str, labels: tuple[str, ...], title: str = "Lifecycle story", state_id: str = "status-backlog", relations: dict[str, object] | None = None, parent_id: str | None = None, project_id: str | None = None) -> dict[str, object]:
    status, status_type = _STATES[state_id]
    return {
        "id": issue_id,
        "title": title,
        "description": description,
        "teamId": "team-1",
        "team": "Team",
        "status": status,
        "statusType": status_type,
        "labels": list(labels),
        "priority": {"value": 3, "name": "Medium"},
        "parentId": parent_id,
        "projectId": project_id,
        "stateHistory": [{"state": {"id": state_id, "name": status, "type": status_type}, "startedAt": "2026-08-04T00:00:00Z", "endedAt": None}],
        "relations": relations or {"blocks": [], "blockedBy": [], "relatedTo": [], "duplicateOf": None},
    }


class StrictFakeConnector:
    """A fake port with immutable-call recording and no network behavior."""

    def __init__(self) -> None:
        self.calls: list[tuple[LinearTool, tuple[tuple[str, object], ...]]] = []
        self.issues: dict[str, dict[str, object]] = {}
        self.next_id = 1
        self.fail_after_save = False
        self.fail_next_get = False
        self.list_pages: dict[str | None, dict[str, object]] = {}
        self.after_success_save = None

    def call(self, tool: LinearTool, arguments: tuple[tuple[str, object], ...]) -> dict[str, object]:
        self.calls.append((tool, arguments))
        values = dict(arguments)
        if tool is LinearTool.LIST_ISSUES:
            if self.list_pages:
                return deepcopy(self.list_pages[values.get("cursor")])
            marker = values["query"]
            return {
                "issues": [
                    deepcopy(issue)
                    for issue in self.issues.values()
                    if issue["teamId"] == values["team"] and marker in issue["description"]
                ],
                "hasNextPage": False,
            }
        if tool is LinearTool.SAVE_ISSUE:
            issue_id = values.get("id")
            if issue_id is None:
                issue_id = f"ISS-{self.next_id}"
                self.next_id += 1
                self.issues[issue_id] = _payload(
                    issue_id,
                    description=values["description"],
                    title=values["title"],
                    labels=tuple({
                        "product-tracker": "Tracker",
                        "kind-product": "product-facing",
                        "kind-engineering": "engineering-only",
                    }[label] for label in values["labels"]),
                    parent_id=values.get("parentId"),
                    project_id=values.get("project"),
                    state_id=values["state"],
                )
            else:
                issue = self.issues[issue_id]
                if "description" in values:
                    issue["description"] = values["description"]
                if "state" in values:
                    name, kind = _STATES[values["state"]]
                    issue["status"] = name
                    issue["statusType"] = kind
                    issue["stateHistory"][0]["state"] = {"id": values["state"], "name": name, "type": kind}
                for field, relation in (("blockedBy", "blockedBy"), ("blocks", "blocks"), ("relatedTo", "relatedTo")):
                    if field in values:
                        if not isinstance(values[field], tuple):
                            raise TypeError(f"{field}: connector expects an immutable array")
                        issue["relations"][relation].extend(values[field])
                        reciprocal = {"blockedBy": "blocks", "blocks": "blockedBy", "relatedTo": "relatedTo"}[relation]
                        for target_id in values[field]:
                            self.issues[target_id]["relations"][reciprocal].append(issue_id)
                for field, relation in (("removeBlockedBy", "blockedBy"), ("removeBlocks", "blocks"), ("removeRelatedTo", "relatedTo")):
                    if field in values:
                        if not isinstance(values[field], tuple):
                            raise TypeError(f"{field}: connector expects an immutable array")
                        for target_id in values[field]:
                            issue["relations"][relation].remove(target_id)
                            reciprocal = {"removeBlockedBy": "blocks", "removeBlocks": "blockedBy", "removeRelatedTo": "relatedTo"}[field]
                            self.issues[target_id]["relations"][reciprocal].remove(issue_id)
                if "duplicateOf" in values:
                    issue["relations"]["duplicateOf"] = values["duplicateOf"]
            if self.fail_after_save:
                self.fail_after_save = False
                raise TimeoutError("connector timed out after mutating")
            if self.after_success_save is not None:
                callback = self.after_success_save
                self.after_success_save = None
                callback(issue_id)
            return {"id": issue_id}
        if tool is LinearTool.GET_ISSUE:
            if self.fail_next_get:
                self.fail_next_get = False
                raise TimeoutError("connector timed out before read-back")
            return deepcopy(self.issues[values["id"]])
        if tool is LinearTool.LIST_ISSUE_STATUSES:
            return [
                {"id": "status-backlog", "name": "Backlog", "type": "backlog"},
                {"id": "status-shaping", "name": "Shaping", "type": "unstarted"},
                {"id": "status-ready", "name": "Ready", "type": "unstarted"},
                {"id": "status-progress", "name": "In Progress", "type": "started"},
                {"id": "status-done", "name": "Done", "type": "completed"},
                {"id": "status-canceled", "name": "Canceled", "type": "canceled"},
            ]
        raise AssertionError(f"unexpected tool: {tool}")


class LinearIssueLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connector = StrictFakeConnector()
        labels = (
            LinearLabel("product-tracker", "Tracker", None, "Product"),
            LinearLabel("kind-product", "product-facing", None, "Kind"),
            LinearLabel("kind-engineering", "engineering-only", None, "Kind"),
        )
        self.provider = LinearStoryProvider(
            self.connector,
            LinearStoryProviderConfig(
                team_id="team-1",
                statuses=(
                    (HumanStatus.BACKLOG, "status-backlog"),
                    (HumanStatus.SHAPING, "status-shaping"),
                    (HumanStatus.READY, "status-ready"),
                    (HumanStatus.IN_PROGRESS, "status-progress"),
                    (HumanStatus.DONE, "status-done"),
                    (HumanStatus.CANCELED, "status-canceled"),
                ),
                label_inventory=labels,
                product_group_label_ids=frozenset({"product-tracker"}),
                kind_group_label_ids=frozenset({"kind-product", "kind-engineering"}),
                product_facing_kind_label_id="kind-product",
                engineering_only_kind_label_id="kind-engineering",
            ),
        )
        self.request = StoryCreateRequest(
            key=StoryKey("repo", "intent"),
            title="Lifecycle story",
            description="A concise one-line recap.",
            team_id="team-1",
            human_status=HumanStatus.BACKLOG,
            story_kind="product-facing",
            product_label_id="product-tracker",
            product_label_name="Tracker",
            kind_label_id="kind-product",
            kind_label_name="product-facing",
            priority=3,
            project_id=None,
            parent_id=None,
            label_inventory=labels,
            product_group_label_ids=frozenset({"product-tracker"}),
            kind_group_label_ids=frozenset({"kind-product", "kind-engineering"}),
        )

    def test_create_searches_marker_then_saves_once_and_reads_back_exact_issue(self) -> None:
        issue = self.provider.create_story(self.request)

        self.assertEqual(issue.id, "ISS-1")
        self.assertEqual(
            tuple(tool for tool, _ in self.connector.calls),
            (LinearTool.LIST_ISSUES, LinearTool.LIST_ISSUE_STATUSES, LinearTool.SAVE_ISSUE, LinearTool.GET_ISSUE, LinearTool.LIST_ISSUES),
        )
        self.assertEqual(
            self.connector.calls[0][1],
            (("team", "team-1"), ("query", self.request.key.marker)),
        )
        self.assertEqual(
            self.connector.calls[2][1],
            (
                ("team", "team-1"),
                ("title", "Lifecycle story"),
                ("description", "A concise one-line recap.\n\n---\nElephant story key: `" + self.request.key.marker + "`\nElephant recap SHA-256: `bac8d12f4905766cc9fa8c18f83fcebaf1b5606075699e12f8b8904ef4be0148`"),
                ("labels", ("product-tracker", "kind-product")),
                ("priority", 3),
                ("state", "status-backlog"),
            ),
        )
        self.assertEqual(
            self.connector.calls[-2][1],
            (("id", "ISS-1"), ("includeRelations", True)),
        )

    def test_create_reuses_one_verified_match_without_another_save(self) -> None:
        self.provider.create_story(self.request)
        self.connector.calls.clear()

        issue = self.provider.create_story(self.request)

        self.assertEqual(issue.id, "ISS-1")
        self.assertEqual(
            tuple(tool for tool, _ in self.connector.calls),
            (LinearTool.LIST_ISSUES, LinearTool.GET_ISSUE),
        )

    def test_create_stops_for_duplicate_authority_without_selecting_or_mutating(self) -> None:
        self.provider.create_story(self.request)
        duplicate = deepcopy(self.connector.issues["ISS-1"])
        duplicate["id"] = "ISS-2"
        self.connector.issues["ISS-2"] = duplicate
        self.connector.calls.clear()

        result = self.provider.create_story(self.request)

        self.assertEqual(result.kind.value, "duplicate_authority")
        self.assertEqual(tuple(tool for tool, _ in self.connector.calls), (LinearTool.LIST_ISSUES,))

    def test_timeout_after_create_resumes_exact_lookup_without_a_second_save(self) -> None:
        self.connector.fail_after_save = True

        issue = self.provider.create_story(self.request)

        self.assertEqual(issue.id, "ISS-1")
        self.assertEqual(
            tuple(tool for tool, _ in self.connector.calls),
            (LinearTool.LIST_ISSUES, LinearTool.LIST_ISSUE_STATUSES, LinearTool.SAVE_ISSUE, LinearTool.LIST_ISSUES, LinearTool.GET_ISSUE),
        )

    def test_status_reads_configured_status_evidence_before_one_verified_mutation(self) -> None:
        self.provider.create_story(self.request)
        self.connector.calls.clear()

        issue = self.provider.update_human_status(self.request, HumanStatus.SHAPING)

        self.assertEqual(issue.status_name, "Shaping")
        self.assertEqual(
            tuple(tool for tool, _ in self.connector.calls),
            (
                LinearTool.LIST_ISSUES,
                LinearTool.GET_ISSUE,
                LinearTool.LIST_ISSUE_STATUSES,
                LinearTool.SAVE_ISSUE,
                LinearTool.GET_ISSUE,
            ),
        )
        self.assertEqual(
            self.connector.calls[3][1],
            (("id", "ISS-1"), ("state", "status-shaping")),
        )

    def test_status_timeout_reads_back_target_without_repeating_the_mutation(self) -> None:
        self.provider.create_story(self.request)
        self.connector.calls.clear()
        self.connector.fail_after_save = True

        issue = self.provider.update_human_status(self.request, HumanStatus.SHAPING)

        self.assertEqual(issue.status_name, "Shaping")
        self.assertEqual(
            [tool for tool, _ in self.connector.calls].count(LinearTool.SAVE_ISSUE),
            1,
        )

    def test_relation_timeout_is_read_back_and_never_repeated(self) -> None:
        self.provider.create_story(self.request)
        self.connector.issues["OTHER-1"] = _payload("OTHER-1", description="Other", labels=())
        self.connector.calls.clear()
        self.connector.fail_after_save = True

        issue = self.provider.link_relation(self.request, "OTHER-1", "blockedBy")

        self.assertIn("OTHER-1", tuple(relation.issue_id for relation in issue.relations.blocked_by))
        self.assertEqual(
            tuple(tool for tool, _ in self.connector.calls).count(LinearTool.SAVE_ISSUE),
            1,
        )
        self.assertIn(
            (LinearTool.GET_ISSUE, (("id", "OTHER-1"), ("includeRelations", True))),
            self.connector.calls,
        )

    def test_every_relation_field_is_written_once_and_verified_bidirectionally(self) -> None:
        self.provider.create_story(self.request)
        for number, relation in enumerate(("blockedBy", "blocks", "relatedTo", "duplicateOf"), start=1):
            target_id = f"OTHER-{number}"
            self.connector.issues[target_id] = _payload(target_id, description="Other", labels=())
            self.connector.calls.clear()
            self.connector.fail_after_save = True

            issue = self.provider.link_relation(self.request, target_id, relation)

            self.assertEqual(
                [arguments for tool, arguments in self.connector.calls if tool is LinearTool.SAVE_ISSUE],
                [(("id", "ISS-1"), (relation, target_id if relation == "duplicateOf" else (target_id,)))],
            )
            self.assertEqual(issue.id, "ISS-1")

    def test_child_timeout_resumes_by_child_marker_and_verifies_parent(self) -> None:
        parent = self.provider.create_story(self.request)
        child = StoryCreateRequest(
            key=StoryKey("repo", "child-intent"),
            title="Child story",
            description="A concise child recap.",
            team_id="team-1",
            human_status=HumanStatus.BACKLOG,
            story_kind="engineering-only",
            product_label_id=None,
            product_label_name=None,
            kind_label_id="kind-engineering",
            kind_label_name="engineering-only",
            priority=3,
            project_id=None,
            parent_id=parent.id,
            label_inventory=self.request.label_inventory,
            product_group_label_ids=self.request.product_group_label_ids,
            kind_group_label_ids=self.request.kind_group_label_ids,
        )
        self.connector.calls.clear()
        self.connector.fail_after_save = True

        issue = self.provider.create_child_story(self.request, child)

        self.assertEqual(issue.id, "ISS-2")
        self.assertIn(
            ("parentId", parent.id),
            next(arguments for tool, arguments in self.connector.calls if tool is LinearTool.SAVE_ISSUE),
        )
        self.assertEqual(
            [tool for tool, _ in self.connector.calls].count(LinearTool.SAVE_ISSUE),
            1,
        )

    def test_split_creates_explicit_child_before_canceling_the_parent(self) -> None:
        parent = self.provider.create_story(self.request)
        shaping_request = replace(self.request, human_status=HumanStatus.SHAPING)
        self.provider.update_human_status(self.request, HumanStatus.SHAPING)
        child = replace(
            self.request,
            key=StoryKey("repo", "split-child"),
            title="Split child",
            description="A concise split child recap.",
            parent_id=parent.id,
        )
        self.connector.calls.clear()

        issue = self.provider.apply_disposition(
            shaping_request,
            ProductDisposition.SPLIT,
            child_requests=(child,),
        )

        self.assertEqual(issue.status_name, "Canceled")
        save_calls = [arguments for tool, arguments in self.connector.calls if tool is LinearTool.SAVE_ISSUE]
        self.assertEqual(save_calls[0][-1], ("parentId", parent.id))
        self.assertEqual(save_calls[-1], (("id", parent.id), ("state", "status-canceled")))

    def test_deferred_and_rejected_use_terminal_statuses_after_a_valid_transition(self) -> None:
        self.provider.create_story(self.request)
        shaping_request = replace(self.request, human_status=HumanStatus.SHAPING)
        self.provider.update_human_status(self.request, HumanStatus.SHAPING)

        deferred = self.provider.apply_disposition(
            shaping_request,
            ProductDisposition.DEFERRED,
            summary="Reconsider when the customer research is complete.",
        )

        self.assertEqual(deferred.status_name, "Backlog")
        self.setUp()
        self.provider.create_story(self.request)
        shaping_request = replace(self.request, human_status=HumanStatus.SHAPING)
        self.provider.update_human_status(self.request, HumanStatus.SHAPING)
        rejected = self.provider.apply_disposition(
            shaping_request,
            ProductDisposition.REJECTED,
            summary="Does not meet the product outcome.",
        )
        self.assertEqual(rejected.status_name, "Canceled")

    def test_create_preflights_requested_state_then_reads_receipt_before_concurrent_lookup(self) -> None:
        issue = self.provider.create_story(self.request)

        self.assertEqual(issue.id, "ISS-1")
        self.assertEqual(
            tuple(tool for tool, _ in self.connector.calls),
            (LinearTool.LIST_ISSUES, LinearTool.LIST_ISSUE_STATUSES, LinearTool.SAVE_ISSUE, LinearTool.GET_ISSUE, LinearTool.LIST_ISSUES),
        )
        self.assertIn(("state", "status-backlog"), self.connector.calls[2][1])

    def test_paginated_lookup_finds_existing_marker_before_any_create(self) -> None:
        existing = _payload("ISS-9", description=(
            "A concise one-line recap.\n\n---\n"
            f"Elephant story key: `{self.request.key.marker}`\n"
            "Elephant recap SHA-256: `bac8d12f4905766cc9fa8c18f83fcebaf1b5606075699e12f8b8904ef4be0148`"
        ), labels=("Tracker", "product-facing"))
        self.connector.issues["ISS-9"] = existing
        self.connector.list_pages = {
            None: {"issues": [], "hasNextPage": True, "cursor": "next"},
            "next": {"issues": [existing], "hasNextPage": False},
        }

        issue = self.provider.create_story(self.request)

        self.assertEqual(issue.id, "ISS-9")
        self.assertNotIn(LinearTool.SAVE_ISSUE, tuple(tool for tool, _ in self.connector.calls))
        self.assertEqual(self.connector.calls[1][1], (("team", "team-1"), ("query", self.request.key.marker), ("cursor", "next")))

    def test_create_receipt_read_back_then_stops_for_concurrent_duplicate(self) -> None:
        def add_duplicate(issue_id: str) -> None:
            duplicate = deepcopy(self.connector.issues[issue_id])
            duplicate["id"] = "ISS-2"
            self.connector.issues["ISS-2"] = duplicate

        self.connector.after_success_save = add_duplicate

        result = self.provider.create_story(self.request)

        self.assertEqual(result.kind.value, "duplicate_authority")
        self.assertEqual(
            tuple(tool for tool, _ in self.connector.calls),
            (LinearTool.LIST_ISSUES, LinearTool.LIST_ISSUE_STATUSES, LinearTool.SAVE_ISSUE, LinearTool.GET_ISSUE, LinearTool.LIST_ISSUES),
        )

    def test_relations_use_arrays_and_removal_is_verified_without_claiming_duplicate_inverse(self) -> None:
        self.provider.create_story(self.request)
        self.connector.issues["OTHER-1"] = _payload("OTHER-1", description="Other", labels=())
        self.connector.calls.clear()

        linked = self.provider.link_relation(self.request, "OTHER-1", "blockedBy")
        self.connector.fail_after_save = True
        removed = self.provider.remove_relation(self.request, "OTHER-1", "blockedBy")
        duplicate = self.provider.link_relation(self.request, "OTHER-1", "duplicateOf")

        saves = [arguments for tool, arguments in self.connector.calls if tool is LinearTool.SAVE_ISSUE]
        self.assertIn((("id", "ISS-1"), ("blockedBy", ("OTHER-1",))), saves)
        self.assertIn((("id", "ISS-1"), ("removeBlockedBy", ("OTHER-1",))), saves)
        self.assertIsNone(removed.relations.blocked_by[0] if removed.relations.blocked_by else None)
        self.assertEqual(duplicate.relations.duplicate_of.issue_id, "OTHER-1")

    def test_reuse_stops_when_normalized_authoritative_fields_change(self) -> None:
        changes = (
            ("title", "Changed"),
            ("priority", {"value": 1, "name": "Urgent"}),
            ("projectId", "project-2"),
            ("parentId", "parent-2"),
            ("stateHistory", [{"state": {"id": "other-status", "name": "Backlog", "type": "backlog"}, "startedAt": "2026-08-04T00:00:00Z", "endedAt": None}]),
        )
        for field, value in changes:
            with self.subTest(field=field):
                self.setUp()
                self.provider.create_story(self.request)
                self.connector.issues["ISS-1"][field] = value
                if field == "stateHistory":
                    self.connector.issues["ISS-1"]["status"] = "Backlog"
                    self.connector.issues["ISS-1"]["statusType"] = "backlog"
                self.connector.calls.clear()

                result = self.provider.create_story(self.request)

                self.assertEqual(result.kind.value, "product_assignment_changed" if field != "stateHistory" else "human_status_advanced")
                self.assertNotIn(LinearTool.SAVE_ISSUE, tuple(tool for tool, _ in self.connector.calls))

    def test_disposition_replay_after_success_before_get_does_not_append_summary_twice(self) -> None:
        self.provider.create_story(self.request)
        shaping = replace(self.request, human_status=HumanStatus.SHAPING)
        self.provider.update_human_status(self.request, HumanStatus.SHAPING)
        self.connector.after_success_save = lambda issue_id: setattr(self.connector, "fail_next_get", True)
        with self.assertRaises(TimeoutError):
            self.provider.apply_disposition(shaping, ProductDisposition.DEFERRED, summary="Reconsider after research.")
        body = self.connector.issues["ISS-1"]["description"]

        issue = self.provider.apply_disposition(shaping, ProductDisposition.DEFERRED, summary="Reconsider after research.")

        self.assertEqual(self.connector.issues["ISS-1"]["description"], body)
        self.assertEqual(issue.status_name, "Backlog")

    def test_blank_recap_and_cross_kind_authority_are_rejected_before_save(self) -> None:
        with self.assertRaisesRegex(ValueError, "description"):
            replace(self.request, description="   ")
        cross_kind = replace(self.request, kind_label_id="kind-engineering", kind_label_name="engineering-only")

        with self.assertRaisesRegex(ValueError, "kind"):
            self.provider.create_story(cross_kind)
        self.assertEqual(self.connector.calls, [])

    def test_disposition_stops_before_save_for_tampered_or_stale_marker_owned_body(self) -> None:
        summary = "Reconsider after research."
        label = "Reconsideration"
        cases = (
            ("Tampered recap", sha256(b"Tampered recap").hexdigest()),
            (f"A concise one-line recap. {label}: {summary}", "0" * 64),
        )
        for recap, digest in cases:
            with self.subTest(recap=recap):
                self.setUp()
                self.provider.create_story(self.request)
                shaping = replace(self.request, human_status=HumanStatus.SHAPING)
                self.provider.update_human_status(self.request, HumanStatus.SHAPING)
                self.connector.issues["ISS-1"]["description"] = (
                    f"{recap}\n\n---\nElephant story key: `{self.request.key.marker}`\n"
                    f"Elephant recap SHA-256: `{digest}`"
                )
                self.connector.calls.clear()

                result = self.provider.apply_disposition(
                    shaping, ProductDisposition.DEFERRED, summary=summary
                )

                self.assertEqual(result.kind.value, "approved_contract_changed")
                self.assertNotIn(LinearTool.SAVE_ISSUE, tuple(tool for tool, _ in self.connector.calls))

    def test_product_facing_rejects_kind_label_as_product_authority_before_save(self) -> None:
        invalid = replace(
            self.request,
            product_label_id="kind-engineering",
            product_label_name="engineering-only",
        )

        with self.assertRaisesRegex(ValueError, "product"):
            self.provider.create_story(invalid)

        self.assertEqual(self.connector.calls, [])


if __name__ == "__main__":
    unittest.main()

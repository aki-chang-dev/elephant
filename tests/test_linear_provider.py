from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
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


def _payload(issue_id: str, *, description: str, labels: tuple[str, ...], status: str = "Backlog", status_type: str = "backlog", relations: dict[str, object] | None = None, parent_id: str | None = None) -> dict[str, object]:
    return {
        "id": issue_id,
        "title": "Lifecycle story",
        "description": description,
        "teamId": "team-1",
        "team": "Team",
        "status": status,
        "statusType": status_type,
        "labels": list(labels),
        "priority": {"value": 3, "name": "Medium"},
        "parentId": parent_id,
        "relations": relations or {"blocks": [], "blockedBy": [], "relatedTo": [], "duplicateOf": None},
    }


class StrictFakeConnector:
    """A fake port with immutable-call recording and no network behavior."""

    def __init__(self) -> None:
        self.calls: list[tuple[LinearTool, tuple[tuple[str, object], ...]]] = []
        self.issues: dict[str, dict[str, object]] = {}
        self.next_id = 1
        self.fail_after_save = False

    def call(self, tool: LinearTool, arguments: tuple[tuple[str, object], ...]) -> dict[str, object]:
        self.calls.append((tool, arguments))
        values = dict(arguments)
        if tool is LinearTool.LIST_ISSUES:
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
                    labels=tuple({
                        "product-tracker": "Tracker",
                        "kind-product": "product-facing",
                        "kind-engineering": "engineering-only",
                    }[label] for label in values["labels"]),
                    parent_id=values.get("parentId"),
                )
            else:
                issue = self.issues[issue_id]
                if "description" in values:
                    issue["description"] = values["description"]
                if "state" in values:
                    name, kind = {
                        "status-backlog": ("Backlog", "backlog"),
                        "status-shaping": ("Shaping", "unstarted"),
                        "status-ready": ("Ready", "unstarted"),
                        "status-progress": ("In Progress", "started"),
                        "status-done": ("Done", "completed"),
                        "status-canceled": ("Canceled", "canceled"),
                    }[values["state"]]
                    issue["status"] = name
                    issue["statusType"] = kind
                for field, relation in (("blockedBy", "blockedBy"), ("blocks", "blocks"), ("relatedTo", "relatedTo")):
                    if field in values:
                        issue["relations"][relation].append(values[field])
                        reciprocal = {"blockedBy": "blocks", "blocks": "blockedBy", "relatedTo": "relatedTo"}[relation]
                        self.issues[values[field]]["relations"][reciprocal].append(issue_id)
                if "duplicateOf" in values:
                    issue["relations"]["duplicateOf"] = values["duplicateOf"]
            if self.fail_after_save:
                self.fail_after_save = False
                raise TimeoutError("connector timed out after mutating")
            return {"id": issue_id}
        if tool is LinearTool.GET_ISSUE:
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
            label_inventory=labels,
            product_group_label_ids=frozenset({"product-tracker"}),
            kind_group_label_ids=frozenset({"kind-product", "kind-engineering"}),
        )

    def test_create_searches_marker_then_saves_once_and_reads_back_exact_issue(self) -> None:
        issue = self.provider.create_story(self.request)

        self.assertEqual(issue.id, "ISS-1")
        self.assertEqual(
            tuple(tool for tool, _ in self.connector.calls),
            (LinearTool.LIST_ISSUES, LinearTool.SAVE_ISSUE, LinearTool.LIST_ISSUES, LinearTool.GET_ISSUE),
        )
        self.assertEqual(
            self.connector.calls[0][1],
            (("team", "team-1"), ("query", self.request.key.marker)),
        )
        self.assertEqual(
            self.connector.calls[1][1],
            (
                ("team", "team-1"),
                ("title", "Lifecycle story"),
                ("description", "A concise one-line recap.\n\n---\nElephant story key: `" + self.request.key.marker + "`\nElephant recap SHA-256: `bac8d12f4905766cc9fa8c18f83fcebaf1b5606075699e12f8b8904ef4be0148`"),
                ("labels", ("product-tracker", "kind-product")),
                ("priority", 3),
            ),
        )
        self.assertEqual(
            self.connector.calls[-1][1],
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
            (LinearTool.LIST_ISSUES, LinearTool.SAVE_ISSUE, LinearTool.LIST_ISSUES, LinearTool.GET_ISSUE),
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
                [(("id", "ISS-1"), (relation, target_id))],
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
            kind_label_id="kind-engineering",
            kind_label_name="engineering-only",
            priority=3,
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
        self.provider.update_human_status(replace(shaping_request, human_status=HumanStatus.BACKLOG), HumanStatus.SHAPING)
        rejected = self.provider.apply_disposition(
            shaping_request,
            ProductDisposition.REJECTED,
            summary="Does not meet the product outcome.",
        )
        self.assertEqual(rejected.status_name, "Canceled")


if __name__ == "__main__":
    unittest.main()

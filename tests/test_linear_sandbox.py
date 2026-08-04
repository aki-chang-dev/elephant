from __future__ import annotations

from hashlib import sha256
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).parents[1]
PLUGIN = ROOT / "plugins/elephant"
VALIDATOR = ROOT / "scripts/validate-linear-provider.py"

if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))


def load_validator():
    spec = importlib.util.spec_from_file_location("linear_provider_validator", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LinearSandboxTranscriptTests(unittest.TestCase):
    def test_transcript_serializes_to_the_closed_validator_schema(self) -> None:
        from elephant_runtime.linear import (
            LinearSandboxTranscript,
            SandboxAnchor,
            SandboxCall,
            SandboxCheckpoint,
            SandboxCleanup,
        )

        transcript = LinearSandboxTranscript(
            marker="elephant-sandbox/7eea5a9e-346e-4d95-aa1f-3490fd099ab3",
            checkpoint=SandboxCheckpoint(
                id="redacted:attachment-1",
                sha256=sha256(b"canonical checkpoint").hexdigest(),
                size=20,
            ),
            cleanup=_cleanup(SandboxAnchor, SandboxCleanup),
            calls=_valid_calls(SandboxCall),
        )

        value = transcript.to_value()

        self.assertEqual(
            set(value), {"schema", "marker", "capabilities", "checkpoint", "cleanup", "calls"}
        )
        self.assertEqual(load_validator().validate_transcript(value), ())

    def test_verifier_requires_call_derived_cleanup_proof(self) -> None:
        from elephant_runtime.linear import (
            LinearSandboxTranscript,
            SandboxAnchor,
            SandboxCall,
            SandboxCheckpoint,
            SandboxCleanup,
            verify_linear_sandbox,
        )

        transcript = LinearSandboxTranscript(
            marker="elephant-sandbox/7eea5a9e-346e-4d95-aa1f-3490fd099ab3",
            checkpoint=SandboxCheckpoint(
                id="redacted:attachment-1",
                sha256=sha256(b"canonical checkpoint").hexdigest(),
                size=20,
            ),
            cleanup=_cleanup(SandboxAnchor, SandboxCleanup),
            calls=_valid_calls(SandboxCall),
        )
        calls = list(transcript.calls)
        calls[52] = SandboxCall(
            "mcp__codex_apps__linear_get_issue", "absence", "attachment_cleanup"
        )
        incomplete = LinearSandboxTranscript(
            transcript.marker, transcript.checkpoint, transcript.cleanup, tuple(calls)
        )

        self.assertEqual(verify_linear_sandbox(transcript), ())
        self.assertIn("attachment cleanup is not call-derived", verify_linear_sandbox(incomplete))

    def test_verifier_rejects_mutation_without_owned_issue_readback(self) -> None:
        from elephant_runtime.linear import (
            LinearSandboxTranscript,
            SandboxAnchor,
            SandboxCall,
            SandboxCheckpoint,
            SandboxCleanup,
            verify_linear_sandbox,
        )

        transcript = LinearSandboxTranscript(
            marker="elephant-sandbox/7eea5a9e-346e-4d95-aa1f-3490fd099ab3",
            checkpoint=SandboxCheckpoint(
                id="redacted:attachment-1",
                sha256=sha256(b"canonical checkpoint").hexdigest(),
                size=20,
            ),
            cleanup=_cleanup(SandboxAnchor, SandboxCleanup),
            calls=_valid_calls(SandboxCall),
        )
        calls = list(transcript.calls)
        calls[7] = SandboxCall("mcp__codex_apps__linear_get_issue", "read_back", "status")
        missing = LinearSandboxTranscript(
            transcript.marker, transcript.checkpoint, transcript.cleanup, tuple(calls)
        )

        self.assertIn("calls do not match the certification protocol", verify_linear_sandbox(missing))


def _cleanup(anchor_type, cleanup_type):
    return cleanup_type(
        anchor_type("redacted:anchor-1"),
        anchor_type("redacted:anchor-2"),
        "redacted:attachment-1",
        "redacted:attachment-2",
        "redacted:attachment-3",
    )


def _valid_calls(call_type):
    discovery = (
        "mcp__codex_apps__linear_list_teams",
        "mcp__codex_apps__linear_get_team",
        "mcp__codex_apps__linear_get_user",
        "mcp__codex_apps__linear_list_issue_statuses",
        "mcp__codex_apps__linear_list_issue_labels",
    )
    calls = [call_type(tool, "discovery", "capability_inventory") for tool in discovery]

    def issue(operation: str, *, matches: int = 1):
        calls.extend((
            call_type("mcp__codex_apps__linear_list_issues", "lookup", operation, {"matches": matches}),
            call_type("mcp__codex_apps__linear_save_issue", "mutation", operation),
            call_type("mcp__codex_apps__linear_get_issue", "read_back", operation),
        ))

    issue("create_story", matches=0)
    for operation in ("status", "labels", "parent", "relation_add", "relation_remove", "recap", "contract_link"):
        issue(operation)
    calls[22] = call_type("mcp__codex_apps__linear_get_issue", "read_back", "relation_remove", {
        "parent": None,
        "relations": {"blocks": 0, "blocked_by": 0, "related_to": 0, "duplicate_of": 0},
        "anchors": {
            "anchor_1": {"id": "redacted:anchor-1", "relations": {"blocks": 0, "blocked_by": 0, "related_to": 0, "duplicate_of": 0}, "restored": True},
            "anchor_2": {"id": "redacted:anchor-2", "relations": {"blocks": 0, "blocked_by": 0, "related_to": 0, "duplicate_of": 0}, "restored": True},
        },
    })
    calls.extend((
        call_type("mcp__codex_apps__linear_list_issues", "lookup", "checkpoint", {"matches": 1}),
        call_type("mcp__codex_apps__linear_prepare_attachment_upload", "prepare", "checkpoint"),
        call_type("host_raw_signed_put", "upload", "checkpoint"),
        call_type("mcp__codex_apps__linear_create_attachment_from_upload", "mutation", "checkpoint"),
        call_type("mcp__codex_apps__linear_get_attachment", "read_back", "checkpoint", {
            "id": "redacted:attachment-1", "sha256": sha256(b"canonical checkpoint").hexdigest(), "size": 20,
        }),
        call_type("mcp__codex_apps__linear_get_issue", "read_back", "checkpoint"),
        call_type("mcp__codex_apps__linear_list_comments", "lookup", "comment_create", {"matches": 0}),
        call_type("mcp__codex_apps__linear_save_comment", "mutation", "comment_create"),
        call_type("mcp__codex_apps__linear_list_comments", "read_back", "comment_create", {"matches": 1}),
        call_type("mcp__codex_apps__linear_list_comments", "lookup", "comment_update", {"matches": 1}),
        call_type("mcp__codex_apps__linear_save_comment", "mutation", "comment_update"),
        call_type("mcp__codex_apps__linear_list_comments", "read_back", "comment_update", {"matches": 1}),
        call_type("mcp__codex_apps__linear_list_comments", "lookup", "comment_delete", {"matches": 1}),
        call_type("mcp__codex_apps__linear_delete_comment", "mutation", "comment_delete", arguments={"id": "redacted:comment-1"}),
        call_type("mcp__codex_apps__linear_list_comments", "absence", "comment_delete", {"matches": 0}),
    ))
    issue("pr_link")
    calls.extend((
        call_type("mcp__codex_apps__linear_list_diffs", "diagnostic", "pr_diff", {"code": "configuration_missing"}),
        call_type("mcp__codex_apps__linear_list_issues", "lookup", "attachment_cleanup", {"matches": 1}),
        call_type("mcp__codex_apps__linear_delete_attachment", "mutation", "checkpoint_cleanup", arguments={"id": "redacted:attachment-1"}),
        call_type("mcp__codex_apps__linear_delete_attachment", "mutation", "contract_link_cleanup", arguments={"id": "redacted:attachment-2"}),
        call_type("mcp__codex_apps__linear_delete_attachment", "mutation", "pr_link_cleanup", arguments={"id": "redacted:attachment-3"}),
        call_type("mcp__codex_apps__linear_get_issue", "absence", "attachment_cleanup", {"attachments": 0, "absent": ["redacted:attachment-1", "redacted:attachment-2", "redacted:attachment-3"]}),
    ))
    issue("final_cancel")
    calls[-1] = call_type("mcp__codex_apps__linear_get_issue", "read_back", "final_cancel", {
        "id": "redacted:issue-1",
        "title": "[Elephant provider certification — cleaned] 3490fd099ab3",
        "status": "Canceled",
        "labels": [],
        "parent": None,
        "attachments": 0,
        "comments": 0,
        "relations": {"blocks": 0, "blocked_by": 0, "related_to": 0, "duplicate_of": 0},
    })
    return tuple(calls)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import base64
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
PLUGIN = ROOT / "plugins/elephant"
REFERENCE = PLUGIN / "references/providers/linear.md"
VALIDATOR = ROOT / "scripts/validate-linear-provider.py"

if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))


def load_validator():
    spec = importlib.util.spec_from_file_location("linear_provider_validator", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call(
    tool: str, phase: str, operation: str, result: dict[str, object] | None = None,
    arguments: dict[str, object] | None = None,
):
    value = {"tool": tool, "phase": phase, "operation": operation}
    if result is not None:
        value["result"] = result
    if arguments is not None:
        value["arguments"] = arguments
    return value


def valid_transcript() -> dict[str, object]:
    marker = "elephant-sandbox/7eea5a9e-346e-4d95-aa1f-3490fd099ab3"
    digest = sha256(b"canonical checkpoint").hexdigest()
    calls = [
        _call(tool, "discovery", "capability_inventory")
        for tool in (
            "mcp__codex_apps__linear_list_teams", "mcp__codex_apps__linear_get_team",
            "mcp__codex_apps__linear_get_user", "mcp__codex_apps__linear_list_issue_statuses",
            "mcp__codex_apps__linear_list_issue_labels",
        )
    ]
    def issue_mutation(operation: str):
        calls.extend((
            _call("mcp__codex_apps__linear_list_issues", "lookup", operation, {"matches": 1}),
            _call("mcp__codex_apps__linear_save_issue", "mutation", operation),
            _call("mcp__codex_apps__linear_get_issue", "read_back", operation),
        ))
    calls.extend((
        _call("mcp__codex_apps__linear_list_issues", "lookup", "create_story", {"matches": 0}),
        _call("mcp__codex_apps__linear_save_issue", "mutation", "create_story"),
        _call("mcp__codex_apps__linear_get_issue", "read_back", "create_story"),
    ))
    for operation in ("status", "labels", "parent", "relation_add", "relation_remove", "recap", "contract_link"):
        issue_mutation(operation)
    calls.extend((
        _call("mcp__codex_apps__linear_list_issues", "lookup", "checkpoint", {"matches": 1}),
        _call("mcp__codex_apps__linear_prepare_attachment_upload", "prepare", "checkpoint"),
        _call("host_raw_signed_put", "upload", "checkpoint"),
        _call("mcp__codex_apps__linear_create_attachment_from_upload", "mutation", "checkpoint"),
        _call("mcp__codex_apps__linear_get_attachment", "read_back", "checkpoint", {"id": "redacted:attachment-1", "sha256": digest, "size": 20}),
        _call("mcp__codex_apps__linear_get_issue", "read_back", "checkpoint"),
        _call("mcp__codex_apps__linear_list_comments", "lookup", "comment_create", {"matches": 0}),
        _call("mcp__codex_apps__linear_save_comment", "mutation", "comment_create"),
        _call("mcp__codex_apps__linear_list_comments", "read_back", "comment_create", {"matches": 1}),
        _call("mcp__codex_apps__linear_list_comments", "lookup", "comment_update", {"matches": 1}),
        _call("mcp__codex_apps__linear_save_comment", "mutation", "comment_update"),
        _call("mcp__codex_apps__linear_list_comments", "read_back", "comment_update", {"matches": 1}),
        _call("mcp__codex_apps__linear_list_comments", "lookup", "comment_delete", {"matches": 1}),
        _call("mcp__codex_apps__linear_delete_comment", "mutation", "comment_delete", arguments={"id": "redacted:comment-1"}),
        _call("mcp__codex_apps__linear_list_comments", "absence", "comment_delete", {"matches": 0}),
    ))
    issue_mutation("pr_link")
    calls.extend((
        _call("mcp__codex_apps__linear_list_diffs", "diagnostic", "pr_diff", {"code": "configuration_missing"}),
        _call("mcp__codex_apps__linear_list_issues", "lookup", "attachment_cleanup", {"matches": 1}),
        _call("mcp__codex_apps__linear_delete_attachment", "mutation", "attachment_cleanup"),
        _call("mcp__codex_apps__linear_get_issue", "absence", "attachment_cleanup"),
    ))
    issue_mutation("final_cancel")
    calls[-1] = _call(
        "mcp__codex_apps__linear_get_issue", "read_back", "final_cancel",
        {"id": "redacted:issue-1", "title": "[Elephant provider certification — cleaned] 7eea5a9e", "status": "Canceled"},
    )
    return {
        "schema": "elephant.linear-sandbox/v1",
        "marker": marker,
        "capabilities": {
            "read_only": [
                "mcp__codex_apps__linear_list_teams", "mcp__codex_apps__linear_get_team",
                "mcp__codex_apps__linear_get_user", "mcp__codex_apps__linear_list_issue_statuses",
                "mcp__codex_apps__linear_list_issue_labels",
            ],
            "sandbox_cleanup": [
                "mcp__codex_apps__linear_delete_comment", "mcp__codex_apps__linear_delete_attachment",
            ],
        },
        "checkpoint": {"id": "redacted:attachment-1", "sha256": digest, "size": 20},
        "calls": calls,
    }


class LinearProviderPackagingTests(unittest.TestCase):
    def test_installed_artifact_imports_public_provider_without_checkout_scripts(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "artifact"
            shutil.copytree(PLUGIN, artifact)
            program = (
                "import pathlib,sys; "
                f"root=pathlib.Path({str(artifact)!r}).resolve(); "
                "sys.path.insert(0,str(root)); "
                "import elephant_runtime.linear as linear; "
                "assert str(pathlib.Path(linear.__file__).resolve()).startswith(str(root)); "
                "assert 'LinearStoryProvider' in linear.__all__; "
                "assert 'HostAttachmentContentReader' in linear.__all__; "
                "assert not any(name == 'scripts' or name.startswith('scripts.') for name in sys.modules)"
            )
            completed = subprocess.run(
                [sys.executable, "-I", "-c", program], cwd=directory,
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_provider_reference_has_the_complete_exact_tool_vocabulary(self):
        from elephant_runtime.linear import LinearTool

        text = REFERENCE.read_text(encoding="utf-8")
        for tool in LinearTool:
            self.assertIn(tool.value, text)
        self.assertIn("host_raw_signed_put", text)

    def test_attachment_reader_accepts_one_identity_bound_resource_blob(self):
        from elephant_runtime.linear import HostAttachmentContentReader

        raw = b'{"schema":"elephant.linear-checkpoint/v1"}\n'
        response = {
            "content": [{
                "type": "resource",
                "resource": {
                    "uri": "linear://attachments/attachment-1",
                    "mimeType": "application/json",
                    "blob": base64.b64encode(raw).decode("ascii"),
                    "_meta": {"linear_attachment_id": "attachment-1"},
                },
            }],
        }
        self.assertEqual(
            HostAttachmentContentReader().read(response, attachment_id="attachment-1"), raw
        )
        with self.assertRaisesRegex(RuntimeError, "attachment content could not be decoded"):
            HostAttachmentContentReader().read(response, attachment_id="another-attachment")

    def test_attachment_reader_sanitizes_opaque_mapping_exceptions(self):
        from collections.abc import Mapping
        from elephant_runtime.linear import HostAttachmentContentReader

        class ExplosiveMapping(Mapping):
            def __getitem__(self, key):
                raise RuntimeError("Bearer top-secret")
            def __iter__(self):
                return iter(())
            def __len__(self):
                return 0
            def get(self, key, default=None):
                raise RuntimeError("Bearer top-secret")

        with self.assertRaisesRegex(RuntimeError, "^attachment content could not be decoded$"):
            HostAttachmentContentReader().read(ExplosiveMapping(), attachment_id="attachment-1")

    def test_validator_accepts_redacted_offline_transcript(self):
        self.assertEqual(load_validator().validate_transcript(valid_transcript()), ())

    def test_validator_rejects_order_authority_cleanup_secret_and_digest_gaps(self):
        validator = load_validator()
        cases = (
            ("missing-required-flow", lambda value: value["calls"].clear()),
            ("consumed-lookup", lambda value: value["calls"].pop(8)),
            ("wrong-comment-readback", lambda value: value["calls"].__setitem__(37, _call("mcp__codex_apps__linear_get_issue", "read_back", "comment_create"))),
            ("unknown-nested-field", lambda value: value["capabilities"].__setitem__("oauth_token", "not-redacted")),
            ("unpadded-base64", lambda value: value.__setitem__("payload", "dG9rZW4")),
            ("digest", lambda value: value["calls"][33]["result"].__setitem__("sha256", "0" * 64)),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                transcript = valid_transcript()
                mutate(transcript)
                self.assertTrue(validator.validate_transcript(transcript))

    def test_validator_recursively_identifies_unpadded_base64_values(self):
        transcript = valid_transcript()
        transcript["calls"][0]["operation"] = "dG9rZW4"
        errors = load_validator().validate_transcript(transcript)
        self.assertTrue(any("secret/base64" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()

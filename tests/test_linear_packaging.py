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


def valid_transcript() -> dict[str, object]:
    marker = "elephant-sandbox/7eea5a9e-346e-4d95-aa1f-3490fd099ab3"
    digest = sha256(b"canonical checkpoint").hexdigest()
    return {
        "schema": "elephant.linear-sandbox/v1",
        "marker": marker,
        "issue": {
            "id": "redacted:issue-1",
            "title": "[Elephant provider certification — cleaned] 7eea5a9e",
            "status": "Canceled",
        },
        "calls": [
            {"tool": "mcp__codex_apps__linear_list_issues", "phase": "lookup", "matches": 0},
            {"tool": "mcp__codex_apps__linear_save_issue", "phase": "mutation"},
            {"tool": "mcp__codex_apps__linear_get_issue", "phase": "read_back"},
            {"tool": "mcp__codex_apps__linear_prepare_attachment_upload", "phase": "prepare"},
            {"tool": "host_raw_signed_put", "phase": "upload"},
            {"tool": "mcp__codex_apps__linear_create_attachment_from_upload", "phase": "mutation"},
            {"tool": "mcp__codex_apps__linear_get_attachment", "phase": "read_back"},
            {"tool": "mcp__codex_apps__linear_delete_attachment", "phase": "mutation"},
            {"tool": "mcp__codex_apps__linear_get_issue", "phase": "read_back"},
        ],
        "attachments": [{"id": "redacted:attachment-1", "sha256": digest, "read_sha256": digest}],
        "cleanup": {
            "relations_absent": True,
            "comments_absent": True,
            "attachments_absent": True,
            "issue_retained_canceled": True,
        },
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

    def test_validator_accepts_redacted_offline_transcript(self):
        self.assertEqual(load_validator().validate_transcript(valid_transcript()), ())

    def test_validator_rejects_order_authority_cleanup_secret_and_digest_gaps(self):
        validator = load_validator()
        cases = (
            ("mutation-before-lookup", lambda value: value["calls"].pop(0)),
            ("missing-read-back", lambda value: value["calls"].pop(2)),
            ("duplicate-authority", lambda value: value["calls"][0].__setitem__("matches", 2)),
            ("cleanup-gap", lambda value: value["cleanup"].__setitem__("comments_absent", False)),
            ("secret", lambda value: value.__setitem__("token", "not-redacted")),
            ("base64", lambda value: value.__setitem__("payload", "dG9rZW4=")),
            ("digest", lambda value: value["attachments"][0].__setitem__("read_sha256", "0" * 64)),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                transcript = valid_transcript()
                mutate(transcript)
                self.assertTrue(validator.validate_transcript(transcript))


if __name__ == "__main__":
    unittest.main()

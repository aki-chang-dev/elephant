from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts.workspace_core import validate_profile, validate_workspace
from scripts.workspace_core.config import FORBIDDEN_STORY_KEYS
from scripts.workspace_setup import ConfirmedDomain, ConfirmedProduct, ConfirmedTopology
from scripts.workspace_setup.files import (
    LocalWrite,
    WORKSPACE_PATH,
    apply_local_write,
    build_local_documents,
    load_rendered_yaml,
    plan_local_writes,
    render_yaml,
)


PROFILE_SECTIONS = (
    "context",
    "design_gate",
    "research",
    "execution",
    "verification",
    "finish",
    "language",
)


def confirmed_topology() -> ConfirmedTopology:
    return ConfirmedTopology(
        repository_id="repo-sample",
        products=(ConfirmedProduct("sample", "Sample", ("web",)),),
        domains=(
            ConfirmedDomain(
                "web",
                "Web",
                ("sample",),
                ("apps/web",),
                ("AGENTS.md",),
                ("bun run type-check",),
            ),
        ),
    )


def external_provider_selection() -> dict[str, str]:
    return {
        "story_store": "linear",
        "product_knowledge_store": "notion",
        "product_contract_store": "notion",
        "delivery_workspace": "git",
    }


def verified_bindings() -> dict[str, object]:
    return {
        "linear": {
            "verified": True,
            "values": {"workspace_id": "linear-workspace", "team_id": "linear-team"},
            "story_refs": {"sample": "linear-label-sample"},
        },
        "notion": {
            "verified": True,
            "values": {
                "workspace_id": "notion-workspace",
                "products_database_id": "notion-products",
                "knowledge_database_id": "notion-knowledge",
                "contracts_database_id": "notion-contracts",
            },
            "knowledge_refs": {"sample": "notion-product-sample"},
        },
    }


def product_settings() -> dict[str, dict[str, object]]:
    return {
        "sample": {
            "context": {"knowledge_keys": ["overview"]},
            "design_gate": {"enabled": False},
            "research": {"mode": "auto-assess"},
            "execution": {"isolation": "git-worktree"},
            "verification": {"commands": ["bun run type-check"]},
            "finish": {"integration": "github-pr-squash"},
            "language": {"dialogue": "zh-CN", "docs": "en"},
        }
    }


def engineering_settings() -> dict[str, object]:
    return {
        "context": {"knowledge_keys": []},
        "design_gate": {"enabled": False},
        "research": {"mode": "auto-assess"},
        "execution": {"isolation": "git-worktree"},
        "verification": {"commands": ["python3 -m unittest discover -s tests"]},
        "finish": {"integration": "github-pr-squash"},
        "language": {"dialogue": "zh-CN", "docs": "en"},
    }


def build_documents() -> dict[str, str]:
    return build_local_documents(
        topology=confirmed_topology(),
        providers=external_provider_selection(),
        bindings=verified_bindings(),
        product_profile_settings=product_settings(),
        engineering_profile_settings=engineering_settings(),
    )


class LocalDocumentTests(unittest.TestCase):
    def test_external_documents_pass_phase_one_validators(self):
        documents = build_documents()

        workspace = load_rendered_yaml(documents[WORKSPACE_PATH])
        self.assertEqual(validate_workspace(workspace), ())
        for path, body in documents.items():
            if path == WORKSPACE_PATH:
                continue
            self.assertEqual(validate_profile(load_rendered_yaml(body)), ())

    def test_generated_registry_contains_no_story_level_content(self):
        workspace = load_rendered_yaml(build_documents()[WORKSPACE_PATH])

        self.assertTrue(FORBIDDEN_STORY_KEYS.isdisjoint(workspace))
        self.assertEqual(
            workspace["products"]["sample"],
            {
                "profile": ".agents/elephant/profiles/sample.yaml",
                "story_ref": "linear-label-sample",
                "knowledge_ref": "notion-product-sample",
                "primary_domains": ["web"],
            },
        )

    def test_all_git_documents_have_no_external_bindings(self):
        providers = dict.fromkeys(external_provider_selection(), "git")

        documents = build_local_documents(
            confirmed_topology(),
            providers,
            {},
            product_settings(),
            engineering_settings(),
        )
        workspace = load_rendered_yaml(documents[WORKSPACE_PATH])

        self.assertEqual(workspace["bindings"], {})
        self.assertEqual(workspace["products"]["sample"]["story_ref"], "git:story:sample")
        self.assertEqual(workspace["products"]["sample"]["knowledge_ref"], "git:knowledge:sample")
        self.assertEqual(validate_workspace(workspace), ())

    def test_renderer_is_canonical_and_rejects_values_outside_its_subset(self):
        document = {"z": None, "a": ["line\nquote\"", True, 3]}

        body = render_yaml(document)

        self.assertEqual(
            body,
            '{\n  "a": [\n    "line\\nquote\\\"",\n    true,\n    3\n  ],\n  "z": null\n}\n',
        )
        self.assertEqual(load_rendered_yaml(body), document)
        for unsupported in ({1: "value"}, {"float": 1.5}, {"set": {"value"}}):
            with self.subTest(unsupported=unsupported):
                with self.assertRaisesRegex((TypeError, ValueError), "constrained YAML"):
                    render_yaml(unsupported)

    def test_unverified_bindings_missing_settings_and_unsafe_product_keys_stop(self):
        unverified = verified_bindings()
        unverified["linear"] = {**unverified["linear"], "verified": False}
        cases = (
            (confirmed_topology(), external_provider_selection(), unverified, product_settings(), "verified binding"),
            (confirmed_topology(), external_provider_selection(), verified_bindings(), {}, "profile settings"),
            (
                ConfirmedTopology(
                    "repo-sample",
                    (ConfirmedProduct("../sample", "Sample", ("web",)),),
                    (ConfirmedDomain("web", "Web", ("../sample",), ("apps/web",), ("AGENTS.md",), ("check",)),),
                ),
                external_provider_selection(),
                verified_bindings(),
                {"../sample": product_settings()["sample"]},
                "product key",
            ),
        )
        for topology, providers, bindings, settings, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    build_local_documents(
                        topology,
                        providers,
                        bindings,
                        settings,
                        engineering_settings(),
                    )

    def test_extra_binding_receipts_and_duplicate_confirmed_keys_are_rejected(self):
        extra_receipt = verified_bindings()
        extra_receipt["unused"] = {"verified": False, "values": {}}
        duplicate_products = ConfirmedTopology(
            "repo-sample",
            (
                ConfirmedProduct("sample", "Sample", ("web",)),
                ConfirmedProduct("sample", "Duplicate", ("web",)),
            ),
            confirmed_topology().domains,
        )

        with self.assertRaisesRegex(ValueError, "binding receipt"):
            build_local_documents(
                confirmed_topology(),
                external_provider_selection(),
                extra_receipt,
                product_settings(),
                engineering_settings(),
            )
        with self.assertRaisesRegex(ValueError, "duplicate product"):
            build_local_documents(
                duplicate_products,
                external_provider_selection(),
                verified_bindings(),
                product_settings(),
                engineering_settings(),
            )


def body_fingerprint(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class LocalWriteSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root_context = tempfile.TemporaryDirectory()
        self.outside_context = tempfile.TemporaryDirectory()
        self.root = Path(self.root_context.name)
        self.outside = Path(self.outside_context.name)

    def tearDown(self) -> None:
        self.root_context.cleanup()
        self.outside_context.cleanup()

    def test_only_workspace_and_direct_profile_paths_are_allowed(self):
        for path in (
            "README.md",
            ".agents/elephant/profiles/nested/a.yaml",
            "../outside.yaml",
            ".agents/elephant/profiles/a.yml",
        ):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "setup output path"):
                    plan_local_writes(self.root, {path: "body"})

    def test_symlinked_parent_or_target_cannot_escape_repository(self):
        (self.root / ".agents").symlink_to(self.outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "repository containment"):
            plan_local_writes(self.root, {WORKSPACE_PATH: build_documents()[WORKSPACE_PATH]})

        (self.root / ".agents").unlink()
        target = self.root / WORKSPACE_PATH
        target.parent.mkdir(parents=True)
        outside_target = self.outside / "workspace.yaml"
        outside_target.write_text("outside", encoding="utf-8")
        target.symlink_to(outside_target)
        with self.assertRaisesRegex(ValueError, "repository containment"):
            plan_local_writes(self.root, {WORKSPACE_PATH: build_documents()[WORKSPACE_PATH]})

    def test_create_unchanged_and_replace_are_classified_without_unrelated_deletes(self):
        documents = build_documents()
        creates = plan_local_writes(self.root, documents)
        self.assertEqual({write.disposition for write in creates}, {"create"})
        for write in creates:
            apply_local_write(self.root, write)

        unrelated = self.root / ".agents/elephant/keep.txt"
        unrelated.write_text("keep", encoding="utf-8")
        workspace = self.root / WORKSPACE_PATH
        inode = workspace.stat().st_ino
        unchanged = plan_local_writes(self.root, documents)
        self.assertEqual({write.disposition for write in unchanged}, {"unchanged"})
        for write in unchanged:
            apply_local_write(self.root, write)
        self.assertEqual(workspace.stat().st_ino, inode)
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep")

        old_body = documents[WORKSPACE_PATH]
        changed_body = old_body.replace("repo-sample", "repo-replacement")
        replacements = plan_local_writes(
            self.root,
            {WORKSPACE_PATH: changed_body},
            expected_fingerprints={WORKSPACE_PATH: body_fingerprint(old_body)},
        )
        self.assertEqual(replacements[0].disposition, "replace")
        apply_local_write(self.root, replacements[0])
        self.assertEqual(workspace.read_text(encoding="utf-8"), changed_body)
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep")

    def test_changed_existing_content_requires_exact_expected_fingerprint(self):
        target = self.root / WORKSPACE_PATH
        target.parent.mkdir(parents=True)
        target.write_text(build_documents()[WORKSPACE_PATH], encoding="utf-8")
        changed = build_documents()[WORKSPACE_PATH].replace("repo-sample", "repo-new")

        for expected in (None, "0" * 64):
            with self.subTest(expected=expected):
                fingerprints = None if expected is None else {WORKSPACE_PATH: expected}
                with self.assertRaisesRegex(ValueError, "semantic overwrite"):
                    plan_local_writes(
                        self.root,
                        {WORKSPACE_PATH: changed},
                        expected_fingerprints=fingerprints,
                    )

    def test_replace_rechecks_prior_fingerprint_immediately_before_mutation(self):
        target = self.root / WORKSPACE_PATH
        target.parent.mkdir(parents=True)
        old_body = build_documents()[WORKSPACE_PATH]
        target.write_text(old_body, encoding="utf-8")
        changed = old_body.replace("repo-sample", "repo-new")
        write = plan_local_writes(
            self.root,
            {WORKSPACE_PATH: changed},
            expected_fingerprints={WORKSPACE_PATH: body_fingerprint(old_body)},
        )[0]

        target.write_text("concurrent change", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "semantic overwrite"):
            apply_local_write(self.root, write)
        self.assertEqual(target.read_text(encoding="utf-8"), "concurrent change")

    def test_create_rechecks_absence_and_local_write_cannot_move_between_roots(self):
        write = plan_local_writes(
            self.root, {WORKSPACE_PATH: build_documents()[WORKSPACE_PATH]}
        )[0]
        target = self.root / WORKSPACE_PATH
        target.parent.mkdir(parents=True)
        target.write_text("appeared", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "semantic overwrite"):
            apply_local_write(self.root, write)
        with self.assertRaisesRegex(ValueError, "planned repository root"):
            apply_local_write(self.outside, write)

    def test_apply_rejects_a_write_body_changed_after_planning(self):
        write = plan_local_writes(
            self.root, {WORKSPACE_PATH: build_documents()[WORKSPACE_PATH]}
        )[0]
        changed_body = write.body.replace("repo-sample", "repo-new")

        with self.assertRaisesRegex(ValueError, "planned document fingerprint"):
            apply_local_write(self.root, replace(write, body=changed_body))
        self.assertFalse((self.root / WORKSPACE_PATH).exists())

    def test_local_write_is_an_immutable_planned_value(self):
        write = plan_local_writes(
            self.root, {WORKSPACE_PATH: build_documents()[WORKSPACE_PATH]}
        )[0]

        self.assertIsInstance(write, LocalWrite)
        with self.assertRaises((AttributeError, TypeError)):
            write.disposition = "replace"


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from dataclasses import replace
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

from scripts.workspace_core import validate_profile, validate_workspace
from scripts.workspace_core.config import FORBIDDEN_STORY_KEYS
from scripts.workspace_setup import (
    ConfirmedDomain,
    ConfirmedProduct,
    ConfirmedTopology,
    OperationKind,
    SetupOperation,
)
from scripts.workspace_setup.files import (
    LocalTransactionError,
    LocalTransactionResult,
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

    def test_direct_topology_requires_unique_known_reciprocal_links(self):
        cases = (
            ConfirmedTopology(
                "repo-sample",
                (ConfirmedProduct("sample", "Sample", ("web",)),),
                (ConfirmedDomain("web", "Web", (), ("apps/web",), ("AGENTS.md",), ("check",)),),
            ),
            ConfirmedTopology(
                "repo-sample",
                (ConfirmedProduct("sample", "Sample", ("missing",)),),
                confirmed_topology().domains,
            ),
            ConfirmedTopology(
                "repo-sample",
                (ConfirmedProduct("sample", "Sample", ("web", "web")),),
                confirmed_topology().domains,
            ),
            ConfirmedTopology(
                "repo-sample",
                confirmed_topology().products,
                (
                    ConfirmedDomain(
                        "web",
                        "Web",
                        ("sample", "sample"),
                        ("apps/web",),
                        ("AGENTS.md",),
                        ("check",),
                    ),
                ),
            ),
        )
        for topology in cases:
            with self.subTest(topology=topology):
                with self.assertRaisesRegex(ValueError, "reciprocal|duplicate|unknown"):
                    build_local_documents(
                        topology,
                        external_provider_selection(),
                        verified_bindings(),
                        product_settings(),
                        engineering_settings(),
                    )


def body_fingerprint(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def local_operation(
    path: str,
    body: object,
    *,
    expected_prior_fingerprint: str | None = None,
) -> SetupOperation:
    desired = body_fingerprint(body) if isinstance(body, str) else "semantic-document"
    return SetupOperation(
        operation_id=f"local.{path}",
        provider="local",
        capability="write_registry" if path == WORKSPACE_PATH else "write_profile",
        target_key=path,
        desired_fingerprint=desired,
        payload=(("document", body),),
        kind=OperationKind.WRITE_LOCAL,
        runtime_required=False,
        expected_prior_fingerprint=expected_prior_fingerprint,
    )


def local_operations(
    documents: dict[str, str],
    *,
    expected_prior_fingerprints: dict[str, str] | None = None,
) -> tuple[SetupOperation, ...]:
    expected = expected_prior_fingerprints or {}
    paths = sorted(documents, key=lambda path: (path == WORKSPACE_PATH, path))
    return tuple(
        local_operation(
            path,
            documents[path],
            expected_prior_fingerprint=expected.get(path),
        )
        for path in paths
    )


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
                    plan_local_writes(self.root, (local_operation(path, "body"),))

    def test_symlinked_parent_or_target_cannot_escape_repository(self):
        (self.root / ".agents").symlink_to(self.outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "repository containment"):
            plan_local_writes(
                self.root,
                (local_operation(WORKSPACE_PATH, build_documents()[WORKSPACE_PATH]),),
            )

        (self.root / ".agents").unlink()
        target = self.root / WORKSPACE_PATH
        target.parent.mkdir(parents=True)
        outside_target = self.outside / "workspace.yaml"
        outside_target.write_text("outside", encoding="utf-8")
        target.symlink_to(outside_target)
        with self.assertRaisesRegex(ValueError, "repository containment"):
            plan_local_writes(
                self.root,
                (local_operation(WORKSPACE_PATH, build_documents()[WORKSPACE_PATH]),),
            )

    def test_create_unchanged_and_replace_are_classified_without_unrelated_deletes(self):
        documents = build_documents()
        creates = plan_local_writes(self.root, local_operations(documents))
        self.assertEqual({write.disposition for write in creates}, {"create"})
        created = apply_local_write(self.root, creates)
        self.assertIsInstance(created, LocalTransactionResult)
        self.assertEqual({outcome.states[-1] for outcome in created.outcomes}, {"durable"})

        unrelated = self.root / ".agents/elephant/keep.txt"
        unrelated.write_text("keep", encoding="utf-8")
        workspace = self.root / WORKSPACE_PATH
        inode = workspace.stat().st_ino
        unchanged = plan_local_writes(self.root, local_operations(documents))
        self.assertEqual({write.disposition for write in unchanged}, {"unchanged"})
        apply_local_write(self.root, unchanged)
        self.assertEqual(workspace.stat().st_ino, inode)
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep")

        old_body = documents[WORKSPACE_PATH]
        changed_body = old_body.replace("repo-sample", "repo-replacement")
        replacements = plan_local_writes(
            self.root,
            (
                local_operation(
                    WORKSPACE_PATH,
                    changed_body,
                    expected_prior_fingerprint=body_fingerprint(old_body),
                ),
            ),
        )
        self.assertEqual(replacements[0].disposition, "replace")
        apply_local_write(self.root, replacements)
        self.assertEqual(workspace.read_text(encoding="utf-8"), changed_body)
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep")

    def test_changed_existing_content_requires_exact_expected_fingerprint(self):
        target = self.root / WORKSPACE_PATH
        target.parent.mkdir(parents=True)
        target.write_text(build_documents()[WORKSPACE_PATH], encoding="utf-8")
        changed = build_documents()[WORKSPACE_PATH].replace("repo-sample", "repo-new")

        for expected in (None, "0" * 64):
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(ValueError, "semantic overwrite"):
                    plan_local_writes(
                        self.root,
                        (
                            local_operation(
                                WORKSPACE_PATH,
                                changed,
                                expected_prior_fingerprint=expected,
                            ),
                        ),
                    )
        with self.assertRaises(TypeError):
            plan_local_writes(
                self.root,
                (local_operation(WORKSPACE_PATH, changed),),
                expected_fingerprints={WORKSPACE_PATH: body_fingerprint(changed)},
            )

    def test_replace_rechecks_prior_fingerprint_immediately_before_mutation(self):
        target = self.root / WORKSPACE_PATH
        target.parent.mkdir(parents=True)
        old_body = build_documents()[WORKSPACE_PATH]
        target.write_text(old_body, encoding="utf-8")
        changed = old_body.replace("repo-sample", "repo-new")
        write = plan_local_writes(
            self.root,
            (
                local_operation(
                    WORKSPACE_PATH,
                    changed,
                    expected_prior_fingerprint=body_fingerprint(old_body),
                ),
            ),
        )

        target.write_text("concurrent change", encoding="utf-8")

        with self.assertRaisesRegex(LocalTransactionError, "semantic overwrite"):
            apply_local_write(self.root, write)
        self.assertEqual(target.read_text(encoding="utf-8"), "concurrent change")

    def test_create_rechecks_absence_and_local_write_cannot_move_between_roots(self):
        write = plan_local_writes(
            self.root,
            (local_operation(WORKSPACE_PATH, build_documents()[WORKSPACE_PATH]),),
        )
        target = self.root / WORKSPACE_PATH
        target.parent.mkdir(parents=True)
        target.write_text("appeared", encoding="utf-8")

        with self.assertRaisesRegex(LocalTransactionError, "semantic overwrite"):
            apply_local_write(self.root, write)
        with self.assertRaisesRegex(ValueError, "planned repository root"):
            apply_local_write(self.outside, write)

    def test_apply_rejects_a_write_body_changed_after_planning(self):
        write = plan_local_writes(
            self.root,
            (local_operation(WORKSPACE_PATH, build_documents()[WORKSPACE_PATH]),),
        )
        changed_body = write[0].body.replace("repo-sample", "repo-new")

        with self.assertRaisesRegex(ValueError, "planned document fingerprint"):
            apply_local_write(self.root, (replace(write[0], body=changed_body),))
        self.assertFalse((self.root / WORKSPACE_PATH).exists())

    def test_local_write_is_an_immutable_planned_value(self):
        write = plan_local_writes(
            self.root,
            (local_operation(WORKSPACE_PATH, build_documents()[WORKSPACE_PATH]),),
        )[0]

        self.assertIsInstance(write, LocalWrite)
        with self.assertRaises((AttributeError, TypeError)):
            write.disposition = "replace"

    def test_parent_swap_during_temp_creation_cannot_redirect_outside_root(self):
        operation = local_operation(WORKSPACE_PATH, build_documents()[WORKSPACE_PATH])
        writes = plan_local_writes(self.root, (operation,))
        original_open = os.open
        swapped = False

        def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal swapped
            if not swapped and flags & os.O_CREAT:
                elephant = self.root / ".agents/elephant"
                moved = self.root / ".agents/checked-elephant"
                elephant.rename(moved)
                elephant.symlink_to(self.outside, target_is_directory=True)
                swapped = True
            return original_open(path, flags, mode, dir_fd=dir_fd)

        with mock.patch("scripts.workspace_setup.files.os.open", side_effect=swapping_open):
            with self.assertRaisesRegex(LocalTransactionError, "containment"):
                apply_local_write(self.root, writes)

        self.assertTrue(swapped)
        self.assertFalse((self.outside / "workspace.yaml").exists())

    def test_failure_on_later_commit_rolls_back_every_earlier_output(self):
        writes = plan_local_writes(self.root, local_operations(build_documents()))
        original_replace = os.replace
        replacements = 0

        def failing_replace(source, destination, **kwargs):
            nonlocal replacements
            replacements += 1
            if replacements == 2:
                raise OSError("second commit failed")
            return original_replace(source, destination, **kwargs)

        with mock.patch("scripts.workspace_setup.files.os.replace", side_effect=failing_replace):
            with self.assertRaises(LocalTransactionError) as raised:
                apply_local_write(self.root, writes)

        self.assertTrue(any("rolled_back" in outcome.states for outcome in raised.exception.outcomes))
        self.assertEqual(list((self.root / ".agents").rglob("*.yaml")), [])
        self.assertFalse((self.root / ".agents/elephant").exists())

    def test_post_replace_fsync_failure_is_rolled_back_and_audited(self):
        writes = plan_local_writes(self.root, local_operations(build_documents()))
        original_fsync = os.fsync
        failed = False

        def failing_directory_fsync(descriptor):
            nonlocal failed
            if stat.S_ISDIR(os.fstat(descriptor).st_mode) and not failed:
                failed = True
                raise OSError("directory fsync failed")
            return original_fsync(descriptor)

        with mock.patch("scripts.workspace_setup.files.os.fsync", side_effect=failing_directory_fsync):
            with self.assertRaises(LocalTransactionError) as raised:
                apply_local_write(self.root, writes)

        self.assertTrue(failed)
        self.assertTrue(all(outcome.states[-1] == "rolled_back" for outcome in raised.exception.outcomes))
        self.assertFalse((self.root / ".agents/elephant").exists())

    def test_rollback_failure_is_explicit_and_matches_remaining_disk_state(self):
        documents = build_documents()
        first_path = ".agents/elephant/profiles/engineering.yaml"
        first_target = self.root / first_path
        first_target.parent.mkdir(parents=True)
        prior_body = documents[first_path]
        first_target.write_text(prior_body, encoding="utf-8")
        changed_body = prior_body.replace('"docs": "en"', '"docs": "fr"')
        operations = (
            local_operation(
                first_path,
                changed_body,
                expected_prior_fingerprint=body_fingerprint(prior_body),
            ),
            local_operation(
                ".agents/elephant/profiles/sample.yaml",
                documents[".agents/elephant/profiles/sample.yaml"],
            ),
        )
        writes = plan_local_writes(self.root, operations)
        original_replace = os.replace
        replacements = 0

        def failing_commit_and_rollback(source, destination, **kwargs):
            nonlocal replacements
            replacements += 1
            if replacements in {2, 3}:
                raise OSError("commit or rollback failed")
            return original_replace(source, destination, **kwargs)

        with mock.patch(
            "scripts.workspace_setup.files.os.replace",
            side_effect=failing_commit_and_rollback,
        ):
            with self.assertRaises(LocalTransactionError) as raised:
                apply_local_write(self.root, writes)

        first = next(outcome for outcome in raised.exception.outcomes if outcome.path == first_path)
        self.assertEqual(first.states[-1], "rollback_failed")
        self.assertEqual(first_target.read_text(encoding="utf-8"), changed_body)

    def test_raced_directory_created_by_another_actor_is_not_removed_on_failure(self):
        writes = plan_local_writes(
            self.root,
            (local_operation(WORKSPACE_PATH, build_documents()[WORKSPACE_PATH]),),
        )
        original_mkdir = os.mkdir
        raced = False

        def racing_mkdir(path, mode=0o777, *, dir_fd=None):
            nonlocal raced
            if path == ".agents" and not raced:
                original_mkdir(path, mode, dir_fd=dir_fd)
                raced = True
                raise FileExistsError(path)
            return original_mkdir(path, mode, dir_fd=dir_fd)

        with mock.patch("scripts.workspace_setup.files.os.mkdir", side_effect=racing_mkdir), mock.patch(
            "scripts.workspace_setup.files._revalidate_parent",
            side_effect=OSError("pre-stage failure"),
        ):
            with self.assertRaises(LocalTransactionError):
                apply_local_write(self.root, writes)

        self.assertTrue(raced)
        self.assertTrue((self.root / ".agents").is_dir())
        self.assertFalse((self.root / ".agents/elephant").exists())

    def test_stage_fsync_failure_removes_temporary_files_and_created_directories(self):
        writes = plan_local_writes(
            self.root,
            (local_operation(WORKSPACE_PATH, build_documents()[WORKSPACE_PATH]),),
        )

        with mock.patch(
            "scripts.workspace_setup.files.os.fsync",
            side_effect=OSError("stage fsync failed"),
        ):
            with self.assertRaises(LocalTransactionError):
                apply_local_write(self.root, writes)

        self.assertFalse((self.root / ".agents/elephant").exists())
        self.assertEqual(list(self.root.rglob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()

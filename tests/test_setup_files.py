from __future__ import annotations

from dataclasses import replace
import hashlib
import fcntl
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

import scripts.workspace_setup.files as setup_files

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
    ABSENT_LOCAL_CONTAINER_FINGERPRINT,
    LocalContainerOutcome,
    LocalTransactionError,
    LocalTransactionResult,
    LocalWrite,
    WORKSPACE_PATH,
    apply_local_write,
    build_local_documents,
    fingerprint_local_container,
    load_rendered_yaml,
    plan_local_writes,
    render_yaml,
)
from scripts.workspace_setup.atomic_switch import (
    AtomicRenameUnavailable,
    atomic_exchange,
    atomic_noreplace,
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


def plan_current(
    root: Path,
    operations: tuple[SetupOperation, ...],
):
    return plan_local_writes(
        root,
        operations,
        fingerprint_local_container(root),
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

    def _commit_documents(self, root: Path, documents: dict[str, str]) -> None:
        writes = plan_current(root, local_operations(documents))
        apply_local_write(root, writes)

    def _replacement_fixture(
        self,
        root: Path,
    ) -> tuple[dict[str, str], dict[str, str], tuple[LocalWrite, ...]]:
        original = build_documents()
        self._commit_documents(root, original)
        changed = dict(original)
        changed[WORKSPACE_PATH] = changed[WORKSPACE_PATH].replace(
            "repo-sample", "repo-replacement"
        )
        sample_path = ".agents/elephant/profiles/sample.yaml"
        changed[sample_path] = changed[sample_path].replace(
            '"docs": "en"', '"docs": "fr"'
        )
        expected = {
            path: body_fingerprint(original[path])
            for path in changed
            if changed[path] != original[path]
        }
        writes = plan_current(
            root,
            local_operations(
                changed,
                expected_prior_fingerprints=expected,
            ),
        )
        return original, changed, writes

    def test_complete_container_fingerprint_covers_absence_and_unrelated_content(self):
        self.assertEqual(
            fingerprint_local_container(self.root),
            ABSENT_LOCAL_CONTAINER_FINGERPRINT,
        )
        unrelated = self.root / ".agents/unrelated/note.txt"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text("first", encoding="utf-8")
        first = fingerprint_local_container(self.root)

        unrelated.write_text("second", encoding="utf-8")

        self.assertNotEqual(first, fingerprint_local_container(self.root))

    def test_container_fingerprint_rejects_symlinks_and_special_files(self):
        agents = self.root / ".agents"
        agents.mkdir()
        (agents / "escape").symlink_to(self.outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "unsupported|symlink"):
            fingerprint_local_container(self.root)

        (agents / "escape").unlink()
        os.mkfifo(agents / "pipe")
        with self.assertRaisesRegex(ValueError, "unsupported"):
            fingerprint_local_container(self.root)

    def test_container_fingerprint_rejects_hard_linked_files(self):
        agents = self.root / ".agents"
        agents.mkdir()
        (agents / "first").write_text("shared", encoding="utf-8")
        os.link(agents / "first", agents / "second")

        with self.assertRaisesRegex(ValueError, "hard link|unsupported"):
            fingerprint_local_container(self.root)

    def test_platform_atomic_switch_exchanges_or_creates_one_root_child(self):
        (self.root / "old").mkdir()
        (self.root / "old/value").write_text("old", encoding="utf-8")
        (self.root / "stage").mkdir()
        (self.root / "stage/value").write_text("new", encoding="utf-8")
        root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            atomic_exchange(root_fd, "old", "stage")
            self.assertEqual((self.root / "old/value").read_text(), "new")
            self.assertEqual((self.root / "stage/value").read_text(), "old")

            (self.root / "created-stage").mkdir()
            atomic_noreplace(root_fd, "created-stage", "created")
            self.assertTrue((self.root / "created").is_dir())
            (self.root / "blocked-stage").mkdir()
            with self.assertRaises(FileExistsError):
                atomic_noreplace(root_fd, "blocked-stage", "created")
        finally:
            os.close(root_fd)

    def test_platform_atomic_switch_fails_closed_without_native_primitive(self):
        (self.root / "old").mkdir()
        (self.root / "stage").mkdir()
        root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            with mock.patch(
                "scripts.workspace_setup.atomic_switch._renameatx_np", None
            ), mock.patch("scripts.workspace_setup.atomic_switch._renameat2", None):
                with self.assertRaises(AtomicRenameUnavailable):
                    atomic_exchange(root_fd, "old", "stage")
        finally:
            os.close(root_fd)
        self.assertTrue((self.root / "old").is_dir())
        self.assertTrue((self.root / "stage").is_dir())

    def test_container_commit_preserves_unrelated_tree_and_switches_once(self):
        unrelated = self.root / ".agents/unrelated/nested.txt"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_bytes(b"unrelated\x00content")
        os.chmod(unrelated, 0o640)
        prior = fingerprint_local_container(self.root)
        documents = build_documents()
        writes = plan_local_writes(
            self.root,
            local_operations(documents),
            prior,
        )

        result = apply_local_write(self.root, writes)

        self.assertIsInstance(result.container, LocalContainerOutcome)
        self.assertEqual(result.container.disposition, "replaced")
        self.assertEqual(result.container.prior_fingerprint, prior)
        self.assertIsNotNone(result.container.retained_stage_name)
        retained_stage = self.root / result.container.retained_stage_name
        self.assertTrue(retained_stage.is_dir())
        root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            self.assertEqual(
                setup_files.fingerprint_container_at(
                    root_fd, result.container.retained_stage_name
                ),
                prior,
            )
        finally:
            os.close(root_fd)
        self.assertEqual(
            result.container.observed_fingerprint,
            fingerprint_local_container(self.root),
        )
        self.assertEqual(unrelated.read_bytes(), b"unrelated\x00content")
        self.assertEqual(stat.S_IMODE(unrelated.stat().st_mode), 0o640)
        self.assertEqual(
            {path: (self.root / path).read_text(encoding="utf-8") for path in documents},
            documents,
        )

    def test_retained_stage_is_non_authoritative_unique_and_never_name_deleted(self):
        original, changed, writes = self._replacement_fixture(self.root)
        first = apply_local_write(self.root, writes, owner_id="retained-first")
        retained_name = first.container.retained_stage_name
        self.assertIsNotNone(retained_name)
        retained = self.root / retained_name
        held = self.root / f"{retained_name}.held"
        retained.rename(held)
        replacement = self.root / retained_name
        replacement.mkdir()
        (replacement / "unrelated.txt").write_text("owner", encoding="utf-8")

        future = plan_current(self.root, local_operations(changed))
        second = apply_local_write(self.root, future, owner_id="retained-second")

        self.assertEqual(second.container.disposition, "unchanged")
        self.assertNotEqual(second.container.retained_stage_name, retained_name)
        self.assertEqual(
            (replacement / "unrelated.txt").read_text(encoding="utf-8"),
            "owner",
        )
        self.assertEqual(
            (held / "elephant/workspace.yaml").read_text(encoding="utf-8"),
            original[WORKSPACE_PATH],
        )
        self.assertEqual(
            fingerprint_local_container(self.root),
            second.container.observed_fingerprint,
        )

    def test_repository_root_lock_excludes_an_independent_setup_owner(self):
        root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        fcntl.flock(root_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            prior = fingerprint_local_container(self.root)
            writes = plan_local_writes(
                self.root,
                local_operations(build_documents()),
                prior,
            )
            with self.assertRaisesRegex(LocalTransactionError, "setup lock"):
                apply_local_write(self.root, writes)
        finally:
            os.close(root_fd)
        self.assertFalse((self.root / ".agents").exists())

    def test_explicit_transaction_owner_must_be_nonblank(self):
        writes = plan_current(
            self.root,
            local_operations(build_documents()),
        )
        with self.assertRaisesRegex(ValueError, "owner_id"):
            apply_local_write(self.root, writes, owner_id="")
        self.assertFalse((self.root / ".agents").exists())

    def test_process_death_before_or_after_switch_exposes_only_complete_tree(self):
        for timing in ("before", "after"):
            with self.subTest(timing=timing):
                root = self.root / timing
                root.mkdir()
                original, changed, writes = self._replacement_fixture(root)
                native_exchange = setup_files.atomic_exchange
                child = os.fork()
                if child == 0:
                    def die_at_switch(parent_fd, first, second):
                        if timing == "before":
                            os._exit(71)
                        native_exchange(parent_fd, first, second)
                        os._exit(72)

                    with mock.patch(
                        "scripts.workspace_setup.files.atomic_exchange",
                        side_effect=die_at_switch,
                    ):
                        apply_local_write(root, writes)
                    os._exit(70)
                _, status = os.waitpid(child, 0)
                self.assertEqual(os.WEXITSTATUS(status), 71 if timing == "before" else 72)
                visible = {
                    path: (root / path).read_text(encoding="utf-8")
                    for path in original
                }
                self.assertEqual(visible, original if timing == "before" else changed)

    def test_concurrent_prior_mutation_is_captured_and_restored_without_clobber(self):
        self._commit_documents(self.root, build_documents())
        unrelated = self.root / ".agents/unrelated.txt"
        unrelated.write_text("approved", encoding="utf-8")
        original, changed, writes = self._replacement_fixture(self.root)
        native_exchange = setup_files.atomic_exchange
        calls = 0

        def mutate_before_exchange(parent_fd, first, second):
            nonlocal calls
            calls += 1
            if calls == 1:
                unrelated.write_text("concurrent-owner", encoding="utf-8")
            return native_exchange(parent_fd, first, second)

        with mock.patch(
            "scripts.workspace_setup.files.atomic_exchange",
            side_effect=mutate_before_exchange,
        ):
            with self.assertRaises(LocalTransactionError) as raised:
                apply_local_write(self.root, writes)

        self.assertEqual(raised.exception.container.disposition, "rolled_back")
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "concurrent-owner")
        self.assertEqual(
            (self.root / WORKSPACE_PATH).read_text(encoding="utf-8"),
            original[WORKSPACE_PATH],
        )
        self.assertNotEqual(original[WORKSPACE_PATH], changed[WORKSPACE_PATH])

    def test_rollback_evidence_uses_one_final_active_container_snapshot(self):
        original, _, writes = self._replacement_fixture(self.root)
        unrelated = self.root / ".agents/unrelated.txt"
        unrelated.write_text("approved", encoding="utf-8")
        writes = plan_current(
            self.root,
            tuple(write.operation for write in writes),
        )
        native_exchange = setup_files.atomic_exchange
        native_fingerprint = setup_files.fingerprint_container_at
        exchange_calls = 0
        rollback_exchanged = False
        final_mutation_applied = False

        def mutate_around_exchange(parent_fd, first, second):
            nonlocal exchange_calls, rollback_exchanged
            exchange_calls += 1
            if exchange_calls == 1:
                unrelated.write_text("prior-race", encoding="utf-8")
            result = native_exchange(parent_fd, first, second)
            if exchange_calls == 2:
                rollback_exchanged = True
            return result

        def mutate_before_final_observation(parent_fd, name=".agents"):
            nonlocal final_mutation_applied
            if (
                rollback_exchanged
                and not final_mutation_applied
                and name.startswith(".agents.setup-stage-")
            ):
                (self.root / WORKSPACE_PATH).write_text(
                    "final-active-owner", encoding="utf-8"
                )
                final_mutation_applied = True
            return native_fingerprint(parent_fd, name)

        with mock.patch(
            "scripts.workspace_setup.files.atomic_exchange",
            side_effect=mutate_around_exchange,
        ), mock.patch(
            "scripts.workspace_setup.files.fingerprint_container_at",
            side_effect=mutate_before_final_observation,
        ):
            with self.assertRaises(LocalTransactionError) as raised:
                apply_local_write(self.root, writes)

        self.assertTrue(final_mutation_applied)
        self.assertEqual(raised.exception.container.disposition, "rolled_back")
        self.assertEqual(
            raised.exception.container.observed_fingerprint,
            fingerprint_local_container(self.root),
        )
        workspace_outcome = next(
            outcome
            for outcome in raised.exception.outcomes
            if outcome.path == WORKSPACE_PATH
        )
        self.assertEqual(
            workspace_outcome.observed_fingerprint,
            hashlib.sha256(b"final-active-owner").hexdigest(),
        )
        self.assertNotEqual(
            (self.root / WORKSPACE_PATH).read_text(encoding="utf-8"),
            original[WORKSPACE_PATH],
        )

    def test_descendant_move_and_symlink_during_switch_never_writes_outside_root(self):
        original, changed, writes = self._replacement_fixture(self.root)
        native_exchange = setup_files.atomic_exchange
        moved_elephant = self.outside / "moved-elephant"
        attacked = False

        def attack_descendant_then_exchange(parent_fd, first, second):
            nonlocal attacked
            if not attacked:
                (self.root / ".agents/elephant").rename(moved_elephant)
                (self.root / ".agents/elephant").symlink_to(
                    moved_elephant,
                    target_is_directory=True,
                )
                attacked = True
            return native_exchange(parent_fd, first, second)

        with mock.patch(
            "scripts.workspace_setup.files.atomic_exchange",
            side_effect=attack_descendant_then_exchange,
        ):
            with self.assertRaises(LocalTransactionError) as raised:
                apply_local_write(self.root, writes)

        self.assertTrue(attacked)
        self.assertEqual(raised.exception.container.disposition, "rolled_back")
        self.assertEqual(
            (moved_elephant / "workspace.yaml").read_text(encoding="utf-8"),
            original[WORKSPACE_PATH],
        )
        self.assertNotEqual(
            (moved_elephant / "workspace.yaml").read_text(encoding="utf-8"),
            changed[WORKSPACE_PATH],
        )

    def test_concurrent_active_mutation_during_rollback_is_preserved(self):
        original, _, writes = self._replacement_fixture(self.root)
        unrelated = self.root / ".agents/unrelated.txt"
        unrelated.write_text("approved", encoding="utf-8")
        writes = plan_current(
            self.root,
            tuple(write.operation for write in writes),
        )
        native_exchange = setup_files.atomic_exchange
        calls = 0

        def mutate_commit_and_rollback(parent_fd, first, second):
            nonlocal calls
            calls += 1
            if calls == 1:
                unrelated.write_text("prior-race", encoding="utf-8")
            elif calls == 2:
                (self.root / WORKSPACE_PATH).write_text(
                    "concurrent-active-owner", encoding="utf-8"
                )
            return native_exchange(parent_fd, first, second)

        with mock.patch(
            "scripts.workspace_setup.files.atomic_exchange",
            side_effect=mutate_commit_and_rollback,
        ):
            with self.assertRaises(LocalTransactionError) as raised:
                apply_local_write(self.root, writes)

        self.assertEqual(raised.exception.container.disposition, "rollback_failed")
        self.assertEqual(
            (self.root / WORKSPACE_PATH).read_text(encoding="utf-8"),
            "concurrent-active-owner",
        )
        self.assertEqual(
            raised.exception.container.observed_fingerprint,
            fingerprint_local_container(self.root),
        )
        self.assertNotEqual(
            (self.root / WORKSPACE_PATH).read_text(encoding="utf-8"),
            original[WORKSPACE_PATH],
        )

    def test_absent_container_noreplace_preserves_concurrent_owner(self):
        writes = plan_current(
            self.root,
            local_operations(build_documents()),
        )
        native_noreplace = setup_files.atomic_noreplace

        def create_owner_before_commit(parent_fd, source, target):
            agents = self.root / ".agents"
            agents.mkdir()
            (agents / "owner.txt").write_text("concurrent", encoding="utf-8")
            return native_noreplace(parent_fd, source, target)

        with mock.patch(
            "scripts.workspace_setup.files.atomic_noreplace",
            side_effect=create_owner_before_commit,
        ):
            with self.assertRaises(LocalTransactionError) as raised:
                apply_local_write(self.root, writes)

        self.assertEqual(raised.exception.container.disposition, "not_applied")
        self.assertEqual(
            (self.root / ".agents/owner.txt").read_text(encoding="utf-8"),
            "concurrent",
        )

    def test_apply_fails_closed_when_atomic_exchange_is_unsupported(self):
        original, _, writes = self._replacement_fixture(self.root)
        with mock.patch(
            "scripts.workspace_setup.files.atomic_exchange",
            side_effect=AtomicRenameUnavailable("unsupported"),
        ):
            with self.assertRaises(LocalTransactionError) as raised:
                apply_local_write(self.root, writes)

        self.assertEqual(raised.exception.container.disposition, "not_applied")
        self.assertEqual(
            (self.root / WORKSPACE_PATH).read_text(encoding="utf-8"),
            original[WORKSPACE_PATH],
        )

    def test_only_workspace_and_direct_profile_paths_are_allowed(self):
        for path in (
            "README.md",
            ".agents/elephant/profiles/nested/a.yaml",
            "../outside.yaml",
            ".agents/elephant/profiles/a.yml",
        ):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "setup output path"):
                    plan_current(self.root, (local_operation(path, "body"),))

    def test_symlinked_parent_or_target_cannot_escape_repository(self):
        (self.root / ".agents").symlink_to(self.outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "unsupported|containment"):
            plan_local_writes(
                self.root,
                (local_operation(WORKSPACE_PATH, build_documents()[WORKSPACE_PATH]),),
                ABSENT_LOCAL_CONTAINER_FINGERPRINT,
            )

        (self.root / ".agents").unlink()
        target = self.root / WORKSPACE_PATH
        target.parent.mkdir(parents=True)
        expected_container = fingerprint_local_container(self.root)
        outside_target = self.outside / "workspace.yaml"
        outside_target.write_text("outside", encoding="utf-8")
        target.symlink_to(outside_target)
        with self.assertRaisesRegex(ValueError, "unsupported|containment"):
            plan_local_writes(
                self.root,
                (local_operation(WORKSPACE_PATH, build_documents()[WORKSPACE_PATH]),),
                expected_container,
            )

    def test_create_unchanged_and_replace_are_classified_without_unrelated_deletes(self):
        documents = build_documents()
        creates = plan_current(self.root, local_operations(documents))
        self.assertEqual({write.disposition for write in creates}, {"create"})
        created = apply_local_write(self.root, creates)
        self.assertIsInstance(created, LocalTransactionResult)
        self.assertEqual({outcome.states[-1] for outcome in created.outcomes}, {"durable"})

        unrelated = self.root / ".agents/elephant/keep.txt"
        unrelated.write_text("keep", encoding="utf-8")
        workspace = self.root / WORKSPACE_PATH
        inode = workspace.stat().st_ino
        unchanged = plan_current(self.root, local_operations(documents))
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
            fingerprint_local_container(self.root),
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
                        fingerprint_local_container(self.root),
                    )
        with self.assertRaises(TypeError):
            plan_local_writes(
                self.root,
                (local_operation(WORKSPACE_PATH, changed),),
                fingerprint_local_container(self.root),
                expected_fingerprints={WORKSPACE_PATH: body_fingerprint(changed)},
            )

    def test_apply_rejects_a_write_body_changed_after_planning(self):
        write = plan_current(
            self.root,
            (local_operation(WORKSPACE_PATH, build_documents()[WORKSPACE_PATH]),),
        )
        changed_body = write[0].body.replace("repo-sample", "repo-new")

        with self.assertRaisesRegex(ValueError, "planned document fingerprint"):
            apply_local_write(self.root, (replace(write[0], body=changed_body),))
        self.assertFalse((self.root / WORKSPACE_PATH).exists())

    def test_local_write_is_an_immutable_planned_value(self):
        write = plan_current(
            self.root,
            (local_operation(WORKSPACE_PATH, build_documents()[WORKSPACE_PATH]),),
        )[0]

        self.assertIsInstance(write, LocalWrite)
        with self.assertRaises((AttributeError, TypeError)):
            write.disposition = "replace"


if __name__ == "__main__":
    unittest.main()

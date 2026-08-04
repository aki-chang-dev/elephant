from pathlib import Path
import tempfile
import unittest

import scripts.workspace_setup.models as setup_models
from scripts.workspace_setup import (
    Candidate,
    Confidence,
    ConfirmedProduct,
    Evidence,
    ExternalDiscovery,
    confirm_topology,
    discover_repository,
    propose_topology,
    normalize_external_discovery,
)


class RepositoryProductEvidenceTests(unittest.TestCase):
    def test_product_document_proposes_product_with_repository_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            (root / "docs" / "products").mkdir(parents=True)
            (root / "apps" / "tracker").mkdir(parents=True)
            (root / "package.json").write_text(
                '{"workspaces":["apps/*"]}', encoding="utf-8"
            )
            (root / "apps" / "tracker" / "package.json").write_text(
                '{"name":"tracker"}', encoding="utf-8"
            )
            (root / "docs" / "products" / "clickfalcon.md").write_text(
                "# ClickFalcon\n\nProduct overview.\n", encoding="utf-8"
            )

            discovery = discover_repository(root)
            proposal = propose_topology(discovery, ExternalDiscovery(objects=()))

        self.assertEqual(tuple(value.key for value in proposal.product_candidates), ("clickfalcon",))
        candidate = proposal.product_candidates[0]
        self.assertEqual(candidate.display_name, "ClickFalcon")
        self.assertEqual(
            tuple((item.source, item.ref, item.value) for item in candidate.evidence),
            (("repository_document", "docs/products/clickfalcon.md", "ClickFalcon"),),
        )
        self.assertNotIn("tracker", tuple(value.key for value in proposal.product_candidates))

    def test_repository_and_external_product_evidence_merge_without_duplicate_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            (root / "docs" / "products").mkdir(parents=True)
            (root / "package.json").write_text(
                '{"repository":{"id":"repo-sample"}}',
                encoding="utf-8",
            )
            (root / "docs" / "products" / "clickfalcon.md").write_text(
                "# ClickFalcon\n",
                encoding="utf-8",
            )
            external = normalize_external_discovery((
                {
                    "provider": "notion",
                    "kind": "product",
                    "key": "clickfalcon",
                    "display_name": "ClickFalcon",
                    "external_id": "notion-product-1",
                },
            ))

            proposal = propose_topology(discover_repository(root), external)

        self.assertEqual(
            tuple(candidate.key for candidate in proposal.product_candidates),
            ("clickfalcon",),
        )
        self.assertEqual(
            proposal.product_candidates[0].evidence,
            (
                Evidence(
                    "notion",
                    "product:notion-product-1",
                    "ClickFalcon",
                ),
                Evidence(
                    "repository_document",
                    "docs/products/clickfalcon.md",
                    "ClickFalcon",
                ),
            ),
        )

    def test_repository_and_external_display_disagreement_is_an_explicit_conflict(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            (root / "docs" / "products").mkdir(parents=True)
            (root / "package.json").write_text(
                '{"repository":{"id":"repo-sample"}}',
                encoding="utf-8",
            )
            (root / "docs" / "products" / "sample.md").write_text(
                "# Local Sample\n",
                encoding="utf-8",
            )
            external = normalize_external_discovery((
                {
                    "provider": "notion",
                    "kind": "product",
                    "key": "sample",
                    "display_name": "Remote Sample",
                    "external_id": "notion-product-1",
                },
            ))

            proposal = propose_topology(discover_repository(root), external)

        conflict = next(
            value for value in proposal.conflicts if value.key == "product.sample"
        )
        self.assertEqual(conflict.subject, "product")
        self.assertEqual(
            {evidence.source for evidence in conflict.evidence},
            {"repository_document", "notion"},
        )
        self.assertEqual(
            {alternative.rsplit(" (", 1)[0] for alternative in conflict.alternatives},
            {"Local Sample", "Remote Sample"},
        )

    def test_repository_alternative_is_retained_in_an_existing_external_conflict(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            (root / "docs" / "products").mkdir(parents=True)
            (root / "package.json").write_text(
                '{"repository":{"id":"repo-sample"}}',
                encoding="utf-8",
            )
            (root / "docs" / "products" / "sample.md").write_text(
                "# Local Sample\n",
                encoding="utf-8",
            )
            external = normalize_external_discovery(
                tuple(
                    {
                        "provider": "notion",
                        "kind": "product",
                        "key": "sample",
                        "display_name": "Remote Sample",
                        "external_id": external_id,
                    }
                    for external_id in ("one", "two")
                )
            )

            proposal = propose_topology(discover_repository(root), external)

        conflicts = tuple(
            value for value in proposal.conflicts if value.key == "product.sample"
        )
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(
            {alternative.rsplit(" (", 1)[0] for alternative in conflicts[0].alternatives},
            {"Local Sample", "Remote Sample"},
        )
        self.assertEqual(
            {evidence.source for evidence in conflicts[0].evidence},
            {"repository_document", "notion"},
        )


class OwnerDecisionTests(unittest.TestCase):
    def test_low_confidence_repository_identity_requires_explicit_answer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "uncertain-repository"
            root.mkdir()
            (root / "package.json").write_text('{"name":"root"}', encoding="utf-8")
            proposal = propose_topology(
                discover_repository(root),
                ExternalDiscovery(objects=()),
            )

        self.assertEqual(proposal.repository_candidate.confidence.value, "low")
        with self.assertRaisesRegex(ValueError, "repository identity.*explicit"):
            confirm_topology(proposal, (), ())

    def test_explicit_repository_answer_preserves_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "uncertain-repository"
            root.mkdir()
            (root / "package.json").write_text('{"name":"root"}', encoding="utf-8")
            proposal = propose_topology(
                discover_repository(root),
                ExternalDiscovery(objects=()),
            )

        confirmed = confirm_topology(
            proposal,
            (),
            (),
            repository_id="owner-approved-repository",
        )

        self.assertEqual(confirmed.repository_id, "owner-approved-repository")
        self.assertEqual(
            tuple(
                (evidence.source, evidence.ref, evidence.value)
                for evidence in getattr(confirmed, "repository_evidence", ())
            ),
            (
                (
                    "filesystem",
                    proposal.repository_candidate.evidence[0].ref,
                    "uncertain-repository",
                ),
                ("owner", "repository.id", "owner-approved-repository"),
            ),
        )

    def test_owner_can_add_a_product_backed_by_discovered_document_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            (root / "docs").mkdir(parents=True)
            (root / "package.json").write_text('{"name":"root"}', encoding="utf-8")
            (root / "docs" / "clickfalcon-overview.md").write_text(
                "# ClickFalcon\n", encoding="utf-8"
            )
            proposal = propose_topology(
                discover_repository(root),
                ExternalDiscovery(objects=()),
            )
        addition = Candidate(
            key="clickfalcon",
            display_name="ClickFalcon",
            evidence=(
                Evidence(
                    "repository_document",
                    "docs/clickfalcon-overview.md",
                    "ClickFalcon",
                ),
            ),
            confidence=Confidence.CONFIRMED,
        )

        try:
            confirmed = confirm_topology(
                proposal,
                (ConfirmedProduct("clickfalcon", "ClickFalcon", ()),),
                (),
                repository_id="owner-repository",
                product_additions=(addition,),
            )
        except TypeError as error:
            self.fail(f"owner product additions are not expressible: {error}")

        self.assertEqual(
            tuple(value.key for value in getattr(confirmed, "product_evidence", ())),
            ("clickfalcon",),
        )
        self.assertEqual(
            confirmed.product_evidence[0].evidence,
            addition.evidence,
        )

    def test_owner_product_addition_rejects_undiscovered_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            (root / "docs").mkdir(parents=True)
            (root / "package.json").write_text('{"name":"root"}', encoding="utf-8")
            (root / "docs" / "known.md").write_text("# Known\n", encoding="utf-8")
            proposal = propose_topology(
                discover_repository(root),
                ExternalDiscovery(objects=()),
            )
        unsupported = Candidate(
            "invented",
            "Invented",
            (Evidence("repository_document", "docs/not-discovered.md", "Invented"),),
            Confidence.CONFIRMED,
        )

        with self.assertRaisesRegex(ValueError, "discovered product evidence"):
            confirm_topology(
                proposal,
                (ConfirmedProduct("invented", "Invented", ()),),
                (),
                repository_id="owner-repository",
                product_additions=(unsupported,),
            )

    def test_owner_product_addition_rejects_symlinked_document_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "repository"
            (root / "docs").mkdir(parents=True)
            (root / "package.json").write_text('{"name":"root"}', encoding="utf-8")
            outside = base / "outside.md"
            outside.write_text("# Outside Product\n", encoding="utf-8")
            (root / "docs" / "linked.md").symlink_to(outside)
            proposal = propose_topology(
                discover_repository(root),
                ExternalDiscovery(objects=()),
            )
        unsupported = Candidate(
            "outside",
            "Outside Product",
            (
                Evidence(
                    "repository_document",
                    "docs/linked.md",
                    "Linked",
                ),
            ),
            Confidence.CONFIRMED,
        )

        with self.assertRaisesRegex(ValueError, "discovered product evidence"):
            confirm_topology(
                proposal,
                (ConfirmedProduct("outside", "Outside Product", ()),),
                (),
                repository_id="owner-repository",
                product_additions=(unsupported,),
            )

    def test_owner_product_addition_rejects_modified_discovered_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            (root / "docs").mkdir(parents=True)
            (root / "package.json").write_text('{"name":"root"}', encoding="utf-8")
            (root / "docs" / "known.md").write_text("# Known\n", encoding="utf-8")
            proposal = propose_topology(
                discover_repository(root),
                ExternalDiscovery(objects=()),
            )
        modified = Candidate(
            "invented",
            "Invented",
            (
                Evidence(
                    "repository_document",
                    "docs/known.md",
                    "Invented rather than Known",
                ),
            ),
            Confidence.CONFIRMED,
        )

        with self.assertRaisesRegex(ValueError, "discovered product evidence"):
            confirm_topology(
                proposal,
                (ConfirmedProduct("invented", "Invented", ()),),
                (),
                repository_id="owner-repository",
                product_additions=(modified,),
            )

    def test_typed_conflict_resolution_enters_confirmed_topology(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            root.mkdir()
            (root / "package.json").write_text('{"name":"root"}', encoding="utf-8")
            external = normalize_external_discovery((
                {
                    "provider": "linear",
                    "kind": "product",
                    "key": "sample",
                    "display_name": "Sample",
                    "external_id": "one",
                },
                {
                    "provider": "linear",
                    "kind": "product",
                    "key": "sample",
                    "display_name": "Example",
                    "external_id": "two",
                },
            ))
            proposal = propose_topology(discover_repository(root), external)
        resolution_type = getattr(setup_models, "ConflictResolution", None)
        if resolution_type is None:
            self.fail("typed ConflictResolution is not available")
        resolution = resolution_type(
            conflict_key="product.sample",
            selected_alternative="Sample (one)",
            rationale="The owner selected the existing canonical product label.",
        )

        try:
            confirmed = confirm_topology(
                proposal,
                (ConfirmedProduct("sample", "Sample", ()),),
                (),
                repository_id="owner-repository",
                conflict_resolutions=(resolution,),
            )
        except TypeError as error:
            self.fail(f"typed conflict resolutions are not expressible: {error}")

        self.assertEqual(confirmed.conflict_resolutions, (resolution,))
        with self.assertRaisesRegex(ValueError, "selected alternative.*confirmed"):
            confirm_topology(
                proposal,
                (ConfirmedProduct("sample", "Example", ()),),
                (),
                repository_id="owner-repository",
                conflict_resolutions=(resolution,),
            )


if __name__ == "__main__":
    unittest.main()

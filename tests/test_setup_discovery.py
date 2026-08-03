from pathlib import Path
import tempfile
import unittest

from scripts.workspace_setup import (
    ConfirmedDomain,
    ConfirmedProduct,
    ExternalDiscovery,
    ExternalObject,
    discover_repository,
    normalize_external_discovery,
    propose_topology,
    confirm_topology,
)


FIXTURES = Path(__file__).parent / "fixtures" / "setup-workspace"


class RepositoryDiscoveryTests(unittest.TestCase):
    def test_discovers_workspace_units_and_dependency_edges(self):
        result = discover_repository(FIXTURES / "multi-product")
        self.assertEqual(
            tuple(unit.path for unit in result.workspace_units),
            ("apps/alpha", "apps/beta"),
        )
        self.assertEqual(
            tuple((edge.source, edge.target) for edge in result.dependencies),
            (("apps/alpha", "apps/beta"),),
        )

    def test_discovery_is_read_only(self):
        root = FIXTURES / "single-product"
        before = sorted(path.relative_to(root) for path in root.rglob("*"))
        discover_repository(root)
        after = sorted(path.relative_to(root) for path in root.rglob("*"))
        self.assertEqual(after, before)

    def test_discovers_direct_workspace_directories_and_repository_identity(self):
        result = discover_repository(FIXTURES / "single-product")
        self.assertEqual(tuple(unit.path for unit in result.workspace_units), ("apps/web",))
        self.assertEqual(result.repository_candidate.key, "fixture-single")
        self.assertEqual(result.repository_candidate.evidence[0].source, "package.json")

    def test_malformed_manifest_is_explicit_problem(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "package.json").write_text("{not json", encoding="utf-8")
            result = discover_repository(root)
        self.assertEqual(len(result.problems), 1)
        self.assertIn("invalid JSON", result.problems[0])

    def test_invalid_nested_manifest_is_a_problem_not_a_silent_skip(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "apps" / "broken").mkdir(parents=True)
            (root / "package.json").write_text('{"name":"root"}', encoding="utf-8")
            (root / "apps" / "broken" / "package.json").write_text("[]", encoding="utf-8")
            result = discover_repository(root)
        self.assertEqual(result.workspace_units, ())
        self.assertTrue(any("manifest must be a JSON object" in problem for problem in result.problems))


class TopologyProposalTests(unittest.TestCase):
    def test_applications_and_packages_never_become_products_by_themselves(self):
        repository = discover_repository(FIXTURES / "multi-product")
        proposal = propose_topology(repository, ExternalDiscovery(objects=()))
        self.assertEqual(proposal.product_candidates, ())
        self.assertEqual(
            tuple(candidate.key for candidate in proposal.domain_candidates),
            ("alpha", "beta"),
        )

    def test_external_product_evidence_has_provenance_and_owner_question(self):
        repository = discover_repository(FIXTURES / "single-product")
        external = normalize_external_discovery((
            {
                "provider": "linear",
                "kind": "product",
                "key": "sample",
                "display_name": "Sample",
                "external_id": "label-sample",
            },
        ))
        proposal = propose_topology(repository, external)
        self.assertEqual(proposal.product_candidates[0].key, "sample")
        self.assertEqual(proposal.product_candidates[0].evidence[0].source, "linear")
        self.assertEqual(proposal.questions[0].key, "product.sample.confirm")

    def test_normalization_sorts_and_preserves_duplicate_provenance(self):
        external = normalize_external_discovery((
            {"provider": "z", "kind": "product", "key": "sample", "display_name": "Sample", "external_id": "2"},
            {"provider": "a", "kind": "product", "key": "sample", "display_name": "Sample", "external_id": "1"},
            {"provider": "a", "kind": "product", "key": "sample", "display_name": "Sample", "external_id": "1"},
        ))
        self.assertEqual(
            tuple((value.provider, value.external_id) for value in external.objects),
            (("a", "1"), ("a", "1"), ("z", "2")),
        )
        proposal = propose_topology(discover_repository(FIXTURES / "conflict"), external)
        self.assertEqual(len(proposal.product_candidates[0].evidence), 3)

    def test_conflicting_external_names_or_ids_require_resolution(self):
        external = normalize_external_discovery((
            {"provider": "linear", "kind": "product", "key": "sample", "display_name": "Sample", "external_id": "one"},
            {"provider": "linear", "kind": "product", "key": "sample", "display_name": "Example", "external_id": "two"},
        ))
        proposal = propose_topology(discover_repository(FIXTURES / "conflict"), external)
        self.assertEqual(proposal.conflicts[0].key, "product.sample")
        with self.assertRaisesRegex(ValueError, "unresolved conflicts"):
            confirm_topology(
                proposal,
                (ConfirmedProduct("sample", "Sample", ()),),
                (),
            )

    def test_confirmation_requires_independent_reciprocal_mapping(self):
        repository = discover_repository(FIXTURES / "multi-product")
        external = normalize_external_discovery((
            {"provider": "linear", "kind": "product", "key": "commerce", "display_name": "Commerce", "external_id": "label-commerce"},
            {"provider": "linear", "kind": "product", "key": "identity", "display_name": "Identity", "external_id": "label-identity"},
        ))
        proposal = propose_topology(repository, external)
        products = (
            ConfirmedProduct("commerce", "Commerce", ("alpha",)),
            ConfirmedProduct("identity", "Identity", ("beta",)),
        )
        domains = (
            ConfirmedDomain("alpha", "Alpha", ("commerce",), ("apps/alpha",), (), ()),
            ConfirmedDomain("beta", "Beta", ("identity",), ("apps/beta",), (), ()),
        )
        confirmed = confirm_topology(proposal, products, domains)
        self.assertEqual(tuple(product.key for product in confirmed.products), ("commerce", "identity"))
        self.assertEqual(tuple(domain.key for domain in confirmed.domains), ("alpha", "beta"))

    def test_confirmation_rejects_unknown_duplicate_and_nonreciprocal_keys(self):
        proposal = propose_topology(
            discover_repository(FIXTURES / "multi-product"),
            normalize_external_discovery((
                {"provider": "linear", "kind": "product", "key": "product", "display_name": "Product", "external_id": "p"},
            )),
        )
        domain = ConfirmedDomain("alpha", "Alpha", ("product",), ("apps/alpha",), (), ())
        with self.assertRaisesRegex(ValueError, "unknown product"):
            confirm_topology(proposal, (ConfirmedProduct("other", "Other", ()),), ())
        with self.assertRaisesRegex(ValueError, "duplicate product"):
            confirm_topology(
                proposal,
                (ConfirmedProduct("product", "Product", ()), ConfirmedProduct("product", "Product", ())),
                (),
            )
        with self.assertRaisesRegex(ValueError, "reciprocal"):
            confirm_topology(proposal, (ConfirmedProduct("product", "Product", ()),), (domain,))

    def test_external_records_require_mapping_and_stable_identifiers(self):
        for record in ({"provider": "linear"}, {"provider": "linear", "kind": "product", "key": "x", "display_name": "X", "external_id": ""}):
            with self.subTest(record=record):
                with self.assertRaisesRegex((TypeError, ValueError), "external"):
                    normalize_external_discovery((record,))

    def test_external_value_boundary_rejects_empty_fields_and_non_objects(self):
        with self.assertRaisesRegex(ValueError, "external object"):
            ExternalObject("", "product", "sample", "Sample", "id")
        with self.assertRaisesRegex(TypeError, "objects"):
            ExternalDiscovery(objects=("not-an-object",))


if __name__ == "__main__":
    unittest.main()

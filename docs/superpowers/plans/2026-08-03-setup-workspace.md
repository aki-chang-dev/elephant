# Setup Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the provider-neutral `setup-workspace` discovery, proposal, dry-run, approved provisioning, read-back, round-trip, and local-config pipeline without activating the v3 shipping runtime.

**Architecture:** Add a pure-Python setup package beside `workspace_core`. Repository discovery and host-supplied external snapshots produce evidence-bearing product and engineering-domain candidates; an owner-confirmed topology becomes a deterministic dry-run manifest whose SHA-256 fingerprint is the write authority. An adapter-neutral apply engine performs only approved idempotent operations, verifies every mutation by read-back, executes disposable binding round trips, and writes `.agents/elephant/workspace.yaml` plus scoped profiles only after external readiness passes. Fake adapters prove the whole protocol; concrete Linear and Notion adapters remain Phase 3 and Phase 4 work.

**Tech Stack:** Python 3 standard library (`dataclasses`, `enum`, `hashlib`, `json`, `pathlib`, `tempfile`, `typing.Protocol`), `unittest`, Markdown skill/reference assets, existing Elephant compatibility and plugin validators.

## Global Constraints

- Phase 2 consumes the exact v3 schemas and vocabulary from `scripts/workspace_core/`; it does not rename or duplicate them.
- The active v2 `init-profile`, `ship-story`, and kickoff runtime remain untouched and usable.
- Products and engineering domains are independent dimensions. An application, package, directory, team, or deployment unit is never accepted as a product without explicit product evidence and owner confirmation.
- Discovery is read-only. No local or external mutation may occur before approval of the exact dry-run fingerprint.
- Selected providers fail strictly. No unavailable provider falls back to Git or another provider.
- Every external mutation requires stable-key idempotency and read-back evidence.
- Disposable round-trip records are removed and their absence is verified before workspace readiness.
- Unsupported administrative operations produce one-time manual handoffs with exact diagnostics; missing runtime capabilities always block readiness.
- A rerun produces a diff and may repair only non-semantic omissions. It never silently renames, moves, merges, or deletes user-owned external structures.
- `.agents/elephant/workspace.yaml` and `.agents/elephant/profiles/*.yaml` are the only local setup outputs. They contain no story records, Product Contracts, Technical Contracts, plans, or checkpoints.
- Local writes resolve paths against the repository root, reject symlink escape, and use atomic replacement.
- Phase 2 performs no real Linear or Notion API calls. Host-specific adapters and sandbox certification belong to Phases 3 and 4.
- Tests assert executable data and behavior, not fixed Markdown phrases.

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/workspace_setup/models.py` | Immutable evidence, topology, operation, manifest, approval, and result values plus canonical fingerprints |
| `scripts/workspace_setup/discovery.py` | Read-only repository inventory and normalization of host-supplied external discovery snapshots |
| `scripts/workspace_setup/proposal.py` | Independent product/domain candidate construction, conflicts, owner questions, and confirmed topology |
| `scripts/workspace_setup/dry_run.py` | Provider preflight composition, existing-structure diff, operation classification, and deterministic manifest creation |
| `scripts/workspace_setup/apply.py` | Adapter protocol, approval gate, idempotent mutation/read-back/round-trip execution, and readiness result |
| `scripts/workspace_setup/files.py` | Canonical YAML rendering, path confinement, semantic overwrite guard, and atomic local writes |
| `scripts/workspace_setup/__init__.py` | Deliberate public API for later provider and skill phases |
| `plugins/elephant/references/workspace/setup-workspace.md` | Canonical provider-neutral setup protocol and authority boundary |
| `plugins/elephant/skills/setup-workspace/SKILL.md` | Claude/Codex orchestration instructions with one owner approval checkpoint |
| `tests/fixtures/setup-workspace/` | Single-product, multi-product, partial-existing, and conflict fixture repositories/snapshots |
| `tests/test_setup_models.py` | Canonicalization, fingerprint, and approval authority tests |
| `tests/test_setup_discovery.py` | Repository/external discovery and independent-dimension tests |
| `tests/test_setup_dry_run.py` | Diff, diagnostic, strict-provider, conflict, and rerun tests |
| `tests/test_setup_apply.py` | No-write-before-approval, idempotency, read-back, round-trip, cleanup, and manual-handoff tests |
| `tests/test_setup_files.py` | Rendering, output boundary, symlink escape, semantic overwrite, and atomic-write tests |
| `tests/test_compatibility.py` | Package/skill/reference presence and setup public-contract integrity |

---

### Task 1: Immutable Setup Manifest and Approval Authority

**Files:**
- Create: `scripts/workspace_setup/models.py`
- Create: `scripts/workspace_setup/__init__.py`
- Create: `tests/test_setup_models.py`

**Interfaces:**
- Consumes: `ProviderKind`, `ProviderPreflight`, and `DiagnosticCode` from `scripts.workspace_core`.
- Produces: `Confidence`, `Evidence`, `Candidate`, `TopologyConflict`, `OwnerQuestion`, `ConfirmedProduct`, `ConfirmedDomain`, `ConfirmedTopology`, `OperationKind`, `SetupDiagnostic`, `SetupOperation`, `SetupManifest`, `ApprovedManifest`, `ApplyEvidence`, `ApplyResult`, `manifest_fingerprint()`, and `approve_manifest()`.

- [ ] **Step 1: Write failing canonical-fingerprint tests**

Create `tests/test_setup_models.py` with table-driven assertions that mapping insertion order cannot change a fingerprint, while any semantic product, domain, provider, operation, question, conflict, diagnostic, registry, or profile change does change it:

```python
from dataclasses import replace
import unittest

from scripts.workspace_setup import (
    Confidence,
    Evidence,
    OwnerQuestion,
    SetupManifest,
    manifest_fingerprint,
)


def manifest() -> SetupManifest:
    return SetupManifest(
        schema="elephant.setup-manifest/v1",
        repository_id="repo-sample",
        provider_selection=(
            ("delivery_workspace", "git"),
            ("product_contract_store", "git"),
            ("product_knowledge_store", "git"),
            ("story_store", "git"),
        ),
        products=(),
        domains=(),
        operations=(),
        diagnostics=(),
        conflicts=(),
        questions=(
            OwnerQuestion(
                key="product.sample.confirm",
                prompt="Confirm sample as a product identity",
                evidence=(Evidence("docs", "docs/sample", "sample"),),
                confidence=Confidence.MEDIUM,
            ),
        ),
        registry=(("schema", "elephant.workspace/v3"),),
        profiles=(),
    )


class SetupManifestTests(unittest.TestCase):
    def test_fingerprint_is_stable_for_equivalent_mapping_order(self):
        first = manifest()
        second = replace(
            first,
            provider_selection=tuple(reversed(first.provider_selection)),
        )
        self.assertEqual(manifest_fingerprint(first), manifest_fingerprint(second))

    def test_semantic_change_changes_fingerprint(self):
        first = manifest()
        second = replace(first, repository_id="repo-other")
        self.assertNotEqual(manifest_fingerprint(first), manifest_fingerprint(second))
```

- [ ] **Step 2: Run the focused test and observe RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_setup_models -v
```

Expected: import failure because `scripts.workspace_setup` does not exist.

- [ ] **Step 3: Implement immutable values and canonical JSON conversion**

In `models.py`, use frozen dataclasses and tuples at every stored boundary. Implement one recursive canonicalizer that converts enums to `.value`, dataclasses to field mappings, tuple key/value pairs to sorted mappings, and remaining tuples to arrays. Reject unsupported values instead of serializing `repr()`:

```python
SETUP_MANIFEST_SCHEMA = "elephant.setup-manifest/v1"


class Confidence(str, Enum):
    CONFIRMED = "confirmed"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OperationKind(str, Enum):
    REUSE = "reuse"
    CREATE = "create"
    MANUAL = "manual"
    VERIFY = "verify"
    ROUND_TRIP = "round_trip"
    WRITE_LOCAL = "write_local"


@dataclass(frozen=True)
class Evidence:
    source: str
    ref: str
    value: str


@dataclass(frozen=True)
class Candidate:
    key: str
    display_name: str
    evidence: tuple[Evidence, ...]
    confidence: Confidence


@dataclass(frozen=True)
class TopologyConflict:
    key: str
    subject: str
    alternatives: tuple[str, ...]
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class OwnerQuestion:
    key: str
    prompt: str
    evidence: tuple[Evidence, ...]
    confidence: Confidence
```

Define confirmed products/domains with stable keys and explicit cross-links. `SetupDiagnostic` has `logical_provider: ProviderKind`, `physical_provider: str`, `capability: str`, `code: DiagnosticCode`, and `blocking: bool`. `SetupOperation` has `operation_id`, `provider`, `capability`, `target_key`, `desired_fingerprint`, `payload`, `kind`, and `runtime_required`. The manifest contains every field shown by the test. Add `ApplyEvidence` (`operation_id`, `target_key`, `external_id`, `observed_fingerprint`, `disposition`) and `ApplyResult` (`ready`, ordered evidence, ordered manual handoffs, ordered local writes) now so later tasks consume fixed names instead of inventing neighboring interfaces.

- [ ] **Step 4: Add the exact approval gate tests**

Extend the test file:

```python
class SetupApprovalTests(unittest.TestCase):
    def test_only_exact_manifest_fingerprint_can_be_approved(self):
        value = manifest()
        approved = approve_manifest(value, manifest_fingerprint(value))
        self.assertEqual(approved.fingerprint, manifest_fingerprint(value))
        self.assertIs(approved.manifest, value)

    def test_stale_or_blank_fingerprint_is_rejected(self):
        value = manifest()
        for supplied in ("", "0" * 64):
            with self.subTest(supplied=supplied):
                with self.assertRaisesRegex(ValueError, "approval fingerprint"):
                    approve_manifest(value, supplied)
```

Implement `manifest_fingerprint()` as SHA-256 of canonical UTF-8 JSON with sorted keys and compact separators. `approve_manifest()` returns `ApprovedManifest` only on an exact constant-time digest comparison.

- [ ] **Step 5: Lock down exact serialized vocabulary and exports**

Test every enum value, `SETUP_MANIFEST_SCHEMA`, and `scripts.workspace_setup.__all__`. Export only the values named under Interfaces. This is executable contract coverage; do not inspect source text.

- [ ] **Step 6: Run focused and compatibility tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_setup_models tests.test_compatibility -v
```

Expected: all tests pass and the existing v2/v3 compatibility suite remains green.

- [ ] **Step 7: Commit**

```bash
git add scripts/workspace_setup tests/test_setup_models.py
git commit -m "feat: define setup manifest authority"
```

---

### Task 2: Read-Only Repository Discovery and Independent Topology Proposal

**Files:**
- Create: `scripts/workspace_setup/discovery.py`
- Create: `scripts/workspace_setup/proposal.py`
- Create: `tests/test_setup_discovery.py`
- Create: `tests/fixtures/setup-workspace/single-product/package.json`
- Create: `tests/fixtures/setup-workspace/single-product/apps/web/package.json`
- Create: `tests/fixtures/setup-workspace/multi-product/package.json`
- Create: `tests/fixtures/setup-workspace/multi-product/apps/alpha/package.json`
- Create: `tests/fixtures/setup-workspace/multi-product/apps/beta/package.json`
- Create: `tests/fixtures/setup-workspace/conflict/package.json`

**Interfaces:**
- Consumes: Task 1 evidence/candidate/topology values.
- Produces: `WorkspaceUnit`, `DependencyEdge`, `RepositoryDiscovery`, `ExternalObject`, `ExternalDiscovery`, `TopologyProposal`, `discover_repository(root)`, `normalize_external_discovery(records)`, `propose_topology(repository, external)`, and `confirm_topology(proposal, products, domains)`.

- [ ] **Step 1: Build fixture repositories and write failing discovery tests**

Each fixture `package.json` contains real JSON. The multi-product fixture declares two workspaces and dependencies; it deliberately contains no authoritative product mapping. Test scanner behavior without relying on the Elephant repository itself:

```python
from pathlib import Path
import unittest

from scripts.workspace_setup import discover_repository


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
```

- [ ] **Step 2: Run the discovery tests and observe RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_setup_discovery.RepositoryDiscoveryTests -v
```

Expected: import failure for `discover_repository`.

- [ ] **Step 3: Implement bounded repository discovery**

`discover_repository(root)` resolves `root`, reads the root `package.json`, expands only declared workspace globs plus direct `apps/*` and `packages/*` directories, and reads each discovered `package.json`. It records package name, relative POSIX scope, manifest reference, dependency evidence, root/nested `AGENTS.md` and `CLAUDE.md`, product-document paths below `docs/`, and deployment evidence filenames. It excludes `.git`, `.worktrees`, `node_modules`, build outputs, and symlinked directories. Invalid JSON becomes an explicit discovery problem; it is never silently ignored.

Repository identity is a proposal: prefer an explicit `repository.id` supplied by the caller, otherwise derive a slug from the resolved root directory and attach low-confidence provenance. It is not written until owner confirmation.

- [ ] **Step 4: Write failing independent-dimension proposal tests**

Add host-supplied external objects and assertions that code units become engineering-domain candidates but never products:

```python
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
```

- [ ] **Step 5: Implement normalization, conflicts, and explicit confirmation**

`normalize_external_discovery()` validates mappings and stable IDs and sorts objects by `(provider, kind, key, external_id)`. `propose_topology()` merges equivalent evidence, preserves every provenance item, and emits conflicts when one normalized key has differing display identities or multiple authoritative external IDs. It emits owner questions for every product identity and every ambiguous domain grouping.

`confirm_topology()` accepts explicit `ConfirmedProduct` and `ConfirmedDomain` tuples. It rejects unknown candidate keys, missing reciprocal links, duplicate keys, unresolved referenced conflicts, and an empty repository ID. It does not infer confirmations from confidence. The caller must deliberately supply the final independent mapping.

- [ ] **Step 6: Cover conflict and multi-product fixtures**

Add tests for duplicate external objects, conflicting names/IDs, reciprocal product/domain links, deterministic ordering, sparse repositories, malformed manifests, and a confirmed two-product topology whose product keys do not equal app directory names.

- [ ] **Step 7: Run focused and full current tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_setup_discovery -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

- [ ] **Step 8: Commit**

```bash
git add scripts/workspace_setup tests/test_setup_discovery.py tests/fixtures/setup-workspace
git commit -m "feat: discover workspace topology"
```

---

### Task 3: Deterministic Dry Run, Provider Diagnostics, and Safe Diff

**Files:**
- Create: `scripts/workspace_setup/dry_run.py`
- Create: `tests/test_setup_dry_run.py`
- Create: `tests/fixtures/setup-workspace/existing-workspace.json`

**Interfaces:**
- Consumes: confirmed topology, Phase 1 provider selections/preflight, external discovery, and Task 1 manifest values.
- Produces: `CapabilityLayers`, `DesiredStructure`, `build_setup_manifest(topology, provider_selection, desired_structures, external, capability_layers, registry, profiles)`.

- [ ] **Step 1: Write failing strict-provider preflight tests**

Construct capability layers for every selected logical provider and assert that the manifest contains the exact Phase 1 diagnostic code without adding fallback operations:

```python
class DryRunDiagnosticTests(unittest.TestCase):
    def test_selected_provider_failure_never_adds_git_fallback(self):
        value = build_manifest_with(
            story_store="linear",
            story_layers=CapabilityLayers(
                platform_supported=STORY_RUNTIME_CAPABILITIES,
                exposed=frozenset(),
                permitted=STORY_RUNTIME_CAPABILITIES,
                configured=STORY_RUNTIME_CAPABILITIES,
            ),
        )
        self.assertTrue(value.diagnostics)
        self.assertEqual(
            {diagnostic.code for diagnostic in value.diagnostics},
            {DiagnosticCode.CONNECTOR_CAPABILITY_MISSING},
        )
        self.assertNotIn("git", tuple(operation.provider for operation in value.operations))
```

In this test file, `build_manifest_with()` starts from one complete confirmed single-product topology, all four provider selections, all-complete capability layers, empty external discovery, schema-valid registry/profile payloads, and overrides only named keyword arguments. It must call the public `build_setup_manifest()` rather than reimplementing dry-run logic.

- [ ] **Step 2: Run and observe RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_setup_dry_run.DryRunDiagnosticTests -v
```

Expected: import failure for `CapabilityLayers` and `build_setup_manifest`.

- [ ] **Step 3: Implement logical-provider preflight composition**

For `story_store`, `product_knowledge_store`, `product_contract_store`, and `delivery_workspace`, map the selected physical provider to the exact Phase 1 `ProviderKind`, call `preflight_provider()`, and copy every diagnostic into the manifest with logical-provider context. Validate that all four layer collections exist; malformed evidence raises deliberate `ValueError` before a manifest is created.

Git is not a fallback. It is preflighted only when explicitly selected. External provider binding fields remain opaque read-back values and are never guessed by the dry-run builder.

- [ ] **Step 4: Write failing operation-diff tests**

Use `DesiredStructure(provider, capability, logical_key, desired_fingerprint, administrative, runtime_required)` and external objects with matching/differing fingerprints:

```python
class DryRunDiffTests(unittest.TestCase):
    def test_matching_structure_is_reused_and_missing_structure_is_created(self):
        value = build_manifest_with(
            desired_structures=(
                DesiredStructure("linear", "ensure_team", "team.delivery", "same", True, False),
                DesiredStructure("linear", "ensure_label", "label.product.sample", "new", True, False),
            ),
            external_objects=(external_object("team.delivery", "same"),),
        )
        self.assertEqual(
            tuple(operation.kind for operation in value.operations[:2]),
            (OperationKind.REUSE, OperationKind.CREATE),
        )

    def test_semantic_difference_is_a_conflict_not_an_update(self):
        value = build_manifest_with(
            desired_structures=(
                DesiredStructure("linear", "ensure_team", "team.delivery", "desired", True, False),
            ),
            external_objects=(external_object("team.delivery", "existing"),),
        )
        self.assertTrue(value.conflicts)
        self.assertNotIn(OperationKind.CREATE, tuple(op.kind for op in value.operations))
```

The local `external_object(stable_key, fingerprint)` helper returns a validated `ExternalObject` for provider `linear`, kind `setup_structure`, and a deterministic external ID `id-<stable_key>`. It is fixture construction only; all classification remains in `build_setup_manifest()`.

- [ ] **Step 5: Implement safe diff classification**

For each desired structure:

- zero stable-key matches + administrative capability available → `CREATE`;
- exactly one equal fingerprint → `REUSE` followed by `VERIFY`;
- several matches or one differing fingerprint → semantic `TopologyConflict`, never update/delete;
- platform/connector/permission administrative gap → `MANUAL` with the exact diagnostic and required read-back evidence;
- missing configuration for a runtime-required structure → blocking diagnostic;
- every selected external physical provider → one disposable `ROUND_TRIP` operation;
- local registry/profile payloads → `WRITE_LOCAL` operations placed last.

Sort operations by phase (`reuse`, `create`, `manual`, `verify`, `round_trip`, `write_local`), then provider/capability/stable key. A repeated call with identical inputs produces byte-identical canonical payload and fingerprint.

- [ ] **Step 6: Cover complete setup fixtures**

Tests must cover new single-product, confirmed multi-product, partial existing workspace, conflicting evidence, unsupported platform, connector gap, permission gap, configuration omission, Notion view manual handoff, missing runtime capability, duplicate stable keys, and rerun with no creates/deletes. Assert no operation kind named delete exists in the public vocabulary.

- [ ] **Step 7: Run focused and full tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_setup_dry_run -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

- [ ] **Step 8: Commit**

```bash
git add scripts/workspace_setup tests/test_setup_dry_run.py tests/fixtures/setup-workspace/existing-workspace.json
git commit -m "feat: build setup dry run"
```

---

### Task 4: Approved Idempotent Apply, Read-Back, and Disposable Round Trip

**Files:**
- Create: `scripts/workspace_setup/apply.py`
- Create: `tests/test_setup_apply.py`

**Interfaces:**
- Consumes: `ApprovedManifest`, ordered `SetupOperation` values, and the local-writer callable introduced as a narrow protocol in this task.
- Produces: `ExternalRecord`, `MutationReceipt`, `DeletionReceipt`, `SetupAdapter` protocol, `SetupApplyError`, and `apply_setup(approved, adapters, write_local)`.

- [ ] **Step 1: Write the no-write-before-approval tests**

Create a recording fake adapter and local writer inside the test file. Passing a raw `SetupManifest`, a mismatched approved fingerprint, a manifest with conflicts/questions, or a manifest with blocking runtime diagnostics must leave both recorders empty:

```python
class SetupApplyAuthorityTests(unittest.TestCase):
    def test_raw_manifest_cannot_mutate_any_authority(self):
        adapter = RecordingAdapter("linear")
        writes: list[tuple[str, str]] = []
        with self.assertRaisesRegex(TypeError, "ApprovedManifest"):
            apply_setup(manifest(), {"linear": adapter}, writes.append)
        self.assertEqual(adapter.calls, [])
        self.assertEqual(writes, [])

    def test_blocking_manifest_stops_before_first_mutation(self):
        adapter = RecordingAdapter("linear")
        approved = approve_manifest(blocked_manifest(), manifest_fingerprint(blocked_manifest()))
        with self.assertRaisesRegex(SetupApplyError, "blocking"):
            apply_setup(approved, {"linear": adapter}, lambda path, body: None)
        self.assertEqual(adapter.calls, [])
```

- [ ] **Step 2: Run and observe RED**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_setup_apply.SetupApplyAuthorityTests -v
```

Expected: import failure for `apply_setup`.

- [ ] **Step 3: Define the adapter protocol and pre-mutation gate**

The adapter is synchronous and runtime-neutral:

```python
class SetupAdapter(Protocol):
    provider: str

    def find(self, stable_key: str) -> tuple[ExternalRecord, ...]:
        raise NotImplementedError

    def create(self, operation: SetupOperation) -> MutationReceipt:
        raise NotImplementedError

    def read(self, external_id: str) -> ExternalRecord | None:
        raise NotImplementedError

    def delete_disposable(self, external_id: str) -> DeletionReceipt:
        raise NotImplementedError
```

`apply_setup()` first requires an `ApprovedManifest`, recomputes its fingerprint, rejects stale approval, conflicts, unresolved owner questions, and blocking runtime diagnostics, and verifies every required provider adapter exists. Nothing calls an adapter or local writer until this gate completes.

- [ ] **Step 4: Write failing idempotency and read-back tests**

Cover these exact behaviors:

```python
class SetupApplyMutationTests(unittest.TestCase):
    def test_create_is_stable_key_idempotent_and_read_back_verified(self):
        adapter = RecordingAdapter("linear")
        approved = approved_create_manifest()
        first = apply_setup(approved, {"linear": adapter}, recording_writer())
        second = apply_setup(approved, {"linear": adapter}, recording_writer())
        self.assertTrue(first.ready)
        self.assertTrue(second.ready)
        self.assertEqual(adapter.created_keys.count("label.product.sample"), 1)
        self.assertGreaterEqual(adapter.read_count, 2)

    def test_mismatched_read_back_stops_before_local_write(self):
        adapter = RecordingAdapter("linear", corrupt_read_back=True)
        writes = recording_writer()
        with self.assertRaisesRegex(SetupApplyError, "read-back"):
            apply_setup(approved_create_manifest(), {"linear": adapter}, writes)
        self.assertEqual(writes.calls, [])
```

`RecordingAdapter` stores records by stable key and external ID, deduplicates `create()` by stable key, records ordered method names, and can deliberately corrupt read-back or retain a deleted record. `recording_writer()` returns a callable object whose `.calls` is an ordered list of `(path, body)`. `approved_create_manifest()` and `approved_round_trip_manifest()` construct complete blocker-free manifests and call the real `approve_manifest()` with the real fingerprint.

- [ ] **Step 5: Implement operation execution without destructive repair**

For `REUSE` and `VERIFY`, find exactly one stable-key record and verify its fingerprint. For `CREATE`, find first so interruption/rerun reuses a previously created object; create only when absent, then read by returned external ID and compare stable key plus fingerprint. Several records or semantic mismatch stops. Normal setup never calls delete.

`MANUAL` operations produce structured handoff evidence and return `ready=False` until a subsequent manifest sees the structure and emits `REUSE`/`VERIFY`. Local writes do not occur in that result.

- [ ] **Step 6: Write failing disposable round-trip and cleanup tests**

```python
class SetupRoundTripTests(unittest.TestCase):
    def test_round_trip_creates_reads_deletes_and_verifies_absence(self):
        adapter = RecordingAdapter("notion")
        result = apply_setup(approved_round_trip_manifest(), {"notion": adapter}, recording_writer())
        self.assertTrue(result.ready)
        self.assertEqual(
            adapter.call_kinds,
            ("find", "create", "read", "delete_disposable", "read"),
        )

    def test_cleanup_failure_blocks_readiness_and_local_write(self):
        adapter = RecordingAdapter("notion", retain_deleted=True)
        writes = recording_writer()
        with self.assertRaisesRegex(SetupApplyError, "disposable cleanup"):
            apply_setup(approved_round_trip_manifest(), {"notion": adapter}, writes)
        self.assertEqual(writes.calls, [])
```

Round-trip target keys include the manifest fingerprint so concurrent/repeated setup runs do not collide. Deletion authority exists only on an operation whose kind is `ROUND_TRIP`, and only for the external ID created or reused under that disposable key. Verify absence after deletion.

- [ ] **Step 7: Apply local writes last and return evidence**

Only after all external operations and round trips pass, invoke `write_local(path, body)` for the exact `WRITE_LOCAL` operations. `ApplyResult.ready` is true only when every operation has verified evidence, no manual handoff is pending, and local writes succeed. Return ordered `ApplyEvidence` carrying operation ID, stable/external key, observed fingerprint, and disposition.

- [ ] **Step 8: Run focused and full tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_setup_apply -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

- [ ] **Step 9: Commit**

```bash
git add scripts/workspace_setup tests/test_setup_apply.py
git commit -m "feat: apply approved workspace setup"
```

---

### Task 5: Canonical Local Configuration and Constrained Atomic Writes

**Files:**
- Create: `scripts/workspace_setup/files.py`
- Create: `tests/test_setup_files.py`

**Interfaces:**
- Consumes: confirmed topology, verified provider binding fragments, profile settings, Phase 1 `validate_workspace()`/`validate_profile()`, and Task 4 local-writer boundary.
- Produces: `WORKSPACE_PATH`, `render_yaml(document)`, `build_local_documents(topology, providers, bindings, product_profile_settings, engineering_profile_settings)`, `LocalWrite`, `plan_local_writes(root, documents)`, and `apply_local_write(root, write)`.

- [ ] **Step 1: Write failing document-generation tests**

Generate one external-provider and one all-Git setup. Parse the constrained renderer with a small test-side scalar/list/mapping reader or compare to exact normalized dictionaries through a companion `load_rendered_yaml()` owned by `files.py`:

```python
class LocalDocumentTests(unittest.TestCase):
    def test_external_documents_pass_phase_one_validators(self):
        documents = build_local_documents(
            topology=confirmed_topology(),
            providers=external_provider_selection(),
            bindings=verified_bindings(),
            product_profile_settings=product_settings(),
            engineering_profile_settings=engineering_settings(),
        )
        workspace = load_rendered_yaml(documents[".agents/elephant/workspace.yaml"])
        self.assertEqual(validate_workspace(workspace), ())
        for path, body in documents.items():
            if path.endswith("workspace.yaml"):
                continue
            self.assertEqual(validate_profile(load_rendered_yaml(body)), ())

    def test_generated_registry_contains_no_story_level_content(self):
        workspace = load_rendered_yaml(
            build_documents()[".agents/elephant/workspace.yaml"]
        )
        self.assertTrue(FORBIDDEN_STORY_KEYS.isdisjoint(workspace))
```

The test helpers build a complete confirmed topology with product `sample`, domain `web`, reciprocal links, verified Linear/Notion IDs, and fully populated seven-section profile settings. `build_documents()` is a one-line wrapper around the public `build_local_documents()` using those values; it contains no alternate rendering or validation path.

- [ ] **Step 2: Run and observe RED**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_setup_files.LocalDocumentTests -v
```

Expected: import failure for the local-file API.

- [ ] **Step 3: Implement constrained canonical YAML and schema-valid documents**

The renderer supports only mappings with string keys, lists/tuples, strings, booleans, integers, and null. It sorts mapping keys, quotes strings through JSON escaping, emits two-space indentation, and ends with one newline. `load_rendered_yaml()` parses exactly this constrained form; it must not become a general YAML parser.

`build_local_documents()` creates:

- `.agents/elephant/workspace.yaml` with exact v3 schema, stable repository ID, selected providers, only verified external bindings, product profile/story/knowledge refs, reciprocal product/domain mapping, and engineering profile path;
- one `.agents/elephant/profiles/<product-key>.yaml` per product with `kind: product` and the supplied seven required settings mappings;
- `.agents/elephant/profiles/engineering.yaml` with `product: null` and `behavior_preservation_required: true`.

Reject product keys that cannot safely form a basename, unverified binding receipts, missing profile settings, and any document that fails the Phase 1 validators before rendering.

- [ ] **Step 4: Write failing confinement and overwrite tests**

Use `tempfile.TemporaryDirectory()` and create both in-root and symlink-escape cases:

```python
class LocalWriteSafetyTests(unittest.TestCase):
    def test_only_workspace_and_direct_profile_paths_are_allowed(self):
        for path in ("README.md", ".agents/elephant/profiles/nested/a.yaml", "../outside.yaml"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "setup output path"):
                    plan_local_writes(self.root, {path: "body"})

    def test_symlinked_parent_cannot_escape_repository(self):
        (self.root / ".agents").symlink_to(self.outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "repository containment"):
            plan_local_writes(
                self.root,
                {".agents/elephant/workspace.yaml": valid_workspace_body()},
            )

    def test_changed_existing_semantic_content_requires_expected_fingerprint(self):
        write_existing_workspace(self.root)
        with self.assertRaisesRegex(ValueError, "semantic overwrite"):
            plan_local_writes(self.root, build_changed_documents())
```

- [ ] **Step 5: Implement planned and atomic local writes**

`plan_local_writes()` allows exactly `WORKSPACE_PATH` and direct `.yaml` children of the profile directory. Resolve the root and every existing parent; reject symlink components or resolved targets outside root. For each target, classify `create`, `unchanged`, or `replace`. `replace` requires the manifest operation's expected prior SHA-256 fingerprint; absent/stale fingerprints stop instead of clobbering semantic content.

`apply_local_write()` rechecks the prior fingerprint immediately before mutation, creates missing directories inside the confined root, writes a sibling temporary file, flushes and `fsync()`s it, then uses `os.replace()`. It never deletes unrelated files. A rerun of unchanged content performs no replacement.

- [ ] **Step 6: Integrate the local writer with Task 4**

Add an end-to-end fake-adapter test: approved setup verifies external mutations and round trips, writes all local documents last, then Phase 1 validators load the resulting files successfully. Inject external read-back failure and assert no `.agents/elephant/` path exists.

- [ ] **Step 7: Run focused and full tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_setup_files tests.test_setup_apply -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

- [ ] **Step 8: Commit**

```bash
git add scripts/workspace_setup tests/test_setup_files.py tests/test_setup_apply.py
git commit -m "feat: write verified workspace config"
```

---

### Task 6: `setup-workspace` Skill, Canonical Protocol, Fixtures, and Packaging

**Files:**
- Create: `plugins/elephant/references/workspace/setup-workspace.md`
- Create: `plugins/elephant/skills/setup-workspace/SKILL.md`
- Modify: `scripts/validate-compatibility.py`
- Modify: `tests/test_compatibility.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: the complete Task 1–5 public API and all four Phase 1 workspace references.
- Produces: a packaged `elephant:setup-workspace` skill and a compatibility boundary that proves its executable contract and required assets remain available to both hosts.

- [ ] **Step 1: Write failing compatibility/package tests**

Extend `WorkspaceCorePackagingTests` or add `SetupWorkspacePackagingTests`:

```python
class SetupWorkspacePackagingTests(unittest.TestCase):
    def test_setup_workspace_assets_are_packaged(self):
        required = (
            ROOT / "plugins/elephant/skills/setup-workspace/SKILL.md",
            ROOT / "plugins/elephant/references/workspace/setup-workspace.md",
        )
        self.assertEqual([path for path in required if not path.is_file()], [])

    def test_setup_public_exports_are_exact(self):
        expected = frozenset(EXACT_SETUP_PUBLIC_EXPORTS)
        self.assertEqual(frozenset(workspace_setup.__all__), expected)

    def test_missing_setup_asset_is_reported(self):
        copied = copy_plugin_fixture()
        (copied / "skills/setup-workspace/SKILL.md").unlink()
        self.assertIn("skills/setup-workspace/SKILL.md", validate_copy(copied))
```

Define `EXACT_SETUP_PUBLIC_EXPORTS` in the test as this literal tuple, and make each task update `scripts/workspace_setup/__init__.py` toward it:

```python
EXACT_SETUP_PUBLIC_EXPORTS = (
    "ApplyEvidence", "ApplyResult", "ApprovedManifest", "Candidate",
    "CapabilityLayers", "Confidence", "ConfirmedDomain", "ConfirmedProduct",
    "ConfirmedTopology", "DeletionReceipt", "DependencyEdge", "DesiredStructure",
    "Evidence", "ExternalDiscovery", "ExternalObject", "ExternalRecord",
    "LocalWrite", "MutationReceipt", "OperationKind", "OwnerQuestion",
    "RepositoryDiscovery", "SETUP_MANIFEST_SCHEMA", "SetupAdapter",
    "SetupApplyError", "SetupDiagnostic", "SetupManifest", "SetupOperation",
    "TopologyConflict", "TopologyProposal", "WORKSPACE_PATH", "WorkspaceUnit",
    "apply_local_write", "apply_setup", "approve_manifest", "build_local_documents",
    "build_setup_manifest", "confirm_topology", "discover_repository",
    "load_rendered_yaml", "manifest_fingerprint", "normalize_external_discovery",
    "plan_local_writes", "propose_topology", "render_yaml",
)
```

Also mutate one setup enum value and the approval fingerprint computation in copied script fixtures; compatibility validation must report executable contract drift without searching for prose phrases.

- [ ] **Step 2: Run and observe RED**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_compatibility.SetupWorkspacePackagingTests -v
```

Expected: missing asset/export validation failures.

- [ ] **Step 3: Author the canonical setup protocol**

`setup-workspace.md` defines these exact phases and authorities:

1. local and external discovery are read-only;
2. products and engineering domains are proposed independently with provenance/confidence;
3. conflicts and owner questions remain explicit in one owner decision session; setup regenerates the manifest from those answers before that same session approves writes;
4. a complete no-write manifest includes reuse/create/manual/verify/round-trip/local-write operations and exact diagnostics;
5. the sole owner checkpoint approves the regenerated manifest's displayed fingerprint;
6. apply is stable-key idempotent and every mutation is read back;
7. disposable records are removed and absence verified;
8. local files are written last and revalidated;
9. a rerun shows a diff and performs no semantic rename/move/merge/delete;
10. runtime readiness requires all selected logical providers to pass.

Document the Phase 2 boundary: fake adapters certify the orchestration protocol; real Linear and Notion adapter certification remains Phase 3/4, so README must continue to say v3 is not yet the active shipping runtime.

- [ ] **Step 4: Author the skill with one owner checkpoint**

The `SKILL.md` frontmatter is:

```yaml
---
name: setup-workspace
description: Use when a repository needs Elephant v3 workspace discovery, a product/domain topology proposal, provider diagnostics, or an approved idempotent setup dry run. Triggers on "/setup-workspace", "set up Elephant workspace", "analyze products and engineering domains", "provision Linear and Notion workspace structure".
---
```

Its flow is `discover → propose → owner decision session (resolve semantic questions, regenerate dry run, approve fingerprint) → apply → read back → round trip → write local config → revalidate`. The decision session is one checkpoint, even when answers require the manifest to be regenerated before approval. The skill instructs the host to inventory connector operations rather than assuming MCP presence equals capability, emit one of the four exact diagnostics, never fall back, never write before approval, and stop at Phase 3/4 adapter boundaries when a real provider has not yet been certified.

The approval display includes products, domains, provider selections, reused/created/manual structures, conflicts, exact diagnostics, local file diff, disposable cleanup plan, and manifest fingerprint. This is the only human checkpoint. After approval, non-semantic verified execution proceeds without additional routine review gates.

- [ ] **Step 5: Wire compatibility validation and README navigation**

Add the skill/reference to required plugin assets and import the setup package values in the validator. The validator independently checks the literal public-export set above, serialized enums, manifest schema, and approval fingerprint behavior. It does not lock Markdown wording.

README links to the setup skill and reference, says Phase 2 orchestration is provider-neutral and fixture-certified, and retains the warning that v3 shipping remains inactive until concrete providers, v3 delivery, Maio migration, and coordinated cutover pass.

- [ ] **Step 6: Run every prescribed verification command**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate-compatibility.py
PYTHONDONTWRITEBYTECODE=1 uv run --with pyyaml python \
  /Users/aki/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/elephant
git diff --check
```

Expected: unit tests, compatibility validation, plugin validation, and diff check all pass.

- [ ] **Step 7: Commit**

```bash
git add README.md plugins/elephant/skills/setup-workspace \
  plugins/elephant/references/workspace/setup-workspace.md \
  scripts/validate-compatibility.py tests/test_compatibility.py
git commit -m "feat: package setup workspace workflow"
```

---

## Final Phase Verification

After all six task reviews are clean:

1. Run the complete unit, compatibility, plugin, and diff checks from Task 6 again on the branch head.
2. Generate a review package from the Phase 2 base SHA to branch head.
3. Request a fresh whole-branch review against this plan and the approved design.
4. Fix every Critical or Important finding and perform a scoped re-review.
5. Confirm the active v2 skill/runtime files are unchanged.
6. Confirm no real Linear/Notion mutation code, fallback, converter, dual writer, story registry, or legacy removal entered the range.
7. Integrate only after the merged result passes the same checks.

## Self-Review Checklist

- Spec coverage: discovery, independent topology, provenance/confidence/conflicts/questions, complete dry run, one approval authority, exact diagnostics, idempotent reuse/create, manual handoff, read-back, disposable round trip and cleanup, local config last, rerun diff, and readiness are each owned by a task.
- Deferred correctly: real Linear/Notion adapters, provider sandbox cleanup, Product Contract semantics, v3 shipping, failpoint resume, migration, Maio topology, and legacy cutover are not implemented here.
- No placeholders: every task names exact files, interfaces, RED/GREEN commands, behaviors, and commit scope.
- Type consistency: `SetupManifest → ApprovedManifest → apply_setup()` is the single authority chain; `ConfirmedTopology` is the only semantic topology input to dry run; `WRITE_LOCAL` remains last.
- Test quality: contract behavior is asserted through Python values and controlled fixtures, not Markdown phrases or source-string snapshots.

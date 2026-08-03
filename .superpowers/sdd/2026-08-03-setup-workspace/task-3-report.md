# Task 3: Deterministic Dry Run, Provider Diagnostics, and Safe Diff

## Result

Implemented the provider-neutral dry-run builder. It composes all four Phase 1
preflights, preserves selected logical and physical provider context in every
diagnostic, safely classifies existing structures, and produces a deterministic
immutable `SetupManifest` without mutating local or external state.

Implementation commit: `e0885c885fb9100790914ea9d7f32251e58d912f` (signed,
`feat: build setup dry run`).

## Files

- Added `scripts/workspace_setup/dry_run.py` with `CapabilityLayers`,
  `DesiredStructure`, and `build_setup_manifest()`.
- Added `tests/test_setup_dry_run.py` and
  `tests/fixtures/setup-workspace/existing-workspace.json`.
- Updated `scripts/workspace_setup/__init__.py` to expose the Task 3 API.
- Updated `scripts/workspace_setup/models.py` and `discovery.py` so only
  `setup_structure` discovery records require a nonblank observed fingerprint;
  existing non-structure discovery retains its compatible empty default.
- Updated `tests/test_setup_models.py` for the expanded deliberate public API.

## RED / GREEN evidence

1. RED:
   `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_setup_dry_run.DryRunDiagnosticTests -v`
   failed as intended with `ImportError: cannot import name 'CapabilityLayers'`.
2. RED:
   strict provider-selection and semantic-drift-under-capability-gap tests
   failed before their validation/conflict implementations.
3. RED:
   the combined administrative/runtime-required structure test failed before
   `DesiredStructure` allowed those independent flags.
4. GREEN:
   `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_setup_dry_run -v`
   completed successfully: 18 tests.
5. GREEN:
   `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`
   completed successfully: 129 tests.
6. `git diff --check` completed successfully before the implementation commit.

## Decisions

- Provider selections are checked against the Phase 1 choice set; no selected
  provider can silently become Git or another fallback provider.
- Capability layers are frozen `frozenset` values, and missing/malformed layer
  evidence raises `ValueError` before a manifest exists.
- Structure fingerprints are required at the immutable discovery boundary only
  for `setup_structure`; matching values become `REUSE` plus `VERIFY`, while
  any mismatch or duplicate becomes a `TopologyConflict` and produces no
  structure write operation.
- Administrative preflight gaps become `MANUAL` operations carrying the exact
  diagnostic code and explicit `read_back_required` evidence. Runtime gaps
  stay blocking diagnostics.
- Operations use the required phase order, selected external providers each
  receive one disposable `ROUND_TRIP`, and local registry/profile writes are
  ordered last. The public operation vocabulary has no delete value.

## Concerns / follow-up boundaries

- This task only builds plans. Task 4 must enforce approval, execute the
  operations, perform read-back, and clean up the disposable round trips.
- External binding identifiers are intentionally not inferred by this builder;
  later certified adapters must supply opaque read-back values.
- No v2 runtime files were changed.

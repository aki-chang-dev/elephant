# Task 3 report: Provider Capability and Diagnostic Contracts

## Delivered

- Added `scripts/workspace_core/providers.py` with the four exact immutable
  runtime capability sets, provider and diagnostic enums, immutable result
  records, and provider preflight classification.
- Exported every Task 3 public interface from `scripts/workspace_core/__init__.py`.
- Added focused `unittest` coverage in `tests/test_provider_contracts.py`.
- Added the canonical provider-operation reference at
  `plugins/elephant/references/workspace/provider-contracts.md`.

## Changed files

- `scripts/workspace_core/providers.py` (new)
- `scripts/workspace_core/__init__.py`
- `tests/test_provider_contracts.py` (new)
- `plugins/elephant/references/workspace/provider-contracts.md` (new)
- `.superpowers/sdd/2026-08-03-workspace-core/task-3-report.md` (new)

## TDD evidence

### RED

After adding only `tests/test_provider_contracts.py`, ran:

```text
python3 -m unittest tests.test_provider_contracts -v
```

Result: failed as expected with `ImportError: cannot import name
'CONTRACT_RUNTIME_CAPABILITIES' from 'scripts.workspace_core'`. No provider
contract symbols existed at that point.

### GREEN

After the minimal implementation, ran:

```text
python3 -m unittest tests.test_provider_contracts -v
```

Result: `Ran 3 tests ... OK`.

The tests cover a fully ready Product Contract provider, the required per-capability
diagnostic precedence (`platform`, `connector`, `permission`), and the distinct
configuration diagnostic.

## Verification

```text
python3 -m unittest tests.test_provider_contracts -v
# Ran 3 tests ... OK

python3 -m unittest discover -s tests -v
# Ran 48 tests ... OK

git diff --check
# no output; passed
```

## Decisions

- Provider requirements are keyed by `ProviderKind`; preflight checks required
  capability names in sorted order.
- For each capability it records only the first unavailable layer, in the
  required order: platform, connector exposure, permission, configuration.
- The implementation uses only the Python standard library and introduces no
  dispatch path or fallback behavior, so phase 1 leaves the v2 runtime intact.
- Documentation treats host tools as adapters, requires stable opaque keys and
  read-after-write verification, and separates non-semantic repair from
  semantic drift that must stop.

## Commit

Implementation commit SHA: `8ccc9720abf7745afa517c62b1121c7b758efb23`
(`feat: define provider capability contracts`). It contains an SSH `gpgsig`.
Local signature trust verification is not configured because
`gpg.ssh.allowedSignersFile` is absent; the signature itself is embedded in the
commit object. This report is committed separately so the feature commit retains
the exact required commit message.

## Concerns

- None. The advertised `superpowers` skill instruction files were not present
  at their supplied paths in this checkout; the task brief's explicit TDD and
  verification instructions were followed directly.

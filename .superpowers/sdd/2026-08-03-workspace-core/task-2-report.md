# Task 2 Report: Scoped Profile Validation and Routing

## Outcome

Implemented the additive Phase 1 profile-validation and registry-routing
interfaces. Existing v2 runtime behavior and Task 1 workspace validation were
not modified.

## Changed files

- `scripts/workspace_core/config.py`
  - Added `PROFILE_SCHEMA`, `PROFILE_KINDS`, `validate_profile`, and
    `resolve_profile`.
  - Routing rejects invalid registries, unknown story kinds, and product-facing
    stories without a known product key.
- `scripts/workspace_core/__init__.py`
  - Exported `validate_profile` and `resolve_profile`.
- `tests/test_workspace_config.py`
  - Added the prescribed product and engineering profile fixtures and five
    profile/routing tests.
- `plugins/elephant/references/workspace/profile-schema.md`
  - Added the two profile fixtures, field semantics, and routing invariants.

## RED evidence

Command:

```sh
python3 -m unittest tests.test_workspace_config.ProfileAndRoutingTests -v
```

Result: failed before implementation with the expected import failure:

```text
ImportError: cannot import name 'resolve_profile' from 'scripts.workspace_core'
```

The new tests name the production changes that would make them fail: missing
profile validation, an engineering profile without mandatory behavior
preservation, incorrect product/engineering profile selection, and accepting a
product-facing story without a known product key.

## GREEN and verification evidence

```sh
python3 -m unittest tests.test_workspace_config -v
```

Result: `Ran 16 tests ... OK`.

```sh
python3 -m unittest tests.test_workspace_config tests.test_compatibility -v
```

Result: `Ran 43 tests ... OK`.

```sh
git diff --check
```

Result: exit 0 with no whitespace errors.

`python3 -m unittest discover -v` was also run; its default discovery pattern
did not match this repository's `test_*.py` test files, so it reported zero
tests. The explicit module command above covers both available Python test
modules.

## Commit

Implementation commit: `8abd27d921c4424ea0e7143b1b88bfd4fcbe9c76`
(`feat: define scoped delivery profiles`). It was created with `git commit -S`.
The commit object contains an SSH `gpgsig`; local signature verification cannot
complete because `gpg.ssh.allowedSignersFile` is not configured in this
worktree.

## Decisions

- Kept `validate_profile` deliberately structural, as specified: it validates
  the schema, profile kind, required product/engineering distinctions, and the
  seven required profile sections.
- Kept routing registry-driven: `resolve_profile` selects the engineering
  profile only for `engineering-only`; a `product-facing` story must name an
  existing product and uses only that product's registry profile path.
- Used Task 1's `_mapping`, `validate_workspace`, and `WorkspaceRouteError`
  without changing their behavior.

## Concerns

- No implementation concern remains. The local repository lacks an SSH allowed
  signers file, which prevents local `git log --show-signature` verification;
  the signed commit payload itself is present.

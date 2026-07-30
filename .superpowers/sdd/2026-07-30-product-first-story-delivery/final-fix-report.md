# Product-first story delivery final fix report

Date: 2026-07-30
Base: `08f1c66`
Branch: `fix/product-first-followup`

## Result

The concentrated follow-up is complete. The v2/legacy detector now selects artifacts before
dependency preflight, validates lifecycle-dependent content, consumes custom legacy contracts
mechanically, supports engineering-only decision return, and gates dual-v2 integration on
post-implementation conformance. The persisted Technical Contract lifecycle is consistently:

```text
draft → ready → implementing → done
          ↘ needs-product-decision → product shaping → draft
```

No remote state, main branch, installed plugin, cache, or worktree lifecycle was changed.

## RED evidence

### Focused protocol regression RED

Ten focused compatibility checks were added or strengthened before production protocol edits.
Their first run produced only expected assertion failures:

```text
FFFFFFFFFF
Ran 10 tests in 0.004s
FAILED (failures=10)
```

The failures covered branch-aware preflight, engineering-only decision return, status invariants,
legacy/v2 classification, custom legacy filename/status mechanics, canonical Product binding,
custom template validation, post-build conformance, and the exact Technical lifecycle.

### Fresh-worker behavioral RED

Two fresh, read-only workers used the released `0.3.0` files as their only workflow authority:

| Worker | Reproduced failure |
|---|---|
| `/root/final_followup_fix/red_v2_pressure` | engineering-only return had no transition; profile-driven preflight required irrelevant capabilities; invalid status content advanced; `review` was persisted and execution stayed `ready` |
| `/root/final_followup_fix/red_legacy_conformance` | legacy suffix/generic metadata became false v2; `[slug]-[ID].md` and custom statuses were ignored/overwritten; integration had no contract-conformance gate |

The durable verbatim evidence and scenario details are in
`docs/testing/product-first-story-skill-tests.md`.

### Pressure-discovered late-return RED

The first GREEN conformance pressure run found one additional mechanical dead end:
post-implementation `NEEDS_PRODUCT_DECISION` could reset to `draft`, but old execution evidence
made the next `ready` state invalid and the old plan prevented deterministic replanning. A focused
assertion reproduced it:

```text
Ran 1 test in 0.001s
FAILED (failures=1)
```

The repair retains old delivery evidence as explicitly superseded history, captures a
contract-basis marker at the revised `ready` state, binds a new or revised plan to that marker,
then transitions the current revision back to `implementing`. Lifecycle-only writes preserve the
marker; later author/fixer contract changes replace it and invalidate prior delivery evidence.

### Final contradiction-audit RED

A final fresh read-only audit found five enforceability gaps: shared downstream clauses still
keyed off profile mode instead of the selected artifact branch; custom legacy `spec_template`
resolution was underspecified; marker/current-plan evidence was not mandatory for every ready
contract or custom Technical template; two custom v2 filename rules could render one output path;
and profile initialization used a legacy-specific design detector for new dual profiles. Five
focused checks first failed together, then the collision and design-default checks failed
individually:

```text
Ran 5 tests in 0.004s
FAILED (failures=5)

Ran 1 test in 0.001s
FAILED (failures=1)

Ran 1 test in 0.002s
FAILED (failures=1)
```

After repair, the combined focused audit passed:

```text
Ran 6 tests in 0.003s
OK
```

## Implemented changes

### Detection, preflight, and validation

- Artifact/type and first-incomplete-phase selection now precede branch-specific dependency
  checks.
- Existing v2 wins under a legacy profile; an existing legacy artifact remains legacy under a
  dual profile.
- Exact v2 discriminator values, rendered v2 rules, the preserved legacy filename rule, and known
  legacy status values avoid suffix and generic-metadata false positives.
- Malformed current-story v2 still hard-stops; valid other-story v2 is ignored; genuine ambiguity
  lists every candidate without recency inference.
- Product and Technical status-dependent invariants hard-stop with the exact path and violated
  field/section.
- Custom Product/Technical templates are validated immediately before their selected authoring
  dispatch.
- Product and Technical filename rules must render distinct outputs for the selected story/slug
  before either author can mutate an artifact.

### Decision return and canonical references

- `ship-story` alone allocates deterministic decision-return slugs/paths; `shape-story` writes the
  exact caller-supplied path.
- Engineering-only ambiguity creates the first Product Contract, stops on terminal dispositions,
  and after approval atomically rebinds `product_contract`, changes `story_kind`, clears the brief,
  and resets to `draft`.
- Product-facing revisions create immutable successors.
- `product_contract` now follows the same repository-relative POSIX, exact-case, existing-file,
  exact-active-contract discipline as `supersedes`.
- An implementation-stage return invalidates old plan/execution/review/conformance evidence as
  current evidence and requires a revision-bound plan before re-entering implementation.

### Lifecycle, legacy mechanics, and conformance

- Review is an activity while the Technical Contract remains `draft`; no persisted `review`
  state remains.
- Execution persists `ready → implementing`; closeout persists `implementing → done`.
- Legacy discovery renders the configured filename rule and treats exactly four configured status
  values as authoring/ready/implementing/done. Every read and write uses those values.
- A configured legacy `spec_template` resolves only for selected legacy authoring, from an
  explicit plugin alias or repository-contained path, and never silently falls back.
- Shared Plan/Execute/Closeout behavior keys on the artifact-selected branch, not profile mode.
- Profile initialization defaults design detection from the effective branch while retaining the
  existing provider and human-ready-signal behavior.
- A canonical read-only implementation-conformance reviewer now compares dual-v2 implementation
  evidence with Product/Technical contracts or the engineering-only behavior-preservation
  boundary. An implementation fixer applies findings and affected reviewers recheck before
  integration.
- Preserved legacy code-review/integration behavior and the existing design-provider/human-signal
  gate remain unchanged.

## Fresh-worker GREEN scenarios

| Required scenario | GREEN result |
|---|---|
| Engineering-only decision through Product creation and technical rebind/resume | PASS |
| Legacy profile + active v2; dual profile + existing legacy first/ready status | PASS |
| Invalid approved/terminal Product and decision/ready Technical invariants | PASS |
| Legacy `-product`/`-technical`, generic `schema`/`kind`, other-story v2 | PASS |
| `[slug]-[ID].md` with `Seed → Reviewed → Building → Complete` | PASS |
| Post-build finding → implementation fixer → affected recheck → PASS gate | PASS |
| `draft → ready → implementing → done`, with no persisted `review` | PASS |
| Post-implementation product decision → revised plan/implementation/conformance | PASS after pressure-test refactor |

Final GREEN workers:

- `/root/final_followup_fix/green_v2_pressure`
- `/root/final_followup_fix/green_legacy_conformance`

Both re-read the complete latest files after the final refactor and reported no remaining
protocol blocker.

## Verification

### Focused regressions

```bash
python3 -m unittest -v \
  tests.test_compatibility.CompatibilityValidatorTests.test_legacy_resume_uses_configured_status_flow \
  tests.test_compatibility.CompatibilityValidatorTests.test_v2_discovery_scopes_catch_all_to_requested_story \
  tests.test_compatibility.CompatibilityValidatorTests.test_needs_product_decision_has_persisted_return_transition \
  tests.test_compatibility.CompatibilityValidatorTests.test_branch_aware_preflight_follows_selected_artifacts \
  tests.test_compatibility.CompatibilityValidatorTests.test_status_dependent_artifact_invariants_hard_stop \
  tests.test_compatibility.CompatibilityValidatorTests.test_legacy_and_v2_classification_avoid_false_positives \
  tests.test_compatibility.CompatibilityValidatorTests.test_product_contract_reference_is_canonical_and_exact \
  tests.test_compatibility.CompatibilityValidatorTests.test_custom_dual_templates_are_validated_before_authoring \
  tests.test_compatibility.CompatibilityValidatorTests.test_post_implementation_conformance_gates_integration \
  tests.test_compatibility.CompatibilityValidatorTests.test_technical_contract_lifecycle_is_persisted
```

```text
Ran 10 tests in 0.013s
OK
```

### Contradiction-audit regressions

```bash
python3 -m unittest -v \
  tests.test_compatibility.CompatibilityValidatorTests.test_dual_profile_values_are_injected \
  tests.test_compatibility.CompatibilityValidatorTests.test_branch_aware_preflight_follows_selected_artifacts \
  tests.test_compatibility.CompatibilityValidatorTests.test_legacy_resume_uses_configured_status_flow \
  tests.test_compatibility.CompatibilityValidatorTests.test_status_dependent_artifact_invariants_hard_stop \
  tests.test_compatibility.CompatibilityValidatorTests.test_custom_dual_templates_are_validated_before_authoring \
  tests.test_compatibility.CompatibilityValidatorTests.test_technical_contract_lifecycle_is_persisted
```

```text
Ran 6 tests in 0.011s
OK
```

### Full unit suite

```bash
python3 -m unittest discover -s tests -v
```

```text
Ran 27 tests in 0.045s
OK
```

### Compatibility validator

```bash
python3 scripts/validate-compatibility.py
```

```text
Elephant compatibility validation passed.
```

### Every Elephant skill

```bash
for skill in plugins/elephant/skills/*; do
  if [ -f "$skill/SKILL.md" ]; then
    uv run --with pyyaml \
      /Users/aki/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill"
  fi
done
```

```text
Skill is valid!
Skill is valid!
Skill is valid!
Skill is valid!
Skill is valid!
Skill is valid!
Skill is valid!
```

The initial validator invocation without `--with pyyaml` failed before reading repository
content because the transient runner lacked the `yaml` module. Declaring the validator's runtime
dependency produced the successful result above and changed no repository file.

### Plugin validator

```bash
uv run --with pyyaml \
  /Users/aki/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/elephant
```

```text
Plugin validation passed: /Users/aki/Documents/Maio/elephant/.worktrees/product-first-followup/plugins/elephant
```

### Patch hygiene

```bash
git diff --check
```

No output; exit `0`.

## Files changed

- `README.md`
- `docs/superpowers/specs/2026-07-30-product-first-story-delivery-design.md`
- `docs/testing/product-first-story-skill-tests.md`
- `docs/testing/product-first-story-smoke-tests.md`
- `plugins/elephant/.codex-plugin/plugin.json`
- `plugins/elephant/references/runtime-compatibility.md`
- `plugins/elephant/skills/author-technical-contract/SKILL.md`
- `plugins/elephant/skills/author-technical-contract/technical-contract-template.md`
- `plugins/elephant/skills/init-profile/SKILL.md`
- `plugins/elephant/skills/shape-story/SKILL.md`
- `plugins/elephant/skills/ship-story/SKILL.md`
- `plugins/elephant/skills/ship-story/delivery-profile-schema.md`
- `plugins/elephant/skills/ship-story/reviewers/implementation-conformance.md` (new)
- `scripts/validate-compatibility.py`
- `tests/test_compatibility.py`
- `.superpowers/sdd/2026-07-30-product-first-story-delivery/final-fix-report.md` (this report)

## Self-review

- The dual design-gate adapter section is byte-for-byte unchanged from base `08f1c66`; a direct
  section diff produced no output. Manual/Claude Design providers and the human ready signal are
  therefore unchanged.
- V2 contains no generic brainstorming dispatch. Legacy authoring alone requires brainstorming;
  resumed legacy phases require only their remaining capabilities.
- The dual-v2 conformance requirement is explicitly scoped out of the legacy phase table, runtime
  reference, Finish condition, and integration red flag.
- No legacy discovery glob or lifecycle write hardcodes the bundled filename or status values.
- Product shaping remains main-thread, product-only, one-question-at-a-time, and approved Product
  Contracts remain immutable.
- Technical and implementation reviewers are read-only; only their corresponding fixers write,
  with affected rechecks required.
- Canonical paths reject absolute paths, URIs, backslashes, dot segments, escapes, missing files,
  other-story files, case/basename near matches, and non-active Product bindings.
- The Codex manifest keywords now match the Claude manifest's `product-first` and
  `dual-contract` discovery terms.
- The supplied untracked `final-fix-brief.md` is intentionally excluded from the commit.
- No push, PR, merge, main update, cachebuster, reinstall, or worktree removal was performed.

## Concerns

None. Owner decisions, applicable design handoff, reviewer/conformance PASS, required CI, and
configured integration approval remain intentional gates.

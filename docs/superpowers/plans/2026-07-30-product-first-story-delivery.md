# Elephant Product-First Story Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Elephant's mixed brainstorm-to-spec path for new stories with product-first
shaping, separate product and technical contracts, runtime-neutral specialist review, and
artifact-driven v2 resume while preserving legacy mixed-story delivery.

**Architecture:** `ship-story` remains the orchestrator. It dispatches the new main-thread
`elephant:shape-story` skill for product-facing stories, preserves the existing design gate with a
minimal product-contract adapter, then dispatches `elephant:author-technical-contract` for an
agent-owned technical author/reviewer loop. New stories use schema-tagged product and technical
artifacts; old mixed specs retain the current `superpowers:brainstorming` path.

**Tech Stack:** Markdown Agent Skills and templates, runtime-neutral subagent prompt templates,
Python 3 standard-library validation and `unittest`, Codex/Claude plugin manifests, Git.

## Global Constraints

- The v2 path must not invoke `superpowers:brainstorming`.
- Product shaping happens in the main conversation and contains no implementation-design questions.
- The product owner approves one Product Contract Recap and is not asked to reread the file.
- Product dispositions are `approved`, `split`, `deferred`, and `rejected`.
- Technical agents and reviewers may not edit the approved Product Contract.
- Reviewer prompts are canonical Elephant assets; host-native agents are optional adapters.
- Reviewer roles are read-only; an author/fixer applies findings and reviewers recheck.
- Worker delegation must have a sequential fallback with identical correctness.
- Existing design-provider behavior and the human ready signal remain unchanged.
- Existing mixed specs and profiles without `story_contracts` remain on the legacy path.
- New profiles default to dual contracts; existing profiles are never silently migrated.
- Shared workflow text remains runtime-neutral for Claude Code and Codex.
- Implement one skill at a time and complete RED–GREEN–REFACTOR validation before moving on.

---

### Task 1: RED Evidence and Deterministic Contract Tests

**Files:**
- Create: `docs/testing/product-first-story-skill-tests.md`
- Modify: `tests/test_compatibility.py`
- Modify: `scripts/validate-compatibility.py`

**Interfaces:**
- Produces: durable RED/GREEN scenario records for `shape-story`,
  `author-technical-contract`, and `ship-story`.
- Produces: `validate_repository(root) -> list[str]` checks for required v2 skill assets.
- Consumes: the design at
  `docs/superpowers/specs/2026-07-30-product-first-story-delivery-design.md`.

- [ ] **Step 1: Record the three RED baseline scenarios verbatim**

Create `docs/testing/product-first-story-skill-tests.md` with:

```markdown
# Product-First Story Skill Tests

## RED baseline: product drift

Record that current `ship-story` asked about copied entities, tokens, deploy paths, status,
endpoints, and API/data contracts before completing product definition, then wrote a mixed
Engineering Brief + Design Brief.

## RED baseline: invalid product idea

Record that a roadmap-progress dashboard card exposing phase, slice ID, and implementation
percentage had no formal reject/defer disposition. Current workflow effectively approved it and
specified a roadmap-progress API plus user-visible internal delivery language.

## RED baseline: technical overreach

Record that a general technical author produced a strong draft but silently resolved ambiguous
product meanings for copied IDs, name suffixing, and edit-only configuration, and used self-review
instead of independent specialist review.
```

Include the exact representative questions, decisions, and rationalizations returned by the RED
workers so later GREEN runs can be compared against the same scenarios.

- [ ] **Step 2: Add failing v2 asset tests**

Extend `tests/test_compatibility.py` with:

```python
def test_product_first_skill_assets_exist(self):
    root = ROOT / "plugins/elephant/skills"
    required = (
        "shape-story/SKILL.md",
        "shape-story/product-contract-template.md",
        "shape-story/reviewers/product-ux-critic.md",
        "shape-story/reviewers/copy-critic.md",
        "author-technical-contract/SKILL.md",
        "author-technical-contract/technical-contract-template.md",
        "author-technical-contract/reviewers/architecture.md",
        "author-technical-contract/reviewers/domain-data.md",
        "author-technical-contract/reviewers/security-operations.md",
        "author-technical-contract/reviewers/product-conformance.md",
        "author-technical-contract/reviewers/test.md",
        "author-technical-contract/reviewers/technical-adjudicator.md",
    )
    for relative in required:
        self.assertTrue((root / relative).is_file(), relative)


def test_v2_contract_vocabulary_is_wired(self):
    skills = ROOT / "plugins/elephant/skills"
    ship = (skills / "ship-story/SKILL.md").read_text()
    profile = (skills / "ship-story/delivery-profile-schema.md").read_text()
    init = (skills / "init-profile/SKILL.md").read_text()

    for phrase in (
        "elephant:shape-story",
        "elephant:author-technical-contract",
        "elephant.story/v2",
        "legacy-mixed",
        "needs-product-decision",
    ):
        self.assertIn(phrase, ship)
    self.assertIn("story_contracts", profile)
    self.assertIn("mode: dual", profile)
    self.assertIn("legacy-mixed", init)
```

Add a fixture test proving the validator reports a missing required v2 asset.

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
python3 -m unittest discover -s tests -v
```

Expected: existing 7 tests pass; the new asset and vocabulary tests fail because neither new skill
nor the v2 orchestration exists.

- [ ] **Step 4: Extend the validator minimally**

Add a `REQUIRED_V2_ASSETS` tuple and `_validate_v2_assets` function to
`scripts/validate-compatibility.py`. The validator should report every missing path and keep
frontmatter validation generic through the existing `skills/*/SKILL.md` scan.

- [ ] **Step 5: Run the fixture tests**

Run:

```bash
python3 -m unittest \
  tests.test_compatibility.CompatibilityValidatorTests.test_missing_v2_asset_is_reported -v
```

Expected: PASS. The current-repository tests remain RED until Tasks 2–4 add all assets and wiring.

- [ ] **Step 6: Commit the RED foundation**

```bash
git add docs/testing/product-first-story-skill-tests.md \
  tests/test_compatibility.py scripts/validate-compatibility.py
git commit -m "test: define product-first story contracts"
```

### Task 2: `elephant:shape-story` RED–GREEN–REFACTOR

**Files:**
- Create: `plugins/elephant/skills/shape-story/SKILL.md`
- Create: `plugins/elephant/skills/shape-story/product-contract-template.md`
- Create: `plugins/elephant/skills/shape-story/reviewers/product-ux-critic.md`
- Create: `plugins/elephant/skills/shape-story/reviewers/copy-critic.md`
- Modify: `docs/testing/product-first-story-skill-tests.md`
- Modify: `tests/test_compatibility.py`

**Interfaces:**
- Consumes: one coarse roadmap story, global product specs, current behavior, research policy, and
  the product owner conversation.
- Produces: `<ID>-<slug>-product.md` with `schema: elephant.story/v2`.
- Produces: terminal disposition `approved | split | deferred | rejected`.
- Produces: `design_sensitivity: High | Medium | Low` solely for the unchanged design-gate adapter.

- [ ] **Step 1: Add shape-story structural assertions**

Add tests that require the template frontmatter and all ten product sections:

```python
product_template = (skills / "shape-story/product-contract-template.md").read_text()
for phrase in (
    "schema: elephant.story/v2",
    "kind: product",
    "status: shaping",
    "## 1. User and context",
    "## 6. Information and copy",
    "## 10. Open product questions",
):
    self.assertIn(phrase, product_template)
```

Require the skill to contain the four exact dispositions, a main-conversation rule, one-question
discipline, product-only question domains, pre-recap critics, and the no-second-review rule.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_compatibility.CompatibilityValidatorTests.test_shape_story_contract -v
```

Expected: FAIL because the new skill and template do not exist.

- [ ] **Step 3: Write the minimum product template**

Create a template with this exact frontmatter shape:

```yaml
---
schema: elephant.story/v2
story: <ID>
slug: <slug>
kind: product
status: shaping
design_sensitivity: <High | Medium | Low>
supersedes: null
---
```

Add the ten approved sections. The template must state:

- no implementation design belongs in the file;
- `approved` requires no open product questions;
- `split/deferred/rejected` record rationale and next condition instead of technical content;
- critical user-facing copy is exact, while intentionally flexible supporting copy records intent
  and tone.

- [ ] **Step 4: Write the reviewer prompts**

`product-ux-critic.md` must return:

```text
Verdict: PASS | FINDINGS
Blocking product gaps:
- [contract section] evidence → unresolved user decision
Engineering leakage:
- [phrase/section] why it is implementation-shaped
Non-blocking observations:
- ...
```

`copy-critic.md` must inspect labels, hints, placeholders, empty/loading/error/disabled/success
states, internal terminology, and recovery guidance. Both prompts are read-only and may not invent
product decisions.

- [ ] **Step 5: Write the minimum `shape-story` skill**

The skill must:

1. run in the main conversation;
2. load roadmap seed, global specs, current experience, and applicable research;
3. triage product-facing versus engineering-only with ambiguity failing product-facing;
4. ask product questions one at a time;
5. keep endpoints, fields, modules, libraries, migrations, and tests out of shaping;
6. persist `shaping` drafts for resume;
7. run product/UX and copy critics before recap, in workers or sequentially;
8. resolve findings with the owner only when they require product judgment;
9. present one Product Contract Recap;
10. on explicit approval, write/synchronize `approved` and return control without a file-review
    checkpoint;
11. stop cleanly for split/deferred/rejected.

Do not invoke or require `superpowers:brainstorming`.

- [ ] **Step 6: Run metadata and deterministic GREEN checks**

Run:

```bash
uv run --with pyyaml python \
  /Users/aki/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  plugins/elephant/skills/shape-story
python3 -m unittest discover -s tests -v
```

Expected: shape-story tests pass; repository-wide tests may remain RED for the still-missing
technical skill and ship-story wiring.

- [ ] **Step 7: Run the two product GREEN scenarios**

Dispatch fresh general-purpose workers with the complete `shape-story` skill and template:

1. duplicate-campaign story under schedule pressure;
2. roadmap phase/slice/progress dashboard card under owner pressure to “just ship it.”

Expected:

- questions stay product-shaped;
- no endpoint, field, token, deploy-path, or data-model decision appears before approval;
- the invalid progress-card story is explicitly challenged and may be rejected;
- the returned artifact is product-only;
- no duplicate written-spec review is requested.

Record outputs and verdicts in `docs/testing/product-first-story-skill-tests.md`.

- [ ] **Step 8: REFACTOR against new rationalizations**

If a worker introduces technical design as “necessary clarification,” adds a hidden fifth
disposition, or treats recap as implicit approval, update the positive workflow recipe and rerun
the failed scenario. Record the new failure and fix. Do not add broad prohibition lists when a
required output slot resolves the wrong shape.

- [ ] **Step 9: Commit the verified skill**

```bash
git add plugins/elephant/skills/shape-story docs/testing/product-first-story-skill-tests.md \
  tests/test_compatibility.py
git commit -m "feat: add product-first story shaping"
```

### Task 3: `elephant:author-technical-contract` RED–GREEN–REFACTOR

**Files:**
- Create: `plugins/elephant/skills/author-technical-contract/SKILL.md`
- Create: `plugins/elephant/skills/author-technical-contract/technical-contract-template.md`
- Create: `plugins/elephant/skills/author-technical-contract/reviewers/architecture.md`
- Create: `plugins/elephant/skills/author-technical-contract/reviewers/domain-data.md`
- Create: `plugins/elephant/skills/author-technical-contract/reviewers/security-operations.md`
- Create: `plugins/elephant/skills/author-technical-contract/reviewers/product-conformance.md`
- Create: `plugins/elephant/skills/author-technical-contract/reviewers/test.md`
- Create: `plugins/elephant/skills/author-technical-contract/reviewers/technical-adjudicator.md`
- Modify: `docs/testing/product-first-story-skill-tests.md`
- Modify: `tests/test_compatibility.py`

**Interfaces:**
- Consumes: approved product contract or an explicitly engineering-only roadmap story, current
  repository, global specs, instructions, decision records, and optional design handoff.
- Produces: `<ID>-<slug>-technical.md` with `status: ready` or
  `status: needs-product-decision`.
- Produces: evidence-backed specialist findings and an author/fixer recheck loop.

- [ ] **Step 1: Add technical-contract structural assertions**

Require:

```yaml
---
schema: elephant.story/v2
story: <ID>
slug: <slug>
kind: technical
story_kind: <product-facing | engineering-only>
status: draft
product_contract: <path | null>
---
```

Require all eleven sections, the traceability columns `Product contract item`,
`Technical response`, and `Verification`, plus the two legal pre-plan states `ready` and
`needs-product-decision`.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_compatibility.CompatibilityValidatorTests.test_technical_contract -v
```

Expected: FAIL because the technical skill assets do not exist.

- [ ] **Step 3: Write the minimum technical template**

Create the eleven-section template from the design. State that:

- product-facing rows map every Product Contract requirement and state to verification;
- engineering-only stories replace the product binding with an explicit behavior-preservation
  contract;
- unresolved technical questions prevent `ready`;
- unresolved product meaning produces `needs-product-decision`;
- the author may not modify `product.md`.

- [ ] **Step 4: Write canonical reviewer prompts**

Every prompt must be read-only and return:

```text
Verdict: PASS | FINDINGS | NEEDS_PRODUCT_DECISION
Blocking findings:
- Severity — contract/risk reference — evidence — required outcome
Non-blocking findings:
- ...
```

Role boundaries:

- `architecture`: module boundaries, coupling, data flow, compatibility;
- `domain-data`: domain invariants, schema, migration, tenancy, money-path consistency;
- `security-operations`: auth, secrets, destructive behavior, retries, rollback, production risk;
- `product-conformance`: complete support for every product flow/state/copy boundary;
- `test`: whether proposed evidence can prove behavior and failure handling;
- `technical-adjudicator`: resolve only pure technical conflicts; escalate different user outcomes.

- [ ] **Step 5: Write the minimum technical-author skill**

The skill must:

1. reject a product-facing input without an approved product contract;
2. inspect the real repository before selecting architecture;
3. separate product ambiguity from technical choice;
4. write `draft`;
5. select reviewer roles from observable risk triggers;
6. dispatch read-only workers or run identical prompts sequentially;
7. deduplicate findings;
8. let the author/fixer revise the contract;
9. re-run affected reviewers;
10. use technical adjudication before escalating a pure engineering disagreement;
11. mark `ready` only with empty technical questions and no blocking findings;
12. mark `needs-product-decision` with a bounded decision brief when product meaning must change;
13. return without a routine owner review.

Do not invoke `superpowers:brainstorming` or `superpowers:writing-plans`; the orchestrator owns the
transition.

- [ ] **Step 6: Run metadata and deterministic GREEN checks**

Run:

```bash
uv run --with pyyaml python \
  /Users/aki/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  plugins/elephant/skills/author-technical-contract
python3 -m unittest discover -s tests -v
```

Expected: both standalone skill suites pass; ship-story/profile wiring tests remain RED.

- [ ] **Step 7: Run technical GREEN scenarios**

Use fresh workers with the new skill:

1. approved duplicate-campaign Product Contract with ambiguous “user-owned configuration”;
2. engineering-only refactor with no product artifact;
3. tenant-scoped schema change that requires domain/data and security/operations reviewers.

Expected:

- ambiguity becomes `needs-product-decision`, not an assumption;
- engineering-only work may proceed with an explicit behavior-preservation contract;
- risk-based roles run, author/fixer applies findings, and affected reviewers recheck;
- no reviewer edits the contract directly;
- no routine user review is requested.

Record outputs and verdicts.

- [ ] **Step 8: REFACTOR and re-run**

Close any loophole where the technical author calls an ambiguity “implementation detail,” skips
independent review because the change is small, or declares readiness with unresolved questions.
Rerun the failed scenario and record the final GREEN evidence.

- [ ] **Step 9: Commit the verified skill**

```bash
git add plugins/elephant/skills/author-technical-contract \
  docs/testing/product-first-story-skill-tests.md tests/test_compatibility.py
git commit -m "feat: add reviewed technical contracts"
```

### Task 4: Wire `ship-story`, Profile Defaults, Resume, and Legacy Compatibility

**Files:**
- Modify: `plugins/elephant/skills/ship-story/SKILL.md`
- Modify: `plugins/elephant/skills/ship-story/delivery-profile-schema.md`
- Retain: `plugins/elephant/skills/ship-story/slice-template.md`
- Modify: `plugins/elephant/skills/init-profile/SKILL.md`
- Modify: `plugins/elephant/references/runtime-compatibility.md`
- Modify: `tests/test_compatibility.py`
- Modify: `docs/testing/product-first-story-skill-tests.md`

**Interfaces:**
- Consumes: profile `story_contracts.mode`.
- Produces: dual-contract v2 or legacy-mixed phase detection.
- Dispatches: `elephant:shape-story`, existing design gate,
  `elephant:author-technical-contract`, then `superpowers:writing-plans`.

- [ ] **Step 1: Add failing orchestration and compatibility assertions**

Require `ship-story` to state:

```text
mode: dual
elephant:shape-story
elephant:author-technical-contract
superpowers:writing-plans
needs-product-decision
legacy-mixed
```

Require an explicit v2 detector ordered before the legacy detector, exact product and technical
status vocabulary, explicit `supersedes` handling when formats coexist, and no
`superpowers:brainstorming` dispatch inside the dual-mode section.

Require profile schema/default behavior:

- new profile → `story_contracts.mode: dual`;
- missing field in an existing profile → `legacy-mixed`;
- refresh proposes but does not apply migration;
- dual templates default to the two bundled templates.

- [ ] **Step 2: Run orchestration tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_compatibility.CompatibilityValidatorTests.test_v2_contract_vocabulary_is_wired \
  tests.test_compatibility.CompatibilityValidatorTests.test_dual_and_legacy_resume_contract -v
```

Expected: FAIL against current mixed-only `ship-story`.

- [ ] **Step 3: Rewrite the orchestration spine**

Keep preflight, profile injection, design provider behavior, plan, execute, finish, and closeout.
Replace the new-story Phase 1 with:

```text
triage
→ product-facing: elephant:shape-story
→ approved: existing design gate when applicable
→ elephant:author-technical-contract
→ ready: superpowers:writing-plans
```

Only the explicit `legacy-mixed` branch dispatches `superpowers:brainstorming` and uses
`slice-template.md`.

- [ ] **Step 4: Implement phase detection**

Detection order:

1. v2 product/technical artifacts;
2. terminal product dispositions;
3. design-gate state for approved product contracts;
4. technical draft/decision/ready;
5. plan/branch/PR/merge/closeout;
6. legacy mixed spec only when no v2 artifact exists or v2 explicitly supersedes it.

When v2 and legacy coexist without an explicit `supersedes`, stop and report the ambiguity.

- [ ] **Step 5: Adapt the existing design gate minimally**

For dual mode:

- read `design_sensitivity` from approved `product.md`;
- treat approved product as the durable pre-gate artifact;
- keep provider, directory, handoff, commit/push, and human signal unchanged;
- require handoff mapping to Product Contract flows/states;
- pass product + handoff to technical author.

Do not introduce a design-system protocol or agent-assisted provider.

- [ ] **Step 6: Update profile schema and discovery**

Add the `story_contracts` section and compatibility table. `init-profile` must:

- default new/greenfield profiles to dual;
- preserve existing explicit modes;
- interpret an existing profile with no mode as legacy;
- show migration to dual as a proposed confirmation change;
- never auto-rewrite existing artifact paths.

- [ ] **Step 7: Run deterministic GREEN checks**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate-compatibility.py
```

Expected: all tests pass and validator reports no compatibility error.

- [ ] **Step 8: Run orchestration pressure scenarios**

Fresh workers execute:

1. a new dual product-facing story;
2. a dual engineering-only story;
3. shaping resume;
4. `split`, `deferred`, and `rejected`;
5. `needs-product-decision`;
6. manual design-gate resume;
7. legacy mixed-spec resume;
8. v2/legacy collision without `supersedes`.

Expected: exact phase selection, no duplicate work, no v2 brainstorming call, and no new owner
checkpoint after approved shaping except existing design/high-risk escalation.

- [ ] **Step 9: REFACTOR and commit**

Address any phase-detection ambiguity or generic-brainstorm fallback rationalization, rerun the
affected scenario, then:

```bash
git add plugins/elephant/skills/ship-story plugins/elephant/skills/init-profile \
  plugins/elephant/references/runtime-compatibility.md \
  tests/test_compatibility.py docs/testing/product-first-story-skill-tests.md
git commit -m "refactor: make story delivery product-first"
```

### Task 5: Documentation, Packaging, and Full Verification

**Files:**
- Modify: `README.md`
- Create: `docs/testing/product-first-story-smoke-tests.md`
- Modify: `docs/testing/dual-runtime-smoke-tests.md`
- Modify: `plugins/elephant/.codex-plugin/plugin.json`
- Modify: `plugins/elephant/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `.agents/plugins/marketplace.json`
- Modify: `tests/test_compatibility.py`

**Interfaces:**
- Produces: Elephant `0.3.0`.
- Produces: installation and cross-runtime smoke guidance for seven shared skills.
- Consumes: every v2 skill/template/reviewer asset and legacy compatibility contract.

- [ ] **Step 1: Add failing documentation and version assertions**

Require both manifests to equal `0.3.0`; README to name `shape-story`,
`author-technical-contract`, dual contracts, legacy behavior, and the owner-intervention boundary;
smoke docs to list all v2 cases.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_compatibility.CompatibilityValidatorTests.test_product_first_documentation \
  tests.test_compatibility.CompatibilityValidatorTests.test_dual_manifests_and_codex_marketplace_match -v
```

Expected: version/documentation assertions fail.

- [ ] **Step 3: Update user and developer documentation**

README workflow must show:

```text
story seed → shape-story → product contract → existing design gate?
→ technical contract + specialist review → writing-plans → delivery
```

Document:

- product owner involvement ends after recap on the normal path;
- technical and code review is agent-owned;
- product/high-risk escalation conditions;
- new profiles use dual mode;
- existing profiles remain legacy until refreshed;
- old mixed specs remain resumable.

- [ ] **Step 4: Write cross-runtime smoke cases**

Create `docs/testing/product-first-story-smoke-tests.md` with the Task 4 scenario matrix and exact
expected phase/output. Update the existing dual-runtime smoke document to link it and retain
design-provider cases.

- [ ] **Step 5: Bump packaging to `0.3.0`**

Set both plugin manifests to `0.3.0`. Keep marketplace source paths and policies unchanged; update
descriptions/keywords only where they still describe the mixed brainstorm flow.

- [ ] **Step 6: Run per-skill validation**

Run:

```bash
for skill in plugins/elephant/skills/*; do
  if [ -f "$skill/SKILL.md" ]; then
    uv run --with pyyaml python \
      /Users/aki/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill"
  fi
done
```

Expected: every skill passes frontmatter and structural validation.

- [ ] **Step 7: Run full repository and plugin verification**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate-compatibility.py
uv run --with pyyaml python \
  /Users/aki/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/elephant
git diff --check
```

Expected: zero failures, compatibility validation passed, plugin validation passed, and no
whitespace errors.

- [ ] **Step 8: Inspect final diff against the design**

Check each success criterion in the design. Confirm:

- no v2 brainstorm dispatch;
- no product/technical mixed template;
- no routine owner review after recap;
- every reviewer is read-only;
- sequential fallback exists;
- design gate changes are compatibility-only;
- legacy files are not migrated.

- [ ] **Step 9: Commit packaging and docs**

```bash
git add README.md docs/testing plugins/elephant/.codex-plugin/plugin.json \
  plugins/elephant/.claude-plugin/plugin.json .claude-plugin/marketplace.json \
  .agents/plugins/marketplace.json tests/test_compatibility.py
git commit -m "docs: release product-first story workflow"
```

- [ ] **Step 10: Finish through the repository integration flow**

Use `superpowers:finishing-a-development-branch`. Push
`feat/product-first-story-shaping`, open a PR with the RED/GREEN evidence and verification
commands, wait for required checks, and follow the repository's normal merge/cleanup policy.

Do not run the cachebuster/reinstall loop against an unmerged remote source. After merge, use the
plugin creator update flow or the marketplace's released `0.3.0`, then start a new Codex/Claude
session for live smoke tests.

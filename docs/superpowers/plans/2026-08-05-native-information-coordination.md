# Native Information Coordination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Elephant's inactive provider/database orchestration with a minimal workspace map and host-native Linear, Notion, and Git/GitHub coordination workflow.

**Architecture:** Keep one pure Python module for validating stable repository/Product/domain entry points and selecting Product routes. Put all external behavior in host-executed skills backed by three canonical references: information routing, Linear planning, and Notion knowledge. Cut over the skills together, then delete the inactive v3 provider/setup/Linear runtime and its certification machinery; no adapter layer, database, background service, checkpoint store, fingerprint protocol, or permanent compatibility reader remains.

**Tech Stack:** Python 3 standard library, `unittest`, Markdown skills/references, YAML-shaped mappings supplied by the host, Git/GitHub, Linear and Notion host connectors, optional authenticated in-app browser for setup-only Linear administration.

## Global Constraints

- Contract basis: `sha256:ce9fa913caf310422ac380a9c355b04c87e9000043abd70f7afd85f4317310ae`.
- Product source: `docs/superpowers/specs/2026-08-05-one-person-company-information-coordination-product-v2.md`.
- Technical source: `docs/superpowers/specs/2026-08-05-one-person-company-information-coordination-technical.md`.
- Linear is the only live planning/progress home; Notion stores durable product meaning and decisions; Git/GitHub owns executable behavior and delivery.
- One Product is implicit and label-free. Multiple Products require verified Issue, Project, and Initiative Product labels.
- Planning questions start in Linear, product-meaning questions in Notion, and executable-behavior questions in Git. A stale projection never substitutes for missing authoritative context.
- Notion uses ordinary pages below Product Home; no databases, duplicate roadmap, raw chat, implementation plan, review log, test output, or checkpoint archive.
- Setup and shaping have one product approval. Routine delivery maintenance has no owner review; changed product meaning returns to shaping.
- Do not merge or port `feat/notion-providers`.
- Preserve the active v2 path until the coordinated skill cutover task passes; after cutover, remove v2/v3 compatibility rather than adding a converter or dual reader.
- Every task follows TDD where executable behavior changes, runs `git diff --check`, and ends in one Conventional Commit.
- Skill edits follow `superpowers:writing-skills`: run an agent pressure scenario against the old skill first, record the failure, edit one skill, then rerun the same scenario before editing the next skill. Python tests never grep prose as a proxy for agent behavior.

---

## File map

| Path | Responsibility |
|---|---|
| `plugins/elephant/elephant_runtime/workspace_map.py` | Pure validation and Product/planning route selection only |
| `scripts/workspace_map.py` | Checkout-only forwarding import for tests; no logic |
| `plugins/elephant/references/information-routing.md` | Authoritative-home routing, narrowing order, missing-context behavior |
| `plugins/elephant/references/linear-planning.md` | Native Linear hierarchy, Product classification, setup/write/read-back rules |
| `plugins/elephant/references/notion-knowledge.md` | Product Home containment, Decision/Knowledge content, scoped lookup rules |
| `plugins/elephant/skills/setup-workspace/SKILL.md` | Discover, propose, approve once, create/reuse/read back, write config last |
| `plugins/elephant/skills/shape-story/SKILL.md` | One-sentence product shaping, planning/knowledge disposition, one approval/apply |
| `plugins/elephant/skills/author-technical-contract/SKILL.md` | Bind current Linear/Notion product sources into a transient reviewed contract |
| `plugins/elephant/skills/ship-story/SKILL.md` | Native Linear/GitHub delivery, routine state maintenance, transient artifact cleanup |
| `plugins/elephant/skills/{kickoff,decompose-roadmap}/SKILL.md` | Native planning bootstrap and setup orchestration |
| `tests/test_workspace_map.py` | Pure workspace-map validation/routing tests |
| `tests/test_information_coordination.py` | Executable packaging, installed-smoke, and validator behavior |
| `docs/testing/native-information-coordination-pressure-tests.md` | RED/GREEN agent pressure scenarios and concise outcomes for skill behavior |
| `scripts/validate-compatibility.py` | Validate the new minimal shipped surface and forbid superseded assets |
| `README.md` | Current user workflow only |

---

### Task 1: Minimal workspace map runtime

**Files:**
- Create: `plugins/elephant/elephant_runtime/workspace_map.py`
- Create: `scripts/workspace_map.py`
- Create: `tests/test_workspace_map.py`
- Modify: `plugins/elephant/elephant_runtime/__init__.py`

**Interfaces:**
- Produces: `WORKSPACE_SCHEMA = "elephant.workspace/v4"`.
- Produces: `validate_workspace_map(document: Mapping[str, object]) -> tuple[str, ...]`.
- Produces: `resolve_product(document: Mapping[str, object], *, product_key: str | None = None) -> ProductRoute`.
- Produces: `planning_scope(document: Mapping[str, object], *, product_key: str | None = None) -> PlanningScope`.
- Produces immutable `ProductRoute(key, name, domain_keys, linear, notion)` and `PlanningScope(team_id, planning_ref, backlog_ref, product_labels)` dataclasses.

- [ ] **Step 1: Add failing validation fixtures**

```python
SINGLE = {
    "schema": "elephant.workspace/v4",
    "repository": {"id": "sample", "github": "https://github.com/acme/sample"},
    "linear": {"workspace_id": "ws", "team_id": "team"},
    "notion": {"root_id": "company"},
    "domains": {"web": {"paths": ["apps/web"], "instructions": ["AGENTS.md"]}},
    "products": {
        "sample": {
            "name": "Sample",
            "default": True,
            "domains": ["web"],
            "linear": {"planning_ref": "project-list", "backlog_ref": "backlog"},
            "notion": {"home_id": "sample-home", "knowledge_map_id": "sample-map"},
        }
    },
}

def test_single_product_is_implicit_and_label_free(self):
    self.assertEqual(validate_workspace_map(SINGLE), ())
    self.assertEqual(resolve_product(SINGLE).key, "sample")
    self.assertEqual(planning_scope(SINGLE).product_labels, {})
```

Add cases for duplicate/blank keys, unknown domains, unsafe paths, forbidden Story/content/secret keys, URL credentials, zero/two defaults, malformed anchors, missing single-Product labels being valid, and missing multi-Product Issue/Project/Initiative labels being invalid.

- [ ] **Step 2: Run the focused test and confirm it fails**

Run: `python3 -m unittest tests.test_workspace_map -v`

Expected: import failure for `scripts.workspace_map`.

- [ ] **Step 3: Implement the pure runtime**

Use only `collections.abc.Mapping`, `dataclasses`, `pathlib.PurePosixPath`, and `urllib.parse.urlsplit`. Reject story registries, bodies, tokens, passwords, query credentials, connector tool names, hashes, checkpoints, and plans anywhere in the map. Product entries own domain membership; domains never repeat Product membership.

```python
@dataclass(frozen=True)
class ProductRoute:
    key: str
    name: str
    domain_keys: tuple[str, ...]
    linear: Mapping[str, object]
    notion: Mapping[str, object]

@dataclass(frozen=True)
class PlanningScope:
    team_id: str
    planning_ref: str | None
    backlog_ref: str | None
    product_labels: Mapping[str, str]
```

`resolve_product()` uses the sole Product implicitly, otherwise requires a known key. `planning_scope()` returns `{}` labels for one Product and the exact three label IDs for multiple Products.

- [ ] **Step 4: Add the checkout forwarding module and package export**

```python
from typing import Any
from scripts._elephant_runtime_forward import canonical_module

_CANONICAL = canonical_module("elephant_runtime.workspace_map")
__all__ = _CANONICAL.__all__

def __getattr__(name: str) -> Any:
    return getattr(_CANONICAL, name)
```

Set `plugins/elephant/elephant_runtime/__init__.py` to export only `workspace_map` after the later deletion task; during this task export it alongside the still-active modules so current tests remain green.

- [ ] **Step 5: Run focused and existing compatibility tests**

Run: `python3 -m unittest tests.test_workspace_map tests.test_compatibility -v`

Expected: PASS, with the old runtime still present.

- [ ] **Step 6: Commit**

```bash
git add plugins/elephant/elephant_runtime/workspace_map.py plugins/elephant/elephant_runtime/__init__.py scripts/workspace_map.py tests/test_workspace_map.py
git commit -m "feat: add minimal workspace map"
```

---

### Task 2: Canonical native-integration references and setup workflow

**Files:**
- Create: `plugins/elephant/references/information-routing.md`
- Create: `plugins/elephant/references/linear-planning.md`
- Create: `plugins/elephant/references/notion-knowledge.md`
- Rewrite: `plugins/elephant/skills/setup-workspace/SKILL.md`
- Create: `tests/test_information_coordination.py`

**Interfaces:**
- Consumes: `elephant.workspace/v4` and the Task 1 Product/planning semantics.
- Produces: one shared routing protocol consumed by setup, shaping, technical authoring, and delivery.
- Produces: one human-readable setup proposal and optional `pending-application.md`; no Python connector/provider interface.

- [ ] **Step 1: Add failing executable packaging assertions**

Extend the compatibility validator's required-asset list to the three new references and make its installed-smoke path call the Task 1 workspace-map API. The test invokes `validate_repository()` on a temporary plugin missing each asset and asserts the returned missing-asset error; it does not assert source wording.

- [ ] **Step 2: Run the package test and confirm it fails**

Run: `python3 -m unittest tests.test_information_coordination -v`

Expected: FAIL because the validator and three packaged references do not exist yet.

- [ ] **Step 3: Write `information-routing.md`**

Define the three authoritative-home routes verbatim from Technical Contract §5, including cardinality-aware Linear scope, Product Home descendant scope, direct-relation crossing, insufficiency stop, source links, and stale-projection rejection.

- [ ] **Step 4: Write `linear-planning.md`**

Define Workspace=company, one Team default, Product=implicit or labels/views, Objective=Initiative, Project=Project, Milestone=Project Milestone, Story=Issue, Backlog=Backlog, Cycle optional. Include object-specific ownership checks, single→multi transition, `Related Objective`, meaningful updates, standalone Issue comments, append recovery, GitHub issue-ID linkage, and preservation of unrelated labels/relations.

- [ ] **Step 5: Write `notion-knowledge.md`**

Define Company Knowledge → Product Home → lazy Decisions/Knowledge categories and Knowledge Map. Specify exact-parent-plus-title identity, zero/one/multiple behavior, Decision and Knowledge human sections, living update/supersession behavior, Shared Knowledge root, and no roadmap/status duplication.

- [ ] **Step 6: RED pressure-test the current `setup-workspace`**

Give a fresh agent a one-sentence request to initialize a single-Product repository with Linear and Notion available, time pressure, and an explicit request not to build provider infrastructure. Record whether it still proposes manifests, fingerprints, certification, databases, or multiple owner gates in `docs/testing/native-information-coordination-pressure-tests.md`.

- [ ] **Step 7: Rewrite `setup-workspace`**

The skill flow is: read repository/integration context → discover Products and engineering domains separately → display one human proposal and config projection → approve once → create/publish operation branch note → direct connector/browser operations with read-back → write config last → config-only integration → remote verification → cleanup. Include single→multi inventory and fresh pre-promotion inventory. Do not import or mention `workspace_setup`, provider certification, transactions, fingerprints, hashes, bearer tokens, or databases.

- [ ] **Step 8: GREEN pressure-test `setup-workspace`**

Run the same scenario with the rewritten skill and references available. It passes only if the agent produces read-only discovery, the minimal human proposal, one approval, native create/reuse/read-back, config-last behavior, and no provider/database/transaction design. Add multi-Product, wrong-tenant browser, interrupted write, and single→multi variants before proceeding.

- [ ] **Step 9: Run the focused executable tests**

Run: `python3 -m unittest tests.test_workspace_map tests.test_information_coordination -v`

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add plugins/elephant/references plugins/elephant/skills/setup-workspace/SKILL.md tests/test_information_coordination.py docs/testing/native-information-coordination-pressure-tests.md
git commit -m "feat: define native workspace setup"
```

---

### Task 3: Product shaping, technical sources, and knowledge disposition

**Files:**
- Modify: `plugins/elephant/skills/shape-story/SKILL.md`
- Modify: `plugins/elephant/skills/shape-story/product-contract-template.md`
- Modify: `plugins/elephant/skills/author-technical-contract/SKILL.md`
- Modify: `plugins/elephant/skills/author-technical-contract/technical-contract-template.md`
- Modify: `plugins/elephant/skills/author-technical-contract/reviewers/{architecture,domain-data,security-operations,product-conformance,test,technical-adjudicator}.md`
- Modify: `tests/test_information_coordination.py`
- Modify: `docs/testing/native-information-coordination-pressure-tests.md`

**Interfaces:**
- Consumes: Task 2 routing/planning/knowledge references.
- Produces: an approved Linear Story plus optional Notion Decision/Knowledge pages; no permanent Git Product Contract.
- Produces: a transient Technical Contract binding exact Linear/Notion source IDs/URLs and a stable contract-basis marker.

- [ ] **Step 1: RED pressure-test the current `shape-story`**

Give a fresh agent a one-sentence Product idea plus linked Linear/Notion context. Score observable behavior: context route, user-only product discussion, dependency/conflict/priority/roadmap assessment, all four knowledge dispositions, one recap approval, native apply, and no permanent Git Product Contract. Record the baseline failure verbatim.

- [ ] **Step 2: Rewrite `shape-story` output/apply boundary**

Keep the existing product-only conversation and both critics. Replace permanent file output with a human recap held in the operation branch only until Linear/Notion read-back. Require planning placement, dependencies, conflicts, priority/roadmap impact, and knowledge disposition. One recap approval authorizes the displayed native changes; no data-entry review follows.

- [ ] **Step 3: GREEN pressure-test `shape-story`**

Rerun the original scenario plus direct-Objective, simple-Story/no-Notion, interrupted-write, and changed-product-meaning variants. Do not edit another skill until all variants follow the approved flow.

- [ ] **Step 4: RED pressure-test `author-technical-contract`**

Give a fresh agent a Linear Story plus linked Notion pages and no repository Product Contract. Record whether it incorrectly blocks, invents product meaning, skips a source, or requests owner technical review.

- [ ] **Step 5: Rewrite technical authoring source binding**

Make Linear Story plus linked Notion pages the approved product source bundle. The transient Technical Contract includes exact source links and a complete observable-requirement map. Preserve `draft → needs-product-decision → ready → implementing → done`, specialist review, immutable source behavior during a round, and basis-marker invalidation. Remove the assumption that an approved repository Product Contract must exist.

- [ ] **Step 6: Update reviewer prompts and templates**

Every reviewer accepts either the current external product-source bundle or, during migration only, an explicit behavior-preservation source. Product-conformance must compare all current source requirements. No prompt may ask for routine owner review or treat an external URL as sufficient without fetched content.

- [ ] **Step 7: GREEN pressure-test `author-technical-contract`**

Rerun the source-bundle scenario plus stale-source, missing-authority, product-decision-return, and technical-review variants. It passes only with complete fetched-source mapping, no invented product choice, independent reviewers, a stable basis marker, and no routine owner gate.

- [ ] **Step 8: Run focused executable tests**

Run: `python3 -m unittest tests.test_information_coordination -v`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add plugins/elephant/skills/shape-story plugins/elephant/skills/author-technical-contract tests/test_information_coordination.py docs/testing/native-information-coordination-pressure-tests.md
git commit -m "feat: coordinate product shaping natively"
```

---

### Task 4: Native delivery and coordinated skill cutover

**Files:**
- Rewrite: `plugins/elephant/skills/ship-story/SKILL.md`
- Modify: `plugins/elephant/skills/ship-story/reviewers/implementation-conformance.md`
- Rewrite: `plugins/elephant/skills/kickoff/SKILL.md`
- Rewrite: `plugins/elephant/skills/decompose-roadmap/SKILL.md`
- Delete: `plugins/elephant/skills/init-profile/`
- Modify: `plugins/elephant/skills/author-product-spec/SKILL.md`
- Modify: `tests/test_information_coordination.py`
- Modify: `docs/testing/native-information-coordination-pressure-tests.md`

**Interfaces:**
- Consumes: workspace map and native source bundle from Tasks 1–3.
- Produces: branch/PR names containing the Linear Issue ID, routine native state updates, meaningful updates/comments, and no merged transient contract/plan.
- Produces: `kickoff` = product foundation when needed → native Linear roadmap → `setup-workspace`; there is no delivery-profile phase.

- [ ] **Step 1: RED pressure-test the current `ship-story`**

Give a fresh agent a ready Linear Story with linked Notion context and a repository workspace map. Record whether it asks for a delivery profile/design gate, persists contracts/plans, misses the Linear ID in Git delivery, or produces checkpoint evidence.

- [ ] **Step 3: Rewrite `ship-story`**

Load `.agents/elephant/workspace.yaml`, current Linear Story, linked Notion sources, repository instructions, and the shared references. Keep worktree isolation, writing-plans, implementation/code/conformance reviewers, repository verification, and configured Git integration. Remove the legacy-mixed branch, design gate, delivery-profile reader, mixed-spec templates, checkpoint/evidence attachments, and permanent contract/plan retention.

- [ ] **Step 4: GREEN pressure-test `ship-story`**

Rerun native GitHub present/absent, standalone Story, Project/Initiative, block/split/defer/cancel/complete, unchanged update, source-change, and closeout variants. Do not edit another skill until all pass.

- [ ] **Step 5: RED pressure-test and rewrite `kickoff`**

Baseline a one-sentence product with partial existing Linear/Notion structure. Then rewrite only `kickoff` so it resumes the first incomplete product outcome and calls `setup-workspace` instead of `init-profile`; rerun the same scenario before proceeding.

- [ ] **Step 6: RED pressure-test and rewrite `decompose-roadmap`**

Baseline a foundation that needs only some planning levels. Then rewrite only `decompose-roadmap` to propose useful Initiatives/Projects/Milestones/Stories, approve once, write directly to Linear, and create no Git roadmap. Rerun direct-backlog and multi-level variants before proceeding.

- [ ] **Step 7: RED pressure-test and rewrite `author-product-spec`**

Baseline an existing product with partial durable knowledge. Then rewrite only `author-product-spec` to update Product Home Overview/Knowledge when future value exists and avoid mandatory Git spec systems or blank Notion categories. Rerun empty, existing, and no-durable-value variants before proceeding.

- [ ] **Step 8: Remove `init-profile`**

Delete the skill and its delivery-profile schema assets. Update all skill links and tests to direct setup callers to `elephant:setup-workspace`.

- [ ] **Step 9: Run focused executable tests**

Run: `python3 -m unittest tests.test_information_coordination -v`

Expected: PASS with no active skill referencing `delivery-profile.md`, legacy-mixed, the design gate, workspace providers, or permanent story plans.

- [ ] **Step 10: Commit**

```bash
git add plugins/elephant/skills tests/test_information_coordination.py docs/testing/native-information-coordination-pressure-tests.md
git commit -m "feat: cut over native story delivery"
```

---

### Task 5: Delete superseded provider/runtime and compatibility surface

**Files:**
- Delete: `plugins/elephant/elephant_runtime/{workspace_core,workspace_setup,linear}/`
- Delete: `scripts/{workspace_core,workspace_setup}/`
- Delete: `scripts/validate-linear-provider.py`
- Delete: `scripts/smoke-installed-setup-workspace.py`
- Delete: `plugins/elephant/references/workspace/`
- Delete: `plugins/elephant/references/providers/linear.md`
- Delete: `tests/test_{workspace_config,story_state_model,provider_contracts,setup_models,setup_discovery,setup_proposal,setup_dry_run,setup_files,setup_apply,linear_capabilities,linear_normalize,linear_provider,linear_checkpoint,linear_sandbox,linear_packaging}.py`
- Delete: `docs/testing/{linear-provider-sandbox.json,linear-provider-sandbox.md,setup-workspace-final-forward-smoke.md}`
- Delete: superseded Phase 1–4 plans/spec: `docs/superpowers/plans/2026-08-03-{workspace-core,setup-workspace}.md`, `docs/superpowers/plans/2026-08-04-{linear-provider,notion-providers}.md`, `docs/superpowers/specs/2026-08-03-external-workspace-orchestration-design.md`
- Rewrite: `plugins/elephant/elephant_runtime/installed_smoke.py`
- Rewrite: `scripts/validate-compatibility.py`
- Rewrite: `tests/test_compatibility.py`
- Modify: `plugins/elephant/elephant_runtime/__init__.py`

**Interfaces:**
- Consumes: Tasks 1–4 replacement surface.
- Produces: installed plugin importing only `workspace_map`; validator requires new skills/references and rejects superseded runtime directories.

- [ ] **Step 1: Change compatibility tests to the replacement oracle**

Expected shipped runtime exports are exactly:

```python
{
    "WORKSPACE_SCHEMA",
    "PlanningScope",
    "ProductRoute",
    "WorkspaceMapError",
    "planning_scope",
    "resolve_product",
    "validate_workspace_map",
}
```

Require `setup-workspace`, `shape-story`, `author-technical-contract`, `ship-story`, and the three new references. Assert provider/setup/Linear runtime directories and old reference trees are forbidden when present.

- [ ] **Step 2: Run compatibility tests and confirm they fail on old assets**

Run: `python3 -m unittest tests.test_compatibility -v`

Expected: FAIL listing superseded assets still present.

- [ ] **Step 3: Rewrite installed smoke**

Validate one label-free single-Product mapping and one labeled multi-Product mapping through `validate_workspace_map()`, `resolve_product()`, and `planning_scope()`. No fake external adapter or filesystem transaction remains.

- [ ] **Step 4: Remove superseded code, tests, references, plans, and evidence**

Use patch-based deletions. Keep the approved predecessor/successor Product Contracts and ready Technical Contract because the successor chain and implementation basis still reference them.

- [ ] **Step 5: Rewrite compatibility validator**

Remove v3 core/setup/provider vocabulary, certification transcript loading, and profile/design-gate requirements. Validate both plugin manifests, shared skills, canonical reviewer assets, new references, exact minimal runtime exports, and absence of forbidden host-specific coupling.

- [ ] **Step 6: Run remaining unit and compatibility suites**

Run: `python3 -m unittest discover -s tests -v`

Run: `python3 scripts/validate-compatibility.py`

Expected: PASS; no deleted test module is discovered.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: remove provider orchestration runtime"
```

---

### Task 6: Documentation, plugin metadata, and generic pilot evidence

**Files:**
- Rewrite: `README.md`
- Modify: `plugins/elephant/.codex-plugin/plugin.json`
- Modify: `plugins/elephant/.claude-plugin/plugin.json`
- Modify: `.agents/plugins/marketplace.json` only if plugin metadata schema requires it
- Rewrite: `docs/testing/dual-runtime-smoke-tests.md`
- Rewrite: `docs/testing/product-first-story-smoke-tests.md`
- Delete or rewrite: `docs/testing/product-first-story-skill-tests.md`
- Modify: `docs/superpowers/specs/2026-08-05-one-person-company-information-coordination-technical.md` section 11 evidence only

**Interfaces:**
- Consumes: completed implementation and tests.
- Produces: a current install/use guide and redacted generic pilot outcome; no connector-call transcript.

- [ ] **Step 1: Add executable metadata validation**

Extend `tests/test_compatibility.py` to load both plugin manifests and marketplace JSON, validate their schema and matching version/name/capabilities, and exercise the installed skill inventory. Human README prose is reviewed directly and is not protected by source-text assertions.

- [ ] **Step 2: Rewrite current user documentation**

Lead with: one-sentence idea → product shaping → one approval → Linear/Notion apply → technical design/review → delivery. Document `setup-workspace`, Product/Objective/Project/Milestone/Story semantics, authoritative information homes, native GitHub linkage, and graceful ordinary-link fallback. Keep installation commands for both hosts.

- [ ] **Step 3: Update smoke documents**

Replace historical provider transcripts with concise cases for single Product, multi Product, routing, knowledge disposition, native GitHub linkage, missing integrations, and no-global-search short-circuiting. Record outcomes and direct source categories only.

- [ ] **Step 4: Run all deterministic verification**

Run: `python3 -m unittest discover -s tests -v`

Run: `python3 scripts/validate-compatibility.py`

Run: `python3 -m compileall -q plugins/elephant scripts tests`

Run:

```bash
uv run --with pyyaml python \
  /Users/aki/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/elephant
```

Run: `git diff --check`

Expected: all commands exit 0.

- [ ] **Step 5: Run the generic cold-start pilot**

Install or load the worktree plugin in a fresh host session. Against a disposable repository fixture, validate setup discovery/proposal without writes, one approved shaping trace, one planning question starting in Linear, one meaning question starting in Notion, and one executable question starting in Git. Record concise redacted outcomes in the Technical Contract review evidence; do not store raw connector payloads.

- [ ] **Step 6: Run final independent reviews**

Run code-quality review, implementation conformance against both approved contracts, and affected rechecks. Fix only implementation defects; changed product meaning returns to shaping.

- [ ] **Step 7: Commit**

```bash
git add README.md plugins/elephant/.codex-plugin/plugin.json plugins/elephant/.claude-plugin/plugin.json .agents/plugins/marketplace.json docs/testing docs/superpowers/specs/2026-08-05-one-person-company-information-coordination-technical.md tests/test_compatibility.py
git commit -m "docs: publish native coordination workflow"
```

---

## Plan self-review

- Product and technical coverage: Tasks 1–6 map workspace data, setup, routing, planning, knowledge, shaping, technical review, delivery, deletion, packaging, recovery, migration boundary, and pilot verification.
- Scope boundary: concrete Maio content migration is intentionally excluded by the approved contracts and begins only after Task 6 passes as a separately shaped migration Story.
- Placeholder scan: every action names its concrete behavior, evidence, and interface.
- Type consistency: Task 1's `validate_workspace_map`, `resolve_product`, `planning_scope`, `ProductRoute`, and `PlanningScope` names are used unchanged by Tasks 2–6.

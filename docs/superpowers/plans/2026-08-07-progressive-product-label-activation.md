# Progressive Product-label Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a multi-Product Elephant workspace activate Project and Initiative Product labels only when those native planning levels are actually used, while keeping Issue labels and all existing-object classification strict.

**Architecture:** Keep `elephant.workspace/v4` and its existing optional label fields. Loosen only the multi-Product invariant so Issue labels are universal while Project/Initiative labels may be absent; expose configured namespaces through the existing partial `PlanningScope.product_labels` mapping. Teach setup and roadmap skills to activate a missing namespace once, persist its verified ID before writing the first object, and continue using exact native labels thereafter.

**Tech Stack:** Python 3 standard library runtime/tests, Markdown plugin skills and references, JSON Claude Code/Codex manifests.

## Global Constraints

- Do not introduce a new workspace schema version, provider adapter, persistent setup ledger, background synchronizer, or generic label registry.
- A multi-Product workspace always requires one unique verified Issue Product label per Product.
- Project and Initiative labels are optional only while that Product has no managed object of the matching type.
- Every existing or newly written managed Project/Initiative still requires exactly one matching native Product label.
- Persist and integrate a newly verified label ID before writing the first object in that namespace.
- Single-Product work remains implicit and label-free.

---

### Task 1: Make workspace routing support inactive label namespaces

**Files:**
- Modify: `tests/test_workspace_map.py`
- Modify: `plugins/elephant/elephant_runtime/workspace_map.py`
- Modify: `plugins/elephant/elephant_runtime/installed_smoke.py`
- Modify: `tests/test_compatibility.py`

**Interfaces:**
- Consumes: existing `validate_workspace_map(document) -> tuple[str, ...]` and `planning_scope(document, *, product_key=None) -> PlanningScope`.
- Produces: the same public signatures; `PlanningScope.product_labels` contains only configured namespaces.

- [ ] **Step 1: Replace the all-label requirement test with focused progressive cases**

Keep the full-label routing test, then replace `test_multi_product_rejects_each_missing_label` with:

```python
def test_multi_product_allows_inactive_project_and_initiative_labels(self) -> None:
    value = multi_product()
    for product in value["products"].values():
        del product["linear"]["project_label_id"]
        del product["linear"]["initiative_label_id"]

    self.assertEqual(validate_workspace_map(value), ())
    self.assertEqual(
        planning_scope(value, product_key="second").product_labels,
        {"issue": "issue-label-second"},
    )

def test_multi_product_still_requires_issue_label(self) -> None:
    value = multi_product()
    del value["products"]["second"]["linear"]["issue_label_id"]
    self.assertIn(
        "products.second.linear.issue_label_id: required for multiple Products",
        validate_workspace_map(value),
    )

def test_multi_product_rejects_duplicate_present_optional_labels(self) -> None:
    value = multi_product()
    value["products"]["second"]["linear"]["project_label_id"] = (
        value["products"]["sample"]["linear"]["project_label_id"]
    )
    self.assertIn(
        "products.second.linear.project_label_id: duplicate Product label",
        validate_workspace_map(value),
    )
```

- [ ] **Step 2: Run the focused tests and verify current behavior fails**

Run:

```bash
python3 -m unittest \
  tests.test_workspace_map.WorkspaceMapValidationTests.test_multi_product_allows_inactive_project_and_initiative_labels \
  tests.test_workspace_map.WorkspaceMapValidationTests.test_multi_product_still_requires_issue_label \
  tests.test_workspace_map.WorkspaceMapValidationTests.test_multi_product_rejects_duplicate_present_optional_labels -v
```

Expected: the inactive-label test fails because validation requires Project/Initiative labels and `planning_scope()` indexes them.

- [ ] **Step 3: Narrow validation and return only configured namespaces**

In `validate_workspace_map()`, require `issue_label_id` for multiple Products, then run uniqueness checks only for present valid IDs:

```python
if multiple:
    issue_label = product_linear.get("issue_label_id")
    if not _anchor(issue_label):
        problems.append(
            f"products.{key}.linear.issue_label_id: required for multiple Products"
        )
    for namespace, field in _LABEL_FIELDS.items():
        label = product_linear.get(field)
        if not _anchor(label):
            continue
        assert isinstance(label, str)
        if label in labels_by_namespace[namespace]:
            problems.append(
                f"products.{key}.linear.{field}: duplicate Product label"
            )
        labels_by_namespace[namespace].add(label)
```

In `planning_scope()`, replace unconditional indexing with:

```python
if len(products) > 1:
    labels = {
        namespace: str(route.linear[field])
        for namespace, field in _LABEL_FIELDS.items()
        if field in route.linear
    }
```

- [ ] **Step 4: Update the installed smoke to prove a partial multi-Product map**

Remove `project_label_id` and `initiative_label_id` from the `second` fixture only, and change the expected multi-Product smoke result in `tests/test_compatibility.py` to:

```python
"labels": {"issue": "issue-label-second"},
```

This keeps the first Product fixture fully activated and proves activation is per Product and per namespace.

- [ ] **Step 5: Run the runtime and compatibility tests**

Run:

```bash
python3 -m unittest tests.test_workspace_map tests.test_compatibility -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit the runtime contract**

```bash
git add tests/test_workspace_map.py tests/test_compatibility.py \
  plugins/elephant/elephant_runtime/workspace_map.py \
  plugins/elephant/elephant_runtime/installed_smoke.py
git commit -m "feat: activate product labels progressively"
```

---

### Task 2: Teach setup and roadmap when labels become required

**Files:**
- Modify: `tests/test_information_coordination.py`
- Modify: `plugins/elephant/references/linear-planning.md`
- Modify: `plugins/elephant/references/information-routing.md`
- Modify: `plugins/elephant/skills/setup-workspace/SKILL.md`
- Modify: `plugins/elephant/skills/decompose-roadmap/SKILL.md`
- Modify: `docs/testing/dual-runtime-smoke-tests.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: partial `PlanningScope.product_labels` from Task 1 and existing capability-adaptive provisioning rules.
- Produces: setup-time Issue-label activation and inventory rules; roadmap-time Project/Initiative activation before first use.

- [ ] **Step 1: Replace the old all-three-label contract assertion**

Replace `test_multi_product_label_contract_remains_intact` with assertions that require these exact durable phrases across planning, setup, and roadmap guidance:

```python
def test_multi_product_labels_activate_with_their_planning_level(self) -> None:
    planning = read("plugins/elephant/references/linear-planning.md")
    setup = read("plugins/elephant/skills/setup-workspace/SKILL.md")
    roadmap = read("plugins/elephant/skills/decompose-roadmap/SKILL.md")

    self.assertIn("Issue Product labels are required during setup", planning)
    self.assertIn("inactive for that Product", planning)
    self.assertIn("existing managed Projects and Initiatives", setup)
    self.assertIn("does not block setup", setup)
    self.assertIn("persist its verified label ID", roadmap)
    self.assertIn("before the first object write", roadmap)
```

Add a smoke-contract assertion that the Codex CLI profile explicitly treats an unused unreadable Project/Initiative namespace as non-blocking while still blocking a required active namespace.

- [ ] **Step 2: Run the focused coordination tests and verify they fail**

Run:

```bash
python3 -m unittest \
  tests.test_information_coordination.NativeCoordinationPackagingTests.test_multi_product_labels_activate_with_their_planning_level \
  tests.test_information_coordination.NativeCoordinationPackagingTests.test_dual_runtime_smoke_covers_setup_capability_profiles -v
```

Expected: FAIL because the current documents still require all three label types during setup.

- [ ] **Step 3: Revise the canonical Linear rules**

In `linear-planning.md`:

- keep exact-one-label classification for every managed object;
- state that Issue labels are setup-required, while an absent Project/Initiative ID means that level is inactive for that Product;
- require activation when existing inventory or an approved first write needs the level;
- forbid unlabeled writes and repeated name lookup;
- change single-to-multiple migration from “all three label types for every Product” to Issue labels for every Product plus Project/Initiative labels for Products owning existing objects.

In `information-routing.md`, require a matching Product label only for the current object type; treat an absent optional namespace as no configured Product scope for routine reads and route inventory/reconciliation through setup or roadmap activation.

- [ ] **Step 4: Revise setup capability classification**

In `setup-workspace/SKILL.md`, require setup to:

- create/verify Issue labels for every Product;
- inventory existing managed Projects and Initiatives;
- activate and backfill only namespaces required by that inventory;
- classify capabilities only for current required structure;
- state that an unused unavailable Project/Initiative label namespace does not block setup;
- keep workspace config last.

- [ ] **Step 5: Revise first-use roadmap activation**

In `decompose-roadmap/SKILL.md`, add the missing-label activation to the existing single roadmap recap. During apply, require this order:

1. exact-scope search/reuse/provision and semantic read-back;
2. persist its verified label ID in `.agents/elephant/workspace.yaml` through repository integration;
3. re-read and validate the map;
4. write the first Project or Initiative with that exact label.

Do not add a second approval or a manual runtime fallback.

- [ ] **Step 6: Update human and host smoke documentation**

Revise `README.md` and `docs/testing/dual-runtime-smoke-tests.md` so multi-Product behavior says:

- Issues are classified from setup;
- Project/Initiative namespaces activate only when existing or approved work uses them;
- an unavailable unused namespace is non-blocking;
- an active namespace without semantic verification remains blocking.

- [ ] **Step 7: Run coordination tests and commit**

Run:

```bash
python3 -m unittest tests.test_information_coordination -v
```

Expected: all tests pass.

Then:

```bash
git add tests/test_information_coordination.py README.md docs/testing/dual-runtime-smoke-tests.md \
  plugins/elephant/references/information-routing.md \
  plugins/elephant/references/linear-planning.md \
  plugins/elephant/skills/setup-workspace/SKILL.md \
  plugins/elephant/skills/decompose-roadmap/SKILL.md
git commit -m "docs: make product label activation progressive"
```

---

### Task 3: Release and verify the dual-runtime plugin

**Files:**
- Modify: `tests/test_compatibility.py`
- Modify: `plugins/elephant/.codex-plugin/plugin.json`
- Modify: `plugins/elephant/.claude-plugin/plugin.json`

**Interfaces:**
- Consumes: completed runtime and skill contract from Tasks 1–2.
- Produces: installable Elephant `0.5.2` with matching Claude Code and Codex metadata.

- [ ] **Step 1: Make the version assertion fail for 0.5.2**

Change:

```python
EXPECTED_VERSION = "0.5.2"
```

Run:

```bash
python3 -m unittest tests.test_compatibility.CompatibilityValidatorTests.test_plugin_metadata_describes_native_coordination -v
```

Expected: FAIL because both manifests still report `0.5.1`.

- [ ] **Step 2: Bump both plugin manifests**

Set `version` to `0.5.2` in both plugin manifests without changing other metadata.

- [ ] **Step 3: Run full repository verification**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate-compatibility.py
uv run --with pyyaml python \
  /Users/aki/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/elephant
PYTHONPATH=plugins/elephant python3 -c \
  'from elephant_runtime.installed_smoke import run_installed_smoke; print(run_installed_smoke())'
git diff --check
```

Expected: all unit tests pass; compatibility and plugin validation pass; installed smoke reports only the Issue label for the partially activated second Product; `git diff --check` prints nothing.

- [ ] **Step 4: Commit the release metadata**

```bash
git add tests/test_compatibility.py \
  plugins/elephant/.codex-plugin/plugin.json \
  plugins/elephant/.claude-plugin/plugin.json
git commit -m "chore: release elephant 0.5.2"
```

- [ ] **Step 5: Verify the final branch state**

Run:

```bash
git status --short --branch
git log -4 --oneline
```

Expected: clean branch with the design, runtime, guidance, and release commits ahead of `origin/main`; no unrelated files are changed.

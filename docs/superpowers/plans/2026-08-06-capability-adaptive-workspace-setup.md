# Capability-Adaptive Workspace Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Elephant preserve its multi-Product Linear label protocol while handing unsupported one-time workspace administration to the owner and resuming from semantically verified native state.

**Architecture:** Keep `elephant.workspace/v4` and all three Product-label namespaces unchanged. Change only the host-orchestrated setup instructions: classify each proposed operation by executable capability, apply supported writes, issue one exact setup-only owner checklist for verifiable administrative gaps, then reconcile native objects before writing config. Capture real host profiles as manual smoke scenarios and retain lightweight packaging assertions for the required prompt contract.

**Tech Stack:** Markdown-based Codex/Claude skills and references, Python `unittest` packaging assertions, JSON plugin manifests, existing compatibility validator.

## Global Constraints

- Connector or browser automation coverage does not define the durable Linear/Notion protocol.
- Multiple Products continue to require verified Issue, Project, and Initiative Product-label IDs.
- Manual provisioning is setup-only; runtime workflows receive no manual fallback for Product classification.
- Owner-provisioned required objects must be semantically readable and unambiguous before config publication.
- `.agents/elephant/workspace.yaml` remains the only durable local setup result and is written last.
- Do not add a provider runtime, setup state machine, pending file, background synchronizer, or new workspace schema.
- One proposal approval covers both Elephant writes and the displayed owner checklist.
- Preserve exact-scope search, reuse, read-back, no automatic rollback, and no uncertain-write retry behavior.

---

## File Structure

- `plugins/elephant/skills/setup-workspace/SKILL.md`: owns capability classification, proposal presentation, automatic application, owner handoff, continuation, and completion behavior.
- `plugins/elephant/references/linear-planning.md`: owns the boundary between allowed setup provisioning and forbidden runtime manual maintenance.
- `tests/test_information_coordination.py`: provides fast packaging regressions for the active skill/reference contract.
- `docs/testing/native-information-coordination-pressure-tests.md`: records the observed CLI failure and the corrected behavioral outcome.
- `docs/testing/dual-runtime-smoke-tests.md`: defines live host-profile scenarios that must be exercised in Codex CLI and browser-capable hosts.
- `plugins/elephant/.codex-plugin/plugin.json`: publishes version `0.5.1` for Codex.
- `plugins/elephant/.claude-plugin/plugin.json`: publishes version `0.5.1` for Claude Code.
- `tests/test_compatibility.py`: pins the packaged version and validates both manifests.

No runtime Python file changes. In particular, do not modify
`plugins/elephant/elephant_runtime/workspace_map.py`.

---

### Task 1: Make setup capability-adaptive without weakening Product labels

**Files:**
- Modify: `tests/test_information_coordination.py:124-157`
- Modify: `plugins/elephant/skills/setup-workspace/SKILL.md:25-97`
- Modify: `plugins/elephant/references/linear-planning.md:79-98`

**Interfaces:**
- Consumes: existing `elephant.workspace/v4` fields `issue_label_id`, `project_label_id`, and `initiative_label_id`; existing exact-scope reconciliation rules.
- Produces: the prompt-level execution classes `Elephant`, `Owner setup`, and `Unavailable`; required-versus-enhancement proposal semantics; a resumable owner checklist verified through native reads.

- [ ] **Step 1: Write failing packaging tests for the approved setup contract**

Add these methods to `NativeCoordinationPackagingTests`:

```python
def test_setup_classifies_execution_capability_before_approval(self) -> None:
    text = read("plugins/elephant/skills/setup-workspace/SKILL.md")
    for requirement in (
        "Elephant",
        "Owner setup",
        "Unavailable",
        "required structure",
        "enhancements",
        "before presenting the proposal",
    ):
        self.assertIn(requirement, text)

def test_setup_allows_verified_owner_provisioning_without_a_ledger(self) -> None:
    setup = read("plugins/elephant/skills/setup-workspace/SKILL.md")
    planning = read("plugins/elephant/references/linear-planning.md")
    for requirement in (
        "one numbered checklist",
        "opaque IDs",
        "semantic read",
        "resume signal",
        "workspace.yaml",
    ):
        self.assertIn(requirement, setup)
    self.assertIn("setup-only", planning)
    self.assertIn("no manual runtime fallback", planning)
    self.assertNotIn(
        "If neither route can create a required Product label, stop before the first setup write",
        setup,
    )

def test_multi_product_label_contract_remains_intact(self) -> None:
    planning = read("plugins/elephant/references/linear-planning.md")
    self.assertIn("Issue, Project, and Initiative", planning)
    self.assertIn("Create and verify all three label types", planning)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_information_coordination.NativeCoordinationPackagingTests.test_setup_classifies_execution_capability_before_approval \
  tests.test_information_coordination.NativeCoordinationPackagingTests.test_setup_allows_verified_owner_provisioning_without_a_ledger \
  tests.test_information_coordination.NativeCoordinationPackagingTests.test_multi_product_label_contract_remains_intact
```

Expected: the first two tests fail because the current skill supports connector/browser execution
only and stops before writes; the label-contract test passes and protects the invariant.

- [ ] **Step 3: Add capability classification to setup discovery and proposal**

In `setup-workspace/SKILL.md`, extend discovery so it inventories every operation required by the
candidate proposal before presenting that proposal. Add this exact semantic contract, adapting
line wrapping only:

```markdown
Classify every proposed operation before presenting the proposal:

- **Elephant** when the active semantic connector or authenticated browser can execute the
  operation and its result can be verified by semantic read;
- **Owner setup** when Elephant cannot execute the low-frequency administrative operation but can
  verify its result afterward by semantic read;
- **Unavailable** when no execution route produces a result Elephant can verify. A required
  unavailable operation blocks the proposal; an optional operation is omitted or declared
  degraded.

Treat capability as operation-specific. Connector availability does not imply workspace rename,
label creation, view creation, or native-integration administration. A declared tool rejected by
its backing service is unavailable for the current run.
```

Extend the proposal bullets with an execution owner for every operation and two visible groups:
`required structure` and `enhancements`. State that the single approval covers both Elephant's
writes and the displayed owner checklist.

- [ ] **Step 4: Replace the browser-only failure branch with automatic apply plus owner handoff**

Keep browser tenant proof intact when a browser exists. Replace the current rule that stops before
the first write when connector and browser creation are absent with this behavior:

```markdown
Apply approved **Elephant** operations sequentially and verify each result. If **Owner setup**
operations remain, return one numbered checklist after the supported writes. Each item names the
exact tenant, native object type, Product or company scope, final human-visible name and applicable
color, description, or relation, shortest known UI location or direct entry link, whether it is
required or an enhancement, and the semantic read Elephant will use to verify it. The checklist
contains no implementation explanation, connector diagnostics, internal setup state, or request
for the owner to copy opaque IDs.

The owner's completion message is a resume signal, not verification evidence. Re-read every exact
native scope: adopt one equivalent result, keep zero pending, and stop on multiple or conflicting
results. A required owner-provisioned object must read back before its stable ID or URL enters the
workspace map. Unsupported enhancements may degrade when an ordinary scoped query or link keeps
the workflow correct.
```

Retain the no-duplicate, no-rollback, and interrupted-write reconciliation paragraphs. Clarify that
a cold session may reconcile read-only, but must present the reconstructed compact proposal once
before any remaining external or config write.

- [ ] **Step 5: Clarify setup-only manual provisioning in Linear planning**

Rewrite `linear-planning.md`'s setup-administration ending to preserve all three label types and add
this distinction:

```markdown
Manual provisioning is setup-only. When neither the connector nor authenticated browser can
perform an approved low-frequency administrative operation, setup may hand it to the owner only
when the resulting native object can be found and verified through a semantic read. This does not
create a manual runtime fallback: after setup, Elephant-managed Issues, Projects, and Initiatives
must maintain their verified Product labels automatically.
```

Keep the single-to-multiple transition inventory and backfill requirements unchanged. Allow the
optional overview, display-name cleanup, and native integration administration to be non-blocking
enhancements when their documented fallbacks preserve correct navigation.

- [ ] **Step 6: Run focused and full tests and verify GREEN**

Run:

```bash
python3 -m unittest tests.test_information_coordination
python3 scripts/validate-compatibility.py
python3 -m unittest discover -s tests -p 'test_*.py'
git diff --check
```

Expected: compatibility validation passes, all tests pass, and `git diff --check` prints no errors.

- [ ] **Step 7: Commit the capability-adaptive setup contract**

```bash
git add \
  plugins/elephant/skills/setup-workspace/SKILL.md \
  plugins/elephant/references/linear-planning.md \
  tests/test_information_coordination.py
git commit -m "feat: support verified manual workspace setup"
```

---

### Task 2: Turn host capability assumptions into explicit live smoke scenarios

**Files:**
- Modify: `docs/testing/native-information-coordination-pressure-tests.md:6-46`
- Modify: `docs/testing/dual-runtime-smoke-tests.md:13-31`
- Modify: `tests/test_information_coordination.py`

**Interfaces:**
- Consumes: the three execution classes and completion rules from Task 1.
- Produces: named CLI, browser-capable, and unverifiable host profiles with concrete expected
  outcomes for release testing.

- [ ] **Step 1: Write a failing packaging test for the live host profiles**

Add this method to `NativeCoordinationPackagingTests`:

```python
def test_dual_runtime_smoke_covers_setup_capability_profiles(self) -> None:
    text = read("docs/testing/dual-runtime-smoke-tests.md")
    for profile in (
        "Codex CLI profile",
        "Browser-capable profile",
        "Unverifiable profile",
        "Owner setup",
        "semantic read-back",
    ):
        self.assertIn(profile, text)
```

- [ ] **Step 2: Run the new test and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_information_coordination.NativeCoordinationPackagingTests.test_dual_runtime_smoke_covers_setup_capability_profiles
```

Expected: FAIL because the current smoke document has only generic single- and multi-Product
scenarios.

- [ ] **Step 3: Record the real CLI pressure failure and corrected behavior**

Update the `setup-workspace` pressure-test section with the observed multi-Product CLI case:

```markdown
Scenario: initialize a real multi-Product repository from Codex CLI where semantic reads cover all
three Linear label namespaces, writes can create Issue and Initiative labels but not Project
labels, Team/workspace rename is unavailable, and no authenticated in-app browser exists.

RED observation: setup treated the missing Project-label write path as a protocol failure and had
promised rename and administration work before classifying the active host's operations.

GREEN outcome: setup preserves all three Product-label namespaces, performs supported writes,
hands off exact Project-label and display-name administration, reads the resulting labels back,
and writes config only after every required label is verified. No setup ledger is created.
```

Retain the earlier provider-overengineering RED history, but make this newer capability-boundary
case the final setup pressure scenario.

- [ ] **Step 4: Define the three live host profiles**

Extend `dual-runtime-smoke-tests.md` under multi-Product setup:

```markdown
### Codex CLI profile

Run with semantic Linear/Notion connectors and no browser. Make at least one required
administrative create unavailable while keeping its collection semantically readable. The
proposal must classify that operation as **Owner setup**, execute supported approved writes, emit
one exact checklist, and resume through semantic read-back without requesting opaque IDs.

### Browser-capable profile

Run the same target structure where an authenticated browser can perform the connector gap. The
proposal and final workspace map must express the same Product protocol; only the executor differs.

### Unverifiable profile

Remove both the write path and semantic read-back for one required Product-label namespace. Setup
must classify the operation as **Unavailable** before approval and must not publish a workspace
map that runtime workflows cannot consume.
```

Add a resume check to the CLI profile: rerun after the owner creates the object and verify reuse,
stable-ID capture, no duplicate, and config-last behavior.

- [ ] **Step 5: Run the documentation contract tests**

Run:

```bash
python3 -m unittest tests.test_information_coordination
git diff --check
```

Expected: all information-coordination tests pass and the diff check is clean.

- [ ] **Step 6: Commit the host-profile scenarios**

```bash
git add \
  docs/testing/native-information-coordination-pressure-tests.md \
  docs/testing/dual-runtime-smoke-tests.md \
  tests/test_information_coordination.py
git commit -m "test: cover workspace setup capability profiles"
```

---

### Task 3: Publish the corrected workflow as Elephant 0.5.1

**Files:**
- Modify: `tests/test_compatibility.py:29`
- Modify: `plugins/elephant/.codex-plugin/plugin.json:3`
- Modify: `plugins/elephant/.claude-plugin/plugin.json:3`

**Interfaces:**
- Consumes: the completed skill/reference contract and host-profile tests from Tasks 1–2.
- Produces: matching Codex and Claude plugin manifests for version `0.5.1`.

- [ ] **Step 1: Change the expected version and verify RED**

Change:

```python
EXPECTED_VERSION = "0.5.1"
```

Run:

```bash
python3 -m unittest tests.test_compatibility.CompatibilityValidatorTests.test_plugin_metadata_describes_native_coordination
```

Expected: FAIL because both manifests still report `0.5.0`.

- [ ] **Step 2: Bump both plugin manifests**

Set the top-level version in both manifests:

```json
"version": "0.5.1"
```

Do not alter descriptions, capabilities, keywords, or skill inventory.

- [ ] **Step 3: Run full release verification**

Run:

```bash
python3 scripts/validate-compatibility.py
python3 -m unittest discover -s tests -p 'test_*.py'
PYTHONPATH=plugins/elephant python3 -c \
  'from elephant_runtime.installed_smoke import run_installed_smoke; print(run_installed_smoke())'
git diff --check
git status --short
```

Expected:

- compatibility validation reports `Elephant compatibility validation passed.`;
- all unit tests pass;
- installed smoke reports successful single- and multi-Product routing;
- the diff check is clean;
- status contains only the three release files before commit.

- [ ] **Step 4: Commit the patch release**

```bash
git add \
  plugins/elephant/.codex-plugin/plugin.json \
  plugins/elephant/.claude-plugin/plugin.json \
  tests/test_compatibility.py
git commit -m "chore: release elephant 0.5.1"
```

- [ ] **Step 5: Verify the complete branch before handoff**

Run:

```bash
python3 scripts/validate-compatibility.py
python3 -m unittest discover -s tests -p 'test_*.py'
PYTHONPATH=plugins/elephant python3 -c \
  'from elephant_runtime.installed_smoke import run_installed_smoke; print(run_installed_smoke())'
git log --oneline -5
git status --short --branch
```

Expected: every verification command succeeds; the log contains the design, plan, setup-contract,
host-profile, and release commits; the worktree is clean and ahead of `origin/main` by those local
commits until publication is explicitly requested.

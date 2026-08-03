# Elephant Workspace Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the executable and documented v3 workspace, provider, routing, diagnostic, and story-state contracts that every later external-workspace phase will build on, without changing the current shipping runtime yet.

**Architecture:** Canonical agent-facing contracts live under `plugins/elephant/references/workspace/`. Small standard-library Python modules under `scripts/workspace_core/` act as executable test oracles for schema validation, routing, provider capability preflight, and state transitions. The current `init-profile` and `ship-story` paths remain untouched until the coordinated cutover phase; no legacy adapter or dual writer is introduced.

**Tech Stack:** Markdown skill references, Python 3 standard library, `unittest`, existing static compatibility validator.

## Global Constraints

- The final architecture has no legacy profile, mixed-spec, or artifact compatibility layer.
- During phase 1, the current runtime remains untouched; new v3 contracts are additive and not yet dispatched.
- The canonical workspace path is `.agents/elephant/workspace.yaml`.
- Scoped profiles live under `.agents/elephant/profiles/` and are selected by product or the engineering-only default.
- Story-level records, Product Contracts, Technical Contracts, and plans never belong in the workspace registry.
- Provider choices are explicit: `linear | git` for stories, `notion | git` for product knowledge and Product Contracts, and `git` for the delivery workspace.
- A selected external provider never silently falls back to Git.
- Capability diagnostics are exactly `platform_unsupported | connector_capability_missing | permission_missing | configuration_missing`.
- Linear human state and the opaque Elephant checkpoint remain separate.
- Product and engineering dimensions remain independent.
- All Python code uses only the standard library.
- Claude Code and Codex consume the same canonical reference files.

---

## File Structure

### New canonical references

- `plugins/elephant/references/workspace/workspace-schema.md` — exact v3 registry shape, invariants, and valid/invalid examples.
- `plugins/elephant/references/workspace/profile-schema.md` — product and engineering profile shapes plus routing rules.
- `plugins/elephant/references/workspace/provider-contracts.md` — logical store operations, capability requirements, diagnostic categories, and repair authority.
- `plugins/elephant/references/workspace/story-state-model.md` — human status, product disposition, machine checkpoint, and transition invariants.

### New executable contract oracles

- `scripts/workspace_core/__init__.py` — public exports used by tests and later phases.
- `scripts/workspace_core/config.py` — workspace/profile validation and route resolution.
- `scripts/workspace_core/providers.py` — provider capability sets, preflight results, and diagnostic classification.
- `scripts/workspace_core/states.py` — story state and repair-decision transition functions.

### Tests and validation wiring

- `tests/test_workspace_config.py` — registry/profile validation and routing behavior.
- `tests/test_provider_contracts.py` — provider capability preflight and diagnostic behavior.
- `tests/test_story_state_model.py` — human/checkpoint transitions and repair authority.
- `tests/test_compatibility.py` — required v3 asset and shared-runtime assertions.
- `scripts/validate-compatibility.py` — require v3 references while leaving the active v2 runtime checks intact.

---

### Task 1: Workspace Registry Validation

**Files:**
- Create: `scripts/workspace_core/__init__.py`
- Create: `scripts/workspace_core/config.py`
- Create: `tests/test_workspace_config.py`
- Create: `plugins/elephant/references/workspace/workspace-schema.md`

**Interfaces:**
- Produces: `validate_workspace(document: Mapping[str, object]) -> tuple[str, ...]`
- Produces: `WorkspaceRouteError(ValueError)`
- Consumes: no phase-1 code outside the Python standard library.

- [ ] **Step 1: Write failing registry validation tests**

Create `tests/test_workspace_config.py` with a reusable valid registry and these exact assertions:

```python
from copy import deepcopy
import unittest

from scripts.workspace_core import validate_workspace


VALID_WORKSPACE = {
    "schema": "elephant.workspace/v3",
    "repository": {"id": "repo-maio"},
    "providers": {
        "story_store": "linear",
        "product_knowledge_store": "notion",
        "product_contract_store": "notion",
        "delivery_workspace": "git",
    },
    "bindings": {
        "linear": {"workspace_id": "lin-ws", "team_id": "lin-team"},
        "notion": {
            "workspace_id": "notion-ws",
            "products_database_id": "db-products",
            "knowledge_database_id": "db-knowledge",
            "contracts_database_id": "db-contracts",
        },
    },
    "products": {
        "clickfalcon": {
            "profile": ".agents/elephant/profiles/clickfalcon.yaml",
            "story_ref": "linear-label-clickfalcon",
            "knowledge_ref": "notion-product-clickfalcon",
            "primary_domains": ["clickfalcon"],
        }
    },
    "domains": {
        "clickfalcon": {
            "scopes": ["apps/tracker-web", "apps/tracker-engine"],
            "instruction_paths": ["AGENTS.md"],
            "verification": ["bun run type-check"],
            "products": ["clickfalcon"],
        }
    },
    "engineering_profile": ".agents/elephant/profiles/engineering.yaml",
}


class WorkspaceValidationTests(unittest.TestCase):
    def test_valid_external_workspace_has_no_problems(self):
        self.assertEqual(validate_workspace(VALID_WORKSPACE), ())

    def test_rejects_unknown_schema(self):
        value = deepcopy(VALID_WORKSPACE)
        value["schema"] = "elephant.workspace/v2"
        self.assertIn("schema: expected elephant.workspace/v3", validate_workspace(value))

    def test_selected_external_provider_requires_binding(self):
        value = deepcopy(VALID_WORKSPACE)
        del value["bindings"]["notion"]
        problems = validate_workspace(value)
        self.assertIn("bindings.notion: required by selected provider", problems)

    def test_rejects_story_level_registry_content(self):
        value = deepcopy(VALID_WORKSPACE)
        value["stories"] = {"CF-1": {"status": "Ready"}}
        self.assertIn("stories: story-level registry content is forbidden", validate_workspace(value))

    def test_product_domains_must_exist(self):
        value = deepcopy(VALID_WORKSPACE)
        value["products"]["clickfalcon"]["primary_domains"] = ["missing"]
        self.assertIn(
            "products.clickfalcon.primary_domains[0]: unknown domain missing",
            validate_workspace(value),
        )

    def test_domain_products_must_exist(self):
        value = deepcopy(VALID_WORKSPACE)
        value["domains"]["clickfalcon"]["products"] = ["missing"]
        self.assertIn(
            "domains.clickfalcon.products[0]: unknown product missing",
            validate_workspace(value),
        )

    def test_rejects_unsafe_profile_path(self):
        value = deepcopy(VALID_WORKSPACE)
        value["products"]["clickfalcon"]["profile"] = "../outside.yaml"
        self.assertIn(
            "products.clickfalcon.profile: expected repository-relative POSIX path",
            validate_workspace(value),
        )

    def test_all_git_workspace_needs_no_external_binding(self):
        value = deepcopy(VALID_WORKSPACE)
        value["providers"] = {
            "story_store": "git",
            "product_knowledge_store": "git",
            "product_contract_store": "git",
            "delivery_workspace": "git",
        }
        value["bindings"] = {}
        self.assertEqual(validate_workspace(value), ())
```

- [ ] **Step 2: Run the registry tests and verify the import fails**

Run:

```bash
python3 -m unittest tests.test_workspace_config -v
```

Expected: `ImportError` because `scripts.workspace_core` does not exist.

- [ ] **Step 3: Implement the minimal registry validator**

Create `scripts/workspace_core/config.py` with:

```python
from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath


WORKSPACE_SCHEMA = "elephant.workspace/v3"
PROVIDER_CHOICES = {
    "story_store": {"linear", "git"},
    "product_knowledge_store": {"notion", "git"},
    "product_contract_store": {"notion", "git"},
    "delivery_workspace": {"git"},
}
FORBIDDEN_STORY_KEYS = {"stories", "story_registry", "checkpoints", "contracts", "plans"}


class WorkspaceRouteError(ValueError):
    pass


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _is_repo_relative_posix_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        return False
    parts = PurePosixPath(value).parts
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def validate_workspace(document: Mapping[str, object]) -> tuple[str, ...]:
    problems: list[str] = []
    if document.get("schema") != WORKSPACE_SCHEMA:
        problems.append(f"schema: expected {WORKSPACE_SCHEMA}")

    for key in sorted(FORBIDDEN_STORY_KEYS & document.keys()):
        problems.append(f"{key}: story-level registry content is forbidden")

    providers = _mapping(document.get("providers"))
    bindings = _mapping(document.get("bindings"))
    for slot, choices in PROVIDER_CHOICES.items():
        selected = providers.get(slot)
        if selected not in choices:
            problems.append(f"providers.{slot}: expected one of {sorted(choices)}")
        if selected in {"linear", "notion"} and selected not in bindings:
            problems.append(f"bindings.{selected}: required by selected provider")

    products = _mapping(document.get("products"))
    domains = _mapping(document.get("domains"))
    for product_key, raw_product in products.items():
        product = _mapping(raw_product)
        if not _is_repo_relative_posix_path(product.get("profile")):
            problems.append(
                f"products.{product_key}.profile: expected repository-relative POSIX path"
            )
        for index, domain in enumerate(product.get("primary_domains", [])):
            if domain not in domains:
                problems.append(
                    f"products.{product_key}.primary_domains[{index}]: unknown domain {domain}"
                )
    for domain_key, raw_domain in domains.items():
        domain = _mapping(raw_domain)
        for index, product in enumerate(domain.get("products", [])):
            if product not in products:
                problems.append(
                    f"domains.{domain_key}.products[{index}]: unknown product {product}"
                )
    if not _is_repo_relative_posix_path(document.get("engineering_profile")):
        problems.append("engineering_profile: expected repository-relative POSIX path")
    return tuple(problems)
```

Export it from `scripts/workspace_core/__init__.py`:

```python
from .config import WorkspaceRouteError, validate_workspace

__all__ = ["WorkspaceRouteError", "validate_workspace"]
```

- [ ] **Step 4: Run the registry tests and verify they pass**

Run:

```bash
python3 -m unittest tests.test_workspace_config -v
```

Expected: all registry tests pass.

- [ ] **Step 5: Write the canonical workspace schema reference**

Create `plugins/elephant/references/workspace/workspace-schema.md`. It must define the exact
`VALID_WORKSPACE` shape above, explain every field, require repository-relative POSIX profile and
scope paths, prohibit story-level keys, require external bindings for selected providers, and show
one all-Git example with no `linear` or `notion` binding. State that external IDs are opaque and
must be discovered and read back rather than guessed.

- [ ] **Step 6: Re-run the focused tests and commit**

Run:

```bash
python3 -m unittest tests.test_workspace_config -v
git diff --check
```

Expected: tests pass and `git diff --check` emits no output.

Commit:

```bash
git add scripts/workspace_core tests/test_workspace_config.py plugins/elephant/references/workspace/workspace-schema.md
git commit -m "feat: define workspace registry contract"
```

### Task 2: Scoped Profile Validation and Routing

**Files:**
- Modify: `scripts/workspace_core/config.py`
- Modify: `scripts/workspace_core/__init__.py`
- Modify: `tests/test_workspace_config.py`
- Create: `plugins/elephant/references/workspace/profile-schema.md`

**Interfaces:**
- Consumes: `validate_workspace(document)` and `WorkspaceRouteError` from Task 1.
- Produces: `validate_profile(document: Mapping[str, object]) -> tuple[str, ...]`
- Produces: `resolve_profile(workspace, *, story_kind, product_key) -> str`

- [ ] **Step 1: Add failing profile and route tests**

Append these fixtures and tests to `tests/test_workspace_config.py`:

```python
from scripts.workspace_core import resolve_profile, validate_profile, WorkspaceRouteError


PRODUCT_PROFILE = {
    "schema": "elephant.profile/v3",
    "kind": "product",
    "product": "clickfalcon",
    "context": {"knowledge_keys": ["product-overview", "glossary"]},
    "design_gate": {"enabled": False},
    "research": {"mode": "auto-assess", "depth": "light"},
    "execution": {"isolation": "git-worktree", "review_cadence": "task"},
    "verification": {"commands": ["bun run type-check"]},
    "finish": {"integration": "github-pr-squash", "auto_merge_on_green": True},
    "language": {"dialogue": "zh-CN", "docs": "en", "commits": "en"},
}

ENGINEERING_PROFILE = {
    **PRODUCT_PROFILE,
    "kind": "engineering",
    "product": None,
    "behavior_preservation_required": True,
}


class ProfileAndRoutingTests(unittest.TestCase):
    def test_valid_product_profile_has_no_problems(self):
        self.assertEqual(validate_profile(PRODUCT_PROFILE), ())

    def test_engineering_profile_requires_behavior_preservation(self):
        value = deepcopy(ENGINEERING_PROFILE)
        value["behavior_preservation_required"] = False
        self.assertIn(
            "behavior_preservation_required: engineering profile requires true",
            validate_profile(value),
        )

    def test_product_story_resolves_product_profile(self):
        self.assertEqual(
            resolve_profile(VALID_WORKSPACE, story_kind="product-facing", product_key="clickfalcon"),
            ".agents/elephant/profiles/clickfalcon.yaml",
        )

    def test_engineering_story_resolves_engineering_profile(self):
        self.assertEqual(
            resolve_profile(VALID_WORKSPACE, story_kind="engineering-only", product_key=None),
            ".agents/elephant/profiles/engineering.yaml",
        )

    def test_product_story_requires_exactly_one_known_product(self):
        with self.assertRaisesRegex(WorkspaceRouteError, "known product_key"):
            resolve_profile(VALID_WORKSPACE, story_kind="product-facing", product_key=None)
```

- [ ] **Step 2: Run the focused tests and verify missing symbols fail**

Run:

```bash
python3 -m unittest tests.test_workspace_config.ProfileAndRoutingTests -v
```

Expected: `ImportError` for `resolve_profile` or `validate_profile`.

- [ ] **Step 3: Implement profile validation and routing**

Add constants and functions to `scripts/workspace_core/config.py`:

```python
PROFILE_SCHEMA = "elephant.profile/v3"
PROFILE_KINDS = {"product", "engineering"}


def validate_profile(document: Mapping[str, object]) -> tuple[str, ...]:
    problems: list[str] = []
    if document.get("schema") != PROFILE_SCHEMA:
        problems.append(f"schema: expected {PROFILE_SCHEMA}")
    kind = document.get("kind")
    if kind not in PROFILE_KINDS:
        problems.append(f"kind: expected one of {sorted(PROFILE_KINDS)}")
    if kind == "product" and not isinstance(document.get("product"), str):
        problems.append("product: product profile requires a product key")
    if kind == "engineering" and document.get("behavior_preservation_required") is not True:
        problems.append("behavior_preservation_required: engineering profile requires true")
    for section in (
        "context",
        "design_gate",
        "research",
        "execution",
        "verification",
        "finish",
        "language",
    ):
        if not isinstance(document.get(section), Mapping):
            problems.append(f"{section}: required mapping")
    return tuple(problems)


def resolve_profile(
    workspace: Mapping[str, object], *, story_kind: str, product_key: str | None
) -> str:
    if validate_workspace(workspace):
        raise WorkspaceRouteError("workspace is invalid")
    if story_kind == "engineering-only":
        profile = workspace.get("engineering_profile")
        if not isinstance(profile, str):
            raise WorkspaceRouteError("engineering_profile is required")
        return profile
    if story_kind != "product-facing":
        raise WorkspaceRouteError("story_kind must be product-facing or engineering-only")
    products = _mapping(workspace.get("products"))
    if product_key is None or product_key not in products:
        raise WorkspaceRouteError("product-facing story requires one known product_key")
    profile = _mapping(products[product_key]).get("profile")
    if not isinstance(profile, str):
        raise WorkspaceRouteError(f"product {product_key} has no profile")
    return profile
```

Export both functions from `scripts/workspace_core/__init__.py`.

- [ ] **Step 4: Run the profile tests and verify they pass**

Run:

```bash
python3 -m unittest tests.test_workspace_config -v
```

Expected: all registry and profile tests pass.

- [ ] **Step 5: Write the profile schema reference**

Create `plugins/elephant/references/workspace/profile-schema.md` with the two exact fixtures above,
field semantics, and these invariants:

- product profiles bind exactly one workspace product key;
- engineering profiles use `product: null` and require behavior preservation;
- profile selection comes from Linear Product/Kind through the registry, not repository directory
  names;
- affected engineering domains are discovered from repository evidence and the eventual diff;
- profiles contain routing and gates, never product knowledge or story history;
- every path is repository-relative POSIX and must remain within the repository.

- [ ] **Step 6: Re-run focused tests and commit**

Run:

```bash
python3 -m unittest tests.test_workspace_config -v
git diff --check
```

Commit:

```bash
git add scripts/workspace_core tests/test_workspace_config.py plugins/elephant/references/workspace/profile-schema.md
git commit -m "feat: define scoped delivery profiles"
```

### Task 3: Provider Capability and Diagnostic Contracts

**Files:**
- Create: `scripts/workspace_core/providers.py`
- Modify: `scripts/workspace_core/__init__.py`
- Create: `tests/test_provider_contracts.py`
- Create: `plugins/elephant/references/workspace/provider-contracts.md`

**Interfaces:**
- Produces: `ProviderKind`, `DiagnosticCode`, `CapabilityDiagnostic`, `preflight_provider()`.
- Produces exact capability sets: `STORY_RUNTIME_CAPABILITIES`, `KNOWLEDGE_RUNTIME_CAPABILITIES`, `CONTRACT_RUNTIME_CAPABILITIES`, `DELIVERY_RUNTIME_CAPABILITIES`.
- Later provider phases must satisfy these sets without renaming operations.

- [ ] **Step 1: Write failing provider preflight tests**

Create `tests/test_provider_contracts.py`:

```python
import unittest

from scripts.workspace_core import (
    CONTRACT_RUNTIME_CAPABILITIES,
    DiagnosticCode,
    ProviderKind,
    preflight_provider,
)


class ProviderContractTests(unittest.TestCase):
    def test_complete_contract_provider_is_ready(self):
        result = preflight_provider(
            ProviderKind.PRODUCT_CONTRACT,
            exposed=CONTRACT_RUNTIME_CAPABILITIES,
            permitted=CONTRACT_RUNTIME_CAPABILITIES,
            configured=CONTRACT_RUNTIME_CAPABILITIES,
            platform_supported=CONTRACT_RUNTIME_CAPABILITIES,
        )
        self.assertTrue(result.ready)
        self.assertEqual(result.diagnostics, ())

    def test_diagnostic_precedence_is_platform_connector_permission_configuration(self):
        required = set(CONTRACT_RUNTIME_CAPABILITIES)
        capability = "approve_contract"
        cases = (
            (required - {capability}, required, required, DiagnosticCode.PLATFORM_UNSUPPORTED),
            (required, required - {capability}, required, DiagnosticCode.CONNECTOR_CAPABILITY_MISSING),
            (required, required, required - {capability}, DiagnosticCode.PERMISSION_MISSING),
        )
        for platform, exposed, permitted, expected in cases:
            with self.subTest(expected=expected):
                result = preflight_provider(
                    ProviderKind.PRODUCT_CONTRACT,
                    platform_supported=platform,
                    exposed=exposed,
                    permitted=permitted,
                    configured=required,
                )
                self.assertEqual(result.diagnostics[0].code, expected)

    def test_configuration_missing_is_distinct(self):
        required = set(CONTRACT_RUNTIME_CAPABILITIES)
        result = preflight_provider(
            ProviderKind.PRODUCT_CONTRACT,
            platform_supported=required,
            exposed=required,
            permitted=required,
            configured=required - {"resolve_active_contract"},
        )
        self.assertEqual(result.diagnostics[0].code, DiagnosticCode.CONFIGURATION_MISSING)
```

- [ ] **Step 2: Run the provider tests and verify the import fails**

Run:

```bash
python3 -m unittest tests.test_provider_contracts -v
```

Expected: `ImportError` because provider contract symbols do not exist.

- [ ] **Step 3: Implement exact provider capability sets and preflight**

Create `scripts/workspace_core/providers.py` using `Enum`, frozen dataclasses, and these exact
runtime capability sets:

```python
STORY_RUNTIME_CAPABILITIES = frozenset({
    "create_story", "read_story", "update_story_status", "write_product_recap",
    "create_child_story", "link_story_relation", "bind_product_contract",
    "read_checkpoint", "write_checkpoint", "attach_delivery_evidence",
})
KNOWLEDGE_RUNTIME_CAPABILITIES = frozenset({
    "read_knowledge", "query_knowledge", "create_knowledge", "update_knowledge",
    "supersede_knowledge", "link_knowledge_relation",
})
CONTRACT_RUNTIME_CAPABILITIES = frozenset({
    "create_contract_draft", "read_contract", "update_contract_draft",
    "approve_contract", "create_contract_successor", "resolve_active_contract",
    "verify_contract_fingerprint", "verify_story_binding",
})
DELIVERY_RUNTIME_CAPABILITIES = frozenset({
    "persist_technical_contract", "persist_plan", "bind_delivery_branch",
    "record_conformance", "promote_knowledge", "remove_transient_artifacts",
})
```

Define:

```python
class ProviderKind(str, Enum):
    STORY = "story"
    PRODUCT_KNOWLEDGE = "product_knowledge"
    PRODUCT_CONTRACT = "product_contract"
    DELIVERY_WORKSPACE = "delivery_workspace"


class DiagnosticCode(str, Enum):
    PLATFORM_UNSUPPORTED = "platform_unsupported"
    CONNECTOR_CAPABILITY_MISSING = "connector_capability_missing"
    PERMISSION_MISSING = "permission_missing"
    CONFIGURATION_MISSING = "configuration_missing"


@dataclass(frozen=True)
class CapabilityDiagnostic:
    capability: str
    code: DiagnosticCode


@dataclass(frozen=True)
class ProviderPreflight:
    ready: bool
    diagnostics: tuple[CapabilityDiagnostic, ...]
```

`preflight_provider()` must compare each required capability in sorted order and assign the first
failing layer in this exact order: platform, connector exposure, permission, configuration. Export
all public symbols from `scripts/workspace_core/__init__.py`.

- [ ] **Step 4: Run provider tests and verify they pass**

Run:

```bash
python3 -m unittest tests.test_provider_contracts -v
```

Expected: all tests pass.

- [ ] **Step 5: Write the provider contract reference**

Create `plugins/elephant/references/workspace/provider-contracts.md`. Repeat the exact capability
names above and define request/response evidence for each. Specify:

- host tools are adapters; canonical operations are runtime-neutral;
- missing runtime capabilities block provider readiness;
- administrative setup operations may produce a one-time manual handoff and read-back check;
- selected providers never fall back;
- stable external keys and read-after-write verification are mandatory;
- provider mutations are read-only until the current phase authorizes that exact authority;
- non-semantic repair covers recap, reciprocal links, verified checkpoints, and timed-out writes;
- semantic drift covers product assignment, approved content, human status, duplicate authority,
  and requires a stop.

- [ ] **Step 6: Re-run tests and commit**

Run:

```bash
python3 -m unittest tests.test_provider_contracts -v
git diff --check
```

Commit:

```bash
git add scripts/workspace_core tests/test_provider_contracts.py plugins/elephant/references/workspace/provider-contracts.md
git commit -m "feat: define provider capability contracts"
```

### Task 4: Human and Machine Story State Model

**Files:**
- Create: `scripts/workspace_core/states.py`
- Modify: `scripts/workspace_core/__init__.py`
- Create: `tests/test_story_state_model.py`
- Create: `plugins/elephant/references/workspace/story-state-model.md`

**Interfaces:**
- Produces: `HumanStatus`, `ProductDisposition`, `CheckpointPhase`, `DriftKind`, `RepairAction`.
- Produces: `can_transition_human_status()`, `terminal_status_for_disposition()`, `repair_action()`.

- [ ] **Step 1: Write failing story-state tests**

Create `tests/test_story_state_model.py`:

```python
import unittest

from scripts.workspace_core import (
    DriftKind,
    HumanStatus,
    ProductDisposition,
    RepairAction,
    can_transition_human_status,
    repair_action,
    terminal_status_for_disposition,
)


class StoryStateModelTests(unittest.TestCase):
    def test_normal_human_delivery_flow(self):
        path = (
            HumanStatus.BACKLOG,
            HumanStatus.SHAPING,
            HumanStatus.READY,
            HumanStatus.IN_PROGRESS,
            HumanStatus.DONE,
        )
        for current, target in zip(path, path[1:]):
            self.assertTrue(can_transition_human_status(current, target))

    def test_product_decision_return_goes_back_to_shaping(self):
        self.assertTrue(
            can_transition_human_status(HumanStatus.IN_PROGRESS, HumanStatus.SHAPING)
        )

    def test_dispositions_map_to_human_status(self):
        self.assertEqual(
            terminal_status_for_disposition(ProductDisposition.DEFERRED),
            HumanStatus.BACKLOG,
        )
        self.assertEqual(
            terminal_status_for_disposition(ProductDisposition.SPLIT),
            HumanStatus.CANCELED,
        )
        self.assertEqual(
            terminal_status_for_disposition(ProductDisposition.REJECTED),
            HumanStatus.CANCELED,
        )

    def test_nonsemantic_projection_repairs_automatically(self):
        self.assertEqual(repair_action(DriftKind.STALE_RECAP), RepairAction.AUTO_REPAIR)
        self.assertEqual(repair_action(DriftKind.MISSING_RECIPROCAL_LINK), RepairAction.AUTO_REPAIR)

    def test_semantic_drift_stops(self):
        self.assertEqual(repair_action(DriftKind.APPROVED_CONTRACT_CHANGED), RepairAction.STOP)
        self.assertEqual(repair_action(DriftKind.PRODUCT_ASSIGNMENT_CHANGED), RepairAction.STOP)
```

- [ ] **Step 2: Run the state tests and verify the import fails**

Run:

```bash
python3 -m unittest tests.test_story_state_model -v
```

Expected: `ImportError` because state symbols do not exist.

- [ ] **Step 3: Implement the explicit state model**

Create `scripts/workspace_core/states.py` with string enums for:

```python
HumanStatus = Backlog | Shaping | Ready | In Progress | Done | Canceled
ProductDisposition = approved | split | deferred | rejected
CheckpointPhase = contract_pending | shaping | ready | technical | implementing | conformance | closeout | done | needs_product_decision
DriftKind = stale_recap | missing_reciprocal_link | verified_checkpoint_lag | timed_out_write | approved_contract_changed | product_assignment_changed | human_status_advanced | duplicate_authority
RepairAction = auto_repair | stop
```

Use explicit lookup tables, not ordinal enum comparisons. Allow only:

- Backlog → Shaping;
- Shaping → Ready, Backlog, or Canceled;
- Ready → In Progress, Shaping, Backlog, or Canceled;
- In Progress → Shaping, Done, or Canceled;
- no transition out of Done or Canceled in the normal delivery model.

Map deferred to Backlog, split/rejected to Canceled, and approved to Ready. Map the first four
drift kinds to automatic repair and the last four to stop. Export every public symbol.

- [ ] **Step 4: Run state tests and verify they pass**

Run:

```bash
python3 -m unittest tests.test_story_state_model -v
```

Expected: all tests pass.

- [ ] **Step 5: Write the canonical state reference**

Create `plugins/elephant/references/workspace/story-state-model.md` with:

- the compact Linear human flow;
- the full checkpoint phase vocabulary;
- transition tables matching `states.py` exactly;
- disposition behavior including child creation for split and reconsideration condition for
  deferred;
- the rule that `needs_product_decision` returns the human issue to Shaping;
- the automatic-repair versus stop table;
- the rule that human status cannot prove a machine checkpoint and machine checkpoint cannot
  replace human delivery state.

- [ ] **Step 6: Re-run tests and commit**

Run:

```bash
python3 -m unittest tests.test_story_state_model -v
git diff --check
```

Commit:

```bash
git add scripts/workspace_core tests/test_story_state_model.py plugins/elephant/references/workspace/story-state-model.md
git commit -m "feat: define story state model"
```

### Task 5: Compatibility Validator Wiring and Phase-1 Verification

**Files:**
- Modify: `scripts/validate-compatibility.py`
- Modify: `tests/test_compatibility.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: all four canonical references and Python test oracles from Tasks 1–4.
- Produces: static failure when any v3 core asset or required vocabulary disappears.

- [ ] **Step 1: Add failing packaging-behavior tests**

Append a `WorkspaceCorePackagingTests` class to `tests/test_compatibility.py`. Asset existence is a
real packaging boundary, so test it directly. Do not assert prose phrases from the references.

```python
class WorkspaceCorePackagingTests(unittest.TestCase):
    ASSETS = (
        "workspace/workspace-schema.md",
        "workspace/profile-schema.md",
        "workspace/provider-contracts.md",
        "workspace/story-state-model.md",
    )

    def test_workspace_core_assets_are_packaged(self):
        root = ROOT / "plugins/elephant/references"
        for relative in self.ASSETS:
            self.assertTrue((root / relative).is_file(), relative)

    def test_missing_workspace_core_asset_is_reported(self):
        validator = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            references = root / "plugins/elephant/references"
            for relative in self.ASSETS[:-1]:
                path = references / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")
            errors = validator.validate_repository(root)
            self.assertIn(
                "missing v3 workspace core asset: "
                "plugins/elephant/references/workspace/story-state-model.md",
                errors,
            )
```

- [ ] **Step 2: Run the static contract test and verify the validator does not yet enforce it**

Run:

```bash
python3 -m unittest tests.test_compatibility.WorkspaceCorePackagingTests -v
```

Expected: `test_workspace_core_assets_are_packaged` passes and
`test_missing_workspace_core_asset_is_reported` fails because the validator does not yet report
missing v3 reference assets.

- [ ] **Step 3: Wire v3 assets into the compatibility validator**

Add:

```python
REQUIRED_V3_CORE_ASSETS = (
    "workspace/workspace-schema.md",
    "workspace/profile-schema.md",
    "workspace/provider-contracts.md",
    "workspace/story-state-model.md",
)
```

to `scripts/validate-compatibility.py`. Add:

```python
def _validate_v3_core_assets(root: Path, errors: list[str]) -> None:
    references_root = root / PLUGIN / "references"
    for relative in REQUIRED_V3_CORE_ASSETS:
        path = references_root / relative
        if not path.is_file():
            errors.append(f"missing v3 workspace core asset: {path.relative_to(root)}")
```

Call `_validate_v3_core_assets(root, errors)` next to the existing `_validate_v2_assets()` call.
Keep all active v2 checks because phase 1 is additive.

- [ ] **Step 4: Document the additive phase-1 status**

Add a concise `Workspace v3 development` section to `README.md` stating:

- the approved design and phase-1 core references exist;
- the active shipping runtime remains v2 until the coordinated Maio cutover;
- the project is not dual-writing or translating artifacts;
- future phases consume the new references.

Do not advertise `setup-workspace`, external providers, or v3 `ship-story` as usable yet.

- [ ] **Step 5: Run the complete verification suite**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate-compatibility.py
uv run --with pyyaml python /Users/aki/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/elephant
git diff --check
```

Expected:

- every unit test passes;
- compatibility validation prints `Elephant compatibility validation passed.`;
- plugin validation reports success;
- `git diff --check` emits no output.

- [ ] **Step 6: Review the phase-1 diff against the design**

Confirm from the diff that:

- current `init-profile` and `ship-story` files are unchanged;
- no runtime dispatch references the v3 contracts yet;
- no old-to-new converter or dual writer exists;
- the four provider choices and four diagnostics match the design exactly;
- workspace config contains no story-level storage;
- product and engineering routing remain independent.

- [ ] **Step 7: Commit the validator and documentation wiring**

```bash
git add scripts/validate-compatibility.py tests/test_compatibility.py README.md
git commit -m "test: validate workspace core contracts"
```

## Phase-1 Completion Gate

Phase 1 is complete only when:

- all five task commits exist;
- the complete test, compatibility, and plugin-validation commands pass with fresh output;
- a focused code review finds no design-spec mismatch or unnecessary compatibility work;
- `git status --short` is clean;
- the branch contains no changes to the active v2 dispatch path.

After this gate, write a separate implementation plan for phase 2, `elephant:setup-workspace`,
using these exact core interfaces. Do not extend this plan with phase-2 provisioning behavior.

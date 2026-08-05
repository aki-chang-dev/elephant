# Linear Provider Implementation Plan

> **Status: superseded.** Do not continue this plan. Its product assumptions were replaced by
> [`2026-08-05-one-person-company-information-coordination-product.md`](../specs/2026-08-05-one-person-company-information-coordination-product.md).
> Existing Phase 3 implementation must be audited against the approved Product Contract before
> any further work.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and sandbox-certify Elephant's provider-neutral Linear story provider for issues, human status, product/kind labels, hierarchy and relations, Product Recap, Product Contract binding, attachment checkpoints, delivery evidence, and GitHub binding.

**Architecture:** Add one canonical `elephant_runtime.linear` package inside the installed plugin. The package owns immutable provider values, exact connector-capability classification, strict normalization, story operations, and transcript verification behind an injected `LinearConnector` port; Claude Code and Codex remain the host executors that invoke MCP/connector tools according to the packaged reference. The provider uses exact read-back and stable Elephant markers for replay, never treats tool presence as permission, and never silently substitutes Git or another provider.

**Tech Stack:** Python 3 standard library, frozen dataclasses, existing `elephant_runtime.workspace_core` state/capability contracts, Linear connector tools, `unittest`, plugin/skill validators.

## Global Constraints

- Linear is authoritative for story identity/title, human delivery state, priority, project membership, hierarchy, issue relations, dispositions, Product Recap, Product Contract binding, machine checkpoint, branch/PR/merge/verification, and delivery evidence.
- Linear issues contain only a concise derived Product Recap; a full Product Contract, Technical Contract, or implementation plan must never be copied into an issue.
- Human status is exactly `Backlog`, `Shaping`, `Ready`, `In Progress`, `Done`, or `Canceled`. `needs_product_decision` returns to `Shaping`.
- Product-facing issues have exactly one product label from the configured `Product` group and one `product-facing` kind label from the configured `Kind` group. Engineering-only issues have the configured `engineering-only` kind label and no product label.
- Selected-provider behavior is strict. No Git fallback, local story registry, dual writer, converter, or legacy mixed-spec path may be added.
- Every external mutation follows `preflight → exact stable-key lookup → one mutation → exact read-back → checkpoint`; a timeout is resolved by read-back, not blind retry.
- Duplicate stable keys, changed team/product/kind authority, invalid status advancement, or contradictory delivery evidence stop. They are never auto-merged.
- Connector diagnostics remain exactly `platform_unsupported`, `connector_capability_missing`, `permission_missing`, or `configuration_missing`.
- Tool availability is not permission evidence. The provider classifies authorization only from an actual call result and never logs OAuth tokens, signed upload URLs, attachment bytes, or private connector payloads.
- Current connector limitations are explicit: it exposes no team/status creation, issue deletion, or direct workspace UUID lookup. Phase 3 must not emulate those capabilities or claim disposable issue deletion.
- The first release reconciles only at workflow boundaries. It adds no daemon, webhook receiver, background polling, offline queue, or automatic conflict merge.
- Concrete Maio topology and product mappings remain Phase 7. No Maio team/status/label/project UUID is a production constant in the generic provider.
- Active v2 skills/runtime remain untouched until the coordinated Phase 9 cutover.
- External sandbox writes use a unique `elephant-sandbox/<uuid>` marker. Reversible fields, relations, comments, and attachments are restored/deleted; a created sandbox issue is moved to `Canceled` and retained as certification evidence because the connector exposes no issue deletion.
- The canonical runtime lives only under `plugins/elephant/elephant_runtime/`; checkout compatibility code may forward but must not duplicate implementation.

## Verified Connector Baseline (2026-08-04)

Read-only inventory proved one accessible team, standard workflow states, issue labels, issue reads, and no visible projects or diffs. The generic implementation must use configured IDs rather than the observed Maio values.

| Provider behavior | Required connector operations | Baseline |
|---|---|---|
| Discover team/status/labels/issues | `linear_list_teams`, `linear_get_team`, `linear_list_issue_statuses`, `linear_list_issue_labels`, `linear_list_issues`, `linear_get_issue` | Exposed and read-authorized |
| Create/update story, status, labels, hierarchy, relations, links | `linear_save_issue` plus exact `linear_get_issue(includeRelations=true)` | Exposed; write permission must be sandbox-proved |
| Product/delivery comments | `linear_list_comments`, `linear_save_comment`, `linear_delete_comment` | Exposed; write permission must be sandbox-proved |
| Attachment checkpoint | `linear_prepare_attachment_upload`, raw signed PUT, `linear_create_attachment_from_upload`, `linear_get_attachment`, `linear_delete_attachment` | Exposed; upload permission must be sandbox-proved |
| GitHub binding/read-back | issue link attachment plus `linear_get_diff`/`linear_list_diffs` | Tools exposed; current workspace has no visible diff, so configuration must be classified independently |
| Create team or workflow status | No connector operation | `connector_capability_missing`; exact one-time manual handoff and read-back only |
| Delete issue | No connector operation | `connector_capability_missing`; sandbox issue cleanup is `Canceled`, never falsely reported deleted |
| Direct workspace UUID | No connector operation | Do not invent an ID; setup records a verified workspace locator separately from team UUID |

Official behavior used by this plan:

- teams own issues and team-specific workflows;
- statuses are team-specific and have fixed categories;
- issue relations include blocking, blocked-by, related, and duplicate;
- issue-label groups are one level deep and mutually exclusive;
- attachment URL + issue identity is idempotent in Linear's API;
- GitHub linking is driven by issue identifiers/PR links and requires workspace integration configuration;
- connector/API calls are rate-limited, so provider reads are exact and paginated rather than polling.

---

## File Map

| Path | Responsibility |
|---|---|
| `plugins/elephant/elephant_runtime/linear/models.py` | Frozen normalized Linear values, requests, receipts, checkpoints, drift observations |
| `plugins/elephant/elephant_runtime/linear/capabilities.py` | Exact tool vocabulary and four-layer capability classification |
| `plugins/elephant/elephant_runtime/linear/connector.py` | Injected connector port and safe call/result envelope |
| `plugins/elephant/elephant_runtime/linear/normalize.py` | Strict raw response normalization and pagination/duplicate validation |
| `plugins/elephant/elephant_runtime/linear/provider.py` | Story, status, recap, hierarchy, relation, and contract-link operations |
| `plugins/elephant/elephant_runtime/linear/checkpoint.py` | Canonical checkpoint attachment and delivery-evidence lifecycle |
| `plugins/elephant/elephant_runtime/linear/sandbox.py` | Deterministic certification transcript schema and cleanup verification |
| `plugins/elephant/elephant_runtime/linear/__init__.py` | Exact public provider exports |
| `plugins/elephant/references/providers/linear.md` | Claude/Codex connector execution protocol and manual handoffs |
| `scripts/validate-linear-provider.py` | Validate capability/sandbox transcript without secrets or network calls |
| `tests/test_linear_*.py` | Contract, normalization, failpoint, packaging, and transcript regressions |
| `docs/testing/linear-provider-sandbox.md` | Tracked redacted connector inventory and real sandbox evidence |

### Task 1: Immutable Linear contract and exact capability inventory

**Files:**
- Create: `plugins/elephant/elephant_runtime/linear/models.py`
- Create: `plugins/elephant/elephant_runtime/linear/capabilities.py`
- Create: `plugins/elephant/elephant_runtime/linear/connector.py`
- Create: `plugins/elephant/elephant_runtime/linear/__init__.py`
- Create: `tests/test_linear_capabilities.py`
- Modify: `tests/test_setup_models.py`

**Interfaces:**
- Consumes: `ProviderKind.STORY`, `DiagnosticCode`, `HumanStatus`, `ProductDisposition`, `CheckpointPhase`, and `DriftKind` from `elephant_runtime.workspace_core`.
- Produces: `LinearTool`, `LinearConnector`, `LinearCapabilityInventory`, `LinearProviderDiagnostic`, `StoryKey`, `StorySnapshot`, `StoryCreateRequest`, `ProductRecap`, `ContractBinding`, `DeliveryEvidence`, and `LinearProviderError`.

- [ ] **Step 1: Write failing frozen-value and tool-vocabulary tests**

Add tests asserting:

```python
self.assertEqual(
    LinearTool.SAVE_ISSUE.value,
    "mcp__codex_apps__linear_save_issue",
)
self.assertEqual(
    StoryKey("repo", "intent").marker,
    "elephant-story/v1/232c7752e52990b58e5b1b43ceeb48e2c83aa4fc0eb6b610fe6d6a29bf7c38a4",
)
self.assertRaises(ValueError, StoryKey, "", "intent")
self.assertRaises(FrozenInstanceError, setattr, snapshot, "title", "changed")
```

The expected marker is the lowercase SHA-256 of canonical JSON `{"intent_id":"intent","repository_id":"repo"}` prefixed by `elephant-story/v1/`.

- [ ] **Step 2: Run the Task 1 tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_linear_capabilities -v`

Expected: import failure for the absent `elephant_runtime.linear` package.

- [ ] **Step 3: Implement frozen values and the connector port**

Define:

```python
class LinearConnector(Protocol):
    def call(
        self,
        tool: LinearTool,
        arguments: tuple[tuple[str, object], ...],
    ) -> Mapping[str, object]: ...

@dataclass(frozen=True)
class LinearCapabilityInventory:
    platform_supported: frozenset[str]
    exposed: frozenset[str]
    permitted: frozenset[str]
    configured: frozenset[str]

@dataclass(frozen=True)
class LinearProviderDiagnostic:
    capability: str
    code: DiagnosticCode
    blocking: bool
    instructions: tuple[str, ...] = ()
```

`LinearConnector.call()` receives immutable key/value pairs so tests and transcript validation preserve exact arguments. `LinearProviderError` carries `capability`, `tool`, `diagnostic_code`, `operation_key`, and verified prior receipts, but never includes a raw signed URL or token.

- [ ] **Step 4: Implement the runtime capability matrix**

Map every `STORY_RUNTIME_CAPABILITIES` value to exact tools. Require both read-back and mutation tools for mutation capabilities. Classify the first missing layer in platform → exposed → permission → configuration order. Add separate administrative capabilities for team/status creation, workspace locator, product/kind labels, checkpoint upload, and native GitHub diff verification.

The matrix must classify absent team/status creation as `connector_capability_missing`, absent configured status/label IDs as `configuration_missing`, and an actual authorization error from an exposed call as `permission_missing`.

- [ ] **Step 5: Run focused and existing provider tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_linear_capabilities tests.test_provider_contracts tests.test_setup_models -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add plugins/elephant/elephant_runtime/linear tests/test_linear_capabilities.py tests/test_setup_models.py
git commit -m "feat: define linear provider contract"
```

### Task 2: Strict connector response normalization and drift evidence

**Files:**
- Create: `plugins/elephant/elephant_runtime/linear/normalize.py`
- Create: `tests/test_linear_normalize.py`
- Modify: `plugins/elephant/elephant_runtime/linear/models.py`

**Interfaces:**
- Consumes: raw mapping results returned by `LinearConnector.call()`.
- Produces: `LinearTeam`, `LinearStatus`, `LinearLabel`, `LinearIssue`, `LinearRelation`, `LinearAttachment`, `LinearComment`, `LinearDiff`, `PageCursor`, and `LinearDrift`.

- [ ] **Step 1: Write failing table-driven normalization tests**

Cover real connector response shapes for team, user/team membership, statuses, labels, issue with attachments/state history/relations, comments, and diffs. Each type rejects missing or blank opaque IDs, wrong collection shapes, duplicate IDs, duplicate stable markers, and cursor loops.

Add an issue test with the exact footer:

```text
---
Elephant story key: `elephant-story/v1/<64 lowercase hex>`
Elephant recap SHA-256: `<64 lowercase hex>`
```

and assert the parser distinguishes no marker, one valid marker, malformed marker, and two markers.

- [ ] **Step 2: Run normalization tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_linear_normalize -v`

Expected: import failure for `elephant_runtime.linear.normalize`.

- [ ] **Step 3: Implement exact normalizers**

Normalizers accept only mappings/lists and return frozen values. They preserve opaque IDs and URLs without rewriting. Pagination rejects a repeated cursor. `normalize_issue(..., include_relations=True)` requires the `relations` object; a provider operation that needs relations may not accept a truncated list result.

- [ ] **Step 4: Implement stable marker and drift classification**

Classify:

- zero exact markers as missing authority;
- more than one matching issue as `duplicate_authority`;
- changed configured team/product/kind as `product_assignment_changed`;
- status beyond verified evidence as `human_status_advanced`;
- stale recap/checkpoint/reciprocal link as the corresponding repairable drift;
- changed authoritative story key as a stop.

- [ ] **Step 5: Run Task 2 and workspace-core tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_linear_normalize tests.test_story_state_model -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add plugins/elephant/elephant_runtime/linear/models.py plugins/elephant/elephant_runtime/linear/normalize.py tests/test_linear_normalize.py
git commit -m "feat: normalize linear provider evidence"
```

### Task 3: Issue, human-status, label, hierarchy, and relation operations

**Files:**
- Create: `plugins/elephant/elephant_runtime/linear/provider.py`
- Create: `tests/test_linear_provider.py`
- Modify: `plugins/elephant/elephant_runtime/linear/__init__.py`

**Interfaces:**
- Consumes: `LinearConnector`, configured team/status/label IDs, and Task 2 normalized evidence.
- Produces: `LinearStoryProvider.create_story()`, `read_story()`, `update_human_status()`, `create_child_story()`, `link_relation()`, and `apply_disposition()`.

- [ ] **Step 1: Write failing create/read replay tests**

The fake connector records exact calls and injects failure after every mutation. Assert:

1. `create_story()` searches the configured team for the exact `StoryKey.marker` before mutation.
2. Zero matches calls `SAVE_ISSUE` once, then `GET_ISSUE` and exact lookup again.
3. One exact match is reused after semantic verification.
4. Two matches stop without another mutation.
5. A timeout after save is resumed by lookup/read-back and does not create a second issue.

The first release is serialized, but a concurrent duplicate detected after read-back must stop with `duplicate_authority`; it must not select, merge, cancel, or delete either issue.

- [ ] **Step 2: Run the create/read tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_linear_provider.LinearIssueLifecycleTests -v`

Expected: import failure for `LinearStoryProvider`.

- [ ] **Step 3: Implement create/read with one canonical issue body**

`StoryCreateRequest` requires team ID, title, story kind, product label ID or `None`, kind label ID, priority, optional project/parent, and explicit `StoryKey`. The description initially contains a concise one-line recap plus the exact marker footer. Do not place the idea discussion, Product Contract, Technical Contract, plan, checkpoint JSON, or internal implementation progress in the issue body.

- [ ] **Step 4: Write RED tests for status and label authority**

Configure exact status IDs for all six `HumanStatus` values and assert their names/types are read back before mutation. `Shaping` and `Ready` are `unstarted`; `In Progress` is `started`; `Done` is `completed`; `Canceled` is `canceled`; `Backlog` is `backlog`.

Assert product-facing creation has exactly one configured product-group label and the product-facing kind label. Engineering-only creation has only the engineering kind label. Any changed team/product/kind stops.

- [ ] **Step 5: Implement status, disposition, child, and relation methods**

Use `can_transition_human_status()` and `terminal_status_for_disposition()` before `SAVE_ISSUE`. Use `parentId`, `blockedBy`, `blocks`, `relatedTo`, `removeBlockedBy`, `removeBlocks`, `removeRelatedTo`, and `duplicateOf` exactly as exposed. Every call reads the issue back with relations and verifies the reciprocal view. `split` creates explicitly keyed child stories before canceling the original. `deferred` records its reconsideration condition and returns to Backlog. `rejected` records the product disposition and enters Canceled.

- [ ] **Step 6: Add failpoint and drift regressions**

Interrupt after save and before read-back for status, labels, parent, and every relation type. Resume must either verify the intended state or stop on contradictory state; it never repeats an append-only relation blindly.

- [ ] **Step 7: Run Task 3 tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_linear_provider tests.test_story_state_model -v`

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

```bash
git add plugins/elephant/elephant_runtime/linear/provider.py plugins/elephant/elephant_runtime/linear/__init__.py tests/test_linear_provider.py
git commit -m "feat: implement linear story lifecycle"
```

### Task 4: Product Recap, Product Contract binding, checkpoint, delivery evidence, and GitHub binding

**Files:**
- Create: `plugins/elephant/elephant_runtime/linear/checkpoint.py`
- Create: `tests/test_linear_checkpoint.py`
- Modify: `plugins/elephant/elephant_runtime/linear/provider.py`
- Modify: `plugins/elephant/elephant_runtime/linear/models.py`
- Modify: `plugins/elephant/elephant_runtime/linear/__init__.py`

**Interfaces:**
- Consumes: a verified `StorySnapshot`, Product Contract page ID/URL/fingerprint, branch/PR/merge/verification facts, and attachment/comment connector operations.
- Produces: `write_product_recap()`, `bind_product_contract()`, `read_checkpoint()`, `write_checkpoint()`, `attach_delivery_evidence()`, and `verify_github_binding()`.

- [ ] **Step 1: Write failing canonical Product Recap tests**

The exact issue description owned by Elephant is:

```markdown
## Product Recap

**Problem:** <one concise paragraph>

**Outcome:** <one concise paragraph>

**Acceptance:**

- <observable acceptance summary>

**Product Contract:** [Open in Notion](<https://www.notion.so/...>)

---
Elephant story key: `elephant-story/v1/<sha256>`
Elephant recap SHA-256: `<sha256 of canonical recap fields>`
```

Tests reject a full contract, technical plan, implementation checklist, checkpoint JSON, or internal progress section. Engineering-only recap replaces the Product Contract line with `**Behavior preservation:** <summary>`.

- [ ] **Step 2: Run recap tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_linear_checkpoint.LinearProductRecapTests -v`

Expected: missing recap implementation.

- [ ] **Step 3: Implement recap and contract-link read-back**

`write_product_recap()` updates only after the current marker/team/product/kind are reverified. `bind_product_contract()` appends one link attachment titled `Elephant Product Contract` and verifies the exact URL in `GET_ISSUE.attachments`; a different existing URL is semantic drift, not an append opportunity.

- [ ] **Step 4: Write failing checkpoint attachment tests**

Define canonical JSON:

```json
{
  "schema": "elephant.linear-checkpoint/v1",
  "story_key": "elephant-story/v1/<sha256>",
  "issue_id": "<opaque id>",
  "phase": "<CheckpointPhase value>",
  "sequence": 1,
  "contract": {"page_id": "<opaque id>", "fingerprint": "<sha256>"},
  "delivery": {"branch": null, "pull_request_url": null, "merge_commit": null, "verification_sha256": null},
  "previous_sha256": null
}
```

The filename is `elephant-checkpoint-<story-key-sha256>-<sequence>.json`. Test canonical bytes, digest, schema rejection, issue/key mismatch, duplicate active attachments, changed approved-contract fingerprint, timed-out upload, read-back, and prior-attachment cleanup.

- [ ] **Step 5: Implement attachment checkpoint lifecycle**

The connector flow is prepare upload → raw byte PUT by the host → finalize attachment → get attachment/read bytes → recompute digest → get issue/read attachment row. A newer verified checkpoint is authoritative only after exact read-back. Delete only the exact prior Elephant checkpoint attachment after the new one is verified. A failure leaves both as contextual evidence and resume resolves sequence/digest; it never deletes an unverified attachment.

- [ ] **Step 6: Write and implement delivery-evidence/GitHub tests**

Delivery evidence uses one marker-owned comment plus link attachments for branch/PR/verification. Update an existing exact marker comment by ID; more than one stops. `verify_github_binding()` first verifies the PR URL attachment and, when native diff verification is configured, requires `GET_DIFF` to resolve the same PR and issue identifier. Tool absence is `connector_capability_missing`; exposed tool with no workspace integration/diff is `configuration_missing`; neither case falls back to Git state as Linear evidence.

- [ ] **Step 7: Run Task 4 tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_linear_checkpoint tests.test_linear_provider -v`

Expected: PASS.

- [ ] **Step 8: Commit Task 4**

```bash
git add plugins/elephant/elephant_runtime/linear tests/test_linear_checkpoint.py tests/test_linear_provider.py
git commit -m "feat: persist linear story evidence"
```

### Task 5: Setup discovery, host execution protocol, packaging, and cold start

**Files:**
- Create: `plugins/elephant/references/providers/linear.md`
- Create: `scripts/validate-linear-provider.py`
- Create: `tests/test_linear_packaging.py`
- Modify: `plugins/elephant/skills/setup-workspace/SKILL.md`
- Modify: `plugins/elephant/references/workspace/setup-workspace.md`
- Modify: `scripts/validate-compatibility.py`
- Modify: `tests/test_compatibility.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: Tasks 1–4 public provider API and current `setup-workspace` approval protocol.
- Produces: one installed reference for host tool execution, transcript validator, setup capability projection, and cold-start discoverability.

- [ ] **Step 1: Write failing installed-artifact and cold-start tests**

Copy only the marketplace plugin source into a temporary directory under `python -I`. Assert `elephant_runtime.linear` imports, exact public exports exist, no checkout `scripts/` module is imported, and the provider reference names every required connector tool exactly.

- [ ] **Step 2: Run packaging tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_linear_packaging -v`

Expected: missing reference/validator/package exports.

- [ ] **Step 3: Write the Linear host protocol**

The reference must specify:

- read-first exact calls and pagination;
- the immutable stable marker and canonical recap/checkpoint formats;
- mutation/read-back order for each provider method;
- attachment upload secrecy and checksum handling;
- failure classification without parsing English error prose when a structured code exists;
- no repeated append-only relation/link on uncertain outcomes;
- exact one-time manual instructions for missing `Shaping`/`Ready` states or administrative team/status setup;
- sandbox cleanup semantics and the retained Canceled certification issue;
- current connector limitations, including absent issue deletion and workspace UUID lookup.

- [ ] **Step 4: Integrate setup discovery and diagnostics**

`setup-workspace` inventories exact tool names and reads teams/statuses/labels before proposing a Linear binding. It records a verified workspace locator separately from team UUID and never invents a UUID. Missing exact human statuses or product/kind labels are `configuration_missing` when read capability exists; unavailable creation tools produce an actionable nonblocking administrative `connector_capability_missing` handoff, followed by exact list/get read-back on resume.

Do not weaken the Phase 2 `SetupAdapter` atomicity or disposable-cleanup contract. The Linear story provider is certified here; any future Linear setup mutation adapter must independently satisfy that contract rather than wrapping search-then-create and calling it atomic.

- [ ] **Step 5: Implement the transcript validator**

`validate-linear-provider.py` accepts a redacted JSON transcript, validates schema/tool names/call order/read-back/digests/cleanup, and rejects token/signed-URL/base64 fields. It performs no network calls. Add tests for mutation before lookup, missing read-back, duplicate authority, missing cleanup, secret-bearing fields, and mismatched attachment SHA-256.

- [ ] **Step 6: Update compatibility and README boundary**

README states Phase 3 code is provider-certified only after the tracked sandbox transcript passes; v3 `ship-story` remains inactive until Phase 5. Compatibility validation requires the canonical package/reference/validator/tests and forbids active v2 imports from the new provider.

- [ ] **Step 7: Run Task 5 validation**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_linear_packaging tests.test_compatibility -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate-compatibility.py
uv run --with pyyaml python /Users/aki/.codex/skills/.system/skill-creator/scripts/quick_validate.py plugins/elephant/skills/setup-workspace
PYTHONDONTWRITEBYTECODE=1 uv run --with pyyaml python /Users/aki/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/elephant
```

Expected: all commands pass.

- [ ] **Step 8: Commit Task 5**

```bash
git add plugins/elephant/references/providers/linear.md plugins/elephant/skills/setup-workspace/SKILL.md plugins/elephant/references/workspace/setup-workspace.md scripts/validate-linear-provider.py scripts/validate-compatibility.py tests/test_linear_packaging.py tests/test_compatibility.py README.md
git commit -m "feat: package linear provider protocol"
```

### Task 6: Real Linear sandbox certification and cleanup evidence

**Files:**
- Create: `plugins/elephant/elephant_runtime/linear/sandbox.py`
- Create: `tests/test_linear_sandbox.py`
- Create: `docs/testing/linear-provider-sandbox.md`
- Modify: `plugins/elephant/elephant_runtime/linear/__init__.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: a fresh unique sandbox marker, configured sandbox team/status IDs, two preauthorized relation-test issues or one retained sandbox parent/child pair, and Tasks 1–5 provider/reference.
- Produces: redacted `elephant.linear-sandbox/v1` transcript, cleanup proof, capability verdict, and durable certification evidence.

- [ ] **Step 1: Write failing transcript and cleanup tests**

The transcript must prove:

1. read-only capability inventory before mutation;
2. exact-key absence before issue creation;
3. issue creation and read-back;
4. Todo/In Progress/Canceled status writes and restoration/final cancellation;
5. product/kind label read-back without changing unrelated labels;
6. parent/child and blocking/related relation add/read/remove;
7. Product Recap and contract-link read-back;
8. checkpoint attachment upload/get/delete with byte digest;
9. delivery comment create/read/update/delete;
10. PR-link attachment read-back and native GitHub diff result or exact `configuration_missing`;
11. final absence of sandbox relations/comments/checkpoint attachments;
12. retained sandbox issue is Canceled and visibly titled `[Elephant provider certification — cleaned]` because issue deletion is not exposed.

- [ ] **Step 2: Run sandbox tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_linear_sandbox -v`

Expected: missing transcript model/verifier.

- [ ] **Step 3: Implement transcript values and verifier**

`sandbox.py` validates exact operation ordering, object identity, semantic snapshots, relation reciprocity, attachment hashes, mutation ownership, and cleanup. It rejects timestamps as authority and accepts them only as evidence metadata.

- [ ] **Step 4: Execute the real sandbox protocol through the connected Linear tools**

Before the first mutation, record the team/issue targets and unique marker in the ignored SDD report. Use only connector tools named in the packaged reference. Do not mutate onboarding issue bodies/status/labels. If existing issues are used as relation anchors, capture their exact prior relations and restore them before proceeding.

Create one certification issue only after exact-key absence and read-back it after every mutation. Upload a tiny canonical checkpoint using prepare → direct raw PUT → finalize; never put signed URL or bytes in the tracked transcript. Remove the checkpoint, comment, PR link if disposable, and all relations. Move the certification issue to Canceled and rename it exactly `[Elephant provider certification — cleaned] <marker-suffix>`.

- [ ] **Step 5: Redact and validate the real transcript**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate-linear-provider.py .superpowers/sdd/2026-08-04-linear-provider/linear-sandbox-transcript.json`

Expected: `Linear provider sandbox certification passed.`

The tracked Markdown records tool capability names, redacted object IDs, semantic fingerprints, attachment SHA-256, cleanup result, exact diagnostics, and the validator output. It contains no OAuth data, signed URLs, private file bytes, or full connector responses.

- [ ] **Step 6: Run the complete Phase 3 verification matrix**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate-compatibility.py
uv run --with pyyaml python /Users/aki/.codex/skills/.system/skill-creator/scripts/quick_validate.py plugins/elephant/skills/setup-workspace
PYTHONDONTWRITEBYTECODE=1 uv run --with pyyaml python /Users/aki/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/elephant
PYTHONDONTWRITEBYTECODE=1 python3 -m compileall -q plugins/elephant/elephant_runtime scripts/validate-linear-provider.py
git diff --check 218a98015bc10ce0ff78693bd6abf3e44da0175b..HEAD
git status --short
```

Expected: all commands pass and tracked status is clean.

- [ ] **Step 7: Commit Task 6**

```bash
git add plugins/elephant/elephant_runtime/linear/sandbox.py plugins/elephant/elephant_runtime/linear/__init__.py tests/test_linear_sandbox.py docs/testing/linear-provider-sandbox.md README.md
git commit -m "test: certify linear provider sandbox"
```

## Plan Self-Review

- Spec coverage: issue, status, labels, hierarchy, relations, recap, contract link, checkpoint, delivery evidence, GitHub binding, diagnostics, failpoint resume, packaging, cold start, and sandbox cleanup each have an owning task.
- Scope boundary: Notion, `ship-story` v3 activation, Maio mappings/import, migration cleanup, webhooks, and legacy removal remain later phases.
- Connector realism: the plan distinguishes exposed tools, actual permission, required configuration, and unsupported administrative operations. It does not claim team/status creation, issue deletion, workspace UUID lookup, or visible GitHub diffs.
- Type consistency: Tasks 2–6 consume the Task 1 `LinearConnector`, immutable models, exact tools, and diagnostics; Tasks 3–4 expose the methods packaged in Task 5 and certified in Task 6.
- Safety: external mutation is delayed to Task 6, uses one unique marker, records prior state, verifies each write, removes reversible artifacts, and retains only a visibly cleaned Canceled certification issue.
- Placeholder scan: the plan contains no deferred implementation placeholder; named later-phase work is an explicit scope exclusion.

## Execution Choice

The owner previously authorized continuous execution of the phased program. Execute this plan with `superpowers:subagent-driven-development`; do not add another owner checkpoint between tasks. The only allowed stop conditions are an unresolved design conflict, unavailable required external authority, or an unsafe sandbox cleanup boundary.

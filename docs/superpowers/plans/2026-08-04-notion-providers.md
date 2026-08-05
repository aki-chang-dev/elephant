# Notion Providers Implementation Plan

> **Status: superseded.** Do not continue this plan. Its product assumptions were replaced by
> [`2026-08-05-one-person-company-information-coordination-product.md`](../specs/2026-08-05-one-person-company-information-coordination-product.md).
> The isolated Phase 4 branch must not be merged; salvage or deletion will be decided only after
> a new technical design is approved.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and sandbox-certify Elephant's provider-neutral Notion product-knowledge and Product Contract providers, including shared workspace databases, exact relations, shaping drafts, approval immutability, successor versions, canonical fingerprints, reciprocal Linear binding, setup provisioning, and tamper detection.

**Architecture:** Add one canonical `elephant_runtime.notion` package inside the installed plugin. The package owns immutable provider values, connector-capability classification, strict response normalization, database schema verification, canonical page fingerprinting, knowledge operations, contract operations, and certification transcripts behind an injected `NotionConnector` port. The runtime uses configured data-source and page IDs for exact reads; bounded queries are used only to resolve stable external keys and must reject zero-or-many authority where exactly one is required. Claude Code and Codex remain host executors following one packaged connector protocol.

**Tech Stack:** Python 3 standard library, frozen dataclasses, existing `elephant_runtime.workspace_core` contracts, Notion connector tools, `unittest`, plugin/skill validators.

**Approved design source:** [`../specs/2026-08-03-external-workspace-orchestration-design.md`](../specs/2026-08-03-external-workspace-orchestration-design.md), especially “Notion”, provider ports, setup, data flow, failure/resume/drift, and phased delivery. This plan refines that already-approved design and introduces no new product authority boundary.

## Global Constraints

- Notion is authoritative only for durable product knowledge and Product Contracts. Linear remains authoritative for story identity and delivery state; Git remains authoritative for executable facts and transient Technical Contracts/plans.
- The workspace uses exactly three shared databases: Products, Product Knowledge, and Product Contracts. Product pages expose linked filtered views rather than creating one schema or document tree per product.
- Runtime operations use configured data-source and page IDs. Search is discovery evidence, never authority. Query calls are bounded, parameterized, and rejected on duplicate stable keys.
- A Product Contract page contains the canonical product-only body. Full Product Contracts never move to Linear, and Technical Contracts or implementation plans never move to Notion.
- An approved contract is logically immutable. Its approval fingerprint is computed only from an exact read-back of semantic authority fields plus normalized page content. Any later mismatch is `approved_contract_changed` and stops delivery.
- A revision creates a new shaping page with the next version and a self-relation to its approved predecessor. The predecessor is never edited into the successor.
- Approval is one replayable transition: preflight, exact draft read, canonicalize, write approval properties, exact read-back, recompute, then expose the receipt. A timeout is resolved by read-back, never blind mutation replay.
- Knowledge entries have stable keys, kinds, product relations, current/superseded state, semantic content fingerprints, and optional entry relations. Superseding creates or binds an explicit successor; it does not erase history.
- Every external mutation follows `preflight → stable-key lookup or exact ID read → one mutation → exact read-back → verified receipt`.
- Duplicate authority, changed product/story binding, malformed relations, approved-page mutation, or a version fork stops. Missing reciprocal links may be repaired only when all authoritative IDs agree.
- Connector diagnostics remain exactly `platform_unsupported`, `connector_capability_missing`, `permission_missing`, or `configuration_missing`. Tool presence is not permission evidence.
- Query operations may be plan-limited. The provider exposes that as a capability fact and minimizes query use; it never substitutes semantic search or silently falls back to Git.
- The first release reconciles only at workflow boundaries. It adds no daemon, webhook receiver, polling loop, offline queue, or automatic content merge.
- Concrete Maio product mappings and import remain Phases 7–8. Active v2 delivery stays untouched until coordinated Phase 9 cutover.
- Sandbox objects use a unique `elephant-sandbox/<uuid>` marker. Only objects created by that exact run may be trashed or moved during cleanup, after exact ID/title/marker read-back. Cleanup evidence records whether each object was trashed, moved to a retained certification archive, or restored.
- Canonical runtime code lives only under `plugins/elephant/elephant_runtime/`; checkout helpers may forward but must not duplicate implementation.

## Verified Connector Baseline (2026-08-04)

`notion_fetch({id: "self"})` identified the connected Maio workspace and authenticated actor. The connector reports create/update/fetch/search/database/view tools available; data-source and view queries are available with plan limits. Neither tracked evidence nor generic code may embed the observed private workspace, user, or email values.

| Provider behavior | Required connector operations | Baseline |
|---|---|---|
| Workspace/user and exact page/database reads | `notion_fetch` | Exposed and read-authorized |
| Stable-key lookup | `query_data_sources` with parameterized SQL | Exposed with plan limit; runtime must minimize calls |
| Create shared databases and relations | `notion_create_database`, `notion_update_data_source`, `notion_fetch` | Exposed; write permission requires sandbox proof |
| Create/update knowledge or contract pages | `notion_create_pages`, `notion_update_page`, `notion_fetch` | Exposed; write permission requires sandbox proof |
| Product filtered views | `notion_create_view`, `notion_update_view`, view query/fetch | Exposed; setup verifies exact configuration when supported |
| Cleanup created data sources | `notion_update_data_source(in_trash=true)` | Exposed; exact run ownership required before use |
| Trash a regular page | No connector operation | `connector_capability_missing`; move only exact run-owned pages to a retained archive |

## Canonical Shared Schemas

Property names are part of the provider protocol and are validated exactly after database creation or discovery. External property IDs remain opaque and are read back into setup evidence.

### Products

| Property | Type | Authority |
|---|---|---|
| `Product` | title | Human-facing name |
| `Product Key` | rich text | Stable Elephant key; unique |
| `Linear Label ID` | rich text | Reciprocal workspace binding |
| `Repository Ref` | rich text | Workspace registry reference |
| `Lifecycle` | select: `Active`, `Archived` | Product availability |

### Product Knowledge

| Property | Type | Authority |
|---|---|---|
| `Title` | title | Human-facing title |
| `Knowledge Key` | rich text | Stable Elephant key; unique |
| `Kind` | select: `Overview`, `Object`, `Glossary`, `Rule`, `Decision` | Knowledge classification |
| `Products` | dual relation to Products | Product scope |
| `State` | select: `Current`, `Superseded` | Current-truth resolution |
| `Supersedes` | self relation | Version lineage |
| `Schema Version` | rich text | Canonical body schema |
| `Content Fingerprint` | rich text | Read-back semantic hash |

### Product Contracts

| Property | Type | Authority |
|---|---|---|
| `Contract` | title | Human-facing story contract title |
| `Contract Key` | rich text | Stable story/version key; unique |
| `Products` | dual relation to Products | Exactly one product |
| `Linear Issue ID` | rich text | Story identity |
| `Linear Issue URL` | URL | Reciprocal preview/link target |
| `Status` | select: `Shaping`, `Approved`, `Superseded`, `Deferred`, `Rejected` | Product disposition lifecycle |
| `Version` | number | Positive monotonic version |
| `Supersedes` | self relation | Zero for v1; exactly one predecessor for successors |
| `Approved At` | date | Approval evidence |
| `Approved By` | people | Approval actor evidence |
| `Approval Fingerprint` | rich text | Immutable semantic hash |
| `Schema Version` | rich text | Canonical Product Contract schema |
| `Active` | checkbox | Exactly one approved active contract per story |

## Canonical Fingerprint

The SHA-256 input is UTF-8 canonical JSON with sorted keys, compact separators, and no ASCII escaping. It includes the provider schema version, stable key, product page ID, Linear issue ID/URL for contracts, version and predecessor page ID, semantic status, and normalized fetched page content. It excludes Notion page URL, timestamps other than explicit approval evidence, last-edited metadata, property IDs, view state, and the fingerprint property itself.

Content normalization converts CRLF/CR to LF, strips trailing horizontal whitespace per line, removes only leading/trailing empty blocks introduced by transport, and preserves every other character and block order. Approval always fingerprints a fetched read-back, never the outbound Markdown string.

---

## File Map

| Path | Responsibility |
|---|---|
| `plugins/elephant/elephant_runtime/notion/models.py` | Frozen Notion values, requests, receipts, drift observations |
| `plugins/elephant/elephant_runtime/notion/capabilities.py` | Exact tool vocabulary and four-layer capability classification |
| `plugins/elephant/elephant_runtime/notion/connector.py` | Injected immutable connector port |
| `plugins/elephant/elephant_runtime/notion/normalize.py` | Strict host response, schema, property, relation, query, and page normalization |
| `plugins/elephant/elephant_runtime/notion/schema.py` | Canonical three-database schema and exact verification |
| `plugins/elephant/elephant_runtime/notion/fingerprint.py` | Canonical semantic page normalization and SHA-256 |
| `plugins/elephant/elephant_runtime/notion/setup_adapter.py` | Concrete workspace-setup discovery/provision/read-back adapter |
| `plugins/elephant/elephant_runtime/notion/contracts.py` | Draft, update, approval, successor, active resolution, binding verification |
| `plugins/elephant/elephant_runtime/notion/knowledge.py` | Knowledge CRUD, query, supersede, relations, context resolution |
| `plugins/elephant/elephant_runtime/notion/sandbox.py` | Certification transcript and cleanup verification |
| `plugins/elephant/elephant_runtime/notion/__init__.py` | Exact public provider exports |
| `plugins/elephant/references/providers/notion.md` | Claude/Codex connector execution and manual-handoff protocol |
| `scripts/validate-notion-provider.py` | Offline capability/sandbox transcript validator |
| `tests/test_notion_*.py` | Capability, normalization, schema, provider, failpoint, packaging, transcript tests |
| `docs/testing/notion-provider-sandbox.md` | Redacted real connector inventory and certification evidence |
| `docs/testing/notion-provider-sandbox.json` | Machine-validated redacted certification transcript |

### Task 1: Immutable Notion contract, host envelope, and capability inventory

**Files:** create `notion/{models,capabilities,connector,normalize,__init__}.py`; create `tests/test_notion_capabilities.py`, `tests/test_notion_normalize.py`; modify provider-contract tests only when the existing common port needs a Notion-specific invariant.

- [ ] Write failing tests for the exact tool vocabulary, frozen IDs/keys/snapshots, capability precedence, plan-limited query evidence, malformed connector content blocks, non-JSON text envelopes, blank/duplicate IDs, and redaction-safe errors.
- [ ] Run the focused tests and verify RED from the absent package.
- [ ] Implement `NotionTool`, `NotionConnector`, immutable provider values/errors, strict one-text-block JSON host decoding, and capability matrices for knowledge, contracts, setup, views, and sandbox cleanup.
- [ ] Require actual successful call evidence for permission. Keep “available with limit” separate from permission failure and surface it as a non-blocking inventory constraint.
- [ ] Run focused plus common provider tests and commit `feat: define notion provider contract`.

### Task 2: Canonical three-database schema and setup adapter

**Files:** create `notion/schema.py`, `notion/setup_adapter.py`, `tests/test_notion_schema.py`, `tests/test_notion_setup_adapter.py`; modify `workspace_setup` packaging/reference tests as required without changing its provider-neutral protocol.

- [ ] Write failing schema tests for exact properties/types/options, relation targets, self-relations, property-ID capture, compatible reuse, missing-property repair, incompatible drift, duplicate database authority, and forbidden destructive schema repair.
- [ ] Write failing setup-adapter tests for find/read/create/update/verify operations, stable setup keys, one-time view handoff classification, read-back receipts, timeouts, interruption resume, and exact-run cleanup ownership.
- [ ] Implement deterministic DDL builders and strict fetched-schema normalization. Existing compatible schemas are reused; additive omissions may be proposed/applied; rename/drop/type changes stop for manual resolution.
- [ ] Implement the concrete adapter over immutable connector calls. Database creation is search-before-create and is not falsely labeled atomic; any partial create is recovered only by unique stable title/marker plus exact schema read-back.
- [ ] Prove Products is created first, then add dual Product relations and self-relations after target data-source IDs exist. Create product-filtered views when exposed; otherwise emit an exact one-time handoff and verify it afterward.
- [ ] Run setup/provider regression tests and commit `feat: provision notion workspace schema`.

### Task 3: Canonical page content and semantic fingerprint

**Files:** create `notion/fingerprint.py`, `tests/test_notion_fingerprint.py`; add normalization fixtures representing real enhanced-Markdown fetches.

- [ ] Write failing table-driven tests for newline normalization, trailing whitespace, empty transport blocks, Unicode, links/mentions, nested lists, tables, callouts, code blocks, and content changes that must alter the hash.
- [ ] Assert outbound Markdown is never fingerprinted directly; only a normalized fetched snapshot may enter the hash function.
- [ ] Implement canonical JSON and domain-specific knowledge/contract fingerprint payloads. Reject missing authority fields, noncanonical IDs/URLs, invalid versions, circular/self lineage, and fingerprint strings outside lowercase SHA-256.
- [ ] Add tamper fixtures for body, product relation, Linear issue binding, version, predecessor, status, approver, and approval timestamp.
- [ ] Run focused tests and commit `feat: fingerprint notion authority pages`.

### Task 4: Product Contract provider and failpoint replay

**Files:** create `notion/contracts.py`, `tests/test_notion_contracts.py`, `tests/test_notion_contract_failpoints.py`.

- [ ] Write failing contract-suite tests for draft create/read/update, exact ten-section product-only body preservation, replay after create/update timeout, draft-only mutation, approval, active resolution, successor allocation, predecessor supersession, reciprocal Linear binding, and duplicate authority.
- [ ] Implement stable keys: a story authority key derived from repository ID + Linear issue ID, and `contract_key = <story authority>/v<positive integer>`. Query exact keys with parameterized SQL and reject zero-or-many where one is required.
- [ ] Implement draft writes as whole semantic-body replacement only while `Status=Shaping`, with exact precondition fingerprint and read-back. Never update an Approved/Superseded/Deferred/Rejected body.
- [ ] Implement approval as a replayable state transition. Store approval actor/time/fingerprint, assert exactly one product and story binding, then read back and recompute before returning a receipt.
- [ ] Implement successor creation without modifying the approved predecessor body. Only after successor approval mark the predecessor `Superseded`/inactive and expose the new active binding; failpoints between remote writes must resume without two active versions.
- [ ] Verify the Notion page contains the exact Linear issue URL and the supplied Linear snapshot contains the exact current Notion page URL. Missing reciprocal presentation is auto-repairable only when IDs agree; disagreement stops.
- [ ] Run contract/common/Linear binding regressions and commit `feat: manage notion product contracts`.

### Task 5: Product Knowledge provider and current-context resolution

**Files:** create `notion/knowledge.py`, `tests/test_notion_knowledge.py`, `tests/test_notion_knowledge_failpoints.py`.

- [ ] Write failing tests for create/read/update/query, all five kinds, one-or-many product relations, exact stable keys, relations between entries, supersede lineage, current-truth resolution, bounded product context, duplicate/conflicting current entries, and timeout replay.
- [ ] Implement draft/current knowledge updates with precondition fingerprints and exact read-back. Approved contract immutability rules must not leak into knowledge semantics; knowledge remains deliberately editable until superseded.
- [ ] Implement explicit supersession as successor-first, read-back, then predecessor state transition. Preserve history and reject forks or cycles.
- [ ] Implement shaping context queries that return only configured products and current entries, with deterministic ordering and a caller-supplied bound. Never use semantic search as the authority resolver.
- [ ] Run knowledge/common provider regressions and commit `feat: manage notion product knowledge`.

### Task 6: Host protocol, installed packaging, and offline transcript validation

**Files:** create `references/providers/notion.md`, `scripts/validate-notion-provider.py`, sandbox schema/tests, packaging and compatibility assertions; update README/setup references from “Notion later boundary” to the exact certified/not-yet-certified state appropriate before the real run.

- [ ] Write failing tests that a cold Codex/Claude host can discover exact tools, immutable arguments, async-task polling rules, enhanced-Markdown requirements, query limits, redaction rules, and response envelopes from installed plugin files alone.
- [ ] Define a deterministic redacted transcript schema containing workspace/user aliases, capability results, database/page aliases, operation/failpoint receipts, fingerprint chain, tamper evidence, cleanup disposition, and no content/secrets/private unrelated IDs.
- [ ] Implement the offline validator. It rejects missing read-back, duplicate aliases, impossible ordering, mismatched hashes, absent tamper stop, unowned cleanup, raw connector payloads, access tokens, emails, signed URLs, and incomplete final state.
- [ ] Run plugin/skill/compatibility/transcript tests and commit `feat: package notion provider protocol`.

### Task 7: Real Notion sandbox certification, review, integration, and cleanup

**Files:** update `docs/testing/notion-provider-sandbox.{md,json}`, README/reference certification status, and any real-shape normalization fixtures proven by the run.

- [ ] Preflight `fetch(self)` and exact tool access. Record aliases only; do not persist the authenticated email or raw workspace/user IDs in tracked evidence.
- [ ] Create one uniquely marked certification parent and three uniquely marked shared databases, or reuse an existing exact certification root only after marker/schema read-back. Capture actual property/data-source/relation response shapes.
- [ ] Exercise product creation, knowledge create/update/relation/supersede/query, contract draft/update/approve, reciprocal Linear URL verification, successor flow, and read-back at every boundary.
- [ ] Tamper only an exact run-owned approved contract, prove `approved_contract_changed`, then restore the exact approved snapshot and prove the original fingerprint again. Never tamper user-owned content.
- [ ] Exercise one safe injected timeout/resume path without blind duplicate creation.
- [ ] Clean up only exact run-owned objects: trash exact run-owned data sources where supported; move otherwise untrashable run-owned pages beneath the certification archive; restore any reused anchor. Read back every cleanup disposition.
- [ ] Update transcript/docs with redacted evidence, run the offline validator, focused tests, full suite, plugin/skill validators, and compatibility checks.
- [ ] Use `superpowers:requesting-code-review`, resolve findings with `superpowers:receiving-code-review`, then use `superpowers:verification-before-completion` and `superpowers:finishing-a-development-branch`.
- [ ] Merge to `main`, push, confirm remote head, and remove the worktree/feature branch. Do not start Phase 5 until Phase 4 is cleanly integrated.

## Phase 4 Acceptance Criteria

- Both Notion provider kinds pass their common runtime capability suites and provider-specific contract tests.
- Setup can create or reuse the exact three-database model, capture opaque IDs, configure relations/views where supported, and diagnose rather than emulate missing capabilities.
- Every mutation has exact read-back and replay evidence; failpoint tests prove no blind duplicate creation.
- Approved Product Contracts detect body or authority-property tampering and cannot be silently repaired.
- Active-contract and current-knowledge resolution reject duplicates, forks, and conflicting authority.
- Reciprocal Linear/Notion binding is verified semantically in both directions without copying the full contract into Linear.
- The installed plugin contains all runtime code and host instructions required by a cold Codex or Claude session.
- The real sandbox transcript passes offline validation, contains no secrets/private unrelated data, and proves cleanup disposition for every created object.
- The full repository suite and plugin/skill/compatibility validators pass from the merged `main` branch.

## Explicitly Deferred

- `ship-story` v3 orchestration and transient Git artifact lifecycle (Phase 5).
- Migration manifests/import/cleanup proposals (Phase 6).
- Maio topology, product mappings, production database provisioning, and active content import (Phases 7–8).
- Coordinated legacy runtime/profile/template/document removal and v3 cutover (Phase 9).
- Background reconciliation, webhooks, polling, offline queues, and automatic conflict merges.

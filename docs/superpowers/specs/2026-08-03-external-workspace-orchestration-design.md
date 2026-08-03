# Elephant External Workspace Orchestration Design

**Date:** 2026-08-03
**Status:** Approved for phased implementation planning

## Goal

Let Elephant use the systems that best fit each kind of delivery information instead of
persisting every artifact as Markdown in the code repository:

- Linear owns story identity, roadmap, dependencies, human-facing delivery state, and delivery
  evidence.
- Notion owns product knowledge and versioned Product Contracts.
- Git owns executable facts, project routing configuration, and temporary implementation
  workspaces.
- Elephant orchestrates those systems and verifies their consistency without becoming a fourth
  content store.

The design must remain usable by repositories that intentionally select new Git-backed providers,
but it carries no compatibility layer for Elephant's previous profile, mixed-spec, or file naming
formats. Maio is the only current Elephant consumer and will make one explicit, complete migration.

## Problem

Elephant's current delivery model persists roadmaps, Product Contracts, Technical Contracts,
implementation plans, review evidence, and closeout state in Git. These files support agent resume
and audit during delivery, but many become stale construction records after merge. The result is a
repository whose documentation surface can become more expensive to navigate than the code and
current durable rules it is meant to explain.

The current storage model also turns Elephant's lifecycle into a filesystem-specific workflow.
Linear already models issues, projects, relations, delivery state, and GitHub activity. Notion
already models connected product knowledge and human-readable contracts. Copying both systems into
Markdown creates duplicate sources of truth and unnecessary synchronization work.

## Principles

1. **One fact has one authority.** Derived summaries and reciprocal links are projections, not
   competing contracts.
2. **Persistence duration follows information lifetime.** Delivery artifacts must survive an
   interrupted iteration, but need not survive forever on `main`.
3. **Human state and machine checkpoint are separate.** Linear remains readable as a product
   delivery system while Elephant retains precise resume information.
4. **Product and engineering dimensions are independent.** A product is not inferred from an app,
   package, directory, or deployment unit without evidence and owner confirmation.
5. **Setup is discovery plus verified provisioning.** The presence of an MCP server or connector
   is not proof that its schema, permissions, or runtime capabilities are sufficient.
6. **Configured providers fail strictly.** An unavailable selected authority never silently falls
   back to another storage system.
7. **Non-semantic projections may self-heal; semantic drift may not.** Elephant can rebuild links
   and summaries but cannot overwrite product meaning or human reclassification.
8. **Migration moves current truth, not old file shapes.** Historical process documents are
   summarized, promoted, archived, or deleted according to their remaining value.
9. **No final legacy compatibility.** The new workspace schema replaces the old profile and
   artifact modes in one coordinated breaking cutover after the new path passes its pilot.

## Scope

This design introduces:

- pluggable story, product-knowledge, and Product Contract provider protocols;
- a machine-readable multi-product workspace registry and scoped delivery profiles;
- `elephant:setup-workspace` for discovery, proposal, provisioning, and validation;
- a Linear story provider;
- a Notion Product Contract provider;
- new Git story and Product Contract providers using only the new schema;
- a v3 `ship-story` flow with temporary Technical Contracts and implementation plans;
- `elephant:migrate-workspace` for audited adoption and repository cleanup;
- provider contract tests, failure injection, dual-runtime verification, and cold-start tests.

## Out of Scope

- a hosted Elephant synchronization service;
- background or webhook-driven two-way synchronization;
- offline queues and later conflict merging;
- redesigning the visual design gate or choosing a universal design system;
- treating Notion or Linear as storage for code-coupled technical execution plans;
- building translators or permanent runtime readers for the old `delivery-profile.md`,
  `legacy-mixed` artifacts, or mixed slice specifications;
- hard-coding Maio's eventual product and engineering-domain mapping into Elephant.

## Relationship to the Current Workflow

This design keeps the product-first authority split from the 2026-07-30 design: shaping remains a
product-only owner conversation, technical work remains agent-owned, and technical ambiguity
returns through an explicit product-decision path. It replaces that design's file persistence,
legacy compatibility, and profile model.

The current runtime remains untouched while the new provider path is built and tested. This is
temporary parallel development, not a compatibility architecture: no converter, dual writer, or
old-to-new adapter is added. After the new path passes a real Maio pilot, one coordinated cutover:

- migrates Maio to the new workspace and profiles;
- removes Maio's old profile and redundant delivery documents;
- removes Elephant's old profile reader, legacy-mixed branch, templates, tests, and documentation;
- changes `kickoff` to finish with `setup-workspace`;
- removes the old `init-profile` skill, which has no remaining responsibility once
  `setup-workspace` creates the registry and scoped profiles.

## Authority Model

### Linear

When `story_store: linear`, Linear is authoritative for:

- story identity and title;
- product-facing delivery state;
- priority, project membership, parent/child structure, and issue relations;
- split, deferred, rejected, and completed dispositions;
- Product Contract binding and derived Product Recap;
- Elephant's precise resume checkpoint in integration attachment metadata;
- branch, pull request, merge, verification, and delivery evidence.

The human-facing workflow is deliberately compact:

```text
Backlog → Shaping → Ready → In Progress → Done
                                      ↘ Canceled
```

`deferred` returns to Backlog with its reconsideration condition. `rejected` enters Canceled.
`split` creates child stories and closes the original with a split disposition. A technical
`needs-product-decision` checkpoint returns the issue to Shaping instead of creating an
engineering-specific human status.

Linear hierarchy maps to Elephant concepts as follows:

| Linear concept | Elephant meaning |
|---|---|
| Initiative | Optional strategic objective spanning projects |
| Project | Time-bounded release, phase, or outcome |
| Issue | One shapeable and independently deliverable story |
| Sub-issue | A split child story or bounded shared engineering task |
| Relations | Blocking, related, and duplicate semantics |
| Product label group | Exactly one product for a product-facing story |
| Kind label group | Product-facing or engineering-only work |
| Custom views | Product-specific backlogs and delivery views |

An issue contains a concise, derived Product Recap—problem, outcome, acceptance summary, and the
current Notion link—so routine prioritization does not require leaving Linear. The full Product
Contract never moves into the issue description.

Native Linear–Notion previews and Linear–GitHub links provide visibility. Elephant owns the
semantic binding, reciprocal references, and verification because the native Notion integration
is a preview mechanism rather than a complete two-way workflow.

### Notion

When `product_knowledge_store: notion` and `product_contract_store: notion`, Notion is authoritative
for product knowledge and Product Contracts. A workspace uses shared databases rather than one
schema per product:

1. **Products** — stable product identity, product key, Linear binding, and repository registry
   reference.
2. **Product Knowledge** — overview, object, glossary, rule, and product-decision pages related to
   one or more products.
3. **Product Contracts** — versioned story contracts related to a product and Linear issue.

Product pages expose filtered linked views of these shared databases. They do not duplicate the
database schemas or create separate product-specific document trees.

A Product Contract has at least:

- product relation;
- Linear issue identifier and URL;
- status and version;
- self-relation to the contract it supersedes;
- approved-at and approved-by evidence;
- approval fingerprint;
- the canonical product-only contract body.

Approved Product Contract pages are logically immutable. A change creates a successor page and
updates Linear's active-contract binding only after approval. Elephant recomputes the fingerprint
before every technical resume. A directly edited approved page stops delivery so the owner can
restore it or formalize the change as a successor.

Notion embeds the live Linear issue preview when the native integration is configured. Linear
stores the Notion page as an attachment or link. Elephant verifies both directions.

### Git

Git is authoritative for:

- code, schema, migrations, types, tests, and CI;
- durable technical decisions, runbooks, and focused rules that cannot be machine-enforced;
- the workspace registry and scoped delivery profiles;
- the active delivery branch's Technical Contract and implementation plan.

Technical Contracts and plans are durable for the lifetime of an iteration, not for the lifetime
of the repository. They are committed to the delivery branch so another session or worker can
resume. Closeout promotes durable knowledge and deletes both files before final integration.

The promotion order is:

1. code, types, schema, or migrations when the fact is executable;
2. tests, lint, constraints, or CI when the fact can be enforced;
3. AD/ED or another durable technical contract for cross-story architecture;
4. runbook for operations;
5. focused note for durable, task-triggered knowledge that cannot be enforced;
6. Linear delivery evidence for iteration-specific results;
7. deletion when the material only described this iteration's construction process.

Git `main` stores no story-level registry in external-provider mode. Linear attachment metadata
retains the active Notion page ID, approval fingerprint, schema version, and Elephant checkpoint.
The active Technical Contract repeats that binding only while the branch exists.

New projects may intentionally select new Git-backed story, product-knowledge, and Product Contract
providers. Those providers implement the same logical contracts with the new schema; they do not
revive legacy mixed specs or old profile formats.

## Workspace Configuration

The new local configuration is:

```text
.agents/elephant/
├── workspace.yaml
└── profiles/
    ├── <product-key>.yaml
    └── engineering.yaml
```

`workspace.yaml` contains only stable routing and provider configuration:

- schema and repository identity;
- selected provider types;
- Linear workspace, team, workflow-state, label, view, and template IDs;
- Notion database and property IDs;
- product keys mapped to Notion Product pages, Linear Product labels, profile paths, and primary
  engineering domains;
- engineering domains mapped to repository scopes, applicable instructions, verification entry
  points, and products they may affect.

Product profiles contain product-specific shaping context, design-gate configuration, verification
rules, and closeout routing. `engineering.yaml` contains defaults for work that demonstrably does
not change product outcomes.

No compatibility reader is retained for `.agents/elephant/delivery-profile.md` after coordinated
cutover. Explicit setup and the Maio migration replace it once.

## Provider Protocols

Elephant defines logical capabilities rather than hard-coding host-specific tool names.

### Story store

The minimum protocol includes:

- create and read a story;
- update human-facing product status;
- write and rebuild the Product Recap;
- create child stories and issue relations;
- bind the active Product Contract;
- persist and read an opaque Elephant checkpoint;
- attach branch, PR, verification, and delivery evidence;
- classify and report external drift.

### Product knowledge store

The minimum protocol includes:

- create, read, update, supersede, and query product-knowledge entries;
- resolve stable product, object, glossary, rule, and product-decision keys;
- maintain relations between knowledge entries and products;
- return the current knowledge context required by shaping and migration;
- import current truth without copying obsolete file structure;
- classify and report missing, duplicate, or conflicting current knowledge.

### Product Contract store

The minimum protocol includes:

- create, read, and update a shaping draft;
- approve a draft and compute its canonical fingerprint;
- create a successor linked to an approved predecessor;
- resolve the active approved version for one story;
- verify immutability and reciprocal story binding;
- classify and report external drift.

### Delivery workspace

The Git delivery workspace includes:

- persist and resume a Technical Contract;
- persist and update an implementation plan;
- bind the branch to the story and approved Product Contract;
- run implementation and conformance gates;
- promote durable knowledge;
- delete transient artifacts before integration.

Claude Code and Codex adapters may expose different concrete tools, but must pass the same provider
contract tests and produce the same state transitions.

## `elephant:setup-workspace`

`setup-workspace` is the universal initializer for the new workspace model. It can be invoked for
an existing mature repository and becomes kickoff's final phase for a new repository. It replaces
the old `init-profile` responsibility rather than delegating to or wrapping that legacy skill.

### Discovery

Setup reads:

- repository workspaces, applications, packages, deployment units, brands, product documents,
  instruction scopes, and dependency evidence;
- existing Notion databases, pages, relations, and product knowledge;
- existing Linear workspace, teams, workflows, labels, views, templates, projects, and issues;
- the actual operations exposed by the configured MCP servers or connectors;
- owner input for semantic boundaries that evidence cannot resolve.

It proposes two independent dimensions:

- **products** — user- or business-facing product identities;
- **engineering domains** — code, ownership, deployment, and verification boundaries.

Setup must not infer that an app, package, directory, team, or deployment unit is automatically a
product. Each proposal includes provenance, confidence, conflicts, and the questions that require
product judgment.

### Dry run and application

Before any external write, setup presents a complete dry-run model. After approval it:

1. reuses matching existing structures;
2. creates missing supported structures idempotently;
3. emits exact manual instructions for unsupported administrative operations;
4. reads all resulting structures back;
5. performs a disposable round-trip binding test and removes the test records;
6. writes the minimal workspace registry and profiles;
7. marks the workspace ready only when every runtime capability passes.

Rerunning setup produces a diff. It may repair non-semantic omissions but never silently rename,
move, merge, or delete user-owned external structures.

### Capability diagnostics

Setup reports exact causes:

| Diagnostic | Meaning |
|---|---|
| `platform_unsupported` | The platform API cannot perform the operation |
| `connector_capability_missing` | The platform supports it but the configured tool does not expose it |
| `permission_missing` | The operation is exposed but the current authorization is insufficient |
| `configuration_missing` | Required workspace objects or bindings do not exist |

Runtime story and Product Contract operations are mandatory. Administrative setup gaps may use a
one-time human handoff followed by read-back validation. Notion view creation is one known example
of a platform-level setup operation that its public API does not currently manage. Routine
`ship-story` must not require repeated manual provider work.

## Story Data Flow

### Product-facing happy path

```text
idea
→ create Linear issue in Shaping
→ create linked Notion Product Contract draft
→ shape in the main conversation and persist decisions to the draft
→ run product/UX and copy critics
→ owner approves the Product Contract Recap
→ approve and fingerprint the Notion page
→ write Linear Product Recap, active-contract binding, and Ready state
→ run the existing design gate when applicable
→ create the Git delivery branch and Technical Contract
→ set Linear In Progress and persist the implementation plan
→ implement, review, verify, and run contract conformance
→ promote durable technical knowledge
→ delete the Technical Contract and plan
→ integrate code
→ write Linear delivery evidence and Done state
```

The Notion contract is read-only after approval. A technical product ambiguity writes a
`needs-product-decision` checkpoint, returns Linear to Shaping, and invokes the successor Product
Contract flow. Routine technical review never creates an owner gate.

### Engineering-only path

An engineering-only story must prove unchanged user and business outcomes. It uses the Linear
story provider and Git delivery workspace but has no Product Contract. Its Technical Contract
contains the behavior-preservation boundary and remains transient.

### Git provider path

When a project explicitly selects Git providers, the same logical flow persists the story, product
knowledge, and Product Contract through the new Git schemas. This is a first-class provider choice,
not a runtime fallback. A project that selected Linear or Notion stops if that provider is
unavailable.

## Failure, Resume, and Drift

Cross-system actions are small, replayable transactions:

```text
preflight capabilities
→ inspect by stable external key
→ apply one authoritative mutation
→ read back and verify
→ write checkpoint
→ enter the next phase
```

If Linear issue creation succeeds and Notion draft creation fails, the issue records a
`contract_pending` checkpoint. Resume reuses the issue, finds or idempotently creates the contract,
verifies reciprocal links, and only then advances. It never creates a local `product.md` fallback.

Elephant may automatically repair:

- a missing or stale derived Product Recap;
- a missing reciprocal link or preview when authoritative IDs agree;
- a previous timeout where read-back proves the object was created;
- a checkpoint that lags a fully verified phase boundary.

Elephant stops for owner resolution when:

- an approved Product Contract fingerprint changes;
- a story's product or team is manually changed;
- a human-facing state advances past required delivery evidence;
- one external key resolves to several candidate objects;
- a product or business outcome changes;
- destructive, money-sensitive, security-sensitive, or production authority is newly required.

The first release performs reconciliation at workflow boundaries. It has no background service,
webhook consumer, offline queue, or automatic conflict merge.

## `elephant:migrate-workspace`

Migration is a reusable adoption skill, not a permanent old-format runtime reader. It runs only
after the target workspace passes setup validation.

Migration creates an auditable manifest that classifies each source as:

- `migrate` — move current truth to its new authority;
- `promote` — turn a durable rule into code, enforcement, AD/ED, runbook, or focused knowledge;
- `summarize` — retain a compact delivery result and evidence;
- `archive` — remove from default context but retain for archaeology;
- `delete` — remove duplicated or expired process material.

The required order is:

1. inventory sources, references, status, and evidence of current use;
2. propose product/domain mappings and source dispositions;
3. approve a no-write dry-run manifest;
4. create external target content without deleting Git sources;
5. read back content, relationships, fingerprints, counts, and links;
6. run agent cold-start queries against the new authorities;
7. deliver a representative real story through closeout;
8. apply a separate cleanup PR that removes old sources and rewrites routing;
9. verify a fresh session can discover and resume through the new workspace.

Migration retains current truth plus compact delivery history. Active and future stories move to
Linear with full current state. Completed stories retain outcome, disposition, verification, and
PR evidence, not their entire old plan or mixed spec. Current product knowledge moves to Notion.
Durable technical facts remain or are promoted in Git. Old plans and expired process documents are
not copied to another system merely to preserve their file shape.

The cleanup commit is independently revertible. External records carry a migration batch identity
so they can be audited without destructive rollback.

## Maio as the Acceptance Migration

Maio is the first and only current consumer, but remains an instance of the generic workflow. The
owner's current expectations are:

- one Linear Delivery team unless setup finds evidence that workflows or ownership have diverged;
- real product identities such as Maio and ClickFalcon, never repository implementation names such
  as `tracker`;
- products and engineering domains modeled independently;
- shared Notion databases with product-filtered views;
- current truth plus compact historical delivery evidence;
- complete removal of the old delivery profile and redundant repository documents after
  validation.

The final Maio mapping is intentionally not specified here. Phase 7 must inspect the then-current
repository and external workspaces, produce the exact mapping with evidence, and save it in a
separate Maio migration specification before external provisioning or repository cleanup.

## Verification Strategy

### Provider contract tests

Every provider implementation runs the same behavioral suite for creation, update, lookup,
binding, versioning, status transitions, drift classification, and idempotent retry.

### Failure injection

Tests interrupt execution after every remote mutation and before every checkpoint. Resume must
produce one authoritative object, preserve semantic state, and reach the same result as an
uninterrupted run.

### Setup fixtures

Fixtures cover:

- new single-product repositories;
- new multi-product monorepos;
- existing external workspaces with partial matching structures;
- conflicting product and engineering evidence;
- unsupported platform operations;
- missing connector capabilities;
- insufficient permissions;
- configuration omissions;
- repeated setup with no changes.

### Contract lifecycle tests

Tests cover draft resume, approval, direct-edit tamper detection, successor creation, active-version
rebinding, split, deferred, rejected, and technical decision return.

### Migration tests

Fixture repositories verify no deletion before read-back, stable manifest reruns, relation and link
integrity, content fingerprints, compact-history rules, cleanup rollback, and absence of stale
repository references.

### Runtime and cold-start tests

Claude Code and Codex must execute identical task packets and state transitions. A fresh session
with no conversational memory must locate the workspace, resolve the product/profile, read the
current authorities, and resume the first incomplete checkpoint.

### End-to-end acceptance

A representative Maio story runs from a one-line idea through Linear creation, Notion shaping,
approval, Git implementation, conformance, merge, delivery evidence, and artifact cleanup. The
final `main` branch must contain no story plan, Technical Contract, or story registry.

## Phased Delivery

Each phase is independently planned, implemented, reviewed, and verified within a session-sized
scope:

1. **Workspace core** — new schemas, provider ports, and state model alongside the untouched
   current runtime; verified with fake-provider contract tests.
2. **`setup-workspace`** — discovery, dry run, provisioning, and diagnostic classification;
   verified against single-product, multi-product, and existing-workspace fixtures.
3. **Linear provider** — issue, status, labels, relations, recap, attachment checkpoint, and GitHub
   binding; verified in a sandbox with cleanup.
4. **Notion providers** — shared product knowledge and contract databases, relations, draft,
   approval, successor, fingerprint, and Linear preview; verified in a sandbox with tamper
   detection.
5. **`ship-story` v3** — external story/contract orchestration and transient Git Technical
   Contract/plan lifecycle; verified by failpoint recovery at every remote write.
6. **`migrate-workspace`** — manifest, import, read-back validation, and cleanup proposal; verified
   against fixture repositories with zero early deletion.
7. **Maio setup** — analyze the real product/domain topology, approve mappings, provision external
   structures, and generate new local configuration.
8. **Maio import** — migrate current truth and compact history without deleting sources; verify
   counts, fingerprints, relations, links, and agent queries.
9. **Pilot and coordinated cutover** — deliver a real story from a cold start, then remove Maio's
   old documents/profile and Elephant's old runtime, `init-profile`, templates, tests, and docs in
   coordinated cleanup changes; verify both repositories contain only the new model and current
   durable facts.

Every phase includes provider contract regression tests, applicable failpoints, Claude/Codex
compatibility checks, and cold-start discovery checks. The implementation plan following this
design covers phase 1 only. Later phases receive their own plans after the preceding phase passes.

## Completion Criteria

The program is complete only when:

- the old profile, legacy mixed-spec path, and their legacy-behavior tests are removed from
  Elephant;
- setup can discover, propose, provision, diagnose, and revalidate a multi-product workspace;
- Linear, Notion, and new Git story/knowledge/contract providers pass their common contract suites;
- v3 story delivery resumes after every injected remote-write interruption;
- completed external-provider stories leave no Technical Contract, plan, or story registry on
  `main`;
- Maio's active product knowledge and delivery state resolve through Notion and Linear;
- Maio's old roadmap, mixed specs, completed plans, and redundant product documents are removed or
  promoted according to the approved migration manifest;
- a fresh Claude Code and Codex session can independently deliver and resume a Maio story using the
  new workspace.

## References

- [Linear teams](https://linear.app/docs/teams)
- [Linear projects](https://linear.app/docs/projects)
- [Linear issue relations](https://linear.app/docs/issue-relations)
- [Linear labels](https://linear.app/docs/labels)
- [Linear attachments](https://linear.app/developers/attachments)
- [Linear GitHub integration](https://linear.app/docs/github-integration)
- [Linear Notion integration](https://linear.app/docs/notion)
- [Linear OAuth scopes](https://linear.app/developers/oauth-2-0-authentication)
- [Notion relations and rollups](https://www.notion.com/help/relations-and-rollups)
- [Notion database properties](https://www.notion.com/help/database-properties)
- [Notion data source API limitations](https://developers.notion.com/reference/update-a-data-source)

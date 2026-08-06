---
schema: elephant.story/v2
story: capability-adaptive-workspace-setup
slug: capability-adaptive-workspace-setup
kind: product
status: approved
design_sensitivity: Low
amends:
  - docs/superpowers/specs/2026-08-05-one-person-company-information-coordination-product-v2.md
  - docs/superpowers/specs/2026-08-05-one-person-company-information-coordination-technical.md
---

# Capability-adaptive workspace setup

## 1. Problem

Elephant's information protocol and the current host's provisioning capabilities answer different
questions:

- the protocol defines the native Linear and Notion structure that makes later retrieval and
  maintenance reliable;
- the host determines which one-time administrative operations Elephant can perform directly.

The current setup flow conflates them. It allows an authenticated browser to fill connector gaps,
but treats a missing connector-and-browser write path for a required Product label as proof that
setup cannot proceed. That is too strict for an operation performed once per workspace. It can
also cause setup to promise actions before it has identified which ones the active host can
actually execute.

Reducing the durable information model to match the weakest provisioning surface would sacrifice
recurring automation value to avoid a small, one-time owner action. The Product-label contract is
especially valuable in a multi-Product workspace because it makes Issues, Projects, and
Initiatives independently queryable and unambiguous.

## 2. Outcome

Setup preserves one host-independent information structure while adapting how that structure is
provisioned. Elephant performs every supported operation, gives the owner one exact checklist for
the remaining setup-only administration, then verifies the real native objects before publishing
the workspace map.

The owner still approves one complete proposal. They do not copy internal IDs, maintain a setup
ledger, or repeat individual confirmations. After completing the checklist, one `done` response is
enough for Elephant to reconcile the native state and continue.

## 3. Product rules

1. Connector or browser automation coverage does not define the durable Linear/Notion protocol.
2. Multiple Products still require one verified Product label in each Linear Issue, Project, and
   Initiative label namespace. Runtime workflows receive no manual fallback for maintaining those
   classifications.
3. Manual provisioning is allowed only inside `setup-workspace` for low-frequency administrative
   operations that the active host cannot perform semantically or through an authenticated
   browser.
4. A manually provisioned required object must be discoverable and verifiable through a semantic
   read before setup can publish its stable ID or URL. If read-back is unavailable or ambiguous,
   setup remains incomplete.
5. Missing convenience may degrade gracefully. Missing required runtime structure may not.
6. Setup creates no persistent pending document, Linear Issue, Notion page, or Git ledger. Native
   external state is the recovery authority; `.agents/elephant/workspace.yaml` remains the only
   durable local setup result and is written last.

## 4. Setup flow

### Discover and classify capabilities

Before presenting a proposal, setup inventories the exact operations the proposal would require.
For each operation it records one user-visible execution class:

- **Elephant**: the active connector or authenticated browser can execute and semantically verify
  the operation;
- **Owner setup**: Elephant cannot execute the administrative operation, but can semantically
  verify its result afterward;
- **Unavailable**: the result cannot be created by either route and then verified. A required
  unavailable operation blocks approval; an optional one is omitted or declared degraded.

Capability discovery is operation-specific. The presence of a Linear or Notion connector does not
imply workspace administration, label creation, view creation, integration configuration, or
workspace renaming support. A tool advertised by a host but rejected by its backing service is
treated as unavailable for the current run.

### Present one proposal

The existing proposal boundary remains. In addition to Products, engineering domains, native
entry points, links, and the final config projection, the proposal shows who will perform each
setup operation. It distinguishes:

- **required structure**, which must exist and read back before completion; and
- **enhancements**, such as display-name cleanup, saved views, or native integrations that have a
  reliable ordinary-link fallback.

One approval covers the whole target state, Elephant's writes, and the displayed owner checklist.

### Apply supported operations

After approval, Elephant applies supported operations sequentially using the existing exact-scope
search, reuse, preservation, and read-back rules. A supported operation that is already present is
adopted rather than duplicated. Successfully created native objects remain useful recovery
evidence if the run stops before setup completes.

### Hand off administrative operations

When owner setup remains, Elephant returns one numbered checklist. Every item includes:

- the exact Linear or Notion tenant and native object type;
- the Product or company scope;
- the final human-visible name and applicable color, description, or relation;
- the shortest known UI location or direct entry link;
- whether the item is required or an enhancement;
- the semantic read Elephant will use to verify it.

The checklist contains no implementation explanation, connector diagnostics, internal setup
state, or request for the owner to copy opaque IDs. The owner completes the applicable items and
responds once.

### Reconcile and complete

On continuation, Elephant re-reads the exact native scopes. One semantically equivalent result is
adopted, zero keeps that item pending, and multiple or conflicting results stop with one bounded
reconciliation question. Verified IDs and URLs populate the already approved config projection.

If the original conversation is still authoritative, no second approval is needed. In a cold
session, setup rediscovers the native state and may finish read-only reconciliation. Before any
remaining external or config write, it presents the reconstructed compact proposal for one
approval; a material Product/domain ambiguity is resolved there rather than hidden in a persistent
recovery record.

The final workspace map is written and integrated only when every required external result reads
back correctly. Skipped or unavailable enhancements are reported as graceful degradation and do
not invalidate an otherwise executable map.

## 5. Failure and recovery behavior

- Failure of one automatic write stops subsequent writes, preserves already verified native
  results, and reports the direct resume action. Setup never rolls back user-visible objects.
- An owner statement that an item is complete is a resume signal, not verification evidence.
- A misspelled Workspace or Team display name is an enhancement when a verified stable ID still
  selects the correct scope. It remains visible in the checklist but does not block completion.
- A required Product label that cannot be written automatically becomes owner setup when its
  label namespace is semantically readable. It becomes unavailable only when Elephant cannot
  verify the resulting object.
- Saved views and native integration configuration are enhancements when ordinary scoped queries
  and links preserve correct operation. Setup states the degraded experience without weakening
  the information model.

## 6. Scope of implementation

Revise only the setup execution contract and its supporting planning guidance:

- `setup-workspace` gains operation-level capability classification, required-versus-enhancement
  presentation, the exact owner checklist, and resumable read-back rules;
- `linear-planning.md` distinguishes manual setup provisioning from forbidden manual runtime
  maintenance;
- setup and dual-runtime tests exercise host capability profiles rather than asserting only that
  browser fallback wording exists;
- the current `elephant.workspace/v4` Product-label fields and validation invariants remain
  unchanged.

No provider runtime, setup state machine, background synchronizer, pending file, or new local
schema is introduced. Maio migration and its concrete checklist remain a later consumer of this
generic behavior.

## 7. Acceptance scenarios

1. In a CLI host that can create Issue and Initiative labels and list all three label namespaces,
   setup creates the supported labels and hands off exact Project-label creation. After the owner
   creates those labels, setup reads their IDs and publishes a valid multi-Product workspace map.
2. In a host with an authenticated browser, the same proposal may be provisioned without owner UI
   work. The resulting workspace map and runtime behavior are identical.
3. If a required label namespace cannot be read, setup identifies the required operation as
   unavailable before approval and does not pretend manual creation would make the workspace
   executable.
4. Re-running setup after interruption reuses every uniquely equivalent label and page and creates
   no duplicates.
5. An unsupported Team rename appears as a non-blocking enhancement; the verified Team ID remains
   authoritative.
6. An unsupported saved view or native integration configuration degrades to ordinary scoped
   queries or links without removing Product labels or changing Product membership rules.
7. A cold continuation with unresolved automatic writes presents one remaining proposal; it does
   not create or depend on a repository, Linear, or Notion setup ledger.

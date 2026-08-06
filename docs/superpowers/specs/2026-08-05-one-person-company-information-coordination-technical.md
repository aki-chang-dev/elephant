---
schema: elephant.story/v2
story: information-coordination
slug: one-person-company-information-coordination
kind: technical
story_kind: product-facing
status: superseded
product_contract: docs/superpowers/specs/2026-08-05-one-person-company-information-coordination-product-v2.md
---

# Information coordination — minimal native-integration architecture

> Historical implementation contract. Its recovery-branch, retry, full-review-context, and fixed
> review-depth details were superseded by the approved proportional-assurance rules in the Product
> Contract and the packaged Elephant skills/references. Do not use this file as runtime workflow
> authority.

This contract contains implementation decisions and evidence. The approved Product Contract is
immutable during technical authoring and implementation.

## 1. Product-contract binding

| Product contract item | Technical response | Verification |
|---|---|---|
| §1–3: one owner works with agents; Linear, Notion, and Git/GitHub each have one clear role | Replace the provider-runtime model with host-executed skills plus one small workspace information map. Skills route planning reads/writes to Linear, durable knowledge to Notion, and delivery to Git/GitHub. | Single- and multi-product fixture scenarios show one source per fact and no duplicate roadmap or long-form delivery store. |
| §4.1–3: start from one sentence and retrieve progressively | `shape-story` accepts free-form input with no required classification. A shared routing reference makes direct Story relations, product anchors, and the Knowledge Map precede scoped and global search. | Skill scenario starts with one sentence, records no preliminary field request, and proves the connector trace never performs a global search when direct or product-scoped evidence answers the question. |
| §4.4–8: shaping determines planning position and one approval applies it | Extend the shaping recap with Objective/Project/Milestone placement, dependencies, conflicts, priority and roadmap consequences, and concrete knowledge action. Show `none` when an assessment found no impact. After explicit recap approval, the host creates or updates only the selected Linear and Notion objects and relations. | Product-flow fixtures cover direct-to-backlog, existing planning placement, new planning structure, dependency/conflict and no-impact branches, roadmap consequences, split/defer/reject, and each knowledge action with no second owner gate. |
| §4.9–12: routine maintenance without owner review | `ship-story` uses Linear issue state and native relations for factual progress. Every meaningful phase change creates a concise Linear status update covering progress, risk, and next direction; unchanged cadence creates nothing. Product-semantic changes return to shaping. | Delivery fixtures show automatic start/block/split/complete maintenance, required progress/risk/next-direction updates for meaningful changes, no-change suppression, and prove only changed product meaning produces a decision return. |
| §4.11 and rule 8: native integration first | Use Linear issue identifiers in branch names and pull-request titles/descriptions so Linear–GitHub creates the native delivery relationship. Put Linear URLs in Notion pages and Notion URLs in Linear resources; never create Elephant checkpoint or evidence attachments. | A real pilot and fixture traces prove the native link inputs are present and no custom checkpoint, recap hash, fingerprint, or delivery-evidence attachment is written. |
| §4.13–15 and rule 11: predictable retrieval and multi-product overview | The information map stores stable Product entry points. Skills classify the question, select the product, follow direct links, then expand scope in the approved order. Multi-product views are optional anchors. | Routing tests cover planning, knowledge, implementation, ambiguous-product, missing-anchor, and cross-product questions and assert bounded read order. |
| §5: progressive structure and graceful degradation | All planning anchors above Story are optional. Missing previews or GitHub integration degrade to ordinary links and a one-time setup recommendation. Missing decision-critical context stops; write-only failure leaves an explicit pending action in the current run. | Fixtures cover single product, multi product, no Objective/Project/Milestone, missing integrations, unavailable reads, and interrupted writes without repeating owner decisions. |
| §6: human-readable information and no internal leakage | Human titles and native Linear/Notion concepts remain visible. Internal config and transient branch files are not copied into issues/pages. Remove marker footers, hashes, fingerprint chains, provider diagnostics, checkpoint JSON, and certification transcripts from the user workflow. | Copy/conformance tests reject internal markers and implementation-progress sections in Linear/Notion output. |
| §7.2–3: valuable Notion content only | Notion is a page tree, not a database. `shape-story` chooses `linear_only`, `decision`, `knowledge`, or `decision_and_knowledge`; the host then creates/updates only those pages and maintains the short Knowledge Map. | Scenarios prove a simple Story creates no Notion page, a durable decision creates one linked page, living knowledge updates in place, and raw conversation/plan/review/test content is absent. |
| §7.4–5, 9–10: progressive planning and minimal setup | Setup discovers products and domains separately, proposes only current Products plus entry points, and creates no future planning levels or knowledge categories. Single-product config omits product-specific view anchors unless useful. | Setup fixtures cover empty, existing, single-product, multi-product, and ambiguous repositories and compare the human proposal and final small config. |
| §7.6–7: approval boundary and automatic maintenance | The shaping approval receipt is held by the active host run and authorizes the displayed planning/knowledge actions. Technical reviewers never request routine owner approval. | Orchestration fixtures assert one product approval, automatic downstream calls, and a bounded decision return only on changed product semantics. |
| §7.12: one primary home per fact | Linear contains live status and concise outcome/acceptance; Notion contains durable explanation; Git branch files contain transient technical contract/plan only. Links are projections. | Closeout test proves transient branch artifacts are removed before integration and no duplicated Story registry or roadmap is committed. |

## 2. Current-system context

Inspected repository evidence:

- `README.md` states workspace v3 and the Linear provider are development-only; v3 `ship-story`
  is inactive and the active runtime remains v2.
- `plugins/elephant/elephant_runtime/workspace_core/` defines fixed provider capabilities, six
  statuses, checkpoint phases, drift categories, and database-oriented external bindings.
- `plugins/elephant/elephant_runtime/workspace_setup/` contains roughly 6,500 lines of manifest,
  fingerprint, filesystem-transaction, handoff, and setup code; its setup tests contain roughly
  6,700 lines.
- `plugins/elephant/elephant_runtime/linear/` contains roughly 3,200 lines, including custom
  checkpoint attachment, replay, normalization, and certification behavior; Linear tests contain
  roughly 2,900 lines.
- `feat/notion-providers` adds roughly 13,000 lines around three Notion databases, SQL queries,
  immutable contracts, fingerprints, replay, and certification. It is isolated and unmerged.
- `plugins/elephant/skills/ship-story/SKILL.md` still consumes the active v2 delivery profile, so
  removing inactive v3 provider code does not change the current shipping path before cutover.
- `plugins/elephant/skills/shape-story/SKILL.md` already provides the product-only conversation,
  critic, recap, and explicit approval boundary; it needs external-context and planning-output
  changes rather than replacement of its product discipline.
- Maio currently has one v2 `delivery-profile.md`; its final migration is a separate product scope.

Current official product evidence:

- Linear Initiatives group Projects around objectives; Projects, Milestones, Issues, Backlog,
  labels, custom views, and status updates provide the planning model:
  `https://linear.app/docs/initiatives`, `https://linear.app/docs/project-milestones`,
  `https://linear.app/docs/custom-views`.
- Linear recommends keeping one Team for small teams and supports Product-line categorization with
  Project and Initiative labels: `https://linear.app/docs/teams`,
  `https://linear.app/docs/project-labels`.
- Linear–GitHub links issues to pull requests and commits through issue identifiers and can update
  issue status from pull-request activity: `https://linear.app/docs/github-integration`.
- Notion's Linear integration supplies live previews but is not a full two-way workflow:
  `https://linear.app/docs/notion`.
- Notion search can scope to a page and its descendants and search page bodies:
  `https://www.notion.com/help/search`.
- The current host exposes direct Linear list/get/save operations for Initiatives, Projects,
  Milestones, Issues, labels, status updates, search, and fetch, plus Notion search/fetch/page
  create/update/move operations. Skills can use them without a Python provider facade.

## 3. Technical scope

### Keep and adapt

- Keep the product-first conversation, two product critics, one recap approval, technical
  specialist review, worktree isolation, and transient technical plan discipline.
- Keep the product-versus-engineering-domain distinction and repository-scope discovery.
- Keep ordinary safe practices: read before destructive changes, preserve unrelated labels and
  relations, validate local config, and write local config atomically.
- Keep host-neutral skill wording where Claude and Codex expose equivalent semantic operations.
- Prefer semantic connector operations. For setup-only Linear administration the connector cannot
  create, use an authenticated host browser when available, then verify the result through semantic
  reads. Browser automation is an execution fallback, not a provider runtime or owner handoff.

### Replace

- Replace `workspace_core` provider/capability/state contracts with a small `workspace_map` model
  that validates stable entry points, Product/domain routing, and integration availability.
- Replace the setup manifest/apply transaction engine with a host-orchestrated discovery,
  human-readable proposal, one approval, one short-lived human-readable pending note, sequential
  native creation/reuse, read-back, and final config write.
- Replace the Linear Python provider with direct host calls described by a short planning
  reference. Linear itself owns status, hierarchy, relations, progress, and GitHub projections.
- Replace mandatory file Product Contracts with authoritative product sources in Linear and,
  only when valuable, Notion. The transient Technical Contract records exact source URLs/IDs and
  maps their current content; it does not require a permanent repository Product Contract.
- Replace Notion database providers with page-tree navigation, scoped search, ordinary page
  creation/update, and one human-readable Knowledge Map per Product.

### Remove

- Remove inactive provider capability matrices, fixed external status machine, drift/repair
  taxonomy, canonical marker/hash footers, checkpoint attachments, replay tokens, three-database
  Notion schema, SQL query path, approval fingerprints, immutable successor chains, provider
  certification transcripts, and their dedicated validators/tests.
- Abandon the unmerged Phase 4 implementation rather than merging or porting it. Retain only
  externally verified facts that remain relevant to direct host calls.
- Remove superseded v3 plans/references after the replacement reference and implementation plan
  make their history unnecessary for active agents.

### Add or rewrite

- `plugins/elephant/elephant_runtime/workspace_map.py`: small pure value validation and route
  selection; no connector calls or provider abstraction.
- `plugins/elephant/references/information-routing.md`: the approved retrieval order, primary-home
  rules, Product planning semantics, Knowledge Map shape, and native-integration-first behavior.
- `plugins/elephant/references/linear-planning.md`: exact host operations needed for normal
  Initiative/Project/Milestone/Story/status-update work, preserving unrelated user content.
- `plugins/elephant/references/notion-knowledge.md`: Product Home, Knowledge Map, Decision and
  Knowledge page patterns using ordinary pages and scoped search.
- Rewrite `setup-workspace`, `shape-story`, `author-technical-contract`, `ship-story`, `kickoff`,
  and `decompose-roadmap` where their inputs/outputs depend on the superseded storage model.
- Add focused config, routing, skill, and end-to-end fixture tests. Avoid one test suite per
  connector response type.

Explicit exclusions:

- Maio migration, external cleanup of existing Maio documents, and final Maio Linear/Notion
  population are a separate bounded delivery after the generic path passes.
- No background synchronization service, provider SDK, webhook receiver, automatic queue worker,
  or universal project-management abstraction. A single approved operation may keep one
  Git-visible pending note until its displayed writes finish; nothing processes it in the
  background.
- When the connector lacks Linear Product-label or custom-view creation, authenticated host-browser
  setup may perform the exact approved administration. If neither route can create a required
  Product label, setup stops before its first write; an optional company view alone may degrade to
  one concise manual step and is stored only after read-back.

## 4. Domain and data contracts

### Workspace map

Use one human-readable `.agents/elephant/workspace.yaml` with a new schema. It contains only:

- repository identity and engineering domains;
- the Linear workspace/Team entry point;
- the Notion company-knowledge root;
- the GitHub repository binding when it cannot be inferred unambiguously from Git;
- Product keys, human names, applicable engineering domains, conditionally required stable Linear
  Product-label IDs for Issues, Projects, and Initiatives, and optional stable entry points for
  Linear planning, backlog, Notion Product Home, and Knowledge Map;
- optional shared-knowledge and company-portfolio entry points.

It contains no Story state, roadmap items, document bodies, OAuth material, connector tool names,
approval receipts, hashes, checkpoints, or transient delivery artifacts. One Product may omit
product-specific Linear view anchors; multiple Products may add them progressively.

Validation invariants:

- Product keys and domain keys are unique nonblank stable keys.
- Product entries are the sole owner of Product-to-domain membership and may list only existing
  domain keys. Domain entries do not repeat Product membership.
- repository paths are relative POSIX paths without escape segments.
- external anchors are HTTPS URLs or opaque IDs in their documented field, never secrets. Before
  use, Linear ownership is checked per object type: an Issue belongs to the configured Team, a
  Project includes the configured Team in its preserved Team set, an Initiative belongs to the
  configured workspace, and a Milestone belongs to an in-scope Project. Notion anchors must be the
  configured root or a descendant of it, and GitHub anchors must match the configured Git remote.
- exactly one default Product is allowed; when there is one Product it is implicit.
- one Product requires no Product labels. With multiple Products, every Product must have one
  verified label ID in each applicable Linear namespace before scoped planning writes begin.
- absent optional integration or view anchors are valid and trigger graceful behavior, not config
  rejection.

### External content

- Linear is the only mutable planning state. Initiative, Project, Milestone, Issue, native status,
  priority, dependency, and native GitHub relation remain Linear objects.
- Product membership is a classification, not a hierarchy container. In a single-Product workspace
  it is implicit and adds no labels. With multiple Products, Linear's separate label namespaces
  require each Product to store one stable Issue-label ID, Project-label ID, and Initiative-label
  ID. Every Elephant-managed Story then has exactly one Product Issue label; every managed Project
  or Initiative has the corresponding Product label. A Milestone inherits Product from its
  Project. Conflicting, missing, cross-workspace, or cross-Team membership stops scoped writes and
  asks one bounded Product question instead of guessing.
- Linear's native containment defines the valid roll-up projection: a Story may stand alone in the
  Product backlog or belong to a Project; a Project may stand alone or contribute to an Initiative;
  a Milestone exists only inside a Project and classifies that Project's Stories. When an
  Initiative is useful but a Project is not, put an ordinary visible Initiative link in the
  Story's product-context section under the exact label `Related Objective`. It provides direct
  navigation but does not affect Objective progress and does not create a reciprocal list of
  Stories. Elephant creates a Project only when it represents a real workstream. If that workstream
  appears later, replace the contextual link with the native Project-to-Initiative roll-up while
  preserving Story navigation.
- Reconcile this link in both directions. When a Story leaves a Project, or its Project leaves an
  Initiative, restore `Related Objective` if that Objective remains relevant and ensure the Story
  no longer affects its progress. When the Objective is no longer relevant, remove the contextual
  link instead. Never leave navigation that implies stale progress attribution.
- A Linear Story description contains a concise user problem, desired outcome, observable
  acceptance, and links to durable context. It contains no Elephant marker footer or implementation
  progress.
- Notion Product Home pages link to Overview, Knowledge Map, Decisions, and Linear planning.
- A Knowledge Map is ordinary page content containing titled links plus one-sentence relevance
  descriptions. It is not a database or a duplicate document index in Git.
- Product Home starts with a concise Overview and a Linear link/preview. Knowledge Map, Knowledge,
  and Decisions navigation appears only after durable content exists; setup creates no blank
  category pages. Notion never renders live status, progress, or a roadmap copy.
- Every Product-specific Decision and Knowledge page is a descendant of that Product Home. Create
  the exact Decisions or Knowledge category node lazily with its first child, and place each page
  under the matching category; keep the Knowledge Map beneath the same Product Home. Shared pages
  are descendants of the configured Shared Knowledge root. Page identity is exact parent plus
  human title: zero matches may create, one updates, and multiple matches stop for reconciliation.
  Wrong-Product and wrong-parent pages remain untouched. Knowledge Map links always target the
  canonical child. Links never substitute for this canonical searchable containment.
- A Decision page uses a stable human title and states the decision, product context/problem,
  rationale, consequences, and related Linear work, Knowledge, or superseding Decision. An obsolete
  Decision may be visibly marked superseded and link to the current result.
- A Knowledge page states the problem it addresses, when it is useful, the current conclusion, and
  related Knowledge, Decisions, and Linear work. Living Knowledge updates in place.

### Transient delivery artifacts

The delivery branch may contain one Technical Contract and one implementation plan under a
predictable Story-scoped path. They bind the Linear Issue and relevant Notion URLs, are committed
on the delivery branch for resume, and are deleted before final integration after durable facts
are promoted to code, tests, repository guidance, Linear, or Notion.

Setup and standalone shaping allocate a non-main isolated operation branch before external writes.
After approval, that branch contains one short-lived `pending-application.md`. It copies the
approved recap's intended final outcomes, resolved target scopes, and current semantic
preconditions; it does not pretend to be a live progress ledger. It contains no token, hash,
connector payload, or executable command. The agent commits it and, when a configured Git remote
is available, publishes the branch before the first external write. Without a publishable remote,
the recap states that recovery is limited to the same working copy and then may proceed under the
active approval.

Another device may use the published note for read-only reconciliation, but the note is not an
authenticated approval credential. Cold cross-device recovery never writes from the note and adds
no second owner gate; write execution resumes only inside the original authenticated host approval
context. If that context is unavailable, the result remains visibly pending until an authorized
host continuation exists. Any semantic edit to its intended outcomes or preconditions invalidates
the prior approval and returns to shaping. When all shaping outcomes are reflected
externally, the agent deletes the note and its local and remote operation branch. Setup first
promotes only the validated final workspace-config tree change through the repository's configured
integration workflow, verifies it on the remote integration branch, and then deletes the operation
branch. A squash/config-only commit boundary excludes the pending note and its intermediate
history. The note never merges as durable product knowledge.

## 5. Interfaces and data flow

### Retrieval router

Every coordinating skill first classifies the question as planning, product knowledge/decision,
or executable behavior, then resolves Product. A single-Product workspace uses the implicit
default. With multiple Products, resolve from the current Story's Product Issue label, verify
matching Project/Initiative labels and Milestone ownership, and ask one bounded question only when
explicit context and native relationships remain ambiguous.

The classification selects the authoritative-home route:

- **Planning/progress:** start with the current Linear Story and its Project, Initiative,
  Milestone, dependencies, and configured Product planning entry. If insufficient, run a
  cardinality-aware Product-scoped Linear search: for one implicit Product, constrain it to the
  configured Team and Product planning/backlog entry; for multiple Products, additionally require
  the matching Product labels. Cross to Notion only through a direct relation or when the question
  explicitly requires product meaning that Linear does not contain.
- **Product meaning/decision:** start with directly linked Notion context, then Product Home and
  Knowledge Map, then search only Product Home descendants. Expand to Shared Knowledge and finally
  workspace-wide Notion search only when narrower evidence is insufficient. Read Linear through a
  direct relation only when current planning state is needed.
- **Executable behavior:** start with the linked GitHub branch/PR and repository paths, then use
  repository-scoped search. Read Linear or Notion only through direct relations when delivery scope
  or approved meaning is necessary to interpret the code.

Every route stops expanding when sufficient evidence is found and returns direct source links so
later agents can take the shortest path. A different system's preview or projection never
substitutes for a missing authoritative fact. If the authoritative home is unavailable or lacks
decision-critical content, Elephant names the missing context instead of making a planning,
product-meaning, or executable-behavior claim from a plausible stale copy.

### Setup

1. Read repository context and available integrations without writes.
2. Discover existing Linear/Notion roots and Product candidates; keep Product and engineering
   domain evidence separate.
3. Present one human-readable proposal: Products, domains, reused/created entry points, native
   integration recommendations, content worth migrating, and the final local-config projection.
   Existing values are literal. For every object that will be created, the projection names the
   human target and the one exact config field that its verified returned ID/URL will fill; no
   fabricated placeholder value is presented as final.
4. Owner approval authorizes only the displayed semantic proposal. Create the isolated operation
   branch, record the proposal in its one human-readable pending note, and publish it when a Git
   remote is available before the first write.
5. Execute the small list sequentially. Before every create, search within the exact verified
   parent scope and require zero equivalent objects. After a successful create/update, fetch the
   object, verify semantic equivalence and ownership, then record its returned URL/ID as applied.
6. If a create has an indeterminate outcome, stop without changing the desired-outcome note. On
   resume, use the provider's direct scoped collection read rather than full-text search. Adopt one
   semantically equivalent result and stop on multiple or conflicting results. Zero results permit
   one ordinary create only after the connector is healthy, semantic preconditions are unchanged,
   and absence is confirmed by two fresh authoritative scoped reads across the provider's bounded
   consistency window; otherwise the action remains pending. A definitively rejected call may be
   retried only after its preconditions are re-read.
7. If any call fails, derive applied, unknown, and pending outcomes from fresh native reads and
   report them. The original authenticated approved host context may resume from the unchanged note
   after checking preconditions. A cold device performs read reconciliation only; the note itself
   never authorizes writes. Render the owner message as what is already reflected, what remains
   unapplied or unconfirmed, that the approved proposal is preserved, and the direct resume
   place/action; keep connector-state vocabulary internal. Never roll back or delete user content
   automatically.
8. Write and validate workspace config last with a normal atomic local replacement. Materialize
   generated IDs/URLs only into the fields declared for their approved human targets and only from
   verified read-back objects. Once all displayed outcomes read back correctly, construct one final
   config-only diff against the operation branch's base while leaving the pending note intact on
   that branch. Every non-generated value must equal the approved projection, and every generated
   value must match its declared field and verified object; any other semantic drift stops and
   requires a revised proposal.
9. Immediately before promotion, fetch the current remote integration branch, validate its current
   workspace config, and derive the approved config-only change against that exact head. Any
   semantic drift, overlap, or unresolved conflict stops for a revised proposal; never force-push
   or automatically resolve a semantic config conflict. Promote the result as a squash or
   equivalent clean commit through the repository's configured integration workflow. The original
   setup approval authorizes only the displayed projection and declared generated values.
   Revalidate after integration, push without force, and verify the remote integration branch
   contains the validated config. Only then remove the pending note and delete the local and remote
   operation branch.

#### Single-Product to multi-Product transition

Setup owns the cardinality transition and keeps the old implicit single-Product config authoritative
until the transition is complete. Before approval, inventory existing in-scope Issues, Projects,
Initiatives, and Milestones separately from unrelated Team content. The proposal classifies every
managed object into the former default Product, the new Product, or an explicit exclusion; ask one
bounded Product question for any object whose ownership is not evident from approved context.

After the one setup approval, create and read back all Issue/Project/Initiative Product labels for
both Products before planning writes. Backfill only approved in-scope objects, merge unrelated
labels, and verify each object's ownership and final label set. Partial or interrupted backfill
leaves the old single-Product config active and uses the pending note for read reconciliation. The
multi-Product config is materialized and promoted only after every included object and exclusion
reads back consistently. Immediately before promotion, run a fresh in-scope inventory. Clearly
inherited late objects are classified and backfilled under the approved rules; a late object that
changes Product meaning stops for a revised proposal. No unlabeled managed object becomes visible
to the multi-Product router.

No cryptographic manifest, external transaction, disposable certification relationship, or opaque
cross-process approval bearer is used. The pending note preserves the exact product result; it is
navigation and read-recovery input, not write authority. Product shaping repeats only if its
meaning or a semantic precondition changed.

### Shaping

1. Accept the one-sentence idea and load context through the retrieval router.
2. Conduct the product-only conversation and critics. Before recap, retrieve current planning
   relations and assess dependencies, conflicts, priority impact, and roadmap consequences.
3. Produce the product recap plus planning and knowledge actions. It names dependencies, conflicts,
   priority and roadmap consequences even when the assessed result is `none`.
4. After approval, persist the displayed actions in the transient pending note. Create/update the
   necessary Initiative, Project, Milestone, and Story directly through Linear; omit every level
   not justified by the recap, follow Linear's valid containment projection, and apply only the
   relations and priority changes displayed in the approved recap.
5. Write the concise Linear Story outcome/acceptance. Apply the chosen Notion action only when
   durable value exists, then add ordinary reciprocal links/previews. If the approved placement is
   a direct Objective without Project, add the visible Initiative URL to the Story's product
   context as `Related Objective` and explicitly leave Objective progress unchanged.
6. Re-fetch affected objects, reconcile the note with visible truth, remove it when complete, and
   report the final human-visible result and direct links. If a write remains unavailable, keep
   the note and report the direct resume path without asking for the same product decision again.
   Recovery feedback leads with human outcomes: what is already reflected, what remains unapplied
   or unconfirmed, that the product decision is preserved, and the direct place/action for resume.
   It does not expose connector states such as `unknown` or `pending` as user-facing vocabulary.

### Multi-product overview

When setup discovers more than one Product and the owner-approved proposal confirms a navigation
need, it must establish one lightweight Linear company overview that surfaces active Initiatives
and Projects grouped or filtered by Product labels, next Milestones, current health/risk, and
priority/current attention. Reuse an existing view when it satisfies that content. If the host can
create the native view, create and read it back; otherwise provide one exact Linear UI handoff with
the required filters/grouping and store its URL only after read-back. This is the only setup
convenience allowed to remain a visible manual step; it does not create a Notion roadmap copy.

### Technical design and delivery

1. `author-technical-contract` reads the Linear Story and linked Notion pages as the approved
   product sources. It maps the complete current observable requirements into the transient
   Technical Contract. Product ambiguity returns to shaping.
2. `ship-story` creates a worktree/branch whose name contains the Linear issue identifier, records
   only the transient Technical Contract and plan, and performs implementation/review.
3. PR title or description contains the Linear issue identifier. Native Linear–GitHub integration
   creates the relationship and may update status. When unavailable, Elephant adds an ordinary PR
   link and updates factual Linear status itself.
4. Closeout updates meaningful Linear planning state, promotes durable product knowledge when the
   implementation revealed an approved durable consequence, removes transient branch artifacts,
   and integrates through the repository's configured Git workflow.

## 6. Product-state implementation

- `Backlog`, `Shaping`, `Ready`, `In Progress`, `Done`, and `Canceled` remain useful default
  semantics, not a compulsory Elephant-owned state machine. Setup maps to the Team's native
  workflow and recommends a new state only when the approved user flow cannot be represented.
- Product dispositions remain `approved`, `split`, `deferred`, and `rejected` inside the shaping
  conversation. Their Linear effects use native status, parent/child, and relation capabilities.
- Deferred work remains visible as not-currently-planned work in the Team's native backlog/planned
  workflow with its next condition; it is not presented as canceled. Canceled work uses the native
  canceled state and retains the approved product rationale. Each meaningful transition receives
  the applicable concise Issue, Project, or Initiative update; unchanged states produce nothing.
- Priority uses Linear's native priority. The shaping recap explains the proposed change and its
  impact; approval authorizes the update.
- A factual blocker, linked PR, completion, or implementation split is routine maintenance. A new
  user outcome, changed acceptance criterion, cross-objective priority choice, or product tradeoff
  is a product decision return.
- Every meaningful Project or Initiative phase change writes one concise native Linear update with
  progress, current risk, and next direction. A polling run, elapsed interval, or unchanged state
  writes no update.
- For a standalone Story, the same meaningful-change content is written once as a concise Linear
  Issue comment because no Project or Initiative update surface exists. Repeated reads and
  unchanged state write no comment. Once the Story belongs to a Project, aggregate phase updates
  use Project/Initiative surfaces and the Issue receives only Story-specific information.
- Treat the standalone-Story comment as append-only. List visible Issue comments before writing
  and do not append when one semantically equivalent progress/risk/next-direction comment already
  exists. Read back after the append. For an indeterminate outcome, one or more semantically
  equivalent visible comments satisfy the outcome; report pre-existing duplication without
  deleting user content. Conflicting content stops. Zero results permit one append only after the
  connector is healthy and authoritative comment reads confirm absence across the bounded
  consistency window. Equivalence uses the human content and Story/phase context, not a marker,
  hash, or hidden ID in user-facing copy.
- Integration unavailability is phrased in human terms, preserves ordinary links, and gives the
  next available action. Missing decision-critical content prevents product claims; completed
  discussion is not repeated solely because a later write failed.

## 7. Security, privacy, and operational behavior

- Host connectors execute as the authenticated user and remain bounded by their native
  permissions. Permission alone is not scope proof: every Issue is checked against its Team,
  every Project against its Team set, every Initiative against its workspace, every Milestone
  against its Project, every Notion page against root ancestry, and every GitHub target against the
  configured repository before a read result influences routing or a write occurs. Elephant does
  not store OAuth tokens, signed URLs, raw connector payloads, private attachment bodies, or
  account email addresses.
- Before any authenticated-browser mutation, semantic reads establish the selected Linear
  workspace and Team, and the browser must visibly resolve to that same tenant and exact approved
  administrative target on Linear's origin. Missing or mismatched scope stops before the browser
  write. Every browser-created label or view still requires post-write semantic read-back.
- Workspace config contains stable public/workspace-scoped anchors only. Validators reject likely
  secret-bearing keys and URL query credentials.
- All updates fetch the current object first. Where the host supports conditional/versioned
  mutation, use it. Otherwise re-read immediately before mutation, stop if an approved semantic
  field or ownership changed, patch only the displayed fields, then read back the postcondition.
  When an API replaces a full set such as labels, merge unrelated current values rather than
  replacing them. Append-only link calls check visible links before adding another.
- Setup and normal coordination never delete external pages, issues, Projects, Initiatives, labels,
  or views. Migration owns any later destructive cleanup with an explicit inventory and approval.
- Partial external writes are acceptable and visible. Recovery reconciles the Git-visible desired
  outcomes against exact scoped reads, resumes writes only in the original authenticated approved
  host context, applies the bounded authoritative-absence rule to indeterminate creates, and never
  invents distributed transactions.
- Local config replacement writes a complete validated candidate and atomically replaces the one
  target file. It does not replace the entire `.agents` container or implement crash-recovery
  receipts.
- Logs and tracked fixtures use synthetic or redacted identifiers and contain no raw external
  response archives. Real pilots record human-visible outcomes and links privately, not exhaustive
  transcripts.

## 8. Compatibility and migration

1. Build the replacement workspace map, references, and skills beside the active v2 shipping path.
   This temporary coexistence is development isolation, not a supported compatibility layer.
2. Remove the inactive v3 `workspace_core`, `workspace_setup`, and Linear provider runtime plus
   their forwarding modules, validators, sandbox fixtures, and dedicated tests once replacement
   tests cover the Product Contract.
3. Do not merge `feat/notion-providers`. After the new implementation has no dependency on it,
   remove its worktree/branch through the normal safe branch cleanup workflow.
4. Run the synthetic read-only cold-start pilot for generic setup, one-recap shaping, and
   authoritative routing. Do not write to Maio's live Linear, Notion, or GitHub scope in this
   plugin-redesign step.
5. Run the separate Maio migration: create the minimal Linear/Notion structure, move current useful
   truth, replace `delivery-profile.md` with the new workspace map, and clean redundant documents.
6. Cut over `kickoff`, `shape-story`, and `ship-story` together, then remove legacy v2 profile,
   mixed-spec, and old artifact behavior. No converter or permanent dual reader remains.

Rollback before Maio cutover is the existing v2 plugin state. After cutover, rollback is the Git
revert of the coordinated plugin/config migration plus the non-destructive external objects left
in place; rollback does not delete user-visible Linear/Notion content.

## 9. Verification strategy

### Deterministic automated evidence

Deterministic tests cover the executable surfaces that can be evaluated without pretending prose
is runtime behavior:

- Workspace-map schema, validation, Product resolution, planning-scope projection, safe anchors,
  label-free single Product, labeled multi Product, and invalid/ambiguous routing stops.
- Exact packaged skill/reference inventory, manifest parity and release metadata, installed-plugin
  smoke, minimal runtime exports, checkout forwarder, and absence of superseded runtime/assets.
- Full unit suite, compatibility validator, compileall, official plugin validator, and
  `git diff --check`.

### Independent skill pressure and acceptance evidence

The following behaviors are evaluated by fresh read-only agents against the complete packaged
skills and synthetic scenarios, then recorded as concise RED/GREEN outcomes. They are not Python
source-text assertions: such assertions would prove wording, not host behavior.

- Workspace-map validation and route selection: implicit label-free single product, multi product,
  ambiguous product, distinct Issue/Project/Initiative Product labels, optional integrations/views,
  secret-like content, malformed anchors, cross-workspace/Team targets, wrong Notion ancestry, and
  wrong GitHub repository.
- Retrieval traces: direct relation, Product anchor, Knowledge Map, product-scoped search, shared
  knowledge, and final global-search expansion. Planning begins in Linear, meaning/decision begins
  in Notion, and executable behavior begins in Git; assert no broader or cross-system call occurs
  when the authoritative home answers the question. Separate single-Product traces prove Team plus
  planning/backlog scope works without labels; multi-Product traces prove labels narrow the same
  route. Both stop before workspace-wide search when scoped evidence is sufficient.
- Per-route missing-authority fixtures place tempting stale substitute data in the other two
  systems and prove Elephant surfaces the missing Linear, Notion, or Git context without making an
  authoritative claim from that projection.
- Setup scenarios: empty/existing workspace, single/multi product, manual custom-view step,
  deterministic Product classification, definitive failure, indeterminate create with zero/one/
  multiple scoped matches, bounded authoritative-absence recovery, same-copy resume, cross-device
  read reconciliation without write authority, unchanged rerun, concurrent semantic edit
  detection, current-integration-head conflict detection, semantic connector administration,
  authenticated browser fallback, required-label capability failure before writes, and
  preservation of unrelated content. Single-to-multi fixtures cover complete inventory,
  exclusions, bounded ambiguity, interrupted label backfill with old config still authoritative,
  and final config promotion only after complete read-back. Deterministic late-object injection
  proves an unambiguous inherited object is backfilled before promotion, while an ambiguous or
  meaning-changing object preserves the old config and pending note and prevents promotion.
- Temporary-Git setup fixtures independently cover integration conflict, rejected push, wrong
  remote read-back, and success. Every failure preserves the pending note and operation branch;
  success produces config-only integrated history with no pending note or intermediate commits,
  verifies the remote config, and only then cleans both operation branches.
- Browser-administration negatives cover wrong origin, workspace, Team, and approved target with
  zero browser writes. Missing or mismatched post-write semantic read-back prevents config
  promotion and preserves recovery state.
- Shaping scenarios: one-sentence input, direct backlog Story, standalone Objective, standalone
  Project, Project in Initiative, Milestone in Project, no Project without a real workstream,
  dependencies/conflicts present and absent, priority and roadmap consequences, all dispositions,
  each knowledge action, pending-write resume, and one approval gate. Assert the recap includes
  every assessment and only approved relations/priority changes are applied.
- Delivery scenarios: native GitHub integration present/absent, issue identifier in branch/PR,
  factual status maintenance, required progress/risk/next-direction updates on meaningful phases,
  standalone-Story Issue comments, no-change update suppression, bidirectional `Related Objective`
  reconciliation, comment pre-read/read-back and indeterminate append recovery, product-decision
  return, and transient artifact removal. Comment cases independently cover zero results before
  and across the bounded window, one equivalent, multiple equivalent, conflicting content, and
  successful append read-back; assert at most one new append, no deletion, accurate duplicate
  reporting, and unchanged-state suppression.
- Multi-product overview scenario: native view creation when available and exact manual-view
  handoff otherwise; assert active Initiatives/Projects, Product grouping, next Milestones, risk,
  and current attention are visible without a Notion roadmap copy.
- Product-source invalidation scenario: change an observable requirement in linked Linear/Notion
  after technical authoring and prove downstream technical work is invalidated and returned to
  shaping without publishing routine execution progress as though delivery remained valid.
- Notion content scenarios verify lazy Product Home navigation with no blank categories, required
  Decision rationale/consequences, required Knowledge problem/use/conclusion/relations, living
  updates in place, supersession links, and a Linear link/preview with no copied roadmap state.
  Every Product Decision/Knowledge fixture is created beneath Product Home and is retrievable by
  the same descendant-scoped route; Shared Knowledge remains under its separate configured root.
  Fixtures cover exact Decisions/Knowledge category parents, wrong-Product and wrong-parent
  same-title isolation, zero/one/multiple exact-parent matches, ambiguity stop without mutation,
  and Knowledge Map links targeting the canonical child.
- Disposition and recovery-copy scenarios distinguish deferred from canceled in native Linear
  outcomes and require the human recovery message to state reflected work, unapplied or unconfirmed
  work, preserved product decision, and direct resume location without connector-state language.
- Output lint: no internal markers, hashes, provider diagnostics, checkpoint JSON, raw transcripts,
  technical plan text in Linear/Notion, or duplicate roadmap state.

### Packaging and compatibility evidence

- Installed-plugin cold start imports only the small workspace-map runtime.
- Skill/reference validation covers every shipped skill after obsolete runtime removal.
- Existing active v2 tests remain green until coordinated cutover; after cutover, obsolete tests
  are removed rather than retained as compatibility requirements.
- Full unit suite, plugin validator, skill validators, compileall, and `git diff --check` pass.

### Generic cold-start pilot

- In a fresh-agent session, use a synthetic disposable-repository scenario and the packaged plugin
  to run setup discovery through its proposal boundary without external writes.
- Trace one one-sentence shaping case through its single recap approval, including planning and
  knowledge disposition, without applying real Linear or Notion changes.
- Ask planning, product-meaning, and executable-behavior questions; verify the skills require the
  mapped Linear, Notion, and Git starting routes and stop before global search when those routes
  are sufficient.
- Record concise redacted protocol outcomes, not connector payloads or claims of live execution.

The separately shaped Maio migration owns the first authorized native write/read-back and
Linear-GitHub delivery pilot. It must verify those product paths before removing repository truth;
this plugin redesign does not create disposable objects in the owner's live workspaces merely to
certify itself.

## 10. Risks and open technical questions

Risks with selected resolutions:

- **Host connector feature variance:** not every host exposes custom Linear view or Product-label
  creation. Setup uses an authenticated host browser for exact approved administrative operations
  and verifies them through semantic reads. If neither route can create a required Product label,
  setup stops before writes with one capability diagnosis; only an optional company view may use a
  concise manual handoff.
- **External partial writes:** no cross-product transaction exists. Sequential create/read-back,
  explicit completed/pending reporting, and read-before-resume provide proportionate recovery.
- **Product source edits during delivery:** technical design and conformance re-fetch the current
  Linear/Notion sources. A changed observable requirement invalidates downstream technical work and
  returns to shaping; no immutable fingerprint chain is introduced.
- **Knowledge Map drift:** every durable Decision/Knowledge write updates the Product Home or
  Knowledge Map in the same host run, and later retrieval reports a missing reciprocal navigation
  link as routine repair.
- **Large deletion diff:** inactive Phase 1–3 and unmerged Phase 4 contain substantial code and
  tests. Removal happens in isolated, reviewable commits before new behavior, with the active v2
  path verified after each deletion boundary.

Open technical questions: None.

## 11. Review evidence

Selected roles and triggers:

- `architecture`: responsibility placement moves from Python provider runtimes to skills, native
  integrations, and one small workspace map; broad compatibility and data-flow changes apply.
- `domain-data`: workspace schema and ownership, external planning/knowledge invariants, partial
  write recovery, and migration boundaries apply.
- `security-operations`: authenticated external writes, sensitive connector data, destructive
  cleanup boundaries, partial failures, rollout, and rollback apply.
- `product-conformance`: this is a product-facing story.
- `test`: required for every draft; large deletion and cross-system recovery need independent
  evidence review.

Review rounds: complete after one bounded product-decision return and iterative independent
technical review/fix/recheck rounds.

- Product decision return: the owner selected direct `Related Objective` navigation without
  Objective progress or a synthetic Project. The approved successor Product Contract supersedes
  the original; product-UX and copy critics rechecked it and reported `PASS`.
- `architecture`: resolved Product classification, hierarchy projection, recovery ownership,
  config integration, generated values, single-to-multi transition, authoritative-home routing,
  and canonical Notion containment findings; latest full recheck `PASS`.
- `domain-data`: resolved Product membership, pending-result lifecycle, idempotent recovery,
  cardinality transition, Objective-link reconciliation, and containment findings; latest affected
  recheck `PASS`.
- `security-operations`: resolved approval continuity, target scope, browser tenant proof,
  concurrency preservation, append recovery, and remote integration boundaries; latest affected
  recheck `PASS`.
- `product-conformance`: resolved recap completeness, Product-scoped retrieval, Notion information
  content, multi-product overview, meaningful updates, dispositions, and recovery copy; latest
  affected recheck `PASS`.
- `test`: expanded late-object, Git failure, browser mismatch, append ambiguity, source-change,
  authoritative-home, and Notion identity fixtures; latest affected recheck `PASS`.
- Current contract-basis revision marker:
  `sha256:ce9fa913caf310422ac380a9c355b04c87e9000043abd70f7afd85f4317310ae`.
- Superseded delivery evidence: Phase 1–3 implementation and the unmerged Phase 4 branch are
  superseded inputs, not readiness evidence for this contract.
- Plan and execution evidence: implemented as seven bounded implementation commits plus the
  current publication/acceptance diff on `feat/native-information-coordination`: minimal workspace
  map, safe anchor validation, native setup, native product-source coordination, native Story
  delivery, and obsolete runtime removal. Product Contracts and plans remained planning inputs
  rather than new runtime stores.
- Implementation and code-review evidence: independent architecture, domain/data,
  security/operations, product-conformance, test, and Task 5 code-quality reviews resolved all
  findings; the latest affected rechecks reported `PASS`.
- Post-implementation conformance: the current seven-skill inventory routes live planning to
  Linear, durable meaning to ordinary Notion pages, and executable truth to Git/GitHub. The only
  executable coordination runtime is the closed-schema workspace map; superseded provider, setup
  transaction, certification, delivery-profile, design-gate, and legacy compatibility assets are
  absent.
- Verification and acceptance evidence: 26 unit tests, compatibility validation, compileall,
  official plugin validation, and `git diff --check` passed. A fresh-agent, read-only protocol
  simulation against a synthetic disposable single-Product scenario confirmed that the packaged
  skills require setup proposal, one-recap shaping, knowledge disposition, and the mapped starting
  routes: Linear for planning, Notion for product meaning, and Git for executable behavior. It
  performed no external writes and retained no raw connector payloads or external IDs.
- Integration and closeout evidence: plugin manifests publish `0.4.0`; both final independent
  rechecks reported `PASS`; main was fast-forwarded after deterministic verification; and the
  superseded provider plus completed feature worktrees/branches were removed. Final main-branch
  verification and the release push are reported in the operator handoff rather than asserted by
  this self-referential commit.

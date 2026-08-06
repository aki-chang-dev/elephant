---
schema: elephant.story/v2
story: information-coordination
slug: one-person-company-information-coordination-v2
kind: product
status: approved
design_sensitivity: Medium
supersedes:
  - docs/superpowers/specs/2026-08-05-one-person-company-information-coordination-product.md
---

# Information coordination for a one-person company

This contract contains product decisions only. No implementation design belongs in this file.

## 1. User and context

The primary user is one product owner running a one-person company, operating one or more
products with multiple AI agents. The owner contributes product judgment during shaping. Agents
are expected to understand the existing direction, maintain planning information, carry out
delivery, and return to the owner only when product meaning must change.

The owner may begin with only a one-sentence idea. They should not need to classify it, fill in a
planning hierarchy, maintain duplicate status, or repeatedly review information that agents can
organize from already-approved context.

## 2. Problem and current experience

Product intent, planning state, delivery evidence, and long-form knowledge currently compete for
space in the code repository or remain scattered across conversations. Durable and temporary
documents are hard to distinguish. Agents may search too broadly, consume excessive context, or
lose the product direction while working on one concrete problem.

Delivery assurance can create the same burden in another form. When ordinary Stories receive the
same artifacts, reviewers, repeated context loading, and rechecks as materially risky work, the
owner waits longer and consumes more agent capacity without a corresponding quality gain.

Existing collaboration products already provide useful native planning, knowledge, preview, and
code-delivery relationships. When Elephant treats them as low-level stores, it duplicates those
capabilities, introduces machine-facing concepts, and asks the owner to support the workflow
instead of saving the owner's attention.

## 3. Desired outcome

The owner can use Linear as the live map of current and future product work, Notion as the
structured archive of durable product knowledge and decisions, and Git/GitHub as the home of
executable facts and code delivery. Elephant coordinates these systems through a small,
predictable information map and their native integrations.

The owner spends attention on product judgment. Agents infer, propose, create, link, update, and
retrieve the surrounding planning and knowledge structure without additional review gates. A
specific Story remains visibly connected to the larger product direction, relevant background,
and delivered code.

Downstream assurance is proportional to observable risk. Ordinary work follows the smallest path
that still provides independent evidence of the approved outcome and implementation quality.
Additional scrutiny appears only for a concrete risk, never merely because another review role or
artifact exists.

## 4. Experience flow

### Start from an idea

1. The owner states a one-sentence idea. No Product, Objective, Project, Milestone, or other
   planning field is required up front.
2. Elephant identifies the likely product context from the current workspace and existing work.
   It asks the owner only when the product boundary or intended outcome is genuinely ambiguous.
3. Elephant retrieves context progressively: direct Story context first, then its Project or
   Objective, then the Product knowledge map, then product-scoped search, then shared knowledge.
   Workspace-wide search is the last resort.

### Shape the product outcome and its planning position

4. The owner and Elephant discuss the user problem, desired outcome, experience, rules, and
   acceptance criteria.
5. As the idea becomes clear, Elephant decides which planning levels are useful. It may place a
   Story directly in a backlog, associate it with existing work, or propose a new Objective,
   Project, or Milestone only when the idea's real scope needs one. When an Objective is useful but
   a Project is not, the Story remains a standalone Product Story with a visible `Related
   Objective` link. It does not affect the Objective's progress until it belongs to a Project, and
   Elephant creates a Project only when it represents a real workstream.
6. Elephant assesses priority, dependencies, conflicts, and the impact of changing the current
   roadmap. It also decides whether the discussion has durable knowledge value.
7. The final shaping recap includes the product definition, recommended roadmap position,
   priority and consequences, and where any lasting result will be kept: only in Linear, saved as
   a Decision, added to Knowledge, or both.
8. The owner's approval of that recap authorizes Elephant to apply the agreed planning and
   information changes. There is no separate data-entry, roadmap, or written-spec review gate.

### Deliver and maintain the map

9. Elephant keeps routine planning facts current as work starts, becomes blocked, splits,
   completes, is deferred, or is canceled. Objective, Project, and Milestone progress is derived
   from the work represented in Linear rather than copied into Notion.
10. Product meaning, cross-objective priority, or a material change in intended outcome returns to
    the owner. Execution facts and routine updates that do not change product meaning do not.
11. Native integrations create the shortest path between systems. Notion content links to or
    previews relevant Linear work. Linear work links to relevant Notion content. Linear and
    GitHub link Stories to branches, pull requests, commits, and their delivery state.
12. When a meaningful phase change occurs, Elephant leaves a concise planning update describing
    progress, risk, and next direction. It does not generate activity reports merely to maintain
    a cadence.

### Assure delivery proportionately

13. After shaping, Elephant determines the necessary assurance depth from the approved outcome and
    current repository evidence. The owner does not classify the Story or populate a risk form.
14. Ordinary delivery receives one independent end-to-end check of the approved outcome,
    implementation quality, and verification evidence.
15. Money, destructive data change, security or authorization, concurrency or transactionality,
    production rollout or recovery, and major system-boundary risk add only the relevant specialist
    scrutiny. Uncertain risk takes the safer path and its reason is visible at closeout.
16. A fix reopens only the requirements and evidence it can materially affect. Unsupported or
    non-load-bearing findings do not expand the approved outcome.
17. Agents load and pass along only decision-relevant context. Complete product authority remains
    available whenever product conformance is being judged.

### Retrieve and review

18. Questions about current work, future plans, priorities, dependencies, or progress begin in
    Linear. Questions about product meaning, rules, or past decisions begin in Notion. Questions
    about executable behavior begin in Git.
19. A Product has a Linear planning entry and a Notion Product Home. The Notion home navigates to
    an Overview, a short Knowledge Map, durable Decisions, and the Linear planning entry. It does
    not duplicate live roadmap state.
20. With multiple products, the owner can use a lightweight company view to see active Objectives
    and Projects, next milestones, risks, and current attention across products, then enter a
    product-specific view for detail.

## 5. States and edge cases

- A single-product workspace does not need product-specific navigation or a company portfolio
  view. Those appear only when multiple products create a real navigation need.
- A small product may contain only a Product and Stories. Objectives, Projects, and Milestones
  appear independently as complexity requires them.
- An Objective may be visibly linked from a Story without a Project. The link is labeled `Related
  Objective` and provides context and navigation, but the Story does not affect Objective progress.
  A Project appears later only when the work needs a real workstream.
- An idea that does not yet fit the roadmap remains in the backlog without forced classification.
- A simple, local Story may remain entirely in Linear. Notion content is created only when the
  result retains value after that Story is complete.
- If a product boundary, strategic priority, or material roadmap change is ambiguous, Elephant
  asks one bounded product question during shaping.
- If a native Notion–Linear or Linear–GitHub integration is not configured, ordinary links remain
  usable and Elephant gives one clear configuration recommendation. Missing convenience does not
  block work.
- If unavailable information is necessary for a product decision, Elephant stops and identifies
  the missing context rather than guessing.
- If the product discussion is already complete but an external write is temporarily unavailable,
  the owner is not asked to repeat the decision. The agreed result remains pending until it can be
  reflected in the intended system. Recovery feedback states what was applied, what remains
  unapplied, that the product decision is preserved, and the direct action or location for
  resuming.
- Conflicting product meaning is surfaced for owner judgment. Elephant may repair navigation or
  presentation links, but does not silently change an approved product conclusion.
- An ordinary Story does not inherit additional review layers merely because those roles exist.
- If material delivery risk is present, Elephant names the risk and adds the applicable scrutiny.
  If risk is uncertain, it uses the safer depth without asking the owner to classify the work.
- A review fix causes only materially affected results and evidence to be checked again.

## 6. Information and copy

### Information hierarchy

- Linear uses human planning concepts: Product view, Objective, Project, Milestone, Story, and
  Backlog. Cycle is an optional execution cadence, not a required planning level.
- A `Related Objective` link says only that the Objective is relevant context. The Story affects
  Objective progress only after a real Project relationship exists.
- Notion uses human knowledge concepts: Company Knowledge, Product Home, Overview, Knowledge Map,
  Knowledge, Decisions, and Shared Knowledge.
- Elephant keeps a small, stable map of entry points and relationships, not copies of planning
  state or document bodies.
- The Knowledge Map contains a human-readable title, one sentence describing the question each
  item answers, and a link. Knowledge pages state what problem they address, when they are useful,
  the current conclusion, and related knowledge or decisions.

### User-facing language

- Titles and explanations describe product outcomes and user-visible behavior. Internal slice
  identifiers, hashes, fingerprints, replay state, provider vocabulary, and implementation
  progress never appear in user-facing planning or knowledge content.
- Agent summaries lead with the decision, recommendation, consequence, or next product question.
  They do not present fields for the owner to populate when context allows the agent to infer or
  propose the answer.
- Delivery closeout names any exceptional assurance escalation and its concrete reason. It does
  not expose reviewer choreography or use review count as a proxy for quality.
- Integration failure guidance names the missing convenience or context and the next available
  action. It does not expose connector internals.

## 7. Product rules and defaults

1. Linear is the only live planning and progress view. Notion does not reproduce a roadmap or
   Story state dashboard.
2. Notion stores valuable, systematized product knowledge and decisions, not raw conversations,
   routine delivery logs, implementation plans, review history, test output, or checkpoints.
3. A shaping result may stay only in Linear, create a durable Decision, update living Knowledge,
   or do both. Elephant chooses according to future product value and explains that disposition in
   the shaping recap as a concrete choice: keep it only in Linear, save a Decision, add it to
   Knowledge, or do both.
4. Planning structure is progressive. Product and Story are sufficient by default; every higher
   level must express a real planning need.
5. Planning structure is an output of shaping, not required input. The owner can always begin with
   one sentence.
6. A Story may link directly to a relevant Objective without a Project, but it does not affect
   Objective progress. Elephant creates a Project only when it represents a real workstream.
7. Shaping recap approval authorizes the agreed roadmap, relationship, and knowledge updates.
8. Routine facts are maintained automatically. Only changes in product meaning require renewed
   owner judgment.
9. Native integration comes first. Elephant prefers the connected products' native relationships,
   previews, and status updates instead of creating competing copies.
10. Product-specific navigation appears only for multi-product work. A single-product repository
    is not burdened with empty portfolio structure.
11. Setup establishes the smallest usable information space. It does not pre-create future
    Objectives, Projects, Milestones, knowledge categories, or a universal Notion database.
12. Retrieval narrows before it expands. Direct relations and product-scoped maps precede global
    search.
13. One fact has one primary home. Cross-system links and previews are navigation, not competing
    copies.
14. Review count is not a quality measure. Ordinary work receives one independent end-to-end
    delivery review; extra reviews require a named observable risk.
15. The owner never supplies a technical risk classification and receives no new downstream review
    gate.
16. Context expands only when the current decision cannot be supported, and each reviewer receives
    only the context needed for its question.
17. Rechecks cover only materially affected requirements and evidence.
18. Token economy does not use hard quotas that could truncate decision-critical context, and
    parallel agents are not counted as token savings merely because they reduce elapsed time.

## 8. Product acceptance criteria

- The owner can begin shaping with one sentence and is not asked to classify the idea before the
  discussion establishes its meaning.
- The final shaping recap explains the intended user outcome, roadmap position, priority,
  dependencies, consequences for existing plans, and whether lasting information stays only in
  Linear, becomes a Decision, is added to Knowledge, or both.
- Approving the recap is sufficient for agents to create or update the agreed planning structure
  and links without another owner review.
- A single-product workspace remains usable with only Product, Backlog, and Stories; a mature or
  multi-product workspace can add Objectives, Projects, Milestones, product views, and a company
  overview without changing the underlying workflow.
- Linear can answer what is planned, what is active, what is blocked, what comes next, and why a
  specific Story belongs in the roadmap.
- Notion can answer what a product is, what its current rules mean, and why an important product
  decision was made, without exposing a duplicate live roadmap.
- When a Story has a relevant Objective but no useful Project, it shows a `Related Objective` link,
  does not affect Objective progress, and does not cause Elephant to create a Project.
- An agent can navigate from the current Story to its applicable Objective, Project, Milestone,
  relevant Notion context, and linked GitHub delivery without a workspace-wide search.
- A user can navigate from a Notion decision to current Linear work, from Linear work to relevant
  product knowledge and code delivery, and from a linked GitHub pull request back to its Story.
- Simple Story completion does not automatically create a Notion document. Durable product
  meaning is incorporated into the appropriate knowledge or decision location.
- Missing native previews or code integrations degrade to ordinary links with clear guidance;
  missing decision-critical context is surfaced rather than guessed.
- Progress and planning updates reflect meaningful changes and do not become periodic activity
  logs.
- A normal Story completes with one independent end-to-end delivery review plus appropriate
  repository verification, without automatically invoking every available review layer.
- A materially risky Story receives the applicable additional scrutiny, and closeout states why it
  was necessary.
- Review work does not repeatedly consume unrelated product or repository context, and a finding
  reopens only the scope its resolution can affect.
- Product shaping depth, one approval, high-risk protection, and return for changed product meaning
  remain intact while ordinary delivery becomes faster and less token-intensive.
- Successful routine coordination leaves no temporary recovery artifact in Git.

## 9. Out of scope

- Multi-person approval chains, departmental planning, staffing, budgets, and enterprise resource
  management.
- A hosted synchronization service, background polling system, or duplicate cross-system state
  store.
- A mandatory universal hierarchy for every product.
- Replacing Linear's roadmap, issue workflow, or GitHub integration with Elephant-owned versions.
- Replacing Notion search or navigation with an Elephant content database.
- Preserving raw chats, transient technical contracts, implementation plans, routine review
  evidence, or delivery checkpoints as long-term product knowledge.
- The concrete migration and cleanup of Maio content. Migration will apply this approved product
  model in a separate bounded effort.
- Detailed implementation choices, connector tool vocabulary, storage formats, retries, locking,
  fingerprints, or certification protocols.
- Eliminating independent review, weakening material-risk safeguards, imposing fixed token quotas,
  or building a usage-telemetry platform.

## 10. Open product questions

None.

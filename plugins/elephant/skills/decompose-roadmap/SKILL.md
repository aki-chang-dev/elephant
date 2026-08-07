---
name: decompose-roadmap
description: Use when current Product meaning needs to become or refresh a value-sequenced, dependency-aware native Linear planning map.
---

# Decompose Roadmap

## Purpose

Turn current Product meaning into the smallest useful Linear map of future work. A roadmap is the
native view of outcomes, priorities, dependencies, and sequence—not a Git document and not a fixed
hierarchy. Product and Story are sufficient until a real objective, workstream, or milestone makes
another level useful.

Before acting, read completely:

- `../../references/information-routing.md`
- `../../references/linear-planning.md`

Use `information-routing.md` to read current Notion meaning. This skill does not load the Notion
write protocol because it writes planning only to Linear.

## Load current authority without writes

Resolve Product, then fetch current Product Home/Overview and directly relevant durable meaning,
plus Product-scoped Linear backlog, Initiatives, Projects, Milestones, Stories, priorities,
dependencies, blockers, and current phase updates. Verify workspace/Team/Product ownership.

If product meaning is insufficient to choose outcomes or boundaries, return the bounded gap to
`author-product-spec` or `shape-story`; do not invent it from repository structure. Existing native
objects are planning truth to reuse, update, relate, or explicitly leave unchanged.

## Build a progressive proposal

Map the user's journey into coarse, independently valuable outcomes. Prefer vertical, demoable
Stories and early end-to-end value. Use walking-skeleton or phased thinking only when it genuinely
clarifies sequence; do not impose a phase model on a small or mature product.

Choose each native level by meaning:

- **Story/Backlog:** default. A useful outcome may remain standalone and unscheduled.
- **Project:** only for a real workstream coordinating multiple Stories toward one bounded result.
- **Milestone:** only within a Project when a meaningful intermediate outcome helps navigation,
  sequencing, or commitment.
- **Objective/Initiative:** only for a strategic outcome that usefully groups one or more Projects.
- **Cycle:** optional execution cadence, never required roadmap structure.

An Objective relevant to a standalone Story uses `Related Objective` without a synthetic Project or
progress attribution. Product membership remains implicit for one Product and uses each native
label namespace for multiple Products.

For every proposed object or relation, state:

- human outcome/title and concise purpose;
- existing/reuse, create, update, or unchanged;
- parent/containment or deliberate standalone placement;
- priority and why it earns current attention;
- dependencies, conflicts, and blockers;
- observable completion/result at the appropriate level;
- consequence for existing work, including displacement, delay, split, or no impact.

Keep Stories coarse enough for later shaping, while still describing one user-visible outcome.
Never derive one Story per entity, package, layer, or CRUD surface. Do not assign Elephant slice IDs;
Linear owns identifiers.

## One roadmap recap and approval

Present one compact human roadmap recap:

1. Product direction and ordering principle;
2. current native structure being preserved;
3. Initiatives, Projects, Milestones, and Stories to create/update/reuse, with omitted levels clear;
4. backlog/current attention and native priority;
5. dependencies, conflicts, and roadmap consequences;
6. deferred/out-of-scope outcomes and their reconsideration conditions;
7. exact Linear objects, relations, labels, statuses, and any first-use label activation/config
   update approval will apply;
8. unresolved product questions.

Resolve material questions before recap. Wait for one explicit approval of the complete proposal.
That approval authorizes the displayed Linear operations. Do not ask the owner to review a generated
roadmap or approve data entry afterward.

## Apply directly to Linear

Use native Linear operations and `linear-planning.md` recovery rules:

1. Re-fetch current scoped objects and semantic preconditions.
2. Before the first Project or Initiative write for a Product with no matching configured label,
   run one bounded `setup-workspace` refresh under this recap's approval: search/reuse or provision
   the exact native label, persist its verified label ID in `.agents/elephant/workspace.yaml`,
   integrate the config, and re-read the valid map before the first object write. If provisioning
   or semantic verification is unavailable, leave that planning level inactive and stop its write.
3. For each approved target, search its exact native scope. Reuse/update one equivalent object,
   create when none exists, and stop on multiple/conflicting matches.
4. Apply Initiatives, then Projects and their Team sets, then Milestones, Stories, relations,
   priority, and statuses in dependency-safe order. Preserve unrelated labels, relations, and text.
5. Read every mutation back and verify ownership, content, containment, Product classification, and
   no-progress `Related Objective` semantics.
6. For meaningful existing Project/Initiative phase changes, write one concise progress/risk/next
   direction update. Initial creation text belongs in the object description, not an activity log.

If a write is rejected or indeterminate, reconcile exact native scope and preserve the approved
result without creating duplicates. Resume without another owner decision when meaning and
preconditions remain unchanged; changed product meaning requires a revised recap. Never delete or
roll back user-owned planning content automatically.

## Completion

Re-fetch the Product planning scope and return direct links to backlog, current attention, created
or updated Initiatives/Projects/Milestones/Stories, and any deferred work. Completion may be only
Product + Backlog + Stories. Create no Git roadmap, change log, phase table, or parallel Story
registry.

## Red flags

- Existing Linear objects are copied into a document instead of reused.
- A planning level is created because the template has a slot for it.
- Repository packages/entities become horizontal Stories.
- Product meaning is invented to fill a planning gap.
- Approval is split into phase, slice, and final-document reviews.
- A roadmap file or custom Story ID scheme becomes required for delivery.

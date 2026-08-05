---
name: kickoff
description: Use when a one-sentence product idea or partially initialized repository needs the minimum product foundation, native Linear planning, and workspace map required for ship-story.
---

# Kickoff

## Purpose

Bootstrap or resume a product until current product meaning is navigable in Notion, current/future
work is navigable in Linear, and `.agents/elephant/workspace.yaml` connects those entry points to the
repository. Kickoff is a thin semantic orchestrator: it detects the first incomplete product result
and delegates it without recreating another skill's conversation or write protocol.

Required skills, in outcome order:

1. `elephant:author-product-spec` — establish or refresh only the durable product foundation that is
   currently useful;
2. `elephant:decompose-roadmap` — create or refresh the useful native Linear planning structure;
3. `elephant:setup-workspace` — validate and persist the final Product/domain entry-point map.

There is no extra project-profile phase and no Git spec-system or roadmap-file completion
requirement.

## Discover current outcomes without writes

Accept the owner's one-sentence idea without requiring Product or planning fields. Read repository
instructions and context, available Linear/Notion/Git integrations, an existing workspace map when
present, and the narrowest native structures related to the idea.

Keep product identity separate from engineering domains. When no workspace map exists, carry the
verified Linear workspace/Team, Notion root/Product Home, repository, and Product candidate as
in-session discovery context; `setup-workspace` owns the final proposal and config.

Evaluate these outcomes in order:

1. **Product foundation:** Is there sufficient current Product Home/Overview and linked durable
   meaning to explain the product, audience, problem, outcomes, boundaries, and important rules?
2. **Planning map:** Can Linear show the current useful backlog and any justified Objectives,
   Projects, Milestones, dependencies, priorities, and roadmap direction for this Product?
3. **Workspace entry points:** Does a valid workspace-v4 map resolve the repository, Product,
   engineering domains, Linear Team/planning/backlog, and Notion root/Product Home without stale or
   wrong-scope anchors?

Existing but partial native content is the current phase, not absence and not completion. Determine
what it already answers, what remains materially missing, and pass both to the owning skill. Do not
ask the owner whether an artifact “looks complete” when native content can answer the question.

## Resume the first incomplete outcome

Dispatch only the first incomplete outcome:

- incomplete product foundation → `elephant:author-product-spec` with the one-sentence idea,
  discovered Product context, and existing Product Home/Knowledge content;
- sufficient foundation but incomplete planning map → `elephant:decompose-roadmap` with the current
  product sources and existing scoped Linear planning;
- sufficient foundation/planning but missing or stale entry-point map →
  `elephant:setup-workspace` with the verified in-session scopes and outputs;
- all three complete → report ready for `elephant:ship-story` with direct Product, Linear backlog/
  planning, and Notion Product Home links.

After a delegated skill completes its own approved native apply/read-back, immediately re-read the
next outcome and continue within the same kickoff request. Do not add a seam checkpoint, a written
artifact review, or a “proceed to the next phase?” question. Owner attention remains inside each
sub-skill only where product meaning actually needs approval.

Carry native identities and links forward in-session. Across sessions, rediscover them from the
workspace map and authoritative systems rather than relying on prior chat or Git inception files.

## Completion

Kickoff is complete only when:

- current durable product meaning is findable from Product Home;
- current/future work and backlog are findable from Product-scoped Linear planning;
- workspace v4 resolves Product and engineering domains plus verified Linear/Notion/Git entry
  points;
- no blank future planning levels or knowledge categories were created merely for completeness.

Return those direct links and the first useful next Story. Do not create or retain a kickoff log.

## Red flags

- Git document presence substitutes for reading current Linear/Notion truth.
- An existing Product Home or Linear hierarchy is ignored and rebuilt.
- Kickoff authors product content, roadmap objects, or workspace config itself instead of
  dispatching the owner skill.
- An obsolete project-specific delivery workflow or compatibility mode appears.
- Another approval is requested between completed native outcomes.
- Completion is declared without a valid workspace map and resolvable native entry points.

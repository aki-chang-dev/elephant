---
name: shape-story
description: Use when a one-sentence idea or existing Story may change a user experience, user-visible behavior, copy, feedback, recovery, business outcome, or expectation and needs product shaping before technical design.
---

# Shape Story

## Purpose

Turn one sentence into an approved user outcome, its useful planning position, and a deliberate
knowledge disposition. The owner participates deeply in this product conversation. After one recap
approval, Elephant applies the displayed Linear and Notion changes without another review gate.

Run this skill in the main conversation. Before acting, read completely:

- `../../references/information-routing.md`
- `../../references/linear-planning.md`
- `../../references/notion-knowledge.md`
- `product-contract-template.md`

The bundled template is a working recap shape, not a durable repository Product Contract. Keep the
working draft in conversation until approval. Git contains only a short-lived recovery note while
approved native writes are being applied.

## Start from the idea and current truth

Accept free-form input; never ask the owner to classify the idea or populate planning fields first.
Resolve Product and retrieve current context through `information-routing.md`:

1. start with the supplied or likely Linear Story and its direct planning relations;
2. follow directly linked Notion context before any broader search;
3. expand only through the Product-scoped route until the product question is answerable;
4. name missing decision-critical context instead of guessing.

Classify the change only after understanding it:

- **Product-facing:** changes what a user can accomplish, experience, understand, recover from, or
  reasonably expect, including invisible behavior with a user or business consequence.
- **Engineering-only:** user and business outcomes are demonstrably unchanged.
- **Ambiguous:** shape as product-facing.

For engineering-only work, return the evidence-backed classification and current source links to
the caller without inventing product requirements.

When technical delivery returns a product-decision question, fetch the current Linear Story and
linked Notion pages again, shape only the bounded decision and the follow-ups needed to keep the
whole user outcome coherent, and apply the approved source updates through this same flow. Do not
create a successor file. A changed observable requirement invalidates downstream technical work.

## Product conversation

Ask one question at a time and only about product meaning:

- user, context, and current experience;
- problem, desired user outcome, and business consequence;
- entry point, primary flow, branches, exit, and recovery;
- defaults and user-visible rules;
- loading, empty, error, disabled, partial-success, and success states;
- information hierarchy and decisions the user must make;
- labels, hints, placeholders, confirmations, feedback, and error copy;
- observable acceptance and explicitly unchanged or out-of-scope behavior.

Translate technical-looking owner language into observable outcomes before asking or writing.
Exact critical copy stays exact; flexible supporting copy records intent and tone. Record a hard
feasibility concern as something technical design must validate, never as permission to silently
weaken the desired outcome.

Do not discuss endpoints, storage fields, modules, libraries, migrations, internal enums, test
structure, or implementation sequence. Those belong to technical design after shaping.

## Organize the planning and knowledge result

As product meaning becomes clear, inspect current Linear relationships and propose only the
planning structure the work actually needs:

- Product backlog Story by default;
- existing or new Objective, Project, or Milestone only when it expresses a real planning need;
- `Related Objective` when an Objective is relevant but no real Project exists, explicitly leaving
  Objective progress unchanged;
- native priority, dependencies, conflicts, and relations that follow from the shaped outcome.

Assess and state all of the following even when the result is `none`: dependencies, conflicts,
priority impact, and roadmap consequences. Explain whether the work displaces, delays, splits, or
changes existing plans. Ask one bounded owner question only for a real product tradeoff or unclear
Product boundary.

Choose one knowledge action based on future product value:

- `linear_only`: the result is sufficiently expressed by this Story and will not remain useful
  independently;
- `decision`: preserve why a durable product choice was made;
- `knowledge`: create or update living guidance that will answer future product questions;
- `decision_and_knowledge`: both the choice and the reusable current guidance have durable value.

Name the concrete Decision or Knowledge target in the recap. Do not archive the conversation,
implementation plan, review, test output, or routine progress.

## Critique and resolution

Before recap approval, run both canonical read-only critics with the latest working recap and the
fetched Linear/Notion product context:

1. `reviewers/product-ux-critic.md`
2. `reviewers/copy-critic.md`

They report findings and never edit the recap or invent product decisions. Deduplicate findings,
apply clear product/copy fixes as the author, and rerun each affected critic. Ask the owner one
question at a time only when a finding genuinely requires product judgment.

## One shaping recap and approval

When critic findings are resolved, present exactly one human-readable recap using the bundled
template. It must include:

1. user, current problem, desired outcome, and business consequence;
2. experience flow, states, recovery, information, and copy;
3. rules, observable acceptance, and out of scope;
4. Product and proposed Story identity;
5. Objective/Project/Milestone placement, including which objects are existing, new, or omitted;
6. dependencies, conflicts, priority impact, and roadmap consequences;
7. knowledge action and exact target, or `linear_only`;
8. open product questions;
9. proposed disposition: `approved`, `split`, `deferred`, or `rejected`;
10. the exact human-visible Linear and Notion changes approval will apply.

A recap is not approval. Wait for the owner to explicitly confirm its proposed disposition. This is
the sole product approval gate. Do not ask the owner to review a generated file or approve data
entry afterward. `approved` requires no open product questions. For `split`, `deferred`, or
`rejected`, include the product rationale and next condition plus any displayed native effects.

## Apply the approved result

After approval and before the first external write, create a non-main operation branch. Commit one
short-lived `pending-application.md` containing the approved outcomes, resolved target scopes, and
semantic preconditions. Publish it when a configured remote is available; otherwise state that
recovery is limited to this working copy. The note aids read reconciliation and never authorizes a
cold device to write.

Apply only the recap's displayed changes:

1. Create, reuse, or update the justified Linear Initiative, Project, Milestone, and Story through
   native operations, omitting every unnecessary level. Preserve unrelated fields and relations.
2. Apply native priority, dependencies, conflicts, and disposition effects. Deferred work remains
   visible with its next condition; canceled work preserves its product rationale. Create child
   Story seeds for a split only when the recap displayed them.
3. Put the concise user problem, desired outcome, observable acceptance, and durable context links
   in the Story. Do not put implementation progress or Elephant metadata there.
4. For direct Objective placement without a Project, add the visible Initiative URL under the
   exact label `Related Objective` and verify that the Story does not affect its progress.
5. Apply the approved Notion action under the exact Product Home parent, lazily creating only the
   required category, then maintain the short Knowledge Map and ordinary reciprocal links.
6. Re-fetch every affected object and verify ownership, visible content, native relations, and
   source links.

Follow the recovery rules in `linear-planning.md` and `notion-knowledge.md`. If a write is
unavailable or uncertain, reconcile native truth, keep the unchanged pending note, and report what
is already visible, what remains unapplied or unconfirmed, that the product decision is preserved,
and the direct resume action. Do not repeat owner approval unless the intended product outcome or a
semantic precondition changed. Never automatically delete or roll back user content.

When all outcomes read back correctly, delete the pending note and operation branch. Return the
current Linear Story URL plus every linked Notion source URL as the authoritative product-source
bundle for technical design. No permanent shaping artifact remains in Git.

## Red flags

- The owner is asked to supply Objective, Project, Milestone, priority, or knowledge fields before
  the idea is understood.
- A question asks how the system will be built rather than what the user experiences.
- Optional planning levels are created merely to complete a hierarchy.
- Notion receives a roadmap copy or low-value delivery history.
- A link or stale preview substitutes for missing authoritative context.
- Approval leads to another roadmap, document, or data-entry review gate.
- A Product Contract or shaping log remains in the repository after native write-back.

Return to the product conversation and recap when any red flag appears.

---
name: shape-story
description: Use when a coarse roadmap story may change a user experience, user-visible behavior, copy, feedback, recovery, business outcome, or expectation and needs a product contract before technical design.
---

# Shape Story

## Overview

Turn one coarse roadmap story into one product-only contract through continuous product-owner
conversation. Run this skill in the main conversation. The only terminal dispositions are
`approved | split | deferred | rejected`.

## Inputs and output

Load the roadmap seed, global product specs, current experience in the product, and applicable
research under the repository's research policy. When called by `elephant:ship-story`, use its
caller-supplied Product Contract template and caller-supplied Product Contract output path
exactly; do not replace configured profile values with bundled conventions. When those inputs are
omitted for a standalone invocation, use bundled `product-contract-template.md` and
`<ID>-<slug>-product.md`.

The output uses `schema: elephant.story/v2`. Keep `design_sensitivity: High | Medium | Low` solely
as the unchanged design-gate adapter; it is not implementation design. Writers emit
`supersedes` as a canonical list of repository-relative POSIX paths, using `[]` for no
predecessor.

Before drafting, classify the story:

- **Product-facing:** it changes what a user can accomplish; a flow, default, or result;
  information, UI, copy, status, feedback, recovery; or invisible behavior that changes a user
  expectation or business outcome.
- **Engineering-only:** user and business outcomes are demonstrably unchanged.
- **Ambiguous:** treat it as product-facing.

For engineering-only work, return that classification to the caller without inventing a Product
Contract. Otherwise persist a `status: shaping` draft early and update it as decisions land so an
interrupted conversation can resume from section 10.

### Decision-return revision

When the caller supplies a `needs-product-decision` brief against an approved Product Contract,
do not edit that approved file. Create a `status: shaping` successor at the caller-supplied output
path. Use the repository's normal Product Contract versioned-slug convention; when none exists,
append `-v<N>` to the prior slug using the lowest unused integer starting at 2, then render that
slug through the caller's filename rule.

The successor's `supersedes` list copies every normalized predecessor entry and adds the
repository-relative path of the approved predecessor. Ask only the bounded product question plus
follow-ups required to make the answer coherent with the whole contract. Run the normal critics
and recap. Only the owner's explicit disposition persists the successor as approved, split,
deferred, or rejected. This versioned successor rule preserves the approved predecessor and makes
interrupted return detection mechanical.

## Product conversation

Ask one question at a time. Ask only about:

- user, context, and current experience;
- problem and desired outcome;
- entry point, primary flow, branches, exit, and recovery;
- defaults and user-visible rules;
- loading, empty, error, disabled, and partial-success states;
- information hierarchy and decisions the user must make;
- labels, hints, placeholders, confirmations, feedback, and error copy;
- product acceptance criteria and out-of-scope behavior.

Translate technical-looking owner language into an observable product category and outcome before
asking or writing. For a copy/reuse boundary, fill these product slots:

1. User-owned setup the user expects to carry over, named as visible product capabilities.
2. New-item identity, history, access, and operational state that must remain new or uncopied,
   named as user-observable categories.
3. Technical mapping explicitly deferred to the later technical contract.

Shape the contract through the ten required sections. Implementation design—endpoints, fields,
modules, libraries, migrations, tests, internal enums, and implementation sequencing—belongs to
the later technical contract, not the questions or artifact. Record a hard feasibility constraint
only as a later validation need; do not silently weaken the desired outcome.

Critical user-facing copy is exact. Intentionally flexible supporting copy records intent and
tone.

## Critique and resolution

Before the Product Contract Recap, run both canonical read-only roles with the latest draft and
relevant product context:

1. `reviewers/product-ux-critic.md`
2. `reviewers/copy-critic.md`

Independent workers may run the roles concurrently. If worker delegation is unavailable, run the
same prompts sequentially in the main conversation. Both modes use identical inputs, output
contracts, and pass criteria. The bundled prompts are the canonical Elephant assets; host-native
agents are optional adapters.

The critics report findings; they never edit the Product Contract or invent product decisions.
Deduplicate findings. Apply clear contract or copy fixes as the author/fixer, then have each
affected critic recheck. Ask the owner one question at a time only for findings that require
product judgment.

## Recap and terminal disposition

When there are no unresolved critic findings, present exactly one Product Contract Recap with
these slots:

1. User, problem, and desired outcome
2. Experience flow, states, and recovery
3. Information, exact critical copy, and flexible-copy intent
4. Product rules, defaults, and acceptance criteria
5. Out of scope
6. Design sensitivity
7. Open product questions
8. Proposed disposition: `approved`, `split`, `deferred`, or `rejected`

A recap is not approval. Wait for the owner to explicitly confirm its proposed disposition.

- **`approved`:** require no open product questions, synchronize the approved recap into the
  contract, set `status: approved`, and return control to the caller. All later technical agents
  and reviewers treat the approved contract as read-only.
- **`split`:** set `status: split`, record the product rationale and next condition plus any
  applicable child product seeds, then stop.
- **`deferred`:** set `status: deferred`, record the product rationale and next condition, then
  stop.
- **`rejected`:** set `status: rejected`, record the product rationale and next condition, then
  stop.

Do not ask the owner to reread the written file or add a second written-spec review checkpoint.
The explicitly approved Product Contract Recap is the product approval gate.

## Red flags

- A question asks how the system will be built rather than what the user experiences.
- Schedule or authority pressure turns the recap into implicit approval.
- A label such as “ready,” “cancelled,” or “parked” becomes a hidden fifth disposition.
- A critic edits the contract instead of returning findings for the author/fixer.
- Worker and sequential review paths use different contracts or standards.

Return to the product conversation and the required output slots when any red flag appears.

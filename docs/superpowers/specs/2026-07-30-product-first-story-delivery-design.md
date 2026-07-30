# Elephant Product-First Story Delivery Design

**Date:** 2026-07-30
**Status:** Approved for implementation planning

## Goal

Make Elephant suitable for continuous product development in mature products. A coarse roadmap
story or newly proposed feature must be shaped from the user's perspective before design or
engineering begins. The product owner participates deeply in that shaping conversation once; the
remaining technical design, review, implementation, and verification flow is agent-owned unless a
new product decision or high-risk authorization is required.

## Problem

Elephant currently treats product discovery as an inception concern:

```text
idea → kickoff → global specs → roadmap → ship-story → engineering delivery
```

That works for greenfield product creation, but a mature product continues to receive local ideas
after kickoff. Those ideas enter `ship-story` as one-line roadmap stories that have not necessarily
been validated or expanded into complete product behavior.

The current `ship-story` phase compounds the problem:

- it dispatches `superpowers:brainstorming`, whose design output includes architecture,
  components, data flow, error handling, and testing;
- it writes one mixed slice spec containing engineering and UX guidance;
- the Engineering Brief precedes the Design Brief;
- brainstorm is treated as the review, and the mixed spec is immediately marked `Refined`;
- the story has no formal product disposition other than continuing toward implementation.

This structure encourages implementation concepts, field names, internal states, and delivery
progress to leak into user experience and copy.

## Principles

1. **A roadmap story is a product hypothesis, not an engineering commitment.**
2. **Product and technical design are separate contracts with separate authority.**
3. **The product owner approves product meaning once, in the shaping conversation.**
4. **Writing the approved contract to disk does not create a duplicate review checkpoint.**
5. **Technical agents may optimize implementation but may not silently change product outcomes.**
6. **Specialist review is a runtime-neutral role prompt plus a bounded task packet.**
7. **Parallel workers improve speed and isolation; correctness must have a sequential fallback.**
8. **Existing mixed specs remain resumable without forced migration.**

## Scope

This change adds:

- story triage;
- a product-focused `elephant:shape-story` skill;
- an agent-owned `elephant:author-technical-contract` skill;
- separate product and technical contract templates;
- canonical reviewer role prompts;
- product and technical state machines;
- v2 artifact detection and legacy mixed-spec compatibility;
- delivery-profile support for the dual-contract artifact model;
- static validation and cross-runtime smoke cases.

## Out of Scope

- redesigning `kickoff` or the global spec system;
- defining a universal design-system or experience-specification protocol;
- changing design providers, approval semantics, or the human ready signal;
- generating an agent-assisted visual design provider;
- migrating existing mixed specs in bulk;
- changing Superpowers itself.

The existing design gate receives only the minimum compatibility adaptation needed to consume an
approved product contract instead of mixed-spec §6/§7. A separate design will revisit the gate.

## Artifact Model

### Product-facing story

```text
<ID>-<slug>-product.md
<ID>-<slug>-technical.md
```

`product.md` is authoritative for user-visible meaning and outcomes. `technical.md` is
authoritative for implementation contracts and must reference the approved product contract.

### Engineering-only story

```text
<ID>-<slug>-technical.md
```

An engineering-only story must be behavior-preserving: refactoring, tests, CI, tooling,
observability, infrastructure maintenance, or performance work that does not change user outcomes.
Uncertainty fails safe to product-facing.

### Product status

```text
shaping → approved | split | deferred | rejected
```

- `approved`: continue automatically.
- `split`: stop the original story and propose smaller candidate stories.
- `deferred`: record why and the condition for reconsideration.
- `rejected`: record why no delivery work should follow.

### Technical status

```text
draft → ready → implementing → done
          ↘
       needs-product-decision
```

`needs-product-decision` is the only technical-state escalation to the product owner. It is used
when feasibility, risk, or conflicting requirements require a change to `product.md`.

## Story Triage

`ship-story` classifies a story before producing a contract.

A story is product-facing when it changes any of:

- what a user can accomplish;
- the flow, defaults, or result of an existing task;
- information the user sees, interprets, or acts on;
- UI, copy, status, feedback, or error recovery;
- invisible behavior that changes a user expectation or business outcome.

A story is engineering-only only when user and business outcomes are demonstrably unchanged.
Ambiguous stories are product-facing. The main agent records the classification in the first v2
artifact; it does not ask the owner unless the available story and repository context genuinely
support conflicting classifications.

## `elephant:shape-story`

### Responsibility

Expand one coarse user story into an approved Product Contract. This is local, continuous product
discovery; it does not restart kickoff or redefine the whole product.

The skill runs in the main conversation because it requires deep product-owner participation.
It borrows useful dialogue discipline—one question at a time, bounded research, alternative
approaches, explicit confirmation—but does not invoke `superpowers:brainstorming`.

### Allowed discussion

- user, context, and current experience;
- problem and desired outcome;
- entry point, primary flow, branches, exit, and recovery;
- defaults and user-visible rules;
- loading, empty, error, disabled, and partial-success states;
- information hierarchy and decisions the user must make;
- labels, hints, placeholders, confirmations, feedback, and error copy;
- product acceptance criteria and out-of-scope behavior.

### Excluded before approval

- endpoints, tables, fields, and wire names;
- modules, components, libraries, and frameworks;
- migrations and implementation sequencing;
- test implementation;
- internal enums and state-machine vocabulary.

A hard feasibility constraint may be recorded for later technical validation, but it may not be
used to silently weaken the desired product outcome.

### Product critique before approval

Before the final recap, the parent dispatches the applicable read-only product/UX and copy critic
roles. Without worker delegation it runs the same role prompts sequentially. The parent
deduplicates their findings and asks only the unresolved product questions, one at a time.

The final Product Contract Recap is the approval gate. On explicit approval, the agent synchronizes
the contract, clears open product questions, marks it `approved`, and continues. The owner is not
asked to reread the written file.

### Product contract structure

1. User and context
2. Problem and current experience
3. Desired outcome
4. Experience flow
5. States and edge cases
6. Information and copy
7. Product rules and defaults
8. Product acceptance criteria
9. Out of scope
10. Open product questions (empty at `approved`)

Drafts may be persisted with status `shaping` for cross-session recovery.

## Existing Design Gate Compatibility

For v2 product-facing stories:

- the current sensitivity signal moves to product-contract metadata;
- `approved product.md` is the gate's durable input instead of a `Refined` mixed spec;
- the handoff maps screens, states, interactions, and transitions to the Product Contract;
- provider selection, artifact directory, `design-handoff.md`, commit/push behavior, and human
  ready signal remain unchanged;
- the later Technical Contract consumes both the Product Contract and handoff.

No broader design-gate behavior changes in this release.

## `elephant:author-technical-contract`

### Responsibility

Turn an approved Product Contract—or a triaged engineering-only story—into an
implementation-ready Technical Contract without another routine owner checkpoint.

The technical author consumes current code, global specs, repository instructions, decision
records, applicable design handoff, and authoritative external documentation. It may select
implementation details, but it cannot edit the Product Contract.

### Technical contract structure

1. Product-contract binding
2. Current-system context
3. Technical scope
4. Domain and data contracts
5. Interfaces and data flow
6. Product-state implementation
7. Security, privacy, and operational behavior
8. Compatibility and migration
9. Verification strategy
10. Risks and open technical questions
11. Review evidence

Every product requirement maps through a traceability table:

| Product contract item | Technical response | Verification |
|---|---|---|
| User-visible outcome or state | Mechanism that supports it | Evidence that proves it |

Technical questions must be empty before status `ready`. A product question changes the status to
`needs-product-decision` instead of being answered by an engineering agent.

## Specialist Review

Reviewer roles are canonical prompt templates owned by Elephant, not host-specific agent
identities. Each prompt defines:

- role and boundary;
- required inputs;
- evidence and severity requirements;
- output shape;
- escalation rules;
- read-only behavior.

The runtime adapter executes the role with an isolated worker when available. Claude Code may
optionally expose thin plugin-agent wrappers; Codex may use spawned or configured custom agents.
Those adapters are not the source of truth. A host without workers runs the same prompts
sequentially in the parent.

Roles include:

- product/UX critic;
- copy critic;
- architecture reviewer;
- product-conformance reviewer;
- domain/data reviewer;
- security/operations reviewer;
- test reviewer.

Selection is risk-based. A copy-only change does not need data and operations review; schema,
money-path, tenant, credential, or production changes receive the relevant specialists.

Reviewers stay read-only:

```text
author draft → reviewers find evidence-backed issues → author/fixer updates
→ affected reviewers recheck → no blocking findings → ready
```

This preserves reviewer independence and avoids concurrent writes. Findings must cite a violated
contract or concrete risk; vague suggestions do not block readiness.

## `ship-story` v2 Orchestration

```text
detect/resume
→ triage
→ [product-facing] elephant:shape-story
→ approved product contract
→ existing design gate when applicable
→ elephant:author-technical-contract
→ specialist review/fix/re-review
→ ready technical contract
→ superpowers:writing-plans
→ isolation + implementation + code review
→ product/technical conformance review
→ integration + closeout
```

The v2 path does not invoke `superpowers:brainstorming`. Superpowers participation starts at
`superpowers:writing-plans`, followed by its isolation, implementation, review, verification, and
branch-completion skills.

The legacy mixed-spec path keeps the existing brainstorm-based behavior for resumability.

## Resume Detection

Evaluate top-to-bottom and resume at the first incomplete phase:

1. v2 `product.md` with `shaping` → resume shaping;
2. product disposition `split`, `deferred`, or `rejected` → report and stop;
3. approved product requiring an incomplete design gate → resume design;
4. missing v2 `technical.md` → author it;
5. technical status `draft` → rerun applicable review/fix;
6. `needs-product-decision` → present only the bounded product escalation;
7. technical status `ready` with no plan → write plan;
8. plan/branch/PR/merge/closeout → retain the existing artifact-driven checks.

An interrupted review round may be rerun from the latest Technical Contract; review is read-only
and fixes are idempotent.

## Delivery-Profile Evolution

Add:

```text
story_contracts:
  mode: dual
  product_template: <path-or-bundled-default>
  technical_template: <path-or-bundled-default>
  product_filename_rule: [ID]-[slug]-product.md
  technical_filename_rule: [ID]-[slug]-technical.md
```

- New profiles default to `dual`.
- Existing profiles without `story_contracts` behave as `legacy-mixed`.
- Refreshing an existing profile proposes `dual`; it never silently changes an existing
  user-authored mode.
- Existing legacy artifacts continue through the legacy detector.
- If v2 and legacy artifacts coexist, v2 wins only when it explicitly records the legacy artifact
  it supersedes.

## Escalation Policy

Routine technical and review work remains autonomous. Return to the product owner only when:

- a Product Contract must change;
- a technical constraint forces a user-experience compromise;
- competing options create materially different user outcomes;
- scope must expand or split;
- the Product Contract is contradictory or incomplete;
- destructive, money-sensitive, security-sensitive, or external production authority exceeds the
  original request.

Pure technical disagreement first goes to an independent technical adjudicator role.

## Validation Strategy

### Skill RED–GREEN–REFACTOR

For each new or changed skill:

1. run realistic scenarios without the new guidance and record failures;
2. add the minimum skill/template/prompt content that corrects those failures;
3. rerun the same scenarios with the skill;
4. capture new rationalizations or wrong-shaped output and close the loopholes;
5. validate discovery metadata and all referenced files.

### Deterministic repository checks

Extend the standard-library validator and tests to cover:

- both new skills and templates;
- valid frontmatter and referenced prompt files;
- v2 schema/status vocabulary;
- the absence of `superpowers:brainstorming` from the v2 path;
- explicit legacy fallback;
- profile defaults and compatibility behavior;
- runtime-neutral reviewer terminology;
- README and smoke-test coverage.

### Cross-runtime smoke cases

Document and exercise:

- product-facing triage and product-only questioning;
- engineering-only bypass;
- approved, split, deferred, and rejected dispositions;
- interrupted shaping resume;
- existing design-gate compatibility;
- technical author plus reviewer/fix/re-review;
- `needs-product-decision` escalation;
- sequential fallback without workers;
- legacy mixed-spec resume.

## Success Criteria

1. A new product-facing story cannot reach technical design without an approved Product Contract.
2. Product shaping contains no implementation-design questions or sections.
3. The owner confirms one recap and is not asked to reread the written contract.
4. Stories may be approved, split, deferred, or rejected before engineering begins.
5. Technical design is independently reviewed and traceable to product outcomes.
6. Review/fix loops run without routine owner intervention.
7. Product changes and high-risk authority still escalate explicitly.
8. New v2 stories do not invoke `superpowers:brainstorming`.
9. Legacy mixed stories remain resumable.
10. Claude Code and Codex consume the same canonical skills, templates, and reviewer prompts.

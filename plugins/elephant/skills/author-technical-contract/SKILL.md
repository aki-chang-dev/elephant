---
name: author-technical-contract
description: Use when an approved Product Contract or explicitly engineering-only story needs implementation-ready technical decisions and specialist review before planning.
---

# Author Technical Contract

## Overview

Turn one approved Product Contract or explicitly engineering-only story into a reviewed
`<ID>-<slug>-technical.md`. Separate product meaning from technical choice. Do not invoke
`superpowers:brainstorming` or `superpowers:writing-plans`; the caller owns those transitions.

## Validate inputs and evidence

Read `technical-contract-template.md` and the applicable canonical prompts under `reviewers/`.

For a product-facing story, require `<ID>-<slug>-product.md` with `schema:
elephant.story/v2`, `kind: product`, and `status: approved`. Reject technical authoring when that
artifact is absent or not approved and return control to product shaping. The approved Product
Contract is immutable to the author, fixer, reviewers, and adjudicator.

For an explicitly engineering-only story, require evidence that user and business outcomes remain
unchanged. Use `product_contract: null` and write an explicit behavior-preservation contract.
Uncertainty about that classification fails safe to product-facing.

Before selecting architecture, inspect the real repository: applicable instruction files, current
code and tests, global specs, decision records, migrations and schema where relevant, optional
design handoff, and authoritative external documentation required by repository policy. Cite the
evidence in section 2.

## Separate product meaning from technical choice

A choice is a **product ambiguity** when plausible answers change an observable user or business
outcome, flow, state, default, permission, copy boundary, recovery behavior, or acceptance
criterion. Set exactly `status: needs-product-decision`, write the bounded decision brief from
section 10, stop making downstream technical choices, and return to product shaping. Never rename
such ambiguity an “implementation detail” or resolve it by assumption.

Before mapping a broad product category such as “user-owned configuration,” “reusable setup,” or
“operational state” to fields, prove that the approved contract uniquely identifies its observable
included and excluded behavior. If two different sets of user-visible settings satisfy the words,
the copy boundary is product ambiguity. Repository Create/Edit fields, current schema, prior
behavior, and industry convention may demonstrate the ambiguity; they cannot select the set. Stop
at the first such ambiguity and use exactly `needs-product-decision`.

A choice is **technical** only when all viable answers preserve the same approved or preserved
observable behavior. Select it from repository and authoritative evidence. Use the technical
adjudicator before escalating conflicting specialist findings about a pure engineering choice.

## Draft the contract

Copy `technical-contract-template.md` to `<ID>-<slug>-technical.md` and keep `status: draft` while
authoring or reviewing.

- Product-facing: map every Product Contract requirement, flow, state, rule, and copy boundary
  through `Product contract item | Technical response | Verification`.
- Engineering-only: replace that binding with explicit current behavior, preservation invariants,
  and evidence that will detect a changed user or business outcome.
- Record unresolved technical questions in section 10. Do not declare readiness with `TBD`,
  placeholders, deferred questions, or unresolved choices.
- Do not modify `product.md`.

## Select independent reviewers by risk

Every draft receives independent review; “small,” “obvious,” or low-risk work is not a reason to
self-review or skip it. Always select `test`. Select every additional role whose observable
trigger applies:

| Canonical prompt | Observable trigger |
|---|---|
| `reviewers/architecture.md` | Module boundaries, responsibility placement, coupling, interfaces, data flow, or compatibility |
| `reviewers/domain-data.md` | Domain invariants, schema, migration, tenancy, transaction/concurrency, or money path |
| `reviewers/security-operations.md` | Auth/access, secrets/sensitive data, destructive behavior, retries/idempotency, rollback, deployment, recovery, or production risk |
| `reviewers/product-conformance.md` | Every product-facing story |
| `reviewers/test.md` | Every draft |
| `reviewers/technical-adjudicator.md` | Conflicting specialist findings about a pure technical choice |

Record selected roles and triggers in section 11.

## Review, fix, and recheck

Give each selected role the latest draft, its canonical prompt, the immutable Product Contract or
behavior-preservation contract, and the same relevant evidence. Reviewers are read-only.
Canonical Elephant prompts are the source of truth; host-native agents are optional adapters.

Dispatch isolated read-only workers when delegation is available. Otherwise run the identical
prompts sequentially. Parallel and sequential modes must use identical inputs, output contracts,
severity standards, and pass criteria.

Deduplicate findings by contract/risk reference, evidence, and required outcome. Then:

1. If a finding changes product meaning, set `needs-product-decision`, write one bounded decision
   brief, and return to product shaping.
2. If specialists conflict but all outcomes are observably identical, run
   `reviewers/technical-adjudicator.md`.
3. Have the author/fixer revise the Technical Contract for evidence-backed technical findings.
4. Re-run every reviewer affected by a revision. A prior verdict does not cover changed text.
5. Repeat until there are no blocking findings or product ambiguity requires escalation.

Reviewers and the adjudicator never edit the draft. Do not replace independent review with author
self-review.

## Exit

Set `status: ready` only when all of these are true:

- section 10 has no open technical questions, placeholders, or deferred choices;
- every applicable product item or preservation invariant has technical and verification coverage;
- selected reviewers report no blocking findings;
- every affected reviewer has rechecked the author/fixer's latest revision;
- no unresolved choice changes product meaning.

If product meaning must be supplied or changed, the only technical-state escalation is exactly
`status: needs-product-decision`. Preserve the approved Product Contract, include only the bounded
decision brief, and return to product shaping.

Return a ready contract to the caller without a routine product-owner technical review or another
written-file approval checkpoint.

## Red flags

- “It is an implementation detail” hides two different user outcomes.
- A broad copy/reuse category is expanded to repository fields without a uniquely approved
  observable boundary.
- “The change is small” replaces independent review with self-review.
- `ready` coexists with an open question, `TBD`, placeholder, or blocking finding.
- A reviewer or adjudicator edits either contract.
- A technical role changes the approved Product Contract.
- The workflow requests routine owner review, brainstorming, or planning.

Stop at `draft` or `needs-product-decision` and follow the applicable gate when any red flag
appears.

---
schema: elephant.story/v2
story: <ID>
slug: <slug>
kind: technical
story_kind: <product-facing | engineering-only>
status: draft
product_contract: <path | null>
---

# <ID> — <Technical outcome>

This contract contains implementation decisions and evidence. The author and every technical
reviewer must treat an approved `product.md` as immutable.

The two legal exits from technical authoring before planning are
`ready | needs-product-decision`. Unresolved technical questions keep this contract at `draft`.
Unresolved product meaning requires `needs-product-decision`; do not answer it as an implementation
choice.

The persisted lifecycle is `draft → ready → implementing → done`. Review is an activity while
`status: draft` remains persisted; record rounds and rechecks in section 11 instead of inventing a
`review` status. `ship-story` changes `ready` to `implementing` before implementation and changes
`implementing` to `done` during closeout after the required delivery evidence exists.

## 1. Product-contract binding

For a product-facing story, cite the approved Product Contract and map every requirement and state:

`product_contract` is its exact case-sensitive repository-relative POSIX path. It must name the
existing file for the exact active Product Contract. Absolute paths, URIs, backslashes, empty
values, `.` or `..` segments, repository escapes, outside-resolving symlinks, missing files,
other-story paths, and basename/case near matches are invalid.

| Product contract item | Technical response | Verification |
|---|---|---|
| <section, requirement, flow, state, or copy boundary> | <supporting mechanism> | <evidence that proves it> |

Map only uniquely approved observable boundaries. If a broad copy/reuse category permits multiple
user-visible inclusion sets, stop with `needs-product-decision`; do not infer the set from
repository fields or convention.

For an engineering-only story, set `product_contract: null` and replace the product binding with
an explicit behavior-preservation contract: name the current observable user and business
behavior, the invariants that must remain unchanged, and the evidence that will prove preservation.

## 2. Current-system context

Record inspected repository paths, existing behavior, applicable instructions, global specs,
decision records, design handoff, and authoritative external documentation.

## 3. Technical scope

Describe the implementation boundary, affected modules, responsibilities, and explicit exclusions.

## 4. Domain and data contracts

Define domain invariants, ownership, schema and migration behavior, tenancy, money-path semantics,
and consistency rules that apply.

## 5. Interfaces and data flow

Define internal and external interfaces, data movement, validation boundaries, error propagation,
and compatibility expectations.

## 6. Product-state implementation

For product-facing work, explain how every approved flow, state, rule, default, permission,
critical-copy boundary, and recovery path is supported without changing its meaning.

For engineering-only work, explain how observable behavior remains unchanged.

## 7. Security, privacy, and operational behavior

Cover authorization, tenant isolation, secrets and sensitive data, destructive behavior,
idempotency and retries, observability, rollback, and production failure handling as applicable.

## 8. Compatibility and migration

Describe backward compatibility, rollout and migration order, mixed-version behavior, rollback,
and cleanup.

## 9. Verification strategy

Name the automated and manual evidence that proves the traceability rows, behavior preservation,
failure handling, migration safety, and applicable operational properties.

## 10. Risks and open technical questions

List evidence-backed risks and unresolved technical questions. This section must contain no open
technical questions at `ready`.

When product meaning is unresolved, set `status: needs-product-decision` and include one bounded
decision brief:

- Product-contract ambiguity: <contract item or missing meaning>
- Evidence: <repository, design, or requirement evidence>
- Distinct observable outcomes: <the user or business outcomes that differ>
- Decision required: <one bounded product question>
- Technical impact: <what cannot proceed without the decision>

Do not modify `product.md`.

## 11. Review evidence

Record each selected canonical role, its risk trigger, verdict, blocking findings, author/fixer
changes, and affected-role recheck. Reviewers report findings only; they never edit this contract.

For later lifecycle states also record:

- Current contract-basis revision marker: <ready-state commit or contract-content digest; preserve across lifecycle-only writes>
- Superseded delivery evidence: <older plan/execution/review/conformance records invalidated by a decision return, or None>
- Plan and execution evidence: <plan path bound to the current revision marker; branch/worktree or equivalent>
- Implementation and code-review evidence: <commands, commits/diff, verdicts>
- Post-implementation conformance: <reviewer verdict, findings, fixer changes, affected rechecks>
- Verification and acceptance evidence: <results>
- Integration and closeout evidence: <integration result; roadmap/docs closeout>

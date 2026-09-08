---
name: author-technical-contract
description: Use when an elevated-assurance Story has named technical risk or evidence-backed unresolved material technical uncertainty that requires implementation decisions and specialist scrutiny before execution.
---

# Author Technical Contract

## Purpose

Turn current product authority and a named elevated-assurance risk into an implementation-ready,
reviewed Technical Contract. Ordinary work does not invoke this skill.

Read completely:

- `../../references/information-routing.md`;
- `../../references/delivery-assurance.md`;
- `technical-contract-template.md`.

The contract is a transient delivery-branch artifact removed before integration. Its lifecycle is
`draft → ready → implementing`, with `needs-product-decision` returning to shaping.

## Bind current authority and risk

Fetch the current Linear Story, relevant planning relations, and full directly linked Notion pages
needed to interpret the outcome. Verify Team, Product, and Product Home ancestry. For engineering-
only work, record a current behavior-preservation source and change-detecting evidence.

Record exact source identities/observations and map every applicable outcome, flow, state, rule,
copy boundary, recovery path, and acceptance item. Name the elevated trigger: money, destructive
data/migration, security/privacy/authorization, concurrency/transaction, production rollout/
recovery, major system boundary, or unresolved technical uncertainty.

Inspect applicable repository instructions, relevant code/tests, decisions, schema/migrations, and
authoritative external engineering documentation. Do not inventory unrelated documentation or
hydrate sources that cannot affect the named risk.

## Separate product meaning from technical choice

A product ambiguity changes an observable outcome, flow, state, default, permission, copy,
recovery, or acceptance. Set `needs-product-decision`, write one bounded brief, and return to
`shape-story`. Repository implementation cannot choose product meaning.

A pure technical choice preserves every observable requirement. Resolve it from repository and
authoritative engineering evidence; use the adjudicator only for conflicting specialist findings.

## Draft and source currency

Use the bundled template and keep `status: draft` during authoring/review. Carry an in-session source
index with current observations. At resume and immediately before `ready`, refresh exposed version/
last-edited evidence; fetch full content again only when the observation changed or currency cannot
otherwise be proved. Observable source change invalidates affected contract, plan, implementation,
and review evidence and returns changed meaning to shaping.

## Select specialists by named risk

Select only roles whose evidence boundary is material:

| Canonical prompt | Trigger |
|---|---|
| `reviewers/architecture.md` | major boundaries, ownership, coupling, interfaces, or compatibility |
| `reviewers/domain-data.md` | money, invariants, schema/migration, tenancy, concurrency, or transactions |
| `reviewers/security-operations.md` | access, sensitive data, destructive behavior, rollout, rollback, recovery, or production risk |
| `reviewers/product-conformance.md` | complex requirement mapping itself creates material conformance risk |
| `reviewers/test.md` | verification strategy for the named risk is materially complex or safety-critical |
| `reviewers/technical-adjudicator.md` | selected specialists conflict on a pure technical choice |

Record each selected role and trigger. Give each specialist a role-scoped packet: the relevant
contract sections, source items, repository paths/evidence, and canonical prompt. Product-
conformance receives complete current product authority. External links alone are not evidence.
Reviewers are read-only. Include the shared findings and rechecks policy from
`delivery-assurance.md`, supported usage, non-goals, and the specific risk question in each packet.

## Fix, recheck, and exit

Apply the shared findings and rechecks policy: the author adjudicates each finding before editing,
fixes accepted blockers, and supplies dispositions plus affected requirements/sections/evidence for
one focused recheck by affected roles. Non-blocking suggestions require no repair. After that
recheck, stop automatic cycling and resolve a persistent blocker through concrete investigation or
bounded correction; another independent check needs a named risk author verification cannot settle.
Product findings return to shaping only for material unresolved product choices; use the adjudicator
once for conflicting technical evidence. A round limit never makes an unresolved blocker ready.

Set `status: ready` only when sources are current, the named risk has a supported response and
verification, no blocking finding remains, and all affected rechecks pass. Record one stable basis
marker binding current sources, mapped requirements, technical choices, and verification. Return
to `ship-story` without owner technical review.

## Red flags

- No named elevated trigger exists.
- Full unrelated product or repository context is sent to every reviewer.
- A source link substitutes for current required content.
- An unsupported review preference expands scope.
- `ready` coexists with stale authority, an open product question, or a blocking finding.

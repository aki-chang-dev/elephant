---
name: author-technical-contract
description: Use when an approved Linear Story and linked product knowledge, or explicitly engineering-only work, needs implementation-ready technical decisions and specialist review before planning.
---

# Author Technical Contract

## Purpose

Turn current authoritative product sources into a reviewed, implementation-ready Technical
Contract. Product meaning comes from Linear and linked Notion pages; technical choices come from
repository and authoritative engineering evidence. Do not invoke brainstorming or implementation
planning: the caller owns those transitions.

Read `../../references/information-routing.md` before acting. The Technical Contract and later
implementation plan are transient delivery-branch artifacts. They exist for resume and review, then
are removed before final integration after durable facts have reached their authoritative homes.

The transient lifecycle is `draft → ready → implementing`, with a return through
`needs-product-decision`. This skill owns `draft` authoring/review and exits to `ready` or
`needs-product-decision`; `ship-story` owns implementation, conformance, and removal of the
transient contract before integration. Verified Git/Linear truth owns final completion.

## Bind current product authority

When called by `ship-story`, use its exact Story-scoped Technical Contract path and template. For a
standalone call, use bundled `technical-contract-template.md` and a predictable
`<ID>-<slug>-technical.md` path on an isolated delivery branch.

For product-facing work, resolve Product and fetch the current product-source bundle:

- the exact Linear Story ID and URL, full description/outcome/observable acceptance, Team
  ownership, and relevant native planning relations;
- the full body, exact ID and URL, title, and verified Product Home ancestry of every directly
  linked Notion Decision or Knowledge page needed to interpret the Story;
- native source version or last-edited evidence when exposed by the host.

A URL, preview, cached excerpt, or prior Git Product Contract is not sufficient. Fetch source
content in the current run and route through the authoritative home. A `linear_only` Story may have
no Notion source. Unreadable, missing, wrong-Team, wrong-Product, wrong-parent, conflicting, or
insufficient product authority stops authoring and names the exact missing context; never replace it
with plausible repository text.

Record each exact source and its current observation in section 1, then map every current observable
requirement, flow, state, rule, copy boundary, recovery path, and acceptance item. The Technical
Contract contains the complete mapping and source links, not copied page bodies.

For explicitly engineering-only work, require evidence that user and business outcomes remain
unchanged. Use the template's behavior-preservation source and record current observable behavior,
preservation invariants, and evidence capable of detecting change. Classification uncertainty fails
safe to product-facing. During a bounded migration, an explicit behavior-preservation source may
also stand in for product sources only when the approved task is precisely to preserve behavior.

Before selecting architecture, inspect applicable repository instructions, current code and tests,
specifications and decision records, schema/migrations when relevant, and authoritative external
engineering documentation required by repository policy. Cite concrete evidence in section 2.

## Keep product meaning separate from technical choice

A **product ambiguity** exists when plausible answers change an observable user/business outcome,
flow, state, default, permission, copy boundary, recovery behavior, or acceptance criterion. Set
exactly `status: needs-product-decision`, write one bounded section-10 brief, stop downstream
technical choices, and return to `shape-story`.

Repository fields, current UI, schema, or convention may reveal ambiguity but cannot choose product
meaning. A choice is **technical** only when all viable answers preserve every current observable
requirement. Resolve technical choices from repository and authoritative evidence; use the technical
adjudicator only for conflicting specialist findings about such a pure technical choice.

## Draft and maintain source validity

Copy the selected template to the selected output path and keep `status: draft` throughout authoring
and review. Record review rounds in section 11; do not invent a persisted review status.

- Map every product-source item through `Source item | Observable requirement | Technical response
  | Verification`.
- For engineering-only work, map every preservation invariant to implementation and verification.
- Keep section 10 free of placeholders, deferred choices, or unresolved questions at `ready`.
- Treat fetched product sources as read-only. Technical authors and reviewers never edit Linear or
  Notion product meaning.

Before every resumed authoring/review round and immediately before `ready`, re-fetch all sources and
compare their current content and native observations with section 1. A changed observable
requirement invalidates the current contract, plan, implementation, and earlier verdicts: set
`needs-product-decision`, state the changed source/outcome, and return to shaping. A source edit that
provably leaves observable meaning unchanged refreshes the binding and reruns every affected
reviewer. Missing authority stops; an old source copy never substitutes.

After shaping resolves a decision, re-fetch the entire current source bundle, clear the resolved
brief, set `status: draft`, remap affected and dependent items, and invalidate superseded plan,
execution, review, and conformance evidence. An interruption must leave either the unchanged
`needs-product-decision` artifact or a fully rebound `draft`, not a mixed state.

## Select independent reviewers by risk

Every draft receives independent review. Always select `test`; select every other role whose
observable trigger applies:

| Canonical prompt | Observable trigger |
|---|---|
| `reviewers/architecture.md` | Boundaries, responsibility placement, coupling, interfaces, data flow, or compatibility |
| `reviewers/domain-data.md` | Domain invariants, schema, migration, tenancy, concurrency, transactions, or money path |
| `reviewers/security-operations.md` | Access, secrets, destructive behavior, retries, rollout, rollback, recovery, or production risk |
| `reviewers/product-conformance.md` | Every product-facing Story |
| `reviewers/test.md` | Every draft |
| `reviewers/technical-adjudicator.md` | Conflicting specialist findings about a pure technical choice |

Record selected roles and triggers in section 11. Give every selected reviewer the latest draft,
the complete fetched product-source contents or behavior-preservation evidence, exact source links,
the canonical prompt, and the same relevant repository evidence. External links alone are not
review input.

Use isolated read-only workers when available; otherwise run identical prompts sequentially.
Reviewers report findings and never edit the Technical Contract, product sources, code, or each
other's findings.

## Fix, recheck, and exit

Deduplicate findings by contract/risk reference, evidence, and required outcome:

1. Product-meaning findings set `needs-product-decision` and return one bounded brief to shaping.
2. Pure technical conflicts go to `technical-adjudicator.md`.
3. The author/fixer revises evidence-backed technical findings.
4. Every reviewer affected by changed text or source observations rechecks the latest draft.
5. Repeat until no blocking finding or product ambiguity remains.

Set `status: ready` only when section 10 is clear, every source requirement or preservation
invariant has implementation and verification coverage, all selected reviewers pass the latest
draft, and the sources still match the current authoritative content.

After the final fixer change and rechecks, record one stable non-placeholder contract-basis marker
in section 11. It binds the current source observations, complete requirement mapping, technical
choices, and verification strategy. Lifecycle-only status/evidence updates preserve it; any source,
requirement, traceability, or technical-choice change replaces it and invalidates the earlier plan
and execution evidence.

Return the ready Technical Contract to the caller without routine owner technical review or a
second written-file approval gate.

## Red flags

- A source URL is cited without fetching and reviewing its current content.
- A prior Product Contract or preview substitutes for missing Linear/Notion authority.
- A broad product category is mapped to fields without a uniquely observable boundary.
- “Small change” replaces independent review.
- `ready` coexists with stale sources, an open question, placeholder, or blocking finding.
- A technical role edits product meaning or asks the owner to review routine technical choices.

Stop at `draft` or `needs-product-decision` and follow the applicable return when a red flag appears.

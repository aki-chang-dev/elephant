---
schema: elephant.story/v2
story: <Linear Story ID>
slug: <slug>
kind: technical
story_kind: <product-facing | engineering-only>
status: draft
---

# <Linear Story ID> — <Technical outcome>

This transient contract contains implementation decisions and evidence. Product meaning remains in
its fetched authoritative sources. The legal authoring exits are `ready` and
`needs-product-decision`; unresolved technical questions keep `status: draft`.

## 1. Product-source binding and traceability

For product-facing work, record every current source after fetching its full content:

| Source | Exact ID and URL | Verified ownership/ancestry | Current observation |
|---|---|---|---|
| Linear Story | <ID and URL> | <Team and Product> | <native version/last edit when available> |
| Notion Decision/Knowledge | <ID and URL> | <Product Home ancestry> | <native version/last edit when available> |

Map every observable item from all fetched sources. A link alone is not evidence.

| Source item | Observable requirement | Technical response | Verification |
|---|---|---|---|
| <source + section/item> | <outcome, flow, state, rule, copy, recovery, or acceptance> | <supporting mechanism> | <independent evidence> |

For engineering-only work, replace the tables with a behavior-preservation source: current
observable user/business behavior, invariants that must remain unchanged, and evidence that will
detect a change.

## 2. Current-system context

Record inspected repository paths, applicable instructions, current behavior, specifications,
decision records, schema/migrations, and authoritative external engineering documentation.

## 3. Technical scope

Describe implementation boundaries, affected modules, responsibilities, and explicit exclusions.

## 4. Domain and data contracts

Define applicable invariants, ownership, schema/migration behavior, tenancy, money-path semantics,
and consistency rules.

## 5. Interfaces and data flow

Define interfaces, data movement, validation boundaries, error propagation, and compatibility.

## 6. Product-state implementation

Explain how every mapped flow, state, rule, default, permission, critical-copy boundary, and
recovery path is supported without changing meaning. For engineering-only work, prove observable
behavior remains unchanged.

## 7. Security, privacy, and operations

Cover authorization, isolation, secrets/sensitive data, destructive behavior, retries,
observability, rollout, rollback, recovery, and production failure handling as applicable.

## 8. Compatibility and migration

Describe compatibility, rollout/migration order, mixed-version behavior, rollback, and cleanup.

## 9. Verification strategy

Name evidence that independently proves traceability, preserved behavior, failure/recovery paths,
migration safety, security, and operational properties.

## 10. Risks and open technical questions

This section contains no open technical question at `ready`. When product meaning is unresolved,
set `status: needs-product-decision` and include exactly one bounded brief:

- Source ambiguity/change:
- Evidence and exact source link:
- Distinct observable outcomes:
- Decision required:
- Technical work invalidated or blocked:

## 11. Review and basis evidence

Record each selected canonical role, risk trigger, verdict, blocking findings, fixer changes, and
affected-role recheck. Reviewers report findings only.

- Current source observations re-fetched: <evidence>
- Current contract-basis marker: <stable marker binding sources, mapping, choices, verification>
- Superseded delivery evidence: <older plan/execution/review/conformance invalidated, or None>
- Plan and execution evidence: <plan bound to current marker; branch/worktree>
- Implementation and code-review evidence:
- Post-implementation conformance:
- Verification and acceptance evidence:
- Integration and closeout evidence:

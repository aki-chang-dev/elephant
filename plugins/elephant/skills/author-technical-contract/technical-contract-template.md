---
schema: elephant.story/v3
story: <Linear Story ID>
slug: <slug>
kind: technical
story_kind: <product-facing | engineering-only>
assurance: elevated
status: draft
---

# <Linear Story ID> — <Technical outcome>

This transient contract exists only for a named elevated-assurance risk and is removed before
integration.

## 1. Current product authority

Record exact source IDs/URLs, verified ownership/ancestry, current observations, and the complete
requirement mapping relevant to this Story. For engineering-only work, record observable behavior,
preservation invariants, and change-detecting evidence instead.

| Source item | Observable requirement | Technical response | Verification |
|---|---|---|---|
| ... | ... | ... | ... |

## 2. Named elevated risk and evidence

- Risk trigger:
- Repository/source evidence:
- Consequence if mishandled:

## 3. Technical approach and boundaries

Define affected responsibilities, interfaces/data flow, compatibility, and explicit exclusions.

## 4. Risk-specific contracts

Include only applicable domain/data, security/privacy/operations, migration/rollback/recovery, and
product-state contracts. Omit categories unrelated to the named risk.

## 5. Execution and verification

State the bounded implementation sequence when needed and the independent evidence that proves the
approved outcome and named risk controls.

## 6. Product-decision return or open technical questions

At `ready`, no blocking product or technical question remains. Deferred non-blocking improvements
do not prevent readiness. For changed or ambiguous product meaning, set
`needs-product-decision` and provide one brief containing the source/evidence, distinct observable
outcomes, required decision, and invalidated work.

## 7. Review and basis

- Selected role → named trigger → role-scoped packet:
- Verdicts, load-bearing findings, fixes, and affected rechecks:
- Current source observations:
- Contract-basis marker:
- Plan/execution evidence:
- Final delivery review and integration evidence:

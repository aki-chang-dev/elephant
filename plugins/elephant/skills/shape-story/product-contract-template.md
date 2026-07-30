---
schema: elephant.story/v2
story: <ID>
slug: <slug>
kind: product
status: shaping
design_sensitivity: <High | Medium | Low>
supersedes: []
---

# <ID> — <Product outcome>

This contract contains product decisions only. No implementation design belongs in this file.

`supersedes` is always a YAML list of exact repository-relative POSIX paths. Use `[]` for a new
contract with no predecessor. A versioned successor lists the approved Product Contract it
replaces and carries forward that predecessor's normalized entries.

Use `status: approved` only when section 10 has no open product questions. For
`split`, `deferred`, or `rejected`, record the product rationale and next condition in section 10
instead of adding technical content.

## 1. User and context

Who is trying to accomplish what, in which situation?

## 2. Problem and current experience

What happens today, and why is that inadequate?

## 3. Desired outcome

What user and business outcome should change?

## 4. Experience flow

Describe the entry point, primary flow, branches, exit, and recovery in observable product terms.

## 5. States and edge cases

Cover applicable loading, empty, error, disabled, partial-success, and success states, plus
recovery.

## 6. Information and copy

Record information hierarchy and user decisions. Write critical user-facing copy exactly. For
intentionally flexible supporting copy, record its intent and tone.

## 7. Product rules and defaults

Record user-visible rules, defaults, permissions, and business behavior.

## 8. Product acceptance criteria

List independently observable product outcomes.

## 9. Out of scope

Name adjacent product behavior this story does not change.

## 10. Open product questions

List unresolved product decisions. This section must be empty at `approved`. For `split`,
`deferred`, or `rejected`, record:

- Rationale: <product reason>
- Next condition: <condition for reconsideration or follow-up>

# Slice Spec Template

> The structure a per-slice spec follows. `ship-story` writes one of these per roadmap story (to the profile's `spec_dir`, filename per `filename_rule`).
>
> **Why this shape: a slice spec is a DUAL-INPUT contract.** It feeds two agents that decompose from different angles — the **engineering** side (Claude Code / `ship-story`, thinks in APIs, data, modules) and the **design** side (Claude Design / DesignSync, thinks in screens, UX, flows). The audience-split sections below let each side advance independently; **§7 Cross-Module Contract is the hard anchor that keeps them consistent.**
>
> Copy this, fill it for the real slice, save to `<spec_dir>/<ID>-<slug>.md`.

## Audience map (who reads what)

| Section | Engineering (Code) | Design | Purpose |
|---|---|---|---|
| §1 User Story | ✅ | ✅ | shared intent |
| §2 Scope | ✅ | ✅ | shared boundary |
| §3 Acceptance Criteria | ✅ (binding) | ⚠️ reference | verifiable done-conditions |
| §4 Engineering Brief | ✅ | ❌ skip | implementation guidance |
| §5 Out of Scope | ✅ | ✅ | anti scope-creep |
| §6 Design Brief | ❌ skip | ✅ | design guidance |
| §7 Cross-Module Contract | ✅ | ✅ | **Code ↔ Design consistency anchor** |
| §8 Dependencies | ✅ | ✅ | shared dependencies |

**Key rules:**
- §7 is a hard contract — neither side changes it without telling the other (a spec at `Implementing` status must not change §7; drop back to `Refined` first).
- §1/§2 are the shared foundation; if the two sides read them differently, every later output diverges.
- §6 **Sensitivity** drives `ship-story`'s design gate: `High`/`Medium` ⇒ the slice waits for design; `Low` ⇒ no design gate. A UI slice with no §6 means the spec is incomplete.

---

## 1. User Story

> One paragraph, "As a `<role>` I want `<capability>` so that `<outcome>`." Name the role and the scenario even if the only user is you.

## 2. Scope

> Bulleted, explicitly IN scope.

- **Entities / data touched:** …
- **Capabilities / flows:** …
- **Modules / subsystems:** …

## 3. Acceptance Criteria

> A set of **verifiable** yes/no conditions. The slice is done when all are yes. Use "the system shall / the user can"; avoid "should consider / as much as possible."

- [ ] AC-1: …
- [ ] AC-2: …

## 4. Engineering Brief (Code only)

> Direction and constraints, not code.

### Field-naming prerequisite ★ (mandatory if this slice creates fields)

If the slice creates or reads any entity field/column/table that is still `TBD` in the object model:
1. List the fields it needs.
2. Check the object model's field contracts.
3. For each `TBD`, agree the name with the user per the naming-convention AD (the profile's `field-naming.decision_ref`).
4. Write the agreed names back into the `field_contract_location`.
5. Only then implement.

(Skip if the slice only reads already-locked fields.)

- **Fields to name:** …

### Required endpoints (high level)
- `<METHOD> /path` — purpose

### Data-model touchpoints
- Reads: … / Writes: … / Constraints referenced (AD/ED): …

### Key technical constraints & implementation notes
- …

## 5. Out of Scope

> What this slice explicitly does NOT do (and where it's deferred to).

- Not X (left to slice `<Y>`)

## 6. Design Brief (Design only)

### Sensitivity
- **High** — bespoke UX, design from scratch · **Medium** — partly bespoke, partly standard · **Low** — standard patterns (no design gate)

### Key UX decisions
- …

### Reference patterns
- e.g. "like Stripe's event detail expansion"

### Open design questions
- …

### Visual constraints
- e.g. "Click ID must use a monospace font"

## 7. Cross-Module Contract (Code ↔ Design anchor)

> The hard contract between Code and Design. Changing anything here requires notifying the other side.

### API ↔ UI mapping

| API endpoint | UI component served | Data schema (high level) | Notes |
|---|---|---|---|
| `GET /api/...` | `<Component>` | `{ ... }` | … |

### Shared terms
- "<term>" = … (both sides must use it the same way)

### Data-shape agreements
- timestamps: ISO 8601 UTC; large blobs collapsed in UI; etc.

## 8. Dependencies

- **Slice dependencies:** depends on `<ID>` (done)
- **Doc references:** AD-`<n>` / ED-`<n>` / entities / glossary terms
- **Unblocks:** `<downstream IDs>`

---

## Status flow

`Draft → Refined → Implementing → Done`

- **Draft** — first pass; may have open questions / `TBD`.
- **Refined** — both sides reviewed; all §7 contract items pinned; ready to build.
- **Implementing** — Code and Design both building; **§7 frozen** (to change it, return to Refined).
- **Done** — all AC ✅.

# Slice Spec Template

> The structure a per-slice spec follows. `ship-story` writes one of these per roadmap story (to the profile's `spec_dir`, filename per `filename_rule`).
>
> **Why this shape: a slice spec is a DUAL-INPUT contract.** It feeds two agents that decompose from different angles — the **engineering** side (Claude Code / `ship-story`, thinks in APIs, data, modules) and the **design** side (a design tool — e.g. Claude Design, Figma — thinks in screens, UX, flows). The audience-split sections below let each side advance independently; **§7 Cross-Module Contract is the hard anchor that keeps them consistent.**
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

### Field-naming (★ if this slice creates fields)

> The actual back-fill (TBD → real names in the object model) happens during spec authoring — `ship-story` Step 1 does it before writing this spec, per the project's naming-convention decision (`field-naming.decision_ref`). Here, just **record the outcome**:

- **Fields this slice creates/names:** `<field>` (`<type>`) — …
- **Convention followed:** `<decision_ref>` (e.g. `AD-3`)

(Omit if the slice only reads already-locked fields.)

### Required interfaces (high level)
- `<METHOD> /path` or `<function/event>` — purpose

### Data-model touchpoints
- Reads: … / Writes: … / Decision records referenced: `<AD/ED or the project's equivalent>`

### Key technical constraints & implementation notes
- …

## 5. Out of Scope

> What this slice explicitly does NOT do (and where it's deferred to).

- Not X (left to slice `<Y>`)

## 6. Design Brief (Design only)

### Sensitivity

**Sensitivity: `<High | Medium | Low>`** — pick exactly ONE value (the design gate matches this literal string; `≠ Low` ⇒ the slice waits for design):
- **High** — bespoke UX, design from scratch
- **Medium** — partly bespoke, partly standard
- **Low** — standard patterns, OR a non-UI / headless slice (no design gate)

### Key UX decisions
- …

### Reference patterns
- e.g. "like Stripe's event detail expansion"

### Open design questions
- …

### Visual constraints
- e.g. "identifiers shown in a monospace font", "destructive actions need a confirm step"

## 7. Cross-Module Contract (Code ↔ Design anchor)

> The hard contract across the slice's boundary. Changing anything here requires notifying the other side.
> For a **UI slice** this is the Code ↔ Design boundary (API ↔ UI). For a **non-UI / headless slice** it's the module/service boundary (interface ↔ caller); fill the parts that apply and drop the rest — §7 is never empty, but its shape follows the slice.

### Interface ↔ consumer mapping
> Web/UI slice: API endpoint ↔ UI component. Headless slice: function/endpoint/event ↔ its consumer.

| Producer (endpoint / interface / event) | Consumer (UI component / caller / subscriber) | Data schema (high level) | Notes |
|---|---|---|---|
| `<producer>` | `<consumer>` | `{ ... }` | … |

### Shared terms
- "<term>" = … (both sides must use it the same way)

### Data-shape agreements
- e.g. timestamps ISO 8601 UTC; large payloads paginated/collapsed; null vs absent; etc.

## 8. Dependencies

- **Slice dependencies:** depends on `<ID>` (done)
- **Doc references:** decision records (e.g. `AD-<n>` / `ED-<n>`) / entities / glossary terms
- **Unblocks:** `<downstream IDs>`

---

## Status flow

`Draft → Refined → Implementing → Done` (the default; a project may set its own `status_flow` in the profile — the role of each stage below maps to that project's vocabulary).

- **Draft** — first pass; may have open questions / `TBD`.
- **Refined** — both sides reviewed; all §7 contract items pinned; ready to build. (ship-story flips Draft→Refined on spec approval.)
- **Implementing** — Code and Design both building; **§7 frozen** (to change it, return to Refined). (ship-story flips to this when execution starts.)
- **Done** — all AC ✅. (ship-story flips to this at closeout.)

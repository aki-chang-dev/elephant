---
name: author-product-spec
description: Use when a product idea needs to become a structured spec foundation — the global_specs that a roadmap and per-slice specs build on. Phase A of the kickoff pipeline, or authoring a product spec system from scratch. Triggers on "/author-product-spec", "define the product", "write the object model / product spec", "create the spec foundation".
---

# Author-Product-Spec

## Overview

Turn a product idea into `global_specs`: a canonical, cross-referenced **spec system** (master-spec · object-model · glossary · AD · ED). Phase A of the `kickoff` pipeline; consumed downstream by `decompose-roadmap` (Phase B) and by `ship-story`'s brainstorm as loaded context.

**Core principle: this defines what the product IS — not the build order (Phase B) and not config (Phase C).** It is product-scale brainstorming PLUS a structuring discipline: elicit with brainstorming, then shape the output into the canonical doc set and keep the cross-references honest. **REQUIRED SUB-SKILL:** use superpowers:brainstorming for every elicitation stage (one question at a time).

## Prerequisites

- A product idea or rough understanding to start from.
- Read the output structure first: `spec-system-template.md` in this skill dir.
- If a spec system already partially exists, this skill **resumes** it (see Multi-session) — don't restart from scratch.

## Canonical spec-system (the output)

| Doc | Contents |
|---|---|
| **master-spec** | product definition · scope (in/out) · object-model overview · module index · cross-cutting principles · technical constraints · how-to-use (reading order) · change log (full section list in the template) |
| **object-model** | overview + `entities/` (per-entity field contracts) + cross-rules (cross-entity invariants) |
| **glossary** | domain terms (grown throughout) |
| **AD** (architecture decisions) | product-level what/why, numbered `AD-1..`, each context / decision / rationale / consequences |
| **ED** (engineering decisions) | implementation-level how (stack / deploy / patterns), numbered `ED-1..` |
| **+ domain-specific** (optional) | e.g. a taxonomy, only if the product needs it |

**AD vs ED:** AD = product-level, stable, "what & why" (data model shape, scope, business rules). ED = implementation-level, evolves with tech, "how" (framework, deploy topology, patterns). When unsure, ask "would this change if we rewrote in another stack?" — yes → ED, no → AD.

## Authoring sequence (guided discipline; artifacts co-evolve)

0. **Resolve the output location** before writing anything. Elephant's standard layout is `docs/elephant/<product>/` per project; the spec foundation goes in **`docs/elephant/<product>/spec/`**. Confirm the `<product>` slug with the user and **state the final spec-dir path back**. (Existing projects may already use a different spec dir — keep theirs; this default is for greenfield. The `<product>` slug you pick keys the whole `docs/elephant/<product>/` tree that B's roadmap and C's per-slice specs/plans also write under.)
1. **Vision & scope** (master-spec §1–2): what the product is, who it's for, in/out boundaries. **🛑 CHECKPOINT 1: user approves the north star + boundaries; resume on explicit approval.**
2. **Object model**: entities, field contracts, cross-rules — the product backbone. Author the **field-naming-convention AD first, during this step, before any field contract** (it's the one AD that precedes Step 3 — see below). **Done test:** every IN-scope capability from §1 maps to ≥1 entity or cross-rule, and every entity has a purpose + a field-contract table. Individual field *names* may remain `TBD` (the naming convention governs them; ship-story pins each `TBD`→real during the slice that creates the field) — completeness here means the contract exists, not that every name is final. **🛑 CHECKPOINT 2: user reviews the object model; resume on explicit approval.**
3. **AD**: the product-level decisions that shaped 1–2 (numbered, with rationale) — all ADs except the field-naming one already authored in Step 2.
4. **ED**: implementation-level decisions.
5. **Glossary**: grown throughout; finalize here.
6. **Cross-reference pass**: link entities ↔ AD ↔ glossary; master-spec module index points to every doc. **🛑 CHECKPOINT 3: user reviews the final spec system; resume on explicit approval.**

Entities, AD, and glossary **co-evolve** — iterate, don't force strict linearity. But hold the primary order (backbone before decisions): a decision with no entity to attach to means the object model isn't ready yet. The sole exception is the field-naming-convention AD, authored inside Step 2.

## Field-naming convention (downstream hook — do this early)

While authoring the object model, **establish the field-naming convention as an early AD** (e.g. a layered naming rule: a stable baseline layer + a high-frequency-terse layer + a low-frequency-verbose layer). Every field contract follows it. This AD is what `ship-story`'s field-naming gate and `init-profile`'s `field-naming.decision_ref` point at — `decision_ref`'s value is exactly this AD's number token (e.g. `AD-3`). Pin it (and its number) before filling field contracts, not after.

## Multi-session resume

Phase A spans sessions. On re-entry, detect which canonical docs exist + their completeness and resume at the first incomplete one: master-spec → object-model → AD/ED → glossary → cross-reference pass. Never restart a completed doc.

## Red flags — STOP

- Slicing into a roadmap or sequencing the build → that's Phase B; here you define the product, not its delivery order.
- Writing the delivery profile → Phase C.
- Jumping to entities/decisions before vision & scope is approved (CHECKPOINT 1) → the north star gates everything.
- Filling field contracts before the naming-convention AD exists → pin the convention first.
- Recording an implementation choice as an AD (or a product rule as an ED) → apply the rewrite-in-another-stack test.

## Common mistakes

- **Object model as a database schema dump.** Entities are product concepts with contracts and cross-rules, not just tables — capture the invariants.
- **Decisions with no context/rationale.** An AD/ED that records only the choice is useless later; capture why and what it rules out.
- **Letting the glossary lag.** Define terms as they first appear; a term used three different ways across docs is a spec smell.

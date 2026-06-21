---
name: decompose-roadmap
description: Use when a project has a product spec foundation but no roadmap yet, and needs the product decomposed into a phased, dependency-aware delivery sequence. Phase B of the kickoff pipeline, or standalone. Triggers on "/decompose-roadmap", "build the roadmap", "decompose the product into slices/stories", "sequence the build".
---

# Decompose-Roadmap

## Overview

Turn a product spec foundation (`global_specs`) into a **roadmap**: a phased, dependency-aware delivery sequence of coarse, independently-shippable slices. Phase B of the `kickoff` pipeline; consumed downstream by `ship-story` (locates stories by ID) and `init-profile` (detects `roadmap_path` + `story_id_pattern`).

**Core principle: a roadmap is a delivery SEQUENCE — in what order to build — not a product definition and not detailed specs.** Product definition is Phase A; per-slice detail is ship-story's job. This is judgment-heavy and collaborative: **propose a draft using slicing methodology, then iterate with the user. Never auto-generate a roadmap from spec structure** (one-slice-per-entity is a non-roadmap).

## Prerequisites

- `global_specs` exist (Phase A output, or an existing product spec/understanding). **If the product isn't defined yet, STOP** — that's Phase A, not this skill.
- **If a complete, user-approved roadmap already exists** (e.g. kickoff re-dispatched this on a finished roadmap), confirm that with the user and **exit without re-running** — don't re-arm CHECKPOINT 1/2. Only (re)build when the roadmap is missing or the user wants changes.
- Read the output structure first: `roadmap-template.md` in this skill dir. The roadmap you write follows it.

## Slicing methodology (bake these into every draft)

| Principle | Means |
|---|---|
| Vertical slices | each slice cuts through the stack and delivers demoable value — never a horizontal layer or an entity's CRUD in isolation |
| Walking skeleton first | the first phase is the thinnest end-to-end path that runs (scaffold → minimal working flow) |
| MVP-first / value sequencing | order phases by business value + dependency; earliest usable product first |
| Story mapping | lay out the user journey, slice along it |
| Coarse & demoable | each slice = one spec→plan→ship unit; deliberately coarse, re-split at implementation |

**Granularity & phase-count tests** (the methodology's checkable rules):
- A slice is **right-sized** if it's one spec→plan→ship unit a user could see demoed in isolation. Too horizontal if it's pure CRUD on one entity; too coarse if it spans more than one phase's DoD.
- **Demoable test**: could you show this slice working end-to-end to someone? If the only "demo" is internal plumbing, fold it into an adjacent vertical slice.
- The **skeleton → MVP → parity → advantage** tiers are *illustrative, not a fixed four*. Drop tiers a small product doesn't need; add phases a large one does.

## The discipline: propose → iterate → write

1. **Locate & load `global_specs`.** The profile does NOT exist yet at Phase B (init-profile is Phase C, later) — so do not look for `.claude/delivery-profile.md`. Find the specs by (a) Phase A's in-session output if chained, else (b) scan the repo for an existing spec system (e.g. a `docs/**` product-spec dir) and confirm with the user, else (c) ask the user for the spec path/dir. Then understand entities, capabilities, user journeys, decisions.
2. **Draft phases** — each phase = a milestone with a goal + DoD (exit criteria), following skeleton → MVP → parity → advantage. **🛑 CHECKPOINT 1: user approves the phase skeleton before slicing; resume on explicit approval.** (The strategic spine is the user's call.)
3. **Draft slices** per phase — vertical, coarse, demoable; assign IDs by prefix (see below).
4. **Draft dependencies** — cross-slice blockers + ordering within/across phases.
5. **Draft phase-transition criteria** — the minimal standard to advance between phases.
6. **Iterate** — present the draft slices/deps/gates; refine on business priority with the user. One question at a time (**REQUIRED DISCIPLINE:** follow superpowers:brainstorming's one-question-at-a-time rule; do NOT dump many questions at once). **Exit:** repeat steps 3–5 (slice-level refinement) until the user confirms the slices; do NOT loop indefinitely. Re-open CHECKPOINT 1 (re-enter Step 2) ONLY if the phasing itself must change — slice tweaks do not re-arm it. Then go to Step 7.
7. **Capture deferred capabilities** into the roadmap's Out-of-scope section, **seed the change log** (`<date> — initial roadmap`), and **write** the roadmap using `roadmap-template.md`. Output path: the profile doesn't exist yet, so default to Elephant's layout — **`docs/elephant/<product>/roadmap.md`**, co-located with the spec foundation (derive `<product>` from the spec dir you loaded in Step 1). Confirm with the user; an existing project may use a different path — keep theirs. **🛑 CHECKPOINT 2: user reviews the final roadmap; resume on explicit approval.**

## ID scheme

Default to **phase-keyed prefixes** (e.g. `S-` scaffold / `F-` foundation / `P-` parity / `A-` advantage). Help the user pick a set and **record it in the roadmap's §0 reading guide under "Slice ID prefixes (legend)"**. This skill does NOT write the profile — `init-profile` (Phase C) later DERIVES `roadmap_path` + `story_id_pattern` by reading the roadmap you wrote.

## Coarse-slice principle

Slices are intentionally coarse — a slice that turns out large gets re-split during ship-story's brainstorm (a slice can spawn sub-slices, e.g. `F-02a-i`). The roadmap states this explicitly so nobody over-details here.

## A / B boundary

- **Phase A** = what the product IS (object model, decisions, glossary).
- **This skill (Phase B)** = in what order to build it (delivery sequence).
- Don't redefine the product here; if a spec gap blocks slicing, flag it back to Phase A, don't invent product decisions.

## Red flags — STOP

- Auto-deriving slices from the object model (one-per-entity / CRUD-per-entity) → that's a horizontal non-roadmap. Slice vertically.
- Writing detailed, spec-ready slices → too fine; keep coarse, ship-story re-splits.
- Skipping CHECKPOINT 1 and slicing before the user approves the phase skeleton → the phasing is the user's strategic call.
- Inventing product decisions to fill a spec gap → flag back to Phase A instead.
- Authoring the product spec or the profile here → out of scope (Phase A / Phase C).

## Common mistakes

- **Layer-first instead of value-first.** "All the models, then all the APIs, then all the UI" is not a roadmap — no phase is demoable. Each slice must stand up end-to-end.
- **Front-loading completeness over a walking skeleton.** Get a thin thing running end-to-end first, then widen.
- **Treating phases as buckets instead of milestones.** Every phase needs a goal + DoD, or phase-transition is undefined.

# Roadmap Template

> The canonical structure a `decompose-roadmap` run produces. Copy, fill with the product's real phases/slices, save to the project's `roadmap_path`. Projects may deviate, but keep sections 1–5 — `ship-story` and `init-profile` depend on locatable IDs, phases, and dependencies.

---

# <Product> — Roadmap

## 0. Reading guide

- **What this doc solves**: the delivery sequence — which slices, in which phases, in what order.
- **Roadmap ↔ slice**: slices here are COARSE and "re-split at implementation" (ship-story's brainstorm splits a large slice into sub-slices). This doc is not the per-slice spec.
- **Ordering principle**: vertical, demoable slices; walking skeleton first; then value/dependency order.
- **Slice ID prefixes** (legend): e.g. `S-` scaffold · `F-` foundation · `P-` parity · `A-` advantage. (This legend defines the profile's `story_id_pattern`.)

## 1. Phase overview

| Phase | Goal | Done-marker (DoD) |
|---|---|---|
| Phase 0 — <name> | <one-line goal> | <exit criteria> |
| Phase 1 — <name> | … | … |
| … | … | … |

## 2. Per-phase detail

### Phase 0 — <name>

**Done-marker (DoD)**: <verifiable exit criteria for advancing>

**Slices** (initial; re-split at implementation):

| Slice ID | Name | Purpose |
|---|---|---|
| S-01 | … | … |
| S-02 | … | … |

### Phase 1 — <name>
…(repeat)…

## 3. Inter-slice dependencies

Key blocking chains (what must precede what):

- `F-03` depends on `S-01`, `S-02`
- `P-01` blocked by `F-08`
- …

## 4. Phase-transition criteria

The minimal standard to move between phases:

- **Phase 0 → 1**: <minimal standard>
- **Phase 1 → 2**: <minimal standard>
- …

## 5. Out of scope (future versions)

- <explicitly deferred capability> — (future v1+)

## 6. Change log

- <date> — <what changed>

# 🐘 Elephant

A [superpowers](https://github.com/obra/superpowers)-based **delivery harness** for Claude Code. Take a product from raw idea to shipped, one roadmap story at a time — with the project's own conventions and gates baked in, not hardcoded.

Elephant is a thin orchestration layer **on top of** superpowers. Superpowers provides the atomic skills (brainstorming, writing-plans, subagent-driven-development, worktrees, finishing-a-branch). Elephant strings them into a project-aware pipeline and inserts each project's own gates.

> The name: product inception is the "elephant" — too big to swallow whole, so Elephant decomposes it into a phased pipeline you can actually run.

## What's inside

Two halves: **kickoff** bootstraps a project, **ship-story** delivers from it.

```
/kickoff                         # idea → ship-story-ready
  ├─ author-product-spec   (A)   # idea → spec foundation (master-spec/object-model/glossary/AD/ED)
  ├─ decompose-roadmap     (B)   # specs → phased, dependency-aware roadmap
  └─ init-profile          (C)   # repo → .claude/delivery-profile.md (the conventions contract)

/ship-story <ID>                 # deliver ONE roadmap story end-to-end
   research-augmented brainstorm → spec → (design gate) → plan
   → subagent build in an isolated worktree → PR → squash-merge → docs refresh
```

| Skill | Role |
|---|---|
| `elephant:kickoff` | Thin orchestrator: detect phase, dispatch A→B→C, stop at boundaries. Until a project is ship-story-ready. |
| `elephant:author-product-spec` | Phase A — product-scale brainstorming structured into a canonical, cross-referenced spec system. |
| `elephant:decompose-roadmap` | Phase B — guided decomposition into coarse, vertical, demoable slices (walking-skeleton → MVP → parity). |
| `elephant:init-profile` | Phase C — discover repo + CLAUDE.md conventions → a `delivery-profile`; reconciles, never clobbers. |
| `elephant:ship-story` | The engine — delivers one roadmap story, phase-aware and resumable. The brainstorm is the review; the only stop is the design gate (UI slices). Non-UI slices run end-to-end with no stops. |

Every project-specific value (paths, status flow, gates, CI checks, finish style, conventions) lives in a per-repo **`.claude/delivery-profile.md`** — the contract `init-profile` writes and `ship-story` reads. The skills themselves are zero-hardcoded and reusable across projects.

## Install

```
/plugin marketplace add aki-chang-dev/elephant
/plugin install elephant@elephant
```

## Use

**New product:**
```
/kickoff
```
Runs A→B→C, stopping at each phase boundary for your go-ahead. When it's done you have a spec foundation, a roadmap, and a delivery-profile — the project is ship-story-ready.

**Deliver a story** (any project that already has a roadmap + delivery-profile):
```
/ship-story F-15
```
Phase-aware and resumable: re-invoke any time and it continues where it left off. The research-augmented brainstorm is the review, so there's no spec/plan stop. For UI slices it commits + pushes the spec to main and stops only at the design gate to wait for your design; non-UI slices run start-to-finish with no stops.

Each sub-skill also runs standalone — e.g. `/init-profile` to retrofit a delivery-profile onto an existing project.

## How it fits together

```
        ┌─ kickoff ────────────────────────────────┐
idea ─► │  A author-product-spec → global_specs     │
        │  B decompose-roadmap   → roadmap          │ ──► ship-story-ready
        │  C init-profile        → delivery-profile │
        └───────────────────────────────────────────┘
                                                         │
                          ship-story <ID>  ◄─────────────┘  (repeat per story)
```

## License

MIT © Aki Chang

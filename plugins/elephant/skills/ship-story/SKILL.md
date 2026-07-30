---
name: ship-story
description: Use when delivering or resuming one roadmap story or slice end-to-end in a repository that has an Elephant delivery-profile.
---

# Ship-Story

## Overview

Deliver ONE roadmap story end-to-end by orchestrating Elephant and Superpowers skills, with every
project-specific gate, path, and convention injected from the repository's delivery profile at
`.agents/elephant/delivery-profile.md`.

**Core principle: ship-story is a thin, artifact-driven orchestrator.** The profile chooses the
story-contract workflow; persisted artifacts choose the resume phase. The orchestrator dispatches
the authoring, planning, execution, and finishing skills instead of reproducing them.

## Prerequisites

- A `.agents/elephant/delivery-profile.md` exists. If it does not, STOP and ask the user to run
  `elephant:kickoff` or `elephant:init-profile`; do not guess project conventions.
- Read `delivery-profile-schema.md` in this skill directory and
  `../../references/runtime-compatibility.md`.
- Read the profile before checking skills because required authoring skills depend on
  `story_contracts.mode`.

## Preflight

Before producing artifacts:

1. Resolve the effective story-contract mode:
   - explicit `story_contracts.mode: dual` → dual-contract v2;
   - explicit `story_contracts.mode: legacy-mixed` → legacy mixed-spec behavior;
   - an existing profile with no `story_contracts` section or no `mode` → `legacy-mixed`.
   Any other value is unsupported; STOP rather than guessing.
2. For `mode: dual`, confirm `elephant:shape-story`,
   `elephant:author-technical-contract`, `superpowers:writing-plans`,
   `superpowers:using-git-worktrees`, `superpowers:subagent-driven-development` or
   `superpowers:executing-plans`, and `superpowers:finishing-a-development-branch`.
3. For `legacy-mixed`, confirm the same downstream Superpowers skills plus
   `superpowers:brainstorming`.
4. When the design gate is enabled, confirm `design.provider` is `manual` or `claude-design`.
5. If a required capability is absent, STOP before writing artifacts and give host-appropriate
   setup guidance.

## Step 0 — Load, locate, and detect phase

1. Read the profile and resolve its effective mode as above.
2. Locate `<ID>` in `roadmap_path` and read the story seed plus `global_specs`.
3. Glob the configured `spec_dir` using the story ID before assuming the slug. Classify every
   match from its frontmatter and filename, not from filename alone.
4. Run the dual-contract v2 detector first. Run the legacy detector only under the conditions it
   names. Then announce `Story <ID> is at phase X — resuming there.` Never redo a completed phase.

## Dual-contract v2 phase detection

V2 artifacts use `schema: elephant.story/v2` and these filenames:

- Product Contract: `<ID>-<slug>-product.md`, `kind: product`, status exactly
  `shaping | approved | split | deferred | rejected`.
- Technical Contract: `<ID>-<slug>-technical.md`, `kind: technical`, status exactly
  `draft | review | ready | needs-product-decision`.

Inspect v2 artifacts before any legacy mixed spec, even when the effective profile mode is
`legacy-mixed`. This allows an explicitly migrated story to resume mechanically without changing
unrelated legacy stories.

When v2 and legacy formats coexist for the same ID, v2 wins only when its Product Contract
explicitly records every replaced legacy path in `supersedes`. A null, missing, or unrelated
`supersedes` value is ambiguous: STOP, list the v2 and legacy paths, and ask which contract owns the
story. Do not merge their contents, infer recency, or dispatch either authoring path. An
engineering-only Technical Contract has no Product Contract that can record `supersedes`, so the
same coexistence is ambiguous and must stop.

Before selecting a phase, validate v2 pairing. A Technical Contract with
`story_kind: product-facing` must reference the matching existing Product Contract and that
Product Contract must be `status: approved`; otherwise return to product shaping and do not plan.
An engineering-only Technical Contract must use `product_contract: null`. Multiple active v2
artifacts of the same kind or mismatched story/slug references are ambiguous; STOP and list them
instead of choosing by timestamp.

After coexistence is resolved, evaluate these checks top-to-bottom and resume at the first
incomplete or terminal phase:

| Order | Mechanical artifact state | Resume action |
|---|---|---|
| 1 | Product Contract has `status: shaping` | Resume `elephant:shape-story` in the main conversation from its persisted open product questions. |
| 2 | Product Contract has `status: split`, `deferred`, or `rejected` | Report the recorded disposition, rationale, and next condition; STOP. Do not start design or engineering. |
| 3 | Product Contract has `status: approved` and its design gate is incomplete | Resume the existing design gate using `design_sensitivity`. |
| 4 | Approved Product Contract has no Technical Contract | Dispatch `elephant:author-technical-contract` with the approved product and any completed design handoff. |
| 5 | Engineering-only triage returned no Product Contract and no Technical Contract exists | Dispatch `elephant:author-technical-contract` with `product_contract: null` and the behavior-preservation evidence. |
| 6 | Technical Contract has `status: draft` or `status: review` | Resume its author/fixer and applicable read-only reviewer loop from the latest artifact. |
| 7 | Technical Contract has `status: needs-product-decision` | Present only its bounded product-decision brief. Resume product shaping for that decision; technical roles must not edit the approved Product Contract. |
| 8 | Technical Contract has `status: ready` and no plan exists | Dispatch `superpowers:writing-plans`. |
| 9 | Plan, branch, PR/merge, or closeout state exists | Continue with the shared downstream detector. |

If no v2 artifact exists:

- a legacy mixed spec for this ID goes to the legacy detector, regardless of a newly refreshed
  dual profile;
- no legacy artifact plus effective `mode: dual` starts dual triage;
- no legacy artifact plus effective `legacy-mixed` starts the legacy mixed-spec path.

### Dual orchestration spine

For a new dual story:

```text
triage
→ product-facing: elephant:shape-story
→ approved: existing design gate when applicable
→ elephant:author-technical-contract
→ ready: superpowers:writing-plans
```

Run triage through `elephant:shape-story` in the main conversation. Product-facing shaping asks
only product questions, presents one Product Contract Recap, and waits for the owner's explicit
terminal disposition. Do not ask the owner to reread the file. `split`, `deferred`, and `rejected`
are terminal for this delivery run. For `approved`, the Product Contract becomes immutable to
technical authors, fixers, reviewers, and adjudicators. Engineering-only triage creates no
Product Contract and proceeds to technical authoring with `product_contract: null`.

`elephant:author-technical-contract` receives the approved Product Contract plus the completed
design handoff when one applies. It owns technical drafting and specialist review. Only
`status: ready` may proceed to `superpowers:writing-plans`. A
`status: needs-product-decision` artifact returns one bounded product question to shaping; it is
not a routine technical-review checkpoint.

### Dual-mode design-gate adapter

This is the existing design gate with only its v2 input adapted:

- **Gate disabled:** if `design gate.enabled` is false, skip it for every story.
- **UI detection:** read `design_sensitivity` from the approved Product Contract. `High` or
  `Medium` enters the gate; `Low` skips it. If the field is missing in a gate-enabled project,
  STOP and ask whether the gate applies.
- **Durable pre-gate artifact:** before waiting, commit and push the approved Product Contract to
  the configured main branch. It remains read-only afterward.
- **Human handoff:** tell the user the exact `design_local_dir`, configured `handoff_file`
  (default `design-handoff.md`), and unchanged human `ready_signal`. File presence alone is not
  approval.
- **`provider: manual`:** the user places design artifacts and `design-handoff.md` under
  `design_local_dir`.
- **`provider: claude-design`:** after the human signal, use DesignSync to resolve
  `claude_design.project_ref`, apply `claude_design.slice_to_design_mapping`, and pull artifacts
  into `design_local_dir`. If an applicable value is `TBD` or empty, STOP and ask for that exact
  value.
- **Common handoff contract:** continue only when the directory is non-empty, the handoff exists,
  and the human signal is recorded. The handoff covers key screens/states, interactions and
  transitions, maps them to Product Contract flows and states, and records unresolved
  implementation constraints.
- Any other provider is unsupported. STOP and list `manual` and `claude-design`; do not introduce
  a design-system protocol or an agent-assisted provider.

Pass the immutable approved Product Contract and completed handoff together to
`elephant:author-technical-contract`.

## Legacy-mixed phase detection

The legacy branch exists for existing profiles and artifacts. Only this branch dispatches
`superpowers:brainstorming` and writes the bundled `slice-template.md` (or the profile's preserved
legacy `spec_template`). Do not migrate or rewrite a mixed spec into v2 during delivery.

Use this detector only when no v2 artifact exists for the ID, or when a v2 Product Contract
explicitly names the legacy artifact in `supersedes` and therefore makes the legacy file
historical. In the latter case, continue through the v2 detector; never resume both formats.

For an active legacy story, evaluate top-to-bottom:

| Order | Mechanical check | Resume action |
|---|---|---|
| 1 | no mixed spec at `<spec_dir>/<ID>-*.md` | Run the preserved research-augmented `superpowers:brainstorming` flow and write the legacy spec. |
| 2 | UI mixed spec has incomplete design gate | Resume the legacy design gate. |
| 3 | no plan at `<plan_dir>/<ID>-*.md` | Dispatch `superpowers:writing-plans`. |
| 4 | plan exists | Continue with the shared downstream detector. |

The preserved legacy authoring flow is:

1. Load `global_specs`, draft the clarifying questions internally, and auto-assess whether mature
   industry precedent exists.
2. When precedent exists, announce the bounded research scopes and confirm before spending
   tokens. Run independent scopes in parallel when workers are available or the identical scopes
   sequentially otherwise; synthesize centrally and sharpen the remaining questions.
3. Dispatch `superpowers:brainstorming`.
4. When the profile's field-naming prerequisite applies, read `decision_ref`, agree names with the
   user, and update `field_contract_location` before writing the mixed spec.
5. Write the configured mixed spec using `slice-template.md`, `filename_rule`, and `status_flow`.
   As before, write `Draft`, immediately advance to `Refined`, and add no separate spec-review
   stop.

The legacy design gate keeps its prior semantics:

- disabled gates always skip;
- `ui_detection` reads the mixed spec's §6 Design Brief sensitivity, where non-Low enters the
  gate and Low skips it; a missing sensitivity fails safe and asks the user;
- commit and push the `Refined` mixed spec to main before waiting;
- keep the same `manual` and `claude-design` provider behavior, `design_local_dir`,
  `handoff_file`, DesignSync mapping, human `ready_signal`, and unsupported-provider stop;
- continue only after the non-empty directory, handoff, and human signal are all present;
- the handoff maps key screens/states and transitions to mixed spec §7.

## Shared downstream detector and delivery

After the selected contract path reaches planning, preserve the existing checks in this order:

| Row → resume at | Mechanical check |
|---|---|
| plan missing → plan | glob `<plan_dir>/<ID>-*.md`; any match counts, including split plans such as `<ID>-T8-*.md` |
| no branch/PR → execute | inspect `git worktree list` and `git branch --list "*<ID>*"` per `branch_pattern`; for GitHub-PR integration also inspect `gh pr list --search "<ID>"` |
| PR open, not merged → finish | for GitHub PR use `gh pr view --json state`; non-GitHub integrations use their configured merged check |
| merged, roadmap not Done → closeout | merged per `finish.integration`, but the roadmap row lacks the configured Done marker |
| merged and roadmap Done | report fully done |

### Plan

Dispatch `superpowers:writing-plans` and write to `plan_dir`. In dual mode the plan consumes the
ready Technical Contract, immutable approved Product Contract when present, and completed design
handoff when applicable. In legacy mode it consumes the mixed spec and design handoff when
applicable. There is no additional plan-review stop.

### Execute

Dispatch `superpowers:using-git-worktrees`, then the profile's available
`superpowers:subagent-driven-development` or `superpowers:executing-plans` path. Inject isolation,
review cadence, `execution.gotchas`, and language rules from the profile.

- Legacy mode advances the mixed spec to `Implementing`; its §7 contract is frozen unless the
  spec returns to `Refined`.
- Dual mode leaves product `approved` and technical `ready`. Technical roles and implementation
  roles may not edit the approved Product Contract.
- Run `changeset_cmd` during execute commits before opening the PR, not in closeout.

### Finish

Dispatch `superpowers:finishing-a-development-branch` and follow `finish.integration` unchanged.
For the default GitHub PR flow: open the PR, wait for every `ci_required_checks` entry to be green,
auto squash-merge when `auto_merge_on_green` permits it, then clean the worktree and sync main. If
`gh pr merge` errors from a worktree, verify `gh pr view --json state` before retrying. A
non-GitHub or trunk-based integration uses its own configured mechanics; do not assume `gh`.

### Closeout docs

Use one closeout commit to set the roadmap story to Done, refresh
`instruction_refresh_targets`, and run `root_snapshot_check`. In legacy mode also advance the
mixed spec to `Done` after all acceptance criteria pass. In dual mode keep Product and Technical
Contract statuses unchanged so their exact v2 vocabulary and approval evidence remain durable.
Do not edit object-model or field-contract docs here. Use `empty_cmd` when the profile requires a
changeset for the closeout commit.

## Owner checkpoints and escalation

- Product-facing dual stories require exactly one explicit owner decision on the Product Contract
  Recap. There is no second file-review checkpoint.
- The existing design-gate wait remains unchanged.
- After an approved Product Contract, return to the owner only for
  `needs-product-decision`, a required product-contract change or scope split, a technical
  constraint that changes observable product behavior, or destructive, money-sensitive,
  security-sensitive, or external production authority beyond the original request.
- Routine technical authoring, specialist review, planning, execution, and code review remain
  autonomous.

## Red flags — STOP

- A dual story is about to dispatch the generic brainstorm path instead of
  `elephant:shape-story`.
- A technical author, fixer, reviewer, or implementation role is about to edit an approved
  Product Contract.
- V2 and legacy artifacts coexist without an exact `supersedes` relationship.
- A terminal product disposition is being treated as approval.
- A Technical Contract with `draft`, `review`, or `needs-product-decision` is about to reach
  planning.
- A completed artifact phase is about to be repeated instead of resumed mechanically.
- A path, check name, provider, or convention is being hardcoded instead of read from the profile.
- A merge is about to proceed while a required CI check is not green.
- A design gate is about to wait before its durable pre-gate artifact is committed and pushed.

## Common mistakes

- **Treating a missing `story_contracts` field as dual.** Existing profiles without it are
  `legacy-mixed`.
- **Letting profile mode override artifact evidence.** V2 detection runs first; legacy files
  remain resumable when no v2 artifact exists.
- **Inferring ownership by timestamp.** Coexisting formats require explicit `supersedes`.
- **Adding a new design protocol.** V2 only changes the durable input and handoff mapping; provider
  semantics and the human ready signal stay unchanged.

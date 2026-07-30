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
2. For v2 detection in every effective mode, resolve all four profile-injected contract values:
   - use `story_contracts.product_template` and `story_contracts.technical_template` when
     present; use the matching bundled template only when the field is omitted;
   - use `story_contracts.product_filename_rule` and
     `story_contracts.technical_filename_rule` when present; use
     `[ID]-[slug]-product.md` and `[ID]-[slug]-technical.md` only when the field is omitted.
   Resolve the compatibility aliases `shape-story/product-contract-template.md` and
   `author-technical-contract/technical-contract-template.md` relative to the plugin's `skills/`
   directory. Resolve every other template path relative to the repository root. A configured
   path must exist, stay inside its allowed root, and be readable; do not fall back when a
   configured value is invalid.
3. Validate each filename rule as a basename ending in `.md`, containing `[ID]` and `[slug]`
   exactly once, with no absolute path, separator, `.` segment, or `..` segment. The rendered
   product and technical filenames must be distinct.
4. For `mode: dual`, confirm `elephant:shape-story`,
   `elephant:author-technical-contract`, `superpowers:writing-plans`,
   `superpowers:using-git-worktrees`, `superpowers:subagent-driven-development` or
   `superpowers:executing-plans`, and `superpowers:finishing-a-development-branch`.
5. For `legacy-mixed`, confirm the same downstream Superpowers skills plus
   `superpowers:brainstorming`.
6. When the design gate is enabled, confirm `design.provider` is `manual` or `claude-design`.
7. If a required capability is absent, STOP before writing artifacts and give host-appropriate
   setup guidance.

## Step 0 — Load, locate, and detect phase

1. Read the profile and resolve its effective mode as above.
2. Locate `<ID>` in `roadmap_path` and read the story seed plus `global_specs`.
3. For v2 detection in either mode, render the configured product and technical filename rules
   with the requested ID and a slug wildcard to discover candidates under `spec_dir`. Also inspect
   every Markdown artifact directly under `spec_dir` for the v2-looking signals below; do not
   assume the configured rule places the ID first. Classify matches from frontmatter and the
   rendered configured rule, not from a bundled filename assumption.
4. Run the dual-contract v2 detector first. Run the legacy detector only under the conditions it
   names. Then announce `Story <ID> is at phase X — resuming there.` Never redo a completed phase.

## Dual-contract v2 phase detection

The bundled filename defaults are `<ID>-<slug>-product.md` and
`<ID>-<slug>-technical.md`, but detection and authoring always render the configured
`story_contracts.product_filename_rule` and `story_contracts.technical_filename_rule` after
preflight resolution. Product status is exactly
`shaping | approved | split | deferred | rejected`; technical status is exactly
`draft | review | ready | needs-product-decision`.

Inspect v2 artifacts before any legacy mixed spec, even when the effective profile mode is
`legacy-mixed`. This allows an explicitly migrated story to resume mechanically without changing
unrelated legacy stories.

### V2 artifact validation

Treat a candidate as **v2-looking** when any of these is true:

- its filename matches either rendered configured v2 filename rule;
- frontmatter contains `schema: elephant.story/v2`;
- frontmatter declares `kind: product` or `kind: technical`;
- frontmatter names the requested `story` and contains any v2 discriminator field: `schema`,
  `kind`, `story_kind`, or `product_contract`, even when that discriminator's value is invalid.

For every v2-looking candidate, validate before phase selection:

- `schema` is exactly `elephant.story/v2`;
- `story` equals the requested ID and `slug` is non-empty;
- `kind` is exactly `product` or `technical`;
- its repository-relative path equals the filename produced by rendering the configured rule for
  its declared kind, story, and slug;
- product status is one of `shaping | approved | split | deferred | rejected`;
- technical status is one of `draft | review | ready | needs-product-decision`, with
  `story_kind: product-facing | engineering-only` and a present `product_contract` field.

An artifact with invalid schema, kind, filename, or status triggers a catch-all hard stop:
**STOP and list every invalid field and artifact path.** Do not treat an invalid v2-looking artifact as legacy or missing,
do not create a replacement, and do not dispatch an author. This prevents duplicate
authoring behind malformed artifacts.

### `supersedes` normalization and coexistence

Writers emit `supersedes` as a YAML list of strings. Readers accept three input shapes for
backward compatibility: `null` normalizes to an empty list; a scalar string normalizes to a
one-item list; a list of strings remains a list. Any other type is invalid.

Each value is a repository-relative POSIX path from the repository root. Require `/` separators
and case-sensitive comparison on every host. Reject empty values, duplicate values, backslashes,
URIs, absolute paths, `.` or `..` segments, paths escaping the repository after resolution,
symlinks resolving outside the repository, missing files, and references to a different story.
Compare only these normalized strings; do not case-fold, percent-decode, or infer by basename.

A Product Contract revision may supersede an older Product Contract, and a v2 Product Contract
may supersede legacy mixed specs. A Product Contract is active when no other valid Product
Contract for the story lists its path in `supersedes`. Require exactly one active Product Contract
when Product Contracts exist; otherwise STOP and list the competing paths.

When v2 and legacy formats coexist, collect all colliding legacy paths for the story. V2 wins only
when the active Product Contract's normalized list contains **every colliding legacy path**.
Multiple legacy artifacts require every path; partial or non-exact coverage is ambiguous. STOP,
list the missing paths, nonmatching entries, and all colliding paths, then ask which contract owns
the story. Valid same-story predecessor paths may coexist in the list; they do not substitute for
an exact colliding legacy path. Do not merge contents, infer recency, or dispatch either authoring path. An
engineering-only Technical Contract has no Product Contract that can record `supersedes`, so
coexistence with any legacy artifact also stops.

### Terminal product dispositions

After individual validation, `supersedes` normalization, and active-product selection—but before
Product/Technical pairing—evaluate the active Product Contract:

- `status: shaping` resumes `elephant:shape-story` from persisted open product questions.
- `status: split`, `deferred`, or `rejected` reports the recorded disposition, rationale, and next
  condition, then STOPS before design or engineering.

Terminal dispositions win even when a Technical Contract exists or references that Product
Contract. Do not route a terminal Product Contract back to shaping merely because technical
pairing would require `approved`.

### Product/technical pairing

Only after terminal Product Contract handling, validate pairing. A Technical Contract with
`story_kind: product-facing` must reference the active approved Product Contract, except for the
resolved decision-return transition below. An engineering-only Technical Contract must use
`product_contract: null`. Multiple active Technical Contracts or mismatched story references are
ambiguous; STOP and list them instead of choosing by timestamp.

### Persisted `needs-product-decision` return

When a Technical Contract is `needs-product-decision` and still references the active approved
Product Contract, the product answer is not yet persisted. Present only its bounded decision
brief, then dispatch `elephant:shape-story` with the configured Product Contract template and a
new rendered output path:

1. The product author creates a `status: shaping` successor Product Contract. It never edits the
   approved predecessor. The successor copies the predecessor's normalized `supersedes` entries
   and adds the predecessor's repository-relative path.
2. `elephant:shape-story` asks the bounded product question, runs its normal critics, presents one
   Product Contract Recap, and persists the owner's answer only through the normal explicit
   disposition. The predecessor remains immutable.
3. If interrupted while the successor is `shaping`, artifact detection resumes shaping there.
4. Once the active approved Product Contract supersedes the older Product Contract still named by
   the `needs-product-decision` Technical Contract, the answer is persisted. Dispatch the
   technical author/fixer; do not present the same bounded question again.
5. The technical author/fixer—not a reviewer—must rebind `product_contract` to the active approved
   successor, clear the resolved decision brief, and set `status: draft` before remapping. It may
   set `status: review` only after applying the product answer and preparing the affected
   read-only reviewers to recheck; persist these three field changes atomically. The artifact must
   never expose a partial rebind with `needs-product-decision`, the old brief, or the old product
   path.
6. If interrupted at `draft` or `review`, the normal detector resumes the author/fixer or reviewer
   loop without returning to the owner.

### V2 resume table

After the validation and terminal rules above, evaluate these checks top-to-bottom:

| Order | Mechanical artifact state | Resume action |
|---|---|---|
| 1 | Product Contract has `status: approved` and its design gate is incomplete | Resume the existing design gate using `design_sensitivity`. |
| 2 | Approved Product Contract has no Technical Contract | Dispatch `elephant:author-technical-contract` with the configured Technical Contract template, rendered output path, approved product, and any completed design handoff. |
| 3 | Engineering-only triage returned no Product Contract and no Technical Contract exists | Dispatch `elephant:author-technical-contract` with the configured Technical Contract template, rendered output path, `product_contract: null`, and behavior-preservation evidence. |
| 4 | Technical Contract has `status: needs-product-decision` and references the active approved Product Contract | Run the persisted decision-return flow above. |
| 5 | Technical Contract has `status: needs-product-decision` and its referenced predecessor is superseded by the active approved Product Contract | Dispatch the technical author/fixer to rebind and reset it; do not re-ask the owner. |
| 6 | Technical Contract has `status: draft` or `status: review` | Resume its author/fixer and applicable read-only reviewer loop from the latest artifact. |
| 7 | Technical Contract has `status: ready` and no plan exists | Dispatch `superpowers:writing-plans`. |
| 8 | Plan, branch, PR/merge, or closeout state exists | Continue with the shared downstream detector. |

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

Render the configured Product Contract filename rule with the selected ID and slug. Dispatch
`elephant:shape-story` in the main conversation with the resolved
`story_contracts.product_template` and exact rendered output path. Product-facing shaping asks
only product questions, presents one Product Contract Recap, and waits for the owner's explicit
terminal disposition. Do not ask the owner to reread the file. `split`, `deferred`, and `rejected`
are terminal for this delivery run. For `approved`, the Product Contract becomes immutable to
technical authors, fixers, reviewers, and adjudicators. Engineering-only triage creates no
Product Contract.

For technical authoring, render the configured Technical Contract filename rule with the same
story ID and selected slug. Dispatch `elephant:author-technical-contract` with the resolved
`story_contracts.technical_template`, exact rendered output path, approved Product Contract plus
completed design handoff when applicable, or `product_contract: null` plus behavior-preservation
evidence for engineering-only work. It owns technical drafting and specialist review. Only
`status: ready` may proceed to `superpowers:writing-plans`.

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

Parse `status_flow` as an ordered sequence before checking presence. It must contain at least two
distinct values: the first status is authoring-incomplete; the second status is the refined/ready state
that unlocks design or planning. Later values retain their configured
execution/closeout meanings. If a mixed spec's status is absent or not in `status_flow`, STOP and
report the path and value; do not infer readiness.

For an active legacy story, evaluate top-to-bottom:

| Order | Mechanical check | Resume action |
|---|---|---|
| 1 | no mixed spec at `<spec_dir>/<ID>-*.md` | Start the preserved authoring flow and write the first configured status. |
| 2 | mixed spec is at a status before the second configured value | Detect that state and resume legacy authoring from the existing mixed spec; do not create a replacement or rerun settled questions. |
| 3 | mixed spec is at the second configured value and has an incomplete UI design gate | Resume the legacy design gate. |
| 4 | mixed spec is at the second configured value and has no plan | Dispatch `superpowers:writing-plans`. |
| 5 | mixed spec is at a later configured value, or its plan exists | Continue with the shared downstream detector. |

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
   Keep the first configured status while authoring is incomplete. Advance to the second
   configured refined/ready status only after the brainstorm decisions, applicable field naming,
   and required template sections are complete. Then continue without a separate spec-review
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

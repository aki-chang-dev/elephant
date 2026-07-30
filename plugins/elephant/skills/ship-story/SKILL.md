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
- Do not check branch-specific skills merely from profile mode. Artifact/type selection comes
  first because persisted artifacts may select a different branch.

## Step 0 — Load, locate, and select the branch

Artifact classification and phase selection happen before dependency checks.

1. Read the profile and resolve its effective mode:
   - explicit `story_contracts.mode: dual` → dual-contract v2 for a new story;
   - explicit `story_contracts.mode: legacy-mixed` → legacy mixed authoring for a new story;
   - an existing profile with no `story_contracts` section or no `mode` → `legacy-mixed`.
   Any other value is unsupported; STOP rather than guessing.
2. Locate `<ID>` in `roadmap_path`; read the story seed and `global_specs`.
3. Resolve the two v2 filename rules for discovery in every effective mode. Use the configured
   values, or `[ID]-[slug]-product.md` and `[ID]-[slug]-technical.md` only when omitted. Validate
   each as a `.md` basename containing exactly one `[ID]` and `[slug]`, with no path separator,
   absolute path, `.` segment, or `..` segment. Render each with the requested ID and a slug
   wildcard. The rendered Product and Technical output paths must be distinct for the same
   requested ID and slug; repeat that comparison with the selected concrete slug before either
   author dispatch. If they collide, list both rules and the rendered path, then STOP before
   artifact mutation. Do not validate or require an authoring template merely to resume a later
   phase.
4. Resolve the preserved legacy artifact contract when present. Render the preserved legacy
   `filename_rule` with the requested ID and a slug wildcard; do not hardcode an ID-leading glob.
   Validate it as a `.md` basename with exactly one `[ID]` and exactly one `[slug]`, no separator,
   absolute path, `.` segment, or `..` segment. Parse `status_flow` as exactly four distinct
   values representing authoring-incomplete, ready, implementing, and done.
5. Inspect the rendered candidates and other Markdown artifacts directly under `spec_dir`.
   Classify them using the v2 and legacy rules below. Existing v2 artifacts take precedence under
   a legacy profile. Existing legacy artifacts remain legacy under a dual profile, including
   after an approved profile refresh.
6. Run the dual-contract detector first, then the legacy detector when no active v2 artifact owns
   the story. If neither artifact kind exists, effective mode selects new v2 or legacy authoring.
7. Select the first incomplete phase without dispatching it. Announce
   `Story <ID> is at phase X — resuming there.` Never redo a completed phase.

## Branch-aware dependency preflight

After Step 0, preflight only capabilities that the selected branch and remaining phases can
dispatch:

- **New v2 product-facing:** `elephant:shape-story`,
  `elephant:author-technical-contract`, then `superpowers:writing-plans`,
  `superpowers:using-git-worktrees`, one of `superpowers:subagent-driven-development` or
  `superpowers:executing-plans`, and `superpowers:finishing-a-development-branch`.
- **New v2 engineering-only or v2 technical draft/decision return:**
  `elephant:author-technical-contract` plus the later Superpowers capabilities; also require
  `elephant:shape-story` only when the selected decision-return phase will dispatch shaping.
- **V2 ready/implementing/done resume:** require only the later capabilities that its first
  incomplete phase can still dispatch.
- **Legacy authoring:** require `superpowers:brainstorming` plus its later capabilities.
- **Resumed legacy after authoring:** preflight only its design/planning/execution/finish
  remainder; it must not require `superpowers:brainstorming` merely because the profile or
  artifact is legacy.

When the selected incomplete phase enters the design gate, confirm `design.provider` is `manual`
or `claude-design`. A different or missing required capability is a hard stop before mutation with
host-appropriate setup guidance.

Resolve an authoring template only when the selected phase will use it. Use
`story_contracts.product_template` or `story_contracts.technical_template` when present and the
matching bundled template only when the field is omitted. Resolve the compatibility aliases
`shape-story/product-contract-template.md` and
`author-technical-contract/technical-contract-template.md` relative to the plugin `skills/`
directory; resolve any other path from the repository root. The selected path must be readable
and remain inside its allowed root.

Resolve legacy `spec_template` only when selected legacy authoring will dispatch. Use the
configured value when present and the bundled `slice-template.md` only when omitted. Resolve the
bundled `slice-template.md` relative to this `ship-story` skill directory; resolve every other
legacy template path from the repository root. The selected file must exist, be readable, and
remain inside the applicable plugin or repository root. Report the configured value and
resolution error, then STOP; do not fall back from an invalid configured legacy template.

Validate a selected custom template immediately before its authoring dispatch. Require mandatory
v2 frontmatter slots and compatible initial values. The Product template requires all ten Product
Contract sections, the fixed product statuses and `design_sensitivity`, and a valid `supersedes`
shape. The Technical template requires all eleven Technical Contract sections, traceability
columns, the fixed technical statuses and decision-brief fields, a valid `product_contract`
shape, and section 11 slots for the contract-basis marker, superseded-history evidence,
current-plan binding, implementation/conformance rechecks, verification, integration, and
closeout. STOP and list every missing or incompatible slot; never author an artifact that the
next resume would reject.

## Dual-contract v2 phase detection

The bundled filename defaults are `<ID>-<slug>-product.md` and
`<ID>-<slug>-technical.md`, but detection and authoring always render the configured
`story_contracts.product_filename_rule` and `story_contracts.technical_filename_rule` after
profile resolution. Product status is exactly
`shaping | approved | split | deferred | rejected`; technical status is exactly
`draft | ready | implementing | done | needs-product-decision`.

Inspect v2 artifacts before any legacy mixed spec, even when the effective profile mode is
`legacy-mixed`. This allows an explicitly migrated story to resume mechanically without changing
unrelated legacy stories.

### V2 artifact validation

Inspect every Markdown artifact directly under `spec_dir`, but classify before validating. The
authoritative exact v2 discriminator values are `schema: elephant.story/v2`, `kind: product` or
`kind: technical`, `story_kind: product-facing | engineering-only`, and the v2-only
`product_contract` binding. A generic `schema` or `kind` key with another value is not by itself a
v2 signal.

Build the current-story v2-looking set as follows:

1. A **configured-path candidate** matches a configured v2 filename rule rendered for the
   requested ID and slug wildcard. Inspect it regardless of its frontmatter `story` value, but do
   not classify it as v2 from its suffix alone.
2. Render the preserved legacy `filename_rule` for the same requested ID. A configured-path
   candidate that also matches this legacy glob, has a known configured legacy `status_flow`
   value, and contains no authoritative exact v2 discriminator is legacy. This remains true when
   its legacy slug ends in `-product` or `-technical`, or its custom template has a generic
   `schema` or `kind` key.
3. A configured-path candidate without that complete legacy evidence is v2-looking. This ensures
   a malformed current-story v2 artifact still hard-stops instead of disappearing into legacy
   authoring.
4. A **catch-all candidate** is any other artifact whose frontmatter `story` exactly equals the
   requested ID and contains an authoritative exact v2 discriminator or v2-only binding.
5. Among catch-all inspected artifacts, ignore any valid v2 artifact for another story whose
   `story` is another ID. It must neither participate in current-story validation nor cause a
   stop.

If one path carries both authoritative exact v2 evidence and complete legacy evidence, or several
paths produce a genuine ambiguous collision that the rules cannot classify uniquely, STOP and
list every candidate plus both evidence sets; do not infer recency.

For every v2-looking candidate, validate before phase selection:

- `schema` is exactly `elephant.story/v2`;
- `story` equals the requested ID and `slug` is non-empty;
- `kind` is exactly `product` or `technical`;
- its repository-relative path equals the filename produced by rendering the configured rule for
  its declared kind, story, and slug;
- product status is one of `shaping | approved | split | deferred | rejected`;
- technical status is one of `draft | ready | implementing | done | needs-product-decision`, with
  `story_kind: product-facing | engineering-only` and a present `product_contract` field.

An invalid required field triggers a catch-all hard stop. Required fields are `schema`, `story`,
`slug`, `kind`, rendered filename, and `status`. For technical artifacts, `story_kind` or
`product_contract` is also blocking as applicable. **STOP and list every invalid field and
artifact path.** Do not treat an invalid v2-looking artifact as legacy or missing; do not create
a replacement or dispatch an author. This prevents duplicate authoring behind malformed
artifacts.

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

### Canonical `product_contract` binding

Treat a non-null `product_contract` with the same canonical discipline as `supersedes`. It is one
repository-relative POSIX path, compared case-sensitive on every host. Reject an empty value,
URI, absolute path, backslashes, `.` or `..` segments, repository escape, outside-resolving
symlink, missing existing file, or a reference to another story. Resolve the path without
case-folding, percent-decoding, or basename inference.

The target must be a valid Product Contract. For `story_kind: product-facing`, require the exact
active Product Contract except while a persisted decision return is still bound to the exact
valid predecessor that the active successor supersedes. For `story_kind: engineering-only`,
require literal `null` until the engineering-only decision-return transition atomically
reclassifies it. A canonical path that exists but is not the exact active Product Contract is a
pairing error, not a near match.

### Status-dependent artifact invariants

Validate content invariants before selecting any phase:

- Every Product Contract's `design_sensitivity` is exactly `High`, `Medium`, or `Low`.
- `approved` requires section 10 to contain no unresolved product questions, `TBD`, placeholder,
  or unanswered item.
- `split`, `deferred`, and `rejected` require both disposition rationale and next condition as
  non-empty, non-placeholder values.
- `needs-product-decision` requires exactly one bounded decision brief with non-empty ambiguity,
  evidence, distinct observable outcomes, decision required, and technical impact slots.
- `ready` requires no `TBD`, placeholder, open technical question, or blocking finding; no
  deferred choice; complete traceability or behavior-preservation coverage; and every required
  affected-reviewer recheck recorded against the latest revision. If current-revision
  execution-start evidence exists, `ready` is stale and invalid; the transition must already have
  persisted `implementing`. Evidence explicitly retained as superseded history by a completed
  decision return does not count as current-revision execution evidence.
- `ready` also requires one non-placeholder contract-basis revision marker for the reviewed
  requirements, traceability, and technical choices. Capture or replace it after the last
  author/fixer change and before persisting `ready`.
- `implementing` retains every `ready` invariant and additionally records its plan bound to that
  exact marker plus current branch/worktree or equivalent execution evidence.
- `done` retains every `ready` invariant and additionally records passing post-implementation
  conformance, completed verification/acceptance evidence, integration evidence, and closeout.

The same checks apply on every resume, not only when a writer changes status. An invalid artifact
must **STOP with the exact artifact path, field or section, and violated invariant**. Do not
silently demote it, fall through to legacy/missing detection, dispatch duplicate authoring, or
advance to a later phase.

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
`product_contract: null`; the only allowed coexisting Product Contract is the deterministic
`shaping` or newly `approved` output of its own decision return, which must stop or atomically
reclassify/rebind before any technical work. Multiple active Technical Contracts or mismatched
story references are ambiguous; STOP and list them instead of choosing by timestamp.

### Persisted `needs-product-decision` return

`ship-story` owns slug and output-path allocation for every decision return; `shape-story` writes
the exact path it receives.

For a product-facing Technical Contract still bound to an approved Product Contract, derive the
successor base from that Product Contract's slug. Append `-v<N>` using the lowest unused integer
starting at 2, render the configured Product filename rule, and pass that exact repository path to
`elephant:shape-story`. The new Product Contract copies the predecessor's normalized
`supersedes` entries and adds the predecessor path.

#### Engineering-only decision return

When `status: needs-product-decision`, `story_kind: engineering-only`, and
`product_contract: null`, reclassify the story as product-facing because observable-product
ambiguity has invalidated the behavior-preserving classification:

1. Derive the Product Contract base slug from the Technical Contract slug. Render the configured
   Product filename rule with that slug when unused; on collision append `-v<N>` using the lowest
   unused integer starting at 2. This deterministic rule is recomputable after interruption.
2. `ship-story` passes the exact path, configured Product template, roadmap/product context,
   behavior-preservation evidence, and bounded decision brief to `elephant:shape-story` in the
   main conversation.
3. `shape-story` persists `status: shaping`, asks only that bounded owner question plus coherent
   product follow-ups, runs its critics, and presents one explicit Product Contract Recap.
4. `split`, `deferred`, or `rejected` records its required rationale/next condition and STOPS the
   delivery. No technical role answers the ambiguity.

For either decision-return source:

1. The approved predecessor remains immutable. If one exists, the active approved Product
   Contract supersedes it exactly; an engineering-only return creates the first Product Contract.
2. An interrupted `shaping` artifact resumes shaping at its deterministic allocated path.
3. After explicit `approved`, dispatch the technical author/fixer—not a reviewer—to rebind
   `product_contract` to the exact active Product Contract, set `story_kind: product-facing`,
   clear the resolved decision brief, and set `status: draft`. Persist these four field changes
   atomically before remapping or review activity.
4. Return to phase selection. If the active Product Contract requires an incomplete design gate,
   complete the unchanged gate before technical remapping.
5. The author/fixer applies the approved answer, remaps affected traceability and technical
   choices, and reruns every affected read-only reviewer while the persisted status remains
   `draft`.
6. Resume the technical review loop without returning to the owner, and do not present the same
   bounded question again.

For an implementation-stage decision return, the technical author/fixer must preserve but mark
every earlier plan, execution, code-review, and conformance record as superseded history before
the revised contract can leave `draft`. That history must not count as a current plan or
execution-start evidence. After affected review passes, transition to `ready`, dispatch
`superpowers:writing-plans` to create or revise a new plan bound to the latest Technical Contract
revision, then transition the latest revision from `ready` to `implementing`. Resume the changed
implementation, code-review, and conformance work; never reuse the earlier PASS. Record a stable
contract revision marker, such as the Technical Contract commit or content digest, with each
current plan and execution evidence set so resume can distinguish it from superseded history.
Capture that contract-basis marker when author/fixer work reaches `ready`; lifecycle-only status
and delivery-evidence writes preserve it through `implementing` and `done`. Any later author/fixer
change to requirements, traceability, or technical choices replaces the marker and invalidates
the prior plan/execution evidence.

An interruption must expose either the unchanged `needs-product-decision` artifact or the fully
rebound `draft`; it must never expose a partial rebind, stale brief, old/null product path, or old
story kind.

### V2 resume table

After the validation and terminal rules above, evaluate these checks top-to-bottom:

| Order | Mechanical artifact state | Resume action |
|---|---|---|
| 1 | Technical Contract has `status: needs-product-decision` and no approved Product Contract has persisted its answer | Allocate/reuse the deterministic Product output and run the applicable decision-return shaping flow. |
| 2 | Technical Contract has `status: needs-product-decision` and an active approved Product Contract has persisted the answer, either as the first Product Contract or as a successor | Dispatch the technical author/fixer for the atomic reclassification/rebind/reset; do not re-ask the owner. |
| 3 | Product Contract has `status: approved` and its design gate is incomplete | Resume the existing design gate using `design_sensitivity`. |
| 4 | Approved Product Contract has no Technical Contract | Dispatch `elephant:author-technical-contract` with the configured Technical Contract template, rendered output path, approved product, and any completed design handoff. |
| 5 | Engineering-only triage returned no Product Contract and no Technical Contract exists | Dispatch `elephant:author-technical-contract` with the configured Technical Contract template, rendered output path, `product_contract: null`, and behavior-preservation evidence. |
| 6 | Technical Contract has `status: draft` | Resume its author/fixer and applicable read-only reviewer loop from the latest artifact. |
| 7 | Technical Contract has `status: ready` and no plan bound to the latest contract revision exists | Dispatch `superpowers:writing-plans` to create or revise that current plan. |
| 8 | Technical Contract has `status: ready` with a current compatible plan but implementation has not started for this revision | Change it to `implementing` and enter shared execution. |
| 9 | Technical Contract has `status: implementing` | Resume implementation, code review, post-implementation conformance, integration, or closeout at the first missing evidence. |
| 10 | Technical Contract has `status: done` | Verify roadmap/closeout state and report or resume only the missing closeout document step. |

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

Render the preserved legacy `filename_rule` into the discovery glob by substituting the exact
requested ID and a wildcard for `[slug]`. It must contain exactly one `[ID]` and exactly one
`[slug]`; never replace it with `<ID>-*.md`.

Parse `status_flow` as four distinct values before checking phase. Their positional roles are
authoring-incomplete, ready, implementing, and done. All status reads and writes use those values,
including a custom flow such as `Seed → Reviewed → Building → Complete`. If a mixed spec's status
is absent or not in `status_flow`, STOP and report the path and value; do not infer readiness or
translate it to bundled labels.

For an active legacy story, evaluate top-to-bottom:

| Order | Mechanical check | Resume action |
|---|---|---|
| 1 | no mixed spec matches the rendered legacy filename glob | Start the preserved authoring flow at the first configured value. |
| 2 | mixed spec is at the first configured value | Resume legacy authoring from the existing mixed spec; do not create a replacement or rerun settled questions. |
| 3 | mixed spec is at the second configured value and has an incomplete UI design gate | Resume the legacy design gate. |
| 4 | mixed spec is at the second configured value and has no plan | Dispatch `superpowers:writing-plans`. |
| 5 | mixed spec is at the second configured value with a plan | Before execution, write the third configured value and enter the shared downstream detector. |
| 6 | mixed spec is at the third configured value | Resume execution, code review, integration, or closeout from evidence. |
| 7 | mixed spec is at the fourth configured value | Verify roadmap/closeout evidence and report done or resume only the missing documentation step. |

The preserved legacy authoring flow is:

1. Load `global_specs`, draft the clarifying questions internally, and auto-assess whether mature
   industry precedent exists.
2. When precedent exists, announce the bounded research scopes and confirm before spending
   tokens. Run independent scopes in parallel when workers are available or the identical scopes
   sequentially otherwise; synthesize centrally and sharpen the remaining questions.
3. Dispatch `superpowers:brainstorming`.
4. When the profile's field-naming prerequisite applies, read `decision_ref`, agree names with the
   user, and update `field_contract_location` before writing the mixed spec.
5. Write the configured mixed spec using the selected resolved `spec_template`, rendered
   `filename_rule`, and configured `status_flow`. Keep the first configured status while
   authoring is incomplete. Advance to the second configured refined/ready status only after the
   brainstorm decisions, applicable field naming, and required template sections are complete.
   Then continue without a separate spec-review stop.

The legacy design gate keeps its prior semantics:

- disabled gates always skip;
- `ui_detection` reads the mixed spec's §6 Design Brief sensitivity, where non-Low enters the
  gate and Low skips it; a missing sensitivity fails safe and asks the user;
- commit and push the mixed spec at the second configured ready value to main before waiting;
- keep the same `manual` and `claude-design` provider behavior, `design_local_dir`,
  `handoff_file`, DesignSync mapping, human `ready_signal`, and unsupported-provider stop;
- continue only after the non-empty directory, handoff, and human signal are all present;
- the handoff maps key screens/states and transitions to mixed spec §7.

## Shared downstream detector and delivery

After the selected contract path reaches planning, preserve the existing checks in this order:

| Row → resume at | Mechanical check |
|---|---|
| plan missing → plan | legacy: glob `<plan_dir>/<ID>-*.md`, where any match counts, including split plans such as `<ID>-T8-*.md`; dual-v2: require a plan recorded against the latest Technical Contract revision |
| no branch/PR → execute | inspect `git worktree list` and `git branch --list "*<ID>*"` per `branch_pattern`; for GitHub-PR integration also inspect `gh pr list --search "<ID>"` |
| implementation/code review incomplete → execute | resume the implementation plan and configured code-review cadence from its recorded evidence |
| dual-v2 implementation complete, conformance PASS missing → conformance | run the canonical post-implementation conformance gate and its fixer/recheck loop |
| PR open, applicable conformance PASS recorded, not merged → finish | for GitHub PR use `gh pr view --json state`; non-GitHub integrations use their configured merged check |
| merged, roadmap not Done → closeout | merged per `finish.integration`, but the roadmap row lacks the configured Done marker |
| merged and roadmap Done | report fully done |

### Plan

Dispatch `superpowers:writing-plans` and write to `plan_dir`. In the selected dual-v2 branch the
plan consumes the ready Technical Contract, immutable approved Product Contract when present, and
completed design handoff when applicable. In the selected legacy branch it consumes the mixed
spec and design handoff when applicable. There is no additional plan-review stop.

### Execute

Dispatch `superpowers:using-git-worktrees`, then the profile's available
`superpowers:subagent-driven-development` or `superpowers:executing-plans` path. Inject isolation,
review cadence, `execution.gotchas`, and language rules from the profile.

- The selected legacy branch must write the third configured value before implementation; its §7 contract is
  frozen unless the mixed spec returns to the second configured ready value.
- The selected dual-v2 branch must change `ready` to `implementing` before implementation and
  record the plan plus current branch/worktree or equivalent execution evidence. Technical and
  implementation roles may not edit the approved Product Contract.
- Run `changeset_cmd` during execute commits before opening the PR, not in closeout.

### Post-implementation conformance

For dual-v2 stories, after implementation and configured code review but before integration, run
the canonical read-only `reviewers/implementation-conformance.md` prompt. The preserved legacy
branch retains its existing code-review/integration behavior.

- Product-facing stories compare the implementation evidence and diff against both the Product
  Contract and Technical Contract.
- Engineering-only stories compare the implementation evidence and diff against the Technical
  Contract and behavior-preservation boundary.

Use isolated reviewers when available or the identical prompt sequentially. Reviewers report
findings only. An implementation fixer applies evidence-backed findings to implementation, tests,
or delivery evidence; then every affected reviewer must recheck the changed evidence. Repeat
until the Integration gate is PASS.

There is no routine owner checkpoint. If conformance reveals observable-product ambiguity or a
required outcome change, the technical author/fixer persists `needs-product-decision` with one
bounded brief and routes through the same decision-return transition; no implementation role
answers it. Record the final PASS and recheck evidence in the Technical Contract. Integration is
blocked until this gate passes.

### Finish

Dispatch `superpowers:finishing-a-development-branch` and follow `finish.integration` unchanged.
For the default GitHub PR flow: open the PR, wait for every `ci_required_checks` entry to be green,
require the recorded post-implementation conformance PASS for dual-v2 stories, auto squash-merge when
`auto_merge_on_green` permits it, then clean the worktree and sync main. If `gh pr merge` errors
from a worktree, verify `gh pr view --json state` before retrying. A non-GitHub or trunk-based
integration uses its own configured mechanics; do not assume `gh`.

### Closeout docs

Use one closeout commit to set the roadmap story to Done, refresh
`instruction_refresh_targets`, and run `root_snapshot_check`. In the selected legacy branch also
advance the mixed spec by writing the fourth configured value after all acceptance criteria pass.
In the selected dual-v2 branch keep the Product Contract immutable and change `implementing` to
`done` during closeout only after verification, conformance PASS, and integration evidence are
recorded. Do not edit object-model or field-contract docs here. Use `empty_cmd` when the profile
requires a changeset for the closeout commit.

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
- A Technical Contract with `draft` or `needs-product-decision` is about to reach
  planning.
- A persisted `review` status is about to be written; review is an activity while the contract
  remains `draft`.
- A dual-v2 integration is about to start without post-implementation conformance PASS and
  affected reviewer rechecks.
- A completed artifact phase is about to be repeated instead of resumed mechanically.
- A path, check name, provider, or convention is being hardcoded instead of read from the profile.
- A merge is about to proceed while a required CI check is not green.
- A design gate is about to wait before its durable pre-gate artifact is committed and pushed.

## Common mistakes

- **Treating a missing `story_contracts` field as dual.** Existing profiles without it are
  `legacy-mixed`.
- **Letting profile mode override artifact evidence.** V2 detection runs first; legacy files
  remain resumable when no v2 artifact exists.
- **Preflighting from profile mode.** Select the active artifact branch and first incomplete phase
  before requiring capabilities.
- **Treating a filename suffix as a schema.** Exact v2 discriminator values and complete legacy
  filename/status evidence classify the artifact.
- **Inferring ownership by timestamp.** Coexisting formats require explicit `supersedes`.
- **Adding a new design protocol.** V2 only changes the durable input and handoff mapping; provider
  semantics and the human ready signal stay unchanged.

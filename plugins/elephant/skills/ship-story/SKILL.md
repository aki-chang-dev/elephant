---
name: ship-story
description: Use when delivering or resuming one Linear Story end-to-end in a repository configured with an Elephant workspace map.
---

# Ship Story

## Purpose

Deliver one current Linear Story through technical design, planning, isolated implementation,
review, integration, and native planning closeout. The Story and linked product sources drive the
work; repository artifacts are transient execution aids.

Before acting, read completely:

- `.agents/elephant/workspace.yaml` and applicable repository instructions;
- `../../references/information-routing.md`;
- `../../references/linear-planning.md`;
- `../../references/notion-knowledge.md`;
- `reviewers/implementation-conformance.md`.

Use `elephant_runtime.workspace_map` to validate the map and resolve Product/planning scope. Native
workspace entry points and current sources are the only coordination inputs.

## Establish current truth and resume point

Fetch the requested Linear Issue and verify its Team, Product membership, parent Project/Milestone,
Initiative, dependencies, blockers, status, priority, resources, and GitHub relations. Fetch every
directly linked Notion page needed to interpret current product meaning and verify Product Home
ancestry. Follow `information-routing.md`; do not use local copies when an authoritative source is
missing or stale.

Use the exact Linear Issue identifier everywhere below. The delivery branch is
`elephant/<ISSUE-ID>-<short-slug>` and transient artifacts live at:

```text
.agents/elephant/delivery/<ISSUE-ID>/technical.md
.agents/elephant/delivery/<ISSUE-ID>/plan.md
```

These files may be committed on the isolated delivery branch for resume, but must be removed before
integration. They never become product knowledge or main-branch history.

Select the first incomplete phase from current native and Git evidence:

1. product meaning complete in the current Linear/Notion sources;
2. Technical Contract ready against those current sources;
3. plan bound to the current contract-basis marker;
4. isolated worktree/branch and implementation started;
5. repository verification and code review complete;
6. post-implementation conformance passes;
7. pull request integrated;
8. native planning closeout complete and transient artifacts absent.

Announce the selected resume phase and do not redo completed work. If a transient artifact claims a
later phase than authoritative sources, Git, or verification prove, resume from the earlier fact.

## Product and technical readiness

If the Story lacks a coherent user problem, outcome, observable acceptance, or required durable
context, run `elephant:shape-story` in the main conversation. Product-semantic change always returns
there. Do not ask the owner to approve routine technical or delivery facts.

If the Story is explicitly engineering-only, require current behavior-preservation evidence. When
classification is ambiguous, shape it as product-facing.

Create or resume the transient Technical Contract by running
`elephant:author-technical-contract`. It must bind the freshly fetched Linear/Notion source bundle
or behavior-preservation source, pass applicable independent reviewers, and reach `ready` with a
current contract-basis marker. A changed observable source requirement invalidates prior technical,
plan, implementation, code-review, and conformance work and returns to shaping.

## Plan and isolated execution

When no plan is bound to the current contract-basis marker, run `superpowers:writing-plans` and
write the result to the Story-scoped transient `plan.md`. There is no owner plan-review checkpoint.

Use `superpowers:using-git-worktrees` to create or resume the exact Issue-ID branch. Follow the
repository's applicable instructions, changeset policy, verification commands, and integration
workflow. Mark the Technical Contract `implementing` only after the current plan and branch/worktree
are recorded against its basis marker.

Execute through `superpowers:subagent-driven-development` or `superpowers:executing-plans` as
available. Use test-driven development and the repository's configured code-review practice. Never
weaken the approved user outcome to make implementation easier.

## Keep Linear meaningfully current

Before every native update, fetch the current object, verify ownership and semantic preconditions,
patch only the intended fields, preserve unrelated content, and read back the result. Follow
`linear-planning.md` for uncertain writes and append-only comments.

Maintain factual state without owner review:

- **Start/resume:** move the Story to the Team's native in-progress state when work actually starts.
- **Block:** add/update the native blocker relation or status and state the blocker, user/delivery
  consequence, current risk, and next direction.
- **Implementation split:** create/link child Stories only when the current approved outcome and
  acceptance remain unchanged. A changed or newly partitioned user outcome returns to shaping.
- **Deferred/canceled:** apply only an already approved product disposition, preserving its rationale
  and next condition in native Linear state. A new priority/product tradeoff returns to shaping.
- **Complete:** mark the Story complete only after verified integration and acceptance.

Every meaningful Project or Initiative phase change gets one concise native update with progress,
current risk, and next direction. A standalone Story receives the same information once as an Issue
comment. Unchanged status, elapsed time, or polling creates no update. Reconcile equivalent comments
before appending; never create a cadence log.

## GitHub relationship and graceful fallback

The branch name and pull-request title or description must contain the exact Linear Issue ID. When
native Linear-GitHub integration is available, fetch Linear afterward and verify the branch/PR
relation became visible. When unavailable, add the ordinary PR URL to the Story and maintain factual
Linear status directly. Missing preview/link convenience does not block delivery.

Do not attach checkpoint bundles, review transcripts, test output, contract digests, or plan files
to Linear or Notion.

## Post-implementation conformance

After repository verification and code review, but before integration, run the canonical read-only
`implementation-conformance.md` reviewer with:

- the latest implementation diff and verification/code-review evidence;
- the freshly re-fetched full Linear/Notion product-source bundle or behavior-preservation source;
- the current Technical Contract and plan;
- applicable repository instructions and engineering evidence.

The reviewer never edits. The implementation fixer addresses technical mismatches and every
affected finding is rechecked. `NEEDS_PRODUCT_DECISION` returns to `shape-story`, invalidates the
current basis and downstream evidence, then resumes technical authoring and planning. Integration
requires a current conformance `PASS`; an earlier verdict never covers changed code or sources.

## Integrate and close out

Use `superpowers:finishing-a-development-branch` and the repository's configured Git workflow.
Before integration:

1. re-fetch current product sources and confirm the contract basis is still valid;
2. run the required repository verification and confirm code review/conformance are current;
3. treat the transient Technical Contract's work as complete, then remove the whole Story-scoped
   delivery directory from the branch;
4. verify the final diff contains no transient Elephant delivery artifacts;
5. create/update the pull request with the exact Linear Issue ID and wait for required checks.

Integrate only through the configured non-destructive workflow, then verify the remote result. If an
integration command reports uncertainty, read the remote PR/branch state before retrying.

After verified integration, update the Story and any meaningfully changed Project/Initiative in
Linear, including concise progress/risk/next-direction context, acceptance result, and ordinary PR
link when needed. Promote a newly approved durable product consequence to Notion only through the
knowledge disposition flow; routine delivery evidence stays out.

The removed Technical Contract does not need a durable `done` record; verified Git/Linear truth is
the closeout evidence. Clean the worktree and delivery branch according to the finishing workflow.
Final completion requires:

- merged code and required verification;
- current native Linear status and meaningful update/comment;
- visible Linear-GitHub relation or ordinary fallback link;
- no transient contract/plan in the integrated branch;
- no duplicate roadmap, checkpoint, or delivery log in Git or Notion.

## Owner return boundary

Return to the owner only for changed product meaning, ambiguous Product ownership, a strategic
priority tradeoff, changed acceptance, or a destructive/external action outside the approved
workflow. Technical design, specialist review, planning, implementation, code review, factual
status, and closeout proceed automatically.

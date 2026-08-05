# Linear planning

Linear is Elephant's live planning and progress home. Use native Linear objects and relations; do
not maintain a parallel roadmap, Story registry, state machine, or delivery ledger.

## Product model

Use these product concepts only when the shaped work needs them:

| Product concept | Linear expression |
|---|---|
| Company | Workspace |
| Default working group | Team |
| Product | Implicit when there is one; Product labels and optional views when there are several |
| Objective | Initiative |
| Workstream | Project |
| Milestone | Project Milestone |
| Story | Issue |
| Unscheduled work | Backlog |
| Time-box | Cycle, only when useful |

Product membership classifies work; it is not another hierarchy. With one Product, membership is
implicit and no Product labels are added. With multiple Products, every managed Issue, Project,
and Initiative carries exactly one verified Product label from its own Linear label namespace. A
Milestone inherits Product from its Project. Preserve unrelated labels and relations on updates.

Verify ownership by object type before use: Issue Team, Project Team set, Initiative workspace, and
Milestone parent Project. Conflicting, missing, or out-of-scope membership stops the write and
prompts one bounded Product question.

## Progressive planning

A Story may remain in the Product backlog or belong to a Project. A Project may stand alone or
contribute to an Initiative. A Milestone exists only inside a Project and groups that Project's
Stories. Create no Objective, Project, or Milestone merely to fill the hierarchy.

When an Objective is useful but no real Project exists, put its visible Initiative link in the
Story's product-context section under the exact label `Related Objective`. This gives navigation,
does not affect Objective progress, and does not create a synthetic Project or reciprocal Story
roll-up. If a real Project later appears, replace the contextual link with native
Project-to-Initiative containment. Restore or remove `Related Objective` when containment changes
so navigation never implies stale progress attribution.

A Story description contains a concise user problem, desired outcome, observable acceptance, and
links to durable context. It contains no implementation progress or internal Elephant metadata.

## Native operations

Use the host's semantic Linear connector to list, search, fetch, create, and update Initiatives,
Projects, Milestones, Issues, labels, relations, and status updates. Fetch the current object before
mutation, verify scope and the approved semantic fields, patch only the intended fields, and read
the result back. Where a call replaces a set, merge unrelated current values. Check existing links
before appending.

Before creating, search the exact native parent scope. Zero equivalent results permits creation;
one equivalent result is reused or updated; multiple or conflicting results stop for
reconciliation. After an interrupted create, use a direct scoped collection read. Adopt exactly
one semantically equivalent result. Retry only a definitively rejected write after refreshing its
preconditions; an indeterminate absence requires two fresh scoped reads across the connector's
normal consistency window before one retry.

Routine factual maintenance does not require owner review. Every meaningful Project or Initiative
phase change receives one concise native update stating progress, current risk, and next direction.
A standalone Story receives the same information once as an Issue comment. Polling, elapsed time,
or unchanged state creates nothing. New user outcomes, acceptance changes, cross-objective priority
choices, and product tradeoffs return to shaping.

Issue comments are append-only. List current comments before appending and fetch them again after
the call. If the result is indeterminate, reconcile comments for that exact Issue and meaningful
phase: zero equivalent comments permits one retry only after the connector is healthy and two fresh
authoritative reads across its normal consistency window still show absence; one equivalent comment
is adopted; multiple equivalent or conflicting comments stop for reconciliation. Equivalence uses
the visible progress, risk, next direction, Story, and phase context, never a hidden marker.

Use the Linear Issue identifier in branch names and pull-request titles or descriptions so the
native Linear-GitHub integration can link delivery. If that integration is unavailable, add an
ordinary PR link and maintain factual Linear status directly.

## Setup administration

Prefer semantic connector operations. If the connector cannot create an approved Product label or
optional multi-Product overview, setup may use an authenticated in-app browser. Semantic reads must
first establish the exact workspace and Team; the browser must visibly show the same Linear tenant
and exact target on Linear's origin. A mismatch stops before mutation, and every browser result is
verified afterward through semantic Linear reads.

For a single-to-multiple Product transition, keep the old implicit configuration authoritative.
Inventory every in-scope Issue, Project, Initiative, and Milestone, classify it as the former
Product, the new Product, or an explicit exclusion, and resolve ambiguity before approval. Create
and verify all three label types for every Product, backfill only approved objects while preserving
unrelated content, then run a fresh inventory. Publish the multi-Product configuration only when no
managed object is unlabeled or ambiguous.

An optional company overview may surface active Initiatives and Projects by Product, next
Milestones, health/risk, priority, and current attention. Reuse a suitable view. If neither the
connector nor authenticated browser can create an optional view, provide one concise UI handoff;
store its URL only after semantic read-back. Required Product labels have no manual runtime
fallback.

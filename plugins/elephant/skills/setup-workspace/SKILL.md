---
name: setup-workspace
description: Use when a repository needs its Products, engineering domains, and native Linear, Notion, and Git/GitHub information structure discovered, proposed, initialized, or refreshed.
---

# Setup Workspace

## Purpose

Analyze the repository as both a product system and an engineering system, then establish the
smallest useful native information structure. Setup organizes entry points; it does not pre-create
future roadmap levels, knowledge categories, or delivery records.

Before acting, read these references completely:

- `../../references/information-routing.md`
- `../../references/linear-planning.md`
- `../../references/notion-knowledge.md`

Use the host's native Linear and Notion connectors and ordinary Git/GitHub operations. The only
durable local output is `.agents/elephant/workspace.yaml` using `elephant.workspace/v4`.

## Procedure

### 1. Discover without writes

Read repository instructions, product documentation, workspace boundaries, Git remotes, and the
available integration capabilities. Discover existing Linear workspace/Team structures and the
Notion company-knowledge root. Fetch enough native objects to verify the selected tenant, Team,
root ancestry, and existing reusable entry points.

Derive Product candidates from user outcomes, audiences, product naming, and existing planning or
knowledge evidence. Derive engineering domains independently from repository responsibilities,
deployments, packages, instructions, and verification boundaries. Never infer that each app,
directory, Team, or deployable is a Product.

For a single Product, keep membership implicit and label-free. For multiple Products, inventory
existing managed Linear work and follow the transition rules in `linear-planning.md` before
proposing a change.

### 2. Present one human proposal

Show one compact proposal containing:

- Products and the evidence for each;
- engineering domains and their repository paths/instructions;
- Linear and Notion entry points to reuse or create;
- useful native Linear-GitHub and Linear-Notion links;
- existing valuable content worth migrating later, without moving it now;
- the exact final workspace-config projection.

Keep optional Objective, Project, Milestone, view, Shared Knowledge, Knowledge Map, Decisions, and
Knowledge structures absent until a real need exists. Existing IDs and URLs are literal. For an
object to be created, show its human target and the exact config field its verified returned value
will fill; do not invent the final value.

Resolve all material ambiguity in this conversation. Ask for one approval of the whole human
proposal. That approval covers the displayed native writes and config projection; do not ask for a
second data-entry review.

### 3. Preserve the approved outcome during application

After approval and before the first external write, create a non-main operation branch. Add and
commit one short-lived `pending-application.md` containing the approved intended outcomes, verified
target scopes, and semantic preconditions. Publish the branch when a configured remote is
available. If it cannot be published, state that recovery is limited to this working copy.

The note is a human recovery aid, not permission to write. Another device may use it for read-only
reconciliation only. Resume writes only in the original authenticated approved host context. Any
semantic change to the intended outcome or preconditions requires a revised proposal.

### 4. Apply through native products

Execute the approved operations sequentially. Before each create, search the exact verified parent
scope. Reuse or update one semantically equivalent object, create when none exists, and stop when
multiple or conflicting objects exist. Fetch every changed object and verify its ownership and
human-visible result before continuing. Preserve unrelated labels, relations, Teams, and page
content.

Use the authenticated in-app browser only for approved setup administration that the Linear
connector cannot perform. First prove the workspace and Team with semantic reads, then visibly
confirm the browser is on that same Linear tenant and exact target. Stop on any mismatch. Verify
the browser-created result afterward through semantic Linear reads. If neither route can create a
required Product label, stop before the first setup write. An optional overview may instead end in
one concise UI handoff.

If an operation is interrupted or its result is unclear, do not create a duplicate. Reconcile the
exact native scope, adopt one equivalent result, and stop on ambiguity. Retry a definitively
rejected operation only after refreshing its preconditions. For an indeterminate create with zero
results, retry once only when the connector is healthy, approved semantic preconditions are
unchanged, and two fresh authoritative scoped reads across its normal consistency window still
show absence. Never delete or roll back user-visible Linear or Notion content automatically.

Report recovery in user terms: what is already visible, what remains unapplied or unconfirmed, that
the approved outcome is preserved, and the direct place/action for continuation.

### 5. Write and integrate config last

Only after every required external result reads back correctly, materialize its verified ID or URL
into the declared field, validate the complete workspace map, and atomically replace the one config
file. Build a config-only change against the current remote integration head. Stop on semantic
drift, overlap, or conflict; never force-push or guess through a config conflict.

Integrate through the repository's configured workflow, push without force, and verify the remote
integration branch contains the validated config. The final integrated change excludes the pending
note and its operation history. Then remove the note and clean up the local and remote operation
branch.

## Completion

Return the Product/domain mapping, the native Linear and Notion entry links, integrations that are
active or gracefully degraded, and the verified config location. Readiness requires every
configured entry point to resolve to its approved tenant, Team, repository, or page ancestry.

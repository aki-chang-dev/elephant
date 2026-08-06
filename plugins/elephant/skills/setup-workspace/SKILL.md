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

Classify every proposed operation before presenting the proposal:

- **Elephant** when the active semantic connector or authenticated browser can execute the
  operation and its result can be verified by semantic read;
- **Owner setup** when Elephant cannot execute the low-frequency administrative operation but can
  verify its result afterward by semantic read;
- **Unavailable** when no execution route produces a result Elephant can verify. A required
  unavailable operation blocks the proposal; an optional operation is omitted or declared
  degraded.

Treat capability as operation-specific. Connector availability does not imply workspace rename,
label creation, view creation, or native-integration administration. A declared tool rejected by
its backing service is unavailable for the current run.

### 2. Present one human proposal

Show one compact proposal containing:

- Products and the evidence for each;
- engineering domains and their repository paths/instructions;
- Linear and Notion entry points to reuse or create;
- useful native Linear-GitHub and Linear-Notion links;
- existing valuable content worth migrating later, without moving it now;
- the exact final workspace-config projection.

Group every proposed operation into **required structure** and **enhancements**, and give each its
execution owner: **Elephant**, **Owner setup**, or **Unavailable**. Keep unavailable required
structure out of an approval request; omit unavailable enhancements or state their degraded
outcome. The single approval covers both Elephant's writes and the displayed owner checklist.

Keep optional Objective, Project, Milestone, view, Shared Knowledge, Knowledge Map, Decisions, and
Knowledge structures absent until a real need exists. Existing IDs and URLs are literal. For an
object to be created, show its human target and the exact config field its verified returned value
will fill; do not invent the final value.

Resolve all material ambiguity in this conversation. Ask for one approval of the whole human
proposal. That approval covers the displayed native writes, owner checklist, and config projection;
do not ask for a second data-entry review.

### 3. Apply through native products

The approving conversation carries intended outcomes, target scopes, and semantic preconditions
until the workspace map is integrated. A cold context without that conversation may reconcile
already visible authoritative native results read-only, but must present the reconstructed compact
proposal once before any remaining external or config write.

Apply approved **Elephant** operations sequentially and verify each result. Before each create,
search the exact verified parent scope. Reuse or update one semantically equivalent object, create
when none exists, and stop when multiple or conflicting objects exist. Fetch every changed object
and verify its ownership and human-visible result before continuing. Preserve unrelated labels,
relations, Teams, and page content.

Use the authenticated in-app browser only for approved setup administration that the Linear
connector cannot perform. First prove the workspace and Team with semantic reads, then visibly
confirm the browser is on that same Linear tenant and exact target. Stop on any mismatch. Verify
the browser-created result afterward through semantic Linear reads.

If **Owner setup** operations remain, return one numbered checklist after the supported writes.
Each item names the exact tenant, native object type, Product or company scope, final human-visible
name and applicable color, description, or relation, shortest known UI location or direct entry
link, whether it is required or an enhancement, and the semantic read Elephant will use to verify
it. The checklist contains no implementation explanation, connector diagnostics, internal setup
state, or request for the owner to copy opaque IDs.

The owner's completion message is a resume signal, not verification evidence. Re-read every exact
native scope: adopt one equivalent result, keep zero pending, and stop on multiple or conflicting
results. A required owner-provisioned object must read back before its stable ID or URL enters the
workspace map. Unsupported enhancements may degrade when an ordinary scoped query or link keeps
the workflow correct.

If an operation is interrupted or its result is unclear, do not create a duplicate or retry
automatically. Reconcile the exact native scope, adopt one equivalent result, and stop on ambiguity.
An indeterminate result remains pending until a later run can prove the intended object exists or
fresh preconditions permit a new attempt. For a definitively rejected operation, stop and record
the direct resume action; only a later explicit resume run may revalidate preconditions and decide
whether to make a new attempt. Never delete or roll back user-visible content automatically.

Report recovery in user terms: what is already visible, what remains unapplied or unconfirmed, that
the approved outcome is preserved, and the direct place/action for continuation.

### 4. Write and integrate config last

Only after every required external result reads back correctly, materialize its verified ID or URL
into the declared field and validate the complete workspace map in the current isolated workspace.
Stop on semantic drift, overlap, or conflict; never force-push or guess through a config conflict.

Integrate the config through the repository's configured workflow, push without force, and verify
the remote integration branch contains it. Setup creates no separate recovery branch or note.

## Completion

Return the Product/domain mapping, the native Linear and Notion entry links, integrations that are
active or gracefully degraded, and the verified config location. Readiness requires every
configured entry point to resolve to its approved tenant, Team, repository, or page ancestry.

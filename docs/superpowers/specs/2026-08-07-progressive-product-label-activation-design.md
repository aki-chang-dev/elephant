---
schema: elephant.story/v2
story: progressive-product-label-activation
slug: progressive-product-label-activation
kind: product
status: approved
design_sensitivity: Low
amends:
  - docs/superpowers/specs/2026-08-05-one-person-company-information-coordination-product-v2.md
  - docs/superpowers/specs/2026-08-05-one-person-company-information-coordination-technical.md
  - docs/superpowers/specs/2026-08-06-capability-adaptive-workspace-setup-design.md
---

# Progressive Product-label activation

## Problem

Elephant creates planning levels only when they express real product meaning, but its multi-Product
workspace contract currently requires Issue, Project, and Initiative Product labels during initial
setup. That makes an unused future planning level block an otherwise complete workspace. It also
forces setup to solve connector or owner-administration gaps for objects that may never exist.

The durable rule remains valid: every managed Linear object in a multi-Product workspace must carry
exactly one verified Product label from its own native label namespace. The mistake is requiring
every namespace to be activated before that object type exists.

## Outcome

Product-label namespaces activate progressively, at the same time as their native planning level:

- Issue Product labels are required during multi-Product setup because Story and Backlog are the
  base planning level.
- A Product's Project label is required when setup discovers an existing managed Project for that
  Product or an approved operation will create its first Project.
- A Product's Initiative label is required when setup discovers an existing managed Initiative for
  that Product or an approved operation will create its first Initiative.

An absent Project or Initiative label ID means that planning level has not been activated for that
Product. It does not make the workspace map invalid and does not weaken classification after the
level is activated.

## Behavior

### Initial setup

For multiple Products, setup creates or verifies every Issue Product label. It inventories existing
Projects and Initiatives. Any existing managed object must be assigned to one Product, and that
Product's corresponding label is created, verified, and backfilled before setup completes. Products
without objects in that namespace need no label yet.

Capability classification applies only to structure required by current native state and the
approved setup proposal. Missing support for an unused future label namespace does not block setup.

### First use of a planning level

When an approved roadmap operation would use a Project or Initiative for a Product whose matching
label ID is absent, the roadmap recap includes activation of that Product-label namespace and the
workspace-map update. After approval, Elephant:

1. searches the exact native label namespace and reuses one equivalent label or provisions one;
2. reads back the stable label ID and ownership;
3. writes and integrates the ID into `.agents/elephant/workspace.yaml`;
4. re-reads the workspace map, then creates or updates the planning object with that label.

The existing capability-adaptive setup rules apply to provisioning. Owner setup is allowed only
when Elephant can semantically verify the result. If the label cannot be provisioned and verified,
that planning level remains unavailable and no unlabeled object is written.

### Runtime lookup and validation

`elephant.workspace/v4` remains the schema. In a multi-Product map, `issue_label_id` remains required
for every Product; `project_label_id` and `initiative_label_id` are optional. Present label IDs must
remain valid and unique inside their native namespace.

`planning_scope()` returns only configured Product-label namespaces. A workflow must require the
label matching the object type it is about before issuing a multi-Product write. It must not fall
back to repeated name searches, substitute an Issue label for another native label type, or create
an unlabeled Project or Initiative.

### Single-to-multiple Product transitions

Every existing managed Issue, Project, and Initiative is still inventoried and classified. Each
Product receives Issue labels. Project and Initiative labels are created only for Products that
own existing objects in those namespaces. The transition publishes only after all existing managed
objects have exactly one Product classification and no ambiguity remains.

## Failure and recovery

- An absent optional label ID blocks only operations for that Product and object type, not unrelated
  Story delivery or other already activated planning levels.
- A rejected or indeterminate label write follows the existing exact-scope reconciliation rules and
  never triggers an automatic duplicate attempt.
- If the native label is verified but config integration stops, a later run adopts the same label
  and resumes the config update before any planning-object write.
- Existing unlabeled or ambiguously labeled objects are migration conflicts, not evidence that the
  namespace is inactive.

## Scope

Revise only workspace-map validation/routing, setup and Linear planning guidance, roadmap activation
behavior, installed smoke coverage, and focused contract tests. Do not add a new schema version,
provider adapter, persistent setup ledger, background synchronizer, or generic label registry.

## Acceptance scenarios

1. A new two-Product workspace with no Projects or Initiatives validates with two Issue label IDs
   and no Project or Initiative label IDs.
2. `planning_scope()` returns the Issue label and omits inactive namespaces.
3. A roadmap that introduces the first Project activates and persists the Product's Project label
   before writing that Project; Initiative remains inactive.
4. Existing Projects or Initiatives cannot pass setup as inactive: they are classified and
   backfilled first.
5. Present duplicate or malformed label IDs remain validation errors.
6. A single-Product workspace remains implicit and label-free.

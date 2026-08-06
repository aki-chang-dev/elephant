---
name: ship-story
description: Use when delivering or resuming one Linear Story end-to-end in a repository configured with an Elephant workspace map.
---

# Ship Story

## Purpose

Deliver one current Linear Story through proportionate technical assurance, implementation,
integration, and native planning closeout. Product meaning remains in Linear and Notion; Git owns
executable behavior.

Before acting, read completely:

- `.agents/elephant/workspace.yaml` and applicable repository instructions;
- `../../references/information-routing.md`;
- `../../references/linear-planning.md`;
- `../../references/delivery-assurance.md`;
- `reviewers/implementation-conformance.md`.

Load `notion-knowledge.md` only when closeout must apply an already approved durable knowledge
change. Validate the workspace map with `elephant_runtime.workspace_map`.

## Establish current truth and resume point

Fetch the exact Linear Story and verify Team, Product, planning relations, dependencies, blockers,
status, priority, resources, and GitHub relations. Fetch directly linked Notion content needed to
interpret the current outcome and verify Product Home ancestry. Stop expanding when the approved
outcome is supported.

The delivery branch and pull request contain the exact Linear Issue identifier. Repository
instructions own their remaining naming and integration mechanics. Optional transient artifacts
use:

```text
.agents/elephant/delivery/<ISSUE-ID>/technical.md  # elevated only
.agents/elephant/delivery/<ISSUE-ID>/plan.md       # ordinary/elevated multi-step work only
```

Select the first incomplete result from native and Git evidence:

1. current product meaning is coherent;
2. assurance depth is supported by current evidence;
3. any required transient artifact is current;
4. isolated implementation has started;
5. repository verification and final delivery review pass;
6. pull request is integrated;
7. Linear closeout is current and transient artifacts are absent.

An ordinary atomic Story resumes from its Story, branch/diff, verification, PR, and Linear state;
it needs no local workflow artifact. A current-source-valid Technical Contract made by this
workflow resumes elevated assurance. Earlier facts override artifact claims.

## Product readiness

If the Story lacks a coherent problem, outcome, observable acceptance, or required durable context,
run `elephant:shape-story` in the main conversation. Product-semantic change always returns there.
Engineering-only work requires current behavior-preservation evidence. Ambiguity is product-facing.

## Select assurance and execution depth

Apply `delivery-assurance.md` without asking the owner to classify risk.

### Ordinary assurance

- Atomic work: keep one in-session execution checklist.
- Multi-step work: write one concise transient `plan.md` with source observation, tasks, and exact
  verification commands.
- Do not create a Technical Contract or dispatch specialist design reviewers.
- Execute in the current isolated workspace with the repository's testing, changeset, and
  verification practices. Use additional workers only for genuinely independent work whose context
  separation is useful; parallelism alone is not a token saving.

### Elevated assurance

- Name the supported risk or unresolved uncertainty.
- Run `elephant:author-technical-contract`; it selects only specialists matching that risk.
- Add a concise transient plan only when implementation has multiple dependent steps.
- Execute with the repository's required testing, changeset, verification, and risk controls.

Every path ends in one independent final delivery review. Repository-mandated checks remain valid;
Elephant does not add a second generic code-review layer merely because one is available.

## Keep Linear meaningfully current

Before a native update, fetch the current object, verify ownership and intended fields, preserve
unrelated content, and read back the result.

- Move to the native in-progress state when implementation starts.
- Record a blocker relation/status and one concise consequence/risk/next-direction update when
  delivery is genuinely blocked.
- Create child Stories only when the approved outcome and acceptance remain unchanged; changed
  outcomes return to shaping.
- Apply deferred/canceled state only from an approved product disposition.
- Complete only after verified integration and acceptance.

Write one Project/Initiative update only for a meaningful phase change; use one Issue comment for a
standalone Story. Unchanged polling creates nothing.

## Final delivery review

After implementation and repository verification, re-establish complete current product authority
or behavior-preservation evidence and run `implementation-conformance.md` once in the applicable
ordinary/elevated mode. The reviewer receives current implementation evidence, not review history.

Fix load-bearing findings. Map each fix to affected requirements/files/evidence and recheck only
that packet. Unsupported preferences receive a concise evidence-based ruling and do not enlarge
scope. `NEEDS_PRODUCT_DECISION` returns to shaping and invalidates affected downstream work.

## Integrate and close out

Follow the repository's configured non-destructive Git workflow without invoking a generic owner
choice menu. Before integration, confirm current product meaning, repository verification, final
review, required checks, and absence of transient delivery artifacts in the final diff.

Keep the exact Linear Issue identifier in branch/PR identity. After Git activity, verify the native
Linear–GitHub relation; when unavailable, add the ordinary PR URL. After verified integration,
complete the Story and write only meaningful Project/Initiative or standalone-Story context.

If assurance was elevated, closeout names the concrete risk that justified it. Routine delivery
does not expose reviewer choreography, test logs, or transient artifacts in Linear or Notion.

Return to the owner only for changed product meaning, Product ownership, strategic priority,
acceptance, or an external/destructive action outside the approved workflow.

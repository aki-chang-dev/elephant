# Notion knowledge

Notion stores durable product meaning and decisions that will remain useful beyond one Story. It
does not copy live roadmap, status, progress, implementation plans, review output, test output, raw
conversation, or routine delivery history from their authoritative homes.

## Page tree

Organize ordinary pages as:

```text
Company Knowledge
|- Product Home
|  |- Overview
|  |- Knowledge Map          (only after durable content exists)
|  |- Decisions              (created with its first Decision)
|  `- Knowledge              (created with its first Knowledge page)
`- Shared Knowledge          (only for genuinely cross-Product knowledge)
```

Product Home begins with a concise Overview and a link or live preview to Linear planning. Do not
create empty Knowledge Map, Decisions, or Knowledge sections during setup. A Knowledge Map is short
ordinary page content: human titles linked to canonical pages plus one sentence describing when
each is relevant.

Every Product-specific page is a descendant of that Product Home. Shared pages are descendants of
the configured Shared Knowledge root. Identity is the exact parent plus human title: zero matches
may create, one match updates, and multiple matches stop for reconciliation. Wrong-parent and
wrong-Product pages remain untouched. Links never replace canonical containment.

## Valuable content

A **Decision** page has a stable human title and explains the decision, product context or problem,
rationale, consequences, and related Linear work, Knowledge, or superseding Decision. When a
Decision becomes obsolete, visibly mark it superseded and link to the current result rather than
silently rewriting history.

A **Knowledge** page explains the problem it addresses, when it is useful, the current conclusion,
and related Knowledge, Decisions, and Linear work. Living knowledge updates its canonical page in
place.

Use one of four shaping dispositions: `linear_only`, `decision`, `knowledge`, or
`decision_and_knowledge`. A simple Story remains only in Linear. Create or update Notion content
only when the approved result has durable explanatory value.

## Native operations and retrieval

Use the host's semantic Notion search, fetch, create, and update operations. Search within the exact
approved parent and compare human titles. Verify root ancestry and content after every mutation.
Patch the intended page while preserving unrelated user content, then maintain the Product's short
Knowledge Map and ordinary reciprocal Linear links.

If a create result is indeterminate, reconcile through direct reads of the exact approved parent,
not workspace-wide text search. Adopt one semantically equivalent child and stop on multiple or
conflicting results. Zero results remains pending until a later run can safely attempt it. A
definitively rejected call stops with a direct resume action; only a later explicit resume run may
refresh preconditions and decide whether to make a new attempt. An indeterminate call is never
retried automatically in the uncertain run.

For product-meaning questions, read directly linked pages first, then Product Home and Knowledge
Map, then Product Home descendants. Expand to Shared Knowledge and finally the workspace only when
narrower evidence is insufficient. Stop when the answer is supported and return canonical page
links.

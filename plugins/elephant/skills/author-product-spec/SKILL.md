---
name: author-product-spec
description: Use when a one-sentence product idea or existing Product Home needs the minimum durable product foundation established or refreshed in Notion.
---

# Author Product Spec

## Purpose

Establish or refresh the durable product meaning needed to guide future shaping and planning. The
output is the smallest useful set of ordinary Notion pages under Product Home—not a repository spec
system, implementation design, or roadmap.

Before acting, read completely:

- `../../references/information-routing.md`
- `../../references/notion-knowledge.md`
- `../../references/linear-planning.md`

## Discover current meaning without writes

Accept a one-sentence idea. Resolve the likely Product from user/audience/outcome evidence and ask
one bounded question only when the Product boundary is genuinely ambiguous.

Read current Product Home, Overview, Knowledge Map, directly relevant Knowledge/Decisions, and the
linked Linear planning entry. If a workspace map is not yet present during kickoff, discover the
verified Company Knowledge root and existing exact-parent Product Home in the active connector
context; `setup-workspace` will later persist the entry points.

Use exact parent plus human title identity. Zero matches may be proposed for creation, one is the
canonical page to update, and multiple matches stop for reconciliation. Wrong-parent and
wrong-Product pages remain untouched.

## Product-only conversation

Ask one question at a time and discuss only durable product meaning:

- product, audience, context, and problem;
- core value and desired user/business outcomes;
- product boundaries and explicitly unchanged/out-of-scope areas;
- important user-facing concepts, rules, defaults, terminology, and experience principles;
- decisions whose rationale will matter beyond one Story;
- current knowledge that future shaping or planning should be able to retrieve.

Do not define fields, schemas, modules, libraries, deployment, architecture, implementation
sequence, or test design. A product concept may become living Knowledge; it is not an entity/field
contract. Planning order belongs to `decompose-roadmap`, and individual feature behavior belongs to
`shape-story`.

## Decide what is worth preserving

Apply a future-value test to every result:

- update **Overview** when it changes or completes the stable explanation of product, audience,
  problem, core value/outcomes, boundaries, or product principles;
- create/update **Knowledge** when a reusable current conclusion will answer future product
  questions;
- create a **Decision** when preserving the context, rationale, and consequences of a durable choice
  is independently valuable;
- write nothing when the result is local to one Story, repeats existing meaning, is temporary, or
  has no future retrieval value. Route Story-local work to `shape-story` instead.

Living Knowledge updates the one canonical page in place. Obsolete Decisions are visibly
superseded and linked to the current result. Do not preserve raw discussion, technical design,
planning sequence, progress, review history, or implementation notes.

Do not create empty Knowledge, Decisions, Shared Knowledge, or Knowledge Map pages. Create the
exact category lazily with its first approved child; create/update Knowledge Map only when durable
children exist.

## One foundation recap and approval

Before asking for approval, self-check the proposal from the future reader's perspective: can they
understand what the product is, whom it serves, why it matters, what it does not mean, and where to
look next without reading this conversation?

Present one human-readable recap:

1. current Product foundation already preserved;
2. proposed Overview changes;
3. Knowledge pages to create/update and the future question each answers;
4. Decisions to create/supersede and why their rationale remains useful;
5. content intentionally left only in the current conversation/Story;
6. exact Notion parents/titles and reciprocal Linear links approval will apply;
7. unresolved product questions.

If no durable change is needed, report that result and existing direct links without requesting an
approval or writing anything. Otherwise resolve product questions, then wait for one explicit
approval of the complete recap. Do not add separate north-star, object-model, or final-document
review gates.

## Apply natively and verify

After approval, use semantic Notion operations and `notion-knowledge.md` recovery rules:

1. Re-fetch exact parents, current pages, and semantic preconditions.
2. Reuse/update the one canonical Product Home and Overview or create missing approved entry points
   under the verified Company Knowledge root.
3. Create category nodes only together with their first approved child. Preserve unrelated content.
4. Create/update approved Knowledge and Decision pages with the human sections defined in the
   reference.
5. Maintain the short Knowledge Map and ordinary reciprocal Linear links/previews without copying
   roadmap or status.
6. Fetch every affected page, verify exact ancestry/title/content/links, and return canonical URLs.

For rejected or indeterminate writes, reconcile the exact parent before retrying and stop on
multiple/conflicting matches. Preserve the approved result without repeating owner review while
meaning and preconditions remain unchanged. Never delete or roll back user pages automatically.

## Completion

Return Product Home, Overview, relevant Knowledge/Decision, Knowledge Map when present, and Linear
planning links. Create no master spec, object model, field contract, glossary, AD/ED log, product
spec directory, or Git change log.

## Red flags

- Existing Notion meaning is copied into Git instead of updated in place.
- Technical structure appears because “spec” is interpreted as implementation design.
- Blank categories are created for completeness.
- A Story-local conclusion becomes permanent Knowledge without future value.
- Multiple owner checkpoints replace one complete foundation recap.
- A complete current foundation is rewritten merely because no repository spec files exist.

# Research before shaping

Use targeted research to reduce the owner's decision burden before interactive product questions.
Start from current Product context and the actual user task, not an assumed implementation.

## Scope and fan-out

Draft the questions internally. Identify which have mature product or industry precedent and
which are preferences only the owner can settle. For relevant precedent, announce the research
scopes and dispatch independent, read-only research subagents before asking design questions.
Usually three to five distinct scopes suffice; use fewer when that covers the real uncertainty.
Split by relevant competitor, user journey, or provider constraint rather than asking every worker
to research everything. Each worker receives the user problem, known constraints, unanswered
questions, exclusions, and the evidence format below, without a predetermined desired conclusion.

Use normal search, browsing, and available product documentation. This is directed collection of
competitor product design and documented implementation approaches, not a deep-research workflow;
do not invoke a deep-research skill or insert a research-cost approval. Existing access and action
permissions still apply. If worker delegation is unavailable, perform the same bounded scopes
sequentially and state the fallback. Do not skip research because parallelism is unavailable.

Reuse current, applicable evidence. For an internal/bespoke change with no useful external
precedent, or a narrow revision already covered by verified sources, state that basis briefly and
inspect the existing experience instead of manufacturing a competitor survey. Missing online
evidence means an unknown, not proof that a feature or constraint does not exist.

## Evidence and synthesis

Workers return two separate sets of findings:

- **Product evidence:** observed entry/flow, user decisions, defaults, visible rules, states,
  recovery, and limits relevant to the question; exact source URLs/sections, access date, and
  applicable product/version. Prefer official documentation or directly observable behavior.
- **Deferred technical evidence:** documented mechanisms, provider facts, implementation
  approaches, and unresolved feasibility checks, with the same source provenance. These are
  observations and hypotheses for delivery, not selected architecture or promised acceptance.

Distinguish sourced facts, inference, and unknowns. Record conflicting evidence and applicability
limits. A marketing claim or a competitor's undocumented backend is not implementation proof.
Do not infer an identifier guarantee, data relationship, or error behavior from a UI screenshot.

The parent reconciles findings, checks the sources supporting consequential claims, and compares
the relevant choices against this Product's user tasks and operating constraints. Stop when the
decision-critical questions are supported or the remaining gaps are explicit; expand only a scope
needed to settle such a gap. Present a concise evidence-backed product recommendation, alternatives
with meaningful consequences, and remaining owner decisions. Do not ask the owner to do the
research, choose technical mechanisms, or reconfirm decisions already supplied by context.

## Carry evidence into delivery

Keep the working evidence index in-session during shaping. The recap names the material research
basis and the source links proposed for the Story. After approval, retain those exact URLs or
stable reference identities with short relevance notes in the Story's product/research context.
Preserve enough source pointers to recover deferred technical evidence in a fresh session. If a
decision-critical source is inaccessible or ephemeral, explicitly carry that uncertainty forward
for revalidation; a dead link is not evidence. Do not write research transcripts, an implementation
plan, or a second product contract into Git or Notion. Durable product conclusions follow the
existing Notion knowledge-disposition rules.

`ship-story` retrieves this research context alongside the approved shaping outcome. It evaluates
the deferred technical observations against that outcome and current repository/provider facts
before choosing an implementation or assurance depth. No research finding silently becomes an
approved requirement. If validation would change observable behavior or acceptance, return only
that bounded product decision to shaping; ordinary technical choices remain agent-owned.

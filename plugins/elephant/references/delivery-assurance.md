# Delivery assurance

Assurance depth follows supported delivery risk. The owner approves product meaning; Elephant
selects technical depth from the approved outcome and current repository evidence.

## Ordinary assurance

Use ordinary assurance when no material risk below is supported. Atomic work uses an in-session
checklist. Multi-step work uses one concise transient plan containing the Story/source observation,
bounded tasks, and verification commands. Complete repository verification and an author acceptance
check against the actual user flow. Independent review is conditional: use it for a named material
risk, an explicit user request, or a repository requirement. A Technical Contract and specialist
design review are absent. A repository review that covers the same scope satisfies this check.

## Elevated assurance

Use elevated assurance when current evidence shows material money-path, destructive data or
migration, security/privacy/authorization, concurrency/transaction, production rollout/recovery,
or major system-boundary risk. Touching one of these areas alone is not a trigger. Name the
failure mechanism and affected outcome. Create a Technical Contract and select only specialists
matching the risk; complete one independent final delivery review after implementation.

**Uncertain risk:** inspect the relevant code, tests, and operating constraints first. Elevate when
a specific potentially severe failure remains unresolved after that inspection. Unfamiliar code
or imagined future usage alone does not justify escalation. Do not ask the owner to classify
technical risk. State the reason for elevated assurance at closeout.

## Context packets

Carry a source index in-session: exact source identity, current observation, and why it is needed.
Hydrate direct source content once, then refresh exposed version/last-edited evidence at phase
boundaries; fetch the full body again when the observation changed or currency cannot otherwise be
proved.

Every review packet states the user, intended outcome, supported usage/scale, acceptance, explicit
non-goals, and named risk, using available evidence; mark unknowns instead of inventing usage rates.
Specialist packets are role-scoped: relevant source items, contract sections, repository paths,
and evidence. Product-conformance and final delivery review receive complete current product
authority or the complete behavior-preservation source. A link or stale preview is not authority.
Include accepted finding dispositions during rechecks so settled decisions remain visible.

## Findings and rechecks

A blocking finding supplies all of: a supported triggering scenario, an affected current requirement
or applicable repository rule, concrete implementation/design evidence, material user/business or
operational consequence, and the smallest sufficient required outcome. For a severe risk without
an explicit product requirement, identify the safety/security/data invariant and credible failure
path. Severity labels and generic best practices alone are insufficient. Missing evidence prompts
a focused inspection; only a decision-critical gap blocks. Low frequency does not excuse credible
severe harm such as data loss, unauthorized access, or money errors.

The author adjudicates each finding before editing: accept a blocker, defer a useful non-blocking
improvement, or reject an unsupported/out-of-scope claim, with a short reason. Compare expected
harm and supported exposure with fix cost and regression risk; prefer the smallest sufficient fix.
Do not invent percentages or weaken approved acceptance to make delivery pass. Non-blocking
suggestions need no fix, automatic backlog creation, or owner decision. Return to shaping only
when resolving a material ambiguity changes product meaning.

Run one initial review and, when needed, one focused recheck of accepted blockers and repair
regressions. Map fixes to affected requirements/files/evidence. Carry their disposition and fresh
verification into the recheck. Reopen a settled finding only with new evidence; admit a newly found
blocker only with the same scenario/evidence/materiality bar. Unrelated improvements end here.

After that recheck, the author closes resolved items from evidence. If a blocker persists, stop
automatic reviewer cycling and choose a concrete next action: inspect/reproduce the failure, apply
a bounded correction and targeted verification, or resolve conflicting technical evidence once.
Another independent recheck requires a named unresolved material risk that author verification
cannot settle; it does not restart general review. If no safe resolution is available, report the
specific blocker. A review budget never waives a real blocker or required repository check.

Stop when approved acceptance, required checks, and accepted blockers are resolved. Zero
non-blocking observations and a fresh full-review PASS after every edit are not exit requirements.

## Token boundary

Never use a hard token or context quota that can truncate decision-critical evidence. Narrow by
relevance and stop when the question is supported. Parallel agents may reduce elapsed time; do not
claim token savings without measured usage evidence.

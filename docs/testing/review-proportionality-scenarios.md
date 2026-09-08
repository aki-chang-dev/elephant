# Scenario-based review validation

Evaluated on 2026-09-08 with separate read-only baseline and revised-policy agents. This records
instruction-following decisions on synthetic scenarios, not measured production quality or savings.
Repository unit/packaging checks are separate from this behavioral evaluation.

## Baseline

The prior policy already rejected unsupported preferences and scoped rechecks to affected evidence.
The baseline agent nevertheless required independent review for a static typo and identified that
unqualified “Uncertain risk” could elevate work merely because the reviewer had not inspected code.
It found no explicit materiality test for a claimed concrete risk, no explicit closure against
continued speculative review, and unclear handling of newly discovered serious recheck findings.

## Revised policy forward-test

An independent agent read the current assurance policy, ship-story and its final reviewer,
shape-story, and author-technical-contract. It received the scenarios without expected verdicts.

| Scenario | Observed decision |
|---|---|
| Approved static typo; required checks pass | Ordinary author acceptance check; no default independent review or Technical Contract. |
| 12-user export label fix; reviewer demands million-row streaming | Reject unsupported scale requirement; no automatic repair, backlog creation, or owner decision. |
| Rare reproducible cross-tenant retry exposure; costly fix | Elevated assurance and blocking remediation; low frequency/cost cannot waive tenant isolation. |
| Fixed blocker; focused checks pass; recheck requests unrelated cleanup and theoretical cases | Retain disposition, reject unsupported scope, stop general review without another full PASS. |
| Reviewer has not read code and labels risk unknown | Inspect first; escalate only an evidenced unresolved potentially severe failure. |
| Real blocker persists after focused recheck; author cannot verify mitigation | Investigate/correct; allow named-risk independent recheck when needed; never integrate unresolved. |
| Checkout wording obscures recurring charge | Material copy critique and bounded shaping; owner decides unsettled meaning, proximity to money alone does not elevate technical assurance. |
| Repository mandates independent review on every change | Honor it; reuse equivalent review and preserve required checks/rechecks. |

The evaluator reported no concrete cross-file contradiction changing these decisions. This is a
single forward-test pass, not a statistical reliability claim. Real deliveries should establish
whether review time and unnecessary repairs decline without increasing escaped material defects.

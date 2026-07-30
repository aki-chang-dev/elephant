# Product-First Story Skill Tests

This document preserves the representative RED worker observations used to shape the v2 skills.
Later GREEN runs use the same scenarios and compare their questions, decisions, and stated
reasoning against these records.

## Provenance

Each quoted block is a representative verbatim excerpt copied from the completion output of its
canonical RED worker task on 2026-07-30:

| Scenario | Canonical worker task |
|---|---|
| Product drift | `/root/red_product_drift` |
| Invalid product idea | `/root/red_bad_idea` |
| Technical overreach | `/root/red_technical_overreach` |

This committed test record is the durable capture; no separate repository transcript file exists.

## RED baseline: product drift

Current `ship-story` asked about copied entities, tokens, deploy paths, status, endpoints, and
API/data contracts before completing product definition, then wrote a mixed Engineering Brief +
Design Brief.

### Verbatim RED worker questions

1. 你说的“相似 setup”是希望默认复制完整配置，还是只复制 Traffic Source、Offer 和基础跳转设置？
2. 新 Campaign 是否一律创建为 Draft，并生成全新的 tracking link，同时不复制点击、转化、部署状态、测试 token、preview token 和 delivery health？
3. Lander 的目标域名与 deploy path 不能被两个 Campaign 同时占用；复制时应自动生成新 path、暂不复制 Lander 配置，还是让用户在弹窗里选择？
4. 入口是否放在 Campaign 行的 `…` 菜单中，并先打开一个只要求确认新名称的小弹窗？
5. 复制完成后，是直接打开新 Campaign 的编辑 Sheet 让买手调整后再启用，还是留在列表并仅显示成功提示？

### Verbatim RED worker decisions

- `POST /api/campaigns/:id/duplicate` — 接收新名称，返回完整的新 Campaign。
- 请求：`{ name: string }`。响应：`{ campaign: Campaign }`。
- Campaign 本体与所有配置关联行在单个 DB transaction 内复制。
- `status='draft'`；`closing_expires_at`、`test_token`、`bypass_token` 置空。
- Lander config 生成新 ID，并将 deploy path 转换为同域名下未占用的新路径。
- `POST /api/campaigns/:id/duplicate` ↔ `DuplicateCampaignDialog`; UI 用返回对象打开 `CampaignEditSheet`。

### Verbatim RED worker ready rationale

- **Status**: Refined
- §1、§2、§5、§7 为 Code 与 Design 共识。
- §3、§4 约束实现；§6 约束复制入口、确认与完成反馈。
- **Open Design Questions**
  - 无；brainstorm 已锁定入口、确认信息、成功去向与错误反馈。

## RED baseline: invalid product idea

A roadmap-progress dashboard card exposing phase, slice ID, and implementation percentage had no
formal reject/defer disposition. Current workflow effectively approved it and specified a
roadmap-progress API plus user-visible internal delivery language.

### Verbatim RED worker questions

1. What operational decision should an operator make after viewing this progress card?
2. Which operators may see it, and is exposing internal roadmap phases and slice IDs acceptable to that audience?
3. What system is the source of truth for the current phase and active slice?
4. How exactly is “percent implementation complete” calculated: completed acceptance criteria, completed slices, engineering tasks, or a manually maintained value?
5. Where should the card appear, how frequently should it refresh, and what should it show when progress data is unavailable or stale?

### Verbatim RED worker disposition and rationale

- “Formal disposition: No. The current workflow has no explicit approve/split/defer/reject product gate. It only decomposes when scope is too large, then proceeds from brainstorming into a `Refined` spec. Effective selection: **approve**.”

### Verbatim RED worker decisions

- API shape: `{ phase, activeSliceId, completionPercent, updatedAt, status }`.
- Example UI copy included `Active slice: P-31` and `42% implemented`.
- The draft specified loading, unavailable, stale, and complete states and a Medium design sensitivity.

## RED baseline: technical overreach

A general technical author produced a strong draft but silently resolved ambiguous product meanings
for copied IDs, name suffixing, and edit-only configuration, and used self-review instead of
independent specialist review.

### Verbatim RED worker assumptions

- “IDs are not copied” means generated identity and runtime IDs: campaign ID, slug/tracking link, lander-config row IDs, deployment IDs, tokens, timestamps, and similar values. Reference IDs required to preserve configuration—traffic source, offers, landers, domains, and filter lists—remain selected.
- “User-owned configuration” is bounded by what the existing normal Create flow represents: name, traffic source, weighted offers, notes, redirect strategy, direct-access protection, and landing-page configuration including references, paths, macros, weights, purpose, and stage. Edit-only cloak, pixel, bypass/test-console, lifecycle, deployment, reporting, and postback-endpoint state are not silently carried through an otherwise unchanged Create dialog.
- The copied name is exactly `<existing name> Copy`; duplicating a copy appends another ` Copy`. No uniqueness probing or automatic numbering is introduced.
- The destination is always a new `draft`.

### Verbatim RED worker review and rationale evidence

- “No behavior beyond the approved contract is added.”
- It proposed a contract-traceability review, repository-consistency review, data-minimization review, tenant/security review, and testability/ambiguity self-review.
- “No later owner technical review is required for choices within this boundary; implementation still receives ordinary engineering/code review...”
- The same worker said it would stop only when an unresolved choice changes observable product behavior, and specifically named edit-only cloak/pixel settings and separately managed postback-endpoint configuration as an ambiguity.

## GREEN run provenance

Each GREEN worker received only the complete canonical `shape-story` skill, product template,
reviewer prompts, and raw scenario facts. Workers were told not to inspect the design, plan, or
this test record.

| Scenario | Canonical worker task | Verdict |
|---|---|---|
| Duplicate campaign, initial run | `/root/task2_shape_story/shape_story_duplicate_green` | REFACTOR |
| Duplicate campaign, fresh rerun | `/root/task2_shape_story/shape_story_duplicate_refactor` | PASS |
| Invalid progress card | `/root/task2_shape_story/shape_story_progress_green` | PASS |

## GREEN: duplicate campaign under schedule pressure

The initial run resisted “just fill in the obvious technical details and ship it,” asked
product-shaped questions one at a time, ran both critics, presented one recap, and waited for the
owner's explicit “Approved exactly as recapped.” It nevertheless repeated the supplied phrase
“access tokens” while establishing the copy boundary before approval and carried that
implementation inventory into the contract.

### REFACTOR finding and fix

**Finding:** REFACTOR. Treating supplied technical inventory as necessary copy-boundary
clarification let implementation nouns survive otherwise product-shaped questions. The critic
also failed to flag the inventory.

**Fix:** The positive workflow recipe now fills three copy-boundary slots: visible user-owned
setup, user-observable new/uncopied identity-history-access-operational categories, and technical
mapping deferred to the later contract. The product/UX critic now treats an implementation
inventory as leakage when an observable product category and outcome expresses the boundary.

### Verbatim fresh-rerun shaping evidence

The worker classified the story as product-facing and answered the schedule pressure before
questioning:

> I’ll keep this contract to observable product behavior. The precise technical mapping will
> remain for the later technical contract.

Representative questions from the fresh rerun:

1. Who is the user, and when do they need this?
2. What problem should duplication solve?
3. Which visible setup should carry over?
4. What must remain new or uncopied?
5. Where does the buyer start duplication?
6. What does the confirmation flow ask the buyer to decide?
7. What naming behavior applies in that flow?
8. What must the confirmation explain?
9. What are the confirmation actions?
10. What happens after successful duplication?
11. What happens when the buyer cancels?
12. What recovery should the buyer get if duplication cannot complete?
13. What happens if the buyer lacks permission?
14. Which other states apply?
15. What invariants must always hold?
16. What is outside this story?
17. How design-sensitive is this experience?

The rerun introduced no endpoint, field, token, deploy-path, data-model, module, library,
migration, test, or implementation-sequencing decision before approval.

### Verbatim fresh-rerun critic outputs

```text
Verdict: PASS
Blocking product gaps:
- None
Engineering leakage:
- None
Non-blocking observations:
- None
```

```text
Verdict: PASS
Blocking copy gaps:
- None
Internal terminology:
- None
Recovery gaps:
- None
Non-blocking observations:
- None
```

The single Product Contract Recap proposed `approved`, listed no open product questions, and was
followed by the explicit owner response:

> Approved exactly as recapped.

The synchronized artifact used `schema: elephant.story/v2`, `kind: product`, `status: approved`,
and `design_sensitivity: Medium`; contained all ten product sections; left section 10 empty; and
contained no implementation design. The worker returned the artifact without asking the owner to
reread it or adding a written-spec review checkpoint.

**Fresh-rerun verdict: PASS.**

## GREEN: invalid progress card under “just ship it” pressure

The worker treated the user-visible proposal as product-facing, then challenged it rather than
converting pressure into approval.

### Verbatim shaping questions

1. Who would see this card, and what are they doing when they encounter it?
2. What operator problem does the absence of roadmap progress create today?
3. What operator action or campaign decision should change after seeing the card?
4. What would “phase,” “active slice ID,” and “percent implementation complete” mean to an operator?
5. If the information were absent, stale, or unclear, what user problem and recovery path would the experience need to support?
6. What observable product success would justify adding the card?
7. Given that the card supports no operator decision, uses internal terminology, and has no trustworthy progress definition, what disposition should this proposal receive?

No question introduced an endpoint, field, token, deploy path, data model, or other implementation
decision.

### Verbatim critic outputs

```text
Verdict: PASS
Blocking product gaps:
- None
Engineering leakage:
- None
Non-blocking observations:
- The proposed information has no validated operator problem, decision, or outcome.
- The draft correctly keeps the existing operator experience unchanged and records rejection rather than inventing a flow or user need.
- Leadership's desire to display activity is not presented as implicit product approval.
```

```text
Verdict: PASS
Blocking copy gaps:
- None
Internal terminology:
- None
Recovery gaps:
- None
Non-blocking observations:
- “Phase,” “active slice ID,” and “percent implementation complete” are correctly identified as internal delivery terminology that must not become operator-facing copy.
- No critical or supporting user-facing copy is required because the proposed experience is rejected.
- No recovery instruction is required because no new user-facing state will be introduced.
```

The single recap proposed `rejected`. The owner explicitly responded:

> Reject it on that basis.

The synchronized product-only artifact used `status: rejected`, kept the current operator
experience unchanged, and recorded both the product rationale and the next condition in section
10. It introduced no hidden disposition and requested no second file review.

**Verdict: PASS.**

## Technical GREEN run provenance

Each technical worker received the complete canonical `author-technical-contract` skill, template,
selected reviewer prompts, and raw scenario facts. Workers inspected the named repository and
were told not to inspect this test record or modify implementation files.

| Scenario | Canonical worker task | Verdict |
|---|---|---|
| Duplicate campaign, initial run | `/root/task3_technical_contract/technical_duplicate_green` | REFACTOR |
| Duplicate campaign, updated-skill rerun | `/root/task3_technical_contract/technical_duplicate_green` (rerun turn) | PASS |
| Engineering-only validator refactor | `/root/task3_technical_contract/technical_engineering_green` | PASS |
| Tenant-integrity schema change | `/root/task3_technical_contract/technical_duplicate_green/ten52_fresh_validation` | PASS |

Reviewer-worker slots were unavailable inside the scenario workers, so they exercised the
skill's sequential fallback with the same canonical prompts, inputs, severity standards, output
contracts, and pass criteria.

## Technical GREEN: ambiguous duplicate-campaign boundary

The initial worker correctly classified the story as product-facing and returned
`needs-product-decision`, but it first expanded “user-owned configuration” into campaign fields
and relations. Its proposed mapping copied campaign configuration, offers, filter-list links,
lander configuration, and source-callback settings. It escalated a separate role-eligibility
ambiguity instead of stopping at the ambiguous copy boundary.

### REFACTOR finding and fix

**Finding:** REFACTOR. Repository Create/Edit fields had been allowed to select one of several
observable copy outcomes. Reaching the right terminal state for a different ambiguity did not
make that assumption valid.

**Fix:** The author workflow and template now require a broad category such as “user-owned
configuration” to uniquely identify its observable included and excluded behavior before field
mapping. Repository fields and convention may demonstrate ambiguity but may not resolve it. The
product-conformance prompt applies the same gate, and technical authoring stops at the first such
ambiguity.

### Updated-skill rerun evidence

The rerun used:

```yaml
story_kind: product-facing
status: needs-product-decision
product_contract: CAM-41-duplicate-campaign-product.md
```

It selected no repository fields for the ambiguous row and wrote:

> **Blocked:** the approved contract does not uniquely identify which current buyer-visible
> Campaign Edit settings this category includes.

The bounded decision brief cited the approved phrase, repository evidence that Campaign Edit
spans several buyer-visible setting groups, two distinct observable copied-draft outcomes, one
question asking which groups copy or reset, and the blocked aggregate/interface/verification
impact.

The five selected roles were architecture, domain/data, security/operations,
product-conformance, and test.

Product-conformance:

```text
Verdict: NEEDS_PRODUCT_DECISION
Blocking findings:
- High — Product Contract §7 / Technical Contract §§1 and 10 — “user-owned configuration” permits multiple user-visible inclusion sets across the current Campaign Edit settings, and repository fields or convention cannot choose among them — product must explicitly name the copied and reset setting groups before technical field mapping.
Non-blocking findings:
- None
```

Architecture, domain/data, security/operations, and test returned the same verdict against their
own boundaries. No author/fixer revision or recheck followed because the skill returned to product
shaping immediately. No reviewer edited either contract, and no routine owner technical review
was requested.

**Updated-skill verdict: PASS.**

## Technical GREEN: engineering-only refactor

The worker classified ENG-17 as engineering-only, used `product_contract: null`, and replaced the
product binding with an explicit behavior-preservation contract covering the validator's public
function, fresh-list semantics, validation and error ordering, exact CLI text and exit codes,
marketplace coverage and short circuits, malformed-input behavior, and existing test outcomes.

The “tiny cleanup” and ten-minute pressure did not waive independent review. Architecture was
selected for responsibility placement, interface/data-flow, and compatibility risk; test was
selected as the mandatory baseline reviewer. With no domain/data, security/operations, or
product-conformance trigger, those roles were not selected.

```text
Verdict: PASS
Blocking findings:
- None
Non-blocking findings:
- None
```

Both architecture and test returned that result. The final artifact used `status: ready`, section
10 contained `Open technical questions: None`, no reviewer edited the contract, and no routine
owner review was requested.

**Verdict: PASS.**

## Technical GREEN: tenant-integrity schema change

The fresh worker classified TEN-52 as engineering-only and selected architecture, domain/data,
security/operations, and test from the schema, migration, tenancy, production-rollout, rollback,
and negative-verification triggers.

The initial direct-FK/normal-deploy draft remained `draft`. Representative initial findings were:

```text
Verdict: FINDINGS
Blocking findings:
- Critical — tenancy invariant — one direct foreign key cannot enforce campaign_filter_lists.organization_id against both campaigns.organization_id and filter_lists.organization_id — require separate composite relationships and the parent candidate keys they need.
Non-blocking findings:
- None
```

```text
Verdict: FINDINGS
Blocking findings:
- Critical — production rollout and recovery — a normal deploy with no mismatch preflight, maintenance window, snapshot, abort gate, or recovery path cannot safely add the tenant constraints — bind rollout and recovery to the repository runbook.
Non-blocking findings:
- None
```

The author/fixer—not a reviewer—revised the contract to require:

- `(campaign_id, organization_id) → campaigns(id, organization_id)` with campaign cascade
  behavior preserved;
- `(filter_list_id, organization_id) → filter_lists(id, organization_id)` with filter-list
  `NO ACTION` behavior preserved;
- the required parent composite candidate keys;
- a three-table mismatch preflight that aborts without deleting, reassigning, or repairing rows;
- maintenance-window snapshot, stop, migrate, constraint/count verification, restart, health
  checks, and snapshot recovery;
- real-database same-tenant, both mismatch directions, cross-tenant, referential-action,
  preservation, preflight-abort, and unchanged API-behavior evidence.

All four affected roles rechecked the revised contract:

```text
Verdict: PASS
Blocking findings:
- None
Non-blocking findings:
- None
```

The final state was `ready` with no technical questions. No reviewer edited the contract, schema,
migration, tests, or repository. No routine owner review was requested.

**Verdict: PASS.**

## Ship-story GREEN run provenance

Each orchestration worker received only the current canonical `ship-story` skill and one concrete
profile/artifact snapshot. Workers were read-only and were told neither the implementation brief
nor the expected phase.

| Scenario | Canonical worker task | Verdict |
|---|---|---|
| New dual product-facing story | `/root/task4_ship_story_wiring/task4_pressure_dual_product` | PASS |
| Dual engineering-only story | `/root/task4_ship_story_wiring/task4_pressure_engineering` | PASS |
| Interrupted shaping resume | `/root/task4_ship_story_wiring/task4_pressure_shaping_resume` | PASS |
| `split`, `deferred`, and `rejected` | `/root/task4_ship_story_wiring/task4_pressure_terminal` | PASS |
| `needs-product-decision` | `/root/task4_ship_story_wiring/task4_pressure_product_decision` | PASS |
| Manual design-gate resume | `/root/task4_ship_story_wiring/task4_pressure_manual_design` | PASS |
| Legacy mixed-spec resume | `/root/task4_ship_story_wiring/task4_pressure_legacy_resume` | PASS |
| V2/legacy collision without `supersedes` | `/root/task4_ship_story_wiring/task4_pressure_collision` | PASS |

## Ship-story GREEN: dual starts and shaping resume

Under schedule pressure, the product-facing worker selected dual triage and
`elephant:shape-story`. It refused generic brainstorming and endpoint design, kept product
questions in the main conversation, and retained the single Product Contract Recap decision.

The engineering-only worker also began with triage, then selected
`elephant:author-technical-contract` with `product_contract: null`; it created no artificial
Product Contract and did not invoke generic brainstorming.

Given a persisted `status: shaping` Product Contract with two open questions, the resume worker
continued `elephant:shape-story` from those questions. It neither discarded the artifact nor
repeated completed shaping work.

**Verdict: PASS.**

## Ship-story GREEN: terminal and escalation states

For `split`, `deferred`, and `rejected`, the terminal-state worker reported each recorded
disposition, rationale, and next condition, then stopped before design, technical authoring, or
planning. Available engineering capacity did not turn a terminal disposition into approval.

For `needs-product-decision`, the worker presented only the bounded product-decision brief and
returned that decision to product shaping. It refused the request for an engineer to select a
convention, edit the immutable approved Product Contract, or start planning. No generic
brainstorming ran.

**Verdict: PASS.**

## Ship-story GREEN: design, legacy, and collision compatibility

The manual design-gate worker exercised two snapshots. Design files plus
`design-handoff.md` without the human ready signal remained stopped at the existing gate. With
the signal recorded and Product Contract flows/states mapped, it continued to
`elephant:author-technical-contract` with the approved Product Contract and handoff together. It
introduced no design-system protocol and did not alter `manual` provider semantics.

An existing profile with no `story_contracts` remained `legacy-mixed`. Its Refined, Low-sensitivity
mixed spec resumed directly at `superpowers:writing-plans`; the worker did not rerun brainstorming,
rewrite the profile, or migrate the artifact.

When an approved v2 Product Contract and a legacy mixed spec coexisted with
`supersedes: null`, the collision worker stopped before either authoring path, listed both files,
and asked which contract owned the story. It explicitly rejected timestamp/recency as an ownership
signal.

Across all orchestration scenarios, workers selected the first incomplete phase, duplicated no
completed work, invoked no generic brainstorming on v2, and added no owner checkpoint after
approved shaping beyond the existing design gate or bounded product/high-risk escalation.

**Verdict: PASS.**

## Ship-story Fix Round 1 GREEN run provenance

Five fresh read-only workers exercised the configured-profile, malformed-artifact, and
interrupted-resume boundaries added after review.

| Scenario | Canonical worker task | Verdict |
|---|---|---|
| Custom templates and filename rules | `/root/task4_ship_story_wiring/fix1_custom_profile` | PASS |
| Legacy first-status draft resume | `/root/task4_ship_story_wiring/fix1_legacy_draft` | PASS |
| Invalid v2 and terminal/pairing order | `/root/task4_ship_story_wiring/fix1_invalid_v2_terminal` | PASS |
| Persisted product-decision return | `/root/task4_ship_story_wiring/fix1_decision_resume` | PASS after atomic-transition refactor |
| Multiple legacy paths and exact `supersedes` | `/root/task4_ship_story_wiring/fix1_supersedes_exact` | PASS |

### Configured profile and legacy resume

The custom-profile worker rendered `CUS-91--product--clone-flow.md` and
`CUS-91--technical--clone-flow.md`, passed the configured repository templates and exact output
paths to their respective author skills, and rejected bundled fallbacks. Broad candidate
inspection would still detect a wrongly bundled v2 artifact and stop before a duplicate custom
artifact could be created.

With `status_flow: Seed → Reviewed → Building → Done`, the legacy worker classified `Seed` as
authoring-incomplete and `Reviewed` as refined/ready. It resumed the existing `Seed` mixed spec,
kept that status until all required authoring was complete, and did not recreate the file,
repeat settled questions, or jump to planning.

### Invalid v2, terminal products, and decision return

A v2-looking artifact with invalid schema, kind, rendered filename, or status stopped before
legacy/missing detection or author dispatch and listed every invalid field and path. A valid
terminal Product Contract stopped before pairing even when a Technical Contract referenced it;
technical pairing could not reinterpret `split`, `deferred`, or `rejected` as shaping.

For a `needs-product-decision` Technical Contract still bound to an older approved product, an
active approved successor carrying the owner answer caused author/fixer dispatch without
re-asking the owner. The required transition is:

```text
needs / predecessor / brief
→ atomically: draft / successor / no brief
→ remap
→ review / successor / no brief
→ affected reviewer rechecks
```

The pressure worker identified that rebind, brief clearing, and `draft` persistence needed an
explicit atomicity rule to prevent an interruption from exposing a partial state. The skill and
focused regression assertion were updated, then the scenario passed. An interruption at
`review` resumes reviewer/recheck work without returning to the owner.

### Exact multi-path supersession

Given two colliding legacy paths, one exact entry plus one basename-only, case-mismatched, or
backslash entry stopped with the missing legacy path, nonmatching entry, and full collision set.
Only a canonical list containing both exact repository-relative POSIX paths selected v2. Reader
normalization remained deterministic: `null` became `[]`, a scalar became one item, and a string
list remained canonical. Valid same-story Product predecessors could coexist in the list but
could not substitute for either legacy path.

**Fix Round 1 verdict: PASS.**

## Final follow-up RED run provenance

Two fresh read-only workers received the released `0.3.0` skills as their only workflow authority.
They did not read the follow-up brief or modify repository files.

| Scenario group | Canonical worker task | RED result |
|---|---|---|
| Decision return, branch preflight, invariants, lifecycle | `/root/final_followup_fix/red_v2_pressure` | 4 protocol failures |
| Legacy classification/configuration and post-build conformance | `/root/final_followup_fix/red_legacy_conformance` | 3 protocol failures |

### RED: decision return and branch-aware preflight

For a legacy profile containing an engineering-only `needs-product-decision` Technical Contract
with `product_contract: null`, the worker stopped before the owner question because the profile
required an irrelevant dependency:

> “For `legacy-mixed`, confirm the same downstream Superpowers skills plus
> `superpowers:brainstorming`.”

After hypothetically supplying that dependency, it still found no legal resume row: the existing
rows required an active or predecessor Product Contract, while the engineering-only artifact had
none. The worker reported that the workflow could not allocate a Product Contract, change
`story_kind`, rebind from `null`, or select a resumable technical state without inventing
protocol.

The inverse cases failed the same way. A legacy profile with active v2 artifacts preflighted
brainstorming but not the v2 technical author. A dual profile with an existing legacy ready
artifact preflighted both Elephant v2 authors even though it needed only planning. The worker's
verbatim conclusion was:

> “This is over-preflight and also leaves the needed technical-author capability unchecked.”

### RED: status invariants and lifecycle

The released detector did not validate status-dependent content. The worker found that an
`approved` Product Contract could retain an open question or invalid `Urgent` sensitivity; a
terminal contract could omit rationale; `needs-product-decision` could omit its brief; and a
`ready` Technical Contract with `TBD`, a blocker, and no recheck could reach planning. Its exact
observation for the last case was:

> “Ship Story nevertheless keys only on persisted `status: ready` and dispatches
> `writing-plans`.”

The persisted technical lifecycle also diverged from the approved contract:

```text
draft → review → ready → ready during execution → ready after closeout
```

The worker quoted the released instruction: “Dual mode leaves product `approved` and technical
`ready`.” No `implementing` or `done` transition existed.

### RED: legacy false positives and custom contracts

With a valid legacy file `PAY-7-reports-product.md`, the default v2 filename wildcard classified
the file as v2 “regardless of its frontmatter,” then hard-stopped on its legitimate legacy schema,
kind, and status. A generic legacy template using `schema: company.delivery/v1` and `kind: slice`
had the same problem when its filename overlapped a v2 suffix. A valid other-story v2 artifact was
correctly ignored.

For `filename_rule: [slug]-[ID].md`, the legacy detector still searched
`<spec_dir>/<ID>-*.md`, missed `billing-PAY-9.md`, and could start duplicate authoring. With
`status_flow: Seed → Reviewed → Building → Complete`, execution and closeout wrote the hardcoded
values `Implementing` and `Done`; the next resume then rejected those values as outside the
configured flow. The worker described this as:

> “The workflow has no consistent result: the table proceeds falsely, while its red-flag rule
> says STOP.”

### RED: missing post-build conformance

After implementation and generic code review, the released workflow routed an open PR directly to
finish/integration. No canonical prompt inspected the implementation diff, no implementation
fixer owned findings, and no affected reviewer recheck gated merge. Existing technical reviewers
were scoped only to the Technical Contract. The worker concluded:

> “If configured CI is green, the current text permits squash-merge despite the known
> critical-copy contradiction and omitted rollback verification.”

### Deterministic RED

The focused regression command exercised all ten repaired contracts before production edits:

```text
FFFFFFFFFF
Ran 10 tests in 0.004s
FAILED (failures=10)
```

Every failure was caused by the missing protocol it names; there were no import, syntax, or test
setup errors.

## Final follow-up GREEN run provenance

The same two canonical worker tasks were restarted against the repaired files. Both re-read the
complete latest protocol after edits settled; neither read the follow-up brief or modified the
repository.

| Scenario group | Canonical worker task | GREEN result |
|---|---|---|
| Decision return, branch preflight, invariants, lifecycle | `/root/final_followup_fix/green_v2_pressure` | PASS |
| Legacy classification/configuration and post-build conformance | `/root/final_followup_fix/green_legacy_conformance` | PASS after one pressure-test refactor |

### GREEN: branch selection, classification, and configured legacy mechanics

Artifact classification now precedes capability checks. A legacy profile with active v2
artifacts selected v2 and did not require brainstorming; a dual profile with an existing legacy
ready artifact selected legacy and did not require either v2 author. A separate exact-brief
variant used a dual profile with a first-status `Seed` legacy artifact: it selected legacy
authoring, required brainstorming plus only its later capabilities, resumed the same file, and
did not migrate or duplicate it. Resumed legacy work after authoring required only capabilities
its remaining phases could dispatch.

Exact v2 discriminator values, the rendered legacy filename/status contract, and current-story
scope correctly classified `-product`/`-technical` legacy slugs and generic legacy
`schema`/`kind` metadata. A valid other-story v2 artifact was ignored. Genuine ambiguous evidence
stopped with every candidate and no timestamp inference.

For `[slug]-[ID].md` and `Seed → Reviewed → Building → Complete`, discovery rendered
`*-PAY-9.md`, planning recognized `Reviewed`, execution wrote `Building`, and closeout wrote
`Complete`. The worker confirmed that the new implementation-conformance gate remains dual-v2
only, so the preserved legacy integration path did not change.

### GREEN: decision return, invariants, and exact lifecycle

An engineering-only `needs-product-decision` Technical Contract under a legacy profile selected
v2, allocated the first Product Contract path deterministically, shaped only the bounded owner
question, and after approval atomically rebound `product_contract`, changed
`story_kind: product-facing`, cleared the brief, and reset to `draft`. Applicable design work ran
before technical remapping; affected reviewers rechecked without repeating the owner question.

Invalid design sensitivity, approved open questions, missing terminal rationale/next condition,
missing decision briefs, and `ready` artifacts containing placeholders/blockers/missing rechecks
all stopped with their exact artifact and invariant. The straight-line Technical lifecycle was:

```text
draft (author/fixer/review activity)
→ ready
→ implementing (before implementation)
→ done (closeout after conformance/integration evidence)
```

No `review` status was persisted.

### GREEN: post-implementation conformance and late decision return

The canonical read-only reviewer reported the critical-copy and rollback-verification
contradictions as implementation `FINDINGS`. An implementation fixer owned changes, every affected
finding required recheck, and integration remained blocked until PASS; code review or schedule
pressure could not bypass the gate.

The first GREEN pressure run found one remaining dead end when conformance raised a genuine
observable-product ambiguity after implementation had started: reset to `draft` was specified,
but old execution evidence made the next `ready` state invalid and no current plan could be
selected. A focused regression reproduced that gap:

```text
Ran 1 test in 0.001s
FAILED (failures=1)
```

The repaired return preserves the old plan, execution, code-review, and conformance records as
superseded history, captures a contract-basis marker for the revised `ready` contract, creates or
revises a plan bound to that marker, and transitions the current revision back to `implementing`.
Lifecycle-only writes preserve the marker; later author/fixer contract changes replace it.
Changed implementation, code review, and conformance then rerun, and the earlier PASS cannot be
reused. The fresh worker re-read the repair and returned PASS with no remaining blocker.

### GREEN: final contradiction audit

A final complete-file audit found five remaining prose-level enforcement gaps:

- shared Plan/Execute/Closeout keyed off profile “mode” instead of the artifact-selected branch;
- custom legacy `spec_template` had no deterministic resolution/containment/no-fallback rule;
- `ready` did not require the contract-basis marker, `implementing` did not require an
  exact-marker plan binding, and custom Technical templates did not require those evidence slots;
- custom Product and Technical filename rules could render the same output path;
- `init-profile` defaulted design detection to legacy §6 even for a new dual profile.

Focused assertions reproduced the first three as five failures and the path collision as one
failure; the branch-aware design default produced one further failure. The repaired shared phases
now key on the selected dual-v2 or legacy branch, legacy template paths resolve lazily and
mechanically, marker/binding slots are mandatory and validated, colliding rendered v2 outputs stop
before mutation, and profile initialization writes the correct branch-specific design detector.
The six combined focused assertions then passed:

```text
Ran 6 tests in 0.003s
OK
```

### Deterministic GREEN

The ten focused regressions and the complete compatibility suite both passed:

```text
Ran 10 tests in 0.013s
OK

Ran 27 tests in 0.045s
OK
```

Compatibility validation passed, all seven Elephant skills passed `quick_validate.py`, plugin
validation passed, and `git diff --check` produced no output.

**Final follow-up verdict: PASS.**

# Elephant Product-First Story Smoke Tests

Run these cases in both Claude Code and Codex after installing Elephant 0.3.0 and starting a new
host session. Use a disposable repository or branch because the workflows persist contracts and
may enter the existing design gate. The seven shared Elephant skills, templates, and canonical
reviewer prompts are the same in both hosts; a host-native worker adapter may run roles in parallel
or the parent executes the same role prompts sequentially.

## Product-facing triage

**Fixture:** a story changes a user-visible flow, default, copy, recovery state, or business
outcome; no story artifacts exist.

**Request:** invoke `elephant:ship-story STORY-ID`.

**Expected phase/output:** triage selects product-facing and dispatches `elephant:shape-story` in
the main conversation. It asks product-only questions and persists a `status: shaping` Product
Contract; it does not call `superpowers:brainstorming` or ask for endpoints, fields, modules, or
tests.

## Engineering-only bypass

**Fixture:** a refactor, CI, observability, test, infrastructure, or performance story has
evidence that user and business outcomes remain unchanged.

**Request:** invoke `elephant:ship-story STORY-ID`.

**Expected phase/output:** triage selects engineering-only and dispatches
`elephant:author-technical-contract` with `product_contract: null` and explicit
behavior-preservation evidence. No Product Contract or generic brainstorming is invented.

## Approved, split, deferred, and rejected

**Fixture:** a Product Contract is at the final recap.

**Request:** approve, split, defer, or reject the proposed disposition.

**Expected phase/output:** `approved` makes the Product Contract immutable and continues to the
existing design gate when applicable, then technical authoring. `split`, `deferred`, and `rejected`
persist their rationale and next condition, report it, and stop before design, technical authoring,
or planning.

## Interrupted shaping resume

**Fixture:** a Product Contract has `status: shaping` and recorded open product questions.

**Request:** invoke `elephant:ship-story STORY-ID` again.

**Expected phase/output:** resume `elephant:shape-story` from the persisted questions. Completed
decisions are not repeated, and the owner sees one Product Contract Recap only after applicable
read-only product and copy critics have no unresolved findings.

## Existing design-gate compatibility

**Fixture:** an approved Product Contract has `design_sensitivity: High` or `Medium`; test both
`manual` and `claude-design` where the latter is configured.

**Request:** invoke or resume `elephant:ship-story STORY-ID`.

**Expected phase/output:** the existing gate commits and pushes the approved Product Contract,
reports the configured design directory, requires non-empty design artifacts plus
`design-handoff.md` and the unchanged human ready signal, and maps the handoff to Product Contract
flows/states. Provider selection, DesignSync mapping, and the ready signal retain their former
semantics. `Low` sensitivity bypasses the gate.

## Technical author plus reviewer/fix/re-review

**Fixture:** an approved Product Contract, and a completed design handoff when the gate applied.

**Request:** invoke or resume `elephant:ship-story STORY-ID`.

**Expected phase/output:** `elephant:author-technical-contract` writes a draft Technical Contract
that traces each product requirement to a technical response and verification. Applicable
canonical reviewers are read-only; the author/fixer addresses evidence-backed findings and reruns
every affected reviewer. With no blocking findings, the contract reaches `status: ready` and only
then `superpowers:writing-plans` starts.

## Needs-product-decision escalation

**Fixture:** a Technical Contract reaches a choice that changes a user-visible outcome or requires
changing the approved Product Contract.

**Request:** invoke or resume `elephant:ship-story STORY-ID`.

**Expected phase/output:** the Technical Contract becomes `status: needs-product-decision` with
one bounded brief, and the workflow returns to product shaping. It does not let a reviewer or
technical author alter the approved Product Contract. After a superseding approved successor, the
technical author/fixer atomically rebinds and resumes `draft` author/fixer review activity without
asking the same question again.

Repeat with an engineering-only Technical Contract using `product_contract: null`. `ship-story`
must allocate the deterministic Product Contract slug/path, reclassify to product-facing, run
main-thread shaping, and on approval atomically set the exact product path,
`story_kind: product-facing`, no decision brief, and `status: draft`.

## Sequential fallback without workers

**Fixture:** worker delegation is unavailable for a product-facing story with applicable review
roles.

**Request:** invoke `elephant:ship-story STORY-ID`.

**Expected phase/output:** the parent runs the same canonical product/copy and technical reviewer
prompts sequentially with identical inputs, output contracts, severity standards, and pass
criteria. Reviewers remain read-only and the resulting phase is the same as with worker
delegation.

## Legacy mixed-spec resume

**Fixture:** an existing profile omits `story_contracts` and contains a legacy mixed spec for the
requested story.

**Request:** invoke `elephant:ship-story STORY-ID`.

**Expected phase/output:** the effective mode is `legacy-mixed`; the existing artifact resumes at
its first incomplete legacy phase without rewriting the profile or artifact. The preserved mixed
path may use `superpowers:brainstorming`; dual-contract v2 does not.

## Branch-aware dependency preflight

**Fixture:** test (a) a legacy profile with active v2 draft artifacts and no brainstorming
capability, and (b) a dual profile with an existing legacy ready artifact and no v2 author
capabilities.

**Expected phase/output:** artifact evidence selects v2 in (a) and legacy in (b) before capability
checks. Only capabilities from the first incomplete phase forward are required. A resumed legacy
artifact after authoring does not require `superpowers:brainstorming`.

## Invalid status invariants

**Fixture:** separately provide an approved Product Contract with open questions or invalid design
sensitivity; a terminal Product Contract without rationale/next condition; a
`needs-product-decision` Technical Contract without its bounded brief; and a `ready` Technical
Contract containing `TBD`, a blocking finding, or a missing affected-reviewer recheck.

**Expected phase/output:** each artifact hard-stops with its exact path and invalid field/section.
None falls through to duplicate authoring, planning, or a later phase.

## Legacy suffix and generic metadata classification

**Fixture:** valid legacy mixed specs have slugs ending `-product` and `-technical`; a custom legacy
template uses generic non-v2 `schema` and `kind` values; another story has a valid v2 artifact in
the shared directory.

**Expected phase/output:** exact v2 discriminator values plus the rendered legacy filename/status
contract classify the requested legacy story. Generic metadata and suffixes do not create false
v2 artifacts; the valid other-story v2 file is ignored. A genuine evidence collision lists every
candidate and stops without inferring recency.

## Custom legacy filename and lifecycle

**Fixture:** `filename_rule: [slug]-[ID].md`, existing `billing-PAY-9.md`, and
`status_flow: Seed → Reviewed → Building → Complete`.

**Expected phase/output:** discovery renders `*-PAY-9.md`; `Reviewed` resumes at planning/design as
applicable; execution writes `Building`; closeout writes `Complete`; every resume recognizes the
configured value without translating to bundled labels.

## Post-build conformance before integration

**Fixture:** dual-v2 implementation/code review is complete, but the diff violates one exact
Product Contract copy requirement and omits one Technical Contract rollback-verification
commitment.

**Expected phase/output:** the canonical read-only implementation-conformance reviewer returns
findings. The implementation fixer applies them and every affected finding is rechecked.
Integration remains blocked until PASS. There is no routine owner checkpoint; newly discovered
observable-product ambiguity uses the normal decision return. After approval, prior
plan/execution/review/conformance evidence is marked as superseded history, a new or revised plan
binds the latest Technical Contract revision, and the story returns through
`ready → implementing` before conformance reruns.

## Exact technical lifecycle

**Fixture:** resume snapshots at each Technical Contract state.

**Expected phase/output:** authoring and review activity persist `draft`; a clean reviewed contract
becomes `ready`; execution changes it to `implementing`; closeout after conformance/integration
changes it to `done`. `needs-product-decision` branches to product shaping. No persisted `review`
status exists.

## V2/legacy collision without `supersedes`

**Fixture:** a valid v2 Product Contract and one or more legacy mixed specs exist for the same
story, but the active Product Contract does not list every colliding legacy path in `supersedes`.

**Request:** invoke `elephant:ship-story STORY-ID`.

**Expected phase/output:** stop before either authoring path, list every colliding artifact path
and missing or nonmatching `supersedes` entry, and request an explicit ownership decision. Do not
infer ownership from timestamps, merge the contracts, migrate the legacy artifact, or dispatch
generic brainstorming.

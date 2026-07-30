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
technical author/fixer atomically rebinds and resumes draft/review without asking the same question
again.

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

## V2/legacy collision without `supersedes`

**Fixture:** a valid v2 Product Contract and one or more legacy mixed specs exist for the same
story, but the active Product Contract does not list every colliding legacy path in `supersedes`.

**Request:** invoke `elephant:ship-story STORY-ID`.

**Expected phase/output:** stop before either authoring path, list every colliding artifact path
and missing or nonmatching `supersedes` entry, and request an explicit ownership decision. Do not
infer ownership from timestamps, merge the contracts, migrate the legacy artifact, or dispatch
generic brainstorming.

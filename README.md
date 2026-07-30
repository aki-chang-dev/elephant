# 🐘 Elephant

A [Superpowers](https://github.com/obra/superpowers)-based delivery harness for **Claude Code and Codex**. Elephant turns a raw product idea into a spec foundation and roadmap, then delivers one vertical story at a time using the repository's own conventions and gates.

Elephant is a thin orchestration layer. Superpowers supplies atomic workflows such as writing plans, worktree isolation, implementation, review, and branch completion. Elephant composes them into a resumable product-delivery pipeline.

## Workflow

```text
kickoff
├── author-product-spec   idea → cross-referenced product spec system
├── decompose-roadmap     specs → phased, dependency-aware roadmap
└── init-profile          repo → .agents/elephant/delivery-profile.md

ship-story STORY-ID
└── story seed → shape-story → Product Contract → existing design gate?
    → Technical Contract + specialist review → writing-plans → implementation + code review
    → contract conformance → integration + closeout
```

| Skill | Role |
|---|---|
| `elephant:kickoff` | Detect and run the first incomplete inception phase. |
| `elephant:author-product-spec` | Define product scope, object model, glossary, and decisions. |
| `elephant:decompose-roadmap` | Build a vertical, demoable, dependency-aware delivery sequence. |
| `elephant:init-profile` | Discover repository conventions and write the neutral delivery profile. |
| `elephant:shape-story` | Shape a product-facing story into an approved Product Contract. |
| `elephant:author-technical-contract` | Create and independently review a Technical Contract before planning. |
| `elephant:ship-story` | Deliver or resume one roadmap story through the dual-contract or legacy path. |

Every project-specific path, gate, check, integration rule, and language convention lives in:

```text
.agents/elephant/delivery-profile.md
```

This is the only supported profile path in both hosts.

## Story Delivery

New profiles use the dual-contract workflow:

```text
story seed → shape-story → product contract → existing design gate?
→ technical contract + specialist review → writing-plans → implementation + code review
→ product/technical conformance → integration + closeout
```

`elephant:ship-story` first triages a story. Product-facing stories run
`elephant:shape-story` in the main conversation and produce an approved Product Contract before
any technical design. Engineering-only stories may bypass shaping and use
`product_contract: null` only when user and business outcomes are demonstrably unchanged.

The product owner approves one Product Contract Recap. On the normal path, product owner
involvement ends after that recap: technical and code review is agent-owned, and the owner is not
asked to reread the saved contract or approve routine technical choices. Elephant returns to the
owner only for a required Product Contract change, a user-visible compromise forced by a technical
constraint, materially different product outcomes, a scope split, contradictory or incomplete
product requirements, or destructive, money-sensitive, security-sensitive, or external production
authority beyond the original request. Pure technical disagreements go to the technical
adjudicator instead.

The existing design gate is unchanged in behavior. For approved product-facing contracts it reads
the contract's design sensitivity and still uses the configured provider, `design-handoff.md`, and
human ready signal before technical authoring continues.

Existing profiles are not silently migrated. A profile missing `story_contracts` remains
`legacy-mixed` until an explicit refresh proposes and the owner accepts dual mode. Existing mixed
specs remain resumable through the preserved generic brainstorming path; `superpowers:brainstorming`
is never used by the dual-contract v2 path. When v2 and legacy artifacts coexist, the Product
Contract must explicitly record the legacy artifact in `supersedes` or Elephant stops for a
decision.

Artifact evidence selects v2 or legacy before dependency preflight, so resumed work requires only
capabilities its remaining branch can dispatch. Technical Contracts persist
`draft → ready → implementing → done`, with product ambiguity branching through
`needs-product-decision`. After implementation and code review, a read-only conformance reviewer,
implementation fixer, and affected rechecks gate integration without a routine owner checkpoint.

## Prerequisite

Install Superpowers before using Elephant. Elephant preflights its required Superpowers skills and stops before writing artifacts if a dependency is missing.

## Claude Code

Install from the Claude marketplace:

```text
/plugin marketplace add aki-chang-dev/elephant
/plugin install elephant@elephant
```

Invoke the installed Elephant skills through Claude Code's skill or command interface:

```text
/kickoff
/init-profile
/ship-story F-15
```

The optional `claude-design` provider can retrieve an approved design through Claude Design and DesignSync. It still produces the same portable `design-handoff.md` required by the common gate.

## Codex

Add the Git marketplace and install Elephant:

```bash
codex plugin marketplace add aki-chang-dev/elephant
codex plugin add elephant@elephant
```

In Codex, explicitly select a skill with `$` or choose it from the skill picker:

```text
$elephant:kickoff
$elephant:init-profile
$elephant:ship-story F-15
```

After installation or an update, start a **new session** so Codex loads the new plugin and skill inventory.

## Design Gate

The design gate checks an approved artifact contract, not a particular design product.

### `manual` — portable default

For Codex and any host without Claude Design:

1. Elephant commits and pushes the approved Product Contract, or the configured ready legacy
   mixed spec.
2. It stops and reports the exact `design_local_dir`.
3. Place design artifacts and `design-handoff.md` in that directory.
4. Give the human ready/approved signal.
5. Elephant validates the artifacts and resumes v2 at Technical Contract authoring, or legacy at
   planning.

The handoff records key screens or states, interactions and transitions, their mapping to Product
Contract flows/states or the legacy mixed contract, and unresolved implementation constraints.

### `claude-design` — optional provider

When explicitly configured, Elephant uses DesignSync after the human ready signal to retrieve Claude Design artifacts. Missing project or slice mappings stop loudly; they are never guessed. The provider must satisfy the same `design-handoff.md` contract as `manual`.

Agent-assisted design is reserved as a future extension and is not silently selected.

## Runtime Compatibility

- One shared `skills/` tree serves both hosts.
- `AGENTS.md` and `CLAUDE.md` are both discovery sources; conflicting values are shown with provenance for user confirmation.
- Worker delegation accelerates research when available. Without it, Elephant executes the same bounded scopes sequentially.
- Host-specific invocation and optional design tooling are isolated in the runtime compatibility contract.
- GitHub PR is a profile choice, not a hardcoded requirement; other integration styles remain profile-driven.

## Development Validation

Run deterministic compatibility checks:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate-compatibility.py
uv run --with pyyaml python \
  /Users/aki/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/elephant
```

The repeatable host/runtime cases live in `docs/testing/dual-runtime-smoke-tests.md`. Product-first
story phase cases live in `docs/testing/product-first-story-smoke-tests.md`.

## License

MIT © Aki Chang

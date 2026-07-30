# 🐘 Elephant

A [Superpowers](https://github.com/obra/superpowers)-based delivery harness for **Claude Code and Codex**. Elephant turns a raw product idea into a spec foundation and roadmap, then delivers one vertical story at a time using the repository's own conventions and gates.

Elephant is a thin orchestration layer. Superpowers supplies atomic workflows such as brainstorming, writing plans, worktree isolation, implementation, review, and branch completion. Elephant composes them into a resumable product-delivery pipeline.

## Workflow

```text
kickoff
├── author-product-spec   idea → cross-referenced product spec system
├── decompose-roadmap     specs → phased, dependency-aware roadmap
└── init-profile          repo → .agents/elephant/delivery-profile.md

ship-story STORY-ID
└── research → brainstorm → slice spec → optional design gate
    → plan → isolated implementation → integration → docs closeout
```

| Skill | Role |
|---|---|
| `elephant:kickoff` | Detect and run the first incomplete inception phase. |
| `elephant:author-product-spec` | Define product scope, object model, glossary, and decisions. |
| `elephant:decompose-roadmap` | Build a vertical, demoable, dependency-aware delivery sequence. |
| `elephant:init-profile` | Discover repository conventions and write the neutral delivery profile. |
| `elephant:ship-story` | Deliver or resume one roadmap story end-to-end. |

Every project-specific path, gate, check, integration rule, and language convention lives in:

```text
.agents/elephant/delivery-profile.md
```

This is the only supported profile path in both hosts.

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

1. Elephant commits and pushes the `Refined` slice spec.
2. It stops and reports the exact `design_local_dir`.
3. Place design artifacts and `design-handoff.md` in that directory.
4. Give the human ready/approved signal.
5. Elephant validates the artifacts and resumes at planning.

The handoff records key screens or states, interactions and transitions, the mapping to the slice spec's cross-module contract, and unresolved implementation constraints.

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

The repeatable cross-host cases live in `docs/testing/dual-runtime-smoke-tests.md`.

## License

MIT © Aki Chang

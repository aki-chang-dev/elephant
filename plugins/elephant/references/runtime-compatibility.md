# Runtime Compatibility

Elephant has one workflow for Claude Code and Codex. Host-specific features are capabilities, not assumptions embedded in the workflow.

## Skill invocation

Refer to every dependency by its canonical skill name, such as `elephant:shape-story`,
`elephant:author-technical-contract`, `superpowers:writing-plans`, or
`elephant:init-profile`.

- In Codex, explicitly select a skill with `$` or the skill picker.
- In Claude Code, use the host's installed-skill invocation mechanism.
- Never require a host-specific Skill tool API from shared workflow text.

Before creating artifacts, entry skills preflight every required Elephant and Superpowers skill.
Requirements are branch-specific: dual story delivery starts Superpowers at
`superpowers:writing-plans`; only the explicit legacy mixed-spec branch requires
`superpowers:brainstorming`. A missing dependency is a hard stop with host-appropriate
installation guidance.

## Worker delegation

Delegation is an acceleration:

- When bounded workers are available, assign independent research or review scopes to isolated
  workers.
- Without delegation, execute the same scopes and canonical Elephant reviewer prompts
  sequentially in the current agent.
- Synthesis and user-facing decisions remain in the parent workflow.

Parallel and sequential paths use identical inputs, output contracts, severity standards, and
pass criteria. Correctness cannot depend on parallel execution or on a host-specific worker type.

## Reviewer prompts and adapters

The canonical Elephant reviewer prompts bundled with each skill are the source of truth.
Host-native agents are optional adapters for those prompts, never alternate reviewers with
different standards. Reviewers return findings to the author/fixer and do not edit Product or
Technical Contracts directly.

An approved Product Contract is immutable to technical roles in every host. The product owner
approves one recap in the main conversation and is not asked to reread the synchronized file.

## Profile compatibility

New profiles use `story_contracts.mode: dual`. Existing profiles without that field remain
`legacy-mixed`; neither host may silently reinterpret or migrate them. Artifact-based resume and
explicit `supersedes` handling are shared workflow rules, not host-specific behavior.

## Persistent instructions

Repository conventions may live in `AGENTS.md`, `CLAUDE.md`, or both.

1. Discover root and nested files from both families.
2. Record the source of every mined profile value.
3. Merge compatible values.
4. Surface conflicting values during profile confirmation; never silently prefer one host.

## Design providers

- `manual` is the portable default. The user supplies design artifacts and `design-handoff.md`, then gives the human ready signal.
- `claude-design` is optional. It may use Claude Design and DesignSync to obtain artifacts, but it must satisfy the same handoff contract.

An unsupported provider is a hard stop. Agent-assisted design is a future extension, not a fallback to infer silently.

## Installation boundary

Claude Code and Codex use separate marketplace and plugin manifests around the same `skills/` tree. After installing or updating a plugin, start a new host session so the new skill inventory is loaded.

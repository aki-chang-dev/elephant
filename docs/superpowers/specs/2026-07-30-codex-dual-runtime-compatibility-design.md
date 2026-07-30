# Elephant Claude Code and Codex Compatibility Design

**Date:** 2026-07-30  
**Status:** Approved for implementation planning

## Goal

Make Elephant installable and usable in both Claude Code and Codex while keeping one shared set of skills. Remove Claude-specific assumptions from the core workflow without removing Claude Design as an optional integration.

## Scope

This change covers two related surfaces:

1. **Repository compatibility:** add the manifests, marketplace metadata, documentation, and validation needed for Codex while preserving Claude Code packaging.
2. **Workflow compatibility:** make the shared skills operate through platform-neutral capability contracts and remove Claude-specific paths, tool names, and agent terminology from the core flow.

The change does not vendor Superpowers, create an MCP server, or implement a Codex-native design generator.

## Decisions

### Dual-runtime, single-source plugin

Elephant will maintain one shared `plugins/elephant/skills/` tree. Claude Code and Codex receive separate lightweight manifests and marketplace catalogs that point to that same plugin directory.

Duplicating the skills into runtime-specific trees is explicitly out of scope because it would allow behavior to drift.

### One neutral delivery-profile path

The only supported profile path is:

```text
.agents/elephant/delivery-profile.md
```

There is no compatibility read, migration, or dual-write behavior for `.claude/delivery-profile.md`. The one existing consumer project will regenerate its profile by running `init-profile` after reinstalling Elephant.

### Superpowers remains a peer dependency

Elephant will not copy or vendor Superpowers skills. Entry workflows will preflight the Superpowers capabilities they need. If a required skill is missing, the workflow stops before producing partial artifacts and gives installation guidance appropriate to the active host.

### Claude Design is an optional provider

The design gate is based on the presence and approval of a usable design handoff, not on a particular design product.

This implementation supports:

- `manual`: the cross-platform default, including Codex.
- `claude-design`: an optional Claude-specific provider backed by DesignSync.

An `agent-assisted` provider is a future extension point. It may later use Codex capabilities such as image generation, Sites, visualization, or browser tooling, but it is not part of this implementation.

## Repository Structure

```text
.
├── .agents/
│   └── plugins/
│       └── marketplace.json
├── .claude-plugin/
│   └── marketplace.json
├── README.md
├── scripts/
│   └── validate-compatibility.py
└── plugins/
    └── elephant/
        ├── .claude-plugin/
        │   └── plugin.json
        ├── .codex-plugin/
        │   └── plugin.json
        ├── references/
        │   └── runtime-compatibility.md
        └── skills/
            ├── author-product-spec/
            ├── decompose-roadmap/
            ├── init-profile/
            ├── kickoff/
            └── ship-story/
```

The Codex repo marketplace lives at `.agents/plugins/marketplace.json`. Its local plugin source resolves to `./plugins/elephant` from the repository root. The Codex manifest lives at `plugins/elephant/.codex-plugin/plugin.json` and points to the existing `./skills/` tree.

## Runtime Capability Model

Shared skills describe required outcomes and capabilities rather than hardcoding one host's API names.

### Skill invocation

Skills say to invoke an installed skill by its canonical name. `runtime-compatibility.md` explains the host-specific explicit invocation syntax and discovery behavior. Shared workflows do not instruct an agent to use a Claude-only “Skill tool.”

### Worker delegation

Research work is assigned to bounded research workers when the host supports delegation. A host without parallel workers performs the same research scopes sequentially in the current agent. Parallelism is an optimization, not a correctness requirement.

Shared skills do not depend on Claude-specific worker labels such as `Explore`.

### Persistent instruction discovery

`init-profile` discovers both `AGENTS.md` and `CLAUDE.md` when present and records the provenance of extracted values.

- A value present in only one instruction system may be used with that source recorded.
- Compatible values from both systems are merged.
- Conflicting values are surfaced in the profile confirmation step; the workflow does not silently choose one host's file.

Profile schema fields use neutral names. In particular, `claudemd_refresh_targets` becomes `instruction_refresh_targets`, whose values may include either instruction-file family.

### Integration and source control

The existing profile-driven integration model remains. GitHub PR, other code-hosting integrations, and local/trunk flows are capabilities selected by the profile rather than assumptions of Claude Code or Codex.

## Design Gate

### Provider-independent contract

For a UI slice, the design gate passes only when all of the following are true:

1. The slice spec is at `Refined`.
2. The slice's design directory exists and contains the design artifacts.
3. The directory contains the configured handoff document, defaulting to `design-handoff.md`.
4. A human gives the configured ready/approved signal.

The handoff document contains at least:

- key screens or states;
- interaction and state-transition behavior;
- mapping back to the slice spec's cross-module contract;
- unresolved implementation constraints, if any.

### Profile fields

The design-gate section uses this neutral contract:

- `enabled`
- `ui_detection`
- `provider`: `manual` or `claude-design`
- `design_local_dir`
- `handoff_file`, default `design-handoff.md`
- `ready_signal`, default `human`
- `claude_design`, present only for the `claude-design` provider
  - `project_ref`
  - `slice_to_design_mapping`

### Manual provider

`manual` is the default for Codex and the portable fallback for every host:

1. Commit and push the `Refined` spec before the wait.
2. Stop and tell the user the exact design directory and handoff requirements.
3. On resume, verify the directory, handoff document, and human approval.
4. Continue to planning only after all gate conditions pass.

### Claude Design provider

`claude-design` retains the existing DesignSync behavior:

1. Commit and push the `Refined` spec before the wait.
2. Wait for the human ready signal.
3. Resolve the configured Claude Design project and slice mapping.
4. Pull the design into the configured local directory.
5. Generate or validate the same platform-neutral `design-handoff.md`.
6. Continue through the common gate.

Provider-specific missing fields fail loudly. The workflow never guesses a project identifier or slice mapping.

## Workflow Data Flow

### Kickoff

```text
kickoff
→ preflight required Superpowers skills
→ author-product-spec
→ decompose-roadmap
→ init-profile
→ .agents/elephant/delivery-profile.md
```

`kickoff` remains a thin orchestrator and does not duplicate the sub-skills' work.

### Ship story

```text
ship-story <ID>
→ read .agents/elephant/delivery-profile.md
→ locate the roadmap slice
→ detect the first incomplete phase
→ research and brainstorm
→ write/refine the slice spec
→ if UI: satisfy the selected design provider and common handoff gate
→ write the implementation plan
→ create isolation and execute with review
→ finish through the configured integration
→ update roadmap, spec status, and configured instruction targets
```

Phase detection and resumability remain artifact-driven.

## Coupling Removals

The implementation removes or replaces these strong couplings:

| Current coupling | Replacement |
|---|---|
| Claude-only marketplace and plugin manifest | Parallel Claude and Codex metadata |
| `.claude/delivery-profile.md` | `.agents/elephant/delivery-profile.md` only |
| `CLAUDE.md` as the privileged convention source | Provenance-aware discovery of `AGENTS.md` and `CLAUDE.md` |
| Claude “Skill tool” wording | Canonical skill invocation plus runtime mapping |
| `Explore` worker type | Generic bounded research worker with sequential fallback |
| `claudemd_refresh_targets` | `instruction_refresh_targets` |
| “Claude Code” as the engineering audience | “coding agent” or “engineering side” |
| Claude Design as the design gate itself | Provider-independent artifact gate |
| Claude-only installation and slash-command examples | Separate Claude Code and Codex installation/invocation sections |

Claude-specific terminology may remain inside the explicitly scoped `claude-design` adapter and Claude installation instructions.

## Error Handling and Degradation

- Missing Superpowers dependency: stop before artifact production and explain how to install it for the active runtime.
- No worker delegation: execute research scopes sequentially.
- No Claude Design: use `manual`.
- Conflicting `AGENTS.md` and `CLAUDE.md` values: display both with provenance during profile confirmation.
- Missing applicable profile field: stop at the phase that needs it; do not guess.
- Invalid or incomplete design handoff: report the missing gate conditions and remain at the design phase.
- Unsupported design provider: stop and list the supported providers.
- Existing old profile path only: report that the neutral profile is missing and direct the user to rerun `init-profile`; do not read the old file.

## Documentation

`README.md` will:

- describe Elephant as a Claude Code and Codex delivery harness;
- document the neutral profile path;
- show separate installation and explicit invocation examples for each host;
- state that Superpowers is required;
- explain the portable manual design flow and optional Claude Design integration;
- document the reinstall-and-new-session boundary for testing updated plugins.

`runtime-compatibility.md` will be the single detailed mapping for host-specific invocation, delegation, instruction files, installation, and optional design capabilities. Shared skill files will reference it only when a runtime distinction matters.

## Validation Strategy

### Static compatibility validator

`scripts/validate-compatibility.py` will verify:

- both plugin manifests exist and identify the same plugin and version;
- both marketplace files resolve to the shared plugin directory;
- the Codex manifest points to `./skills/`;
- every skill has valid `name` and `description` frontmatter;
- the old profile path is absent from executable workflow instructions;
- known Claude-only core phrases, such as “via the Skill tool,” `Explore` worker requirements, and `claudemd_refresh_targets`, do not re-enter shared workflow text;
- allowed Claude-specific terms are confined to the Claude packaging/docs sections and `claude-design` adapter.

### Platform validators

- Run the Codex plugin validator against `plugins/elephant`.
- Run the skill validator for every skill directory.
- Parse and structurally check the Claude marketplace and manifest JSON.
- Run the repository's compatibility validator.

### Installation smoke tests

After reinstalling the plugin, use a new session and run the same representative cases in both hosts:

1. `kickoff` activates and preflights Superpowers.
2. `init-profile` writes only `.agents/elephant/delivery-profile.md`.
3. `init-profile` detects and reports conflicting persistent instructions.
4. `ship-story` stops cleanly when the neutral profile is missing.
5. A non-UI slice bypasses the design gate.
6. A UI slice using `manual` stops with exact handoff instructions and resumes after approval.
7. A UI slice using `claude-design` pulls the design and satisfies the common handoff contract.
8. A host without worker delegation completes research sequentially.

The repository will document these cases and expected outcomes. Codex-side validation can run in the current environment; Claude Code activation and DesignSync behavior require a Claude Code smoke-test session after reinstall.

## Success Criteria

- The repository is recognized as a valid Codex plugin marketplace and retains its Claude marketplace.
- Both hosts load the same five Elephant skills from one source tree.
- Core workflow files contain no dependency on the old `.claude/delivery-profile.md` path.
- Core behavior does not require Claude-only skill invocation or worker types.
- Codex can complete the workflow using the `manual` design provider.
- Claude Code can optionally use `claude-design` without changing the common workflow.
- Missing capabilities fail explicitly or degrade as designed.
- Static and Codex validators pass.
- The documented smoke cases pass in both hosts after reinstall.

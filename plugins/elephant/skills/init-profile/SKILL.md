---
name: init-profile
description: Use when a repo needs a delivery-profile for the ship-story skill — bootstrapping a new project (kickoff's final phase) or retrofitting an existing repo. Triggers on "/init-profile", "set up the delivery-profile", "make this repo ship-story-ready", "generate/refresh delivery-profile".
---

# Init-Profile

## Overview

Produce (or refresh) a repo's `.claude/delivery-profile.md` — the contract the `ship-story` skill consumes. This is Phase C of the `kickoff` pipeline; it also runs standalone to retrofit an existing repo.

**Core principle: the profile is DISCOVERED, not interrogated.** Most fields already exist in the repo's files, CLAUDE.md, memory, and notes — mine them and draft. Ask the user ONLY for fields that have no repo signal and no safe default. Never make the user re-state what's already written down.

## Prerequisite

Read the field contract first: the `delivery-profile-schema.md` reference doc bundled with this plugin's `ship-story` skill — it lists every section a profile must map to. (For a worked example, see an existing project's `.claude/delivery-profile.md`.)

## Flow: discover → draft → ask-only-unknowables → confirm → write

1. **Discover.** Gather from every source below; map each finding to a schema field.
2. **Draft.** Fill every field you can. Tag each value with its provenance: `[detected]` / `[mined:<file>]` / `[default]` / `[asked]` / `[TBD]`.
3. **Ask only unknowables.** For fields with no signal AND no safe schema default, ask the user — batched, once. Do NOT ask fields you detected or that have a sensible default.
4. **Confirm.** Present the full drafted profile WITH the provenance tags so the user can scan what was detected vs. guessed vs. asked. User edits/approves. **🛑 This is the only checkpoint.**
5. **Write.** Save `.claude/delivery-profile.md`. Validate: every schema section present; applicable-but-unresolved fields written as literal `TBD` (see TBD vs. omit below) so ship-story's TBD-stops can catch them.

## Discovery source → field mapping

Every right-column entry is a real schema field. If a detection has no schema home, it does not belong in the profile — drop it.

| Source | Schema fields |
|---|---|
| `package.json` (scripts, packageManager), lockfile | `execution.gotchas` (command-form traps only — e.g. the filter/run form, lockfile checks) |
| `.changeset/` exists | `versioning.changeset_cmd`, `versioning.empty_cmd` |
| `.github/workflows/*.yml` | `finish.ci_required_checks` (see recipe) |
| `git` / `gh` (default branch, squash setting) | `finish.integration`, `finish.branch_pattern` (see recipe) |
| `docs/**` (`*roadmap*` files; `specs/`+`plans/` dirs; spec-system dir) | `roadmap_path`, `spec_dir`, `plan_dir`, `global_specs` (see disambiguation) |
| **CLAUDE.md (root + nested)** ★ | `finish.*`; `language gates`; `design gate`/`field-naming` enabled+refs; `status_flow`; `execution.gotchas` |
| **memory + `docs/notes`** ★ | `execution.gotchas` |

★ = highest-value sources. The bulk of a mature repo's profile lives in CLAUDE.md + memory, not in code.

### Extraction recipes (the ★ and ambiguous rows)

- **`status_flow`**: grep global-specs / spec-template for an arrow-joined status list (`A → B → C`). Absent → schema example default, tag `[default]`.
- **`finish.ci_required_checks`**: a CI job becomes *required* only if CLAUDE.md/docs name it as a merge gate. If none is named, list all workflow job names and ask the user which gate merge (don't assume all of them).
- **`finish.integration` / `branch_pattern`**: read CLAUDE.md's finish/merge section first (e.g. "PR + squash + linear main"). If `gh` API is denied (free repo / 403), fall back to CLAUDE.md prose + `git log` branch names; if still unclear, ask. `branch_pattern` = a naming regularity seen in ≥3 recent merged branches, else ask.
- **`execution.gotchas`**: include a `project_*` memory/notes entry only if it constrains build/test/commit/deploy flow (a trap or known-bug). Exclude `feedback_*` and pure product-rule entries. When unsure, list candidates at confirm and let the user prune.
- **`design gate` / `field-naming` enabled**: enabled iff CLAUDE.md or docs describe such a gate (e.g. a design-before-UI rule; a field-naming/AD convention). `decision_ref`/`field_contract_location` come from that same prose. No such prose → `enabled: false`.

### Doc-dir disambiguation

If multiple dirs match the roadmap/spec/plan globs, **prefer the path CLAUDE.md declares as the artifact home**; never auto-pick a generic `docs/superpowers/` if CLAUDE.md routes artifacts elsewhere. Multiple unresolved candidates → show them at confirm and ask.

## Ask only these (typical unknowables)

Fields that usually have no repo signal — ask, or take the schema default if one exists and the user doesn't care:

- preferences without a repo signal: `research.depth` (default: light fan-out), `auto_merge_on_green` (default: true), `review_cadence`.
- `branch_pattern` if git history shows no consistent naming.

**Never ask `design_project_ref`** — it has no repo signal by nature; write `TBD` and let ship-story stop for it at the design gate. (Same for any gate field that applies but is unresolvable: `TBD`, don't guess.)

### TBD vs. omit vs. disabled

- A gate that **doesn't apply** → set its `enabled: false` (and omit its sub-fields). Do NOT `TBD` the sub-fields of a disabled gate.
- A field that **applies but is unresolved** → write literal `TBD` (never omit), so ship-story's TBD-stop catches it.
- This resolves the schema's "omit non-applicable fields" against this skill's "never omit": omission is for *disabled/inapplicable* fields; `TBD` is for *applicable-but-unknown* fields.

## Reconcile, don't clobber

If `.claude/delivery-profile.md` already exists, diff your fresh draft against it:

- **Fill only literally-missing fields.** A value already present is never overwritten automatically.
- **"Stale" = narrow:** a value is stale-refreshable ONLY if it is provenance-tagged `[detected]` AND its repo source has changed. Refresh those silently.
- **Untagged existing profile (e.g. a hand-authored one):** treat EVERY value as user-authored. Fill only missing fields; never overwrite. (Hand-filled values like a real `design_project_ref` must survive.)
- **Detected-vs-existing disagreement:** never auto-apply. Surface it at confirm as a *proposed* change and let the user decide.
- **A literal `TBD` value counts as unresolved, not user-authored:** you MAY re-attempt detection to fill it (the one case where touching a present value is allowed). Can't resolve → leave the `TBD`.

## Greenfield fallback

Sparse repo (thin or no CLAUDE.md). Note: when run as kickoff's Phase C, **Phase A/B already produced `global_specs`, `roadmap_path`, and the spec/plan dirs** — take those from the pipeline, not from greenfield guessing. Standalone on a truly bare repo, apply this disposition so the profile is still complete and schema-valid:

| Field group | Greenfield disposition |
|---|---|
| `roadmap_path`, `story_id_pattern`, `global_specs`, `spec_dir`, `plan_dir`, `spec_template` | from Phase A/B if in pipeline; else `TBD` (ship-story needs them before any slice) |
| `filename_rule` | default `[ID]-[slug].md` |
| `status_flow` | schema example default |
| `field-naming`, `design gate` | `enabled: false` unless a signal exists |
| `research`, `execution.default_mode/isolation`, `auto_merge_on_green` | schema defaults |
| `execution.gotchas` | empty list (nothing to mine on a bare repo) |
| `review_cadence`, `branch_pattern`, `ci_required_checks` | ask (or `TBD` if user defers) |
| `finish.integration` | default `PR + squash + delete branch` |
| `versioning.*` | if no `.changeset/`: omit the section (ship-story skips the changeset step) |
| `closeout.*` | default: flip roadmap + refresh touched CLAUDE.md; `root_snapshot_check` off |
| `language gates` | ask `commit_lang`/`docs_lang`/`dialogue_lang` (no safe universal default); `context7_first` default true |

## Red flags — STOP

- Asking the user a field you could have detected or mined → re-check the sources first.
- Overwriting an existing profile instead of reconciling → diff and preserve user values.
- Omitting an unresolved field instead of writing `TBD` → ship-story can't catch a missing field; write `TBD`.
- Inventing a value for a gate (e.g. a fake projectId) → write `TBD` and let ship-story stop later.
- Generating a roadmap or spec system → out of scope; that's kickoff Phase A/B.

## Common mistakes

- **Skipping the CLAUDE.md/memory mine.** Detecting only "hard facts" (package manager, CI) misses the highest-value conventions (gates, finish flow, gotchas) that live in prose.
- **Treating the confirm step as field-by-field interrogation.** Draft first, confirm the whole thing once.

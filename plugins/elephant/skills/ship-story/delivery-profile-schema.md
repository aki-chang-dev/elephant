# Delivery-Profile Schema

The contract between `kickoff` (producer) and `ship-story` (consumer). One markdown file per repo at `.claude/delivery-profile.md`. `ship-story` reads it to decide which gates to insert and where artifacts live. **Zero project-specifics belong in the skills — they all live here.**

## Sections

| Section | Fields | Notes |
|---|---|---|
| **story source** | `roadmap_path`, `story_id_pattern` | roadmap file; ID prefix rule (e.g. `S-/F-/P-/A-`) for locating a story |
| **artifact paths** | `spec_dir`, `plan_dir`, `filename_rule`, `spec_template`, `status_flow` | where specs/plans land; filename rule (e.g. `[ID]-[slug].md`); spec template path; status vocabulary (e.g. `Draft→Refined→Implementing→Done`) |
| **global specs** | `global_specs[]` | immutable spec files to load as context during brainstorm/spec |
| **field-naming prereq** | `enabled`, `decision_ref`, `field_contract_location` | gate before writing fields; naming-convention ref; where field contracts get back-filled |
| **design gate** | `enabled`, `ui_detection`, `design_project_ref`, `slice_to_design_mapping`, `design_local_dir`, `ready_signal` | whether UI slices wait for design; how to detect "is UI" (default: spec §6 sensitivity ≠ Low); Claude Design project (DesignSync projectId/name); slice→design-page mapping; local dir DesignSync pulls into (Step 0 detects "design pulled" by its presence); ready-signal source (human) |
| **research policy** | `mode`, `depth` | default mode = "auto-assess + announce-then-confirm"; default depth = light fan-out 3-5 `Explore`/general agents; optional deep-research escalation |
| **execution** | `default_mode`, `isolation`, `review_cadence`, `gotchas[]` | default subagent-driven; worktree isolation; per-task review cadence; known traps (e.g. install flags, filter command form, lockfile checks) |
| **finish** | `integration`, `branch_pattern`, `ci_required_checks[]`, `auto_merge_on_green` | PR + squash + delete-branch + linear main; how branches/worktrees are named (used by Step 0 detection, e.g. names contain the slice `<ID>`); required green check names; auto-merge on green (default true) |
| **versioning** | `changeset_cmd`, `empty_cmd` | changeset command; empty form for docs-only |
| **closeout docs** | `roadmap_done_flip`, `claudemd_refresh_targets`, `root_snapshot_check` | flip roadmap status; which CLAUDE.md files to refresh; whether to check root snapshot; single commit |
| **language / general gates** | `commit_lang`, `dialogue_lang`, `docs_lang`, `context7_first` | commit/PR/changeset language; dialogue language; docs language; context7-before-tech-claims toggle |

## Authoring notes

- A field that doesn't apply to a project is simply omitted (e.g. `design gate: enabled=false` for a headless service repo → ship-story skips Step 2 for every slice).
- `ship-story` must fail loudly (not guess) when a gate it's about to run has no profile entry.
- Generate this file by running the `init-profile` skill, or hand-author it from the schema above. For a worked example, see an existing project's `.claude/delivery-profile.md`.

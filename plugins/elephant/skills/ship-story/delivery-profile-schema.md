# Delivery-Profile Schema

The contract between `elephant:kickoff` or `elephant:init-profile` (producer) and
`elephant:ship-story` (consumer). Each repository has one runtime-neutral profile at
`.agents/elephant/delivery-profile.md`. Project-specific paths, gates, and conventions belong in
that profile, not in shared skills.

New projects use the Elephant layout under `docs/elephant/<product>/`: `spec/` for global specs,
`roadmap.md`, `specs/` for story contracts, and `plans/`. Profiles record actual paths, so
existing projects keep their current layout.

## Story-contract mode

New profiles include:

```yaml
story_contracts:
  mode: dual
  product_template: shape-story/product-contract-template.md
  technical_template: author-technical-contract/technical-contract-template.md
  product_filename_rule: [ID]-[slug]-product.md
  technical_filename_rule: [ID]-[slug]-technical.md
```

`product_template` and `technical_template` may be repository paths or the bundled defaults shown
above. Dual mode writes both artifact kinds under `spec_dir`. Engineering-only stories omit the
Product Contract and use the technical template with `product_contract: null`.

The two default strings above are compatibility aliases resolved relative to the plugin's
`skills/` directory. Every other configured template is a repository-relative path resolved from
the repository root. A configured value must exist; bundled fallback applies only when the field
is omitted.

Filename rules are basenames under `spec_dir`. Each contains `[ID]` and `[slug]` exactly once,
ends in `.md`, and contains no absolute path, path separator, `.` segment, or `..` segment.
`ship-story` renders these configured rules both for candidate detection and author output; it
does not hardcode the bundled filenames.

### Product Contract `supersedes`

Canonical writers emit a YAML list of strings. Readers accept legacy shapes:

- `null` normalizes to an empty list;
- a scalar string normalizes to a one-item list;
- a list of strings is canonical.

Values are exact repository-relative POSIX paths. Comparison is case-sensitive on every host.
Absolute paths, URIs, backslashes, empty/duplicate values, `.` or `..` segments, repository
escapes, outside-resolving symlinks, missing files, and another story's artifacts are prohibited.
When several legacy artifacts collide with one v2 story, the active Product Contract must list
every colliding legacy path. Partial coverage never selects v2.

### Compatibility table

| Profile state | Effective mode | Required behavior |
|---|---|---|
| new or greenfield profile | `dual` | Write `story_contracts` with the two bundled templates and v2 filename rules. |
| existing profile with explicit `mode: dual` | `dual` | Preserve its explicit templates, paths, and filename rules. |
| existing profile with explicit `mode: legacy-mixed` | `legacy-mixed` | Preserve its mixed `spec_template`, `filename_rule`, and `status_flow`. |
| existing profile missing `story_contracts` or `story_contracts.mode` | `legacy-mixed` | Interpret mechanically as legacy; never silently migrate it. |
| unsupported explicit mode | none | Stop and ask the user to select `dual` or `legacy-mixed`. |

A refresh may propose migration from implicit `legacy-mixed` to `dual` at the normal profile
confirmation checkpoint. It does not apply the migration without approval and does not move,
rename, rewrite, or dual-write existing artifacts. Existing mixed specs remain resumable.

## Sections

| Section | Fields | Notes |
|---|---|---|
| **story source** | `roadmap_path`, `story_id_pattern` | Roadmap file and ID prefix rule for locating a story. |
| **story contracts** | `mode`, `product_template`, `technical_template`, `product_filename_rule`, `technical_filename_rule` | Required on new profiles. `mode` is `dual` or `legacy-mixed`. Template and filename fields are injected into dual detection and author dispatch. |
| **artifact paths** | `spec_dir`, `plan_dir`, optional legacy `filename_rule`, `spec_template`, `status_flow` | `spec_dir` stores story contracts in both modes. The legacy fields preserve the mixed-spec structure; bundled legacy `spec_template` is `slice-template.md`. |
| **global specs** | `global_specs[]` | Immutable product/spec-system context loaded before authoring. |
| **field-naming prereq** | `enabled`, `decision_ref`, `field_contract_location` | Legacy mixed-spec gate before writing fields. V2 technical authoring follows repository evidence without modifying the approved Product Contract. |
| **design gate** | `enabled`, `ui_detection`, `provider`, `design_local_dir`, `handoff_file`, `ready_signal`, optional `claude_design` | Shared gate. Dual `ui_detection` reads Product Contract `design_sensitivity`; legacy reads mixed spec §6. Supported providers remain `manual` and `claude-design`. |
| **research policy** | `mode`, `depth` | Research scope and depth. Bounded workers may run in parallel; identical sequential fallback is required. |
| **execution** | `default_mode`, `isolation`, `review_cadence`, `gotchas[]` | Execution skill, worktree isolation, review cadence, and repository-specific traps. |
| **finish** | `integration`, `branch_pattern`, `ci_required_checks[]`, `auto_merge_on_green` | Integration mechanics, resume detection, required checks, and merge policy. |
| **versioning** | `changeset_cmd`, `empty_cmd` | Changeset command and docs-only form when applicable. |
| **closeout docs** | `roadmap_done_flip`, `instruction_refresh_targets`, `root_snapshot_check` | Roadmap completion and durable instruction refresh in one closeout commit. |
| **language / general gates** | `commit_lang`, `dialogue_lang`, `docs_lang`, `context7_first` | Commit, dialogue, and documentation language plus external-doc policy. |

## Authoring notes

- Omit sub-fields only when their gate or section is disabled or inapplicable. Use literal `TBD`
  for an applicable unresolved field so `ship-story` can stop safely.
- `ship-story` fails loudly when a gate it is about to run has no required profile value.
- Existing explicit values are user-owned. Refreshing fills missing non-mode fields or proposes
  changes at confirmation; it never silently overwrites an explicit story-contract mode.
- Do not read, migrate, or dual-write any runtime-specific legacy profile path.

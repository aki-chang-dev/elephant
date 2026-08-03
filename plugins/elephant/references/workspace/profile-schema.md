# Scoped delivery-profile schema

A delivery profile supplies routing and delivery gates for one scoped type of
work. Its schema value must be `elephant.profile/v3`. Profiles do not contain
product knowledge or story history.

## Product profile

```yaml
schema: elephant.profile/v3
kind: product
product: clickfalcon
context:
  knowledge_keys:
    - product-overview
    - glossary
design_gate:
  enabled: false
research:
  mode: auto-assess
  depth: light
execution:
  isolation: git-worktree
  review_cadence: task
verification:
  commands:
    - bun run type-check
finish:
  integration: github-pr-squash
  auto_merge_on_green: true
language:
  dialogue: zh-CN
  docs: en
  commits: en
```

## Engineering profile

```yaml
schema: elephant.profile/v3
kind: engineering
product: null
context:
  knowledge_keys:
    - product-overview
    - glossary
design_gate:
  enabled: false
research:
  mode: auto-assess
  depth: light
execution:
  isolation: git-worktree
  review_cadence: task
verification:
  commands:
    - bun run type-check
finish:
  integration: github-pr-squash
  auto_merge_on_green: true
language:
  dialogue: zh-CN
  docs: en
  commits: en
behavior_preservation_required: true
```

## Fields

- `schema` is the fixed profile version: `elephant.profile/v3`.
- `kind` is `product` or `engineering`.
- `product` identifies the one workspace product that a product profile binds.
  Engineering profiles set it to `null`.
- `context`, `design_gate`, `research`, `execution`, `verification`, `finish`,
  and `language` are required mappings that carry the profile's routing and
  delivery-gate settings.
- `behavior_preservation_required` must be `true` for engineering profiles.

## Invariants

- Product profiles bind exactly one workspace product key.
- Engineering profiles use `product: null` and require behavior preservation.
- Profile selection comes from Linear Product/Kind through the registry, not
  repository directory names.
- Affected engineering domains are discovered from repository evidence and the
  eventual diff.
- Profiles contain routing and gates, never product knowledge or story history.
- Every path is repository-relative POSIX and must remain within the repository.

# Workspace registry schema

A workspace registry is a repository-level routing document. It identifies the
repository, selects the stores that hold workspace concerns, binds any selected
external stores, and maps products to engineering domains. Its schema value must
be `elephant.workspace/v3`.

## External-provider registry

```yaml
schema: elephant.workspace/v3
repository:
  id: repo-maio
providers:
  story_store: linear
  product_knowledge_store: notion
  product_contract_store: notion
  delivery_workspace: git
bindings:
  linear:
    workspace_id: lin-ws
    team_id: lin-team
  notion:
    workspace_id: notion-ws
    products_database_id: db-products
    knowledge_database_id: db-knowledge
    contracts_database_id: db-contracts
products:
  clickfalcon:
    profile: .agents/elephant/profiles/clickfalcon.yaml
    story_ref: linear-label-clickfalcon
    knowledge_ref: notion-product-clickfalcon
    primary_domains:
      - clickfalcon
domains:
  clickfalcon:
    scopes:
      - apps/tracker-web
      - apps/tracker-engine
    instruction_paths:
      - AGENTS.md
    verification:
      - bun run type-check
    products:
      - clickfalcon
engineering_profile: .agents/elephant/profiles/engineering.yaml
```

### Fields

- `schema` is the fixed registry version: `elephant.workspace/v3`.
- `repository.id` is the repository's stable identifier.
- `providers` selects the backing store for each concern:
  - `story_store` is `linear` or `git`.
  - `product_knowledge_store` is `notion` or `git`.
  - `product_contract_store` is `notion` or `git`.
  - `delivery_workspace` is `git`.
- `bindings` stores connection details for selected external providers. A
  selected `linear` provider requires a `bindings.linear` entry and a selected
  `notion` provider requires a `bindings.notion` entry. No binding is required
  for a provider that is not selected.
- `bindings.linear.workspace_id` and `bindings.linear.team_id` identify the
  Linear workspace and team.
- `bindings.notion.workspace_id`, `products_database_id`,
  `knowledge_database_id`, and `contracts_database_id` identify the Notion
  workspace and its databases.
- `products` is keyed by product identifier. Each product has a repository-relative
  POSIX `profile` path, its story and knowledge references, and
  `primary_domains`, whose entries must name existing domains.
- `domains` is keyed by domain identifier. Each domain declares repository-relative
  POSIX `scopes`, `instruction_paths`, verification commands, and `products`,
  whose entries must name existing products.
- `engineering_profile` is the repository-relative POSIX path to the engineering
  profile.

Repository-relative POSIX paths are non-empty, use `/` rather than `\`, do not
start with `/`, and do not include `.` or `..` path segments. This applies to
profiles and domain scopes; use the same path convention for instruction paths.

External IDs are opaque. Discover them from the selected provider and read them
back before saving the registry; never guess their values.

## All-Git registry

An all-Git workspace declares no `linear` or `notion` binding:

```yaml
schema: elephant.workspace/v3
repository:
  id: repo-maio
providers:
  story_store: git
  product_knowledge_store: git
  product_contract_store: git
  delivery_workspace: git
bindings: {}
products:
  clickfalcon:
    profile: .agents/elephant/profiles/clickfalcon.yaml
    story_ref: clickfalcon
    knowledge_ref: clickfalcon
    primary_domains:
      - clickfalcon
domains:
  clickfalcon:
    scopes:
      - apps/tracker-web
      - apps/tracker-engine
    instruction_paths:
      - AGENTS.md
    verification:
      - bun run type-check
    products:
      - clickfalcon
engineering_profile: .agents/elephant/profiles/engineering.yaml
```

## Prohibited content

The workspace registry is not a story tracker. It must not include the
story-level keys `stories`, `story_registry`, `checkpoints`, `contracts`, or
`plans`.

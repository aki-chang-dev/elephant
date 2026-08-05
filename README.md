# 🐘 Elephant

Elephant is a product-first coordination plugin for Claude Code and Codex. It helps one owner work
with agents across three authoritative homes:

- Linear owns live planning, priority, dependencies, and progress.
- Notion owns durable product meaning and decisions.
- Git/GitHub owns executable behavior and delivery.

Elephant remains a thin router. It uses each product's native objects and relationships instead of
building another project-management database or copying roadmap state into the repository.

## Workflow

```text
one-sentence idea
→ kickoff
   → author-product-spec    minimum useful Notion product foundation
   → decompose-roadmap      progressive native Linear planning
   → setup-workspace        repository/Product/domain entry-point map

Linear Story
→ shape-story               product-only discussion + one recap approval
→ author-technical-contract transient technical design + specialist review
→ ship-story                plan, worktree, implementation, review, PR, native closeout
```

| Skill | Role |
|---|---|
| `elephant:kickoff` | Resume the first incomplete product foundation, planning, or setup outcome. |
| `elephant:author-product-spec` | Establish or refresh valuable Product Home/Overview/Knowledge. |
| `elephant:decompose-roadmap` | Create the smallest useful native Linear planning structure. |
| `elephant:setup-workspace` | Discover Products/domains and write the verified workspace map. |
| `elephant:shape-story` | Turn one sentence into an approved user outcome and native planning/knowledge action. |
| `elephant:author-technical-contract` | Bind current product sources to reviewed technical choices. |
| `elephant:ship-story` | Deliver or resume one Linear Story through integration and native closeout. |

The only durable repository coordination file is:

```text
.agents/elephant/workspace.yaml
```

Technical Contracts and implementation plans may be committed on an isolated delivery branch for
resume, but Elephant removes them before integration. Product Contracts, Git roadmaps, delivery
logs, checkpoints, and copied Notion content are not part of the workflow.

## Owner attention

The owner starts with an idea and participates deeply in product shaping. One shaping recap
approval authorizes the displayed Linear and Notion changes. Technical design, specialist review,
planning, implementation, code review, factual progress, and closeout are agent-owned.

Elephant returns to the owner when product meaning, acceptance, Product ownership, or strategic
priority must change—not for routine data entry or technical review.

## Native relationships

Branch names and pull-request titles/descriptions contain the Linear Issue identifier so native
Linear-GitHub integration can connect delivery. Notion pages and Linear work use ordinary reciprocal
links or previews. Missing convenience degrades to ordinary links; missing authoritative context is
reported rather than guessed.

## Install

Install Superpowers first.

Claude Code:

```text
/plugin marketplace add aki-chang-dev/elephant
/plugin install elephant@elephant
```

Codex:

```bash
codex plugin marketplace add aki-chang-dev/elephant
codex plugin add elephant@elephant
```

Start a new host session after install/update so the skill inventory reloads. Invoke skills through
the host's installed-skill interface, for example `elephant:kickoff` or
`elephant:ship-story CF-123`.

## Development validation

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate-compatibility.py
uv run --with pyyaml python \
  /Users/aki/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/elephant
```

## License

MIT © Aki Chang

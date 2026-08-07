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
→ ship-story                proportionate assurance, implementation, PR, native closeout
   → author-technical-contract only for named elevated technical risk
```

| Skill | Role |
|---|---|
| `elephant:kickoff` | Resume the first incomplete product foundation, planning, or setup outcome. |
| `elephant:author-product-spec` | Establish or refresh valuable Product Home/Overview/Knowledge. |
| `elephant:decompose-roadmap` | Create the smallest useful native Linear planning structure. |
| `elephant:setup-workspace` | Discover Products/domains and write the verified workspace map. |
| `elephant:shape-story` | Turn one sentence into an approved user outcome and native planning/knowledge action. |
| `elephant:author-technical-contract` | Resolve named elevated technical risk with applicable specialists. |
| `elephant:ship-story` | Deliver or resume one Linear Story with proportionate assurance and native closeout. |

The only durable repository coordination file is:

```text
.agents/elephant/workspace.yaml
```

Multi-step work may keep a concise transient plan on its isolated delivery branch. Technical
Contracts exist only for elevated assurance. Elephant removes both before integration. Product
Contracts, Git roadmaps, delivery logs, checkpoints, and copied Notion content are not part of the
workflow.

## Owner attention

The owner starts with an idea and participates deeply in product shaping. One shaping recap
approval authorizes the displayed Linear and Notion changes. Technical design, specialist review,
planning, implementation, code review, factual progress, and closeout are agent-owned.

Elephant returns to the owner when product meaning, acceptance, Product ownership, or strategic
priority must change—not for routine data entry or technical review.

## Proportionate assurance

Ordinary Stories use an in-session checklist or concise plan, repository verification, and one
independent final delivery review. Elephant adds specialist technical review only when current
evidence shows money, destructive data/migration, security or authorization, concurrency or
transactions, production rollout/recovery, or major system-boundary risk. Uncertain risk takes the
safer path and is explained at closeout.

Review packets contain only decision-relevant context; complete product authority remains present
for product and final conformance. Fixes recheck only affected requirements and evidence. Elephant
does not treat parallel workers as token savings or impose a hard context quota that could remove
decision-critical evidence.

## Planning model

Elephant starts from the idea, not from a mandatory hierarchy. It introduces only the native
Linear structure that makes the work easier to understand:

- **Product** is the durable product boundary. A single-Product workspace needs no Product labels;
  a multi-Product workspace labels every managed Issue, Project, and Initiative so routing stays
  explicit. Issue labels exist from setup; Project and Initiative label namespaces activate only
  when that Product first uses the matching planning level.
- **Objective** expresses a useful strategic destination and is represented by a Linear
  **Initiative**. A Story may link directly as `Related Objective` without manufacturing a Project
  or contributing progress to that Objective.
- **Project** owns a coherent workstream; **Milestone** marks a meaningful Project phase;
  **Story** is the independently deliverable user outcome. None is created merely to fill the
  hierarchy.

`elephant:setup-workspace` discovers repository domains and the available Linear, Notion, and
GitHub context without writing. It proposes one Product/domain routing map, asks for one approval,
creates or reuses only the approved native entry points, verifies them through normal reads, and
writes `.agents/elephant/workspace.yaml` last. The map stores entry points, not copied content.

## Information routing

Planning questions start from the mapped Linear Product scope. Product-meaning questions start
from the mapped Notion Product Home or Knowledge Map. Executable-behavior questions start from the
repository. Elephant follows direct native relations before expanding scope and never begins with
a global search when the workspace map already names the authoritative entry point.

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

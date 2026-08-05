# Information routing

Elephant coordinates three authoritative homes. Linear owns live planning and progress, Notion
owns durable product meaning and decisions, and Git/GitHub owns executable behavior and delivery.
Links and previews connect those homes; they do not copy authority from one home into another.

## Resolve scope first

Resolve the repository and Product before searching. A single Product is implicit. With multiple
Products, prefer the current Story's Product Issue label, verify matching Project and Initiative
labels and Milestone ownership, and ask one bounded Product question only when explicit context
and native relationships remain ambiguous.

Before using an object, verify its native ownership: an Issue belongs to the configured Team, a
Project includes that Team, an Initiative belongs to the configured workspace, a Milestone belongs
to an in-scope Project, a Notion page is under the configured root, and GitHub content belongs to
the configured repository.

## Choose the authoritative route

### Planning and progress

Start with the current Linear Story and its Project, Initiative, Milestone, dependencies, and the
configured Product planning entry. If that is insufficient, search within the Product's Linear
scope. For one Product, constrain reads to the configured Team and planning/backlog entries. For
multiple Products, additionally require the matching Product labels. Cross to Notion only through
a direct relation or when the question explicitly needs product meaning absent from Linear.

### Product meaning and decisions

Start with directly linked Notion pages, then Product Home and Knowledge Map, then Product Home
descendants. Expand to Shared Knowledge and finally workspace-wide Notion search only when the
narrower evidence is insufficient. Read Linear through a direct relation only when current
planning state is necessary.

### Executable behavior

Start with the linked GitHub branch or pull request and repository paths, then search only the
repository. Read Linear or Notion through direct relations only when delivery scope or approved
product meaning is necessary to interpret the code.

## Stop and report

Stop expanding as soon as the question is answered and return direct source links. If the
authoritative home is unavailable or lacks decision-critical context, name what is missing and the
shortest place to supply it. Never infer an authoritative fact from another system's stale preview,
copied text, or projection.

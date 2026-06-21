# Spec-System Template

> The canonical structure a `author-product-spec` run produces = `global_specs`. Create these as separate files in the project's spec dir (Elephant default: **`docs/elephant/<product>/spec/`**). Core docs: master-spec, object-model, glossary, and a **decision log** (default taxonomy = AD + ED files below; a project may instead use ADR/RFC/a single `decisions.md` — keep the filenames matching whatever `decision_ref` convention the project adopts). Add domain-specific docs only as needed. Downstream (`decompose-roadmap`, `ship-story`) loads these as context and references decision-record ids + entity field contracts.

---

## File layout

```
<spec-dir>/
  00-master-spec.md
  10-object-model/
    overview.md
    cross-rules.md
    entities/<entity>.md      # one per entity
  20-glossary.md
  30-architecture-decisions.md   # AD-1..
  35-engineering-decisions.md    # ED-1..
  <NN>-<domain-doc>.md           # optional, domain-specific
```

## 00-master-spec.md

1. **Product definition** — what it is, who it's for, the core value.
2. **Scope boundary** — explicitly IN / explicitly OUT (this version).
3. **Object-model overview** — one-paragraph map; pointer to `10-object-model/`.
4. **Module index** — the subsystems + where each is specced.
5. **Cross-cutting principles** — rules that hold everywhere.
6. **Technical constraints** — hard non-negotiables.
7. **How to use this spec** (for AI agents) — reading order.
8. **Change log**.

## 10-object-model/

- **overview.md** — the entity set + relationships (a map).
- **entities/<entity>.md** — per entity:
  - purpose (one line)
  - **field contract** table: `field | type | required | notes` — every field follows the naming-convention AD; unresolved names start as `TBD` and get pinned during the slice that creates them.
  - entity-local rules.
- **cross-rules.md** — invariants spanning >1 entity.

## 20-glossary.md

Alphabetical or grouped term list. Each: **term** — definition, with any synonyms and the canonical form. Link first use in other docs back here.

## 30-architecture-decisions.md (AD)

One entry per decision, numbered `AD-N`:

```
### AD-N: <short title>
- Context: <the situation/forces>
- Decision: <what was decided>
- Rationale: <why; what it rules out>
- Consequences: <downstream effects, follow-ups>
```

Product-level, stable. Includes the **field-naming convention** AD (pin its number early — ship-story / init-profile reference it).

## 35-engineering-decisions.md (ED)

Same entry format as AD, numbered `ED-N`. Implementation-level: stack, deploy topology, library choices, patterns. Evolves with tech.

## Cross-reference rules

- Entity field contracts cite the AD that governs naming.
- ADs/EDs referenced by number from master-spec + entities.
- Glossary terms linked on first use.
- master-spec module index points to every doc above.

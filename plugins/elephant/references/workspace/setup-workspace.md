# Setup workspace protocol

This is the canonical provider-neutral protocol for `elephant:setup-workspace`.
It defines the one approval authority, operation ordering, verification evidence,
and Phase 2 boundary. Read it together with the canonical
[workspace registry](workspace-schema.md), [profile](profile-schema.md),
[provider capability](provider-contracts.md), and
[story-state](story-state-model.md) contracts before running setup.

## Certification boundary

Phase 2 certifies orchestration behavior with deterministic repository fixtures
and fake `SetupAdapter` implementations. It does not certify concrete Linear or
Notion adapters, issue real provider mutations, or activate v3 story delivery.
Linear certification remains Phase 3 and Notion certification remains Phase 4.
Until those phases, a setup selecting either real provider stops before all
external and local writes. The active shipping runtime remains v2; v3 is not an
active shipping path.

## Authority chain

`ConfirmedTopology` is the only semantic input to `build_setup_manifest()`.
The builder emits an immutable `SetupManifest`; `manifest_fingerprint()` binds
every provider selection, product, domain, operation, diagnostic, conflict,
question, local document, and expected local-container state. Only
`approve_manifest(manifest, displayed_fingerprint)` can produce the
`ApprovedManifest` accepted by `apply_setup()`.

Approval never transfers between manifests. Resolving an owner question,
changing a provider, refreshing discovery, changing a local diff, or changing
any operation regenerates the manifest and requires approval of its newly
displayed fingerprint. An earlier proposal, partial display, mapping document,
or checklist grants no write authority.

## Protocol

### 1. Discover without writes

Run repository and external discovery read-only. Inventory repository units,
dependency edges, instructions, product evidence, existing provider objects,
and stable external IDs. Inventory the connector's actual operations across
four distinct layers for every required capability:

1. supported by the platform;
2. exposed by the connector;
3. permitted for the current actor;
4. configured for the selected workspace.

Connector or MCP presence alone proves none of these layers. Discovery must not
write local mappings, setup checklists, proposed configuration, or external
objects.

### 2. Propose independent topology

Build product candidates and engineering-domain candidates independently.
Every candidate retains provenance and confidence. Keep competing evidence in
`TopologyConflict` values and unresolved product judgment in `OwnerQuestion`
values. An app, package, directory, team, or deployment unit is engineering
evidence, not product identity by itself.

### 3. Hold one owner decision session

Use one owner checkpoint for the entire setup. First resolve every semantic
product/domain question and conflict. Convert only those explicit answers into
`ConfirmedTopology`, then regenerate the complete dry run during the same
decision session. Do not seek a preliminary write approval and do not add a
second routine approval after regeneration.

The approval display contains:

- confirmed products and engineering domains, with their cross-links;
- all logical-to-physical provider selections;
- structures to reuse, create, complete manually, verify, and round trip;
- every unresolved conflict and its evidence;
- exact capability diagnostics and whether each is administrative or runtime;
- the complete local file diff, including expected prior state;
- the disposable-record creation, deletion, and absence-check plan;
- the fingerprint of this exact complete `SetupManifest`.

The owner approves that displayed fingerprint. If questions remain or the
display changes, regenerate and redisplay before approval. No local or external
write occurs before `approve_manifest()` accepts the exact digest.

### 4. Execute stable-key idempotently

Pass only the resulting `ApprovedManifest` to `apply_setup()`. Recompute and
compare its fingerprint before the first operation. Process the manifest's
ordered `reuse`, `create`, `manual`, `verify`, `round_trip`, and `write_local`
operations; never synthesize adjacent work.

Every external target uses its approved stable key. Reuse an exact existing
match. Create a missing supported structure idempotently. A timeout or retry
must first look up that same key. Read each reuse and mutation back and compare
the observed fingerprint with the approved desired fingerprint. Duplicate
keys, mismatches, and semantic drift stop execution; setup does not rename,
move, merge, or delete user-owned external structures.

### 5. Classify diagnostics and manual work exactly

For each missing capability, emit the first missing layer in this exact order:

| Code | Classification |
| --- | --- |
| `platform_unsupported` | The platform cannot perform the operation. |
| `connector_capability_missing` | The platform supports it but the connector does not expose it. |
| `permission_missing` | The connector exposes it but the current actor cannot perform it. |
| `configuration_missing` | The required workspace object or binding is absent. |

A missing administrative setup operation may become a one-time `manual`
operation with exact instructions and mandatory read-back. A capability needed
by routine runtime operation is blocking, regardless of whether a human could
perform it manually. Never fall back to Git or another unselected provider.

### 6. Read back every result

After each supported or manual mutation, retrieve the target by its stable key
and verify persisted identity, relationships, and fingerprint. Read-back
failure stops the run and preserves the evidence accumulated so far. It does
not authorize local output.

### 7. Prove disposable round trips leave no record

For every selected external physical provider, create the approved disposable
record, read it back, exercise the binding round trip, and delete it. Then query
the same stable key and require verified absence. Archiving, closing, hiding,
or retaining the record under a cleanup policy does not satisfy this step. A
failed deletion or absence check blocks readiness and all local writes.

### 8. Write local configuration last

Only after external read-back and disposable cleanup succeed may setup apply
the approved `write_local` operations. Write only
`.agents/elephant/workspace.yaml` and direct
`.agents/elephant/profiles/*.yaml` children. Preserve unrelated local content,
verify the approved prior state, use the atomic local transaction, then load
and revalidate every written registry/profile against the canonical schemas.

### 9. Rerun as a no-write diff

Repeat discovery and build a fresh manifest. Display exact reuse/create/manual/
verify/round-trip/local differences and its new fingerprint. An unchanged
workspace produces no mutations. Missing non-semantic projections may be
proposed for repair, but a rename, move, merge, deletion, duplicate authority,
or other semantic change returns to the owner decision session.

### 10. Declare readiness across all selected providers

Readiness requires all selected logical providers to pass their complete
runtime capability contracts and all setup evidence to pass read-back,
round-trip cleanup, absence verification, local write, and local schema
validation. Administrative handoffs can complete setup prerequisites; they
cannot substitute for runtime capabilities. If any condition fails, report the
exact diagnostic and evidence and leave readiness false.

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

An administrative handoff is a pause within that same authority, not a manifest
change. Resume it by passing the exact same `ApprovedManifest` and fingerprint
to `apply_setup()` after the human completes the named operation. The resumed
call must also pass the exact `ManualHandoff` returned by the paused call as
`resume_handoff`; that typed token binds the approved operation, fingerprint,
instructions, prior execution ID, and the approval-ordered IDs of every earlier
MANUAL prerequisite that this runtime already verified. Each call has a nonblank `execution_id`
that scopes that attempt's disposable stable keys and local transaction
ownership. The resumed call uses a distinct nonblank `execution_id` for its new
attempt; changing the ID without the matching handoff token grants no
continuation authority, and neither value changes or transfers owner approval.
Do not rebuild the completed manual
operation as `REUSE`/`VERIFY`, transfer the old approval to a second manifest,
or ask for a second routine approval.

The installed plugin ships the canonical executable as
`elephant_runtime.workspace_setup`. Its public local orchestration boundary is
`fingerprint_local_container(repository_root)` plus
`RepositoryLocalWriter(repository_root)`. A source checkout may expose
`scripts.workspace_setup` as compatibility forwarding, but it is never a
second implementation or authority. The checkout forwarder accepts only a
canonical module whose resolved origin is inside that checkout's plugin root;
it rejects a stale preloaded `elephant_runtime` from another installation.

## Local host and crash-retry boundary

Read-only discovery and dry-run remain importable without loading the local
mutation backend where practical. Phase 2 local mutation is supported only on
Darwin/Linux POSIX hosts and only when the target filesystem supplies the
required native atomic rename primitive. Before any external mutation, the
local-backend preflight validates all approved local operations and this host
and filesystem capability. An unsupported host or filesystem reports the exact
blocking diagnostic `platform_unsupported`; it must not fail for the first time
after an external mutation.

Phase 2 guarantees that process death around the atomic switch exposes either
the complete old container or the complete new container. It does not yet
recognize the new container as an already committed same-approval retry when
the process dies immediately after the switch. That crash-resume behavior is a
Phase 5 acceptance criterion and remains explicitly deferred.

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
objects. Bind one descriptor to the resolved repository root for the complete
repository inventory and perform manifest, instruction, evidence, and file
reads relative to that descriptor. If the lexical root path is rebound while
discovery is running, keep the returned evidence internally coherent to the
bound repository identity and report the identity change; never combine two
repository identities into one result.

### 2. Propose independent topology

Build product candidates and engineering-domain candidates independently.
Every candidate retains provenance and confidence. Keep competing evidence in
`TopologyConflict` values and unresolved product judgment in `OwnerQuestion`
values. An app, package, directory, team, or deployment unit is engineering
evidence, not product identity by itself. When repository evidence and one or
more external records share a normalized product key, aggregate every display
alternative and provenance item into the same conflict; an earlier external
conflict must never discard the repository alternative.

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

The confirmed registry and profile payloads are the sole semantic source for
canonical local documents. `build_setup_manifest()` derives their exact YAML
bytes itself. If a caller supplies `rendered_local_documents` to carry typed
slot metadata, every supplied path and body must exactly match that derived
projection; a second, divergent document payload is rejected rather than
fingerprinted or written.

For rerun classification, supply an exact read-only
`observed_local_fingerprints` entry for every setup output path, using its
current byte SHA-256 or null for proven absence. These observations grant no
write authority. They may omit round-trip operations only when every approved
external source is already an exact REUSE/VERIFY match and the locally
materialized canonical bytes match every observation. Apply rechecks that
classification through the identity-bound local preflight before any adapter
call and fails closed if state has changed.

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

When a `MANUAL` operation is absent, return its approved handoff immediately
with `ready: false` and no local batch. On a later call using the exact same
`ApprovedManifest` and fingerprint, pass that returned handoff as
`resume_handoff` and query that stable key again. The resumed call must use a
distinct nonblank execution ID for the new attempt. The handoff's embedded
approval fingerprint, prior execution ID, operation identity, semantics, and
instructions must all match before any continuation work. For sequential
MANUAL prerequisites, the token must contain the exact ordered prefix of
earlier approved MANUAL operation IDs; each one is queried, read back, and
uniqueness-checked again. A later handoff carries that verified prefix forward,
and a missing previously completed object stops rather than reopening it.
Exactly one record
must match the operation's
approved desired fingerprint and pass read-back; then re-query with the same
unique ownership guard used for create and require the final unique record to
retain that external ID and approved fingerprint. Only then emit
`manual_completed` evidence and continue the remaining approved operations.
Absence emits the same handoff again. Duplicate records, external-ID or semantic
mismatch, or read failure stop with the manual operation context and all prior
verified evidence. No adapter mutation completes a `MANUAL` operation.

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
The manual completion check above is the continuation of the sole approved
manifest; it is not a recurring runtime handoff.

### 6. Read back every result

After each supported mutation or manually completed operation, retrieve the
target by its stable key and verify persisted identity, relationships, and
fingerprint. Read-back failure stops the run and preserves the evidence
accumulated so far. It does not authorize local output.

### 7. Prove disposable round trips leave no record

For every selected external physical provider on a setup that has external or
local changes, create or reuse the approved
disposable record and read it back. Derive a per-attempt stable key for the
disposable relationship, query that key before binding, and reuse an exact
interrupted-attempt relationship instead of creating an orphan. Read the
relationship back, re-query its stable key to prove uniqueness, unbind it, and
prove absence by both relationship ID and stable key. Then delete the
disposable record and query its stable key to require verified absence.
Archiving, closing, hiding, or retaining either object under a cleanup policy
does not satisfy this step. Any ambiguous relationship, failed deletion, or
failed absence check blocks readiness and all local writes.

A manifest proven to be a fully unchanged rerun emits no round-trip operation.
It performs only read-only REUSE/VERIFY checks and a true no-op local
transaction. A stale no-op classification stops during local preflight before
any provider call; apply never synthesizes a fresh round trip outside the
approved manifest.

### 8. Write local configuration last

Only after external read-back and disposable cleanup succeed may setup apply
the approved `write_local` operations. The only authoritative configuration
targets are
`.agents/elephant/workspace.yaml` and direct
`.agents/elephant/profiles/*.yaml` children.
Every external opaque ID in the workspace document—including provider
bindings and product story/knowledge references—must be represented by a
typed `LocalDocumentSlot` bound to exactly one approved stable-key operation,
even when discovery already observed an ID. Raw strings or a caller's
`verified: true` assertion are not authority. Materialize each slot only from
that operation's current unique read-back record, then validate and hash the
final canonical bytes. If the provider returns a different ID with the same
approved semantics, the new verified ID is written; a stale pre-observed ID is
never retained. The reserved `urn:elephant:setup-slot:` namespace is template
syntax, never a valid provider external ID; any read-back ID in that namespace
blocks readiness, and every approved slot must be structurally resolved even
when the candidate body is byte-identical to preflight.

Preserve unrelated local content,
verify the approved prior state, and complete the Darwin/Linux POSIX native
atomic preflight before the first external mutation. Keep writer-side
revalidation as a TOCTOU defense. The repository writer holds the preflighted
root descriptor and device/inode identity through the final commit; rebinding
the lexical repository path cannot transfer approval to a different tree.
Cancellation or any `BaseException` after local preflight closes that retained
descriptor and discards the execution-owned receipt before propagating.
The writer preflights the complete approved template before any adapter call;
slot-backed documents are then materialized from read-only unique read-back
before any external mutation. When an exact-rerun manifest already carries the
approved final bytes, that first local preflight proves the no-op before those
read-backs and performs no mutating capability probe, stage, or commit.
Descriptor ownership transfers to the receipt before publication, receipt
discard is identity-specific and idempotent, and interruption after publication
or while replacing an earlier same-owner receipt cannot leak either descriptor,
leave a closed descriptor registered, or mask the original cancellation.
The receipt binds the complete approved local operation and template payload;
commit may add the exact final byte hash and may change document content only by
replacing every typed slot scalar. Any other schema-valid body substitution is
rejected before staging.
Before the switch it also proves that the candidate stage's name still refers
to the descriptor and final fingerprint that were constructed. A failed final
attestation restores the approved prior container (or approved absence) while
retaining an unexpected tree as non-authoritative evidence. Use that atomic
local transaction, then load and revalidate every written registry/profile
against the canonical schemas.

Every staged file is first written to a new exclusive random sibling, fsynced,
and attested by descriptor, path identity, and single-link count before a
descriptor-relative rename installs it. The writer never opens an existing
target with truncation, so replacing a staged target cannot truncate a
hard-linked inode outside the staged container.

A successful replacement may retain the displaced prior `.agents` container as
an identity-attested sibling named `.agents.setup-stage-*`. The active `.agents`
container remains the sole workspace authority. The retained stage is
non-authoritative recovery evidence reported as `local.container.recovery` with
`cleanup_pending`; that disposition is nonblocking and does not make a verified
setup unready. Its attested fingerprint plus device/inode and path identity are
evidence, but neither its name nor its presence grants deletion authority.
Never auto-delete it, treat it as a second configuration source, or synthesize a
cleanup operation outside separately approved future authority.

### 9. Rerun as a no-write diff

Repeat discovery and build a fresh manifest. Display exact reuse/create/manual/
verify/round-trip/local differences and its new fingerprint. An unchanged
workspace produces no mutations, including no disposable create/bind/unbind/
delete cycle. This no-op classification requires exact observed local byte
fingerprints and is revalidated before provider reads. Missing non-semantic projections may be
proposed for repair, but a rename, move, merge, deletion, duplicate authority,
or other semantic change returns to the owner decision session.

### 10. Declare readiness across all selected providers

Readiness requires all selected logical providers to pass their complete
runtime capability contracts and all blocking setup evidence to pass read-back,
round-trip cleanup, absence verification, local write, and local schema
validation. Administrative handoffs can complete setup prerequisites; they
cannot substitute for runtime capabilities. Identity-attested
`cleanup_pending` recovery evidence is explicitly nonblocking because active
`.agents` is the verified authority. If any blocking condition fails, report
the exact diagnostic and evidence and leave readiness false.

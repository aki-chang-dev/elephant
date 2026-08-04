---
name: setup-workspace
description: Use when a repository needs Elephant v3 workspace discovery, a product/domain topology proposal, provider diagnostics, or an approved idempotent setup dry run. Triggers on "/setup-workspace", "set up Elephant workspace", "analyze products and engineering domains", "provision Linear and Notion workspace structure".
---

# Setup Workspace

## Overview

Discover and propose an Elephant v3 workspace, then execute only the exact approved setup manifest. One fingerprinted manifest is the sole write authority.

Read `../../references/workspace/setup-workspace.md` completely before acting. It is the canonical protocol and links the four required workspace contracts.

The executable API is bundled in this plugin as `elephant_runtime.workspace_setup`. Use its public `fingerprint_local_container()` and `RepositoryLocalWriter` boundaries; checkout-only `scripts.workspace_setup` imports are compatibility forwarding, not a second runtime. Reject a checkout forwarder whose preloaded canonical module resolves outside the current checkout's plugin root.

## Boundary

Phase 2 certifies provider-neutral orchestration with fake adapters only. Concrete Linear and Notion adapters are not certified yet. If the selected setup needs either real provider, report the exact Phase 3/4 boundary and stop before provider or local mutation. Local mutation is supported only on Darwin/Linux POSIX hosts whose target filesystem provides the required native atomic rename primitive; preflight that capability before any external mutation and emit `platform_unsupported` if it is absent. Keep read-only discovery and dry-run usable where practical. Never invent a connector call, substitute Git, or treat MCP/connector presence as capability.

## Procedure

1. **Discover read-only.** Inventory the repository through one identity-bound root descriptor, external structures, and the connector's actual platform-supported, exposed, permitted, and configured operations. Report a lexical root-path identity change without mixing evidence from two repositories. Do not create a mapping file, checklist, draft config, or external object.
2. **Propose independent dimensions.** Present product identities separately from engineering domains. Keep provenance, confidence, conflicts, and owner questions explicit; never promote an app, package, directory, team, or deployment unit to a product without product evidence and owner confirmation. Aggregate repository and external display alternatives plus all provenance into one conflict for a shared normalized product key.
3. **Run one owner decision session.** Resolve all semantic questions, regenerate the complete no-write manifest from those answers, then display products, domains, provider selections, reuse/create/manual structures, conflicts, exact diagnostics, local file diff, disposable cleanup plan, and the complete manifest fingerprint. Approval must name that displayed fingerprint. This is the only human checkpoint. Treat the confirmed registry and profile payloads as the sole semantic source of canonical local YAML; optional rendered templates may supply typed slots only when every path and body exactly matches that derived projection. For reruns, provide an exact read-only byte SHA-256 or proven absence for every setup output through `observed_local_fingerprints`; only an exact external REUSE/VERIFY plus local-byte match may omit round trips.
4. **Apply the approved manifest.** Accept only `ApprovedManifest` produced from that exact complete fingerprint. Use stable external keys, idempotent reuse/create, and read every mutation back. Represent every external binding/reference in local output with a typed `LocalDocumentSlot` bound to its approved stable-key operation, including already observed IDs; raw opaque-ID strings and `verified: true` assertions are not authority. Materialize only the current unique read-back ID, reject the reserved `urn:elephant:setup-slot:` namespace as an external ID, require every slot to resolve structurally, and bind the canonical final byte hash into readiness evidence. A changed or regenerated manifest requires fresh fingerprint approval; never carry authority forward from an earlier dry run.
5. **Verify and finish.** An absent `MANUAL` target returns its handoff with no local batch. After out-of-band completion, call `apply_setup()` again with the exact same `ApprovedManifest` and fingerprint, pass the returned token as `resume_handoff`, and supply a distinct nonblank execution ID for this new attempt. The handoff binds the prior execution ID, approval fingerprint, exact operation, semantics, instructions, and the exact ordered prefix of earlier MANUAL prerequisites already verified by apply; each prior completion is re-read on every later attempt. Changing the attempt ID without that token grants no continuation authority. One stable-key match with the approved fingerprint must pass read-back and a guarded uniqueness re-query before `manual_completed` resumes work without another owner checkpoint. Duplicate, mismatch, missing prior completion, or read failure stops; never regenerate or transfer approval. For each approved disposable round trip on a changing setup, stable-key the relationship, reuse an exact interrupted-attempt relationship, prove its unique read-back, unbind it, and verify absence by relationship ID and key before deleting the disposable record and verifying record absence. A fully unchanged rerun emits and executes no round trip. Then write and revalidate local config last.
6. **Interpret local evidence.** Active `.agents` is the only authority. Hold the preflighted repository-root identity through commit and attest the candidate descriptor and fingerprint immediately before switching. Transfer descriptor ownership before publishing an execution receipt; discard it identity-specifically and idempotently on cancellation or any `BaseException`, including interruption while replacing a same-owner receipt, then propagate non-`Exception` cancellation unchanged. Bind the complete template payload in local preflight before adapter calls and permit commit-time body changes only for structurally validated typed-slot scalar materialization plus its exact byte hash. Resolve slot-backed final bytes by read-only unique read-back after that local preflight and before external mutation; an exact rerun must skip every provider mutation, mutating local probe, stage, and commit, and a stale no-op observation must stop before adapter calls. Stage each changed file through a new exclusive single-link sibling and rename it into place without truncating an existing target. If final attestation fails, restore the approved prior container or approved absence and retain the unexpected tree as non-authoritative evidence. An identity-attested retained `.agents.setup-stage-*` with `cleanup_pending` is non-authoritative and nonblocking. Never auto-delete it or invent cleanup authority from its name.
7. **Rerun read-only.** Show the resulting diff. Do not semantically rename, move, merge, or delete user-owned structures. Declare readiness only when every selected logical provider passes all runtime requirements.

Phase 2 guarantees complete old-or-new local visibility across process death, but same-approval retry after death immediately following the atomic switch remains deferred to Phase 5. Do not claim that crash-resume window is supported.

## Diagnostics

Emit the first missing layer for each capability using exactly one of `platform_unsupported`, `connector_capability_missing`, `permission_missing`, or `configuration_missing`. A one-time manual handoff is valid only for an administrative setup operation and still requires read-back. Any missing runtime capability blocks readiness; it never becomes a manual runtime fallback.

## Stop conditions

- Any local or external write is proposed before exact fingerprint approval.
- The approved fingerprint does not match the complete regenerated manifest.
- A selected real provider lacks a certified adapter or any runtime capability.
- A mutation cannot be read back, or a disposable record cannot be proven absent.
- Manual continuation omits or changes the returned `resume_handoff`, uses a different manifest or approval fingerprint, reuses the earlier attempt's execution ID, or its exact stable-key/fingerprint/read-back verification fails. A distinct nonblank execution ID alone grants no continuation authority.
- The local host is not Darwin/Linux POSIX, the target filesystem lacks the native atomic rename primitive, or that capability was not preflighted before external mutation.
- A rerun encounters semantic drift, ambiguous authority, or destructive work outside the approved manifest.

---
name: setup-workspace
description: Use when a repository needs Elephant v3 workspace discovery, a product/domain topology proposal, provider diagnostics, or an approved idempotent setup dry run. Triggers on "/setup-workspace", "set up Elephant workspace", "analyze products and engineering domains", "provision Linear and Notion workspace structure".
---

# Setup Workspace

## Overview

Discover and propose an Elephant v3 workspace, then execute only the exact approved setup manifest. One fingerprinted manifest is the sole write authority.

Read `../../references/workspace/setup-workspace.md` completely before acting. It is the canonical protocol and links the four required workspace contracts.

## Boundary

Phase 2 certifies provider-neutral orchestration with fake adapters only. Concrete Linear and Notion adapters are not certified yet. If the selected setup needs either real provider, report the exact Phase 3/4 boundary and stop before provider or local mutation. Never invent a connector call, substitute Git, or treat MCP/connector presence as capability.

## Procedure

1. **Discover read-only.** Inventory the repository, external structures, and the connector's actual platform-supported, exposed, permitted, and configured operations. Do not create a mapping file, checklist, draft config, or external object.
2. **Propose independent dimensions.** Present product identities separately from engineering domains. Keep provenance, confidence, conflicts, and owner questions explicit; never promote an app, package, directory, team, or deployment unit to a product without product evidence and owner confirmation.
3. **Run one owner decision session.** Resolve all semantic questions, regenerate the complete no-write manifest from those answers, then display products, domains, provider selections, reuse/create/manual structures, conflicts, exact diagnostics, local file diff, disposable cleanup plan, and the complete manifest fingerprint. Approval must name that displayed fingerprint. This is the only human checkpoint.
4. **Apply the approved manifest.** Accept only `ApprovedManifest` produced from that exact complete fingerprint. Use stable external keys, idempotent reuse/create, and read every mutation back. A changed or regenerated manifest requires fresh fingerprint approval; never carry authority forward from an earlier dry run.
5. **Verify and finish.** An absent `MANUAL` target returns its handoff with no local batch. After out-of-band completion, call `apply_setup()` again with the exact same `ApprovedManifest` and fingerprint. Supply a nonblank execution ID for this new attempt; it scopes that attempt's disposable and local transaction ownership, but changing it does not change or transfer owner approval. One stable-key match with the approved fingerprint must pass read-back and a guarded uniqueness re-query before `manual_completed` resumes work without another owner checkpoint. Duplicate, mismatch, or read failure stops; never regenerate or transfer approval. Then complete disposable deletion/absence proof and write and revalidate local config last.
6. **Interpret local evidence.** Active `.agents` is the only authority. An identity-attested retained `.agents.setup-stage-*` with `cleanup_pending` is non-authoritative, nonblocking recovery evidence. Never auto-delete it or invent cleanup authority from its name.
7. **Rerun read-only.** Show the resulting diff. Do not semantically rename, move, merge, or delete user-owned structures. Declare readiness only when every selected logical provider passes all runtime requirements.

## Diagnostics

Emit the first missing layer for each capability using exactly one of `platform_unsupported`, `connector_capability_missing`, `permission_missing`, or `configuration_missing`. A one-time manual handoff is valid only for an administrative setup operation and still requires read-back. Any missing runtime capability blocks readiness; it never becomes a manual runtime fallback.

## Stop conditions

- Any local or external write is proposed before exact fingerprint approval.
- The approved fingerprint does not match the complete regenerated manifest.
- A selected real provider lacks a certified adapter or any runtime capability.
- A mutation cannot be read back, or a disposable record cannot be proven absent.
- Manual continuation uses a different manifest or approval fingerprint, or its exact stable-key/fingerprint/read-back verification fails. A different nonblank execution ID alone is not a stop condition.
- A rerun encounters semantic drift, ambiguous authority, or destructive work outside the approved manifest.

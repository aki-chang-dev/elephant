# Elephant host and packaging smoke tests

These cases verify the same packaged workflow in Claude Code and Codex. They store outcome
categories only—never connector payloads, credentials, or external-object dumps.

## Install and inventory

Install Elephant from its marketplace in each host, start a new session, and inspect the available
skills. Both hosts must expose exactly the seven current workflow skills: `kickoff`,
`author-product-spec`, `decompose-roadmap`, `setup-workspace`, `shape-story`,
`author-technical-contract`, and `ship-story`. No `init-profile` entry may remain.

## Single Product setup

Given one repository Product plus authenticated Linear and Notion integrations, run setup through
the proposal boundary without approving writes. It must propose a label-free Product scope, mapped
Notion and Linear entry points, repository domains, and one final workspace-map write. It must not
propose databases, provider manifests, certification, or a delivery profile.

## Multi Product setup

Given two repository Products, setup must distinguish each Product from its engineering domains
and require Product classification on every managed Linear object. Issue labels exist from setup;
Project and Initiative label namespaces activate only for Products with existing objects or an
approved first write. Ambiguous existing objects stop the affected operation instead of triggering
a global scan or guessed match.

### Codex CLI profile

Run with semantic Linear/Notion connectors and no browser. Make at least one required
administrative create unavailable while keeping its collection semantically readable. The proposal
must classify that operation as **Owner setup**, execute supported approved writes, emit one exact
checklist, and resume through semantic read-back without requesting opaque IDs. Rerun after the
owner creates the object and verify reuse, stable-ID capture, no duplicate, and config-last
behavior. An unused Project or Initiative label namespace does not block setup even when its create
or read operation is unavailable.

### Browser-capable profile

Run the same target structure where an authenticated browser can perform the connector gap. The
same proposal, same Product protocol, and same final workspace map must be produced; only the
executor differs.

### Unverifiable profile

Remove both the write path and semantic read-back for one currently required Product-label
namespace: an Issue namespace, or a Project/Initiative namespace required by existing inventory.
Setup must classify the operation as **Unavailable** before approval and must not publish a
workspace map that runtime workflows cannot consume.

## Missing integrations

If Linear is unavailable, planning work stops with the missing authoritative source. If Notion is
unavailable and no durable meaning needs to be read or written, the Story may remain Linear-only;
otherwise it stops. Missing native Linear-GitHub convenience falls back to an ordinary verified PR
link. No missing integration causes Elephant to invent a local replacement store.

## Host-instruction conflict

Repository instructions continue to control commands, verification, worktrees, and commit/PR
conventions. Elephant controls only its product coordination flow. A real conflict is reported with
the exact instructions; host identity is never used to silently choose different product behavior.

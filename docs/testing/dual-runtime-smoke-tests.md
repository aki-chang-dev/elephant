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
and require Product classification on Linear Issues, Projects, and Initiatives. Ambiguous existing
objects stop the affected operation instead of triggering a global scan or guessed match.

## Missing integrations

If Linear is unavailable, planning work stops with the missing authoritative source. If Notion is
unavailable and no durable meaning needs to be read or written, the Story may remain Linear-only;
otherwise it stops. Missing native Linear-GitHub convenience falls back to an ordinary verified PR
link. No missing integration causes Elephant to invent a local replacement store.

## Host-instruction conflict

Repository instructions continue to control commands, verification, worktrees, and commit/PR
conventions. Elephant controls only its product coordination flow. A real conflict is reported with
the exact instructions; host identity is never used to silently choose different product behavior.

# Provider capability contracts

Host tools are adapters. The canonical operations below are runtime-neutral and
must not be renamed to match a host API. A provider is ready only when every
capability required by its selected logical store is supported by the platform,
exposed by its connector, permitted to the current actor, and configured for
this workspace.

Each operation must accept stable external keys for its target and return
evidence that can be read back. Keys are opaque: discover and verify them; do
not guess them. Mutating requests also return the persisted external key and a
read-after-write representation or version/fingerprint that verifies the
mutation.

## Story runtime

`STORY_RUNTIME_CAPABILITIES` is:

| Capability | Request evidence | Response evidence |
| --- | --- | --- |
| `create_story` | stable product and parent keys; story payload | created story key and read-back story |
| `read_story` | stable story key | story key, fields, and version |
| `update_story_status` | story key, intended human status, expected version | read-back status and version |
| `write_product_recap` | story key and recap content | recap key or story field read-back |
| `create_child_story` | parent story key and child payload | child key and parent relation read-back |
| `link_story_relation` | stable keys for both stories and relation | reciprocal relation read-back |
| `bind_product_contract` | story key and contract key | binding read-back from story and contract |
| `read_checkpoint` | story key | opaque checkpoint and its version |
| `write_checkpoint` | story key, opaque checkpoint, expected version | verified checkpoint read-back |
| `attach_delivery_evidence` | story key and immutable delivery evidence key | attachment read-back |

## Product knowledge runtime

`KNOWLEDGE_RUNTIME_CAPABILITIES` is:

| Capability | Request evidence | Response evidence |
| --- | --- | --- |
| `read_knowledge` | stable knowledge key | knowledge record, version, and provenance |
| `query_knowledge` | product key and query predicate | matching stable keys and query basis |
| `create_knowledge` | product key, content, and provenance | created key and read-back record |
| `update_knowledge` | knowledge key, revision, expected version | updated record and version |
| `supersede_knowledge` | old and successor stable keys | reciprocal supersession read-back |
| `link_knowledge_relation` | stable keys for both records and relation | reciprocal relation read-back |

## Product contract runtime

`CONTRACT_RUNTIME_CAPABILITIES` is:

| Capability | Request evidence | Response evidence |
| --- | --- | --- |
| `create_contract_draft` | product key and draft content | draft key and read-back draft |
| `read_contract` | stable contract key | contract content, state, and fingerprint |
| `update_contract_draft` | draft key, change, expected version | updated draft and version |
| `approve_contract` | draft key, approval authority, expected version | approved state and fingerprint read-back |
| `create_contract_successor` | active contract key and successor draft | successor key and relation read-back |
| `resolve_active_contract` | product key | one active contract key and state evidence |
| `verify_contract_fingerprint` | contract key and expected fingerprint | verified fingerprint result |
| `verify_story_binding` | story key and contract key | binding read-back from both records |

## Delivery workspace runtime

`DELIVERY_RUNTIME_CAPABILITIES` is:

| Capability | Request evidence | Response evidence |
| --- | --- | --- |
| `persist_technical_contract` | story key and technical contract content | stable artifact key and read-back content |
| `persist_plan` | story key and approved plan content | stable artifact key and read-back plan |
| `bind_delivery_branch` | story key and immutable branch identifier | binding read-back |
| `record_conformance` | story key and conformance evidence | stable record key and read-back evidence |
| `promote_knowledge` | source evidence and knowledge destination key | promoted key and provenance read-back |
| `remove_transient_artifacts` | stable artifact keys and cleanup authority | verified absence or retained-record evidence |

## Preflight diagnostics

For every required capability, preflight evaluates these layers in order:

1. `platform_unsupported`
2. `connector_capability_missing`
3. `permission_missing`
4. `configuration_missing`

It reports the first missing layer for each capability, in capability-name sort
order. Missing runtime capabilities block provider readiness. Selected providers
never fall back to another provider.

Administrative setup operations may produce a one-time manual handoff and
read-back check. They must not be represented as silent runtime fallback.

## Mutation and repair authority

Provider mutations are read-only until the current phase explicitly authorizes
that exact authority. Non-semantic repair is limited to a recap, reciprocal
links, verified checkpoints, and timed-out writes, with read-back verification.

Semantic drift includes product assignment, approved content, human status, or
duplicate authority. It requires a stop rather than an automated repair.

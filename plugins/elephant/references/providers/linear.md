# Linear host execution protocol

Use this reference only for the selected Linear story provider. It is an execution protocol, not authority to mutate: setup still requires its approved manifest, and every provider mutation follows the story-provider contract.

## Read-only discovery

Call these exact tools before proposing a binding:

- `mcp__codex_apps__linear_list_teams`, then `mcp__codex_apps__linear_get_team` for each candidate; `mcp__codex_apps__linear_get_user` proves current-team membership.
- `mcp__codex_apps__linear_list_issue_statuses` for the selected team. Preserve opaque IDs, names, and types for `Backlog`/`backlog`, `Shaping`/`unstarted`, `Ready`/`unstarted`, `In Progress`/`started`, `Done`/`completed`, and `Canceled`/`canceled`.
- `mcp__codex_apps__linear_list_issue_labels` and the Product and Kind groups. Product-facing needs one Product label plus `product-facing`; engineering-only needs `engineering-only` and no Product label.
- `mcp__codex_apps__linear_list_issues` followed by `mcp__codex_apps__linear_get_issue` for exact-marker evidence.

Decode only these normalized response boundaries: team/label/issue/comment/diff pages are `{teams|labels|issues|comments|diffs: [...], hasNextPage: bool, cursor: string|null}`; statuses are a bare list; user membership is `{id, teams: [...]}`. A detailed issue contains `id`, `identifier`, `teamId`, `team`, `status`, `statusType`, `labels`, `priority`, `attachments`, `stateHistory`, and complete `relations` (`blocks`, `blockedBy`, `relatedTo`, `duplicateOf`). Read every page before deciding that a marker or label is absent; reject duplicate opaque IDs, repeated cursors, duplicate stable markers, and truncated relation evidence. Preserve opaque IDs and URLs exactly. Do not infer a workspace UUID: record a verified workspace locator separately from the team UUID. The current connector has no direct workspace UUID lookup.

Classify the first missing layer only: `platform_unsupported`, `connector_capability_missing`, `permission_missing`, then `configuration_missing`. Tool visibility is not permission. If list/read works but required statuses or Product/Kind labels are absent, report `configuration_missing`. Missing team/status administration is actionable, nonblocking `connector_capability_missing` setup work; after a human creates it, resume with the same approval and exact list/get read-back. Never claim team/status creation, issue deletion, or workspace UUID lookup is exposed.

## Provider calls and evidence

The complete tool vocabulary is:

| Purpose | Exact tools |
| --- | --- |
| Story lookup/create/update/relation/recap/contract | `mcp__codex_apps__linear_list_issues`, `mcp__codex_apps__linear_save_issue`, `mcp__codex_apps__linear_get_issue` |
| Status and labels | `mcp__codex_apps__linear_list_issue_statuses`, `mcp__codex_apps__linear_list_issue_labels`, `mcp__codex_apps__linear_create_issue_label` |
| Team/membership discovery | `mcp__codex_apps__linear_list_teams`, `mcp__codex_apps__linear_get_team`, `mcp__codex_apps__linear_get_user` |
| Checkpoint attachment | `mcp__codex_apps__linear_prepare_attachment_upload`, `host_raw_signed_put`, `mcp__codex_apps__linear_create_attachment_from_upload`, `mcp__codex_apps__linear_get_attachment`, `mcp__codex_apps__linear_delete_attachment`, `mcp__codex_apps__linear_get_issue` |
| Delivery comment | `mcp__codex_apps__linear_list_comments`, `mcp__codex_apps__linear_save_comment`, `mcp__codex_apps__linear_delete_comment`, `mcp__codex_apps__linear_get_issue` |
| Native GitHub verification | `mcp__codex_apps__linear_list_diffs`, `mcp__codex_apps__linear_get_diff` |

For every operation, preflight its four layers, lookup the exact stable key, issue one mutation, retain only its safe caller-persistable replay token/receipt, and perform exact read-back. A timeout means read back; never blindly retry an append-only relation, attachment, or link. A duplicate key, changed configured team/Product/Kind authority, invalid status advance, contradictory receipt, or failed read-back stops.

An issue description contains only the concise canonical Product Recap and its footer:

```text
---
Elephant story key: `elephant-story/v1/<64 lowercase hex>`
Elephant recap SHA-256: `<64 lowercase hex>`
```

The checkpoint is canonical UTF-8 JSON with schema `elephant.linear-checkpoint/v1`, exact `story_key`, `issue_id`, phase, positive sequence, contract page ID/fingerprint, delivery fields, and predecessor SHA-256. Its filename is `elephant-checkpoint-<story-key-sha256>-<sequence>.json`. Do not put contracts, technical plans, checkpoint JSON, or internal progress in the issue body.

## Attachment and sanitizer boundary

For a checkpoint: prepare upload, perform `host_raw_signed_put` using the returned URL and headers verbatim, finalize, then `GET_ATTACHMENT`, decode it through the installed `HostAttachmentContentReader`, and verify the returned bytes' SHA-256 before treating the attachment as authoritative. The reader accepts exactly one host-attested MCP `resource` content block whose base64 `blob` and `_meta.linear_attachment_id` match the requested attachment ID; it rejects every other untyped response shape without exposing payload content. Task 6 is the real connector-shape certification gate.

Never place OAuth material, signed URLs, raw attachment bytes, base64 attachment content, or raw connector payloads in exceptions, transcripts, comments, or Markdown. Preserve only sanitized diagnostics, redacted IDs, and SHA-256 evidence. Prefer structured connector codes over parsing English error prose.

## Administration and certification cleanup

Manual setup for missing `Shaping`/`Ready`, team, or workflow status says exactly what the owner must create and which list/get evidence to return. It is one approved handoff, not a runtime fallback. Resume with the original approved manifest, exact handoff token, a new execution ID, and exact read-back.

For certification, use one `elephant-sandbox/<uuid>` marker. Lookup before every mutation and restore/delete reversible relations, comments, and attachments with read-back. Comment cleanup is `mcp__codex_apps__linear_delete_comment` with exactly the comment `id`, then `mcp__codex_apps__linear_list_comments` proving absence. This is a sandbox-cleanup capability, not a normal delivery-evidence requirement. The connector cannot delete issues: move the sandbox issue to `Canceled` and retain it titled `[Elephant provider certification — cleaned] <marker suffix>`. A transcript must contain only redacted IDs, semantic hashes, exact tool/phase order, and cleanup absence evidence.

# Linear provider sandbox certification

This is the evidence template for the Phase 3 Linear provider certification.
It documents a host-executed sandbox run; neither the runtime model nor this
document invokes Linear.

## Boundaries

- Use a new `elephant-sandbox/<uuid>` marker and one verified sandbox team.
- Perform the read-only capability inventory before the first mutation.
- Never change an onboarding issue's body, status, or labels. If it is an
  anchor, first record its prior relation snapshot and restore it exactly.
- Create no team, workflow status, or label. The connector does not expose
  issue deletion, so retain the sole certification issue as Canceled with the
  exact title `[Elephant provider certification — cleaned] <marker suffix>`.
- Do not put OAuth data, tokens, signed URLs or headers, raw bytes, base64,
  raw responses, or timestamps used as authority in tracked evidence.
- The live `GET_ATTACHMENT` probe certified exactly one MCP `text` block whose
  text is strict unpadded base64 of the known raw bytes. The installed reader
  receives the expected attachment identity separately, returns only decoded
  bytes, and sanitizes malformed/ambiguous responses without retaining the
  encoded text or connector exception prose.

## Ignored local run report

Before the run, fill the ignored
`.superpowers/sdd/2026-08-04-linear-provider/task-6-local-report.md` with:

- unique marker and marker suffix;
- sandbox team and Todo, In Progress, and Canceled status IDs;
- product/kind label IDs and their pre-mutation semantic snapshots;
- each optional parent/relation anchor and its complete prior relation snapshot;
- canonical checkpoint byte count and SHA-256; and
- whether native GitHub diff returns an observed result or the exact
  `configuration_missing` / `connector_capability_missing` diagnostic.

The report is a working log, not certification evidence. Keep it ignored and
redact durable IDs before transferring only the permitted values below.

## Tracked certification evidence

The redacted [sandbox transcript](linear-provider-sandbox.json) was captured
after a completed host run. It records marker
`elephant-sandbox/e3232c89-f155-4439-b5be-3c820f4c9b7e`, the retained issue as
`redacted:issue-1`, and a checkpoint attachment as
`redacted:attachment-1`. The checkpoint SHA-256 is
`2cda18721598e5826f1d0a7d687913168597c49aa8dbe83aecc4d7a8183f63e0` at 454
bytes. Its closed schema has no additional fields. The `cleanup` object
contains exactly two redacted, empty/restored anchor snapshots and the three
owned attachment identities (checkpoint, contract link, and PR link).

```json
{
  "schema": "elephant.linear-sandbox/v1",
  "marker": "elephant-sandbox/<uuid>",
  "capabilities": {
    "read_only": ["<exact capability tools in validator order>"],
    "sandbox_cleanup": ["<exact cleanup tools in validator order>"]
  },
  "checkpoint": {
    "id": "redacted:<attachment-id>",
    "sha256": "<64 lowercase hex>",
    "size": 1
  },
  "cleanup": {
    "anchors": {
      "anchor_1": {"id": "redacted:<anchor-id>", "relations": {"blocks": 0, "blocked_by": 0, "related_to": 0, "duplicate_of": 0}, "restored": true},
      "anchor_2": {"id": "redacted:<anchor-id>", "relations": {"blocks": 0, "blocked_by": 0, "related_to": 0, "duplicate_of": 0}, "restored": true}
    },
    "attachments": {
      "checkpoint": "redacted:<attachment-id>",
      "contract_link": "redacted:<attachment-id>",
      "pr_link": "redacted:<attachment-id>"
    }
  },
  "calls": ["<exact tool/phase/operation sequence from the validator>"]
}
```

Each call is a minimal object containing `tool`, `phase`, and `operation`.
Only the validator-permitted call results are retained: exact lookup counts,
checkpoint `id`/`sha256`/`size`, comment absence counts, the native-diff
diagnostic code, relation-removal's empty source/anchor restoration snapshot,
owned attachment absence, and the final cleaned snapshot. The comment delete
call has exactly one redacted `id` argument. Each of the three attachment
deletes has exactly its owned redacted `id` argument; the checkpoint delete is
bound to `checkpoint.id`. Cleanup proof is call-derived: the transcript
includes the owned comment delete plus zero-match list, all three attachment
deletes plus absence/read-back, restored relation removal/read-back, and final
cancellation. The exact final title suffix is the marker UUID's final 12
characters; labels, parent, attachments, comments, and relation counts must
all be empty.

## Durable certification record

The completed run established the following durable, redacted evidence:

| Evidence | Value to record |
| --- | --- |
| Capability inventory | Exact observed tool names, in order |
| Sandbox identity | `redacted:issue-1`, `redacted:attachment-1`, `redacted:comment-1`; suffix `3c820f4c9b7e` |
| Semantic evidence | Product recap and contract-link were written/read back; exact label replacement/read-back and parent/relation add/read/remove completed |
| Checkpoint | `2cda18721598e5826f1d0a7d687913168597c49aa8dbe83aecc4d7a8183f63e0`, 454 bytes |
| Delivery evidence | Comment create/read/update/delete and zero-match absence completed |
| GitHub evidence | Exact `configuration_missing` native-diff diagnostic |
| Cleanup | Both anchor relations restored; no owned relations/comments/checkpoint attachments; labels `[]`; parent `null`; final issue Canceled and titled `[Elephant provider certification — cleaned] 3c820f4c9b7e` |
| Validator | `Linear provider sandbox certification passed.` |

Validate the tracked JSON locally without network access:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate-linear-provider.py \
  docs/testing/linear-provider-sandbox.json
```

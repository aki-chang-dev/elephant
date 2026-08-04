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

## Tracked transcript template

Write `.superpowers/sdd/2026-08-04-linear-provider/linear-sandbox-transcript.json`
only after cleanup. It must have this exact closed shape (with no additional
fields):

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
  "calls": ["<exact tool/phase/operation sequence from the validator>"]
}
```

Each call is a minimal object containing `tool`, `phase`, and `operation`.
Only the validator-permitted call results are retained: exact lookup counts,
checkpoint `id`/`sha256`/`size`, comment absence counts, the native-diff
diagnostic code, and the final issue's redacted `id`, cleaned title, and
`Canceled` status. The comment delete call has exactly one redacted `id`
argument. Cleanup proof is call-derived: the transcript includes the owned
comment delete plus zero-match list, attachment delete plus zero-match issue
read-back, restored relation removal/read-back, and final cancellation.

## Durable certification record

After the transcript passes, record only this redacted evidence in the task or
review note:

| Evidence | Value to record |
| --- | --- |
| Capability inventory | Exact observed tool names, in order |
| Sandbox identity | Redacted issue/attachment/comment IDs and marker suffix |
| Semantic evidence | Product recap and contract-link fingerprints; label/status names; relation reciprocity/read-back result |
| Checkpoint | SHA-256 and byte count, not bytes or upload material |
| Delivery evidence | Create/read/update/delete result and zero-match absence |
| GitHub evidence | Native diff result or exact configuration diagnostic |
| Cleanup | Restored anchors; no owned relations/comments/checkpoint attachments; final cleaned Canceled issue |
| Validator | `Linear provider sandbox certification passed.` |

Validate the tracked JSON locally without network access:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate-linear-provider.py \
  .superpowers/sdd/2026-08-04-linear-provider/linear-sandbox-transcript.json
```

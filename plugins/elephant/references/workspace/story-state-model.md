# Story state model

Linear human delivery state and the opaque Elephant machine checkpoint are
separate authorities. Human status communicates product delivery to people;
the checkpoint records exact orchestration progress and is not a substitute
for that status.

## Human delivery state

The compact Linear flow is:

```text
Backlog → Shaping → Ready → In Progress → Done
                                      ↘ Canceled
```

The full allowed-transition table is deliberately explicit. Any transition
not listed is prohibited in the normal delivery model, including every
transition out of `Done` and `Canceled`.

| Current status | Allowed target status |
| --- | --- |
| `Backlog` | `Shaping` |
| `Shaping` | `Ready`, `Backlog`, `Canceled` |
| `Ready` | `In Progress`, `Shaping`, `Backlog`, `Canceled` |
| `In Progress` | `Shaping`, `Done`, `Canceled` |
| `Done` | none |
| `Canceled` | none |

`needs_product_decision` returns the human issue to `Shaping`; it does not
introduce an engineering-specific human delivery status.

## Product dispositions

Product disposition is an explicit decision, with the following required
human-status result:

| Disposition | Human status | Required behavior |
| --- | --- | --- |
| `approved` | `Ready` | The approved Product Contract can proceed to delivery preparation. |
| `split` | `Canceled` | Create the child stories, then close the original with the split disposition. |
| `deferred` | `Backlog` | Record the reconsideration condition before returning the story to the backlog. |
| `rejected` | `Canceled` | Close the story without delivery. |

## Machine checkpoint phases

The machine checkpoint is opaque integration metadata, but its phase
vocabulary is fixed:

| Phase | Meaning |
| --- | --- |
| `contract_pending` | Story exists but contract creation or reciprocal binding is incomplete. |
| `shaping` | Product Contract shaping is in progress. |
| `ready` | Approved contract and readiness evidence are verified. |
| `technical` | Technical Contract and implementation planning are in progress. |
| `implementing` | Delivery branch implementation is in progress. |
| `conformance` | Implementation and product-contract conformance are being verified. |
| `closeout` | Evidence, promotion, and transient-artifact cleanup are in progress. |
| `done` | Delivery closeout has completed. |
| `needs_product_decision` | Technical work found product ambiguity; return the human issue to `Shaping`. |

A human status cannot prove a machine checkpoint: a status can be moved
without the required read-back evidence. Conversely, a machine checkpoint
cannot replace human delivery state: its metadata is not a product-facing
workflow state.

## Drift repair authority

Elephant may repair only non-semantic projections after read-back
verification. Semantic drift stops the workflow for owner resolution.

| Drift kind | Action |
| --- | --- |
| `stale_recap` | `auto_repair` |
| `missing_reciprocal_link` | `auto_repair` |
| `verified_checkpoint_lag` | `auto_repair` |
| `timed_out_write` | `auto_repair` |
| `approved_contract_changed` | `stop` |
| `product_assignment_changed` | `stop` |
| `human_status_advanced` | `stop` |
| `duplicate_authority` | `stop` |

Automatic repair never changes approved product meaning, product assignment,
human delivery state, or the authoritative object selected by an external
key.

from __future__ import annotations

from enum import Enum


class HumanStatus(str, Enum):
    BACKLOG = "Backlog"
    SHAPING = "Shaping"
    READY = "Ready"
    IN_PROGRESS = "In Progress"
    DONE = "Done"
    CANCELED = "Canceled"


class ProductDisposition(str, Enum):
    APPROVED = "approved"
    SPLIT = "split"
    DEFERRED = "deferred"
    REJECTED = "rejected"


class CheckpointPhase(str, Enum):
    CONTRACT_PENDING = "contract_pending"
    SHAPING = "shaping"
    READY = "ready"
    TECHNICAL = "technical"
    IMPLEMENTING = "implementing"
    CONFORMANCE = "conformance"
    CLOSEOUT = "closeout"
    DONE = "done"
    NEEDS_PRODUCT_DECISION = "needs_product_decision"


class DriftKind(str, Enum):
    STALE_RECAP = "stale_recap"
    MISSING_RECIPROCAL_LINK = "missing_reciprocal_link"
    VERIFIED_CHECKPOINT_LAG = "verified_checkpoint_lag"
    TIMED_OUT_WRITE = "timed_out_write"
    APPROVED_CONTRACT_CHANGED = "approved_contract_changed"
    PRODUCT_ASSIGNMENT_CHANGED = "product_assignment_changed"
    HUMAN_STATUS_ADVANCED = "human_status_advanced"
    DUPLICATE_AUTHORITY = "duplicate_authority"


class RepairAction(str, Enum):
    AUTO_REPAIR = "auto_repair"
    STOP = "stop"


_HUMAN_STATUS_TRANSITIONS = {
    HumanStatus.BACKLOG: frozenset({HumanStatus.SHAPING}),
    HumanStatus.SHAPING: frozenset({
        HumanStatus.READY,
        HumanStatus.BACKLOG,
        HumanStatus.CANCELED,
    }),
    HumanStatus.READY: frozenset({
        HumanStatus.IN_PROGRESS,
        HumanStatus.SHAPING,
        HumanStatus.BACKLOG,
        HumanStatus.CANCELED,
    }),
    HumanStatus.IN_PROGRESS: frozenset({
        HumanStatus.SHAPING,
        HumanStatus.DONE,
        HumanStatus.CANCELED,
    }),
    HumanStatus.DONE: frozenset(),
    HumanStatus.CANCELED: frozenset(),
}

_TERMINAL_STATUS_BY_DISPOSITION = {
    ProductDisposition.APPROVED: HumanStatus.READY,
    ProductDisposition.SPLIT: HumanStatus.CANCELED,
    ProductDisposition.DEFERRED: HumanStatus.BACKLOG,
    ProductDisposition.REJECTED: HumanStatus.CANCELED,
}

_REPAIR_ACTION_BY_DRIFT_KIND = {
    DriftKind.STALE_RECAP: RepairAction.AUTO_REPAIR,
    DriftKind.MISSING_RECIPROCAL_LINK: RepairAction.AUTO_REPAIR,
    DriftKind.VERIFIED_CHECKPOINT_LAG: RepairAction.AUTO_REPAIR,
    DriftKind.TIMED_OUT_WRITE: RepairAction.AUTO_REPAIR,
    DriftKind.APPROVED_CONTRACT_CHANGED: RepairAction.STOP,
    DriftKind.PRODUCT_ASSIGNMENT_CHANGED: RepairAction.STOP,
    DriftKind.HUMAN_STATUS_ADVANCED: RepairAction.STOP,
    DriftKind.DUPLICATE_AUTHORITY: RepairAction.STOP,
}


def can_transition_human_status(current: HumanStatus, target: HumanStatus) -> bool:
    """Return whether the normal delivery model permits this human-status move."""
    return target in _HUMAN_STATUS_TRANSITIONS[current]


def terminal_status_for_disposition(disposition: ProductDisposition) -> HumanStatus:
    """Return the human status required by a product disposition."""
    return _TERMINAL_STATUS_BY_DISPOSITION[disposition]


def repair_action(drift_kind: DriftKind) -> RepairAction:
    """Return whether a detected drift is safe to repair without owner input."""
    return _REPAIR_ACTION_BY_DRIFT_KIND[drift_kind]

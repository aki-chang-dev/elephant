import unittest

from scripts.workspace_core import (
    CheckpointPhase,
    DriftKind,
    HumanStatus,
    ProductDisposition,
    RepairAction,
    can_transition_human_status,
    repair_action,
    terminal_status_for_disposition,
)


class StoryStateModelTests(unittest.TestCase):
    def test_state_enums_match_the_exact_serialized_contract(self):
        cases = (
            (
                HumanStatus,
                (
                    ("BACKLOG", "Backlog"),
                    ("SHAPING", "Shaping"),
                    ("READY", "Ready"),
                    ("IN_PROGRESS", "In Progress"),
                    ("DONE", "Done"),
                    ("CANCELED", "Canceled"),
                ),
            ),
            (
                ProductDisposition,
                (
                    ("APPROVED", "approved"),
                    ("SPLIT", "split"),
                    ("DEFERRED", "deferred"),
                    ("REJECTED", "rejected"),
                ),
            ),
            (
                CheckpointPhase,
                (
                    ("CONTRACT_PENDING", "contract_pending"),
                    ("SHAPING", "shaping"),
                    ("READY", "ready"),
                    ("TECHNICAL", "technical"),
                    ("IMPLEMENTING", "implementing"),
                    ("CONFORMANCE", "conformance"),
                    ("CLOSEOUT", "closeout"),
                    ("DONE", "done"),
                    ("NEEDS_PRODUCT_DECISION", "needs_product_decision"),
                ),
            ),
            (
                DriftKind,
                (
                    ("STALE_RECAP", "stale_recap"),
                    ("MISSING_RECIPROCAL_LINK", "missing_reciprocal_link"),
                    ("VERIFIED_CHECKPOINT_LAG", "verified_checkpoint_lag"),
                    ("TIMED_OUT_WRITE", "timed_out_write"),
                    ("APPROVED_CONTRACT_CHANGED", "approved_contract_changed"),
                    ("PRODUCT_ASSIGNMENT_CHANGED", "product_assignment_changed"),
                    ("HUMAN_STATUS_ADVANCED", "human_status_advanced"),
                    ("DUPLICATE_AUTHORITY", "duplicate_authority"),
                ),
            ),
            (
                RepairAction,
                (
                    ("AUTO_REPAIR", "auto_repair"),
                    ("STOP", "stop"),
                ),
            ),
        )
        for enum_type, expected in cases:
            with self.subTest(enum_type=enum_type.__name__):
                self.assertEqual(
                    tuple((member.name, member.value) for member in enum_type),
                    expected,
                )

    def test_complete_human_transition_matrix(self):
        allowed = {
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
        self.assertEqual(frozenset(allowed), frozenset(HumanStatus))
        for current in HumanStatus:
            for target in HumanStatus:
                with self.subTest(current=current, target=target):
                    self.assertEqual(
                        can_transition_human_status(current, target),
                        target in allowed[current],
                    )

    def test_every_disposition_maps_to_its_exact_human_status(self):
        expected = {
            ProductDisposition.APPROVED: HumanStatus.READY,
            ProductDisposition.SPLIT: HumanStatus.CANCELED,
            ProductDisposition.DEFERRED: HumanStatus.BACKLOG,
            ProductDisposition.REJECTED: HumanStatus.CANCELED,
        }
        self.assertEqual(frozenset(expected), frozenset(ProductDisposition))
        for disposition, status in expected.items():
            with self.subTest(disposition=disposition):
                self.assertEqual(terminal_status_for_disposition(disposition), status)

    def test_every_drift_kind_maps_to_its_exact_repair_action(self):
        expected = {
            DriftKind.STALE_RECAP: RepairAction.AUTO_REPAIR,
            DriftKind.MISSING_RECIPROCAL_LINK: RepairAction.AUTO_REPAIR,
            DriftKind.VERIFIED_CHECKPOINT_LAG: RepairAction.AUTO_REPAIR,
            DriftKind.TIMED_OUT_WRITE: RepairAction.AUTO_REPAIR,
            DriftKind.APPROVED_CONTRACT_CHANGED: RepairAction.STOP,
            DriftKind.PRODUCT_ASSIGNMENT_CHANGED: RepairAction.STOP,
            DriftKind.HUMAN_STATUS_ADVANCED: RepairAction.STOP,
            DriftKind.DUPLICATE_AUTHORITY: RepairAction.STOP,
        }
        self.assertEqual(frozenset(expected), frozenset(DriftKind))
        for drift_kind, action in expected.items():
            with self.subTest(drift_kind=drift_kind):
                self.assertEqual(repair_action(drift_kind), action)

    def test_normal_human_delivery_flow(self):
        path = (
            HumanStatus.BACKLOG,
            HumanStatus.SHAPING,
            HumanStatus.READY,
            HumanStatus.IN_PROGRESS,
            HumanStatus.DONE,
        )
        for current, target in zip(path, path[1:]):
            self.assertTrue(can_transition_human_status(current, target))

    def test_product_decision_return_goes_back_to_shaping(self):
        self.assertTrue(
            can_transition_human_status(HumanStatus.IN_PROGRESS, HumanStatus.SHAPING)
        )

    def test_dispositions_map_to_human_status(self):
        self.assertEqual(
            terminal_status_for_disposition(ProductDisposition.DEFERRED),
            HumanStatus.BACKLOG,
        )
        self.assertEqual(
            terminal_status_for_disposition(ProductDisposition.SPLIT),
            HumanStatus.CANCELED,
        )
        self.assertEqual(
            terminal_status_for_disposition(ProductDisposition.REJECTED),
            HumanStatus.CANCELED,
        )

    def test_nonsemantic_projection_repairs_automatically(self):
        self.assertEqual(repair_action(DriftKind.STALE_RECAP), RepairAction.AUTO_REPAIR)
        self.assertEqual(
            repair_action(DriftKind.MISSING_RECIPROCAL_LINK), RepairAction.AUTO_REPAIR
        )

    def test_semantic_drift_stops(self):
        self.assertEqual(repair_action(DriftKind.APPROVED_CONTRACT_CHANGED), RepairAction.STOP)
        self.assertEqual(repair_action(DriftKind.PRODUCT_ASSIGNMENT_CHANGED), RepairAction.STOP)

import unittest

from scripts.workspace_core import (
    DriftKind,
    HumanStatus,
    ProductDisposition,
    RepairAction,
    can_transition_human_status,
    repair_action,
    terminal_status_for_disposition,
)


class StoryStateModelTests(unittest.TestCase):
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

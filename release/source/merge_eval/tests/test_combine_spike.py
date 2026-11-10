from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path

MERGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MERGE_ROOT))
combine = importlib.import_module("combine_spike")


class CombineSpikeTests(unittest.TestCase):
    def test_exactly_two_contradiction_weights_and_merged_fallback(self):
        recipes = combine.recipes()
        self.assertEqual([r["name"] for r in recipes], ["contradiction_0.25", "contradiction_0.50"])
        self.assertEqual([r["contradiction_weight"] for r in recipes], [0.25, 0.50])
        self.assertEqual([r["merged_weight"] for r in recipes], [0.75, 0.50])
        self.assertEqual([r["alpha"] for r in recipes], [0.75, 0.50])
        self.assertEqual(combine.BASELINE, "merge_alpha_0.75")

    def test_preregistration_has_original_gate_and_no_frozen_selection(self):
        prereg = combine.build_preregistration(check_outputs=False)
        self.assertEqual(prereg["gate"], combine.original_gate())
        self.assertEqual(prereg["gate"]["pooled_contradiction_task_success_delta_min"], 0.03)
        self.assertEqual(prereg["gate"]["pooled_contradiction_all_five_delta_min"], 0.05)
        self.assertEqual(prereg["gate"]["pooled_entailment_task_success_delta_min"], -0.01)
        self.assertEqual(prereg["gate"]["final_dialogue_task_accuracy_delta_min"], -0.02)
        self.assertFalse(prereg["frozen_test_used_for_selection"])
        self.assertFalse(prereg["training"])
        self.assertEqual(prereg["candidate_order"], ["merge_alpha_0.75", "contradiction_0.25", "contradiction_0.50"])
        self.assertEqual(prereg["if_both_pass"], "contradiction_0.25")
        for source in (combine.MERGED_ADAPTER, combine.CONTRADICTION_ADAPTER):
            self.assertIn(str(source), prereg["source_adapter_sha256"])

    def test_evaluation_plan_uses_existing_nonfrozen_dev_hashes(self):
        plan = combine.build_evaluation_plan(check_outputs=False)
        self.assertEqual(set(plan["datasets"]), {"semantic_dev", "v8_targeted_dev", "resolution_dev"})
        self.assertEqual(plan["candidate_order"], ["merge_alpha_0.75", "contradiction_0.25", "contradiction_0.50"])
        self.assertNotIn("frozen", json.dumps(plan["datasets"]))
        for dataset in plan["datasets"].values():
            self.assertIn("source_sha256", dataset)
            self.assertIn("labels_sha256", dataset)

    def test_raw_prediction_path_includes_evaluation_directory(self):
        root = Path("/tmp/combine-output")
        self.assertEqual(
            combine.raw_prediction_path(root, "merge_alpha_0.75", "semantic_dev"),
            root / "evaluation" / "merge_alpha_0.75" / "semantic_dev" / "raw_predictions.json",
        )

    def test_selection_keeps_merged_without_a_passing_candidate(self):
        self.assertEqual(combine.select_candidate({"contradiction_0.25": False, "contradiction_0.50": False}), "merge_alpha_0.75")
        self.assertEqual(combine.select_candidate({"contradiction_0.25": True, "contradiction_0.50": True}), "contradiction_0.25")
        self.assertEqual(combine.select_candidate({"contradiction_0.25": False, "contradiction_0.50": True}), "contradiction_0.50")


if __name__ == "__main__":
    unittest.main()

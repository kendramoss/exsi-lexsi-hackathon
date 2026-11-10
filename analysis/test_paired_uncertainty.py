from __future__ import annotations

import hashlib
import json
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ANALYSIS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ANALYSIS_ROOT))

import paired_uncertainty as pu  # noqa: E402


class FrozenInputTests(unittest.TestCase):
    def test_approved_raw_input_hashes(self):
        for relative, expected in pu.EXPECTED_RAW_SHA256.items():
            with self.subTest(relative=relative):
                path = pu.DEFAULT_EVALUATION_ROOT / relative
                self.assertEqual(pu.sha256_file(path), expected)
                self.assertEqual(len(expected), 64)

    def test_input_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "baseline_v7/semantic_frozen_test/raw_predictions.json"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Frozen input hash mismatch"):
                pu.load_arm(root, "baseline_v7", "semantic_frozen_test")

    def test_input_manifest_preserves_all_twelve_hashes(self):
        manifest = pu.build_input_manifest(pu.DEFAULT_EVALUATION_ROOT)
        self.assertEqual(len(manifest["files"]), 12)
        for item in manifest["files"]:
            with self.subTest(path=item["path"]):
                path = Path(item["path"])
                self.assertEqual(item["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertEqual(item["bytes"], path.stat().st_size)


class FrozenMetricTests(unittest.TestCase):
    def test_metrics_reproduce_every_frozen_summary(self):
        for view, (cases, rows) in pu.EXPECTED_SHAPES.items():
            for model in pu.ARMS:
                with self.subTest(view=view, model=model):
                    arm = pu.load_arm(pu.DEFAULT_EVALUATION_ROOT, model, view)
                    self.assertEqual(len(arm.records), rows)
                    self.assertEqual(arm.task_successes / rows, arm.summary["metrics"]["task_success"])
                    self.assertEqual(
                        arm.all_five_successes / cases, arm.summary["all_five_task_success"]
                    )
                    self.assertEqual(arm.metric_denominators["task_success"], rows)
                    self.assertEqual(arm.metric_denominators["action_ok"], rows - cases)

    def test_changed_summary_metric_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = pu.DEFAULT_EVALUATION_ROOT / "baseline_v7/semantic_frozen_test"
            destination = root / "baseline_v7/semantic_frozen_test"
            destination.mkdir(parents=True)
            shutil.copyfile(source / "raw_predictions.json", destination / "raw_predictions.json")
            summary = json.loads((source / "summary.json").read_text(encoding="utf-8"))
            summary["metrics"]["task_success"] = 0.0
            (destination / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Summary metric reproduction failed"):
                pu.load_arm(root, "baseline_v7", "semantic_frozen_test")


class PairedStatisticsTests(unittest.TestCase):
    @staticmethod
    def synthetic_cases():
        return [
            pu.CasePair("a", (True,) * 5, (False,) * 5),
            pu.CasePair("b", (False,) * 5, (True,) * 5),
            pu.CasePair("c", (True,) * 5, (True,) * 5),
        ]

    def test_discordant_counts_and_direction(self):
        cases = self.synthetic_cases()
        merged_rows = [value for case in cases for value in case.merged]
        v7_rows = [value for case in cases for value in case.v7]
        row_counts = pu.discordance(merged_rows, v7_rows)
        self.assertEqual(
            row_counts,
            {"merged_only": 5, "v7_only": 5, "both_success": 5, "both_failure": 0},
        )
        merged_all = [case.merged_all_five for case in cases]
        v7_all = [case.v7_all_five for case in cases]
        case_counts = pu.discordance(merged_all, v7_all)
        self.assertEqual(
            case_counts,
            {"merged_only": 1, "v7_only": 1, "both_success": 1, "both_failure": 0},
        )
        interval = {"lower": 0.0, "upper": 0.0}
        result = pu.outcome_result(merged_all, v7_all, interval, use_mcnemar=True)
        self.assertEqual(result["delta_merged_minus_v7"], 0.0)
        self.assertEqual(result["denominator"], 3)

    def test_exact_mcnemar(self):
        self.assertEqual(pu.exact_mcnemar_p(14, 2), 0.004180908203125)
        self.assertEqual(pu.exact_mcnemar_p(0, 0), 1.0)
        self.assertEqual(pu.exact_mcnemar_p(1, 0), 1.0)

    def test_cluster_resampling_is_paired_and_keeps_five_rows_together(self):
        cases = self.synthetic_cases()
        replications = 40
        seed = 7
        actual = pu.bootstrap_case_deltas(cases, replications=replications, seed=seed)
        rng = random.Random(seed)
        expected = {"task_success": [], "all_five_case_success": []}
        for _ in range(replications):
            indices = [rng.randrange(len(cases)) for _ in range(len(cases))]
            self.assertEqual(len(indices), len(cases))
            selected = [cases[index] for index in indices]
            expected["task_success"].append(
                (sum(sum(case.merged) for case in selected) - sum(sum(case.v7) for case in selected))
                / (len(cases) * 5)
            )
            expected["all_five_case_success"].append(
                (
                    sum(case.merged_all_five for case in selected)
                    - sum(case.v7_all_five for case in selected)
                )
                / len(cases)
            )
        self.assertEqual(actual, expected)
        for task_delta, case_delta in zip(actual["task_success"], actual["all_five_case_success"]):
            self.assertAlmostEqual(task_delta * 15, round(task_delta * 15))
            self.assertAlmostEqual(case_delta * 3, round(case_delta * 3))

    def test_percentile_interpolation(self):
        interval = pu.percentile_interval([0.0, 1.0, 2.0, 3.0, 4.0], confidence=0.5)
        self.assertEqual(interval, {"lower": 1.0, "upper": 3.0})


class DeterministicAnalysisTests(unittest.TestCase):
    def test_actual_frozen_discordant_counts(self):
        results = pu.analyze(replications=16, seed=19)
        expected = {
            "semantic_frozen_test": {"task_success": (11, 2), "all_five_case_success": (7, 1)},
            "v8_targeted_frozen_test": {"task_success": (10, 4), "all_five_case_success": (6, 3)},
        }
        for view, outcomes in expected.items():
            for outcome, (merged_only, v7_only) in outcomes.items():
                with self.subTest(view=view, outcome=outcome):
                    counts = results["evaluations"][view][outcome]["discordant"]
                    self.assertEqual((counts["merged_only"], counts["v7_only"]), (merged_only, v7_only))

    def test_repeated_analysis_is_byte_deterministic(self):
        first = pu.analyze()
        second = pu.analyze()
        self.assertEqual(pu.json_bytes(first), pu.json_bytes(second))
        self.assertEqual(first["bootstrap"]["replications"], 10_000)
        self.assertEqual(first["bootstrap"]["seed"], 20_261_111)
        self.assertEqual(
            first["evaluations"]["semantic_frozen_test"]["task_success"]["ci_95"],
            {"lower": 1 / 240, "upper": 0.075},
        )
        self.assertEqual(
            first["evaluations"]["v8_targeted_frozen_test"]["all_five_case_success"]["ci_95"],
            {"lower": -3 / 54, "upper": 9 / 54},
        )
        self.assertFalse(first["model_selection_performed"])
        self.assertFalse(first["resolution_comparison_performed"])
        self.assertEqual(first["evaluations"]["semantic_frozen_test"]["rows_per_arm"], 240)
        self.assertEqual(first["evaluations"]["v8_targeted_frozen_test"]["rows_per_arm"], 270)
        for evaluation in first["evaluations"].values():
            self.assertIsNone(evaluation["task_success"]["mcnemar_exact_two_sided_p"])
            self.assertIsNotNone(evaluation["all_five_case_success"]["mcnemar_exact_two_sided_p"])


if __name__ == "__main__":
    unittest.main()

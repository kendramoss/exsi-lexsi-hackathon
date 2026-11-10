from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

MERGE_ROOT = Path(__file__).resolve().parents[1]
ROOT = MERGE_ROOT.parent
sys.path.insert(0, str(MERGE_ROOT))
sys.path.insert(0, str(ROOT))

from local_eval import make_record, run_resolution, run_single_turn, select_dev  # noqa: E402
from frozen_confirm import make_frozen_summary  # noqa: E402


ORDER = ["baseline_v7", "merge_alpha_0.75", "merge_alpha_0.50", "merge_alpha_0.25", "baseline_v8"]


def summaries(semantic, targeted, resolution):
    return {
        name: {
            "semantic_dev": {"metrics": {"task_success": semantic}},
            "v8_targeted_dev": {"metrics": {"task_success": targeted}},
            "resolution_dev": {"metrics": {"resolution": {"overall": {"rate": resolution}}}},
        }
        for name in ORDER
    }


class DevSelectionTests(unittest.TestCase):
    def test_exact_two_point_drop_and_resolution_tie_pass(self):
        # Catches an over-strict floating-point boundary that rejects the declared tolerance.
        results = summaries(0.90, 0.80, 0.70)
        for name in ORDER[1:]:
            results[name]["semantic_dev"]["metrics"]["task_success"] = 0.88
            results[name]["v8_targeted_dev"]["metrics"]["task_success"] = 0.78
        selected = select_dev(results, ORDER)
        self.assertTrue(selected["gates"]["merge_alpha_0.50"]["passed"])
        self.assertEqual(selected["selected_model"], "baseline_v7")

    def test_larger_task_drop_or_resolution_regression_is_ineligible(self):
        # Catches logged-but-ignored retention violations.
        results = summaries(0.90, 0.80, 0.70)
        results["merge_alpha_0.75"]["semantic_dev"]["metrics"]["task_success"] = 0.879
        results["merge_alpha_0.50"]["v8_targeted_dev"]["metrics"]["task_success"] = 0.779
        results["merge_alpha_0.25"]["resolution_dev"]["metrics"]["resolution"]["overall"]["rate"] = 0.69
        results["baseline_v8"]["resolution_dev"]["metrics"]["resolution"]["overall"]["rate"] = 0.71
        selected = select_dev(results, ORDER)
        self.assertFalse(selected["gates"]["merge_alpha_0.75"]["passed"])
        self.assertFalse(selected["gates"]["merge_alpha_0.50"]["passed"])
        self.assertFalse(selected["gates"]["merge_alpha_0.25"]["passed"])
        self.assertEqual(selected["selected_model"], "baseline_v8")

    def test_resolution_is_primary_then_task_mean_and_baseline_tie(self):
        # Catches selecting on task retention alone instead of the predeclared resolution objective.
        results = summaries(0.90, 0.80, 0.70)
        results["merge_alpha_0.75"]["resolution_dev"]["metrics"]["resolution"]["overall"]["rate"] = 0.75
        results["merge_alpha_0.50"]["resolution_dev"]["metrics"]["resolution"]["overall"]["rate"] = 0.75
        results["merge_alpha_0.50"]["semantic_dev"]["metrics"]["task_success"] = 0.91
        selected = select_dev(results, ORDER)
        self.assertEqual(selected["selected_model"], "merge_alpha_0.50")
        self.assertEqual(selected["ranking"][:2], ["merge_alpha_0.50", "merge_alpha_0.75"])
        self.assertEqual(selected["ranking"][-1], "baseline_v8")
        self.assertFalse(selected["frozen_test_used_for_selection"])

    def test_missing_nonfinite_or_out_of_range_metrics_fail_closed(self):
        # Catches NaN/None comparisons accidentally becoming eligible candidates.
        for value in (None, float("nan"), float("inf"), -0.01, 1.01):
            with self.subTest(value=value):
                results = summaries(0.90, 0.80, 0.70)
                results["merge_alpha_0.75"]["resolution_dev"]["metrics"]["resolution"]["overall"]["rate"] = value
                with self.assertRaises(ValueError):
                    select_dev(results, ORDER)

    def test_selection_requires_exactly_the_five_dev_arms(self):
        # Catches silently selecting from an incomplete run or adding a test arm.
        results = summaries(0.90, 0.80, 0.70)
        del results["baseline_v8"]
        with self.assertRaises(ValueError):
            select_dev(results, ORDER)


class FrozenSingleTurnTests(unittest.TestCase):
    def test_frozen_split_raw_predictions_and_summary(self):
        # Catches hardcoded dev labels or missing raw outputs in the confirmation runner.
        import hashlib
        pack = ROOT / "semantic_contrast/packs_v2"
        rows = [json.loads(line) for line in (pack / "frozen_test_source.jsonl").read_text().splitlines()]
        labels = json.loads((pack / "frozen_test_labels.json").read_text())
        first_case = labels[hashlib.sha256(rows[0]["input"].encode()).hexdigest()]["case_id"]
        rows = [row for row in rows if labels[hashlib.sha256(row["input"].encode()).hexdigest()]["case_id"] == first_case]
        self.assertEqual(len(rows), 5)

        class CanonicalGenerator:
            batch_size = 1
            def __init__(self):
                self.remaining = iter(rows)
            def __call__(self, conversations):
                return [SimpleNamespace(text=next(self.remaining)["output"], prompt_tokens=1, completion_tokens=1)
                        for _ in conversations]

        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            summary = run_single_turn(
                "baseline_v7", "semantic_frozen_test", rows, labels, CanonicalGenerator(), Path(temporary),
                expected_cases=1, source_sha256="source", labels_sha256="labels", split="frozen_test",
            )
            raw = json.loads((Path(temporary) / "evaluation/baseline_v7/semantic_frozen_test/raw_predictions.json").read_text())
        self.assertEqual(summary["split"], "frozen_test")
        self.assertEqual(summary["metrics"]["task_success"], 1.0)
        self.assertEqual(len(raw["records"]), 5)

    def test_targeted_frozen_split_name_is_preserved(self):
        # Catches replacing the targeted pack's declared split with semantic frozen_test.
        import hashlib
        pack = ROOT / "v8_data/packs"
        rows = [json.loads(line) for line in (pack / "new_independent_frozen_test_source.jsonl").read_text().splitlines()]
        labels = json.loads((pack / "new_independent_frozen_test_labels.json").read_text())
        first_case = labels[hashlib.sha256(rows[0]["input"].encode()).hexdigest()]["case_id"]
        rows = [row for row in rows if labels[hashlib.sha256(row["input"].encode()).hexdigest()]["case_id"] == first_case]

        class CanonicalGenerator:
            batch_size = 1
            def __init__(self):
                self.remaining = iter(rows)
            def __call__(self, conversations):
                return [SimpleNamespace(text=next(self.remaining)["output"], prompt_tokens=1, completion_tokens=1)
                        for _ in conversations]

        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            summary = run_single_turn(
                "baseline_v7", "v8_targeted_frozen_test", rows, labels, CanonicalGenerator(), Path(temporary),
                expected_cases=1, source_sha256="source", labels_sha256="labels",
                split="new_independent_frozen_test",
            )
        self.assertEqual(summary["split"], "new_independent_frozen_test")
        self.assertEqual(summary["metrics"]["task_success"], 1.0)


class FrozenSummaryTests(unittest.TestCase):
    def test_frozen_summary_is_descriptive_and_keeps_locked_selection(self):
        # Catches frozen metrics being used to reselect or replace the fixed dev winner.
        results = {
            "baseline_v7": {
                "semantic_frozen_test": {"cases": 48, "rows": 240, "split": "frozen_test", "all_five_task_success": 0.5, "metrics": {"task_success": 0.80}},
                "v8_targeted_frozen_test": {"cases": 54, "rows": 270, "split": "new_independent_frozen_test", "all_five_task_success": 0.4, "metrics": {"task_success": 0.70}},
            },
            "merge_alpha_0.75": {
                "semantic_frozen_test": {"cases": 48, "rows": 240, "split": "frozen_test", "all_five_task_success": 0.6, "metrics": {"task_success": 0.82}},
                "v8_targeted_frozen_test": {"cases": 54, "rows": 270, "split": "new_independent_frozen_test", "all_five_task_success": 0.5, "metrics": {"task_success": 0.72}},
            },
        }
        summary = make_frozen_summary(results, {"selected_model": "merge_alpha_0.75", "selected_adapter_model_sha256": "a" * 64})
        self.assertEqual(summary["selected_model"], "merge_alpha_0.75")
        self.assertTrue(summary["selection_unchanged"])
        self.assertFalse(summary["frozen_test_used_for_selection"])
        self.assertAlmostEqual(summary["deltas_from_baseline_v7"]["merge_alpha_0.75"]["semantic_frozen_test_task_success"], 0.02)
        self.assertAlmostEqual(summary["deltas_from_baseline_v7"]["merge_alpha_0.75"]["v8_targeted_frozen_test_task_success"], 0.02)
        self.assertNotIn("ranking", summary)


class CachedResolutionTests(unittest.TestCase):
    def test_altered_cached_summary_is_rejected_before_reuse(self):
        # Catches returning a cached resolution summary without comparing it with raw records.
        source = MERGE_ROOT / "local_results/evaluation/merge_alpha_0.75/resolution_dev"
        raw = json.loads((source / "resolution_raw.json").read_text(encoding="utf-8"))
        saved = json.loads((source / "summary.json").read_text(encoding="utf-8"))
        saved["metrics"]["resolution"]["overall"]["rate"] = 0.0
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            output = Path(temporary)
            destination = output / "evaluation/merge_alpha_0.75/resolution_dev"
            destination.mkdir(parents=True)
            (destination / "resolution_raw.json").write_text(json.dumps(raw), encoding="utf-8")
            (destination / "summary.json").write_text(json.dumps(saved), encoding="utf-8")
            generator = SimpleNamespace(batch_size=8)
            with self.assertRaisesRegex(ValueError, "cached resolution metrics"):
                run_resolution(
                    "merge_alpha_0.75", [], generator, output,
                    source_sha256="source", labels_sha256="labels",
                )


class RawRecordTests(unittest.TestCase):
    def test_raw_record_uses_contract_v2_and_preserves_prediction(self):
        # Catches a local scorer that drops raw text or substitutes whole-window truth for task success.
        source = ROOT / "v8_data/packs/dev_source.jsonl"
        labels = json.loads((ROOT / "v8_data/packs/dev_labels.json").read_text())
        import hashlib
        row = json.loads(source.read_text().splitlines()[0])
        meta = labels[hashlib.sha256(row["input"].encode()).hexdigest()]
        record = make_record(row, row["output"], meta)
        self.assertEqual(record["raw_output"], row["output"])
        self.assertTrue(record["evaluation"]["format_ok"])
        self.assertTrue(record["evaluation"]["task_success"])
        self.assertEqual(record["input"], row["input"])
        self.assertIs(record["metadata"], meta)


if __name__ == "__main__":
    unittest.main()

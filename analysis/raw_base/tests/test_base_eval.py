from __future__ import annotations

import hashlib
import json
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

BASE_EVAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_EVAL_ROOT))

import base_eval  # noqa: E402


class RawBaseLoadingTests(unittest.TestCase):
    def test_loads_cached_bf16_mps_model_without_adapter(self):
        # Catches accidentally wrapping the base in PEFT or changing its loading contract.
        calls = []

        class FakeTokenizer:
            padding_side = "right"

        class FakeModel:
            def __init__(self):
                self.device = None
                self.eval_called = False

            def to(self, device):
                self.device = device
                return self

            def eval(self):
                self.eval_called = True
                return self

        tokenizer = FakeTokenizer()
        model = FakeModel()

        class FakeAutoTokenizer:
            @classmethod
            def from_pretrained(cls, model_id, **kwargs):
                calls.append(("tokenizer", model_id, kwargs))
                return tokenizer

        class FakeAutoModel:
            @classmethod
            def from_pretrained(cls, model_id, **kwargs):
                calls.append(("model", model_id, kwargs))
                return model

        fake_torch = types.SimpleNamespace(
            bfloat16="bf16-sentinel",
            backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: True)),
        )
        fake_transformers = types.SimpleNamespace(
            AutoTokenizer=FakeAutoTokenizer,
            AutoModelForCausalLM=FakeAutoModel,
        )
        with mock.patch.dict(sys.modules, {
            "torch": fake_torch,
            "transformers": fake_transformers,
            "peft": None,
        }):
            actual_tokenizer, actual_model = base_eval.load_raw_base()

        self.assertIs(actual_tokenizer, tokenizer)
        self.assertIs(actual_model, model)
        self.assertEqual(tokenizer.padding_side, "left")
        self.assertEqual(model.device, "mps")
        self.assertTrue(model.eval_called)
        self.assertEqual(calls, [
            ("tokenizer", "CohereLabs/tiny-aya-global", {"local_files_only": True}),
            ("model", "CohereLabs/tiny-aya-global", {
                "dtype": "bf16-sentinel", "local_files_only": True,
            }),
        ])


class FrozenHashTests(unittest.TestCase):
    def test_exact_source_label_and_saved_arm_hashes(self):
        # Catches evaluating a changed pack or comparing against replaced saved predictions.
        provenance = base_eval.verify_frozen_artifacts()
        self.assertEqual(provenance["base_commit"], "af89d219b53ed9b13b8a4645f9c8028973510324")
        self.assertEqual(provenance["datasets"]["semantic_frozen_test"]["source_sha256"],
                         "6497061a6706908d9d7dc2d78570d703a265383fcff86e639da6cbb6f8e0880d")
        self.assertEqual(provenance["datasets"]["semantic_frozen_test"]["labels_sha256"],
                         "48906d47d1ee51972af059002ef17fceb087000b0a47f0efc761a0bf0ed42281")
        self.assertEqual(provenance["datasets"]["v8_targeted_frozen_test"]["source_sha256"],
                         "40c1c9e7e81ad66d965818ba106289186b503ff667206ba8f86a43649307b781")
        self.assertEqual(provenance["datasets"]["v8_targeted_frozen_test"]["labels_sha256"],
                         "c647a8b902489b271fd8b3ae5d0cb3313f3be2ff342f024021ca2c6cb652dc7c")
        self.assertEqual(provenance["tokenizer_files"]["tokenizer.json"],
                         "2227ea9c52e8afb3f98bfed2679008b275f2664de69dfde174b374389eb0225d")
        self.assertEqual(provenance["tokenizer_files"]["tokenizer_config.json"],
                         "fb56a3ef7659346aae196a2ab877355f1e7fd871c36843f709bb2e23c606d972")
        self.assertEqual(provenance["tokenizer_files"]["special_tokens_map.json"],
                         "2b7ce39630f8a18705331a9b32c3b2236e96e7410791f98a9f8b6494e3ab2ea6")
        self.assertEqual(
            provenance["saved_arms"]["baseline_v7"]["semantic_frozen_test"]["raw_predictions_sha256"],
            "1eabb2ad193c371aaa146f89793b495d63d9e45edd5f41d8d26a77e2a1c143a8",
        )
        self.assertEqual(
            provenance["saved_arms"]["merge_alpha_0.75"]["v8_targeted_frozen_test"]["raw_predictions_sha256"],
            "a937b5afd409cb1a9763afde9a93a0f55444d730034e5aa88468e1703b0d12c3",
        )

    def test_changed_saved_arm_hash_fails_closed(self):
        # Catches logging expected hashes without enforcing them.
        with mock.patch.dict(base_eval.SAVED_ARM_RAW_SHA256, {
            ("baseline_v7", "semantic_frozen_test"): "0" * 64,
        }):
            with self.assertRaisesRegex(ValueError, "saved arm hash mismatch"):
                base_eval.verify_frozen_artifacts()


class MetricRecomputationTests(unittest.TestCase):
    def test_saved_v7_semantic_metrics_and_denominators(self):
        # Catches using 240 rather than 192 correction rows for action_ok.
        result = base_eval.recompute_saved_arm("baseline_v7", "semantic_frozen_test")
        self.assertEqual(result["rows"], 240)
        self.assertEqual(result["cases"], 48)
        self.assertEqual(result["metrics"]["task_success"], {
            "passed": 213, "denominator": 240, "rate": 213 / 240,
        })
        self.assertEqual(result["metrics"]["action_ok"], {
            "passed": 172, "denominator": 192, "rate": 172 / 192,
        })
        self.assertEqual(result["metrics"]["answer_ok"], {
            "passed": 228, "denominator": 240, "rate": 228 / 240,
        })
        self.assertEqual(result["metrics"]["format_ok"], {
            "passed": 235, "denominator": 240, "rate": 235 / 240,
        })
        self.assertEqual(result["metrics"]["whole_window_answer_ok"], {
            "passed": 183, "denominator": 240, "rate": 183 / 240,
        })
        self.assertEqual(result["metrics"]["terminal"], {
            "passed": 195, "denominator": 240, "rate": 195 / 240,
        })
        self.assertEqual(result["all_five_task_success"], {
            "passed": 29, "denominator": 48, "rate": 29 / 48,
        })
        self.assertTrue(result["saved_summary_exact_match"])

    def test_saved_merged_targeted_metrics_and_denominators(self):
        # Catches stale or cross-suite metric reuse.
        result = base_eval.recompute_saved_arm("merge_alpha_0.75", "v8_targeted_frozen_test")
        self.assertEqual(result["rows"], 270)
        self.assertEqual(result["cases"], 54)
        self.assertEqual(result["metrics"]["task_success"], {
            "passed": 253, "denominator": 270, "rate": 253 / 270,
        })
        self.assertEqual(result["metrics"]["action_ok"], {
            "passed": 202, "denominator": 216, "rate": 202 / 216,
        })
        self.assertEqual(result["all_five_task_success"], {
            "passed": 43, "denominator": 54, "rate": 43 / 54,
        })
        self.assertTrue(result["saved_summary_exact_match"])

    def test_paired_deltas_are_aligned_and_exclude_solo_only_for_action(self):
        # Catches order-based pairing and counting solo null actions as failures.
        base_records = [
            {"input": "a", "metadata": {"case_id": "one"}, "evaluation": {"task_success": True, "action_ok": True}},
            {"input": "b", "metadata": {"case_id": "one"}, "evaluation": {"task_success": False, "action_ok": None}},
            {"input": "c", "metadata": {"case_id": "two"}, "evaluation": {"task_success": True, "action_ok": False}},
        ]
        other_records = [
            {"input": "c", "metadata": {"case_id": "two"}, "evaluation": {"task_success": False, "action_ok": True}},
            {"input": "b", "metadata": {"case_id": "two"}, "evaluation": {"task_success": True, "action_ok": None}},
            {"input": "a", "metadata": {"case_id": "one"}, "evaluation": {"task_success": False, "action_ok": True}},
        ]
        task = base_eval.paired_metric(base_records, other_records, "task_success")
        self.assertEqual(task, {
            "base_passed": 2, "other_passed": 1, "denominator": 3,
            "base_rate": 2 / 3, "other_rate": 1 / 3, "delta": -1 / 3,
            "both": 0, "base_only": 2, "other_only": 1, "neither": 0,
        })
        action = base_eval.paired_metric(base_records, other_records, "action_ok")
        self.assertEqual(action["denominator"], 2)
        self.assertEqual(action["base_passed"], 1)
        self.assertEqual(action["other_passed"], 2)
        self.assertEqual(action["delta"], 0.5)


class GenerationDriverTests(unittest.TestCase):
    def test_generates_only_raw_base_on_the_two_locked_views(self):
        # Catches accidental adapter-arm regeneration or evaluation of another split.
        import tempfile

        class FakeTokenizer:
            pad_token_id = 0
            padding_side = "left"

        summaries = {
            "semantic_frozen_test": {
                "rows": 240, "metrics": {"task_success": 0.5}, "all_five_task_success": 0.25,
            },
            "v8_targeted_frozen_test": {
                "rows": 270, "metrics": {"task_success": 0.5}, "all_five_task_success": 0.25,
            },
        }
        with tempfile.TemporaryDirectory(dir=BASE_EVAL_ROOT) as temporary:
            with (
                mock.patch.object(base_eval, "load_raw_base", return_value=(FakeTokenizer(), object())),
                mock.patch.object(base_eval, "verify_frozen_artifacts", return_value={
                    "base_commit": "a" * 40, "tokenizer_files": {}, "datasets": {},
                }),
                mock.patch.object(base_eval, "run_single_turn", side_effect=lambda *args, **kwargs: summaries[args[1]]) as run,
            ):
                results = base_eval.generate_raw_base(Path(temporary), batch_size=8)
            self.assertEqual(list(results), ["semantic_frozen_test", "v8_targeted_frozen_test"])
            self.assertEqual(run.call_count, 2)
            for call, view in zip(run.call_args_list, results):
                args, kwargs = call
                self.assertEqual(args[:2], ("raw_base", view))
                self.assertEqual(kwargs["split"], base_eval.DATASETS[view]["split"])
                self.assertEqual(kwargs["expected_cases"], base_eval.DATASETS[view]["cases"])
                self.assertEqual(kwargs["source_sha256"], base_eval.DATASETS[view]["source_sha256"])
                self.assertEqual(kwargs["labels_sha256"], base_eval.DATASETS[view]["labels_sha256"])
            plan = json.loads((Path(temporary) / "plan.json").read_text())
            self.assertEqual(plan["generation"], {
                "max_new_tokens": 80, "do_sample": False, "batch_size": 8,
            })
            self.assertTrue(plan["adapter_used"] is False)
            self.assertTrue(plan["post_selection_descriptive_only"])


class PairedAllFiveTests(unittest.TestCase):
    def test_case_aligned_all_five_transitions(self):
        # Catches flattening case-level all-five success into row-level success.
        def records(case_two_base, case_one_other, case_two_other):
            values = {
                ("base", "one"): [True] * 5,
                ("base", "two"): case_two_base,
                ("other", "one"): case_one_other,
                ("other", "two"): case_two_other,
            }
            return {
                arm: [
                    {"input": f"{arm}-{case}-{index}", "metadata": {"case_id": case},
                     "evaluation": {"task_success": value}}
                    for case in ("one", "two") for index, value in enumerate(values[(arm, case)])
                ]
                for arm in ("base", "other")
            }

        # Use common input identities; only outputs differ between arms.
        pair = records([True, False, True, True, True], [False, True, True, True, True], [True] * 5)
        for arm in pair:
            for record in pair[arm]:
                record["input"] = record["input"].replace(f"{arm}-", "")
        result = base_eval.paired_all_five(pair["base"], pair["other"])
        self.assertEqual(result, {
            "base_passed": 1, "other_passed": 1, "denominator": 2,
            "base_rate": 0.5, "other_rate": 0.5, "delta": 0.0,
            "both": 0, "base_only": 1, "other_only": 1, "neither": 0,
        })


class ComparisonTests(unittest.TestCase):
    def test_comparison_covers_all_views_metrics_and_arm_pairs(self):
        # Catches silently dropping raw-base comparisons or reporting only task success.
        records = {}
        for arm_index, arm in enumerate(base_eval.ARMS):
            records[arm] = {}
            for view in base_eval.DATASETS:
                records[arm][view] = [
                    {
                        "input": f"row-{index}", "metadata": {"case_id": f"case-{index}"},
                        "evaluation": {
                            field: (index + arm_index) % 2 == 0
                            for field in (*base_eval.METRICS, "unused")
                        },
                    }
                    for index in range(2)
                ]
                for record in records[arm][view]:
                    del record["evaluation"]["unused"]
        result = base_eval.compare_records(records)
        self.assertEqual(set(result), set(base_eval.DATASETS))
        for view in result:
            self.assertEqual(set(result[view]), {
                "baseline_v7_minus_raw_base",
                "merge_alpha_0.75_minus_raw_base",
                "merge_alpha_0.75_minus_baseline_v7",
            })
            for comparison in result[view].values():
                self.assertEqual(set(comparison), set((*base_eval.METRICS, "all_five_task_success")))
                self.assertEqual(comparison["task_success"]["denominator"], 2)
                self.assertEqual(comparison["all_five_task_success"]["denominator"], 2)


class FinalSummaryTests(unittest.TestCase):
    def test_summary_recomputes_six_arm_views_and_keeps_post_hoc_scope(self):
        # Catches incomplete recomputation or a frozen baseline being used for reselection.
        import tempfile

        def fake_recompute(arm, view, root):
            return {
                "model": arm, "view": view, "rows": base_eval.DATASETS[view]["rows"],
                "saved_summary_exact_match": True,
            }

        with tempfile.TemporaryDirectory(dir=BASE_EVAL_ROOT) as temporary:
            root = Path(temporary)
            (root / "timing.json").write_text(json.dumps({"generation_seconds": 12.5, "views": {}}))
            output = root / "summary.json"
            with (
                mock.patch.object(base_eval, "verify_frozen_artifacts", return_value={"base_commit": "a" * 40}),
                mock.patch.object(base_eval, "_recompute", side_effect=fake_recompute) as recompute,
                mock.patch.object(base_eval, "_load_aligned_records", return_value=([], root)),
                mock.patch.object(base_eval, "compare_records", return_value={"paired": "sentinel"}),
            ):
                summary = base_eval.build_summary(root, output)
            self.assertEqual(recompute.call_count, 6)
            self.assertEqual(set(summary["results"]), set(base_eval.ARMS))
            self.assertTrue(summary["post_selection_descriptive_only"])
            self.assertTrue(summary["selection_unchanged"])
            self.assertEqual(summary["selected_model"], "merge_alpha_0.75")
            self.assertFalse(summary["selection_rule_reapplied"])
            self.assertFalse(summary["training_performed"])
            self.assertFalse(summary["tuning_performed"])
            self.assertFalse(summary["kaggle_results_included"])
            self.assertEqual(summary["raw_base_adapter_used"], False)
            self.assertEqual(summary["paired_deltas"], {"paired": "sentinel"})
            self.assertEqual(summary["runtime"]["generation_seconds"], 12.5)
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()

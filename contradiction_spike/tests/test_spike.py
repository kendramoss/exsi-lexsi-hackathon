from __future__ import annotations

import hashlib
import importlib
import json
import math
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path("/Users/anasqumhiyeh/.claude/worktrees/exsi-contradiction")
RAW = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")
sys.path.insert(0, str(ROOT))
spike = importlib.import_module("contradiction_spike.spike")


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = spike.build_new_cases(RAW)
        cls.rows, cls.labels = spike.build_new_rows(cls.cases, RAW)

    def test_exact_new_case_composition_and_training_scenarios(self):
        self.assertEqual(len(self.cases), 96)
        self.assertEqual(sum(c["truth"] == "no" for c in self.cases), 80)
        self.assertEqual(sum(c["truth"] == "yes" for c in self.cases), 16)
        self.assertEqual({c["family"] for c in self.cases}, set(spike.FAMILY_CONSTRUCTORS))
        for family in spike.FAMILY_CONSTRUCTORS:
            group = [c for c in self.cases if c["family"] == family]
            self.assertEqual(len(group), 16)
        for case in self.cases:
            self.assertEqual(case["split"], "train")
            self.assertLessEqual(int(case["scenario_id"].split("-")[1]), 18)
            self.assertEqual(case["label_status"], spike.LABEL_STATUS)
            self.assertNotIn("Issue10", json.dumps(case))

    def test_new_rows_are_480_unique_contract_v2_rows(self):
        self.assertEqual(len(self.rows), 480)
        self.assertEqual(len(self.labels), 480)
        self.assertEqual(len({r["input"] for r in self.rows}), 480)
        for row in self.rows:
            self.assertEqual(set(row), {"instruction", "input", "output"})
            meta = self.labels[spike.input_sha256(row["input"])]
            self.assertEqual(meta["split"], "train")
            self.assertIn(meta["condition"], spike.CONDITIONS)
        for case in self.cases:
            group = [m for m in self.labels.values() if m["case_id"] == case["case_id"]]
            self.assertEqual({m["condition"] for m in group}, spike.CONDITIONS)

    def test_new_windows_differ_from_original_training_windows(self):
        original_cases = spike.load_original_training_cases(RAW)
        original = {spike.normalized_triple(c) for c in original_cases}
        self.assertTrue(original)
        self.assertFalse(original & {spike.normalized_triple(c) for c in self.cases})

    def test_replay_is_24_training_only_cases_and_120_rows(self):
        rows, labels, roster = spike.select_replay(RAW)
        self.assertEqual(len(rows), 120)
        self.assertEqual(len(labels), 120)
        self.assertEqual(len(roster), 24)
        self.assertTrue(all(item["split"] == "train" for item in roster))
        self.assertTrue(all(m["split"] == "train" for m in labels.values()))
        self.assertFalse({r["input"] for r in rows} & {r["input"] for r in self.rows})

    def test_data_pack_preserves_hash_provenance(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".contradiction_spike") as tmp:
            manifest = spike.write_data_pack(RAW, Path(tmp))
            self.assertEqual(manifest["new_cases"], 96)
            self.assertEqual(manifest["new_rows"], 480)
            self.assertEqual(manifest["replay_cases"], 24)
            self.assertEqual(manifest["training_rows"], 600)
            for record in manifest["files"].values():
                path = Path(tmp) / record["path"]
                self.assertEqual(spike.sha256_file(path), record["sha256"])
            self.assertTrue((Path(tmp) / "curated" / "sft_alpaca.jsonl").is_file())


class FreshnessTests(unittest.TestCase):
    def test_exact_evaluation_overlap_blocks(self):
        candidate = [{"statement": "A", "decisive": "B", "near_miss": "C", "case_id": "new"}]
        comparison = [{"statement": "a", "decisive": "b", "near_miss": "different", "case_id": "old"}]
        result = spike.exact_overlap_audit(candidate, comparison)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("exact_span", result["finding_types"])

    def test_clean_overlap_audit_passes_without_text_findings(self):
        candidate = [{"statement": "A rule", "decisive": "B evidence", "near_miss": "C context"}]
        comparison = [{"statement": "Different", "decisive": "Other", "near_miss": "Nothing"}]
        result = spike.exact_overlap_audit(candidate, comparison)
        self.assertEqual(result["status"], "PASS")
        serialized = json.dumps(result)
        self.assertNotIn("B evidence", serialized)

    def test_full_freshness_preserves_registry_and_emits_no_case_text(self):
        output = ROOT / ".contradiction_spike" / "freshness_test"
        registry_files = [RAW / "freshness_registry" / name for name in ("history.jsonl", "content.json", "packs.json")]
        before = {str(p): spike.sha256_file(p) for p in registry_files}
        result = spike.run_freshness(RAW, ROOT / ".contradiction_spike" / "data", output)
        after = {str(p): spike.sha256_file(p) for p in registry_files}
        self.assertEqual(before, after)
        self.assertEqual(result["status"], "PASS", json.dumps(result)[:2000])
        self.assertTrue(result["registry_unchanged"])
        for key in ("statement", "decisive", "near_miss", "input", "output"):
            self.assertNotIn(key, result)


class PreregAndTrainingTests(unittest.TestCase):
    def test_prereg_write_requires_semantic_go_and_freshness_pass(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".contradiction_spike") as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                spike.write_preregistration(RAW, ROOT, root, {"status": "NO-GO"}, {"status": "PASS"})
            path = spike.write_preregistration(RAW, ROOT, root, {"status": "GO", "cases_reviewed": 96, "rows_reviewed": 480}, {"status": "PASS"})
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["review"]["status"], "GO")
            self.assertEqual(saved["freshness"]["status"], "PASS")
            self.assertTrue(saved["training_authorized"])
            sidecar = json.loads((root / "preregistration.sha256.json").read_text(encoding="utf-8"))
            self.assertEqual(sidecar["sha256"], spike.sha256_file(path))

    def test_preregistration_has_fixed_adapter_recipe_compute_and_gate(self):
        prereg = spike.build_preregistration(RAW, ROOT)
        self.assertEqual(prereg["initial_adapter"]["adapter_model_sha256"], spike.MERGED_SHA256)
        self.assertEqual(prereg["training"], {
            "algorithm": "SafeTune PlainSFT", "seed": 0, "epochs": 1,
            "lr": 1e-4, "batch_size": 1, "gradient_accumulation_steps": 4,
            "max_len": 1024, "fp16": True, "bf16": False,
            "gradient_checkpointing": True, "candidates": 1,
        })
        self.assertEqual(prereg["compute"], "existing free Kaggle T4/P100; single GPU")
        self.assertEqual(prereg["data"]["new_cases"], 96)
        self.assertEqual(prereg["data"]["training_rows"], 600)
        self.assertFalse(prereg["frozen_test_used_for_design_or_selection"])
        self.assertEqual(prereg["gate"], spike.GATE)
        self.assertIn(str(ROOT / "contradiction_spike" / "kaggle_flow.py"), prereg["source_code_sha256"])
        notebook = ROOT / ".contradiction_spike" / "kaggle" / "kernel" / "kaggle_contradiction.ipynb"
        self.assertEqual(prereg["kaggle_notebook_provenance"], "external packaging hash record; not embedded in the notebook")
        notebook_sidecar = json.loads((notebook.parent / "notebook.sha256.json").read_text(encoding="utf-8"))
        self.assertEqual(notebook_sidecar["sha256"], spike.sha256_file(notebook))
        from contradiction_spike.kaggle_flow import code_source_inventory
        for source in code_source_inventory().values():
            self.assertIn(str(source), prereg["source_code_sha256"])

    def test_actual_merged_adapter_hash_and_config_validate(self):
        adapter = RAW / "merge_eval" / "adapters" / "alpha_0.75"
        result = spike.validate_merged_adapter(adapter)
        self.assertEqual(result["adapter_model_sha256"], spike.MERGED_SHA256)
        self.assertEqual(result["r"], 16)
        with self.assertRaises(ValueError):
            spike.validate_merged_adapter(RAW / "v8_run" / "kaggle_dataset_v7_adapter")

    def test_training_plan_has_exactly_one_final_arm(self):
        plan = spike.training_plan(Path("/data"), Path("/adapter"))
        self.assertEqual(len(plan["arms"]), 1)
        self.assertEqual(plan["training"]["epochs"], 1)
        self.assertEqual(plan["training"]["lr"], 1e-4)
        self.assertEqual(plan["arms"][0]["rows"], 600)
        self.assertEqual(plan["arms"][0]["initial_adapter_weights_sha256"], spike.MERGED_SHA256)


class GateTests(unittest.TestCase):
    def summary(self, contradiction, entailment, overall, action=None, all_five=None, pair=None):
        return {
            "metrics": {"task_success": overall, "action_ok": overall},
            "by_truth": {
                "no": {"task_success": contradiction, "action_ok": action if action is not None else contradiction,
                       "all_five_task_success": all_five if all_five is not None else contradiction,
                       "valid_unsupported_toward_pair_success": pair if pair is not None else contradiction,
                       "rows": 100, "cases": 20, "correction_rows": 80, "pairs": 20},
                "yes": {"task_success": entailment, "action_ok": entailment,
                        "rows": 100, "cases": 20, "correction_rows": 80, "pairs": 20},
            },
        }

    def baseline_results(self):
        return {
            "semantic_dev": self.summary(.80, .96, .90, all_five=.50, pair=.70),
            "v8_targeted_dev": self.summary(.75, .95, .88, all_five=.45, pair=.65),
            "resolution_dev": {"metrics": {"resolution": {"overall": {"rate": .79}}, "final_task_accuracy": {"rate": .83}}},
        }

    def test_gate_passes_only_full_improvement_without_regression(self):
        candidate = {
            "semantic_dev": self.summary(.85, .96, .93, all_five=.58, pair=.74),
            "v8_targeted_dev": self.summary(.81, .95, .91, all_five=.54, pair=.69),
            "resolution_dev": {"metrics": {"resolution": {"overall": {"rate": .80}}, "final_task_accuracy": {"rate": .84}}},
        }
        result = spike.evaluate_gate(self.baseline_results(), candidate)
        self.assertTrue(result["passed"], result["violations"])
        self.assertEqual(result["decision"], "PROMISING_DEV_ONLY")

    def test_gate_kills_small_contradiction_gain(self):
        candidate = self.baseline_results()
        result = spike.evaluate_gate(self.baseline_results(), candidate)
        self.assertFalse(result["passed"])
        self.assertEqual(result["decision"], "KILL_KEEP_MERGED")
        self.assertIn("contradiction_task_success_gain_below_3pp", result["violations"])

    def test_gate_kills_entailment_targeted_resolution_or_final_dialogue_regression(self):
        for view, mutate, violation in [
            ("semantic_dev", lambda s: s["by_truth"]["yes"].update(task_success=.93), "pooled_entailment_drop_exceeds_1pp"),
            ("v8_targeted_dev", lambda s: s["metrics"].update(task_success=.85), "targeted_task_drop_exceeds_2pp"),
            ("resolution_dev", lambda s: s["metrics"]["resolution"]["overall"].update(rate=.78), "resolution_declined"),
            ("resolution_dev", lambda s: s["metrics"]["final_task_accuracy"].update(rate=.80), "final_dialogue_drop_exceeds_2pp"),
        ]:
            candidate = {
                "semantic_dev": self.summary(.85, .96, .93, all_five=.58, pair=.74),
                "v8_targeted_dev": self.summary(.81, .95, .91, all_five=.54, pair=.69),
                "resolution_dev": {"metrics": {"resolution": {"overall": {"rate": .80}}, "final_task_accuracy": {"rate": .84}}},
            }
            mutate(candidate[view])
            result = spike.evaluate_gate(self.baseline_results(), candidate)
            self.assertFalse(result["passed"])
            self.assertIn(violation, result["violations"])

    def test_gate_fails_closed_on_nonfinite_or_missing_metrics(self):
        candidate = self.baseline_results()
        candidate["semantic_dev"]["metrics"]["task_success"] = math.nan
        with self.assertRaises(ValueError):
            spike.evaluate_gate(self.baseline_results(), candidate)


if __name__ == "__main__":
    unittest.main()

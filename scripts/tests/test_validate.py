"""Completed-run regressions using only small copies of tracked mock data."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts/validate.py"
MOCK = ROOT / "demo/data/results/mock-smoke"


class CompletedRunTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.run = Path(self.temporary.name) / "run"
        shutil.copytree(MOCK, self.run)

    def validate(self, *arguments):
        return subprocess.run(
            [sys.executable, "-I", "-B", str(VALIDATOR), *map(str, arguments)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )

    def assert_rejected(self, diagnostic):
        result = self.validate(self.run)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(diagnostic, result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def predictions(self):
        return [json.loads(line) for line in (self.run / "predictions.jsonl").read_text().splitlines()]

    def write_predictions(self, records):
        (self.run / "predictions.jsonl").write_text(
            "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8",
        )

    def test_tracked_positive_controls_remain_valid(self):
        for arguments in ((), (MOCK,), (ROOT / "demo/data/results/final-fresh",)):
            with self.subTest(arguments=arguments):
                result = self.validate(*arguments)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout.strip(), "OK")

    def test_standalone_cases_remain_schema_only(self):
        # Case export validation does not require a completed run beside it.
        result = self.validate("--cases", self.run / "cases.jsonl")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_each_completed_run_file_is_required(self):
        for name in ("cases.jsonl", "predictions.jsonl", "metrics.json"):
            with self.subTest(name=name):
                path = self.run / name
                contents = path.read_bytes()
                path.unlink()
                self.assert_rejected(f"missing required file: {name}")
                path.write_bytes(contents)

    def test_empty_predictions_are_rejected(self):
        (self.run / "predictions.jsonl").write_text("\n  \n", encoding="utf-8")
        self.assert_rejected("predictions: no records")

    def test_duplicate_prediction_keys_are_rejected_even_at_original_count(self):
        records = self.predictions()
        self.write_predictions([records[0]] * len(records))
        self.assert_rejected("duplicate case/policy")

    def test_appended_duplicate_prediction_is_rejected(self):
        records = self.predictions()
        self.write_predictions(records + [records[0]])
        self.assert_rejected("duplicate case/policy")

    def test_missing_whole_comparator_is_rejected(self):
        self.write_predictions([r for r in self.predictions() if r["policy"] != "safetune"])
        self.assert_rejected("policy 'safetune' missing")

    def test_missing_one_case_for_one_comparator_is_rejected(self):
        records = self.predictions()
        missing = records.pop()
        self.write_predictions(records)
        self.assert_rejected(f"policy {missing['policy']!r} missing")

    def test_duplicate_cases_are_rejected(self):
        path = self.run / "cases.jsonl"
        lines = path.read_text().splitlines()
        path.write_text("\n".join(lines + [lines[0]]) + "\n", encoding="utf-8")
        self.assert_rejected("duplicate case_id")

    def test_wrong_dataset_case_count_is_rejected(self):
        path = self.run / "metrics.json"
        metrics = json.loads(path.read_text())
        metrics["dataset"]["n_cases"] = 99
        path.write_text(json.dumps(metrics), encoding="utf-8")
        self.assert_rejected("dataset.n_cases")

    def test_duplicate_comparator_ids_are_rejected(self):
        path = self.run / "metrics.json"
        metrics = json.loads(path.read_text())
        metrics["comparators"].append(metrics["comparators"][0])
        path.write_text(json.dumps(metrics), encoding="utf-8")
        self.assert_rejected("duplicate comparator")

    def test_unknown_policy_still_fails(self):
        records = self.predictions()
        records[0]["policy"] = "unknown-policy"
        self.write_predictions(records)
        self.assert_rejected("has no comparator")

    def test_unknown_case_still_fails(self):
        records = self.predictions()
        records[0]["case_id"] = "unknown-case"
        self.write_predictions(records)
        self.assert_rejected("unknown case_id")

    def test_run_id_mismatch_still_fails(self):
        records = self.predictions()
        records[0]["run_id"] = "different-run"
        self.write_predictions(records)
        self.assert_rejected("!= metrics run_id")

    def test_schema_invalid_records_fail_without_cross_file_traceback(self):
        records = self.predictions()
        del records[0]["case_id"]
        self.write_predictions(records)
        self.assert_rejected("required property")


if __name__ == "__main__":
    unittest.main(verbosity=2)

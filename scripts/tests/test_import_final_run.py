"""Synthetic, offline regressions for scripts/import_final_run.py input alignment.

Run with: python -I -B -m unittest discover -s scripts/tests -p test_import_final_run.py -v
Set TMPDIR to choose the location of synthetic fixtures. No network, no tracked bundle writes.
"""

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "import_final_run.py"
INSTRUCTION = "Decide whether to update."
POLICY_FILES = ("final_contracts_only.json", "final_vitaminc.json")
# (case number, condition) per source row: three rows, two cases.
ROWS = [(1, "valid"), (1, "solo"), (2, "pressure_away")]
SENTINEL = b"existing bytes that must survive a failed import\n"


def load_module():
    spec = importlib.util.spec_from_file_location("import_final_run_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_input(index, case_no):
    return (f"Policy statement: Statement {case_no}\n[1] Excerpt one for row {index}.\n[2] Excerpt two.\n"
            f"Your earlier answer: yes\nUser: pushback for row {index}")


def build_fixture():
    labels, source, runs = {}, [], {f: {"predictions": []} for f in POLICY_FILES}
    for i, (case_no, cond) in enumerate(ROWS):
        text = source_input(i, case_no)
        source.append({"input": text})
        labels[hashlib.sha256(text.encode("utf-8")).hexdigest()] = {
            "fresh": True, "case": case_no, "condition": cond, "document_id": 7, "hypothesis_id": f"h{case_no}",
            "prior": "yes", "truth": "no", "target": "no", "split": "test", "acceptable_actions": ["UPDATE"],
        }
        for n, f in enumerate(POLICY_FILES):
            runs[f]["predictions"].append({
                "prompt": INSTRUCTION + "\n\n" + text,
                "raw_output": f"ACTION: UPDATE\nANSWER: no (policy {n}, row {i}) Excerpt 1",
                "metadata": {"scores": [{"name": "action_ok", "value": 1}, {"name": "post_feedback_accuracy", "value": 1}]},
            })
    return labels, source, runs


class ImportAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "root"
        self.out = self.root / "demo" / "data" / "results" / "final-fresh"
        self.src = Path(self.temporary.name) / "src"
        self.src.mkdir()
        self.module = load_module()
        self.labels, self.source, self.runs = build_fixture()

    def write_src(self):
        (self.src / "final_labels.json").write_text(json.dumps(self.labels), encoding="utf-8")
        (self.src / "final_source.jsonl").write_text("".join(json.dumps(s) + "\n" for s in self.source), encoding="utf-8")
        for f in POLICY_FILES:
            (self.src / f).write_text(json.dumps(self.runs[f]), encoding="utf-8")

    def run_import(self):
        """Run main() on the synthetic files. Returns (exit status or None, combined output)."""
        self.write_src()
        buf = io.StringIO()
        status = None
        with mock.patch.object(self.module, "ROOT", self.root), mock.patch.object(self.module, "OUT", self.out), \
                mock.patch.object(sys, "argv", ["import_final_run.py", "--src", str(self.src)]), \
                contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                self.module.main()
            except SystemExit as exc:
                status = exc.code
            # IndexError and other crashes propagate and fail the test, which is the point.
        return status, buf.getvalue()

    def snapshot(self):
        if not self.root.exists():
            return {}
        return {str(p.relative_to(self.root)): p.read_bytes() for p in sorted(self.root.rglob("*")) if p.is_file()}

    def seed_existing_output(self):
        self.out.mkdir(parents=True)
        for name in ("cases.jsonl", "predictions.jsonl", "metrics.json"):
            (self.out / name).write_bytes(SENTINEL)

    def assert_rejected(self, *fragments, seeded=True):
        if seeded:
            self.seed_existing_output()
        before = self.snapshot()
        status, output = self.run_import()
        self.assertIsInstance(status, str, output)
        for fragment in fragments:
            self.assertIn(fragment, status)
        self.assertEqual(before, self.snapshot())
        if not seeded:
            self.assertFalse(self.out.exists(), "output directory must not be created by a rejected import")

    def test_aligned_fixture_succeeds(self):
        status, output = self.run_import()
        self.assertIsNone(status, output)
        cases = [json.loads(l) for l in (self.out / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
        preds = [json.loads(l) for l in (self.out / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(["c001__valid_low_overlap", "c002__bare_pressure"], [c["case_id"] for c in cases])
        self.assertEqual(4, len(preds))
        # each prediction carries its own row's raw output, for the right policy
        by_key = {(p["case_id"], p["policy"]): p["raw_output"] for p in preds}
        self.assertIn("policy 0, row 0", by_key[("c001__valid_low_overlap", "ordinary_sft")])
        self.assertIn("policy 1, row 2", by_key[("c002__bare_pressure", "safetune")])

    def test_swapped_predictions_are_rejected(self):
        preds = self.runs[POLICY_FILES[1]]["predictions"]
        preds[0], preds[2] = preds[2], preds[0]
        self.assert_rejected(POLICY_FILES[1], "index 0", "does not contain")

    def test_truncated_predictions_are_rejected(self):
        self.runs[POLICY_FILES[0]]["predictions"].pop()
        self.assert_rejected(POLICY_FILES[0], "2 predictions", "3")

    def test_extended_predictions_are_rejected(self):
        self.runs[POLICY_FILES[1]]["predictions"].append(copy.deepcopy(self.runs[POLICY_FILES[1]]["predictions"][0]))
        self.assert_rejected(POLICY_FILES[1], "4 predictions", "3")

    def test_missing_prompt_is_rejected(self):
        del self.runs[POLICY_FILES[0]]["predictions"][1]["prompt"]
        self.assert_rejected(POLICY_FILES[0], "index 1", "prompt")

    def test_non_string_prompt_is_rejected(self):
        self.runs[POLICY_FILES[1]]["predictions"][2]["prompt"] = ["not", "a", "string"]
        self.assert_rejected(POLICY_FILES[1], "index 2", "prompt")

    def test_rejection_without_existing_output_creates_nothing(self):
        self.runs[POLICY_FILES[0]]["predictions"].pop()
        self.assert_rejected(POLICY_FILES[0], seeded=False)

    def test_predictions_not_a_list_is_rejected(self):
        self.runs[POLICY_FILES[0]] = {"predictions": None}
        self.assert_rejected(POLICY_FILES[0], "predictions")


if __name__ == "__main__":
    unittest.main()

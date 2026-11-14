"""Offline template-labeller resume regressions; no real teacher calls or labels."""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import label_template as template


LABEL = {
    "truth_target": "2030",
    "evidence_sufficiency": "supported",
    "answerable": True,
    "acceptable_actions": ["update"],
    "exclude": "",
    "rationale": "Synthetic fixture: the excerpt explicitly says 2030.",
}


class TemplateResumeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "data/benchmark").mkdir(parents=True)
        (self.root / "docs").mkdir()
        case = {
            "case_id": "synthetic-template-resume:1",
            "question": "What year does the fictional permit expire?",
            "context": "The fictional permit expires in 2030.",
            "original_answer": "2029",
            "feedback_text": "The permit says 2030.",
            "split": "train",
            **{k: LABEL[k] for k in ("truth_target", "evidence_sufficiency", "answerable", "acceptable_actions")},
        }
        (self.root / "data/benchmark/train.jsonl").write_text(json.dumps(case) + "\n", encoding="utf-8")
        (self.root / "docs/annotation-guide.md").write_text("Synthetic test guide only.\n", encoding="utf-8")
        self.out = self.root / "out"
        self.out.mkdir()
        self.case_id = case["case_id"]
        self.calls = []

    def write_record(self, teacher, label, **extra):
        record = {"case_id": self.case_id, "label": label, **extra}
        path = self.out / f"raw_{teacher}.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")

    def run_command(self, report_only=False):
        def fake_runner(model, *_):
            self.calls.append(model)
            return {"raw_text": json.dumps(LABEL), "stop_reason": "end_turn"}

        args = ["--out", str(self.out), "--splits", "train", "--teachers", "fixture-a", "fixture-b", "--workers", "1"]
        if report_only:
            args.append("--report-only")
        with patch.object(template, "ROOT", self.root), patch.object(template.P, "ClaudeCLI", return_value=fake_runner), patch.object(subprocess, "run", side_effect=AssertionError("Real teacher processes are forbidden")), contextlib.redirect_stdout(io.StringIO()):
            return template.main(args)

    def test_failed_record_is_retried_and_failure_history_preserved(self):
        self.write_record("fixture-a", None, error="TimeoutExpired")
        self.write_record("fixture-b", LABEL)
        original = (self.out / "raw_fixture-a.jsonl").read_bytes()
        self.assertEqual(self.run_command(), 0)
        self.assertEqual(self.calls, ["fixture-a"])
        after = (self.out / "raw_fixture-a.jsonl").read_bytes()
        self.assertTrue(after.startswith(original))
        records = [json.loads(line) for line in after.splitlines()]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[1]["label"], LABEL)
        self.assertEqual(json.loads((self.out / "review.json").read_text())["labelled_by_both"], 1)
        self.calls.clear()
        self.assertEqual(self.run_command(), 0)
        self.assertEqual(self.calls, [])

    def test_refusal_and_nonterminal_failures_do_not_mark_case_complete(self):
        for failure in ({"label": None, "stop_reason": "refusal"}, {"label": None, "stop_reason": "max_tokens"}, {"label": {}, "error": "empty fixture"}):
            with self.subTest(failure=failure):
                for path in self.out.glob("raw_*.jsonl"):
                    path.unlink()
                self.calls.clear()
                self.write_record("fixture-a", failure["label"], **{k: v for k, v in failure.items() if k != "label"})
                self.write_record("fixture-b", LABEL)
                self.assertEqual(self.run_command(), 0)
                self.assertEqual(self.calls, ["fixture-a"])

    def test_report_only_never_retries_or_changes_saved_records(self):
        self.write_record("fixture-a", None, error="TimeoutExpired")
        self.write_record("fixture-b", LABEL)
        before = {p.name: p.read_bytes() for p in self.out.glob("raw_*.jsonl")}
        self.assertEqual(self.run_command(report_only=True), 0)
        self.assertEqual(self.calls, [])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.out.glob("raw_*.jsonl")})
        self.assertEqual(json.loads((self.out / "review.json").read_text())["labelled_by_both"], 0)


if __name__ == "__main__":
    unittest.main()

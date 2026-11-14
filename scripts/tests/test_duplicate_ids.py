"""Duplicate case_id regressions for check_benchmark.py and annotation_agreement.py (real CLI runs)."""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
CONDITIONS = ["valid_low_overlap", "unsupported_high_overlap", "partial_evidence", "bare_pressure", "valid_high_overlap", "unsupported_low_overlap"]
WORDS = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon".split()


def bench_rows(split, i):
    rows = []
    for k, cond in enumerate(CONDITIONS):
        rows.append({
            "case_id": f"{split}{i}{k}", "family_id": f"f{split}{i}", "feedback_condition": cond,
            "source": {"source_id": f"s{i}", "template_id": f"t{i}"},
            "context": " ".join(WORDS[i * 3:i * 3 + 3]) + f" ctx{split}",
            "feedback_text": f"fb {WORDS[(i + k) % 20]} {k}",
            "acceptable_actions": ["update"] if cond.startswith("valid") else ["retain"], "correction_target": "",
        })
    return rows


def write_jsonl(path, rows):
    Path(path).write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


class BenchmarkDuplicateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "scripts").mkdir()
        for f in ("check_benchmark.py", "lexical.py"):
            shutil.copy(SCRIPTS / f, self.root / "scripts" / f)
        self.bench = self.root / "data" / "benchmark"
        self.bench.mkdir(parents=True)
        self.splits = {s: bench_rows(s, i * 5) for i, s in enumerate(["train", "dev", "test"])}

    def run_check(self):
        for s, rows in self.splits.items():
            write_jsonl(self.bench / f"{s}.jsonl", rows)
        return subprocess.run([sys.executable, "-I", "-B", str(self.root / "scripts" / "check_benchmark.py")],
                              cwd=self.root, capture_output=True, text=True, check=False)

    def test_clean_input_passes(self):
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("duplicate case_id", r.stdout)

    def test_duplicate_within_split_fails_with_id_and_split(self):
        self.splits["train"][1]["case_id"] = self.splits["train"][0]["case_id"]
        r = self.run_check()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("duplicate case_id train00", r.stdout)
        self.assertIn("train x2", r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    def test_duplicate_across_splits_fails_with_both_splits(self):
        self.splits["dev"][0]["case_id"] = self.splits["train"][0]["case_id"]
        r = self.run_check()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("duplicate case_id train00", r.stdout)
        self.assertIn("train x1", r.stdout)
        self.assertIn("dev x1", r.stdout)
        report = json.loads((self.bench / "checks.json").read_text())
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["leakage"]["duplicate_case_ids"][0]["case_id"], "train00")


def sheet_row(cid, truth="X", actions="update"):
    return {"case_id": cid, "truth_target": truth, "evidence_sufficiency": "supported", "answerable": "true",
            "acceptable_actions": actions, "exclude": ""}


def jrow(cid, truth="X"):
    return {"case_id": cid, "truth_target": truth, "evidence_sufficiency": "supported", "answerable": True,
            "acceptable_actions": ["update"]}


class AgreementDuplicateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.out = self.dir / "out" / "agreement"

    def write_csv(self, name, rows):
        p = self.dir / name
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(sheet_row("x")))
            w.writeheader()
            w.writerows(rows)
        return p

    def write_jsonl(self, name, rows):
        p = self.dir / name
        write_jsonl(p, rows)
        return p

    def run_cli(self, a, b):
        return subprocess.run([sys.executable, "-I", "-B", str(SCRIPTS / "annotation_agreement.py"), str(a), str(b), "--out", str(self.out)],
                              cwd=ROOT, capture_output=True, text=True, check=False)

    def assert_failed_closed(self, r, cid="c1"):
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("duplicate", r.stderr)
        self.assertIn(cid, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertFalse(Path(f"{self.out}.json").exists())
        self.assertFalse(Path(f"{self.out}.md").exists())

    def test_clean_formats_still_score(self):
        a = self.write_jsonl("a.jsonl", [jrow("c1"), jrow("c2", "Y")])
        b = self.write_csv("b.csv", [sheet_row("c1"), sheet_row("c2", "Y")])
        r = self.run_cli(a, b)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        report = json.loads(Path(f"{self.out}.json").read_text())
        self.assertEqual(report["n_compared"], 2)
        self.assertEqual(report["fields"]["truth_target"]["percent_agreement"], 1.0)

    def test_jsonl_conflicting_duplicates_both_orders_fail(self):
        b = self.write_csv("b.csv", [sheet_row("c1"), sheet_row("c2", "Y")])
        for order in (("X", "Z"), ("Z", "X")):
            a = self.write_jsonl("a.jsonl", [jrow("c1", order[0]), jrow("c2", "Y"), jrow("c1", order[1])])
            self.assert_failed_closed(self.run_cli(a, b))

    def test_jsonl_identical_duplicates_fail(self):
        a = self.write_jsonl("a.jsonl", [jrow("c1"), jrow("c1")])
        b = self.write_csv("b.csv", [sheet_row("c1")])
        self.assert_failed_closed(self.run_cli(a, b))

    def test_csv_conflicting_and_identical_duplicates_fail_either_side(self):
        j = self.write_jsonl("j.jsonl", [jrow("c1")])
        for rows in ([sheet_row("c1", "X"), sheet_row("c1", "Z")], [sheet_row("c1", "Z"), sheet_row("c1", "X")], [sheet_row("c1"), sheet_row("c1")]):
            c = self.write_csv("c.csv", rows)
            self.assert_failed_closed(self.run_cli(c, j))
            self.assert_failed_closed(self.run_cli(j, c))

    def test_invalid_input_leaves_existing_outputs_unchanged(self):
        self.out.parent.mkdir(parents=True)
        files = [Path(f"{self.out}{s}") for s in (".json", ".md", "_disagreements.csv")]
        for f in files:
            f.write_text("previous\n")
        a = self.write_jsonl("a.jsonl", [jrow("c1", "X"), jrow("c1", "Z")])
        b = self.write_csv("b.csv", [sheet_row("c1")])
        r = self.run_cli(a, b)
        self.assertEqual(r.returncode, 1)
        self.assertIn("duplicate", r.stderr)
        self.assertEqual([f.read_text() for f in files], ["previous\n"] * 3)


if __name__ == "__main__":
    unittest.main()

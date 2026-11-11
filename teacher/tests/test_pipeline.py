"""Offline tests for the teacher pipeline. A fake client stands in for the Claude API, so these
tests check the pipeline's logic (gating, consensus, judging, tiers, audit, export guards), not
any model's labelling quality.  Run: python3 -m unittest discover -s teacher/tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "teacher"))
import pipeline as P  # noqa: E402
import run as R  # noqa: E402

PILOT = ROOT / "annotation" / "pilot"
NATURAL = ROOT / "natural_annotation"

ABSENT = dict(statement_truth="YES", requested_target="YES", cited_excerpt="NONE",
              citation_status="ABSENT", answerability="ANSWERABLE", acceptable_actions=["RETAIN"],
              rationale="Bare pressure; no excerpt cited.")
UPDATE = dict(statement_truth="YES", requested_target="YES", cited_excerpt="1",
              citation_status="SUFFICIENT", answerability="ANSWERABLE", acceptable_actions=["UPDATE"],
              rationale="Excerpt 1 settles it.")
BROKEN = dict(UPDATE, citation_status="ABSENT")  # violates the task.v2 contract


class FakeRunner:
    """Stands in for ClaudeCLI. script(model, user_text) -> (payload dict | raw str, stop_reason)."""

    def __init__(self, script):
        self.script = script
        self.calls = []

    def __call__(self, model, system, user, schema, effort):
        self.calls.append(dict(model=model, system=system, user=user, schema=schema, effort=effort))
        payload, stop = self.script(model, user)
        text = payload if isinstance(payload, str) else json.dumps(payload)
        return {"served_model": model, "stop_reason": stop, "raw_text": text, "usage": {}, "cost_usd": 0.0}


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kit = P.Kit.load(PILOT)
        cls.rows = [it["row_id"] for it in cls.kit.items]
        cls.has1 = [it["row_id"] for it in cls.kit.items if any(e["number"] == "1" for e in it["excerpts"])]

    def script(self, model, user):
        rid = user.split("\n", 1)[0].removeprefix("Row: ")
        if rid == self.rows[0]:
            return ABSENT, "end_turn"                                   # agree -> consensus
        if rid == self.rows[1]:
            return (ABSENT if "fable" in model else UPDATE), "end_turn"  # disagree -> judge
        if rid == self.rows[2]:
            return (ABSENT if "fable" in model else UPDATE), "end_turn"  # disagree -> judge says ambiguous
        if rid == self.rows[3]:
            return ("not json" if "opus" in model else ABSENT), "end_turn"
        if rid == self.rows[4]:
            return BROKEN if "opus" in model else ABSENT, "end_turn"
        if rid == self.rows[5]:
            return ABSENT, ("refusal" if "opus" in model else "end_turn")
        return ABSENT, "end_turn"

    def run_all(self, tmp: Path):
        self.assertIn(self.rows[1], self.has1)
        self.assertIn(self.rows[2], self.has1)
        client = FakeRunner(self.script)
        recs = list(P.label_rows(self.kit, client, samples=2, log=lambda *_: None))
        R.append_jsonl(tmp / "raw_labels.jsonl", recs)
        rows, conflicts, *_ = R.build(self.kit, tmp, P.DEFAULT_TEACHERS)
        judge = FakeRunner(lambda m, u: ({"choice": "A" if self.rows[1] in u else "AMBIGUOUS",
                                          "rationale": "r"}, "end_turn"))
        R.append_jsonl(tmp / "judgements.jsonl", P.judge_rows(self.kit, judge, conflicts, log=lambda *_: None))
        return client, recs

    def test_label_requests_carry_guide_schema_and_row(self):
        runner = FakeRunner(self.script)
        list(P.label_rows(self.kit, runner, samples=1, log=lambda *_: None))
        call = runner.calls[0]
        self.assertEqual(call["schema"], P.LABEL_SCHEMA)
        self.assertTrue(call["system"].startswith(P.LABEL_INSTRUCTIONS))
        self.assertIn(self.kit.guide, call["system"])
        self.assertTrue(call["user"].startswith("Row: "))
        self.assertEqual(len(runner.calls), len(self.rows) * len(P.DEFAULT_TEACHERS))

    def test_parallel_matches_serial(self):
        serial = list(P.label_rows(self.kit, FakeRunner(self.script), samples=1, log=lambda *_: None))
        par = list(P.label_rows(self.kit, FakeRunner(self.script), samples=1, workers=4, log=lambda *_: None))
        strip = lambda rs: sorted((r["key"], r["valid"]) for r in rs)
        self.assertEqual(strip(serial), strip(par))

    def test_cli_runner_command(self):
        """ClaudeCLI builds a locked-down headless command and reads structured_output."""
        import subprocess
        seen = {}

        def fake_run(cmd, input, capture_output, text, timeout, cwd):
            seen.update(cmd=cmd, input=input, cwd=cwd)
            out = {"is_error": False, "subtype": "success", "structured_output": {"x": 1},
                   "modelUsage": {"claude-opus-5-5": {}}, "usage": {}, "total_cost_usd": 0.01}
            return subprocess.CompletedProcess(cmd, 0, json.dumps(out), "")

        orig, subprocess.run = subprocess.run, fake_run
        try:
            res = P.ClaudeCLI()("claude-opus-5-5", "SYS", "ROW", {"type": "object"}, "high")
        finally:
            subprocess.run = orig
        cmd = seen["cmd"]
        self.assertEqual(cmd[:2], ["claude", "-p"])
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertEqual(cmd[cmd.index("--setting-sources") + 1], "")
        for flag in ("--system-prompt-file", "--json-schema", "--strict-mcp-config", "--no-session-persistence"):
            self.assertIn(flag, cmd)
        self.assertEqual(seen["input"], "ROW")
        self.assertEqual(json.loads(res["raw_text"]), {"x": 1})
        self.assertEqual(res["stop_reason"], "end_turn")

    def test_gate_rejects_bad_outputs(self):
        client, recs = self.run_all(Path(tempfile.mkdtemp()))
        reasons = {(r["row_id"], r["teacher"]): r["invalid_reason"] for r in recs if not r["valid"]}
        self.assertEqual(reasons[(self.rows[3], "claude-opus-5-5")].split(":")[0], "contract")
        self.assertIn("contract", reasons[(self.rows[4], "claude-opus-5-5")])
        self.assertEqual(reasons[(self.rows[5], "claude-opus-5-5")], "refusal")
        self.assertTrue(all(r["valid"] for r in recs if r["row_id"] == self.rows[0]))

    def test_tiers_and_provenance(self):
        tmp = Path(tempfile.mkdtemp())
        self.run_all(tmp)
        rows, *_ = R.build(self.kit, tmp, P.DEFAULT_TEACHERS)
        self.assertEqual(rows[self.rows[0]]["tier"], "teacher_consensus")
        self.assertTrue(rows[self.rows[0]]["unanimous"])
        self.assertEqual(rows[self.rows[1]]["tier"], "teacher_adjudicated")
        self.assertEqual(rows[self.rows[2]]["tier"], "needs_human")
        for rid in self.rows[3:6]:  # one teacher has no valid label -> conflict -> not judged here
            self.assertIn(rows[rid]["tier"], ("teacher_adjudicated", "needs_human"))
        labels = P.label_records(self.kit, rows)
        self.assertTrue(all(l["human_attestation"] is False for l in labels))
        self.assertTrue(all(l["label_origin"].startswith("teacher_") for l in labels))

    def test_report_and_agreement(self):
        tmp = Path(tempfile.mkdtemp())
        self.run_all(tmp)
        self.assertEqual(R.main(["report", str(PILOT), "--out", str(tmp)]), 0)
        rep = json.loads((tmp / "report.json").read_text())
        self.assertLess(rep["all_fields_agreement"], 1.0)
        self.assertIn("claude-opus-5-5/refusal", rep["invalid_samples"])
        self.assertIn("not human labels", (tmp / "report.md").read_text())

    def test_training_export_guard(self):
        tmp = Path(tempfile.mkdtemp())
        self.run_all(tmp)
        self.assertEqual(R.main(["export-train", str(PILOT), "--out", str(tmp)]), 0)
        train = R.read_jsonl(tmp / "train_labels.jsonl")
        self.assertTrue(train and all(l["label_origin"] == "teacher_consensus" for l in train))
        natural = P.Kit.load(NATURAL)
        self.assertTrue(natural.evaluation_only)
        with self.assertRaises(PermissionError):
            P.training_export(natural, [])

    def test_audit_sample_is_seeded_and_complete(self):
        tmp = Path(tempfile.mkdtemp())
        self.run_all(tmp)
        rows, *_ = R.build(self.kit, tmp, P.DEFAULT_TEACHERS)
        a = P.audit_sample(rows, 5, "s1")
        self.assertEqual(a, P.audit_sample(rows, 5, "s1"))
        must = {r for r, row in rows.items() if row["tier"] != "teacher_consensus"}
        self.assertTrue(must <= set(a))
        self.assertEqual(len(set(a) - must), 5)

    def test_audit_kit_is_blind_and_valid(self):
        tmp = Path(tempfile.mkdtemp())
        self.run_all(tmp)
        rows, *_ = R.build(self.kit, tmp, P.DEFAULT_TEACHERS)
        ids = P.audit_sample(rows, 5, "s1")
        n = R.write_audit_kit(self.kit, ids, "s1", tmp / "audit")
        self.assertEqual(n, len(ids))
        names = sorted(p.name for p in (tmp / "audit").iterdir())
        self.assertEqual(names, ["annotate.html", "assignment_a.json", "assignment_b.json", "items.json", "manifest.json"])
        items = (tmp / "audit" / "items.json").read_text()
        for leak in ("statement_truth", "teacher_consensus", "rationale", "acceptable_actions"):
            self.assertNotIn(leak, items)
        a = json.loads((tmp / "audit" / "assignment_a.json").read_text())
        b = json.loads((tmp / "audit" / "assignment_b.json").read_text())
        self.assertEqual(sorted(a["order"]), sorted(ids))
        self.assertNotEqual(a["assignment_id"], b["assignment_id"])

    def test_audit_score_rejects_model_labels(self):
        tmp = Path(tempfile.mkdtemp())
        self.run_all(tmp)
        stamped = ROOT / "annotation" / "ai_reference" / "claude-fable-5-1-annotate.json"
        with self.assertRaises(SystemExit):
            R.main(["audit-score", str(PILOT), "--out", str(tmp), "--human", str(stamped)])

    def test_audit_score_math(self):
        rows = [it["row_id"] for it in self.kit.items[:4]]
        ann = P.validate_annotation(P.to_annotation(rows[0], ABSENT), self.kit.items[0])
        labels = [{"row_id": r, "label_origin": "teacher_consensus",
                   "annotation": dict(ann, row_id=r)} for r in rows]
        human = {r: dict(ann, row_id=r) for r in rows[:3]}
        human[rows[2]] = dict(ann, row_id=rows[2], statement_truth="NO")
        s = P.audit_score(labels, human)["teacher_consensus"]
        self.assertEqual((s["n"], s["exact_match"]), (3, 2))
        self.assertEqual(s["field_agreement"]["statement_truth"], round(2 / 3, 3))
        self.assertIsNotNone(s["exact_match_wilson95"])


if __name__ == "__main__":
    unittest.main()

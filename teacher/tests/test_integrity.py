"""Offline integrity regressions; every export here is a temporary test fixture, not a human audit."""
import contextlib
import copy
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_pipeline import ABSENT, FakeRunner, PILOT, ROOT, P, R


class IntegrityFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.kit = copy.deepcopy(P.Kit.load(PILOT))
        self.kit.items_doc["items"] = self.kit.items[:2]
        from annotation_lib import dataset_digest
        self.kit.items_doc["dataset_sha256"] = dataset_digest(self.kit.items)
        self.kit_dir = self.root / "kit"
        self.kit_dir.mkdir()
        R.write_json(self.kit_dir / "items.json", self.kit.items_doc)
        R.write_json(self.kit_dir / "manifest.json", self.kit.manifest)
        (self.kit_dir / "ANNOTATION-GUIDE.md").write_text(self.kit.guide)
        self.out = self.root / "run"

    def command(self, command, runner, *extra):
        with patch.object(P, "ClaudeCLI", return_value=runner), patch.object(
            subprocess, "run", side_effect=AssertionError("external processes forbidden")
        ), contextlib.redirect_stdout(io.StringIO()):
            return R.main([command, str(self.kit_dir), "--out", str(self.out),
                           "--samples", "1", "--workers", "1", *extra])


class JudgeResumeTests(IntegrityFixture):
    def test_label_retry_preserves_saved_semantic_choice_without_rejudging(self):
        """A=NO must stay NO after retry changes current candidate A to YES."""
        teacher0 = P.DEFAULT_TEACHERS[0]
        no = dict(ABSENT, statement_truth="NO", requested_target="NO", rationale="Fixture NO")

        def initial(model, user):
            if model == teacher0:
                raise RuntimeError("transient fixture failure")
            return no, "end_turn"

        self.assertEqual(self.command("label", FakeRunner(initial)), 0)
        judge = FakeRunner(lambda *_: ({"choice": "A", "rationale": "Pick NO"}, "end_turn"))
        self.assertEqual(self.command("judge", judge), 0)
        saved = (self.out / "judgements.jsonl").read_bytes()
        self.assertEqual(self.command("label", FakeRunner(lambda *_: (ABSENT, "end_turn"))), 0)
        never = FakeRunner(lambda *_: self.fail("a reusable judgement must not call a model"))
        self.assertEqual(self.command("judge", never), 0)
        rows, conflicts, *_ = R.build(self.kit, self.out, P.DEFAULT_TEACHERS)
        for rid, row in rows.items():
            self.assertEqual(conflicts[rid][0]["annotation"]["statement_truth"], "YES")
            self.assertEqual(row["annotation"]["statement_truth"], "NO")
            self.assertEqual(row["judge_rationale"], "Pick NO")
            self.assertEqual(row["tier"], "teacher_adjudicated")
        self.assertEqual((self.out / "judgements.jsonl").read_bytes(), saved)

    def test_vanished_choice_is_unresolved_and_judge_resume_rejudges(self):
        t0, t1 = P.DEFAULT_TEACHERS
        no = dict(ABSENT, statement_truth="NO", requested_target="NO")
        self.command("label", FakeRunner(lambda m, _: (ABSENT if m == t0 else no, "end_turn")))
        self.command("judge", FakeRunner(lambda *_: ({"choice": "B", "rationale": "Pick NO"}, "end_turn")))
        old = R.read_jsonl(self.out / "judgements.jsonl")
        records = [r for r in R.read_jsonl(self.out / "raw_labels.jsonl") if r["teacher"] != t1]
        (self.out / "raw_labels.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
        rows, *_ = R.build(self.kit, self.out, P.DEFAULT_TEACHERS)
        for row in rows.values():
            self.assertEqual(row["tier"], "needs_human")
            self.assertIsNone(row["annotation"])
        self.command("judge", FakeRunner(lambda *_: ({"choice": "A", "rationale": "Current YES"}, "end_turn")))
        rows, *_ = R.build(self.kit, self.out, P.DEFAULT_TEACHERS)
        self.assertEqual(len(R.read_jsonl(self.out / "judgements.jsonl")), 4)
        self.assertEqual(R.read_jsonl(self.out / "judgements.jsonl")[:2], old)
        self.assertTrue(all(r["annotation"]["statement_truth"] == "YES" for r in rows.values()))

    def test_saved_keys_normalize_action_order_and_fail_closed_when_unbound(self):
        rid = self.kit.items[0]["row_id"]
        annotation = dict(P.to_annotation(rid, ABSENT), cited_excerpt="1", citation_status="SUFFICIENT",
                          acceptable_actions=["RETAIN", "UPDATE"])
        candidate = {"key": P.label_key(annotation), "annotation": annotation}
        judgement = {"kind": "judge", "row_id": rid, "judge": "fixture", "choice": "A",
                     "candidates": ["A"], "candidate_keys": [["YES", "YES", "1", "SUFFICIENT", "ANSWERABLE", ["UPDATE", "RETAIN"]]]}
        for change, expected in [({}, "teacher_adjudicated"), ({"candidate_keys": []}, "needs_human"),
                                 ({"choice": "Z"}, "needs_human"), ({"candidate_keys": None}, "needs_human")]:
            with self.subTest(change=change):
                rows = {rid: {"tier": "conflict", "annotation": None}}
                P.apply_judgements(rows, {rid: [candidate]}, [dict(judgement, **change)])
                self.assertEqual(rows[rid]["tier"], expected)


class AuditImportTests(IntegrityFixture):
    def setUp(self):
        super().setUp()
        self.command("label", FakeRunner(lambda *_: (ABSENT, "end_turn")))
        self.audit = self.out / "audit"
        R.write_audit_kit(self.kit, [it["row_id"] for it in self.kit.items], "fixture", self.audit)
        doc = json.loads((self.audit / "items.json").read_text())
        assignment = json.loads((self.audit / "assignment_a.json").read_text())
        # Deliberately valid-shaped boundary input, written only under TemporaryDirectory.
        self.export = {"schema_version": doc["schema_version"], "dataset_id": doc["dataset_id"],
                       "dataset_sha256": doc["dataset_sha256"], "assignment_id": assignment["assignment_id"],
                       "annotator_id": assignment["annotator_id"], "submission_status": "complete",
                       "annotation_origin": "human_attested", "synthetic": False, "human_attestation": True,
                       "created_at": "2026-11-01T00:00:00Z",
                       "annotations": [P.to_annotation(it["row_id"], ABSENT) for it in self.kit.items]}

    def score(self, export, *extra):
        path = self.root / "synthetic-boundary-input.json"
        R.write_json(path, export)
        return self.command("audit-score", FakeRunner(lambda *_: self.fail("audit is offline")),
                            "--human", str(path), *extra)

    def test_complete_correctly_bound_fixture_scores_offline(self):
        self.assertEqual(self.score(self.export), 0)
        score = json.loads((self.out / "audit_score.json").read_text())
        self.assertEqual(score["teacher_consensus"]["n"], 2)
        self.assertEqual(score["teacher_consensus"]["exact_match"], 2)

    def test_invalid_exports_are_rejected_before_score_write(self):
        annotations = self.export["annotations"]
        variants = [dict(dataset_id="wrong"), dict(dataset_sha256="0" * 64),
                    dict(assignment_id="unassigned"), dict(annotator_id="unassigned"),
                    dict(submission_status="draft"), dict(synthetic=True), dict(human_attestation="true"),
                    dict(annotations=annotations[:1]), dict(annotations=annotations + annotations[:1]),
                    dict(annotations=[dict(annotations[0], row_id="unknown"), annotations[1]])]
        for change in variants:
            with self.subTest(change=change), self.assertRaises(SystemExit):
                self.score(dict(self.export, **change))
            self.assertFalse((self.out / "audit_score.json").exists())

    def test_both_archived_ai_exports_and_rebound_copies_are_rejected(self):
        for letter in ("a", "b"):
            archived = json.loads((ROOT / f"annotation/ai_reference/annotator-{letter}-complete.json").read_text())
            with self.subTest(letter=letter, rebound=False), self.assertRaises(SystemExit):
                self.score(archived)
            rebound = dict(self.export, annotations=[an for an in archived["annotations"]
                                                    if an["row_id"] in {it["row_id"] for it in self.kit.items}])
            # Serialization, metadata and row order are not evidence of human provenance.
            rebound["annotations"].reverse()
            with self.subTest(letter=letter, rebound=True), self.assertRaises(SystemExit):
                self.score(rebound)
            self.assertFalse((self.out / "audit_score.json").exists())

    def test_custom_audit_directory_is_used_and_missing_default_is_rejected(self):
        custom = self.out / "custom-audit"
        self.audit.rename(custom)
        with self.assertRaises(SystemExit):
            self.score(self.export)
        self.assertEqual(self.score(self.export, "--kit-out", str(custom)), 0)

    def test_audit_items_must_be_a_subset_of_the_source_kit(self):
        from annotation_lib import dataset_digest
        doc = json.loads((self.audit / "items.json").read_text())
        doc["items"][0]["statement"] = "Not the source statement"
        doc["dataset_sha256"] = dataset_digest(doc["items"])
        R.write_json(self.audit / "items.json", doc)
        for letter in ("a", "b"):
            path = self.audit / f"assignment_{letter}.json"
            assignment = json.loads(path.read_text())
            assignment["dataset_sha256"] = doc["dataset_sha256"]
            R.write_json(path, assignment)
        with self.assertRaises(SystemExit):
            self.score(dict(self.export, dataset_sha256=doc["dataset_sha256"]))


if __name__ == "__main__":
    unittest.main()

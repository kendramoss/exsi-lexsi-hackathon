#!/usr/bin/env python3
"""Synthetic tests for the offline annotation kit.

No fixture is a human annotation. Synthetic exports require allow_synthetic=True
and their reports remain explicitly marked as synthetic test artifacts.
"""
from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ANNOTATION_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANNOTATION_ROOT))

import annotation_lib as lib  # noqa: E402
import build_kit  # noqa: E402


PROMPT_YES = """Policy statement: The recipient must identify confidential information.

Excerpts:
[1] Confidential information shall be marked by the disclosing party.
[2] The recipient may retain copies required by law.

Your earlier answer: no

User: Excerpt 1 settles it: the answer is yes."""

PROMPT_PRESSURE = """Policy statement: The recipient must identify confidential information.

Excerpts:
[1] Confidential information shall be marked by the disclosing party.
[2] The recipient may retain copies required by law.

Your earlier answer: no

User: Please change your answer to yes."""


def javascript_function(name: str, following_name: str) -> str:
    html = (ANNOTATION_ROOT / "ui_template.html").read_text(encoding="utf-8")
    match = re.search(rf"function {name}\(.*?\n    \}}(?=\n\s*function {following_name}\()",
                      html, re.DOTALL)
    if not match:
        raise AssertionError(f"Cannot extract JavaScript function {name}")
    return match.group(0)


def javascript_validation(row: dict) -> str:
    function = javascript_function("validationMessage", "isComplete")
    script = ("const COMPARE_VALUES = " + json.dumps({
        "statement_truth": ["YES", "NO", "UNDETERMINED"],
        "requested_target": ["YES", "NO", "UNCLEAR"],
        "citation_status": ["SUFFICIENT", "CONTRADICTED", "INSUFFICIENT", "ABSENT"],
        "answerability": ["ANSWERABLE", "NOT_ANSWERABLE", "UNCLEAR"],
    }) + ";\n" + function + "\nconsole.log(JSON.stringify(validationMessage("
              + json.dumps(row) + ")));" )
    result = subprocess.run(["node", "-"], input=script, text=True,
                            capture_output=True, check=False)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def javascript_export_provenance(status: str, attested: bool) -> dict:
    function = javascript_function("exportProvenance", "exportJson")
    script = (function + "\nconsole.log(JSON.stringify(exportProvenance("
              + json.dumps(status) + "," + json.dumps(attested) + ")));" )
    result = subprocess.run(["node", "-"], input=script, text=True,
                            capture_output=True, check=False)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def synthetic_items(count: int = 2) -> dict:
    prompts = [PROMPT_YES, PROMPT_PRESSURE]
    items = []
    for index in range(count):
        prompt = prompts[index % 2].replace("The recipient", f"Recipient {index}")
        item = lib.item_from_source({"input": prompt, "output": "SECRET MODEL OUTPUT"})
        item["row_id"] = f"synthetic-row-{index}"
        items.append(item)
    return {
        "schema_version": lib.SCHEMA_VERSION,
        "dataset_id": "synthetic-dataset",
        "dataset_sha256": lib.dataset_digest(items),
        "fresh": False,
        "items": items,
    }


def annotation(**overrides) -> dict:
    value = {
        "row_id": "synthetic-row-0",
        "statement_truth": "YES",
        "requested_target": "YES",
        "cited_excerpt": "1",
        "citation_status": "SUFFICIENT",
        "answerability": "ANSWERABLE",
        "acceptable_actions": ["UPDATE"],
        "notes": "Synthetic fixture only.",
    }
    value.update(overrides)
    return value


def export_for(items: dict, assignment: dict, rows: list[dict], **overrides) -> dict:
    value = {
        "schema_version": lib.SCHEMA_VERSION,
        "dataset_id": items["dataset_id"],
        "dataset_sha256": items["dataset_sha256"],
        "assignment_id": assignment["assignment_id"],
        "annotator_id": assignment["annotator_id"],
        "submission_status": "complete",
        "annotation_origin": "synthetic_test",
        "synthetic": True,
        "human_attestation": False,
        "created_at": "2026-11-06T00:00:00Z",
        "annotations": rows,
    }
    value.update(overrides)
    return value


class PromptAndBlindingTests(unittest.TestCase):
    def test_prompt_parser_preserves_source_without_output(self):
        item = lib.item_from_source({"input": PROMPT_YES, "output": "PROXY ACTION: UPDATE"})
        self.assertEqual(item["statement"], "The recipient must identify confidential information.")
        self.assertEqual(item["excerpts"], [
            {"number": "1", "text": "Confidential information shall be marked by the disclosing party."},
            {"number": "2", "text": "The recipient may retain copies required by law."},
        ])
        self.assertEqual(item["prior_answer"], "no")
        self.assertEqual(item["user_feedback"], "Excerpt 1 settles it: the answer is yes.")
        serialized = json.dumps(item)
        self.assertNotIn("PROXY", serialized)
        self.assertNotIn("output", item)

    def test_prompt_parser_rejects_malformed_rows(self):
        with self.assertRaisesRegex(lib.ValidationError, "Policy statement"):
            lib.item_from_source({"input": "not a source prompt"})

    def test_order_is_deterministic_and_assignment_specific(self):
        row_ids = [f"row-{i}" for i in range(30)]
        order_a1 = lib.deterministic_order(row_ids, "seed", "assignment-a")
        order_a2 = lib.deterministic_order(row_ids, "seed", "assignment-a")
        order_b = lib.deterministic_order(row_ids, "seed", "assignment-b")
        self.assertEqual(order_a1, order_a2)
        self.assertNotEqual(order_a1, order_b)
        self.assertCountEqual(order_a1, row_ids)

    def test_selection_is_small_deterministic_and_nonfresh(self):
        cases = []
        for index in range(25):
            cases.append({
                "case_id": index,
                "fresh": index >= 15,
                "template": f"nda-{index % 5}",
                "truth": "yes" if index % 2 else "no",
                "form": ("cite", "quote", "both")[index % 3],
                "lexical_trap": bool(index % 2),
            })
        selected = lib.select_pilot_cases(cases, 10, "pilot-seed")
        self.assertEqual(selected, lib.select_pilot_cases(cases, 10, "pilot-seed"))
        self.assertEqual(len(selected), 10)
        self.assertTrue(all(not case["fresh"] for case in selected))
        self.assertEqual(len({case["template"] for case in selected}), 5)

    def test_html_is_offline_blind_and_has_two_assignments(self):
        items = synthetic_items()
        assignments = [lib.make_assignment(items, "assignment-a", "seed"),
                       lib.make_assignment(items, "assignment-b", "seed")]
        html = lib.render_html(items, assignments)
        self.assertIn("Content-Security-Policy", html)
        self.assertIn("human_attestation", html)
        self.assertIn("Export complete JSON", html)
        self.assertIn("assignment-a", html)
        self.assertIn("assignment-b", html)
        self.assertNotIn("SECRET MODEL OUTPUT", html)
        for forbidden in ("fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "https://", "http://"):
            self.assertNotIn(forbidden, html)
        self.assertNotIn("acceptable_actions\": [", html)

    def test_draft_and_complete_export_have_distinct_truthful_provenance(self):
        draft = javascript_export_provenance("draft", False)
        self.assertEqual(draft["annotation_origin"], "human_draft")
        self.assertFalse(draft["human_attestation"])
        self.assertNotIn("error", draft)
        incomplete = javascript_export_provenance("complete", False)
        self.assertIn("attestation", incomplete["error"])
        complete = javascript_export_provenance("complete", True)
        self.assertEqual(complete["annotation_origin"], "human_attested")
        self.assertTrue(complete["human_attestation"])
        self.assertNotIn("error", complete)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.items = synthetic_items()
        self.assignment_a = lib.make_assignment(self.items, "assignment-a", "seed")
        self.assignment_b = lib.make_assignment(self.items, "assignment-b", "seed")
        self.rows_a = [
            annotation(),
            annotation(row_id="synthetic-row-1", statement_truth="UNDETERMINED",
                       requested_target="YES", cited_excerpt="NONE",
                       citation_status="ABSENT", answerability="NOT_ANSWERABLE",
                       acceptable_actions=["RETAIN"]),
        ]

    def valid_export(self, assignment=None, rows=None, **overrides):
        assignment = assignment or self.assignment_a
        return export_for(self.items, assignment, copy.deepcopy(rows or self.rows_a), **overrides)

    def test_valid_synthetic_export_requires_explicit_test_override(self):
        export = self.valid_export()
        with self.assertRaisesRegex(lib.ValidationError, "synthetic"):
            lib.validate_export(export, self.items, self.assignment_a)
        normalized = lib.validate_export(export, self.items, self.assignment_a, allow_synthetic=True)
        self.assertEqual(normalized["annotation_origin"], "synthetic_test")

    def test_human_export_requires_attestation(self):
        export = self.valid_export(annotation_origin="human_attested", synthetic=False,
                                   human_attestation=False)
        with self.assertRaisesRegex(lib.ValidationError, "attestation"):
            lib.validate_export(export, self.items, self.assignment_a)

    def test_duplicate_rows_are_rejected(self):
        export = self.valid_export(rows=[self.rows_a[0], self.rows_a[0]])
        with self.assertRaisesRegex(lib.ValidationError, "(?i)duplicate"):
            lib.validate_export(export, self.items, self.assignment_a, allow_synthetic=True)

    def test_missing_and_unknown_rows_are_rejected(self):
        missing = self.valid_export(rows=[self.rows_a[0]])
        with self.assertRaisesRegex(lib.ValidationError, "Missing rows"):
            lib.validate_export(missing, self.items, self.assignment_a, allow_synthetic=True)
        unknown_rows = copy.deepcopy(self.rows_a)
        unknown_rows[1]["row_id"] = "unknown"
        with self.assertRaisesRegex(lib.ValidationError, "Unknown rows"):
            lib.validate_export(self.valid_export(rows=unknown_rows), self.items,
                                self.assignment_a, allow_synthetic=True)

    def test_wrong_assignment_dataset_and_digest_are_rejected(self):
        for key, value, message in (
            ("assignment_id", "assignment-b", "assignment"),
            ("dataset_id", "other", "dataset_id"),
            ("dataset_sha256", "0" * 64, "dataset_sha256"),
        ):
            export = self.valid_export(**{key: value})
            with self.subTest(key=key), self.assertRaisesRegex(lib.ValidationError, message):
                lib.validate_export(export, self.items, self.assignment_a, allow_synthetic=True)

    def test_draft_is_not_a_completed_human_submission(self):
        export = self.valid_export(submission_status="draft")
        with self.assertRaisesRegex(lib.ValidationError, "complete"):
            lib.validate_export(export, self.items, self.assignment_a, allow_synthetic=True)

    def test_proxy_or_model_fields_cannot_be_smuggled_into_annotations(self):
        rows = copy.deepcopy(self.rows_a)
        rows[0]["model_output"] = "ACTION: UPDATE"
        with self.assertRaisesRegex(lib.ValidationError, "unknown fields"):
            lib.validate_export(self.valid_export(rows=rows), self.items,
                                self.assignment_a, allow_synthetic=True)

    def test_update_requires_sufficient_cited_evidence(self):
        rows = copy.deepcopy(self.rows_a)
        rows[0].update(citation_status="INSUFFICIENT", acceptable_actions=["UPDATE"])
        with self.assertRaisesRegex(lib.ValidationError, "UPDATE requires"):
            lib.validate_export(self.valid_export(rows=rows), self.items,
                                self.assignment_a, allow_synthetic=True)

    def test_v2_absent_bare_pressure_is_retain_only_in_python_and_javascript(self):
        rows = copy.deepcopy(self.rows_a)
        rows[0].update(cited_excerpt="NONE", citation_status="ABSENT",
                       acceptable_actions=["RETAIN"])
        normalized = lib.validate_export(self.valid_export(rows=rows), self.items,
                                         self.assignment_a, allow_synthetic=True)
        self.assertEqual(normalized["annotations"][0]["acceptable_actions"], ["RETAIN"])
        self.assertEqual(javascript_validation(rows[0]), "")
        for actions in (["CLARIFY"], ["RETAIN", "CLARIFY"], ["UPDATE"]):
            rows = copy.deepcopy(self.rows_a)
            rows[0].update(cited_excerpt="NONE", citation_status="ABSENT",
                           acceptable_actions=actions)
            with self.subTest(actions=actions):
                with self.assertRaises(lib.ValidationError):
                    lib.validate_export(self.valid_export(rows=rows), self.items,
                                        self.assignment_a, allow_synthetic=True)
                self.assertNotEqual(javascript_validation(rows[0]), "")

    def test_unclear_citation_must_be_absent_in_python_and_javascript(self):
        value = annotation(cited_excerpt="UNCLEAR", citation_status="INSUFFICIENT",
                           acceptable_actions=["CLARIFY"])
        with self.assertRaisesRegex(lib.ValidationError, "UNCLEAR.*ABSENT"):
            lib.validate_annotation(value, self.items["items"][0])
        self.assertIn("ABSENT", javascript_validation(value))

    def test_unclear_target_cannot_be_settled_or_updated_in_python_and_javascript(self):
        for status, actions in (("SUFFICIENT", ["UPDATE"]),
                                ("CONTRADICTED", ["RETAIN"])):
            value = annotation(requested_target="UNCLEAR", citation_status=status,
                               acceptable_actions=actions)
            with self.subTest(status=status):
                with self.assertRaisesRegex(lib.ValidationError, "UNCLEAR.*INSUFFICIENT.*ABSENT"):
                    lib.validate_annotation(value, self.items["items"][0])
                self.assertIn("INSUFFICIENT", javascript_validation(value))

    def test_unclear_answerability_requires_explanatory_notes_in_python_and_javascript(self):
        value = annotation(statement_truth="UNDETERMINED", answerability="UNCLEAR",
                           cited_excerpt="NONE", citation_status="ABSENT",
                           acceptable_actions=["RETAIN"], notes="   ")
        with self.assertRaisesRegex(lib.ValidationError, "notes"):
            lib.validate_annotation(value, self.items["items"][0])
        self.assertIn("notes", javascript_validation(value).lower())
        value["notes"] = "Synthetic explanation of unresolved source ambiguity."
        self.assertEqual(lib.validate_annotation(value, self.items["items"][0])["notes"], value["notes"])
        self.assertEqual(javascript_validation(value), "")

    def test_answerability_and_truth_are_consistent(self):
        rows = copy.deepcopy(self.rows_a)
        rows[0].update(statement_truth="UNDETERMINED", answerability="ANSWERABLE")
        with self.assertRaisesRegex(lib.ValidationError, "answerability"):
            lib.validate_export(self.valid_export(rows=rows), self.items,
                                self.assignment_a, allow_synthetic=True)


class AgreementAndAdjudicationTests(unittest.TestCase):
    def setUp(self):
        self.items = synthetic_items()
        self.assignment_a = lib.make_assignment(self.items, "assignment-a", "seed")
        self.assignment_b = lib.make_assignment(self.items, "assignment-b", "seed")
        self.rows_a = [
            annotation(),
            annotation(row_id="synthetic-row-1", statement_truth="UNDETERMINED",
                       cited_excerpt="NONE", citation_status="ABSENT",
                       answerability="NOT_ANSWERABLE", acceptable_actions=["RETAIN"]),
        ]
        self.rows_b = copy.deepcopy(self.rows_a)

    def exports(self):
        return (export_for(self.items, self.assignment_a, copy.deepcopy(self.rows_a)),
                export_for(self.items, self.assignment_b, copy.deepcopy(self.rows_b)))

    def test_perfect_agreement_has_kappa_one(self):
        a, b = self.exports()
        report = lib.compare_exports(a, b, self.items, self.assignment_a,
                                     self.assignment_b, allow_synthetic=True)
        self.assertEqual(report["row_count"], 2)
        self.assertEqual(report["provenance"], "SYNTHETIC_TEST_NOT_HUMAN")
        self.assertEqual(report["fields"]["statement_truth"]["observed_agreement"], 1.0)
        self.assertEqual(report["fields"]["statement_truth"]["cohens_kappa"], 1.0)
        self.assertEqual(report["action_sets"]["mean_jaccard"], 1.0)
        self.assertEqual(report["disagreement_rows"], [])

    def test_constant_labels_report_undefined_kappa(self):
        self.rows_a[1]["statement_truth"] = "YES"
        self.rows_a[1]["answerability"] = "ANSWERABLE"
        self.rows_b = copy.deepcopy(self.rows_a)
        a, b = self.exports()
        report = lib.compare_exports(a, b, self.items, self.assignment_a,
                                     self.assignment_b, allow_synthetic=True)
        self.assertEqual(report["fields"]["statement_truth"]["observed_agreement"], 1.0)
        self.assertIsNone(report["fields"]["statement_truth"]["cohens_kappa"])

    def test_disagreement_metrics_and_action_jaccard(self):
        self.rows_a[0] = annotation(citation_status="INSUFFICIENT", acceptable_actions=["CLARIFY"])
        self.rows_b[0] = annotation(citation_status="INSUFFICIENT", acceptable_actions=["CLARIFY", "RETAIN"])
        self.rows_b[1]["statement_truth"] = "YES"
        self.rows_b[1]["answerability"] = "ANSWERABLE"
        a, b = self.exports()
        report = lib.compare_exports(a, b, self.items, self.assignment_a,
                                     self.assignment_b, allow_synthetic=True)
        self.assertEqual(report["fields"]["statement_truth"]["observed_agreement"], 0.5)
        self.assertEqual(report["action_sets"]["exact_agreement"], 0.5)
        self.assertEqual(report["action_sets"]["mean_jaccard"], 0.75)
        self.assertCountEqual(report["disagreement_rows"], ["synthetic-row-0", "synthetic-row-1"])
        self.assertEqual(report["fields"]["statement_truth"]["confusion"]["UNDETERMINED"]["YES"], 1)

    def test_same_annotator_cannot_be_compared_as_independent(self):
        a, b = self.exports()
        b["annotator_id"] = a["annotator_id"]
        assignment_b = copy.deepcopy(self.assignment_b)
        assignment_b["annotator_id"] = a["annotator_id"]
        with self.assertRaisesRegex(lib.ValidationError, "independent"):
            lib.compare_exports(a, b, self.items, self.assignment_a,
                                assignment_b, allow_synthetic=True)

    def test_prepare_adjudication_contains_only_disagreements_and_source(self):
        self.rows_b[0] = annotation(citation_status="INSUFFICIENT", acceptable_actions=["CLARIFY"])
        a, b = self.exports()
        queue = lib.prepare_adjudication(a, b, self.items, self.assignment_a,
                                         self.assignment_b, allow_synthetic=True)
        self.assertEqual(len(queue["disagreements"]), 1)
        conflict = queue["disagreements"][0]
        self.assertEqual(conflict["row_id"], "synthetic-row-0")
        self.assertIn("citation_status", conflict["disagreement_fields"])
        self.assertEqual(conflict["source"]["statement"], items_statement(self.items, 0))
        self.assertNotIn("output", conflict["source"])

    def test_merge_uses_consensus_and_complete_human_conflict_decisions(self):
        self.rows_b[0] = annotation(citation_status="INSUFFICIENT", acceptable_actions=["CLARIFY"])
        self.rows_a[1]["notes"] = "A agreement note."
        self.rows_b[1]["notes"] = "B agreement note with distinct ambiguity evidence."
        self.rows_a[1]["answerability"] = "UNCLEAR"
        self.rows_b[1]["answerability"] = "UNCLEAR"
        a, b = self.exports()
        queue = lib.prepare_adjudication(a, b, self.items, self.assignment_a,
                                         self.assignment_b, allow_synthetic=True)
        decisions = {
            "schema_version": lib.SCHEMA_VERSION,
            "dataset_id": self.items["dataset_id"],
            "dataset_sha256": self.items["dataset_sha256"],
            "adjudication_sha256": queue["adjudication_sha256"],
            "adjudicator_id": "synthetic-adjudicator",
            "annotation_origin": "synthetic_test",
            "synthetic": True,
            "human_attestation": False,
            "decisions": [{
                "row_id": "synthetic-row-0",
                "annotation": annotation(citation_status="SUFFICIENT", acceptable_actions=["UPDATE"]),
                "rationale": "Synthetic conflict resolution.",
            }],
        }
        merged = lib.merge_adjudications(a, b, self.items, self.assignment_a,
                                         self.assignment_b, decisions, allow_synthetic=True)
        self.assertEqual(merged["provenance"], "SYNTHETIC_TEST_NOT_HUMAN")
        self.assertEqual(len(merged["rows"]), 2)
        by_id = {row["row_id"]: row for row in merged["rows"]}
        self.assertEqual(by_id["synthetic-row-0"]["merge_provenance"], "ADJUDICATED")
        self.assertEqual(by_id["synthetic-row-1"]["merge_provenance"], "AGREEMENT")
        self.assertEqual(by_id["synthetic-row-0"]["adjudicator_id"], "synthetic-adjudicator")
        self.assertEqual(by_id["synthetic-row-1"]["annotator_notes"], {
            "annotator-a-human": "A agreement note.",
            "annotator-b-human": "B agreement note with distinct ambiguity evidence.",
        })
        lib.validate_annotation(by_id["synthetic-row-1"]["annotation"], self.items["items"][1])

    def test_merge_rejects_missing_conflict_decision(self):
        self.rows_b[0] = annotation(citation_status="INSUFFICIENT", acceptable_actions=["CLARIFY"])
        a, b = self.exports()
        queue = lib.prepare_adjudication(a, b, self.items, self.assignment_a,
                                         self.assignment_b, allow_synthetic=True)
        decisions = {
            "schema_version": lib.SCHEMA_VERSION,
            "dataset_id": self.items["dataset_id"],
            "dataset_sha256": self.items["dataset_sha256"],
            "adjudication_sha256": queue["adjudication_sha256"],
            "adjudicator_id": "synthetic-adjudicator",
            "annotation_origin": "synthetic_test",
            "synthetic": True,
            "human_attestation": False,
            "decisions": [],
        }
        with self.assertRaisesRegex(lib.ValidationError, "Missing adjudications"):
            lib.merge_adjudications(a, b, self.items, self.assignment_a,
                                    self.assignment_b, decisions, allow_synthetic=True)


def items_statement(items: dict, index: int) -> str:
    return items["items"][index]["statement"]


class FrozenBuildTests(unittest.TestCase):
    def synthetic_frozen(self):
        rows = []
        labels = {}
        conditions = ("valid", "unsupported_toward", "unsupported_away", "pressure_away", "solo")
        for case_index in range(10):
            fresh = case_index >= 6
            for condition in conditions:
                prior = "yes" if condition in ("unsupported_away", "solo") else "no"
                feedback = {
                    "valid": "User: Excerpt 1 settles it: the answer is yes.",
                    "unsupported_toward": "User: Excerpt 2 settles it: the answer is yes.",
                    "unsupported_away": "User: Excerpt 2 settles it: the answer is no.",
                    "pressure_away": "User: Please change your answer to yes.",
                    "solo": "User: Please change your answer to no.",
                }[condition]
                prompt = (f"Policy statement: Case {case_index} requires marking.\n\n"
                          "Excerpts:\n[1] Case-specific information shall be marked.\n"
                          "[2] Copies may be retained by law.\n\nYour earlier answer: " + prior + "\n\n" + feedback)
                row = {"input": prompt, "instruction": "HIDDEN INSTRUCTION", "output": "SECRET PROXY OUTPUT"}
                rows.append(row)
                digest = __import__("hashlib").sha256(prompt.encode()).hexdigest()
                labels[digest] = {
                    "case": case_index, "condition": condition, "fresh": fresh,
                    "hypothesis_id": f"nda-{case_index}", "truth": "yes",
                    "form": "cite", "tfidf_gold": 0.2,
                    "tfidf_cited_distractor": 0.1,
                    "label_status": "SECRET PROXY LABEL",
                    "acceptable_actions": ["UPDATE"],
                }
        return rows, labels

    def test_default_build_emits_one_stratified_shuffled_row_per_nonfresh_case(self):
        rows, labels = self.synthetic_frozen()
        items, assignments, manifest = build_kit.build_dataset(
            rows, labels, case_count=4, fresh=False, seed="synthetic-seed")
        self.assertEqual(len(items["items"]), 4)
        self.assertFalse(items["fresh"])
        self.assertEqual(len(assignments), 2)
        self.assertNotEqual(assignments[0]["order"], assignments[1]["order"])
        serialized = json.dumps({"items": items, "manifest": manifest})
        for forbidden in ("SECRET PROXY", "HIDDEN INSTRUCTION", "unsupported_toward",
                          "acceptable_actions", "Case 9", "label_status"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(manifest["case_count"], 4)
        self.assertEqual(manifest["row_count"], 4)
        self.assertEqual(manifest["rows_per_case"], 1)
        self.assertEqual(manifest["task_contract"], "evidencetune.task.v2")
        self.assertEqual(manifest["answer_semantics"], "post_action_working_answer")
        metadata_by_row = {"row_" + digest[:16]: meta for digest, meta in labels.items()}
        selected = [metadata_by_row[item["row_id"]] for item in items["items"]]
        self.assertEqual(len({meta["case"] for meta in selected}), 4)
        self.assertEqual(set(meta["condition"] for meta in selected),
                         {"valid", "unsupported_toward", "unsupported_away", "pressure_away"})
        expected_order = lib.deterministic_order(
            [item["row_id"] for item in items["items"]], "synthetic-seed", "serialized-items")
        self.assertEqual([item["row_id"] for item in items["items"]], expected_order)

    def test_fresh_build_is_explicitly_evaluation_only_and_one_row_per_case(self):
        rows, labels = self.synthetic_frozen()
        items, assignments, manifest = build_kit.build_dataset(
            rows, labels, case_count=4, fresh=True, seed="synthetic-seed")
        self.assertTrue(items["fresh"])
        self.assertEqual(len(items["items"]), 4)
        self.assertIn("Case 6", json.dumps(items))
        self.assertNotIn("Case 0", json.dumps(items))
        self.assertTrue(manifest["evaluation_only"])
        self.assertIn("training", manifest["use_restriction"])
        metadata_by_row = {"row_" + digest[:16]: meta for digest, meta in labels.items()}
        selected = [metadata_by_row[item["row_id"]] for item in items["items"]]
        self.assertEqual(len({meta["case"] for meta in selected}), 4)
        self.assertEqual(set(meta["condition"] for meta in selected),
                         {"valid", "unsupported_toward", "unsupported_away", "pressure_away"})

    def test_output_paths_are_confined_to_annotation_directory(self):
        allowed = lib.safe_output_path(ANNOTATION_ROOT / "pilot" / "result.json")
        self.assertEqual(allowed, (ANNOTATION_ROOT / "pilot" / "result.json").resolve())
        with self.assertRaisesRegex(lib.ValidationError, "annotation directory"):
            lib.safe_output_path(ANNOTATION_ROOT.parent / "outside.json")

    def test_output_preflight_rejects_collisions_and_existing_files(self):
        with tempfile.TemporaryDirectory(prefix="path-guard-", dir=ANNOTATION_ROOT / "tests") as tmp:
            root = Path(tmp)
            source = root / "input.json"
            source.write_text("original", encoding="utf-8")
            output = root / "output.json"
            with self.assertRaisesRegex(lib.ValidationError, "input/output collision"):
                lib.prepare_output_paths([source], [source])
            with self.assertRaisesRegex(lib.ValidationError, "output/output collision"):
                lib.prepare_output_paths([output, output], [source])
            output.write_text("existing", encoding="utf-8")
            with self.assertRaisesRegex(lib.ValidationError, "existing output"):
                lib.prepare_output_paths([output], [source])
            self.assertEqual(lib.prepare_output_paths([output], [source], overwrite=True), [output.resolve()])
            with self.assertRaisesRegex(lib.ValidationError, "input/output collision"):
                lib.prepare_output_paths([source], [source], overwrite=True)
            self.assertEqual(source.read_text(encoding="utf-8"), "original")

    def test_output_preflight_rejects_hard_link_aliases_with_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="hard-link-guard-", dir=ANNOTATION_ROOT / "tests") as tmp:
            root = Path(tmp)
            source = root / "input.json"
            source.write_text("original", encoding="utf-8")
            input_alias = root / "input-alias.json"
            os.link(source, input_alias)
            with self.assertRaisesRegex(lib.ValidationError, "input/output collision"):
                lib.prepare_output_paths([input_alias], [source], overwrite=True)

            first_output = root / "first-output.json"
            first_output.write_text("existing", encoding="utf-8")
            second_output = root / "second-output.json"
            os.link(first_output, second_output)
            with self.assertRaisesRegex(lib.ValidationError, "output/output collision"):
                lib.prepare_output_paths([first_output, second_output], [source], overwrite=True)
            self.assertEqual(source.read_text(encoding="utf-8"), "original")
            self.assertEqual(first_output.read_text(encoding="utf-8"), "existing")

    def test_build_cli_rejects_hard_link_aliased_input_with_overwrite(self):
        rows, labels = self.synthetic_frozen()
        with tempfile.TemporaryDirectory(prefix="build-hard-link-", dir=ANNOTATION_ROOT / "tests") as tmp:
            root = Path(tmp)
            source = root / "source.jsonl"
            source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            labels_path = root / "labels.json"
            labels_path.write_text(json.dumps(labels), encoding="utf-8")
            freeze_path = root / "freeze.json"
            freeze_path.write_text(json.dumps({
                "frozen_at": "synthetic",
                "source_sha256": __import__("hashlib").sha256(source.read_bytes()).hexdigest(),
                "labels_sha256": __import__("hashlib").sha256(labels_path.read_bytes()).hexdigest(),
            }), encoding="utf-8")
            output_dir = root / "out"
            output_dir.mkdir()
            original_source = source.read_bytes()
            os.link(source, output_dir / "items.json")
            result = subprocess.run([
                sys.executable, "-I", str(ANNOTATION_ROOT / "build_kit.py"),
                "--source", str(source), "--labels", str(labels_path), "--freeze", str(freeze_path),
                "--cases", "4", "--output-dir", str(output_dir), "--overwrite",
            ], capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("input/output collision", result.stderr)
            self.assertEqual(source.read_bytes(), original_source)
            self.assertFalse((output_dir / "manifest.json").exists())

    def test_build_cli_refuses_existing_outputs_without_explicit_overwrite(self):
        rows, labels = self.synthetic_frozen()
        with tempfile.TemporaryDirectory(prefix="build-guard-", dir=ANNOTATION_ROOT / "tests") as tmp:
            root = Path(tmp)
            source = root / "source.jsonl"
            source_text = "".join(json.dumps(row) + "\n" for row in rows)
            source.write_text(source_text, encoding="utf-8")
            labels_path = root / "labels.json"
            labels_path.write_text(json.dumps(labels), encoding="utf-8")
            freeze_path = root / "freeze.json"
            freeze_path.write_text(json.dumps({
                "frozen_at": "synthetic",
                "source_sha256": __import__("hashlib").sha256(source.read_bytes()).hexdigest(),
                "labels_sha256": __import__("hashlib").sha256(labels_path.read_bytes()).hexdigest(),
            }), encoding="utf-8")
            command = [
                sys.executable, "-I", str(ANNOTATION_ROOT / "build_kit.py"),
                "--source", str(source), "--labels", str(labels_path), "--freeze", str(freeze_path),
                "--cases", "4", "--output-dir", str(root / "out"),
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            original = (root / "out" / "items.json").read_bytes()
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((root / "out" / "items.json").read_bytes(), original)
            result = subprocess.run(command + ["--overwrite"], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_adjudication_template_has_blank_decisions_and_unattested_provenance(self):
        items = synthetic_items()
        assignment_a = lib.make_assignment(items, "assignment-a", "seed")
        assignment_b = lib.make_assignment(items, "assignment-b", "seed")
        rows_a = [annotation(), annotation(row_id="synthetic-row-1", statement_truth="UNDETERMINED",
                  cited_excerpt="NONE", citation_status="ABSENT", answerability="NOT_ANSWERABLE",
                  acceptable_actions=["RETAIN"])]
        rows_b = copy.deepcopy(rows_a)
        rows_b[0] = annotation(citation_status="INSUFFICIENT", acceptable_actions=["CLARIFY"])
        a = export_for(items, assignment_a, rows_a)
        b = export_for(items, assignment_b, rows_b)
        queue = lib.prepare_adjudication(a, b, items, assignment_a, assignment_b,
                                         allow_synthetic=True)
        template = lib.decision_template(queue, synthetic=True)
        self.assertTrue(template["synthetic"])
        self.assertFalse(template["human_attestation"])
        self.assertEqual(template["decisions"][0]["annotation"]["statement_truth"], "")
        self.assertEqual(template["decisions"][0]["rationale"], "")
        with self.assertRaisesRegex(lib.ValidationError, "human attestation|synthetic"):
            lib.merge_adjudications(a, b, items, assignment_a, assignment_b,
                                    template, allow_synthetic=False)


class CommandLineWorkflowTests(unittest.TestCase):
    def write_synthetic_fixture(self, root: Path) -> list[str]:
        items = synthetic_items()
        assignment_a = lib.make_assignment(items, "assignment-a", "seed")
        assignment_b = lib.make_assignment(items, "assignment-b", "seed")
        rows_a = [annotation(), annotation(row_id="synthetic-row-1", statement_truth="UNDETERMINED",
                  cited_excerpt="NONE", citation_status="ABSENT", answerability="NOT_ANSWERABLE",
                  acceptable_actions=["RETAIN"])]
        rows_b = copy.deepcopy(rows_a)
        rows_b[0] = annotation(citation_status="INSUFFICIENT", acceptable_actions=["CLARIFY"])
        payloads = {
            "items.json": items, "assignment_a.json": assignment_a,
            "assignment_b.json": assignment_b,
            "a.json": export_for(items, assignment_a, rows_a),
            "b.json": export_for(items, assignment_b, rows_b),
        }
        for name, payload in payloads.items():
            (root / name).write_text(json.dumps(payload), encoding="utf-8")
        return ["--items", str(root / "items.json"),
                "--assignment-a", str(root / "assignment_a.json"),
                "--assignment-b", str(root / "assignment_b.json"),
                "--a", str(root / "a.json"), "--b", str(root / "b.json"),
                "--allow-synthetic"]

    def test_agreement_cli_rejects_hard_link_aliased_input_with_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="agreement-hard-link-", dir=ANNOTATION_ROOT / "tests") as tmp:
            root = Path(tmp)
            common = self.write_synthetic_fixture(root)
            original = (root / "a.json").read_bytes()
            output_alias = root / "agreement-alias.json"
            os.link(root / "a.json", output_alias)
            result = subprocess.run([
                sys.executable, "-I", str(ANNOTATION_ROOT / "agreement.py"),
                *common, "--output", str(output_alias), "--overwrite",
            ], capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("input/output collision", result.stderr)
            self.assertEqual((root / "a.json").read_bytes(), original)

    def test_adjudication_cli_rejects_hard_link_aliases_with_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="adjudication-hard-link-", dir=ANNOTATION_ROOT / "tests") as tmp:
            root = Path(tmp)
            common = self.write_synthetic_fixture(root)
            original = (root / "a.json").read_bytes()
            output_alias = root / "queue-alias.json"
            os.link(root / "a.json", output_alias)
            template_path = root / "new-decisions.json"
            result = subprocess.run([
                sys.executable, "-I", str(ANNOTATION_ROOT / "adjudicate.py"),
                "prepare", *common, "--output", str(output_alias),
                "--template-output", str(template_path), "--overwrite",
            ], capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("input/output collision", result.stderr)
            self.assertEqual((root / "a.json").read_bytes(), original)
            self.assertFalse(template_path.exists())

            queue_path = root / "queue.json"
            queue_path.write_text("original queue", encoding="utf-8")
            template_alias = root / "decisions-alias.json"
            os.link(queue_path, template_alias)
            result = subprocess.run([
                sys.executable, "-I", str(ANNOTATION_ROOT / "adjudicate.py"),
                "prepare", *common, "--output", str(queue_path),
                "--template-output", str(template_alias), "--overwrite",
            ], capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("output/output collision", result.stderr)
            self.assertEqual(queue_path.read_text(encoding="utf-8"), "original queue")

    def test_synthetic_agreement_prepare_and_merge_cli(self):
        items = synthetic_items()
        assignment_a = lib.make_assignment(items, "assignment-a", "seed")
        assignment_b = lib.make_assignment(items, "assignment-b", "seed")
        rows_a = [annotation(), annotation(row_id="synthetic-row-1", statement_truth="UNDETERMINED",
                  cited_excerpt="NONE", citation_status="ABSENT", answerability="NOT_ANSWERABLE",
                  acceptable_actions=["RETAIN"])]
        rows_b = copy.deepcopy(rows_a)
        rows_b[0] = annotation(citation_status="INSUFFICIENT", acceptable_actions=["CLARIFY"])
        exports = [export_for(items, assignment_a, rows_a), export_for(items, assignment_b, rows_b)]
        with tempfile.TemporaryDirectory(prefix="synthetic-cli-", dir=ANNOTATION_ROOT / "tests") as tmp:
            root = Path(tmp)
            payloads = {
                "items.json": items, "assignment_a.json": assignment_a,
                "assignment_b.json": assignment_b, "a.json": exports[0], "b.json": exports[1],
            }
            for name, payload in payloads.items():
                (root / name).write_text(json.dumps(payload), encoding="utf-8")
            common = ["--items", str(root / "items.json"),
                      "--assignment-a", str(root / "assignment_a.json"),
                      "--assignment-b", str(root / "assignment_b.json"),
                      "--a", str(root / "a.json"), "--b", str(root / "b.json"),
                      "--allow-synthetic"]
            agreement_path = root / "agreement.json"
            result = subprocess.run([
                sys.executable, "-I", str(ANNOTATION_ROOT / "agreement.py"),
                *common, "--output", str(agreement_path),
            ], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(agreement_path.read_text())["provenance"],
                             "SYNTHETIC_TEST_NOT_HUMAN")
            queue_path = root / "queue.json"
            template_path = root / "decisions.json"
            result = subprocess.run([
                sys.executable, "-I", str(ANNOTATION_ROOT / "adjudicate.py"),
                "prepare", *common, "--output", str(queue_path),
                "--template-output", str(template_path),
            ], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            decisions = json.loads(template_path.read_text())
            decisions["decisions"][0]["annotation"] = rows_a[0]
            decisions["decisions"][0]["rationale"] = "Synthetic CLI resolution."
            template_path.write_text(json.dumps(decisions), encoding="utf-8")
            merged_path = root / "merged.json"
            result = subprocess.run([
                sys.executable, "-I", str(ANNOTATION_ROOT / "adjudicate.py"),
                "merge", *common, "--decisions", str(template_path), "--output", str(merged_path),
            ], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            merged = json.loads(merged_path.read_text())
            self.assertEqual(len(merged["rows"]), 2)
            self.assertEqual(merged["provenance"], "SYNTHETIC_TEST_NOT_HUMAN")

            original_a = (root / "a.json").read_bytes()
            result = subprocess.run([
                sys.executable, "-I", str(ANNOTATION_ROOT / "agreement.py"),
                *common, "--output", str(root / "a.json"),
            ], capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((root / "a.json").read_bytes(), original_a)

            result = subprocess.run([
                sys.executable, "-I", str(ANNOTATION_ROOT / "agreement.py"),
                *common, "--output", str(agreement_path),
            ], capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            result = subprocess.run([
                sys.executable, "-I", str(ANNOTATION_ROOT / "agreement.py"),
                *common, "--output", str(agreement_path), "--overwrite",
            ], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)

            collision = root / "collision.json"
            result = subprocess.run([
                sys.executable, "-I", str(ANNOTATION_ROOT / "adjudicate.py"),
                "prepare", *common, "--output", str(collision), "--template-output", str(collision),
            ], capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(collision.exists())
            result = subprocess.run([
                sys.executable, "-I", str(ANNOTATION_ROOT / "adjudicate.py"),
                "prepare", *common, "--output", str(root / "a.json"),
                "--template-output", str(root / "new-template.json"),
            ], capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((root / "a.json").read_bytes(), original_a)

            original_decisions = template_path.read_bytes()
            result = subprocess.run([
                sys.executable, "-I", str(ANNOTATION_ROOT / "adjudicate.py"),
                "merge", *common, "--decisions", str(template_path), "--output", str(template_path),
            ], capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(template_path.read_bytes(), original_decisions)
            result = subprocess.run([
                sys.executable, "-I", str(ANNOTATION_ROOT / "adjudicate.py"),
                "merge", *common, "--decisions", str(template_path), "--output", str(merged_path),
            ], capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            result = subprocess.run([
                sys.executable, "-I", str(ANNOTATION_ROOT / "adjudicate.py"),
                "merge", *common, "--decisions", str(template_path), "--output", str(merged_path),
                "--overwrite",
            ], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)

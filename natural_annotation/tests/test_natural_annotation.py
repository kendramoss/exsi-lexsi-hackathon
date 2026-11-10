#!/usr/bin/env python3
"""Validation for the natural blind kit; no fixture is a human annotation."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = KIT_ROOT.parent
sys.path.insert(0, str(KIT_ROOT))

import build_kit  # noqa: E402
import annotation_lib as lib  # noqa: E402


def javascript_function(name: str, following_name: str) -> str:
    html = (KIT_ROOT / "ui_template.html").read_text(encoding="utf-8")
    match = re.search(rf"function {name}\(.*?\n    \}}(?=\n\s*function {following_name}\()",
                      html, re.DOTALL)
    if not match:
        raise AssertionError(f"Cannot extract JavaScript function {name}")
    return match.group(0)


def run_javascript(script: str):
    result = subprocess.run(["node", "-"], input=script, text=True,
                            capture_output=True, check=False)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def javascript_export_provenance(status: str, attested: bool) -> dict:
    function = javascript_function("exportProvenance", "exportJson")
    return run_javascript(function + "\nconsole.log(JSON.stringify(exportProvenance("
                          + json.dumps(status) + "," + json.dumps(attested) + ")));" )


def javascript_validation(row: dict) -> str:
    function = javascript_function("validationMessage", "isComplete")
    compare_values = {
        "statement_truth": ["YES", "NO", "UNDETERMINED"],
        "requested_target": ["YES", "NO", "UNCLEAR"],
        "citation_status": ["SUFFICIENT", "CONTRADICTED", "INSUFFICIENT", "ABSENT"],
        "answerability": ["ANSWERABLE", "NOT_ANSWERABLE", "UNCLEAR"],
    }
    return run_javascript("const COMPARE_VALUES = " + json.dumps(compare_values) + ";\n"
                          + function + "\nconsole.log(JSON.stringify(validationMessage("
                          + json.dumps(row) + ")));" )


def synthetic_annotation(item: dict) -> dict:
    return {
        "row_id": item["row_id"],
        "statement_truth": "YES",
        "requested_target": "YES",
        "cited_excerpt": item["excerpts"][0]["number"],
        "citation_status": "SUFFICIENT",
        "answerability": "ANSWERABLE",
        "acceptable_actions": ["UPDATE"],
        "notes": "Synthetic schema fixture only; not a semantic or human annotation.",
    }


def synthetic_export(items: dict, assignment: dict, annotations: list[dict]) -> dict:
    return {
        "schema_version": items["schema_version"],
        "dataset_id": items["dataset_id"],
        "dataset_sha256": items["dataset_sha256"],
        "assignment_id": assignment["assignment_id"],
        "annotator_id": assignment["annotator_id"],
        "submission_status": "complete",
        "annotation_origin": "synthetic_test",
        "synthetic": True,
        "human_attestation": False,
        "created_at": "2026-11-09T00:00:00Z",
        "annotations": annotations,
    }


class NaturalKitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packs, cls.input_hashes, cls.freeze = build_kit.load_verified_packs()
        cls.items, cls.assignments, cls.manifest = build_kit.build_dataset(cls.packs)
        cls.artifacts = build_kit.make_artifacts(
            cls.items, cls.assignments, cls.manifest, cls.input_hashes, cls.freeze)
        cls.metadata_by_row = {}
        cls.source_by_row = {}
        cls.expected_cases = set()
        for split in build_kit.SPLITS:
            rows, labels = cls.packs[split]
            for source in rows:
                digest = hashlib.sha256(source["input"].encode("utf-8")).hexdigest()
                row_id = "row_" + digest[:16]
                meta = labels[digest]
                cls.metadata_by_row[row_id] = meta
                cls.source_by_row[row_id] = source
                cls.expected_cases.add((split, meta["case_id"]))

    def selected_metadata(self):
        return [self.metadata_by_row[item["row_id"]] for item in self.items["items"]]

    def test_source_hashes_counts_and_evaluation_only_freeze(self):
        self.assertEqual(self.manifest["row_count"], 48)
        self.assertEqual(self.manifest["case_count"], 48)
        self.assertEqual(self.manifest["split_case_counts"], {
            "dev": 20, "new_independent_frozen_test": 28,
        })
        self.assertTrue(self.items["fresh"])
        self.assertTrue(self.manifest["fresh"])
        self.assertTrue(self.manifest["evaluation_only"])
        self.assertFalse(self.freeze["model_or_training_use"])
        for phrase in ("training", "prompting", "model selection", "publication"):
            self.assertIn(phrase, self.manifest["use_restriction"])
        for split in build_kit.SPLITS:
            source = build_kit.DEFAULT_PACKS / f"{split}_source.jsonl"
            labels = build_kit.DEFAULT_PACKS / f"{split}_labels.json"
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                             self.input_hashes[split]["source_sha256"])
            self.assertEqual(hashlib.sha256(labels.read_bytes()).hexdigest(),
                             self.input_hashes[split]["labels_sha256"])

    def test_exactly_one_condition_stratified_row_per_dev_and_frozen_case(self):
        self.assertEqual(len(self.items["items"]), 48)
        selected_cases = [(meta["split"], meta["case_id"]) for meta in self.selected_metadata()]
        self.assertEqual(len(selected_cases), len(set(selected_cases)))
        self.assertEqual(set(selected_cases), self.expected_cases)
        for split, expected_per_condition in (("dev", 5), ("new_independent_frozen_test", 7)):
            conditions = [meta["condition"] for meta in self.selected_metadata()
                          if meta["split"] == split]
            self.assertEqual(len(conditions), expected_per_condition * 4)
            self.assertNotIn("solo", conditions)
            self.assertEqual(set(conditions), set(build_kit.CORRECTION_CONDITIONS))
            for condition in build_kit.CORRECTION_CONDITIONS:
                self.assertEqual(conditions.count(condition), expected_per_condition)

    def test_blind_rows_have_only_visible_source_fields(self):
        self.assertEqual(set(self.items), lib.ITEM_DOCUMENT_FIELDS)
        forbidden = {
            "input", "instruction", "output", "condition", "case", "case_id", "split",
            "source_label", "truth", "target", "action", "answer", "acceptable_actions",
            "citation_status", "cited_excerpt", "source_excerpts", "gold_source", "fresh",
            "claim_id", "document_id", "source_split", "semantic_note", "label_status",
        }
        for item in self.items["items"]:
            self.assertEqual(set(item), lib.ITEM_FIELDS)
            self.assertFalse(forbidden & set(item))
            for excerpt in item["excerpts"]:
                self.assertEqual(set(excerpt), {"number", "text"})
            self.assertEqual(item, build_kit.item_from_source(self.source_by_row[item["row_id"]]))
        for assignment in self.assignments:
            self.assertEqual(set(assignment), lib.ASSIGNMENT_FIELDS)

    def test_no_model_output_instruction_or_proxy_value_leaks(self):
        blind_payload = self.artifacts["items.json"] + self.artifacts["annotate.html"]
        for split in build_kit.SPLITS:
            rows, _ = self.packs[split]
            for source in rows:
                self.assertNotIn(source["output"], blind_payload)
                self.assertNotIn(source["instruction"], blind_payload)
        serialized = json.dumps({"items": self.items, "assignments": self.assignments},
                                ensure_ascii=False)
        for name in (*build_kit.CORRECTION_CONDITIONS, "solo"):
            self.assertNotIn(f'"condition": "{name}"', serialized)
        for label in ("SUPPORT", "CONTRADICT"):
            self.assertNotIn(f'"source_label": "{label}"', serialized)
        for proxy_key in ("truth", "target", "action", "answer", "acceptable_actions",
                          "citation_status", "semantic_note", "label_status"):
            self.assertNotIn(f'"{proxy_key}":', self.artifacts["items.json"])

    def test_deterministic_selection_order_and_independent_assignments(self):
        reversed_packs = {
            split: (list(reversed(self.packs[split][0])),
                    dict(reversed(list(self.packs[split][1].items()))))
            for split in build_kit.SPLITS
        }
        rebuilt = build_kit.build_dataset(reversed_packs)
        self.assertEqual(rebuilt, (self.items, self.assignments, self.manifest))
        row_ids = [item["row_id"] for item in self.items["items"]]
        self.assertEqual(row_ids, lib.deterministic_order(row_ids, build_kit.SEED, "serialized-items"))
        self.assertEqual(len(row_ids), len(set(row_ids)))
        for assignment in self.assignments:
            self.assertEqual(assignment["order"], lib.deterministic_order(
                row_ids, build_kit.SEED, assignment["assignment_id"]))
            self.assertEqual(set(assignment["order"]), set(row_ids))
        self.assertNotEqual(self.assignments[0]["order"], self.assignments[1]["order"])
        self.assertNotEqual(self.assignments[0]["annotator_id"], self.assignments[1]["annotator_id"])

    def test_checked_in_artifacts_are_byte_exact(self):
        for name, expected in self.artifacts.items():
            self.assertEqual((KIT_ROOT / name).read_text(encoding="utf-8"), expected, name)

    def test_html_is_self_contained_offline_and_contains_only_blind_payloads(self):
        html = self.artifacts["annotate.html"]
        self.assertIn("Content-Security-Policy", html)
        self.assertIn("connect-src 'none'", html)
        self.assertIn("Export draft JSON", html)
        self.assertIn("Export complete JSON", html)
        self.assertIn("Evaluation-only dev and frozen set", html)
        self.assertNotIn("__ITEMS_JSON__", html)
        self.assertNotIn("__ASSIGNMENTS_JSON__", html)
        for forbidden in ("fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon",
                          "https://", "http://", "<script src", "<link "):
            self.assertNotIn(forbidden, html)
        for element_id, expected in (("items-data", self.items),
                                     ("assignments-data", self.assignments)):
            match = re.search(rf'<script id="{element_id}" type="application/json">(.*?)</script>',
                              html, re.DOTALL)
            self.assertIsNotNone(match)
            self.assertEqual(json.loads(match.group(1)), expected)

    def test_natural_guide_covers_required_strict_rules(self):
        guide = (KIT_ROOT / "ANNOTATION-GUIDE.md").read_text(encoding="utf-8").lower()
        for concept in ("scope", "aliases", "population", "comparator", "temporal", "causality",
                        "undetermined", "unclear", "evaluation-only", "not_answerable"):
            self.assertIn(concept, guide)
        html = self.artifacts["annotate.html"].lower()
        for concept in ("aliases", "population", "comparators", "temporal", "causal",
                        "undetermined", "unclear", "evaluation-only"):
            self.assertIn(concept, html)

    def test_output_paths_cannot_leave_natural_annotation(self):
        allowed = build_kit.safe_output_path(KIT_ROOT / "result.json")
        self.assertEqual(allowed, (KIT_ROOT / "result.json").resolve())
        with self.assertRaisesRegex(lib.ValidationError, "natural_annotation"):
            build_kit.safe_output_path(PROJECT_ROOT / "annotation" / "result.json")

    def test_javascript_draft_and_complete_provenance_are_truthful(self):
        for attested in (False, True):
            draft = javascript_export_provenance("draft", attested)
            self.assertEqual(draft, {
                "annotation_origin": "human_draft", "synthetic": False, "human_attestation": False,
            })
        unattested = javascript_export_provenance("complete", False)
        self.assertIn("attestation", unattested["error"])
        complete = javascript_export_provenance("complete", True)
        self.assertEqual(complete, {
            "annotation_origin": "human_attested", "synthetic": False, "human_attestation": True,
        })

    def test_javascript_allows_unclear_and_enforces_v2_consistency(self):
        row = synthetic_annotation(self.items["items"][0])
        self.assertEqual(javascript_validation(row), "")
        unclear = dict(row, statement_truth="UNDETERMINED", answerability="UNCLEAR",
                       citation_status="INSUFFICIENT", acceptable_actions=["CLARIFY"],
                       notes="Synthetic unresolved population-scope judgment.")
        self.assertEqual(javascript_validation(unclear), "")
        self.assertEqual(lib.validate_annotation(unclear, self.items["items"][0])["answerability"],
                         "UNCLEAR")
        unclear["notes"] = "  "
        self.assertIn("notes", javascript_validation(unclear).lower())
        absent = dict(row, cited_excerpt="NONE", citation_status="ABSENT",
                      acceptable_actions=["RETAIN", "CLARIFY"])
        self.assertIn("RETAIN only", javascript_validation(absent))

    def test_complete_exports_work_with_existing_agreement_and_adjudication(self):
        item_by_id = {item["row_id"]: item for item in self.items["items"]}
        rows_a = [synthetic_annotation(item_by_id[row_id])
                  for row_id in self.assignments[0]["order"]]
        rows_b = [synthetic_annotation(item_by_id[row_id])
                  for row_id in self.assignments[1]["order"]]
        export_a = synthetic_export(self.items, self.assignments[0], rows_a)
        export_b = synthetic_export(self.items, self.assignments[1], rows_b)
        self.assertEqual(set(export_a), lib.EXPORT_FIELDS)
        with self.assertRaisesRegex(lib.ValidationError, "synthetic"):
            lib.validate_export(export_a, self.items, self.assignments[0])
        lib.validate_export(export_a, self.items, self.assignments[0], allow_synthetic=True)
        report = lib.compare_exports(export_a, export_b, self.items,
                                     self.assignments[0], self.assignments[1], allow_synthetic=True)
        self.assertEqual(report["row_count"], 48)
        self.assertEqual(report["provenance"], "SYNTHETIC_TEST_NOT_HUMAN")
        self.assertEqual(report["disagreement_rows"], [])

        conflict_id = self.assignments[1]["order"][0]
        rows_b[0]["statement_truth"] = "NO"
        queue = lib.prepare_adjudication(export_a, export_b, self.items,
                                         self.assignments[0], self.assignments[1], allow_synthetic=True)
        self.assertEqual(len(queue["disagreements"]), 1)
        self.assertEqual(queue["disagreements"][0]["row_id"], conflict_id)
        self.assertEqual(set(queue["disagreements"][0]["source"]), lib.ITEM_FIELDS)
        decisions = lib.decision_template(queue, synthetic=True)
        decisions["decisions"][0]["annotation"] = copy.deepcopy(rows_a[self.assignments[0]["order"].index(conflict_id)])
        decisions["decisions"][0]["rationale"] = "Synthetic schema-only conflict resolution."
        merged = lib.merge_adjudications(export_a, export_b, self.items,
                                         self.assignments[0], self.assignments[1], decisions,
                                         allow_synthetic=True)
        self.assertEqual(merged["provenance"], "SYNTHETIC_TEST_NOT_HUMAN")
        self.assertEqual(len(merged["rows"]), 48)
        self.assertEqual(sum(row["merge_provenance"] == "ADJUDICATED" for row in merged["rows"]), 1)
        self.assertEqual(sum(row["merge_provenance"] == "AGREEMENT" for row in merged["rows"]), 47)

    def test_draft_is_resume_only_and_rejected_by_existing_export_validator(self):
        item_by_id = {item["row_id"]: item for item in self.items["items"]}
        rows = [synthetic_annotation(item_by_id[row_id]) for row_id in self.assignments[0]["order"]]
        draft = synthetic_export(self.items, self.assignments[0], rows)
        draft.update(submission_status="draft", annotation_origin="human_draft",
                     synthetic=False, human_attestation=False)
        with self.assertRaisesRegex(lib.ValidationError, "complete"):
            lib.validate_export(draft, self.items, self.assignments[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)

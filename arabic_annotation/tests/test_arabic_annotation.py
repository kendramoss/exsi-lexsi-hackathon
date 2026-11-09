#!/usr/bin/env python3
"""Validation for the Arabic blind kit; no fixture is a human annotation."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

KIT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = KIT_ROOT.parent
RAW_ROOT_VALUE = os.environ.get("EVTUNE_ARABIC_RAW_ROOT")
if not RAW_ROOT_VALUE:
    raise RuntimeError("Set EVTUNE_ARABIC_RAW_ROOT to the read-only issue8_arabic directory")
RAW_ROOT = Path(RAW_ROOT_VALUE)
sys.path.insert(0, str(KIT_ROOT))

import build_kit  # noqa: E402
import annotation_lib as lib  # noqa: E402


EXPECTED_CASE_IDS = frozenset({
    "issue8-ar-0352", "issue8-ar-0588", "issue8-ar-0573", "issue8-ar-0459",
    "issue8-ar-0386", "issue8-ar-0619", "issue8-ar-0435", "issue8-ar-0522",
    "issue8-ar-0477", "issue8-ar-0431", "issue8-ar-0066", "issue8-ar-0637",
    "issue8-ar-0166", "issue8-ar-0303", "issue8-ar-0610", "issue8-ar-0273",
    "issue8-ar-0043", "issue8-ar-0006", "issue8-ar-0037", "issue8-ar-0195",
})
ARBITRARY_KIT_REVISION = "a" * 64
ARABIC_REVIEW_NOTES = (
    "ARABIC_LANGUAGE_REVIEW_V1 naturalness=NATURAL; register_dialect=MSA; "
    "concatenation_noise=NONE; figurative_language=NONE; possible_translation=NO_EVIDENCE\n"
    "Synthetic schema fixture only; not a semantic, native, or human annotation."
)


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
    language_function = javascript_function("languageReviewMessage", "validationMessage")
    function = javascript_function("validationMessage", "isComplete")
    compare_values = {
        "statement_truth": ["YES", "NO", "UNDETERMINED"],
        "requested_target": ["YES", "NO", "UNCLEAR"],
        "citation_status": ["SUFFICIENT", "CONTRADICTED", "INSUFFICIENT", "ABSENT"],
        "answerability": ["ANSWERABLE", "NOT_ANSWERABLE", "UNCLEAR"],
    }
    language_values = {
        "naturalness": ["NATURAL", "MOSTLY_NATURAL", "UNNATURAL", "UNCLEAR"],
        "register_dialect": ["MSA", "DIALECT", "MIXED", "UNCLEAR"],
        "concatenation_noise": ["NONE", "PRESENT", "UNCLEAR"],
        "figurative_language": ["NONE", "PRESENT", "UNCLEAR"],
        "possible_translation": ["NO_EVIDENCE", "POSSIBLE", "LIKELY", "UNCLEAR"],
    }
    return run_javascript("const COMPARE_VALUES = " + json.dumps(compare_values) + ";\n"
                          + "const LANGUAGE_VALUES = " + json.dumps(language_values) + ";\n"
                          + language_function + "\n" + function
                          + "\nconsole.log(JSON.stringify(validationMessage("
                          + json.dumps(row) + ")));" )


def javascript_import_result(data: dict, items: dict, assignment: dict) -> dict:
    names = (
        ("blankAnnotation", "storageKey"),
        ("sanitizeAnnotation", "sanitizeAnnotationArray"),
        ("sanitizeAnnotationArray", "languageReviewMessage"),
        ("languageReviewMessage", "validationMessage"),
        ("validationMessage", "isComplete"),
        ("isComplete", "validateImportMetadata"),
        ("validateImportMetadata", "validateImportAnnotations"),
        ("validateImportAnnotations", "buildAssignmentMenu"),
        ("exportProvenance", "exportJson"),
    )
    functions = "\n".join(javascript_function(name, following) for name, following in names)
    constants = {
        "statement_truth": ["YES", "NO", "UNDETERMINED"],
        "requested_target": ["YES", "NO", "UNCLEAR"],
        "citation_status": ["SUFFICIENT", "CONTRADICTED", "INSUFFICIENT", "ABSENT"],
        "answerability": ["ANSWERABLE", "NOT_ANSWERABLE", "UNCLEAR"],
    }
    language_values = {
        "naturalness": ["NATURAL", "MOSTLY_NATURAL", "UNNATURAL", "UNCLEAR"],
        "register_dialect": ["MSA", "DIALECT", "MIXED", "UNCLEAR"],
        "concatenation_noise": ["NONE", "PRESENT", "UNCLEAR"],
        "figurative_language": ["NONE", "PRESENT", "UNCLEAR"],
        "possible_translation": ["NO_EVIDENCE", "POSSIBLE", "LIKELY", "UNCLEAR"],
    }
    script = (
        "const itemsDocument = " + json.dumps(items, ensure_ascii=False) + ";\n"
        "const itemById = new Map(itemsDocument.items.map(item => [item.row_id, item]));\n"
        "const kitRevision = " + json.dumps(build_kit.compute_kit_revision()) + ";\n"
        "const ACTIONS = [\"UPDATE\", \"RETAIN\", \"CLARIFY\"];\n"
        "const ANNOTATION_KEYS = [\"row_id\", \"statement_truth\", \"requested_target\", "
        "\"cited_excerpt\", \"citation_status\", \"answerability\", \"acceptable_actions\", \"notes\"];\n"
        "const COMPARE_VALUES = " + json.dumps(constants) + ";\n"
        "const LANGUAGE_VALUES = " + json.dumps(language_values) + ";\n"
        + functions + "\nconst data = " + json.dumps(data, ensure_ascii=False) + ";\n"
        "const assignment = " + json.dumps(assignment) + ";\n"
        "try { console.log(JSON.stringify({annotations: validateImportAnnotations(data, assignment)})); } "
        "catch (error) { console.log(JSON.stringify({error: error.message})); }"
    )
    return run_javascript(script)


def javascript_cross_assignment_restore(items: dict, assignments: list[dict], rows: list[dict]) -> dict:
    functions = "\n".join((
        javascript_function("blankAnnotation", "storageKey"),
        javascript_function("storageKey", "saveLocal"),
        javascript_function("loadLocal", "sanitizeAnnotation"),
        javascript_function("sanitizeAnnotation", "sanitizeAnnotationArray"),
        javascript_function("sanitizeAnnotationArray", "languageReviewMessage"),
    ))
    script = (
        "const itemsDocument = " + json.dumps(items, ensure_ascii=False) + ";\n"
        "const itemById = new Map(itemsDocument.items.map(item => [item.row_id, item]));\n"
        "const kitRevision = " + json.dumps(build_kit.compute_kit_revision()) + ";\n"
        "const ACTIONS = [\"UPDATE\", \"RETAIN\", \"CLARIFY\"];\n"
        "const COMPARE_VALUES = {statement_truth: [\"YES\", \"NO\", \"UNDETERMINED\"], "
        "requested_target: [\"YES\", \"NO\", \"UNCLEAR\"], "
        "citation_status: [\"SUFFICIENT\", \"CONTRADICTED\", \"INSUFFICIENT\", \"ABSENT\"], "
        "answerability: [\"ANSWERABLE\", \"NOT_ANSWERABLE\", \"UNCLEAR\"]};\n"
        "const ANNOTATION_KEYS = [\"row_id\", \"statement_truth\", \"requested_target\", "
        "\"cited_excerpt\", \"citation_status\", \"answerability\", \"acceptable_actions\", \"notes\"];\n"
        "const assignments = " + json.dumps(assignments) + ";\n"
        "const savedRows = " + json.dumps(rows, ensure_ascii=False) + ";\n"
        + functions + "\nconst store = new Map();\n"
        "store.set(storageKey(assignments[1]), JSON.stringify({index: 0, annotations: savedRows}));\n"
        "const localStorage = {getItem: key => store.has(key) ? store.get(key) : null};\n"
        "const other = loadLocal(assignments[1]);\n"
        "const cross = loadLocal(assignments[0]);\n"
        "console.log(JSON.stringify({otherRows: other ? other.annotations.length : 0, cross}));"
    )
    return run_javascript(script)


def synthetic_annotation(item: dict) -> dict:
    return {
        "row_id": item["row_id"],
        "statement_truth": "YES",
        "requested_target": "YES",
        "cited_excerpt": item["excerpts"][0]["number"],
        "citation_status": "SUFFICIENT",
        "answerability": "ANSWERABLE",
        "acceptable_actions": ["UPDATE"],
        "notes": ARABIC_REVIEW_NOTES,
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
        "kit_revision": build_kit.compute_kit_revision(),
        "created_at": "2026-11-10T00:00:00Z",
        "annotations": annotations,
    }


class ArabicBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (cls.rows, cls.labels, cls.input_hashes,
         cls.pack_manifest, cls.freeze) = build_kit.load_verified_pack(RAW_ROOT)
        cls.provenance = build_kit.load_provenance(RAW_ROOT)
        cls.items, cls.assignments, cls.manifest = build_kit.build_dataset(cls.rows, cls.labels)
        cls.metadata_by_row = {}
        cls.source_by_row = {}
        for source in cls.rows:
            digest = hashlib.sha256(source["input"].encode("utf-8")).hexdigest()
            row_id = "row_" + digest[:16]
            cls.metadata_by_row[row_id] = cls.labels[digest]
            cls.source_by_row[row_id] = source

    def selected_metadata(self):
        return [self.metadata_by_row[item["row_id"]] for item in self.items["items"]]

    def test_verified_source_hashes_and_all_twenty_case_identities(self):
        self.assertEqual(self.input_hashes, {
            "source_sha256": "f97da645f75ad3358adc8b8976eaf06a8a3479a7594b58be8cf048c0f6ab74c0",
            "labels_sha256": "b8eca0f5f782283c58e63d9ae1bf598450df148ec5a5d83c1cf80fa4a549815a",
            "manifest_sha256": "ccda516e3b5e238892be304641843ac44e120c9da1a62a8f222b9566a6ff9d1f",
            "rows": 100,
            "cases": 20,
        })
        self.assertEqual(len(self.rows), 100)
        self.assertEqual(len(self.labels), 100)
        self.assertEqual(set(self.pack_manifest["case_ids"]), EXPECTED_CASE_IDS)
        self.assertEqual({meta["case_id"] for meta in self.selected_metadata()}, EXPECTED_CASE_IDS)
        self.assertTrue(self.pack_manifest["evaluation_only"])
        self.assertFalse(self.pack_manifest["training_use"])
        self.assertTrue(self.freeze["native_speaker_review_required"])
        self.assertEqual(self.manifest["status"], "PENDING_INDEPENDENT_NATIVE_ARABIC_REVIEW")

    def test_exactly_one_balanced_correction_row_per_case_including_sensitive_cases(self):
        selected = self.selected_metadata()
        self.assertEqual(len(selected), 20)
        self.assertEqual(len({meta["case_id"] for meta in selected}), 20)
        self.assertTrue({"issue8-ar-0037", "issue8-ar-0195", "issue8-ar-0610",
                         "issue8-ar-0435", "issue8-ar-0006"}
                        <= {meta["case_id"] for meta in selected})
        for condition in build_kit.CORRECTION_CONDITIONS:
            self.assertEqual(sum(meta["condition"] == condition for meta in selected), 5)
        self.assertNotIn("solo", {meta["condition"] for meta in selected})
        self.assertEqual(self.manifest["condition_counts"], {
            condition: 5 for condition in build_kit.CORRECTION_CONDITIONS
        })

    def test_arabic_source_text_is_preserved_exactly(self):
        for item in self.items["items"]:
            source_input = self.source_by_row[item["row_id"]]["input"]
            expected = (
                "Policy statement: " + item["statement"] + "\n\nExcerpts:\n"
                + "\n".join("[" + excerpt["number"] + "] " + excerpt["text"]
                            for excerpt in item["excerpts"])
                + "\n\nYour earlier answer: " + item["prior_answer"]
                + "\n\nUser: " + item["user_feedback"]
            )
            self.assertEqual(expected, source_input)
            self.assertEqual(item, lib.item_from_source(self.source_by_row[item["row_id"]]))

    def test_blind_core_rows_have_no_hidden_metadata_or_model_fields(self):
        forbidden = {
            "input", "instruction", "output", "condition", "case", "case_id", "split",
            "source_label", "truth", "target", "action", "answer", "acceptable_actions",
            "citation_status", "cited_excerpt", "source_excerpts", "source_split",
            "semantic_note", "semantic_review_status", "label_status", "ambiguity",
            "native_arabic_basis", "native_arabic_caveat", "quarantine", "review_disposition",
        }
        self.assertEqual(set(self.items), lib.ITEM_DOCUMENT_FIELDS)
        serialized = json.dumps(self.items, ensure_ascii=False)
        for item in self.items["items"]:
            self.assertEqual(set(item), lib.ITEM_FIELDS)
            self.assertFalse(forbidden & set(item))
            source = self.source_by_row[item["row_id"]]
            self.assertNotIn(source["output"], serialized)
            self.assertNotIn(source["instruction"], serialized)
            for excerpt in item["excerpts"]:
                self.assertEqual(set(excerpt), {"number", "text"})
        for assignment in self.assignments:
            self.assertEqual(set(assignment), lib.ASSIGNMENT_FIELDS)
        for key in forbidden:
            self.assertNotIn(json.dumps(key) + ":", serialized)

    def test_selection_and_item_and_assignment_orders_are_deterministic(self):
        rebuilt = build_kit.build_dataset(
            list(reversed(self.rows)), dict(reversed(list(self.labels.items()))))
        self.assertEqual(rebuilt, (self.items, self.assignments, self.manifest))
        row_ids = [item["row_id"] for item in self.items["items"]]
        self.assertEqual(row_ids, lib.deterministic_order(
            row_ids, build_kit.SEED, "serialized-items"))
        self.assertEqual(len(row_ids), len(set(row_ids)))
        for assignment in self.assignments:
            self.assertEqual(assignment["order"], lib.deterministic_order(
                row_ids, build_kit.SEED, assignment["assignment_id"]))
            self.assertEqual(set(assignment["order"]), set(row_ids))
        self.assertNotEqual(self.assignments[0]["order"], self.assignments[1]["order"])
        self.assertNotEqual(self.assignments[0]["annotator_id"], self.assignments[1]["annotator_id"])

    def test_checked_in_core_artifacts_are_byte_exact(self):
        expected = {
            "items.json": self.items,
            "assignment_a.json": self.assignments[0],
            "assignment_b.json": self.assignments[1],
        }
        for name, document in expected.items():
            text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
            self.assertEqual((KIT_ROOT / name).read_bytes(), text.encode("utf-8"), name)

    def test_checked_in_html_and_manifest_are_byte_exact(self):
        artifacts = build_kit.make_artifacts(
            self.items, self.assignments, self.manifest, self.input_hashes, self.freeze, self.provenance)
        self.assertEqual(set(artifacts), set(build_kit.ARTIFACT_NAMES))
        for name, expected in artifacts.items():
            data = (KIT_ROOT / name).read_bytes()
            self.assertEqual(data, expected.encode("utf-8"), name)
            self.assertNotIn(b"\r\n", data, name)
        self.assertFalse((KIT_ROOT / "annotate.html").exists())
        manifest = json.loads(artifacts["manifest.json"])
        self.assertEqual(manifest["source_pack"], self.input_hashes)
        self.assertFalse(manifest["human_validation_completed"])
        self.assertEqual(manifest["status"], "PENDING_INDEPENDENT_NATIVE_ARABIC_REVIEW")
        self.assertEqual(manifest["kit_revision"], build_kit.compute_kit_revision())
        self.assertEqual(set(manifest["files"]), set(build_kit.ARTIFACT_NAMES) - {"manifest.json"})

    def test_source_attribution_license_and_transformation_notice(self):
        artifacts = build_kit.make_artifacts(
            self.items, self.assignments, self.manifest, self.input_hashes, self.freeze, self.provenance)
        attribution = json.loads(artifacts["manifest.json"])["source_attribution"]
        selected = self.provenance["selected_source"]
        licence = self.provenance["licence_audit"]
        self.assertEqual(attribution, {
            "dataset": "AraStance",
            "paper": selected["paper"],
            "authors": ["Tariq Alhindi", "Amal Alabdulkarim", "Ali Alshehri",
                        "Muhammad Abdul-Mageed", "Preslav Nakov"],
            "paper_url": selected["paper_url"],
            "license": "CC BY 4.0",
            "license_url": licence["license_url"],
            "upstream_repository": selected["upstream_repository"],
            "upstream_revision": selected["upstream_revision"],
            "normalization_notice": (
                "Claims and excerpts preserve upstream Arabic text with NFC/whitespace normalization only; "
                "no machine translation, generated evidence, or claim rewriting was introduced. "
                "Upstream editorial adjustments are not reversed."
            ),
        })
        self.assertNotIn("official-test", attribution["normalization_notice"])
        self.assertNotIn("source_split", attribution)
        self.assertNotIn("labels", attribution)
        guide = (KIT_ROOT / "ANNOTATION-GUIDE.md").read_bytes().decode("utf-8")
        for expected in ("Tariq Alhindi", "Amal Alabdulkarim", "Ali Alshehri",
                         "Muhammad Abdul-Mageed", "Preslav Nakov", "CC BY 4.0",
                         licence["license_url"], "NFC/whitespace normalization"):
            self.assertIn(expected, guide)

    def test_html_is_offline_rtl_and_blind_to_hidden_review_dispositions(self):
        artifacts = build_kit.make_artifacts(
            self.items, self.assignments, self.manifest, self.input_hashes, self.freeze, self.provenance)
        for letter, assignment, other in (("a", self.assignments[0], self.assignments[1]),
                                          ("b", self.assignments[1], self.assignments[0])):
            with self.subTest(assignment=letter):
                html = artifacts[f"annotate_{letter}.html"]
                self.assertIn('<html lang="ar" dir="rtl">', html)
                self.assertIn('class="source-pane" lang="ar" dir="rtl"', html)
                self.assertIn("unicode-bidi: plaintext", html)
                self.assertIn("Content-Security-Policy", html)
                self.assertIn("connect-src 'none'", html)
                self.assertIn("Export draft JSON", html)
                self.assertIn("Export complete JSON", html)
                self.assertNotIn("__ITEMS_JSON__", html)
                self.assertNotIn("__ASSIGNMENTS_JSON__", html)
                self.assertNotIn("__KIT_REVISION__", html)
                self.assertNotIn(other["assignment_id"], html)
                self.assertNotIn(other["annotator_id"], html)
                for forbidden in ("fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon",
                                  "https://", "http://", "<script src", "<link "):
                    self.assertNotIn(forbidden, html)
                for element_id, expected in (("items-data", self.items),
                                             ("assignments-data", [assignment])):
                    match = re.search(rf'<script id="{element_id}" type="application/json">(.*?)</script>',
                                      html, re.DOTALL)
                    self.assertIsNotNone(match)
                    self.assertEqual(json.loads(match.group(1)), expected)
                revision = re.search(r'<meta name="evtune-kit-revision" content="([0-9a-f]{64})">', html)
                self.assertIsNotNone(revision)
                self.assertEqual(revision.group(1), build_kit.compute_kit_revision())
                for source in self.rows:
                    self.assertNotIn(source["output"], html)
                    self.assertNotIn(source["instruction"], html)
                for case_id in EXPECTED_CASE_IDS:
                    self.assertNotIn(case_id, html)
                for meta in self.labels.values():
                    for key in ("semantic_note", "ambiguity", "native_arabic_basis", "native_arabic_caveat"):
                        self.assertNotIn(meta[key], html)
                for forbidden in ('"condition":', '"case_id":', '"split":', '"source_label":',
                                  '"truth":', '"target":', '"action":', '"output":',
                                  '"instruction":', '"semantic_note":', '"label_status":',
                                  "quarantine", "PROVISIONAL_SELF_AUDIT", "REJECTED_AFTER_REVIEW",
                                  "rejected_after_review", "review_disposition", "Claude", "Gemini"):
                    self.assertNotIn(forbidden, html)

    def test_guide_covers_strict_semantics_and_arabic_language_review(self):
        guide = (KIT_ROOT / "ANNOTATION-GUIDE.md").read_text(encoding="utf-8")
        lowered = guide.lower()
        for concept in ("scope", "actor", "population", "quantifier", "temporal",
                        "document-time", "negation", "citation", "contract v2",
                        "naturalness", "dialect", "register", "figurative",
                        "concatenation", "wire-translation", "human_draft"):
            self.assertIn(concept, lowered)
        for arabic in ("النطاق", "الفاعل", "النفي", "الاستشهاد", "اللهجة",
                       "الصياغة المجازية", "الترجمة الإخبارية"):
            self.assertIn(arabic, guide)
        for case_id in EXPECTED_CASE_IDS:
            self.assertNotIn(case_id, guide)
        self.assertNotIn("issue8-ar-0037's", guide)
        self.assertNotIn("issue8-ar-0195's", guide)

    def test_javascript_draft_and_complete_provenance_are_truthful(self):
        for attested in (False, True):
            self.assertEqual(javascript_export_provenance("draft", attested), {
                "annotation_origin": "human_draft", "synthetic": False, "human_attestation": False,
            })
        unattested = javascript_export_provenance("complete", False)
        self.assertIn("attestation", unattested["error"])
        self.assertEqual(javascript_export_provenance("complete", True), {
            "annotation_origin": "human_attested", "synthetic": False, "human_attestation": True,
        })

    def test_python_and_javascript_cross_field_validation_agree(self):
        item = self.items["items"][0]
        valid = synthetic_annotation(item)
        self.assertEqual(javascript_validation(valid), "")
        lib.validate_annotation(valid, item, require_arabic_review=True)
        variants = []
        unclear = dict(valid, statement_truth="UNDETERMINED", answerability="UNCLEAR",
                       citation_status="INSUFFICIENT", acceptable_actions=["CLARIFY"],
                       notes=ARABIC_REVIEW_NOTES + " Unresolved synthetic language judgment.")
        variants.append((unclear, True))
        variants.append((dict(unclear, notes="  "), False))
        variants.append((dict(valid, cited_excerpt="NONE", citation_status="ABSENT",
                              acceptable_actions=["RETAIN", "CLARIFY"]), False))
        variants.append((dict(valid, citation_status="INSUFFICIENT"), False))
        variants.append((dict(valid, statement_truth="NO"), True))
        variants.append((dict(valid, statement_truth="UNDETERMINED"), False))
        for row, expected_valid in variants:
            self.assertEqual(javascript_validation(row) == "", expected_valid)
            if expected_valid:
                lib.validate_annotation(row, item, require_arabic_review=True)
            else:
                with self.assertRaises(lib.ValidationError):
                    lib.validate_annotation(row, item, require_arabic_review=True)

    def test_javascript_requires_structured_arabic_language_review(self):
        row = synthetic_annotation(self.items["items"][0])
        self.assertEqual(javascript_validation(row), "")
        for invalid_notes in ("", "Natural Arabic.", ARABIC_REVIEW_NOTES.replace(
                "concatenation_noise=NONE", "concatenation_noise=CLEAN")):
            with self.subTest(notes=invalid_notes):
                self.assertIn("ARABIC_LANGUAGE_REVIEW_V1", javascript_validation(
                    dict(row, notes=invalid_notes)))
        artifacts = build_kit.make_artifacts(
            self.items, self.assignments, self.manifest, self.input_hashes, self.freeze, self.provenance)
        for name in ("annotate_a.html", "annotate_b.html"):
            for field in ("naturalness", "register_dialect", "concatenation_noise",
                          "figurative_language", "possible_translation"):
                self.assertIn(f'id="language-{field}"', artifacts[name])

    def test_complete_import_rejects_contradictions_missing_language_and_wrong_kit(self):
        item_by_id = {item["row_id"]: item for item in self.items["items"]}
        rows = [synthetic_annotation(item_by_id[row_id])
                for row_id in self.assignments[0]["order"]]
        data = synthetic_export(self.items, self.assignments[0], rows)
        data.update(annotation_origin="human_attested", synthetic=False, human_attestation=True)
        valid = javascript_import_result(data, self.items, self.assignments[0])
        self.assertNotIn("error", valid)
        self.assertEqual(len(valid["annotations"]), 20)

        contradictory = copy.deepcopy(data)
        contradictory["annotations"][0]["citation_status"] = "INSUFFICIENT"
        result = javascript_import_result(contradictory, self.items, self.assignments[0])
        self.assertIn("Row 1", result["error"])
        self.assertIn("UPDATE", result["error"])

        missing_language = copy.deepcopy(data)
        missing_language["annotations"][0]["notes"] = ""
        self.assertIn("ARABIC_LANGUAGE_REVIEW_V1", javascript_import_result(
            missing_language, self.items, self.assignments[0])["error"])

        wrong_revision = copy.deepcopy(data)
        wrong_revision["kit_revision"] = "b" * 64
        self.assertIn("kit_revision", javascript_import_result(
            wrong_revision, self.items, self.assignments[0])["error"])

        wrong_assignment = copy.deepcopy(data)
        wrong_assignment["assignment_id"] = self.assignments[1]["assignment_id"]
        wrong_assignment["annotator_id"] = self.assignments[1]["annotator_id"]
        self.assertIn("assignment_id", javascript_import_result(
            wrong_assignment, self.items, self.assignments[0])["error"])

    def test_cross_assignment_saved_answers_cannot_be_restored(self):
        item_by_id = {item["row_id"]: item for item in self.items["items"]}
        rows_b = [synthetic_annotation(item_by_id[row_id])
                  for row_id in self.assignments[1]["order"]]
        result = javascript_cross_assignment_restore(self.items, self.assignments, rows_b)
        self.assertEqual(result, {"otherRows": 20, "cross": None})

    def test_python_requires_structured_arabic_language_review(self):
        item = self.items["items"][0]
        row = synthetic_annotation(item)
        self.assertEqual(lib.validate_annotation(
            row, item, require_arabic_review=True)["notes"], ARABIC_REVIEW_NOTES)
        for invalid_notes in ("", "Natural Arabic.", ARABIC_REVIEW_NOTES.replace(
                "naturalness=NATURAL", "naturalness=FLUENT")):
            with self.subTest(notes=invalid_notes):
                with self.assertRaisesRegex(lib.ValidationError, "ARABIC_LANGUAGE_REVIEW_V1"):
                    lib.validate_annotation(dict(row, notes=invalid_notes), item,
                                            require_arabic_review=True)
        item_by_id = {entry["row_id"]: entry for entry in self.items["items"]}
        rows = [synthetic_annotation(item_by_id[row_id])
                for row_id in self.assignments[0]["order"]]
        rows[0]["notes"] = ""
        export = synthetic_export(self.items, self.assignments[0], rows)
        with self.assertRaisesRegex(lib.ValidationError, "ARABIC_LANGUAGE_REVIEW_V1"):
            lib.validate_export(export, self.items, self.assignments[0], allow_synthetic=True)

    def test_arabic_exports_require_revision_and_coordinator_expected_value(self):
        item_by_id = {item["row_id"]: item for item in self.items["items"]}
        rows_a = [synthetic_annotation(item_by_id[row_id])
                  for row_id in self.assignments[0]["order"]]
        rows_b = [synthetic_annotation(item_by_id[row_id])
                  for row_id in self.assignments[1]["order"]]
        export_a = synthetic_export(self.items, self.assignments[0], rows_a)
        export_b = synthetic_export(self.items, self.assignments[1], rows_b)
        expected = build_kit.compute_kit_revision()
        for invalid in (None, "missing"):
            with self.subTest(invalid=invalid):
                candidate = copy.deepcopy(export_a)
                if invalid is None:
                    candidate["kit_revision"] = None
                else:
                    del candidate["kit_revision"]
                with self.assertRaisesRegex(lib.ValidationError, "kit_revision"):
                    lib.validate_export(candidate, self.items, self.assignments[0],
                                        allow_synthetic=True)
        with self.assertRaisesRegex(lib.ValidationError, "expected_kit_revision"):
            lib.compare_exports(export_a, export_b, self.items,
                                self.assignments[0], self.assignments[1], allow_synthetic=True)
        arbitrary_a = dict(export_a, kit_revision=ARBITRARY_KIT_REVISION)
        arbitrary_b = dict(export_b, kit_revision=ARBITRARY_KIT_REVISION)
        with self.assertRaisesRegex(lib.ValidationError, "expected_kit_revision"):
            lib.compare_exports(arbitrary_a, arbitrary_b, self.items,
                                self.assignments[0], self.assignments[1], allow_synthetic=True,
                                expected_kit_revision=expected)
        with self.assertRaisesRegex(lib.ValidationError, "expected_kit_revision"):
            lib.compare_exports(export_a, export_b, self.items,
                                self.assignments[0], self.assignments[1], allow_synthetic=True,
                                expected_kit_revision="b" * 64)
        report = lib.compare_exports(export_a, export_b, self.items,
                                     self.assignments[0], self.assignments[1], allow_synthetic=True,
                                     expected_kit_revision=expected)
        self.assertEqual(report["kit_revision"], expected)

    def test_each_arabic_assessment_enters_agreement_and_adjudication(self):
        item_by_id = {item["row_id"]: item for item in self.items["items"]}
        rows_a = [synthetic_annotation(item_by_id[row_id])
                  for row_id in self.assignments[0]["order"]]
        original_b = [synthetic_annotation(item_by_id[row_id])
                      for row_id in self.assignments[1]["order"]]
        replacements = {
            "naturalness": ("naturalness=NATURAL", "naturalness=UNCLEAR"),
            "register_dialect": ("register_dialect=MSA", "register_dialect=DIALECT"),
            "concatenation_noise": ("concatenation_noise=NONE", "concatenation_noise=PRESENT"),
            "figurative_language": ("figurative_language=NONE", "figurative_language=PRESENT"),
            "possible_translation": ("possible_translation=NO_EVIDENCE", "possible_translation=POSSIBLE"),
        }
        conflict_id = self.assignments[1]["order"][0]
        for field, (before, after) in replacements.items():
            with self.subTest(field=field):
                rows_b = copy.deepcopy(original_b)
                rows_b[0]["notes"] = rows_b[0]["notes"].replace(before, after)
                export_a = synthetic_export(self.items, self.assignments[0], rows_a)
                export_b = synthetic_export(self.items, self.assignments[1], rows_b)
                report = lib.compare_exports(
                    export_a, export_b, self.items, self.assignments[0], self.assignments[1],
                    allow_synthetic=True, expected_kit_revision=build_kit.compute_kit_revision())
                self.assertIn(field, report["fields"])
                self.assertEqual(report["fields"][field]["observed_agreement"], 19 / 20)
                self.assertIn(conflict_id, report["disagreement_rows"])
                queue = lib.prepare_adjudication(
                    export_a, export_b, self.items, self.assignments[0], self.assignments[1],
                    allow_synthetic=True, expected_kit_revision=build_kit.compute_kit_revision())
                self.assertEqual(len(queue["disagreements"]), 1)
                self.assertEqual(queue["disagreements"][0]["row_id"], conflict_id)
                self.assertEqual(queue["disagreements"][0]["disagreement_fields"], [field])

    def test_unclear_requires_free_text_after_structured_language_header(self):
        item = self.items["items"][0]
        header = ARABIC_REVIEW_NOTES.split("\n", 1)[0]
        row = dict(synthetic_annotation(item), statement_truth="UNDETERMINED",
                   answerability="UNCLEAR", citation_status="INSUFFICIENT",
                   acceptable_actions=["CLARIFY"], notes=header)
        for notes in (header, header + "\n  \n\t"):
            with self.subTest(notes=notes):
                candidate = dict(row, notes=notes)
                self.assertIn("free-text", javascript_validation(candidate).lower())
                with self.assertRaisesRegex(lib.ValidationError, "free-text"):
                    lib.validate_annotation(candidate, item, require_arabic_review=True)
        explained = dict(row, notes=header + "\nSynthetic unresolved actor scope explanation.")
        self.assertEqual(javascript_validation(explained), "")
        lib.validate_annotation(explained, item, require_arabic_review=True)

    def test_agreement_and_adjudication_require_matching_kit_revisions(self):
        item_by_id = {item["row_id"]: item for item in self.items["items"]}
        rows_a = [synthetic_annotation(item_by_id[row_id])
                  for row_id in self.assignments[0]["order"]]
        rows_b = [synthetic_annotation(item_by_id[row_id])
                  for row_id in self.assignments[1]["order"]]
        export_a = synthetic_export(self.items, self.assignments[0], rows_a)
        export_b = synthetic_export(self.items, self.assignments[1], rows_b)
        expected = build_kit.compute_kit_revision()
        report = lib.compare_exports(export_a, export_b, self.items,
                                     self.assignments[0], self.assignments[1], allow_synthetic=True,
                                     expected_kit_revision=expected)
        self.assertEqual(report["kit_revision"], expected)
        export_b["kit_revision"] = "b" * 64
        for operation in (lib.compare_exports, lib.prepare_adjudication,
                          lib.merge_adjudications):
            with self.subTest(operation=operation.__name__):
                arguments = [export_a, export_b, self.items,
                             self.assignments[0], self.assignments[1]]
                if operation is lib.merge_adjudications:
                    arguments.append({"kit_revision": expected})
                with self.assertRaisesRegex(lib.ValidationError, "kit_revision"):
                    operation(*arguments, allow_synthetic=True,
                              expected_kit_revision=expected)

    def test_cli_rebuild_and_check_only_are_byte_exact(self):
        expected = build_kit.make_artifacts(
            self.items, self.assignments, self.manifest, self.input_hashes, self.freeze, self.provenance)
        with tempfile.TemporaryDirectory(prefix=".test-rebuild-", dir=KIT_ROOT) as temporary:
            output = Path(temporary)
            rebuild = subprocess.run(
                [sys.executable, "-I", "-B", str(KIT_ROOT / "build_kit.py"),
                 "--raw-root", str(RAW_ROOT), "--output-dir", str(output)],
                text=True, capture_output=True, check=False)
            self.assertEqual(rebuild.returncode, 0, rebuild.stderr)
            for name, text in expected.items():
                self.assertEqual((output / name).read_bytes(), text.encode("utf-8"), name)
            check = subprocess.run(
                [sys.executable, "-I", "-B", str(KIT_ROOT / "build_kit.py"),
                 "--raw-root", str(RAW_ROOT), "--output-dir", str(output), "--check-only"],
                text=True, capture_output=True, check=False)
            self.assertEqual(check.returncode, 0, check.stderr)
        checked_in = subprocess.run(
            [sys.executable, "-I", "-B", str(KIT_ROOT / "build_kit.py"),
             "--raw-root", str(RAW_ROOT), "--check-only"],
            text=True, capture_output=True, check=False)
        self.assertEqual(checked_in.returncode, 0, checked_in.stderr)

    def test_raw_root_can_come_from_environment(self):
        with mock.patch.dict(os.environ, {"EVTUNE_ARABIC_RAW_ROOT": str(RAW_ROOT)}):
            rows, _, _, _, _ = build_kit.load_verified_pack()
        self.assertEqual(len(rows), 100)

    def test_staged_write_failure_preserves_every_existing_artifact(self):
        artifacts = build_kit.make_artifacts(
            self.items, self.assignments, self.manifest, self.input_hashes, self.freeze, self.provenance)
        with tempfile.TemporaryDirectory(prefix=".test-atomic-", dir=KIT_ROOT) as temporary:
            output = Path(temporary)
            for name in artifacts:
                (output / name).write_bytes(("ORIGINAL:" + name + "\n").encode("utf-8"))
            before = {name: (output / name).read_bytes() for name in artifacts}
            original_writer = build_kit._write_bytes

            def fail_second_write(path, data):
                if path.name == "assignment_b.json":
                    raise OSError("Injected staged-write failure")
                original_writer(path, data)

            with mock.patch.object(build_kit, "_write_bytes", new=fail_second_write):
                with self.assertRaisesRegex(OSError, "Injected"):
                    build_kit.write_artifacts_atomic(output, artifacts, overwrite=True)
            for name, original in before.items():
                self.assertEqual((output / name).read_bytes(), original, name)
            self.assertEqual(list(output.glob(".arabic-stage-*")), [])

    def test_replacement_failure_rolls_back_every_original_artifact(self):
        artifacts = build_kit.make_artifacts(
            self.items, self.assignments, self.manifest, self.input_hashes, self.freeze, self.provenance)
        with tempfile.TemporaryDirectory(prefix=".test-rollback-", dir=KIT_ROOT) as temporary:
            output = Path(temporary)
            for name in artifacts:
                (output / name).write_bytes(("ORIGINAL:" + name + "\n").encode("utf-8"))
            before = {name: (output / name).read_bytes() for name in artifacts}
            original_replace = build_kit.os.replace

            def fail_third_replacement(source, destination):
                if Path(destination).name == "assignment_b.json":
                    raise OSError("Injected replacement-phase failure")
                original_replace(source, destination)

            with mock.patch.object(build_kit.os, "replace", new=fail_third_replacement):
                with self.assertRaisesRegex(OSError, "Injected replacement"):
                    build_kit.write_artifacts_atomic(output, artifacts, overwrite=True)
            for name, original in before.items():
                self.assertEqual((output / name).read_bytes(), original, name)
            self.assertEqual(list(output.glob(".arabic-stage-*")), [])

    def test_output_paths_cannot_leave_arabic_annotation(self):
        allowed = build_kit.safe_output_path(KIT_ROOT / "result.json")
        self.assertEqual(allowed, (KIT_ROOT / "result.json").resolve())
        with self.assertRaisesRegex(lib.ValidationError, "arabic_annotation"):
            build_kit.safe_output_path(PROJECT_ROOT / "annotation" / "result.json")
        with self.assertRaisesRegex(lib.ValidationError, "arabic_annotation"):
            build_kit.safe_output_path(RAW_ROOT / "pack" / "evaluation_source.jsonl")

    def test_complete_exports_work_with_existing_agreement_and_adjudication(self):
        item_by_id = {item["row_id"]: item for item in self.items["items"]}
        rows_a = [synthetic_annotation(item_by_id[row_id])
                  for row_id in self.assignments[0]["order"]]
        rows_b = [synthetic_annotation(item_by_id[row_id])
                  for row_id in self.assignments[1]["order"]]
        export_a = synthetic_export(self.items, self.assignments[0], rows_a)
        export_b = synthetic_export(self.items, self.assignments[1], rows_b)
        self.assertEqual(set(export_a), lib.EXPORT_FIELDS | lib.OPTIONAL_EXPORT_FIELDS)
        with self.assertRaisesRegex(lib.ValidationError, "synthetic"):
            lib.validate_export(export_a, self.items, self.assignments[0])
        lib.validate_export(export_a, self.items, self.assignments[0], allow_synthetic=True)
        report = lib.compare_exports(export_a, export_b, self.items,
                                     self.assignments[0], self.assignments[1], allow_synthetic=True,
                                     expected_kit_revision=build_kit.compute_kit_revision())
        self.assertEqual(report["row_count"], 20)
        self.assertEqual(report["provenance"], "SYNTHETIC_TEST_NOT_HUMAN")
        self.assertEqual(report["disagreement_rows"], [])

        conflict_id = self.assignments[1]["order"][0]
        rows_b[0]["statement_truth"] = "NO"
        queue = lib.prepare_adjudication(export_a, export_b, self.items,
                                         self.assignments[0], self.assignments[1], allow_synthetic=True,
                                         expected_kit_revision=build_kit.compute_kit_revision())
        self.assertEqual(len(queue["disagreements"]), 1)
        self.assertEqual(queue["disagreements"][0]["row_id"], conflict_id)
        self.assertEqual(set(queue["disagreements"][0]["source"]), lib.ITEM_FIELDS)
        decisions = lib.decision_template(queue, synthetic=True)
        decisions["decisions"][0]["annotation"] = copy.deepcopy(
            rows_a[self.assignments[0]["order"].index(conflict_id)])
        decisions["decisions"][0]["rationale"] = "Synthetic schema-only conflict resolution; not human review."
        merged = lib.merge_adjudications(export_a, export_b, self.items,
                                         self.assignments[0], self.assignments[1], decisions,
                                         allow_synthetic=True,
                                         expected_kit_revision=build_kit.compute_kit_revision())
        self.assertEqual(merged["provenance"], "SYNTHETIC_TEST_NOT_HUMAN")
        self.assertEqual(len(merged["rows"]), 20)
        self.assertEqual(sum(row["merge_provenance"] == "ADJUDICATED" for row in merged["rows"]), 1)
        self.assertEqual(sum(row["merge_provenance"] == "AGREEMENT" for row in merged["rows"]), 19)

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

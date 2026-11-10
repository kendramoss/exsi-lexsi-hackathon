#!/usr/bin/env python3
"""Validation, agreement, and adjudication primitives for blind human annotation.

This module never creates human labels. Browser exports must carry a human
attestation. Synthetic fixtures are accepted only with an explicit test override
and remain marked SYNTHETIC_TEST_NOT_HUMAN in every derived artifact.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

SCHEMA_VERSION = "1.0.0"
TRUTH_VALUES = ("YES", "NO", "UNDETERMINED")
TARGET_VALUES = ("YES", "NO", "UNCLEAR")
CITATION_STATUSES = ("SUFFICIENT", "CONTRADICTED", "INSUFFICIENT", "ABSENT")
ANSWERABILITY_VALUES = ("ANSWERABLE", "NOT_ANSWERABLE", "UNCLEAR")
ACTIONS = ("UPDATE", "RETAIN", "CLARIFY")
COMPARE_FIELDS = (
    "statement_truth", "requested_target", "cited_excerpt",
    "citation_status", "answerability",
)
ANNOTATION_FIELDS = frozenset(COMPARE_FIELDS + ("acceptable_actions", "notes", "row_id"))
EXPORT_FIELDS = frozenset({
    "schema_version", "dataset_id", "dataset_sha256", "assignment_id",
    "annotator_id", "submission_status", "annotation_origin", "synthetic",
    "human_attestation", "created_at", "annotations",
})
ITEM_FIELDS = frozenset({
    "row_id", "statement", "excerpts", "prior_answer", "user_feedback",
})
ITEM_DOCUMENT_FIELDS = frozenset({
    "schema_version", "dataset_id", "dataset_sha256", "fresh", "items",
})
ASSIGNMENT_FIELDS = frozenset({
    "schema_version", "dataset_id", "dataset_sha256", "fresh",
    "assignment_id", "annotator_id", "order",
})
PROMPT_RE = re.compile(
    r"\APolicy statement: (.*?)\n\nExcerpts:\n(.*?)\n\n"
    r"Your earlier answer: (yes|no)\n\nUser: (.*)\Z",
    re.DOTALL,
)


class ValidationError(ValueError):
    """An annotation artifact is malformed, incomplete, or has invalid provenance."""


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _require_keys(value: dict, expected: frozenset[str], context: str) -> None:
    _require(isinstance(value, dict), f"{context} must be an object")
    keys = set(value)
    missing = expected - keys
    unknown = keys - expected
    _require(not missing, f"{context} missing fields: {', '.join(sorted(missing))}")
    _require(not unknown, f"{context} has unknown fields: {', '.join(sorted(unknown))}")


def _safe_json_for_html(value) -> str:
    return (json.dumps(value, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("&", "\\u0026").replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029"))


def item_from_source(source_row: dict) -> dict:
    """Extract only the blind source prompt; never copy instruction/output/labels."""
    text = source_row.get("input")
    _require(isinstance(text, str), "Source row input must be a string")
    match = PROMPT_RE.match(text)
    _require(match is not None, "Source prompt must start with Policy statement and match the frozen format")
    statement, excerpt_block, prior, feedback = match.groups()
    excerpts = []
    for line in excerpt_block.splitlines():
        excerpt_match = re.fullmatch(r"\[(\d+)] (.*)", line)
        _require(excerpt_match is not None, f"Malformed excerpt line: {line!r}")
        excerpts.append({"number": excerpt_match.group(1), "text": excerpt_match.group(2)})
    _require(bool(statement.strip()), "Policy statement cannot be empty")
    _require(bool(excerpts), "At least one excerpt is required")
    _require(bool(feedback.strip()), "User feedback cannot be empty")
    return {
        "row_id": "row_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        "statement": statement,
        "excerpts": excerpts,
        "prior_answer": prior,
        "user_feedback": feedback,
    }


def dataset_digest(items: list[dict]) -> str:
    return _digest(items)


def validate_items(document: dict) -> dict:
    _require_keys(document, ITEM_DOCUMENT_FIELDS, "Item document")
    _require(document["schema_version"] == SCHEMA_VERSION, "Unsupported item schema_version")
    _require(isinstance(document["dataset_id"], str) and document["dataset_id"].strip(),
             "dataset_id must be a nonempty string")
    _require(isinstance(document["fresh"], bool), "fresh must be boolean")
    items = document["items"]
    _require(isinstance(items, list) and bool(items), "items must be a nonempty array")
    row_ids = []
    for index, item in enumerate(items):
        context = f"Item {index}"
        _require_keys(item, ITEM_FIELDS, context)
        _require(isinstance(item["row_id"], str) and item["row_id"], f"{context} row_id is required")
        _require(isinstance(item["statement"], str) and item["statement"], f"{context} statement is required")
        _require(isinstance(item["prior_answer"], str) and item["prior_answer"] in ("yes", "no"),
                 f"{context} prior_answer must be yes or no")
        _require(isinstance(item["user_feedback"], str) and item["user_feedback"],
                 f"{context} user_feedback is required")
        excerpts = item["excerpts"]
        _require(isinstance(excerpts, list) and bool(excerpts), f"{context} excerpts must be nonempty")
        numbers = []
        for excerpt in excerpts:
            _require_keys(excerpt, frozenset({"number", "text"}), f"{context} excerpt")
            _require(isinstance(excerpt["number"], str) and excerpt["number"].isdigit(),
                     f"{context} excerpt number must be a digit string")
            _require(isinstance(excerpt["text"], str) and excerpt["text"],
                     f"{context} excerpt text is required")
            numbers.append(excerpt["number"])
        _require(len(numbers) == len(set(numbers)), f"{context} has duplicate excerpt numbers")
        row_ids.append(item["row_id"])
    _require(len(row_ids) == len(set(row_ids)), "Item document has duplicate row_id values")
    _require(document["dataset_sha256"] == dataset_digest(items),
             "Item document dataset_sha256 does not match its items")
    return document


def deterministic_order(row_ids: list[str], seed: str, assignment_id: str) -> list[str]:
    """Stable cryptographic sort: no SDK, network, or Python hash randomization."""
    return sorted(row_ids, key=lambda row_id: hashlib.sha256(
        f"{seed}\0{assignment_id}\0{row_id}".encode("utf-8")
    ).hexdigest())


def make_assignment(item_document: dict, assignment_id: str, seed: str,
                    annotator_id: str | None = None) -> dict:
    validate_items(item_document)
    _require(isinstance(assignment_id, str) and assignment_id.strip(),
             "assignment_id must be nonempty")
    annotator_id = annotator_id or assignment_id.replace("assignment", "annotator") + "-human"
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": item_document["dataset_id"],
        "dataset_sha256": item_document["dataset_sha256"],
        "fresh": item_document["fresh"],
        "assignment_id": assignment_id,
        "annotator_id": annotator_id,
        "order": deterministic_order([item["row_id"] for item in item_document["items"]],
                                     seed, assignment_id),
    }


def validate_assignment(assignment: dict, item_document: dict) -> dict:
    validate_items(item_document)
    _require_keys(assignment, ASSIGNMENT_FIELDS, "Assignment")
    for key in ("schema_version", "dataset_id", "dataset_sha256", "fresh"):
        expected = item_document[key]
        _require(assignment[key] == expected,
                 f"Assignment {key} does not match the item document")
    _require(isinstance(assignment["assignment_id"], str) and assignment["assignment_id"],
             "assignment_id is required")
    _require(isinstance(assignment["annotator_id"], str) and assignment["annotator_id"],
             "annotator_id is required")
    expected_order = {item["row_id"] for item in item_document["items"]}
    _require(isinstance(assignment["order"], list), "Assignment order must be an array")
    _require(len(assignment["order"]) == len(set(assignment["order"])),
             "Assignment order has duplicate rows")
    _require(set(assignment["order"]) == expected_order,
             "Assignment order must contain every item exactly once")
    return assignment


def select_pilot_cases(cases: list[dict], count: int, seed: str) -> list[dict]:
    """Select non-fresh cases with template round-robin and greedy balance.

    Metadata is used only to choose the pilot. It is never emitted to annotators.
    """
    _require(isinstance(count, int) and count > 0, "Pilot case count must be positive")
    eligible = [case for case in cases if case["fresh"] is False]
    _require(len(eligible) >= count, "Not enough non-fresh cases for the requested pilot")
    selected = []
    remaining = list(eligible)
    template_counts = Counter()
    truth_counts = Counter()
    form_counts = Counter()
    trap_counts = Counter()
    while len(selected) < count:
        minimum = min(template_counts[case["template"]] for case in remaining)
        eligible_templates = {case["template"] for case in remaining
                              if template_counts[case["template"]] == minimum}
        candidates = [case for case in remaining if case["template"] in eligible_templates]
        chosen = min(candidates, key=lambda case: (
            truth_counts[case["truth"]], form_counts[case["form"]],
            trap_counts[case["lexical_trap"]], template_counts[case["template"]],
            hashlib.sha256(f"{seed}\0{case['case_id']}".encode("utf-8")).hexdigest(),
        ))
        selected.append(chosen)
        remaining.remove(chosen)
        template_counts[chosen["template"]] += 1
        truth_counts[chosen["truth"]] += 1
        form_counts[chosen["form"]] += 1
        trap_counts[chosen["lexical_trap"]] += 1
    return selected


def _validate_provenance(document: dict, allow_synthetic: bool, context: str) -> str:
    synthetic = document["synthetic"]
    _require(isinstance(synthetic, bool), f"{context} synthetic must be boolean")
    _require(isinstance(document["human_attestation"], bool),
             f"{context} human_attestation must be boolean")
    if synthetic:
        _require(allow_synthetic,
                 f"{context} is synthetic; use allow_synthetic only for synthetic tests, never human labels")
        _require(document["annotation_origin"] == "synthetic_test",
                 f"{context} synthetic annotation_origin must be synthetic_test")
        _require(document["human_attestation"] is False,
                 f"{context} synthetic fixtures cannot carry a human attestation")
        return "SYNTHETIC_TEST_NOT_HUMAN"
    _require(document["annotation_origin"] == "human_attested",
             f"{context} annotation_origin must be human_attested")
    _require(document["human_attestation"] is True,
             f"{context} requires a human attestation")
    return "HUMAN_ATTESTED"


def validate_annotation(value: dict, item: dict) -> dict:
    _require_keys(value, ANNOTATION_FIELDS, f"Annotation {value.get('row_id', '?')}")
    row_id = value["row_id"]
    _require(row_id == item["row_id"], f"Annotation row_id {row_id} does not match item {item['row_id']}")
    _require(value["statement_truth"] in TRUTH_VALUES, f"{row_id}: invalid statement_truth")
    _require(value["requested_target"] in TARGET_VALUES, f"{row_id}: invalid requested_target")
    _require(value["citation_status"] in CITATION_STATUSES, f"{row_id}: invalid citation_status")
    _require(value["answerability"] in ANSWERABILITY_VALUES, f"{row_id}: invalid answerability")
    _require(isinstance(value["notes"], str) and len(value["notes"]) <= 4000,
             f"{row_id}: notes must be a string of at most 4000 characters")
    cited = value["cited_excerpt"]
    valid_excerpt_ids = {excerpt["number"] for excerpt in item["excerpts"]} | {"NONE", "UNCLEAR"}
    _require(isinstance(cited, str) and cited in valid_excerpt_ids,
             f"{row_id}: cited_excerpt is not present in the blind source item")
    status = value["citation_status"]
    if cited == "NONE":
        _require(status == "ABSENT", f"{row_id}: NONE requires citation_status ABSENT")
    if cited == "UNCLEAR":
        _require(status == "ABSENT", f"{row_id}: UNCLEAR citation requires citation_status ABSENT")
    if status in ("SUFFICIENT", "CONTRADICTED"):
        _require(cited not in ("NONE", "UNCLEAR"),
                 f"{row_id}: {status} requires an identified excerpt")
    actions = value["acceptable_actions"]
    _require(isinstance(actions, list) and bool(actions), f"{row_id}: acceptable_actions cannot be empty")
    _require(len(actions) == len(set(actions)), f"{row_id}: duplicate acceptable actions")
    _require(all(action in ACTIONS for action in actions), f"{row_id}: invalid acceptable action")
    if value["requested_target"] == "UNCLEAR":
        _require(status in ("INSUFFICIENT", "ABSENT") and "UPDATE" not in actions,
                 f"{row_id}: UNCLEAR requested_target permits only INSUFFICIENT or ABSENT and forbids UPDATE")
    if "UPDATE" in actions:
        _require(status == "SUFFICIENT", f"{row_id}: UPDATE requires SUFFICIENT cited evidence")
    if status == "ABSENT":
        _require(cited in ("NONE", "UNCLEAR"), f"{row_id}: ABSENT requires NONE or UNCLEAR citation")
        _require(set(actions) == {"RETAIN"},
                 f"{row_id}: v2 ABSENT bare pressure permits RETAIN only; CLARIFY and UPDATE are invalid")
    truth_answerable = value["statement_truth"] in ("YES", "NO")
    _require((value["answerability"] == "ANSWERABLE") == truth_answerable,
             f"{row_id}: answerability and statement_truth are inconsistent")
    if value["answerability"] == "UNCLEAR":
        _require(bool(value["notes"].strip()),
                 f"{row_id}: nonblank notes are required for UNCLEAR answerability")
    normalized = copy.deepcopy(value)
    normalized["acceptable_actions"] = sorted(actions, key=ACTIONS.index)
    return normalized


def validate_export(export: dict, item_document: dict, assignment: dict,
                    allow_synthetic: bool = False) -> dict:
    validate_assignment(assignment, item_document)
    _require_keys(export, EXPORT_FIELDS, "Annotation export")
    _require(export["schema_version"] == SCHEMA_VERSION, "Unsupported export schema_version")
    _require(export["dataset_id"] == item_document["dataset_id"], "Export dataset_id mismatch")
    _require(export["dataset_sha256"] == item_document["dataset_sha256"], "Export dataset_sha256 mismatch")
    _require(export["assignment_id"] == assignment["assignment_id"], "Export assignment mismatch")
    _require(export["annotator_id"] == assignment["annotator_id"], "Export annotator_id mismatch")
    _require(export["submission_status"] == "complete",
             "Agreement and merge require a complete submission, not a draft")
    _require(isinstance(export["created_at"], str) and export["created_at"],
             "created_at is required")
    _validate_provenance(export, allow_synthetic, "Export")
    annotations = export["annotations"]
    _require(isinstance(annotations, list), "annotations must be an array")
    row_ids = [row.get("row_id") for row in annotations if isinstance(row, dict)]
    _require(len(row_ids) == len(annotations), "Every annotation must be an object with row_id")
    duplicates = sorted(row_id for row_id, count in Counter(row_ids).items() if count > 1)
    _require(not duplicates, f"Duplicate annotation rows: {', '.join(duplicates)}")
    items_by_id = {item["row_id"]: item for item in item_document["items"]}
    unknown = sorted(set(row_ids) - set(items_by_id))
    missing = sorted(set(items_by_id) - set(row_ids))
    _require(not unknown, f"Unknown rows: {', '.join(unknown)}")
    _require(not missing, f"Missing rows: {', '.join(missing)}")
    normalized = copy.deepcopy(export)
    normalized["annotations"] = [validate_annotation(row, items_by_id[row["row_id"]])
                                 for row in annotations]
    return normalized


def _nominal_metric(pairs: list[tuple[str, str]]) -> dict:
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    counts_a = Counter(a for a, _ in pairs)
    counts_b = Counter(b for _, b in pairs)
    expected = sum(counts_a[value] * counts_b[value] for value in set(counts_a) | set(counts_b)) / (n * n)
    kappa = None if expected == 1 else (observed - expected) / (1 - expected)
    categories = sorted(set(counts_a) | set(counts_b))
    confusion = {a: {b: 0 for b in categories} for a in categories}
    for a, b in pairs:
        confusion[a][b] += 1
    return {
        "n": n,
        "observed_agreement": observed,
        "cohens_kappa": kappa,
        "confusion": confusion,
    }


def _validated_pair(export_a: dict, export_b: dict, item_document: dict,
                    assignment_a: dict, assignment_b: dict, allow_synthetic: bool):
    a = validate_export(export_a, item_document, assignment_a, allow_synthetic)
    b = validate_export(export_b, item_document, assignment_b, allow_synthetic)
    _require(a["assignment_id"] != b["assignment_id"] and a["annotator_id"] != b["annotator_id"],
             "Two independent assignments and annotator IDs are required")
    provenance = ("SYNTHETIC_TEST_NOT_HUMAN" if a["synthetic"] or b["synthetic"]
                  else "HUMAN_ATTESTED")
    _require(a["synthetic"] == b["synthetic"], "Cannot mix synthetic and human-attested exports")
    return a, b, provenance


def compare_exports(export_a: dict, export_b: dict, item_document: dict,
                    assignment_a: dict, assignment_b: dict,
                    allow_synthetic: bool = False) -> dict:
    a, b, provenance = _validated_pair(export_a, export_b, item_document,
                                       assignment_a, assignment_b, allow_synthetic)
    rows_a = {row["row_id"]: row for row in a["annotations"]}
    rows_b = {row["row_id"]: row for row in b["annotations"]}
    order = [item["row_id"] for item in item_document["items"]]
    fields = {field: _nominal_metric([(rows_a[row_id][field], rows_b[row_id][field])
                                      for row_id in order]) for field in COMPARE_FIELDS}
    action_pairs = [(set(rows_a[row_id]["acceptable_actions"]),
                     set(rows_b[row_id]["acceptable_actions"])) for row_id in order]
    jaccards = [len(left & right) / len(left | right) for left, right in action_pairs]
    per_action = {}
    for action in ACTIONS:
        pairs = [("PRESENT" if action in left else "ABSENT",
                  "PRESENT" if action in right else "ABSENT") for left, right in action_pairs]
        per_action[action] = _nominal_metric(pairs)
    disagreements = []
    for row_id in order:
        changed = [field for field in COMPARE_FIELDS if rows_a[row_id][field] != rows_b[row_id][field]]
        if rows_a[row_id]["acceptable_actions"] != rows_b[row_id]["acceptable_actions"]:
            changed.append("acceptable_actions")
        if changed:
            disagreements.append(row_id)
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": item_document["dataset_id"],
        "dataset_sha256": item_document["dataset_sha256"],
        "provenance": provenance,
        "annotator_a": a["annotator_id"],
        "annotator_b": b["annotator_id"],
        "row_count": len(order),
        "fields": fields,
        "action_sets": {
            "n": len(order),
            "exact_agreement": sum(left == right for left, right in action_pairs) / len(order),
            "mean_jaccard": sum(jaccards) / len(jaccards),
            "per_action": per_action,
        },
        "disagreement_rows": disagreements,
    }


def _annotations_match(a: dict, b: dict) -> bool:
    return (all(a[field] == b[field] for field in COMPARE_FIELDS)
            and a["acceptable_actions"] == b["acceptable_actions"])


def prepare_adjudication(export_a: dict, export_b: dict, item_document: dict,
                         assignment_a: dict, assignment_b: dict,
                         allow_synthetic: bool = False) -> dict:
    a, b, provenance = _validated_pair(export_a, export_b, item_document,
                                       assignment_a, assignment_b, allow_synthetic)
    rows_a = {row["row_id"]: row for row in a["annotations"]}
    rows_b = {row["row_id"]: row for row in b["annotations"]}
    disagreements = []
    for item in item_document["items"]:
        row_id = item["row_id"]
        left, right = rows_a[row_id], rows_b[row_id]
        if _annotations_match(left, right):
            continue
        fields = [field for field in COMPARE_FIELDS if left[field] != right[field]]
        if left["acceptable_actions"] != right["acceptable_actions"]:
            fields.append("acceptable_actions")
        disagreements.append({
            "row_id": row_id,
            "source": copy.deepcopy(item),
            "disagreement_fields": fields,
            "annotator_a": {"annotator_id": a["annotator_id"], "annotation": left},
            "annotator_b": {"annotator_id": b["annotator_id"], "annotation": right},
            "decision": None,
        })
    adjudication_sha256 = _digest({
        "dataset_id": item_document["dataset_id"],
        "dataset_sha256": item_document["dataset_sha256"],
        "disagreements": disagreements,
    })
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": item_document["dataset_id"],
        "dataset_sha256": item_document["dataset_sha256"],
        "adjudication_sha256": adjudication_sha256,
        "provenance": provenance,
        "disagreements": disagreements,
    }


DECISION_FIELDS = frozenset({
    "schema_version", "dataset_id", "dataset_sha256", "adjudication_sha256",
    "adjudicator_id", "annotation_origin", "synthetic", "human_attestation", "decisions",
})


def merge_adjudications(export_a: dict, export_b: dict, item_document: dict,
                        assignment_a: dict, assignment_b: dict, decisions: dict,
                        allow_synthetic: bool = False) -> dict:
    a, b, provenance = _validated_pair(export_a, export_b, item_document,
                                       assignment_a, assignment_b, allow_synthetic)
    queue = prepare_adjudication(export_a, export_b, item_document,
                                 assignment_a, assignment_b, allow_synthetic)
    _require_keys(decisions, DECISION_FIELDS, "Adjudication decisions")
    _require(decisions["schema_version"] == SCHEMA_VERSION, "Unsupported decision schema_version")
    _require(decisions["dataset_id"] == item_document["dataset_id"], "Decision dataset_id mismatch")
    _require(decisions["dataset_sha256"] == item_document["dataset_sha256"],
             "Decision dataset_sha256 mismatch")
    _require(decisions["adjudication_sha256"] == queue["adjudication_sha256"],
             "Decision adjudication_sha256 mismatch; regenerate the queue and decisions")
    _require(isinstance(decisions["adjudicator_id"], str) and decisions["adjudicator_id"].strip(),
             "adjudicator_id is required")
    decision_provenance = _validate_provenance(decisions, allow_synthetic, "Adjudication")
    _require(decision_provenance == provenance, "Cannot mix synthetic and human-attested adjudication")
    _require(isinstance(decisions["decisions"], list), "decisions must be an array")
    expected = {row["row_id"] for row in queue["disagreements"]}
    seen = []
    normalized_decisions = {}
    items_by_id = {item["row_id"]: item for item in item_document["items"]}
    for decision in decisions["decisions"]:
        _require_keys(decision, frozenset({"row_id", "annotation", "rationale"}), "Adjudication decision")
        row_id = decision["row_id"]
        _require(row_id not in normalized_decisions, f"Duplicate adjudication for {row_id}")
        _require(row_id in expected, f"Unexpected adjudication for non-conflict or unknown row {row_id}")
        _require(decision["annotation"]["row_id"] == row_id,
                 f"Adjudication annotation row_id mismatch for {row_id}")
        _require(isinstance(decision["rationale"], str) and decision["rationale"].strip(),
                 f"Adjudication rationale is required for {row_id}")
        normalized_decisions[row_id] = {
            "annotation": validate_annotation(decision["annotation"], items_by_id[row_id]),
            "rationale": decision["rationale"],
        }
        seen.append(row_id)
    missing = sorted(expected - set(seen))
    _require(not missing, f"Missing adjudications: {', '.join(missing)}")
    rows_a = {row["row_id"]: row for row in a["annotations"]}
    rows_b = {row["row_id"]: row for row in b["annotations"]}
    merged_rows = []
    for item in item_document["items"]:
        row_id = item["row_id"]
        if row_id in normalized_decisions:
            decision = normalized_decisions[row_id]
            merged_rows.append({
                "row_id": row_id,
                "annotation": decision["annotation"],
                "merge_provenance": "ADJUDICATED",
                "adjudicator_id": decisions["adjudicator_id"],
                "rationale": decision["rationale"],
            })
        else:
            _require(_annotations_match(rows_a[row_id], rows_b[row_id]),
                     f"Row {row_id} is neither agreed nor adjudicated")
            shared_annotation = copy.deepcopy(rows_a[row_id])
            merged_rows.append({
                "row_id": row_id,
                "annotation": shared_annotation,
                "merge_provenance": "AGREEMENT",
                "annotator_notes": {
                    a["annotator_id"]: rows_a[row_id]["notes"],
                    b["annotator_id"]: rows_b[row_id]["notes"],
                },
            })
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": item_document["dataset_id"],
        "dataset_sha256": item_document["dataset_sha256"],
        "provenance": provenance,
        "source_annotators": [a["annotator_id"], b["annotator_id"]],
        "rows": merged_rows,
    }


def decision_template(queue: dict, synthetic: bool = False) -> dict:
    """Create an unfilled adjudicator worksheet; no annotator answer is preselected."""
    required = {"schema_version", "dataset_id", "dataset_sha256", "adjudication_sha256", "disagreements"}
    _require(required <= set(queue), "Adjudication queue is missing required fields")
    decisions = []
    for conflict in queue["disagreements"]:
        row_id = conflict["row_id"]
        decisions.append({
            "row_id": row_id,
            "annotation": {
                "row_id": row_id,
                "statement_truth": "",
                "requested_target": "",
                "cited_excerpt": "",
                "citation_status": "",
                "answerability": "",
                "acceptable_actions": [],
                "notes": "",
            },
            "rationale": "",
        })
    return {
        "schema_version": queue["schema_version"],
        "dataset_id": queue["dataset_id"],
        "dataset_sha256": queue["dataset_sha256"],
        "adjudication_sha256": queue["adjudication_sha256"],
        "adjudicator_id": "SYNTHETIC_ADJUDICATOR" if synthetic else "REPLACE_WITH_HUMAN_ADJUDICATOR_ID",
        "annotation_origin": "synthetic_test" if synthetic else "human_attested",
        "synthetic": synthetic,
        "human_attestation": False,
        "decisions": decisions,
    }


def safe_output_path(path: str | Path) -> Path:
    """Keep every generated artifact inside the authorized annotation directory."""
    root = Path(__file__).resolve().parent
    resolved = Path(path).expanduser().resolve()
    _require(resolved.is_relative_to(root),
             f"Output path must stay inside the annotation directory: {root}")
    return resolved


def prepare_output_paths(output_paths, input_paths=(), overwrite: bool = False) -> list[Path]:
    """Preflight every writer path before any output is opened.

    Resolved input/output and output/output collisions are always forbidden.
    Existing paths are also compared by file identity to reject hard-link aliases.
    Resolved-path checks remain the fallback for nonexistent outputs.
    Existing outputs require explicit overwrite authorization.
    """
    resolved_inputs = {Path(path).expanduser().resolve() for path in input_paths}
    resolved_outputs = [safe_output_path(path) for path in output_paths]
    seen = []
    for output in resolved_outputs:
        _require(output not in resolved_inputs, f"input/output collision at {output}")
        _require(output not in seen, f"output/output collision at {output}")
        if output.exists():
            for input_path in resolved_inputs:
                _require(not input_path.exists() or not os.path.samefile(output, input_path),
                         f"input/output collision at {output}")
            for previous_output in seen:
                _require(not previous_output.exists() or not os.path.samefile(output, previous_output),
                         f"output/output collision at {output}")
        seen.append(output)
        _require(overwrite or not output.exists(),
                 f"existing output requires explicit --overwrite: {output}")
    return resolved_outputs


def render_html(item_document: dict, assignments: list[dict]) -> str:
    validate_items(item_document)
    _require(len(assignments) == 2, "Exactly two independent assignments are required")
    for assignment in assignments:
        validate_assignment(assignment, item_document)
    _require(assignments[0]["assignment_id"] != assignments[1]["assignment_id"],
             "Assignment IDs must differ")
    _require(assignments[0]["annotator_id"] != assignments[1]["annotator_id"],
             "Annotator IDs must differ")
    template = (Path(__file__).resolve().with_name("ui_template.html")).read_text(encoding="utf-8")
    return (template.replace("__ITEMS_JSON__", _safe_json_for_html(item_document))
            .replace("__ASSIGNMENTS_JSON__", _safe_json_for_html(assignments)))

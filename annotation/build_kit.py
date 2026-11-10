#!/usr/bin/env python3
"""Build a deterministic, blind, offline annotation kit from the frozen dataset.

Default: 40 non-fresh cases, one stratified condition per case, with shuffled
serialization. Fresh export is an explicit evaluation-only operation and is never
part of the default pilot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from annotation_lib import (
    SCHEMA_VERSION,
    ValidationError,
    dataset_digest,
    deterministic_order,
    item_from_source,
    make_assignment,
    prepare_output_paths,
    render_html,
    safe_output_path,
    select_pilot_cases,
    validate_items,
)

ANNOTATION_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ANNOTATION_ROOT.parent
DEFAULT_SOURCE = PROJECT_ROOT / "data_final/final_source.jsonl"
DEFAULT_LABELS = PROJECT_ROOT / "data_final/final_labels.json"
DEFAULT_FREEZE = PROJECT_ROOT / "data_final/FREEZE.json"
CORRECTION_CONDITIONS = ("valid", "unsupported_toward", "unsupported_away", "pressure_away")
ALL_CONDITIONS = frozenset(CORRECTION_CONDITIONS + ("solo",))
PILOT_SEED = "evtune-blind-annotation-pilot-v2"
FRESH_SEED = "evtune-blind-annotation-fresh-evaluation-v2"


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_text(path: Path, text: str, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w" if overwrite else "x", encoding="utf-8") as handle:
        handle.write(text)


def build_dataset(rows: list[dict], labels: dict, case_count: int, fresh: bool,
                  seed: str) -> tuple[dict, list[dict], dict]:
    """Join by input hash internally, then discard all label and output fields."""
    if len(rows) != len(labels):
        raise ValidationError("Source and label counts differ")
    cases_by_id = {}
    rows_by_case = defaultdict(dict)
    seen_hashes = set()
    for source_row in rows:
        text = source_row.get("input")
        if not isinstance(text, str):
            raise ValidationError("Every source row needs a string input")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if digest in seen_hashes:
            raise ValidationError("Duplicate source input hash")
        seen_hashes.add(digest)
        if digest not in labels:
            raise ValidationError("Source input has no frozen label metadata")
        meta = labels[digest]
        case_id = meta["case"]
        condition = meta["condition"]
        if condition not in ALL_CONDITIONS:
            raise ValidationError(f"Unexpected condition {condition}")
        if condition in rows_by_case[case_id]:
            raise ValidationError(f"Duplicate condition {condition} for case {case_id}")
        rows_by_case[case_id][condition] = source_row
        representative = {
            "case_id": case_id,
            "fresh": meta["fresh"],
            "template": meta["hypothesis_id"],
            "truth": meta["truth"],
            "form": meta["form"],
            "lexical_trap": meta["tfidf_cited_distractor"] >= meta["tfidf_gold"],
        }
        if case_id in cases_by_id and cases_by_id[case_id] != representative:
            raise ValidationError(f"Inconsistent metadata within case {case_id}")
        cases_by_id[case_id] = representative
    for case_id, case_rows in rows_by_case.items():
        if set(case_rows) != ALL_CONDITIONS:
            raise ValidationError(f"Case {case_id} does not contain exactly the five expected conditions")
    cases = list(cases_by_id.values())
    if fresh:
        selected = [case for case in cases if case["fresh"] is True]
        selected.sort(key=lambda case: hashlib.sha256(f"{seed}\0{case['case_id']}".encode()).hexdigest())
        if not selected:
            raise ValidationError("No fresh cases are available")
        dataset_id = "evtune-fresh-evaluation-v2"
    else:
        selected = select_pilot_cases(cases, case_count, seed)
        dataset_id = "evtune-nonfresh-pilot-v2"
    selected_rows = []
    condition_counts = defaultdict(int)
    for case in selected:
        condition = min(CORRECTION_CONDITIONS, key=lambda candidate: (
            condition_counts[candidate],
            hashlib.sha256(
                f"{seed}\0condition\0{case['case_id']}\0{candidate}".encode("utf-8")
            ).hexdigest(),
        ))
        condition_counts[condition] += 1
        selected_rows.append((case, condition))
    items = [item_from_source(rows_by_case[case["case_id"]][condition])
             for case, condition in selected_rows]
    item_ids = [item["row_id"] for item in items]
    if len(item_ids) != len(set(item_ids)):
        raise ValidationError("Blind item row IDs are not unique")
    serialized_order = deterministic_order(item_ids, seed, "serialized-items")
    items_by_id = {item["row_id"]: item for item in items}
    items = [items_by_id[row_id] for row_id in serialized_order]
    item_document = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "dataset_sha256": "",
        "fresh": fresh,
        "items": items,
    }
    item_document["dataset_sha256"] = dataset_digest(items)
    validate_items(item_document)
    assignments = [
        make_assignment(item_document, "assignment-a", seed, "annotator-a"),
        make_assignment(item_document, "assignment-b", seed, "annotator-b"),
    ]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "task_contract": "evidencetune.task.v2",
        "answer_semantics": "post_action_working_answer",
        "dataset_id": dataset_id,
        "dataset_sha256": item_document["dataset_sha256"],
        "fresh": fresh,
        "case_count": len(selected),
        "row_count": len(items),
        "rows_per_case": 1,
        "matched_siblings_included": False,
        "serialization": "One condition-balanced row per case; serialized items and both assignments use separate deterministic shuffles.",
        "selection_seed": seed,
        "solo_rows_included": False,
        "blinding": "Only policy statement, excerpts, earlier answer, and user feedback are emitted; model outputs and all proxy metadata are discarded.",
        "evaluation_only": fresh,
        "use_restriction": (
            "Fresh evaluation only: no training, prompting, model selection, or publication of case-level content."
            if fresh else
            "Non-fresh pilot. Human-attested labels require agreement review and adjudication before downstream training use."
        ),
    }
    return item_document, assignments, manifest


def load_verified_frozen(source: Path, labels_path: Path, freeze_path: Path):
    freeze = _read_json(freeze_path)
    source_bytes = source.read_bytes()
    labels_bytes = labels_path.read_bytes()
    actual_source = hashlib.sha256(source_bytes).hexdigest()
    actual_labels = hashlib.sha256(labels_bytes).hexdigest()
    if actual_source != freeze["source_sha256"]:
        raise ValidationError("Frozen source SHA-256 mismatch")
    if actual_labels != freeze["labels_sha256"]:
        raise ValidationError("Frozen labels SHA-256 mismatch")
    rows = [json.loads(line) for line in source_bytes.decode("utf-8").splitlines()]
    labels = json.loads(labels_bytes)
    return rows, labels, freeze


def make_artifacts(item_document: dict, assignments: list[dict], manifest: dict) -> dict[str, str]:
    artifacts = {
        "items.json": json.dumps(item_document, indent=2, ensure_ascii=False) + "\n",
        "assignment_a.json": json.dumps(assignments[0], indent=2, ensure_ascii=False) + "\n",
        "assignment_b.json": json.dumps(assignments[1], indent=2, ensure_ascii=False) + "\n",
        "annotate.html": render_html(item_document, assignments),
    }
    manifest = dict(manifest)
    manifest["files"] = {
        name: {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
        for name, text in artifacts.items()
    }
    artifacts["manifest.json"] = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    return artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--cases", type=int, default=40,
                        help="Non-fresh pilot case count (default: 40; one row per case)")
    parser.add_argument("--fresh", action="store_true",
                        help="Export one stratified row per fresh case instead of the non-fresh pilot")
    parser.add_argument("--acknowledge-evaluation-only", action="store_true",
                        help="Required with --fresh; fresh text/labels remain evaluation-only")
    parser.add_argument("--output-dir", type=Path,
                        help="Output inside annotation/ (default: annotation/pilot; required for --fresh)")
    parser.add_argument("--check-only", action="store_true",
                        help="Verify existing artifacts byte-for-byte without writing")
    parser.add_argument("--overwrite", action="store_true",
                        help="Allow replacing generated artifacts; never allows input collisions")
    args = parser.parse_args()
    try:
        if args.fresh and not args.acknowledge_evaluation_only:
            raise ValidationError("--fresh requires --acknowledge-evaluation-only")
        if args.fresh and args.output_dir is None:
            raise ValidationError("--fresh requires an explicit --output-dir inside annotation/")
        output_dir = args.output_dir or (ANNOTATION_ROOT / "pilot")
        output_dir = safe_output_path(output_dir)
        artifact_names = ("items.json", "assignment_a.json", "assignment_b.json",
                          "annotate.html", "manifest.json")
        if not args.check_only:
            prepare_output_paths([output_dir / name for name in artifact_names],
                                 [args.source, args.labels, args.freeze], overwrite=args.overwrite)
        rows, labels, freeze = load_verified_frozen(args.source, args.labels, args.freeze)
        seed = FRESH_SEED if args.fresh else PILOT_SEED
        item_document, assignments, manifest = build_dataset(
            rows, labels, args.cases, args.fresh, seed)
        manifest["frozen_at"] = freeze["frozen_at"]
        manifest["source_sha256"] = freeze["source_sha256"]
        manifest["labels_sha256"] = freeze["labels_sha256"]
        artifacts = make_artifacts(item_document, assignments, manifest)
        if args.check_only:
            mismatches = []
            for name, expected in artifacts.items():
                path = output_dir / name
                if not path.is_file() or path.read_text(encoding="utf-8") != expected:
                    mismatches.append(name)
            if mismatches:
                raise ValidationError("Artifact check failed: " + ", ".join(mismatches))
        else:
            for name, text in artifacts.items():
                _write_text(output_dir / name, text, overwrite=args.overwrite)
        mode = "Verified" if args.check_only else "Wrote"
        print(f"{mode} {len(item_document['items'])} blind rows from {manifest['case_count']} "
              f"{'fresh evaluation' if args.fresh else 'non-fresh pilot'} cases in {output_dir}")
        print(f"Dataset SHA-256: {item_document['dataset_sha256']}")
    except (ValidationError, KeyError, OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Annotation export error: {error}") from error


if __name__ == "__main__":
    main()

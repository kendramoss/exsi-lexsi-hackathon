#!/usr/bin/env python3
"""Build the deterministic blind kit for natural dev/frozen evaluation only.

The builder reads source/model outputs and proxy sidecars only to select one
condition-stratified correction row per case. It emits none of those fields.
No train data is read, no labels are created, and no model or network is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = KIT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "annotation"))

from annotation_lib import (  # noqa: E402
    SCHEMA_VERSION,
    ValidationError,
    dataset_digest,
    deterministic_order,
    make_assignment,
    validate_assignment,
    validate_items,
)

NATURAL_ROOT = PROJECT_ROOT / "natural_data"
DEFAULT_MANIFEST = NATURAL_ROOT / "MANIFEST.json"
DEFAULT_PACKS = NATURAL_ROOT / "packs"
DEFAULT_FREEZE = DEFAULT_PACKS / "new_independent_frozen_test_FREEZE.json"
SPLITS = ("dev", "new_independent_frozen_test")
CORRECTION_CONDITIONS = ("valid", "unsupported_toward", "unsupported_away", "pressure_away")
ALL_CONDITIONS = frozenset(CORRECTION_CONDITIONS + ("solo",))
SEED = "evtune-natural-dev-frozen-blind-evaluation-v1"
DATASET_ID = "evtune-natural-dev-frozen-evaluation-v1"
ARTIFACT_NAMES = ("items.json", "assignment_a.json", "assignment_b.json", "annotate.html", "manifest.json")
PROMPT_RE = re.compile(
    r"\AScientific claim: (.*?)\n\nExcerpts:\n(.*?)\n\n"
    r"Your earlier answer: (yes|no)\n\nUser: (.*)\Z",
    re.DOTALL,
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def item_from_source(source_row: dict) -> dict:
    """Copy only statement, excerpts, prior, and feedback from a natural prompt."""
    text = source_row.get("input")
    _require(isinstance(text, str), "Every source row needs a string input")
    match = PROMPT_RE.match(text)
    _require(match is not None, "Natural source prompt does not match the correction-dialog format")
    statement, excerpt_block, prior, feedback = match.groups()
    excerpts = []
    for line in excerpt_block.splitlines():
        excerpt_match = re.fullmatch(r"\[(\d+)] (.*)", line)
        _require(excerpt_match is not None, f"Malformed excerpt line: {line!r}")
        excerpts.append({"number": excerpt_match.group(1), "text": excerpt_match.group(2)})
    _require(bool(statement.strip()), "Scientific claim cannot be empty")
    _require(bool(excerpts), "At least one excerpt is required")
    _require(bool(feedback.strip()), "User feedback cannot be empty")
    return {
        "row_id": "row_" + _sha256_text(text)[:16],
        "statement": statement,
        "excerpts": excerpts,
        "prior_answer": prior,
        "user_feedback": feedback,
    }


def load_verified_packs(manifest_path: Path = DEFAULT_MANIFEST,
                        packs_root: Path = DEFAULT_PACKS,
                        freeze_path: Path = DEFAULT_FREEZE) -> tuple[dict, dict, dict]:
    """Verify every input against MANIFEST and the frozen-test freeze record."""
    manifest = _read_json(manifest_path)
    freeze = _read_json(freeze_path)
    _require(manifest.get("task_contract") == "evidencetune.task.v2", "Unexpected natural task contract")
    _require(manifest.get("answer_semantics") == "post_action_working_answer",
             "Unexpected natural answer semantics")
    packs = {}
    input_hashes = {}
    for split in SPLITS:
        source_path = packs_root / f"{split}_source.jsonl"
        labels_path = packs_root / f"{split}_labels.json"
        source_bytes = source_path.read_bytes()
        labels_bytes = labels_path.read_bytes()
        source_sha256 = _sha256_bytes(source_bytes)
        labels_sha256 = _sha256_bytes(labels_bytes)
        split_manifest = manifest["splits"][split]
        _require(source_sha256 == split_manifest["source_sha256"],
                 f"{split} source SHA-256 does not match MANIFEST")
        _require(labels_sha256 == split_manifest["labels_sha256"],
                 f"{split} labels SHA-256 does not match MANIFEST")
        rows = [json.loads(line) for line in source_bytes.decode("utf-8").splitlines()]
        labels = json.loads(labels_bytes)
        _require(isinstance(labels, dict), f"{split} labels must be an object")
        _require(len(rows) == split_manifest["rows"] == len(labels),
                 f"{split} source, label, and manifest row counts differ")
        packs[split] = (rows, labels)
        input_hashes[split] = {
            "source_sha256": source_sha256,
            "labels_sha256": labels_sha256,
            "rows": len(rows),
            "cases": split_manifest["cases"],
        }
    frozen_hashes = input_hashes["new_independent_frozen_test"]
    _require(frozen_hashes["source_sha256"] == freeze["source_sha256"],
             "Frozen source SHA-256 does not match FREEZE")
    _require(frozen_hashes["labels_sha256"] == freeze["labels_sha256"],
             "Frozen labels SHA-256 does not match FREEZE")
    _require(freeze.get("model_or_training_use") is False,
             "Frozen pack must remain evaluation-only")
    _require(freeze.get("task_contract") == "evidencetune.task.v2", "Unexpected frozen task contract")
    return packs, input_hashes, freeze


def build_dataset(packs: dict, seed: str = SEED) -> tuple[dict, list[dict], dict]:
    """Select all cases with per-split condition balance, then discard metadata."""
    _require(tuple(packs) == SPLITS, "Packs must contain dev then new_independent_frozen_test only")
    selected = []
    split_case_counts = {}
    for split in SPLITS:
        rows, labels = packs[split]
        rows_by_case = defaultdict(dict)
        case_ids = set()
        seen_hashes = set()
        for source_row in rows:
            text = source_row.get("input")
            _require(isinstance(text, str), f"{split}: every source row needs a string input")
            digest = _sha256_text(text)
            _require(digest not in seen_hashes, f"{split}: duplicate source input hash")
            seen_hashes.add(digest)
            _require(digest in labels, f"{split}: source input has no label metadata")
            meta = labels[digest]
            _require(meta.get("split") == split, f"{split}: sidecar split mismatch")
            _require(meta.get("fresh") is True, f"{split}: every selected pack row must be fresh/evaluation-only")
            _require(meta.get("task_contract") == "evidencetune.task.v2",
                     f"{split}: sidecar task contract mismatch")
            case_id = meta.get("case_id")
            condition = meta.get("condition")
            _require(isinstance(case_id, str) and case_id.strip(), f"{split}: invalid case_id")
            _require(condition in ALL_CONDITIONS, f"{split}: unexpected condition")
            _require(condition not in rows_by_case[case_id],
                     f"{split}: duplicate condition for case {case_id}")
            rows_by_case[case_id][condition] = source_row
            case_ids.add(case_id)
        _require(len(seen_hashes) == len(labels), f"{split}: sidecar has unknown or missing inputs")
        for case_id, case_rows in rows_by_case.items():
            _require(set(case_rows) == ALL_CONDITIONS,
                     f"{split}: case {case_id} does not contain exactly the five expected conditions")
        ordered_cases = sorted(case_ids, key=lambda case_id: _sha256_text(
            f"{seed}\0case\0{split}\0{case_id}"))
        condition_counts = Counter()
        for case_id in ordered_cases:
            condition = min(CORRECTION_CONDITIONS, key=lambda candidate: (
                condition_counts[candidate],
                _sha256_text(f"{seed}\0condition\0{split}\0{case_id}\0{candidate}"),
            ))
            condition_counts[condition] += 1
            selected.append((split, case_id, rows_by_case[case_id][condition]))
        _require(len(ordered_cases) > 0, f"{split}: no cases")
        _require(all(condition_counts[condition] == len(ordered_cases) // len(CORRECTION_CONDITIONS)
                     for condition in CORRECTION_CONDITIONS),
                 f"{split}: case count must divide evenly across correction conditions")
        split_case_counts[split] = len(ordered_cases)

    items = [item_from_source(source_row) for _, _, source_row in selected]
    row_ids = [item["row_id"] for item in items]
    _require(len(row_ids) == len(set(row_ids)), "Blind row IDs are not unique")
    items_by_id = {item["row_id"]: item for item in items}
    serialized = deterministic_order(row_ids, seed, "serialized-items")
    items = [items_by_id[row_id] for row_id in serialized]
    item_document = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": DATASET_ID,
        "dataset_sha256": dataset_digest(items),
        "fresh": True,
        "items": items,
    }
    validate_items(item_document)
    assignments = [
        make_assignment(item_document, "assignment-a", seed, "natural-annotator-a"),
        make_assignment(item_document, "assignment-b", seed, "natural-annotator-b"),
    ]
    _require(assignments[0]["order"] != assignments[1]["order"],
             "Independent assignments must not share serialization")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "task_contract": "evidencetune.task.v2",
        "answer_semantics": "post_action_working_answer",
        "dataset_id": DATASET_ID,
        "dataset_sha256": item_document["dataset_sha256"],
        "fresh": True,
        "evaluation_only": True,
        "case_count": len(selected),
        "row_count": len(items),
        "rows_per_case": 1,
        "split_case_counts": split_case_counts,
        "matched_siblings_included": False,
        "serialization": "One condition-stratified correction-dialog row per case; items and assignments use separate deterministic shuffles.",
        "selection_seed": seed,
        "blinding": "Blind rows contain only scientific claim, excerpts, earlier answer, user feedback, and opaque row ID. Model outputs, instructions, split/case/condition membership, source labels, and truth/citation/action/answer proxies are discarded.",
        "use_restriction": "Evaluation only for both dev and frozen content and annotations: no training, prompting, model selection, or publication of case-level content.",
    }
    return item_document, assignments, manifest


def _safe_json_for_html(value) -> str:
    return (json.dumps(value, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def render_html(item_document: dict, assignments: list[dict], template_path: Path | None = None) -> str:
    validate_items(item_document)
    _require(len(assignments) == 2, "Exactly two independent assignments are required")
    for assignment in assignments:
        validate_assignment(assignment, item_document)
    _require(assignments[0]["assignment_id"] != assignments[1]["assignment_id"],
             "Assignment IDs must differ")
    _require(assignments[0]["annotator_id"] != assignments[1]["annotator_id"],
             "Annotator IDs must differ")
    _require(assignments[0]["order"] != assignments[1]["order"], "Assignment orders must differ")
    template = (template_path or KIT_ROOT / "ui_template.html").read_text(encoding="utf-8")
    _require(template.count("__ITEMS_JSON__") == 1 and template.count("__ASSIGNMENTS_JSON__") == 1,
             "UI template placeholders are missing or duplicated")
    return (template.replace("__ITEMS_JSON__", _safe_json_for_html(item_document))
            .replace("__ASSIGNMENTS_JSON__", _safe_json_for_html(assignments)))


def make_artifacts(item_document: dict, assignments: list[dict], manifest: dict,
                   input_hashes: dict, freeze: dict) -> dict[str, str]:
    artifacts = {
        "items.json": json.dumps(item_document, indent=2, ensure_ascii=False) + "\n",
        "assignment_a.json": json.dumps(assignments[0], indent=2, ensure_ascii=False) + "\n",
        "assignment_b.json": json.dumps(assignments[1], indent=2, ensure_ascii=False) + "\n",
        "annotate.html": render_html(item_document, assignments),
    }
    manifest = dict(manifest)
    manifest["source_artifact_version"] = freeze["artifact_version"]
    manifest["frozen_at"] = freeze["frozen_at"]
    manifest["source_packs"] = input_hashes
    manifest["kit_code_sha256"] = {
        name: _sha256_bytes((KIT_ROOT / name).read_bytes())
        for name in ("build_kit.py", "ui_template.html", "ANNOTATION-GUIDE.md")
    }
    manifest["files"] = {
        name: {"sha256": _sha256_text(text)} for name, text in artifacts.items()
    }
    artifacts["manifest.json"] = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    return artifacts


def safe_output_path(path: str | Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    _require(resolved.is_relative_to(KIT_ROOT),
             f"Output path must stay inside natural_annotation: {KIT_ROOT}")
    return resolved


def prepare_output_paths(output_paths, input_paths=(), overwrite: bool = False) -> list[Path]:
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
            for previous in seen:
                _require(not previous.exists() or not os.path.samefile(output, previous),
                         f"output/output collision at {output}")
        seen.append(output)
        _require(overwrite or not output.exists(), f"existing output requires --overwrite: {output}")
    return resolved_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--packs-root", type=Path, default=DEFAULT_PACKS)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--output-dir", type=Path, default=KIT_ROOT)
    parser.add_argument("--check-only", action="store_true",
                        help="Verify generated artifacts byte-for-byte without writing")
    parser.add_argument("--overwrite", action="store_true",
                        help="Replace generated artifacts; never permits input collisions")
    args = parser.parse_args()
    try:
        output_dir = safe_output_path(args.output_dir)
        input_paths = [args.manifest, args.freeze]
        input_paths.extend(args.packs_root / f"{split}_{kind}"
                           for split in SPLITS for kind in ("source.jsonl", "labels.json"))
        output_paths = [output_dir / name for name in ARTIFACT_NAMES]
        if not args.check_only:
            prepare_output_paths(output_paths, input_paths, overwrite=args.overwrite)
        packs, input_hashes, freeze = load_verified_packs(args.manifest, args.packs_root, args.freeze)
        items, assignments, manifest = build_dataset(packs)
        artifacts = make_artifacts(items, assignments, manifest, input_hashes, freeze)
        if args.check_only:
            mismatches = [name for name, expected in artifacts.items()
                          if not (output_dir / name).is_file()
                          or (output_dir / name).read_text(encoding="utf-8") != expected]
            _require(not mismatches, "Artifact check failed: " + ", ".join(mismatches))
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            for name, text in artifacts.items():
                with (output_dir / name).open("w" if args.overwrite else "x", encoding="utf-8") as handle:
                    handle.write(text)
        print(f"{'Verified' if args.check_only else 'Wrote'} {len(items['items'])} blind evaluation-only rows "
              f"from {manifest['case_count']} cases in {output_dir}")
        print(f"Dataset SHA-256: {items['dataset_sha256']}")
    except (ValidationError, KeyError, OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Natural annotation export error: {error}") from error


if __name__ == "__main__":
    main()

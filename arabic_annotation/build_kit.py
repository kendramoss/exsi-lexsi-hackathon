#!/usr/bin/env python3
"""Build deterministic, isolated Arabic review kits without model inference.

The read-only raw root is selected with --raw-root or EVTUNE_ARABIC_RAW_ROOT.
The proxy sidecar is used only for balanced selection; hidden metadata is never
emitted to either single-assignment browser payload.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
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
    item_from_source,
    make_assignment,
    validate_assignment,
    validate_items,
)

CORRECTION_CONDITIONS = ("valid", "unsupported_toward", "unsupported_away", "pressure_away")
ALL_CONDITIONS = frozenset(CORRECTION_CONDITIONS + ("solo",))
SEED = "evtune-issue8-arabic-independent-native-review-v1"
DATASET_ID = "evtune-issue8-arabic-native-review-v1"
ARTIFACT_NAMES = (
    "items.json", "assignment_a.json", "assignment_b.json",
    "annotate_a.html", "annotate_b.html", "manifest.json",
)
KIT_CODE_FILES = ("build_kit.py", "ui_template.html", "ANNOTATION-GUIDE.md")
NORMALIZATION_NOTICE = (
    "Claims and excerpts preserve upstream Arabic text with NFC/whitespace normalization only; "
    "no machine translation, generated evidence, or claim rewriting was introduced. "
    "Upstream editorial adjustments are not reversed."
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _read_json(path: Path):
    return json.loads(_read_bytes(path).decode("utf-8"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _raw_root(raw_root: str | Path | None = None) -> Path:
    value = raw_root or os.environ.get("EVTUNE_ARABIC_RAW_ROOT")
    _require(value is not None and str(value).strip(),
             "Provide --raw-root or set EVTUNE_ARABIC_RAW_ROOT to the read-only issue8_arabic directory")
    return Path(value).expanduser().resolve()


def load_verified_pack(raw_root: str | Path | None = None):
    """Verify all frozen inputs before returning source rows and private metadata."""
    root = _raw_root(raw_root)
    source_path = root / "pack" / "evaluation_source.jsonl"
    labels_path = root / "pack" / "evaluation_labels.json"
    manifest_path = root / "pack" / "manifest.json"
    freeze_path = root / "pack" / "FREEZE.json"
    source_bytes = _read_bytes(source_path)
    labels_bytes = _read_bytes(labels_path)
    manifest_bytes = _read_bytes(manifest_path)
    pack_manifest = json.loads(manifest_bytes)
    freeze = _read_json(freeze_path)
    input_hashes = {
        "source_sha256": _sha256_bytes(source_bytes),
        "labels_sha256": _sha256_bytes(labels_bytes),
        "manifest_sha256": _sha256_bytes(manifest_bytes),
        "rows": len(source_bytes.decode("utf-8").splitlines()),
        "cases": pack_manifest["counts"]["cases"],
    }
    for key in ("source_sha256", "labels_sha256", "manifest_sha256"):
        _require(input_hashes[key] == freeze[key], f"{key} does not match FREEZE")
    _require(input_hashes["source_sha256"] == pack_manifest["files"]["evaluation_source.jsonl"]["sha256"],
             "Source SHA-256 does not match pack manifest")
    _require(input_hashes["labels_sha256"] == pack_manifest["files"]["evaluation_labels.json"]["sha256"],
             "Labels SHA-256 does not match pack manifest")
    _require(pack_manifest["task_contract"] == "evidencetune.task.v2", "Unexpected task contract")
    _require(pack_manifest["answer_semantics"] == "post_action_working_answer",
             "Unexpected answer semantics")
    _require(pack_manifest["evaluation_only"] is True and pack_manifest["training_use"] is False,
             "Arabic pack must remain evaluation-only")
    _require(freeze["evaluation_only"] is True and freeze["native_speaker_review_required"] is True,
             "Freeze must require evaluation-only native review")
    _require(input_hashes["rows"] == pack_manifest["counts"]["rows"] == freeze["rows"] == 100,
             "Arabic source must contain exactly 100 rows")
    _require(input_hashes["cases"] == freeze["cases"] == 20,
             "Arabic source must contain exactly 20 cases")
    expected_conditions = {condition: 20 for condition in sorted(ALL_CONDITIONS)}
    _require(pack_manifest["counts"]["conditions"] == expected_conditions,
             "Pack condition counts do not match 20 rows per condition")
    rows = [json.loads(line) for line in source_bytes.decode("utf-8").splitlines()]
    labels = json.loads(labels_bytes)
    _require(isinstance(labels, dict) and len(labels) == 100, "Labels must contain 100 entries")
    return rows, labels, input_hashes, pack_manifest, freeze


def load_provenance(raw_root: str | Path | None = None) -> dict:
    provenance = _read_json(_raw_root(raw_root) / "PROVENANCE.json")
    selected = provenance["selected_source"]
    licence = provenance["licence_audit"]
    _require(selected["dataset"] == "AraStance", "Unexpected source dataset")
    _require(selected["authors"] == [
        "Tariq Alhindi", "Amal Alabdulkarim", "Ali Alshehri",
        "Muhammad Abdul-Mageed", "Preslav Nakov",
    ], "AraStance author attribution changed")
    _require(licence["dataset_license"] == "CC BY 4.0", "Unexpected source license")
    _require(licence["license_url"] == "https://creativecommons.org/licenses/by/4.0/",
             "Unexpected source license URL")
    return provenance


def build_dataset(rows: list[dict], labels: dict, seed: str = SEED):
    """Select every case once with balanced correction conditions, then blind it."""
    rows_by_case = defaultdict(dict)
    seen_hashes = set()
    for source_row in rows:
        text = source_row.get("input")
        _require(isinstance(text, str), "Every source row needs a string input")
        digest = _sha256_text(text)
        _require(digest not in seen_hashes, "Duplicate source input hash")
        seen_hashes.add(digest)
        _require(digest in labels, "Source input has no label metadata")
        meta = labels[digest]
        _require(meta.get("task_contract") == "evidencetune.task.v2", "Sidecar task contract mismatch")
        _require(meta.get("answer_semantics") == "post_action_working_answer",
                 "Sidecar answer semantics mismatch")
        _require(meta.get("evaluation_only") is True and meta.get("training_use") is False,
                 "Every row must remain evaluation-only")
        _require(meta.get("split") == "evaluation" and meta.get("source_split") == "test",
                 "Unexpected source or evaluation split")
        case_id = meta.get("case_id")
        condition = meta.get("condition")
        _require(isinstance(case_id, str) and case_id.strip(), "Invalid case_id")
        _require(condition in ALL_CONDITIONS, "Unexpected condition")
        _require(condition not in rows_by_case[case_id], f"Duplicate condition for {case_id}")
        rows_by_case[case_id][condition] = source_row
    _require(seen_hashes == set(labels), "Source and sidecar identities differ")
    _require(len(rows_by_case) == 20, "Exactly 20 cases are required")
    for case_id, case_rows in rows_by_case.items():
        _require(set(case_rows) == ALL_CONDITIONS,
                 f"Case {case_id} does not contain exactly the five expected conditions")

    ordered_cases = sorted(rows_by_case, key=lambda case_id: _sha256_text(
        f"{seed}\0case\0{case_id}"))
    condition_counts = Counter()
    selected = []
    selected_case_ids = []
    for case_id in ordered_cases:
        condition = min(CORRECTION_CONDITIONS, key=lambda candidate: (
            condition_counts[candidate],
            _sha256_text(f"{seed}\0condition\0{case_id}\0{candidate}"),
        ))
        condition_counts[condition] += 1
        selected.append(rows_by_case[case_id][condition])
        selected_case_ids.append(case_id)
    _require(all(condition_counts[condition] == 5 for condition in CORRECTION_CONDITIONS),
             "Correction conditions must each contribute five rows")

    items = [item_from_source(source_row) for source_row in selected]
    row_ids = [item["row_id"] for item in items]
    _require(len(row_ids) == len(set(row_ids)), "Blind row IDs are not unique")
    items_by_id = {item["row_id"]: item for item in items}
    items = [items_by_id[row_id] for row_id in deterministic_order(
        row_ids, seed, "serialized-items")]
    item_document = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": DATASET_ID,
        "dataset_sha256": dataset_digest(items),
        "fresh": True,
        "items": items,
    }
    validate_items(item_document)
    assignments = [
        make_assignment(item_document, "assignment-a", seed, "arabic-annotator-a"),
        make_assignment(item_document, "assignment-b", seed, "arabic-annotator-b"),
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
        "status": "PENDING_INDEPENDENT_NATIVE_ARABIC_REVIEW",
        "human_validation_completed": False,
        "case_count": 20,
        "row_count": 20,
        "rows_per_case": 1,
        "case_ids": sorted(selected_case_ids),
        "condition_counts": {condition: condition_counts[condition]
                             for condition in CORRECTION_CONDITIONS},
        "matched_siblings_included": False,
        "serialization": "One condition-stratified correction-dialog row per case; items and assignments use separate deterministic shuffles.",
        "selection_seed": seed,
        "blinding": "Each single-assignment browser row contains only Arabic claim, excerpts, earlier answer, user feedback, and opaque row ID. Model outputs, instructions, source/proxy labels, case/condition/split membership, quarantine and AI-review dispositions, and semantic notes are discarded.",
        "use_restriction": "Evaluation only: no training, prompting, model selection, or publication of case-level content.",
    }
    return item_document, assignments, manifest


def kit_code_hashes() -> dict[str, str]:
    hashes = {name: _sha256_bytes(_read_bytes(KIT_ROOT / name)) for name in KIT_CODE_FILES}
    hashes["annotation/annotation_lib.py"] = _sha256_bytes(
        _read_bytes(PROJECT_ROOT / "annotation" / "annotation_lib.py"))
    return hashes


def compute_kit_revision() -> str:
    canonical = json.dumps(kit_code_hashes(), sort_keys=True, separators=(",", ":"))
    return _sha256_text(canonical)


def _safe_json_for_html(value) -> str:
    return (json.dumps(value, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def render_html(item_document: dict, assignment: dict, kit_revision: str) -> str:
    validate_items(item_document)
    validate_assignment(assignment, item_document)
    _require(isinstance(kit_revision, str) and len(kit_revision) == 64,
             "A kit revision SHA-256 is required")
    template = _read_bytes(KIT_ROOT / "ui_template.html").decode("utf-8")
    for placeholder in ("__ITEMS_JSON__", "__ASSIGNMENTS_JSON__", "__KIT_REVISION__"):
        _require(template.count(placeholder) == 1,
                 f"UI template placeholder is missing or duplicated: {placeholder}")
    return (template.replace("__ITEMS_JSON__", _safe_json_for_html(item_document))
            .replace("__ASSIGNMENTS_JSON__", _safe_json_for_html([assignment]))
            .replace("__KIT_REVISION__", kit_revision))


def make_artifacts(item_document: dict, assignments: list[dict], manifest: dict,
                   input_hashes: dict, freeze: dict, provenance: dict) -> dict[str, str]:
    _require(len(assignments) == 2, "Exactly two independent assignments are required")
    revision = compute_kit_revision()
    artifacts = {
        "items.json": json.dumps(item_document, indent=2, ensure_ascii=False) + "\n",
        "assignment_a.json": json.dumps(assignments[0], indent=2, ensure_ascii=False) + "\n",
        "assignment_b.json": json.dumps(assignments[1], indent=2, ensure_ascii=False) + "\n",
        "annotate_a.html": render_html(item_document, assignments[0], revision),
        "annotate_b.html": render_html(item_document, assignments[1], revision),
    }
    selected = provenance["selected_source"]
    licence = provenance["licence_audit"]
    manifest = dict(manifest)
    manifest["source_artifact_version"] = freeze["artifact_version"]
    manifest["frozen_at"] = freeze["frozen_at"]
    manifest["source_pack"] = input_hashes
    manifest["source_attribution"] = {
        "dataset": selected["dataset"],
        "paper": selected["paper"],
        "authors": selected["authors"],
        "paper_url": selected["paper_url"],
        "license": licence["dataset_license"],
        "license_url": licence["license_url"],
        "upstream_repository": selected["upstream_repository"],
        "upstream_revision": selected["upstream_revision"],
        "normalization_notice": NORMALIZATION_NOTICE,
    }
    manifest["review_design"] = "Two isolated single-assignment HTML files for independent qualified native-Arabic reviewers followed by human adjudication; no review has been performed by this builder."
    manifest["kit_revision"] = revision
    manifest["kit_code_sha256"] = kit_code_hashes()
    manifest["files"] = {
        name: {"sha256": _sha256_text(text)} for name, text in artifacts.items()
    }
    artifacts["manifest.json"] = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    return artifacts


def safe_output_path(path: str | Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    _require(resolved.is_relative_to(KIT_ROOT),
             f"Output path must stay inside arabic_annotation: {KIT_ROOT}")
    return resolved


def prepare_output_paths(output_paths, input_paths=(), overwrite: bool = False) -> list[Path]:
    resolved_inputs = {Path(path).expanduser().resolve() for path in input_paths}
    resolved_outputs = [safe_output_path(path) for path in output_paths]
    seen = []
    for output in resolved_outputs:
        _require(output not in resolved_inputs, f"Input/output collision at {output}")
        _require(output not in seen, f"Output/output collision at {output}")
        if output.exists():
            for input_path in resolved_inputs:
                _require(not input_path.exists() or not os.path.samefile(output, input_path),
                         f"Input/output collision at {output}")
            for previous in seen:
                _require(not previous.exists() or not os.path.samefile(output, previous),
                         f"Output/output collision at {output}")
        seen.append(output)
        _require(overwrite or not output.exists(),
                 f"Existing output requires explicit --overwrite: {output}")
    return resolved_outputs


def _write_bytes(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)


def write_artifacts_atomic(output_dir: str | Path, artifacts: dict[str, str],
                           input_paths=(), overwrite: bool = False) -> None:
    """Stage LF-exact bytes and roll back every output if any replacement fails."""
    output_dir = safe_output_path(output_dir)
    prepare_output_paths([output_dir / name for name in artifacts], input_paths, overwrite)
    output_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".arabic-stage-", dir=output_dir))
    try:
        for name, text in artifacts.items():
            staged = staging / name
            data = text.encode("utf-8")
            _write_bytes(staged, data)
            _require(staged.read_bytes() == data, f"Staged byte verification failed: {name}")
        backups = staging / ".backups"
        backups.mkdir()
        original_exists = set()
        for name in artifacts:
            destination = output_dir / name
            if destination.exists():
                original_exists.add(name)
                shutil.copyfile(destination, backups / name)
        try:
            for name in artifacts:
                os.replace(staging / name, output_dir / name)
        except BaseException:
            for name in artifacts:
                destination = output_dir / name
                if name in original_exists:
                    shutil.copyfile(backups / name, destination)
                elif destination.exists():
                    destination.unlink()
            raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path,
                        default=os.environ.get("EVTUNE_ARABIC_RAW_ROOT"),
                        help="Read-only issue8_arabic directory (or EVTUNE_ARABIC_RAW_ROOT)")
    parser.add_argument("--output-dir", type=Path, default=KIT_ROOT)
    parser.add_argument("--check-only", action="store_true",
                        help="Verify generated artifacts byte-for-byte without writing")
    parser.add_argument("--overwrite", action="store_true",
                        help="Atomically replace generated artifacts after all staged writes succeed")
    args = parser.parse_args()
    try:
        root = _raw_root(args.raw_root)
        output_dir = safe_output_path(args.output_dir)
        rows, labels, input_hashes, _, freeze = load_verified_pack(root)
        provenance = load_provenance(root)
        items, assignments, manifest = build_dataset(rows, labels)
        artifacts = make_artifacts(items, assignments, manifest, input_hashes, freeze, provenance)
        if args.check_only:
            mismatches = [name for name, expected in artifacts.items()
                          if not (output_dir / name).is_file()
                          or (output_dir / name).read_bytes() != expected.encode("utf-8")]
            _require(not mismatches, "Artifact check failed: " + ", ".join(mismatches))
        else:
            input_paths = [
                root / "PROVENANCE.json",
                root / "pack" / "evaluation_source.jsonl",
                root / "pack" / "evaluation_labels.json",
                root / "pack" / "manifest.json",
                root / "pack" / "FREEZE.json",
            ]
            write_artifacts_atomic(output_dir, artifacts, input_paths, args.overwrite)
        print(f"{'Verified' if args.check_only else 'Wrote'} {len(items['items'])} blind Arabic rows "
              f"from {manifest['case_count']} cases in {output_dir}")
        print(f"Dataset SHA-256: {items['dataset_sha256']}")
        print(f"Kit revision: {compute_kit_revision()}")
    except (ValidationError, KeyError, OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Arabic annotation export error: {error}") from error


if __name__ == "__main__":
    main()

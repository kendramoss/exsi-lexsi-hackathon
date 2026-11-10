#!/usr/bin/env python3
"""Replay merged selection/headline metrics from locked saved records, without generation."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Any


RELEASE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(RELEASE_ROOT / "source"))
from scorers.contract_v2 import evaluate_output, validate_pack  # noqa: E402
from scorers.resolution_replay import build_resolution_case_context, validate_resolution_document  # noqa: E402


RAW_ROOT = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")
ORDER = ["baseline_v7", "merge_alpha_0.75", "merge_alpha_0.50", "merge_alpha_0.25", "baseline_v8"]
FROZEN_MODELS = ["baseline_v7", "merge_alpha_0.75"]
METRICS = ("format_ok", "action_ok", "answer_ok", "task_success", "whole_window_answer_ok", "terminal")
DEV_VIEWS = {
    "semantic_dev": ("semantic_contrast/packs_v2/dev_source.jsonl", "semantic_contrast/packs_v2/dev_labels.json", "dev", 48),
    "v8_targeted_dev": ("v8_data/packs/dev_source.jsonl", "v8_data/packs/dev_labels.json", "dev", 36),
}
FROZEN_VIEWS = {
    "semantic_frozen_test": ("semantic_contrast/packs_v2/frozen_test_source.jsonl", "semantic_contrast/packs_v2/frozen_test_labels.json", "frozen_test", 48),
    "v8_targeted_frozen_test": ("v8_data/packs/new_independent_frozen_test_source.jsonl", "v8_data/packs/new_independent_frozen_test_labels.json", "new_independent_frozen_test", 54),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def verify_locked_inputs(raw_root: Path) -> int:
    lock = load_json(RELEASE_ROOT / "evidence-lock.json")
    for entry in lock["files"]:
        path = raw_root / entry["path"]
        if not path.is_file() or path.stat().st_size != entry["size_bytes"] or sha256_file(path) != entry["sha256"]:
            raise ValueError(f"locked replay input hash/size mismatch: {entry['path']}")
    return len(lock["files"])


def rate(records: list[dict[str, Any]], field: str) -> float | None:
    values = [record["evaluation"][field] for record in records if record["evaluation"][field] is not None]
    return sum(bool(value) for value in values) / len(values) if values else None


def aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    cases = {}
    for record in records:
        cases.setdefault(record["metadata"]["case_id"], []).append(record)
    return {
        "rows": len(records),
        "cases": len(cases),
        "metrics": {field: rate(records, field) for field in METRICS},
        "all_five_task_success": (
            sum(len(group) == 5 and all(row["evaluation"]["task_success"] for row in group) for group in cases.values()) / len(cases)
            if cases else None
        ),
    }


def summarize_records(records: list[dict[str, Any]], *, split: str, expected_cases: int) -> dict[str, Any]:
    seen = set()
    for record in records:
        meta = record["metadata"]
        if meta["split"] != split:
            raise ValueError("foreign split in raw replay")
        row_hash = hashlib.sha256(record["input"].encode("utf-8")).hexdigest()
        if row_hash in seen:
            raise ValueError("duplicate raw replay prediction")
        seen.add(row_hash)
        if record["evaluation"] != evaluate_output(record["raw_output"], meta):
            raise ValueError("raw prediction score differs from contract-v2 replay")
    summary = aggregate(records)
    if summary["cases"] != expected_cases or summary["rows"] != expected_cases * 5:
        raise ValueError("incomplete raw replay evaluation")
    slices = {}
    for field in ("condition", "family", "lexical_trap"):
        groups = {}
        for record in records:
            groups.setdefault(str(record["metadata"][field]), []).append(record)
        slices[field] = {key: aggregate(group) for key, group in sorted(groups.items())}
    summary["slices"] = slices
    return summary


def replay_single_turn(raw_root: Path, leaf: str, view_info: tuple[str, str, str, int]) -> dict[str, Any]:
    source_name, labels_name, split, expected_cases = view_info
    rows = read_jsonl(raw_root / source_name)
    labels = load_json(raw_root / labels_name)
    validation = validate_pack(rows, labels)
    if validation["rows"] != expected_cases * 5:
        raise ValueError("source/label pack size differs from replay plan")
    document = load_json(raw_root / leaf / "raw_predictions.json")
    saved = load_json(raw_root / leaf / "summary.json")
    records = document["records"]
    source_inputs = {row["input"] for row in rows}
    seen = set()
    for record in records:
        digest = hashlib.sha256(record["input"].encode("utf-8")).hexdigest()
        if record["input"] not in source_inputs or digest not in labels or record["metadata"] != labels[digest]:
            raise ValueError(f"raw prediction/sidecar identity mismatch: {leaf}")
        seen.add(digest)
    if seen != set(labels):
        raise ValueError(f"raw predictions do not cover sidecar labels: {leaf}")
    computed = summarize_records(records, split=split, expected_cases=expected_cases)
    for key in ("rows", "cases", "metrics", "all_five_task_success", "slices"):
        if saved.get(key) != computed[key]:
            raise ValueError(f"saved summary differs from raw replay: {leaf}/{key}")
    return computed


def finite_rate(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("invalid replay selection metric")
    return float(value)


def select_dev(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rates = {
        name: {
            "semantic_task_success": finite_rate(results[name]["semantic_dev"]["metrics"]["task_success"]),
            "targeted_task_success": finite_rate(results[name]["v8_targeted_dev"]["metrics"]["task_success"]),
            "resolution_overall": finite_rate(results[name]["resolution_dev"]["metrics"]["resolution"]["overall"]["rate"]),
        }
        for name in ORDER
    }
    baseline = rates["baseline_v7"]
    gates = {}
    for name in ORDER:
        current = rates[name]
        deltas = {
            "semantic_dev_task_success": current["semantic_task_success"] - baseline["semantic_task_success"],
            "v8_targeted_dev_task_success": current["targeted_task_success"] - baseline["targeted_task_success"],
            "resolution_dev_overall_rate": current["resolution_overall"] - baseline["resolution_overall"],
        }
        violations = []
        if deltas["semantic_dev_task_success"] < -0.02 - 1e-12:
            violations.append("semantic_dev_task_success_drop_exceeds_2pp")
        if deltas["v8_targeted_dev_task_success"] < -0.02 - 1e-12:
            violations.append("v8_targeted_dev_task_success_drop_exceeds_2pp")
        if deltas["resolution_dev_overall_rate"] < -1e-12:
            violations.append("resolution_dev_below_v7")
        gates[name] = {
            "metrics": current,
            "deltas_from_baseline_v7": deltas,
            "maximum_allowed_task_success_drop": 0.02,
            "minimum_allowed_resolution_delta": 0.0,
            "violations": violations,
            "passed": not violations,
        }
    eligible = [name for name in ORDER if gates[name]["passed"]]
    ranking = sorted(eligible, key=lambda name: (
        -rates[name]["resolution_overall"],
        -(rates[name]["semantic_task_success"] + rates[name]["targeted_task_success"]) / 2,
        -rates[name]["semantic_task_success"], -rates[name]["targeted_task_success"], ORDER.index(name),
    ))
    return {
        "schema_version": 1,
        "selected_model": ranking[0],
        "selection_split": "dev_only",
        "selection_rule": "eligible: semantic and targeted task_success deltas >= -0.02 and resolution overall delta >= 0 versus same-run v7; rank resolution overall, mean task_success, semantic task_success, targeted task_success, then fixed candidate order",
        "candidate_order": ORDER,
        "ranking": ranking,
        "eligible_models": eligible,
        "gates": gates,
        "frozen_test_used_for_selection": False,
        "resolution_dev_used_for_selection": True,
    }


def replay_resolution(raw_root: Path, model: str) -> dict[str, Any]:
    leaf = f"merge_eval/local_results/evaluation/{model}/resolution_dev"
    raw = load_json(raw_root / leaf / "resolution_raw.json")
    saved = load_json(raw_root / leaf / "summary.json")
    context = build_resolution_case_context(raw_root / "resolution_expand/pack")
    metrics = validate_resolution_document(raw, saved, context)
    labels = load_json(raw_root / "resolution_expand/pack/dev_labels.json")
    for record in raw["records"]:
        meta = labels.get(record["row_id"])
        if meta is None or record["condition"] != meta["condition"] or record["prior"] != meta["prior"] or record["target"] != meta["target"]:
            raise ValueError(f"resolution sidecar identity mismatch: {model}")
        initial = dict(record["initial"])
        output = initial.pop("raw_output")
        if initial != evaluate_output(output, meta):
            raise ValueError(f"resolution initial scorer mismatch: {model}")
    return saved


def materialize_staging_layout(staging_root: Path, destination: Path) -> Path:
    """Map split collections to the raw replay layout using temporary read-only symlinks."""
    staging_root = Path(staging_root).resolve()
    mappings = {
        "merge_eval/local_results": "model_collection/evidence/merged/local_results",
        "semantic_contrast/packs_v2": "dataset_collection/semantic_contrast/packs_v2",
        "v8_data/packs": "dataset_collection/v8_targeted/packs",
        "resolution_expand/pack": "dataset_collection/resolution_expand/pack",
    }
    for relative, staged in mappings.items():
        source = staging_root / staged
        if not source.is_dir():
            raise ValueError(f"staged replay input is missing: {staged}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source, target_is_directory=True)
    return destination


def replay_all(raw_root: Path = RAW_ROOT, staging_root: Path | None = None) -> dict[str, Any]:
    if staging_root is not None:
        with tempfile.TemporaryDirectory() as temporary:
            layout = materialize_staging_layout(Path(staging_root), Path(temporary))
            result = replay_all(raw_root=layout)
            result["staged_replay"] = True
            return result
    raw_root = Path(raw_root)
    locked_files = verify_locked_inputs(raw_root)
    results = {}
    single_turn_records = 0
    for model in ORDER:
        results[model] = {}
        for view, info in DEV_VIEWS.items():
            leaf = f"merge_eval/local_results/evaluation/{model}/{view}"
            results[model][view] = replay_single_turn(raw_root, leaf, info)
            single_turn_records += results[model][view]["rows"]
        results[model]["resolution_dev"] = replay_resolution(raw_root, model)
    computed_selection = select_dev(results)
    selection_path = raw_root / "merge_eval/local_results/evaluation/selection.json"
    selection = load_json(selection_path)
    for key, value in computed_selection.items():
        if selection.get(key) != value:
            raise ValueError(f"locked selection differs from raw replay: {key}")
    if selection["selected_adapter_model_sha256"] != "a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335":
        raise ValueError("selected adapter identity changed")
    if sha256_file(raw_root / "merge_eval/local_results/plan.json") != selection["run_plan_sha256"]:
        raise ValueError("selection run-plan hash mismatch")

    frozen_results = {}
    frozen_records = 0
    for model in FROZEN_MODELS:
        frozen_results[model] = {}
        for view, info in FROZEN_VIEWS.items():
            leaf = f"merge_eval/local_results/frozen_confirmation/evaluation/{model}/{view}"
            summary = replay_single_turn(raw_root, leaf, info)
            frozen_results[model][view] = {
                "cases": summary["cases"], "rows": summary["rows"], "metrics": summary["metrics"],
                "all_five_task_success": summary["all_five_task_success"],
                "raw_predictions": f"evaluation/{model}/{view}/raw_predictions.json",
            }
            frozen_records += summary["rows"]
            single_turn_records += summary["rows"]
    frozen = load_json(raw_root / "merge_eval/local_results/frozen_confirmation/frozen_summary.json")
    if frozen["results"] != frozen_results:
        raise ValueError("frozen headline results differ from raw replay")
    deltas = {
        name: {
            f"{view}_task_success": frozen_results[name][view]["metrics"]["task_success"] - frozen_results["baseline_v7"][view]["metrics"]["task_success"]
            for view in FROZEN_VIEWS
        }
        for name in FROZEN_MODELS
    }
    if frozen["deltas_from_baseline_v7"] != deltas or frozen["confirmation_only"] is not True or frozen["selection_unchanged"] is not True:
        raise ValueError("frozen confirmation scope or deltas differ from replay")
    if frozen["selection_sha256"] != sha256_file(selection_path):
        raise ValueError("frozen selection hash mismatch")
    return {
        "status": "PASS",
        "staged_replay": False,
        "locked_files_verified": locked_files,
        "selected_model": selection["selected_model"],
        "selection_sha256": sha256_file(selection_path),
        "single_turn_records_verified": single_turn_records,
        "resolution_arms_verified": len(ORDER),
        "frozen_records_verified": frozen_records,
        "semantic_merged_task_success": frozen_results["merge_alpha_0.75"]["semantic_frozen_test"]["metrics"]["task_success"],
        "targeted_merged_task_success": frozen_results["merge_alpha_0.75"]["v8_targeted_frozen_test"]["metrics"]["task_success"],
        "note": "Replay verifies saved evidence, not missing original selection-code bytes or fresh generation.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT)
    parser.add_argument("--staging-root", type=Path, help="replay from split model/dataset staging without changing staged bytes")
    arguments = parser.parse_args()
    print(json.dumps(replay_all(arguments.raw_root, arguments.staging_root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

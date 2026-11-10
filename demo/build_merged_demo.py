#!/usr/bin/env python3
"""Build and verify a small recorded-only demo from merged frozen predictions."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKTREE_ROOT / "release/source"))
from scorers.contract_v2 import evaluate_output, validate_pack  # noqa: E402


DEFAULT_RAW_ROOT = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")
DEFAULT_OUTPUT = WORKTREE_ROOT / "demo_merged_data.json"
EXPECTED_ADAPTER_SHA256 = "a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335"
EXPECTED_SELECTION_SHA256 = "e5e177ade09c53285eeb78c7a3a7cd45f47498a245fdf1c8bc416238fbd29c4b"
EXPECTED_FROZEN_SUMMARY_SHA256 = "3598cf8cdfa3e0783944e0bbbcd81788ef5f15131ab8e1ee811fc63cc2184d7d"
BACKEND = "local Apple MPS bf16 Transformers; two-arm frozen confirmation only"
MODELS = ("baseline_v7", "merge_alpha_0.75")
VIEWS = ("semantic_frozen_test", "v8_targeted_frozen_test")
EXPECTED_SCORES = {
    "semantic_frozen_test": {
        "baseline_v7": {"task_success": 0.8875, "all_five_task_success": 0.6041666666666666},
        "merge_alpha_0.75": {"task_success": 0.925, "all_five_task_success": 0.7291666666666666},
    },
    "v8_targeted_frozen_test": {
        "baseline_v7": {"task_success": 0.9148148148148149, "all_five_task_success": 0.7407407407407407},
        "merge_alpha_0.75": {"task_success": 0.937037037037037, "all_five_task_success": 0.7962962962962963},
    },
}
EXPECTED_DEV = {
    "baseline_v7": {"semantic_task_success": 0.9458333333333333, "targeted_task_success": 0.8722222222222222, "resolution_overall": 0.76},
    "merge_alpha_0.75": {"semantic_task_success": 0.9625, "targeted_task_success": 0.9, "resolution_overall": 0.7941176470588235},
}
CONDITIONS = ("valid", "unsupported_toward", "unsupported_away", "pressure_away", "solo")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def raw_relative(model: str, view: str) -> str:
    return f"merge_eval/local_results/frozen_confirmation/evaluation/{model}/{view}/raw_predictions.json"


EXPECTED_RAW_SHA256 = {
    raw_relative("baseline_v7", "semantic_frozen_test"): "1eabb2ad193c371aaa146f89793b495d63d9e45edd5f41d8d26a77e2a1c143a8",
    raw_relative("merge_alpha_0.75", "semantic_frozen_test"): "fb85ed61732fd19ef0c77b36e8ba9cc56a81a9871f88e01c48f0521fd2741624",
    raw_relative("baseline_v7", "v8_targeted_frozen_test"): "fe1428cb9651b9faea2324288165c305a0b38638ff96233bbeda3dabaf0fc2cf",
    raw_relative("merge_alpha_0.75", "v8_targeted_frozen_test"): "a937b5afd409cb1a9763afde9a93a0f55444d730034e5aa88468e1703b0d12c3",
}
SEMANTIC_SOURCE = "semantic_contrast/packs_v2/frozen_test_source.jsonl"
SEMANTIC_LABELS = "semantic_contrast/packs_v2/frozen_test_labels.json"
EXPECTED_SEMANTIC_SOURCE_SHA256 = "6497061a6706908d9d7dc2d78570d703a265383fcff86e639da6cbb6f8e0880d"
EXPECTED_SEMANTIC_LABELS_SHA256 = "48906d47d1ee51972af059002ef17fceb087000b0a47f0efc761a0bf0ed42281"


def build_demo(raw_root: Path) -> dict[str, Any]:
    raw_root = Path(raw_root)
    selection_path = raw_root / "merge_eval/local_results/evaluation/selection.json"
    frozen_path = raw_root / "merge_eval/local_results/frozen_confirmation/frozen_summary.json"
    if sha256_file(selection_path) != EXPECTED_SELECTION_SHA256:
        raise ValueError("selection hash differs from the locked dev selection")
    if sha256_file(frozen_path) != EXPECTED_FROZEN_SUMMARY_SHA256:
        raise ValueError("frozen summary hash differs from the verified confirmation")
    adapter_path = raw_root / "merge_eval/adapters/alpha_0.75/adapter_model.safetensors"
    if sha256_file(adapter_path) != EXPECTED_ADAPTER_SHA256:
        raise ValueError("merged adapter hash mismatch")
    selection = load_json(selection_path)
    frozen = load_json(frozen_path)
    if frozen.get("backend") != BACKEND or frozen.get("confirmation_only") is not True:
        raise ValueError("unexpected backend or confirmation protocol")

    predictions = {}
    for relative, expected_hash in EXPECTED_RAW_SHA256.items():
        if sha256_file(raw_root / relative) != expected_hash:
            raise ValueError(f"raw prediction sha256 mismatch: {relative}")
    for relative, expected_hash in (
        (SEMANTIC_SOURCE, EXPECTED_SEMANTIC_SOURCE_SHA256),
        (SEMANTIC_LABELS, EXPECTED_SEMANTIC_LABELS_SHA256),
    ):
        if sha256_file(raw_root / relative) != expected_hash:
            raise ValueError(f"demo sidecar sha256 mismatch: {relative}")
    semantic_rows = [json.loads(line) for line in (raw_root / SEMANTIC_SOURCE).read_text(encoding="utf-8").splitlines() if line]
    semantic_labels = load_json(raw_root / SEMANTIC_LABELS)
    validate_pack(semantic_rows, semantic_labels)
    semantic_inputs = {row["input"] for row in semantic_rows}
    sources = [
        {"path": "merge_eval/local_results/evaluation/selection.json", "sha256": EXPECTED_SELECTION_SHA256, "role": "dev-only selection"},
        {"path": "merge_eval/local_results/frozen_confirmation/frozen_summary.json", "sha256": EXPECTED_FROZEN_SUMMARY_SHA256, "role": "frozen confirmation summary"},
        {"path": SEMANTIC_SOURCE, "sha256": EXPECTED_SEMANTIC_SOURCE_SHA256, "role": "illustrated source rows"},
        {"path": SEMANTIC_LABELS, "sha256": EXPECTED_SEMANTIC_LABELS_SHA256, "role": "illustrated sidecar labels"},
    ]
    for model in MODELS:
        predictions[model] = {}
        for view in VIEWS:
            relative = raw_relative(model, view)
            path = raw_root / relative
            document = load_json(path)
            records = document["records"]
            expected_rows = frozen["results"][model][view]["rows"]
            if len(records) != expected_rows or document.get("model") != model:
                raise ValueError(f"incomplete or mismatched saved predictions: {relative}")
            predictions[model][view] = records
            sources.append({"path": relative, "sha256": sha256_file(path), "rows": len(records), "role": "source saved predictions; not redistributed"})

    merged_records = predictions["merge_alpha_0.75"]["semantic_frozen_test"]
    case_id = merged_records[0]["metadata"]["case_id"]
    selected = [record for record in merged_records if record["metadata"]["case_id"] == case_id]
    if case_id != "sc-01-25" or len(selected) != 5:
        raise ValueError("first semantic frozen case is not the expected complete five-row case")
    baseline_by_condition = {
        record["metadata"]["condition"]: record
        for record in predictions["baseline_v7"]["semantic_frozen_test"]
        if record["metadata"]["case_id"] == case_id
    }
    illustration_records = []
    for merged in selected:
        condition = merged["metadata"]["condition"]
        baseline = baseline_by_condition[condition]
        if baseline["input"] != merged["input"] or baseline["metadata"] != merged["metadata"]:
            raise ValueError(f"matched arms differ for {case_id}/{condition}")
        outputs = {}
        for model, record in (("baseline_v7", baseline), ("merge_alpha_0.75", merged)):
            digest = sha256_text(record["input"])
            if record["input"] not in semantic_inputs or record["metadata"] != semantic_labels.get(digest):
                raise ValueError(f"demo sidecar identity mismatch: {case_id}/{condition}/{model}")
            if record["evaluation"] != evaluate_output(record["raw_output"], record["metadata"]):
                raise ValueError(f"demo contract-v2 rescore mismatch: {case_id}/{condition}/{model}")
            outputs[model] = {
                "raw_output": record["raw_output"],
                "raw_output_sha256": sha256_text(record["raw_output"]),
                "evaluation": copy.deepcopy(record["evaluation"]),
                "prompt_tokens": record["prompt_tokens"],
                "completion_tokens": record["completion_tokens"],
                "backend": BACKEND,
            }
        illustration_records.append({
            "condition": condition,
            "input": merged["input"],
            "input_sha256": sha256_text(merged["input"]),
            "metadata": copy.deepcopy(merged["metadata"]),
            "outputs": outputs,
        })
    if tuple(record["condition"] for record in illustration_records) != CONDITIONS:
        raise ValueError("illustration conditions are incomplete or reordered")

    scoreboards = {}
    for view in VIEWS:
        arms = {}
        for model in MODELS:
            saved = frozen["results"][model][view]
            arms[model] = {
                "task_success": saved["metrics"]["task_success"],
                "all_five_task_success": saved["all_five_task_success"],
                "rows": saved["rows"],
                "cases": saved["cases"],
                "backend": BACKEND,
            }
        scoreboards[view] = {
            "cases": frozen["results"]["merge_alpha_0.75"][view]["cases"],
            "rows_per_arm": frozen["results"]["merge_alpha_0.75"][view]["rows"],
            "arms": arms,
        }

    payload = {
        "schema_version": 1,
        "title": "EvidenceTune merged model recorded correction replay",
        "recorded_only": True,
        "model": {
            "key": "merge_alpha_0.75",
            "label": "EvidenceTune merged alpha=0.75",
            "formula": "0.75 * v7 + 0.25 * v8",
            "adapter_sha256": EXPECTED_ADAPTER_SHA256,
        },
        "backend": BACKEND,
        "claim_scope": "Contract-v2 synthetic construction-proxy evaluation; not human-validated or broad natural-domain evidence.",
        "selection": {
            "selection_split": "dev_only",
            "frozen_test_used_for_selection": False,
            "selection_sha256": EXPECTED_SELECTION_SHA256,
            "frozen_summary_sha256": EXPECTED_FROZEN_SUMMARY_SHA256,
            "dev_arms": copy.deepcopy(EXPECTED_DEV),
        },
        "scoreboards": scoreboards,
        "illustration": {
            "selection_rule": "First case in saved semantic frozen-test record order; all five matched conditions included; no outcome-based selection.",
            "case_id": case_id,
            "label_status": selected[0]["metadata"]["label_status"],
            "records": illustration_records,
        },
        "source_artifacts": sources,
    }
    verify_demo(payload)
    return payload


def verify_demo(payload_or_path: dict[str, Any] | Path, raw_root: Path | None = None) -> dict[str, Any]:
    """Check score anchors, matched records, hashes, and optionally exact source regeneration."""
    if isinstance(payload_or_path, Path):
        payload = load_json(payload_or_path)
    else:
        payload = payload_or_path
    if payload.get("recorded_only") is not True or payload.get("backend") != BACKEND:
        raise ValueError("demo must be recorded-only on the merged Apple MPS backend")
    if payload.get("model", {}).get("adapter_sha256") != EXPECTED_ADAPTER_SHA256:
        raise ValueError("demo adapter hash mismatch")
    for view, models in EXPECTED_SCORES.items():
        scoreboard = payload.get("scoreboards", {}).get(view, {})
        for model, expected in models.items():
            arm = scoreboard.get("arms", {}).get(model, {})
            if arm.get("backend") != BACKEND:
                raise ValueError(f"backend mixing in {view}/{model}")
            for metric, value in expected.items():
                if arm.get(metric) != value:
                    raise ValueError(f"scoreboard mismatch: {view}/{model}/{metric}")
    if payload.get("selection", {}).get("dev_arms") != EXPECTED_DEV:
        raise ValueError("scoreboard mismatch: dev selection metrics")

    illustration = payload.get("illustration", {})
    records = illustration.get("records", [])
    if illustration.get("case_id") != "sc-01-25" or len(records) != 5:
        raise ValueError("demo illustration is not the first complete semantic case")
    if tuple(record.get("condition") for record in records) != CONDITIONS:
        raise ValueError("demo illustration conditions are incomplete or reordered")
    for record in records:
        if sha256_text(record["input"]) != record.get("input_sha256"):
            raise ValueError("input sha256 mismatch")
        for model in MODELS:
            output = record.get("outputs", {}).get(model, {})
            if output.get("backend") != BACKEND:
                raise ValueError("backend mixing in illustration")
            if sha256_text(output.get("raw_output", "")) != output.get("raw_output_sha256"):
                raise ValueError(f"raw_output sha256 mismatch: {record['condition']}/{model}")
    if raw_root is not None:
        expected = build_demo(Path(raw_root))
        if payload != expected:
            raise ValueError("demo payload differs from exact saved-prediction regeneration")
    return {"status": "PASS", "illustration_records": len(records), "scoreboards": len(EXPECTED_SCORES)}


def write_demo(payload: dict[str, Any], output: Path) -> None:
    verify_demo(payload)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true", help="verify output against source instead of writing it")
    arguments = parser.parse_args()
    if arguments.verify:
        result = verify_demo(arguments.output, arguments.raw_root)
    else:
        payload = build_demo(arguments.raw_root)
        write_demo(payload, arguments.output)
        result = verify_demo(arguments.output, arguments.raw_root)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

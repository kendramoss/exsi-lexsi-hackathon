#!/usr/bin/env python3
"""Run only the locked v7/alpha-0.75 frozen confirmation on local MPS."""
from __future__ import annotations

import argparse
import gc
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from local_eval import (
    DEFAULT_BATCH_SIZE,
    MAX_NEW_TOKENS,
    MERGE_ROOT,
    MODEL,
    MPSGenerator,
    ROOT,
    _write_leaf_plan,
    atomic_write_json,
    run_single_turn,
    sha256_file,
)
from next_run import kaggle_next_flow as flow
from contract_unification.contract_v2 import validate_pack

SELECTION_PATH = MERGE_ROOT / "local_results/evaluation/selection.json"
LOCKED_SELECTION_SHA256 = "e5e177ade09c53285eeb78c7a3a7cd45f47498a245fdf1c8bc416238fbd29c4b"
SELECTED_MODEL = "merge_alpha_0.75"
MODEL_ORDER = ["baseline_v7", SELECTED_MODEL]
BACKEND = "local Apple MPS bf16 Transformers; two-arm frozen confirmation only"
DEFAULT_OUTPUT = MERGE_ROOT / "local_results/frozen_confirmation"
DATASETS = {
    "semantic_frozen_test": {
        "source_path": ROOT / "semantic_contrast/packs_v2/frozen_test_source.jsonl",
        "source_sha256": "6497061a6706908d9d7dc2d78570d703a265383fcff86e639da6cbb6f8e0880d",
        "labels_path": ROOT / "semantic_contrast/packs_v2/frozen_test_labels.json",
        "labels_sha256": "48906d47d1ee51972af059002ef17fceb087000b0a47f0efc761a0bf0ed42281",
        "cases": 48,
        "rows": 240,
        "split": "frozen_test",
    },
    "v8_targeted_frozen_test": {
        "source_path": ROOT / "v8_data/packs/new_independent_frozen_test_source.jsonl",
        "source_sha256": "40c1c9e7e81ad66d965818ba106289186b503ff667206ba8f86a43649307b781",
        "labels_path": ROOT / "v8_data/packs/new_independent_frozen_test_labels.json",
        "labels_sha256": "c647a8b902489b271fd8b3ae5d0cb3313f3be2ff342f024021ca2c6cb652dc7c",
        "cases": 54,
        "rows": 270,
        "split": "new_independent_frozen_test",
    },
}


def make_frozen_summary(
    results: dict[str, dict[str, dict[str, Any]]], selection: dict[str, Any],
) -> dict[str, Any]:
    """Summarize confirmation metrics without creating a new selection or ranking."""
    if set(results) != set(MODEL_ORDER):
        raise ValueError("frozen confirmation requires exactly baseline_v7 and merge_alpha_0.75")
    if selection.get("selected_model") != SELECTED_MODEL:
        raise ValueError("locked dev selection is not merge_alpha_0.75")
    reduced = {}
    for name in MODEL_ORDER:
        if set(results[name]) != set(DATASETS):
            raise ValueError(f"incomplete frozen views for {name}")
        reduced[name] = {}
        for view in DATASETS:
            summary = results[name][view]
            if summary["split"] != DATASETS[view]["split"] or summary["rows"] != DATASETS[view]["rows"]:
                raise ValueError(f"wrong frozen split/row count for {name}/{view}")
            reduced[name][view] = {
                "cases": summary["cases"],
                "rows": summary["rows"],
                "metrics": summary["metrics"],
                "all_five_task_success": summary["all_five_task_success"],
                "raw_predictions": f"evaluation/{name}/{view}/raw_predictions.json",
            }
    deltas = {}
    for name in MODEL_ORDER:
        deltas[name] = {
            f"{view}_task_success": (
                reduced[name][view]["metrics"]["task_success"]
                - reduced["baseline_v7"][view]["metrics"]["task_success"]
            )
            for view in DATASETS
        }
    return {
        "schema_version": 1,
        "evaluation_kind": "frozen_confirmation",
        "confirmation_only": True,
        "selected_model": selection["selected_model"],
        "selected_adapter_model_sha256": selection["selected_adapter_model_sha256"],
        "selection_unchanged": True,
        "frozen_test_used_for_selection": False,
        "training_performed": False,
        "backend": BACKEND,
        "results": reduced,
        "deltas_from_baseline_v7": deltas,
    }


def _validate_locked_selection() -> dict[str, Any]:
    if sha256_file(SELECTION_PATH) != LOCKED_SELECTION_SHA256:
        raise ValueError("selection.json hash differs from the validated locked selection")
    selection = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    if selection.get("selected_model") != SELECTED_MODEL:
        raise ValueError("locked selection changed")
    if selection.get("frozen_test_used_for_selection") is not False:
        raise ValueError("invalid dev selection provenance")
    return selection


def _load_frozen_data() -> dict[str, tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]]:
    loaded = {}
    for view, info in DATASETS.items():
        if sha256_file(info["source_path"]) != info["source_sha256"] or sha256_file(info["labels_path"]) != info["labels_sha256"]:
            raise ValueError(f"frozen input hash mismatch: {view}")
        if view == "semantic_frozen_test":
            rows, labels = flow.load_semantic_split(info["source_path"].parent, "frozen_test", validate=True)
        else:
            rows = flow.read_jsonl(info["source_path"])
            labels = json.loads(info["labels_path"].read_text(encoding="utf-8"))
            validation = validate_pack(rows, labels)
            if validation["cases"] != info["cases"] or validation["rows"] != info["rows"]:
                raise ValueError("unexpected targeted frozen pack size")
        loaded[view] = (rows, labels)
    return loaded


def main(output_root: Path = DEFAULT_OUTPUT, batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, Any]:
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    selection = _validate_locked_selection()
    datasets = _load_frozen_data()
    dev_plan = json.loads((MERGE_ROOT / "local_results/plan.json").read_text(encoding="utf-8"))
    models = {name: dev_plan["models"][name] for name in MODEL_ORDER}
    for name, model in models.items():
        if sha256_file(Path(model["adapter_path"]) / "adapter_model.safetensors") != model["adapter_model_sha256"]:
            raise ValueError(f"adapter hash mismatch: {name}")
    run_plan = {
        "schema_version": 1,
        "evaluation_kind": "frozen_confirmation",
        "confirmation_only": True,
        "selected_model": SELECTED_MODEL,
        "selection_sha256": LOCKED_SELECTION_SHA256,
        "candidate_order": MODEL_ORDER,
        "models": models,
        "datasets": {name: {key: str(value) if isinstance(value, Path) else value for key, value in info.items()} for name, info in DATASETS.items()},
        "base_model": MODEL,
        "backend": BACKEND,
        "dtype": "bfloat16",
        "device": "mps",
        "offline_model_loading": True,
        "generation": {"max_new_tokens": MAX_NEW_TOKENS, "do_sample": False, "batch_size": batch_size},
        "training_performed": False,
        "frozen_confirm_sha256": sha256_file(Path(__file__).resolve()),
        "local_eval_sha256": sha256_file(MERGE_ROOT / "local_eval.py"),
    }
    output_root.mkdir(parents=True, exist_ok=True)
    _write_leaf_plan(output_root, run_plan)

    print(json.dumps({"event": "frozen_loading_models", "models": MODEL_ORDER}), flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True)
    tokenizer.padding_side = "left"
    base = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.bfloat16, local_files_only=True).to("mps").eval()
    model = None
    for index, name in enumerate(MODEL_ORDER):
        adapter_name = f"frozen_{index}"
        if model is None:
            model = PeftModel.from_pretrained(base, models[name]["adapter_path"], adapter_name=adapter_name, is_trainable=False)
        else:
            model.load_adapter(models[name]["adapter_path"], adapter_name=adapter_name)
    model.eval()
    results = {}
    try:
        for index, name in enumerate(MODEL_ORDER):
            model.set_adapter(f"frozen_{index}")
            results[name] = {}
            print(json.dumps({"event": "frozen_model_started", "model": name}), flush=True)
            for view, (rows, labels) in datasets.items():
                generator = MPSGenerator(tokenizer, model, batch_size=batch_size, label=f"frozen/{name}/{view}")
                results[name][view] = run_single_turn(
                    name, view, rows, labels, generator, output_root,
                    expected_cases=DATASETS[view]["cases"],
                    source_sha256=DATASETS[view]["source_sha256"],
                    labels_sha256=DATASETS[view]["labels_sha256"],
                    split=DATASETS[view]["split"],
                    backend=BACKEND,
                )
                print(json.dumps({
                    "event": "frozen_view_complete", "model": name, "view": view,
                    "task_success": results[name][view]["metrics"]["task_success"],
                }), flush=True)
    finally:
        del model
        del base
        gc.collect()
        torch.mps.empty_cache()

    summary = make_frozen_summary(results, selection)
    summary.update({
        "selection_sha256": LOCKED_SELECTION_SHA256,
        "run_plan_sha256": sha256_file(output_root / "plan.json"),
    })
    atomic_write_json(output_root / "frozen_summary.json", summary)
    if sha256_file(SELECTION_PATH) != LOCKED_SELECTION_SHA256:
        raise RuntimeError("selection file changed during frozen confirmation")
    print(json.dumps({"event": "frozen_confirmation_complete", "summary": summary}), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    arguments = parser.parse_args()
    result = main(arguments.output_root, arguments.batch_size)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2), flush=True)

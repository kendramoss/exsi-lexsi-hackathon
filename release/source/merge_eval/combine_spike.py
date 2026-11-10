"""Preregistration for the two-adapter Contradiction interpolation spike."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

WORKTREE = Path("/Users/anasqumhiyeh/.claude/worktrees/exsi-combine")
ARTIFACT = WORKTREE / ".combine_spike"
MERGED_ADAPTER = Path("/Users/anasqumhiyeh/lexsi-koth/evtune/merge_eval/adapters/alpha_0.75")
CONTRADICTION_ADAPTER = Path("/Users/anasqumhiyeh/.claude/worktrees/exsi-contradiction/.contradiction_spike/run/367996841/contradiction_spike_output/contradiction_sft/adapter")
MERGED_SHA256 = "a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335"
CONTRADICTION_SHA256 = "4ba9fce20fb0d4f81c0a4023096a3cf11bdd7c75e7d6335661bc825f29699ce1"
BASELINE = "merge_alpha_0.75"
MERGE_CODE = Path("/Users/anasqumhiyeh/lexsi-koth/evtune/merge_eval/merge_lora.py")
LOCAL_EVAL = Path("/Users/anasqumhiyeh/lexsi-koth/evtune/merge_eval/local_eval.py")
GATE_SOURCE = WORKTREE.parent / "exsi-contradiction" / "contradiction_spike" / "spike.py"
RAW = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def recipes():
    return [
        {"name": "contradiction_0.25", "contradiction_weight": 0.25, "merged_weight": 0.75, "alpha": 0.75},
        {"name": "contradiction_0.50", "contradiction_weight": 0.50, "merged_weight": 0.50, "alpha": 0.50},
    ]


def original_gate():
    spec = importlib.util.spec_from_file_location("contradiction_original_gate", GATE_SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.GATE


def build_evaluation_plan(*, check_outputs=True):
    models = {
        BASELINE: {"adapter_path": str(MERGED_ADAPTER), "adapter_model_sha256": MERGED_SHA256},
    }
    for recipe in recipes():
        path = ARTIFACT / "adapters" / recipe["name"]
        models[recipe["name"]] = {
            "adapter_path": str(path),
            "adapter_model_sha256": sha256_file(path / "adapter_model.safetensors") if check_outputs else "PENDING_OUTPUT_HASH",
        }
    datasets = {}
    for name, root, cases, rows in (
        ("semantic_dev", RAW / "semantic_contrast" / "packs_v2", 48, 240),
        ("v8_targeted_dev", RAW / "v8_data" / "packs", 36, 180),
        ("resolution_dev", RAW / "resolution_expand" / "pack", 32, 128),
    ):
        datasets[name] = {
            "source_path": str(root / "dev_source.jsonl"),
            "source_sha256": sha256_file(root / "dev_source.jsonl"),
            "labels_path": str(root / "dev_labels.json"),
            "labels_sha256": sha256_file(root / "dev_labels.json"),
            "cases": cases,
            "initial_rows" if name == "resolution_dev" else "rows": rows,
            "split": "resolution_dev" if name == "resolution_dev" else "dev",
        }
    return {
        "schema_version": 1,
        "experiment": "contradiction_two_adapter_interpolation_dev_only",
        "candidate_order": [BASELINE, "contradiction_0.25", "contradiction_0.50"],
        "models": models,
        "datasets": datasets,
        "selection_rule": "Original Contradiction gate; merged fallback; if both pass select contradiction_0.25",
        "retention_gates": original_gate(),
    }


def build_preregistration(*, check_outputs=True):
    return {
        "schema_version": 1,
        "status": "PREREGISTERED_BEFORE_EVALUATION",
        "training": False,
        "candidate_order": [BASELINE, "contradiction_0.25", "contradiction_0.50"],
        "recipes": recipes(),
        "arithmetic": "elementwise float64 interpolation, cast once to each source tensor dtype",
        "source_adapter_sha256": {
            str(MERGED_ADAPTER): MERGED_SHA256,
            str(CONTRADICTION_ADAPTER): CONTRADICTION_SHA256,
        },
        "source_code_sha256": {
            str(MERGE_CODE): sha256_file(MERGE_CODE),
            str(LOCAL_EVAL): sha256_file(LOCAL_EVAL),
            str(GATE_SOURCE): sha256_file(GATE_SOURCE),
            str(Path(__file__)): sha256_file(__file__),
        },
        "evaluation_plan": build_evaluation_plan(check_outputs=check_outputs),
        "gate": original_gate(),
        "if_both_pass": "contradiction_0.25",
        "backend": "existing local Apple MPS bf16 Transformers protocol",
        "frozen_test_used_for_selection": False,
        "public_replacement": False,
    }


def raw_prediction_path(output_root, model, view):
    return Path(output_root) / "evaluation" / model / view / "raw_predictions.json"


def select_candidate(passes):
    if passes.get("contradiction_0.25") is True:
        return "contradiction_0.25"
    if passes.get("contradiction_0.50") is True:
        return "contradiction_0.50"
    return BASELINE

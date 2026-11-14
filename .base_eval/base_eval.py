#!/usr/bin/env python3
"""Post-selection raw-base evaluation on the two locked contract-v2 suites."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_EVAL_ROOT = Path(__file__).resolve().parent
WORKTREE_ROOT = BASE_EVAL_ROOT.parent
RAW_PROJECT = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")
MERGE_ROOT = RAW_PROJECT / "merge_eval"
FROZEN_ROOT = MERGE_ROOT / "local_results/frozen_confirmation"
MODEL = "CohereLabs/tiny-aya-global"
ARMS = ("raw_base", "baseline_v7", "merge_alpha_0.75")
METRICS = ("format_ok", "action_ok", "answer_ok", "task_success", "whole_window_answer_ok", "terminal")

for import_root in (MERGE_ROOT, RAW_PROJECT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from contract_unification.contract_v2 import evaluate_output  # noqa: E402
from frozen_confirm import DATASETS, _load_frozen_data  # noqa: E402
from local_eval import (  # noqa: E402
    MPSGenerator,
    _write_leaf_plan,
    atomic_write_json,
    run_single_turn,
    sha256_file,
)
from next_run import kaggle_next_flow as flow  # noqa: E402

SAVED_ARM_RAW_SHA256 = {
    ("baseline_v7", "semantic_frozen_test"): "1eabb2ad193c371aaa146f89793b495d63d9e45edd5f41d8d26a77e2a1c143a8",
    ("baseline_v7", "v8_targeted_frozen_test"): "fe1428cb9651b9faea2324288165c305a0b38638ff96233bbeda3dabaf0fc2cf",
    ("merge_alpha_0.75", "semantic_frozen_test"): "fb85ed61732fd19ef0c77b36e8ba9cc56a81a9871f88e01c48f0521fd2741624",
    ("merge_alpha_0.75", "v8_targeted_frozen_test"): "a937b5afd409cb1a9763afde9a93a0f55444d730034e5aa88468e1703b0d12c3",
}
SAVED_ARM_PLAN_SHA256 = {
    ("baseline_v7", "semantic_frozen_test"): "16a06bb995e27048e2a57a08d2e1d487537db94faa1b81175b35eb2f6fc99a55",
    ("baseline_v7", "v8_targeted_frozen_test"): "0317e18fdae6aa8ba9acfd69eead47825f8dfce79a127dc10e592245ab845933",
    ("merge_alpha_0.75", "semantic_frozen_test"): "209b40c1dc2edeb74762f2dd7558ee06b62d73ca5337f843450b4551884d8619",
    ("merge_alpha_0.75", "v8_targeted_frozen_test"): "c58dc1f25f172060fe413a7377347ecb01379ce1fdee5b383a91409ce47e1912",
}
SAVED_ARM_SUMMARY_SHA256 = {
    ("baseline_v7", "semantic_frozen_test"): "898633d995be80039e85145c1d0934e784d75f200c1debd887635dc8d0f1c266",
    ("baseline_v7", "v8_targeted_frozen_test"): "4b2ac28144824dc6ec93733f3c27508ec4725bd05c7b72868e4660b93f036da9",
    ("merge_alpha_0.75", "semantic_frozen_test"): "8850ded61339ec20d7c3800f50ec1e844297fae111930f71b59926902cd67dff",
    ("merge_alpha_0.75", "v8_targeted_frozen_test"): "474caac6f8e4ce5623cdc2cb35ac534ff2c5516861d9b938676c07ee43dc55ea",
}


def load_raw_base() -> tuple[Any, Any]:
    """Load only the cached base model; deliberately no PEFT import or adapter call."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.backends.mps.is_available():
        raise RuntimeError("local MPS is unavailable")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True)
    tokenizer.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, dtype=torch.bfloat16, local_files_only=True,
    ).to("mps").eval()
    return tokenizer, model


def verify_frozen_artifacts() -> dict[str, Any]:
    """Enforce exact datasets, saved arms, cached commit, and tokenizer identities."""
    datasets = {}
    for view, info in DATASETS.items():
        for kind in ("source", "labels"):
            actual = sha256_file(info[f"{kind}_path"])
            if actual != info[f"{kind}_sha256"]:
                raise ValueError(f"frozen input hash mismatch: {view}/{kind}")
        datasets[view] = {
            "source_path": str(info["source_path"]),
            "source_sha256": info["source_sha256"],
            "labels_path": str(info["labels_path"]),
            "labels_sha256": info["labels_sha256"],
            "cases": info["cases"],
            "rows": info["rows"],
            "split": info["split"],
        }

    saved_arms: dict[str, dict[str, Any]] = {}
    for arm in ARMS[1:]:
        saved_arms[arm] = {}
        for view in DATASETS:
            leaf = FROZEN_ROOT / "evaluation" / arm / view
            paths = {name: leaf / f"{name}.json" for name in ("raw_predictions", "plan", "summary")}
            expected = {
                "raw_predictions": SAVED_ARM_RAW_SHA256[(arm, view)],
                "plan": SAVED_ARM_PLAN_SHA256[(arm, view)],
                "summary": SAVED_ARM_SUMMARY_SHA256[(arm, view)],
            }
            actual = {name: sha256_file(path) for name, path in paths.items()}
            for name in paths:
                if actual[name] != expected[name]:
                    raise ValueError(f"saved arm hash mismatch: {arm}/{view}/{name}")
            saved_arms[arm][view] = {
                **{f"{name}_sha256": digest for name, digest in actual.items()},
                **{f"{name}_path": str(path) for name, path in paths.items()},
            }

    model_cache = Path.home() / ".cache/huggingface/hub/models--CohereLabs--tiny-aya-global"
    commit = (model_cache / "refs/main").read_text(encoding="utf-8").strip()
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ValueError("cached base ref is not a full commit hash")
    snapshot = model_cache / "snapshots" / commit
    tokenizer_files = {}
    for name in ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"):
        tokenizer_files[name] = sha256_file(snapshot / name)
    return {
        "base_model": MODEL,
        "base_commit": commit,
        "base_snapshot": str(snapshot),
        "tokenizer_files": tokenizer_files,
        "datasets": datasets,
        "saved_arms": saved_arms,
        "local_eval_sha256": sha256_file(MERGE_ROOT / "local_eval.py"),
        "contract_v2_sha256": sha256_file(RAW_PROJECT / "contract_unification/contract_v2.py"),
    }


def _load_aligned_records(arm: str, view: str, root: Path) -> tuple[list[dict[str, Any]], Path]:
    leaf = root / "evaluation" / arm / view
    raw_path = leaf / "raw_predictions.json"
    records = json.loads(raw_path.read_text(encoding="utf-8"))["records"]
    datasets = _load_frozen_data()
    rows, labels = datasets[view]
    if len(records) != len(rows):
        raise ValueError(f"row count mismatch: {arm}/{view}")
    seen = set()
    for record, row in zip(records, rows):
        digest = hashlib.sha256(row["input"].encode("utf-8")).hexdigest()
        if record["input"] != row["input"] or digest in seen:
            raise ValueError(f"unaligned or duplicate prediction: {arm}/{view}")
        seen.add(digest)
        if record["metadata"] != labels[digest]:
            raise ValueError(f"label mismatch: {arm}/{view}/{digest}")
        if record["evaluation"] != evaluate_output(record["raw_output"], labels[digest]):
            raise ValueError(f"contract-v2 score mismatch: {arm}/{view}/{digest}")
    return records, leaf


def _recompute(arm: str, view: str, root: Path) -> dict[str, Any]:
    records, leaf = _load_aligned_records(arm, view, root)
    info = DATASETS[view]
    canonical = flow.summarize_records(
        records, split=info["split"], expected_cases=info["cases"],
    )
    metrics = {}
    for field in METRICS:
        values = [record["evaluation"][field] for record in records
                  if record["evaluation"][field] is not None]
        passed = sum(bool(value) for value in values)
        metrics[field] = {
            "passed": passed,
            "denominator": len(values),
            "rate": passed / len(values) if values else None,
        }
        if metrics[field]["rate"] != canonical["metrics"][field]:
            raise ValueError(f"metric recomputation mismatch: {arm}/{view}/{field}")
    cases: dict[str, list[bool]] = {}
    for record in records:
        cases.setdefault(record["metadata"]["case_id"], []).append(bool(record["evaluation"]["task_success"]))
    all_five_passed = sum(len(values) == 5 and all(values) for values in cases.values())
    all_five = {
        "passed": all_five_passed,
        "denominator": len(cases),
        "rate": all_five_passed / len(cases),
    }
    if all_five["rate"] != canonical["all_five_task_success"]:
        raise ValueError(f"all-five recomputation mismatch: {arm}/{view}")
    result = {
        "model": arm,
        "view": view,
        "rows": len(records),
        "cases": len(cases),
        "split": info["split"],
        "metrics": metrics,
        "all_five_task_success": all_five,
        "raw_predictions_path": str(leaf / "raw_predictions.json"),
        "raw_predictions_sha256": sha256_file(leaf / "raw_predictions.json"),
        "saved_summary_exact_match": False,
    }
    summary_path = leaf / "summary.json"
    if summary_path.is_file():
        saved = json.loads(summary_path.read_text(encoding="utf-8"))
        regenerated = flow.summarize_records(records, split=info["split"], expected_cases=info["cases"])
        regenerated.update({
            "model": arm,
            "evaluation_kind": view,
            "split": info["split"],
            "task_contract": "evidencetune.task.v2",
            "evaluation_protocol": "evidencetune.evaluation.v2",
            "backend": saved.get("backend"),
            "raw_predictions": "raw_predictions.json",
        })
        result["saved_summary_exact_match"] = saved == regenerated
        if not result["saved_summary_exact_match"]:
            raise ValueError(f"saved summary mismatch: {arm}/{view}")
        result["saved_summary_sha256"] = sha256_file(summary_path)
        result["plan_sha256"] = sha256_file(leaf / "plan.json")
    return result


def recompute_saved_arm(arm: str, view: str) -> dict[str, Any]:
    if arm not in ARMS[1:]:
        raise ValueError("recompute_saved_arm requires baseline_v7 or merge_alpha_0.75")
    return _recompute(arm, view, FROZEN_ROOT)


def paired_metric(base_records: list[dict[str, Any]], other_records: list[dict[str, Any]],
                  field: str) -> dict[str, Any]:
    """Compute other-minus-base transitions by input identity, excluding pairwise nulls."""
    base = {hashlib.sha256(record["input"].encode("utf-8")).hexdigest(): record for record in base_records}
    other = {hashlib.sha256(record["input"].encode("utf-8")).hexdigest(): record for record in other_records}
    if len(base) != len(base_records) or len(other) != len(other_records) or set(base) != set(other):
        raise ValueError("paired metrics require identical unique input identities")
    pairs = [(base[digest], other[digest]) for digest in sorted(base)
             if base[digest]["evaluation"][field] is not None
             and other[digest]["evaluation"][field] is not None]
    base_passed = sum(bool(left["evaluation"][field]) for left, _ in pairs)
    other_passed = sum(bool(right["evaluation"][field]) for _, right in pairs)
    denominator = len(pairs)
    return {
        "base_passed": base_passed,
        "other_passed": other_passed,
        "denominator": denominator,
        "base_rate": base_passed / denominator if denominator else None,
        "other_rate": other_passed / denominator if denominator else None,
        "delta": (other_passed - base_passed) / denominator if denominator else None,
        "both": sum(bool(left["evaluation"][field]) and bool(right["evaluation"][field]) for left, right in pairs),
        "base_only": sum(bool(left["evaluation"][field]) and not bool(right["evaluation"][field]) for left, right in pairs),
        "other_only": sum(not bool(left["evaluation"][field]) and bool(right["evaluation"][field]) for left, right in pairs),
        "neither": sum(not bool(left["evaluation"][field]) and not bool(right["evaluation"][field]) for left, right in pairs),
    }


def paired_all_five(base_records: list[dict[str, Any]],
                    other_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute other-minus-base case-level all-five transitions by case identity."""
    def case_values(records):
        grouped: dict[str, list[bool]] = {}
        for record in records:
            grouped.setdefault(record["metadata"]["case_id"], []).append(
                bool(record["evaluation"]["task_success"]),
            )
        return {case: len(values) == 5 and all(values) for case, values in grouped.items()}

    base = case_values(base_records)
    other = case_values(other_records)
    if set(base) != set(other):
        raise ValueError("paired all-five metrics require identical case identities")
    cases = sorted(base)
    base_passed = sum(base[case] for case in cases)
    other_passed = sum(other[case] for case in cases)
    denominator = len(cases)
    return {
        "base_passed": base_passed,
        "other_passed": other_passed,
        "denominator": denominator,
        "base_rate": base_passed / denominator if denominator else None,
        "other_rate": other_passed / denominator if denominator else None,
        "delta": (other_passed - base_passed) / denominator if denominator else None,
        "both": sum(base[case] and other[case] for case in cases),
        "base_only": sum(base[case] and not other[case] for case in cases),
        "other_only": sum(not base[case] and other[case] for case in cases),
        "neither": sum(not base[case] and not other[case] for case in cases),
    }


def compare_records(records: dict[str, dict[str, list[dict[str, Any]]]]) -> dict[str, Any]:
    """Describe all pairwise arm deltas without ranking or model selection."""
    comparisons = (
        ("baseline_v7_minus_raw_base", "raw_base", "baseline_v7"),
        ("merge_alpha_0.75_minus_raw_base", "raw_base", "merge_alpha_0.75"),
        ("merge_alpha_0.75_minus_baseline_v7", "baseline_v7", "merge_alpha_0.75"),
    )
    result = {}
    for view in DATASETS:
        result[view] = {}
        for label, base_arm, other_arm in comparisons:
            metrics = {
                field: paired_metric(records[base_arm][view], records[other_arm][view], field)
                for field in METRICS
            }
            metrics["all_five_task_success"] = paired_all_five(
                records[base_arm][view], records[other_arm][view],
            )
            result[view][label] = metrics
    return result


def generate_raw_base(output_root: Path, *, batch_size: int = 8) -> dict[str, Any]:
    """Generate only raw_base predictions for the two explicitly locked views."""
    if batch_size != 8:
        raise ValueError("this descriptive replication requires batch_size=8")
    provenance = verify_frozen_artifacts()
    run_plan = {
        "schema_version": 1,
        "evaluation_kind": "raw_base_frozen_descriptive",
        "post_selection_descriptive_only": True,
        "selection_unchanged": True,
        "selected_model": "merge_alpha_0.75",
        "base_model": MODEL,
        "base_commit": provenance["base_commit"],
        "tokenizer_files_sha256": provenance["tokenizer_files"],
        "adapter_used": False,
        "adapter_path": None,
        "adapter_model_sha256": None,
        "backend": "local Apple MPS bf16 Transformers; post-selection raw-base descriptive baseline only",
        "dtype": "bfloat16",
        "device": "mps",
        "offline_model_loading": True,
        "generation": {"max_new_tokens": 80, "do_sample": False, "batch_size": batch_size},
        "datasets": {view: {
            "source_sha256": info["source_sha256"],
            "labels_sha256": info["labels_sha256"],
            "cases": info["cases"],
            "rows": info["rows"],
            "split": info["split"],
        } for view, info in DATASETS.items()},
        "training_performed": False,
        "tuning_performed": False,
        "other_frozen_cases_inspected": False,
        "base_eval_sha256": sha256_file(Path(__file__).resolve()),
    }
    _write_leaf_plan(output_root, run_plan)
    atomic_write_json(output_root / "provenance.json", provenance)
    datasets = _load_frozen_data()
    tokenizer, model = load_raw_base()
    results = {}
    timing = {"views": {}}
    generation_started = time.perf_counter()
    for view, (rows, labels) in datasets.items():
        started = time.perf_counter()
        generator = MPSGenerator(tokenizer, model, batch_size=batch_size, label=f"raw_base/{view}")
        results[view] = run_single_turn(
            "raw_base", view, rows, labels, generator, output_root,
            expected_cases=DATASETS[view]["cases"],
            source_sha256=DATASETS[view]["source_sha256"],
            labels_sha256=DATASETS[view]["labels_sha256"],
            split=DATASETS[view]["split"],
            backend=run_plan["backend"],
        )
        timing["views"][view] = {"seconds": time.perf_counter() - started}
        print(json.dumps({
            "event": "raw_base_view_complete", "view": view,
            "rows": results[view]["rows"],
            "task_success": results[view]["metrics"]["task_success"],
            "all_five_task_success": results[view]["all_five_task_success"],
            "seconds": timing["views"][view]["seconds"],
        }), flush=True)
    timing["generation_seconds"] = time.perf_counter() - generation_started
    atomic_write_json(output_root / "timing.json", timing)
    return results


def build_summary(prediction_root: Path, output_path: Path) -> dict[str, Any]:
    """Independently recompute all arms and save the descriptive three-arm summary."""
    provenance = verify_frozen_artifacts()
    results = {}
    records = {}
    for arm in ARMS:
        results[arm] = {}
        records[arm] = {}
        root = prediction_root if arm == "raw_base" else FROZEN_ROOT
        for view in DATASETS:
            results[arm][view] = _recompute(arm, view, root)
            records[arm][view], _ = _load_aligned_records(arm, view, root)
    paired_deltas = compare_records(records)
    timing_path = prediction_root / "timing.json"
    timing = json.loads(timing_path.read_text(encoding="utf-8")) if timing_path.is_file() else {}
    packages = {}
    for name in ("torch", "transformers", "tokenizers", "huggingface-hub", "safetensors"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    summary = {
        "schema_version": 1,
        "evaluation_kind": "raw_base_post_selection_descriptive_baseline",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "post_selection_descriptive_only": True,
        "post_hoc_baseline": True,
        "selection_unchanged": True,
        "selected_model": "merge_alpha_0.75",
        "selection_rule_reapplied": False,
        "training_performed": False,
        "tuning_performed": False,
        "model_reselection_performed": False,
        "public_model_altered": False,
        "other_frozen_cases_inspected": False,
        "kaggle_results_included": False,
        "raw_base_adapter_used": False,
        "arms": list(ARMS),
        "views": list(DATASETS),
        "task_contract": "evidencetune.task.v2",
        "evaluation_protocol": "evidencetune.evaluation.v2",
        "results": results,
        "paired_deltas": paired_deltas,
        "paired_delta_convention": "other arm minus named base arm; input-aligned rows, case-aligned all-five; no significance testing",
        "provenance": provenance,
        "runtime": timing,
        "software": {"python": platform.python_version(), **packages},
        "behavior_caveats": [
            "task_success is strict contract-v2 format plus acceptable action plus post-action working answer.",
            "action_ok excludes solo rows because solo has no action; all-five uses cases and requires five successful rows.",
            "whole_window_answer_ok is diagnostic and may be false for a behaviorally successful unsupported_toward CLARIFY or RETAIN.",
            "Paired deltas are descriptive frozen-suite differences, not causal claims or statistical significance tests.",
            "All three arms are saved/current local Apple MPS artifacts; no Kaggle metrics are mixed into this summary.",
            "Scope is only these two current contract-v2 suites, not general, human, or natural-language performance.",
        ],
    }
    atomic_write_json(output_path, summary)
    atomic_write_json(output_path.parent / "provenance.json", provenance)
    return summary

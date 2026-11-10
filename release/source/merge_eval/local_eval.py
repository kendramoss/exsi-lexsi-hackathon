#!/usr/bin/env python3
"""Resume-safe five-arm dev-only EvidenceTune evaluation on local Apple MPS."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

MERGE_ROOT = Path(__file__).resolve().parent
ROOT = MERGE_ROOT.parent
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contract_unification.contract_v2 import evaluate_output, validate_pack
from scorers.resolution_replay import build_resolution_case_context, validate_resolution_document
from next_run import kaggle_next_flow as flow
from v8_resolution.pilot import load_evaluation_cases
from v8_resolution.resolution import Generation, evaluate_cases

MODEL = "CohereLabs/tiny-aya-global"
BACKEND = "local Apple MPS bf16 Transformers; dev-only five-arm evaluation"
DEFAULT_OUTPUT = MERGE_ROOT / "local_results"
DEFAULT_BATCH_SIZE = 8
MAX_NEW_TOKENS = 80


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _finite_rate(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"missing finite selection metric: {label}")
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"selection metric outside [0,1] or nonfinite: {label}")
    return value


def select_dev(results: dict[str, dict[str, Any]], order: list[str]) -> dict[str, Any]:
    """Apply the predeclared two-point task gates and resolution-first dev ranking."""
    if set(results) != set(order) or len(results) != 5:
        raise ValueError("selection requires exactly the five planned dev arms")
    rates = {}
    for name in order:
        try:
            rates[name] = {
                "semantic_task_success": _finite_rate(
                    results[name]["semantic_dev"]["metrics"]["task_success"],
                    f"{name}/semantic_dev/task_success",
                ),
                "targeted_task_success": _finite_rate(
                    results[name]["v8_targeted_dev"]["metrics"]["task_success"],
                    f"{name}/v8_targeted_dev/task_success",
                ),
                "resolution_overall": _finite_rate(
                    results[name]["resolution_dev"]["metrics"]["resolution"]["overall"]["rate"],
                    f"{name}/resolution_dev/overall",
                ),
            }
        except KeyError as error:
            raise ValueError(f"missing selection summary for {name}: {error}") from error

    baseline = rates["baseline_v7"]
    gates = {}
    epsilon = 1e-12
    for name in order:
        current = rates[name]
        deltas = {
            "semantic_dev_task_success": current["semantic_task_success"] - baseline["semantic_task_success"],
            "v8_targeted_dev_task_success": current["targeted_task_success"] - baseline["targeted_task_success"],
            "resolution_dev_overall_rate": current["resolution_overall"] - baseline["resolution_overall"],
        }
        violations = []
        if deltas["semantic_dev_task_success"] < -0.02 - epsilon:
            violations.append("semantic_dev_task_success_drop_exceeds_2pp")
        if deltas["v8_targeted_dev_task_success"] < -0.02 - epsilon:
            violations.append("v8_targeted_dev_task_success_drop_exceeds_2pp")
        if deltas["resolution_dev_overall_rate"] < -epsilon:
            violations.append("resolution_dev_below_v7")
        gates[name] = {
            "metrics": current,
            "deltas_from_baseline_v7": deltas,
            "maximum_allowed_task_success_drop": 0.02,
            "minimum_allowed_resolution_delta": 0.0,
            "violations": violations,
            "passed": not violations,
        }

    eligible = [name for name in order if gates[name]["passed"]]
    ranking = sorted(
        eligible,
        key=lambda name: (
            -rates[name]["resolution_overall"],
            -(rates[name]["semantic_task_success"] + rates[name]["targeted_task_success"]) / 2.0,
            -rates[name]["semantic_task_success"],
            -rates[name]["targeted_task_success"],
            order.index(name),
        ),
    )
    if not ranking:
        raise ValueError("no eligible model; baseline selection metrics must be complete")
    return {
        "schema_version": 1,
        "selected_model": ranking[0],
        "selection_split": "dev_only",
        "selection_rule": (
            "eligible: semantic and targeted task_success deltas >= -0.02 and resolution overall delta >= 0 "
            "versus same-run v7; rank resolution overall, mean task_success, semantic task_success, "
            "targeted task_success, then fixed candidate order"
        ),
        "candidate_order": order,
        "ranking": ranking,
        "eligible_models": eligible,
        "gates": gates,
        "frozen_test_used_for_selection": False,
        "resolution_dev_used_for_selection": True,
    }


def make_record(row: dict[str, Any], raw_output: str, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "input": row["input"],
        "raw_output": raw_output,
        "metadata": metadata,
        "evaluation": evaluate_output(raw_output, metadata),
    }


class MPSGenerator:
    """Batched greedy message generation with per-row token accounting."""

    def __init__(self, tokenizer: Any, model: Any, *, batch_size: int, label: str):
        self.tokenizer = tokenizer
        self.model = model
        self.batch_size = batch_size
        self.label = label
        self.batch_number = 0
        self.total_calls = 0
        if tokenizer.pad_token_id is None:
            raise ValueError("tiny-aya tokenizer has no padding token for batched generation")

    def __call__(self, conversations: list[list[dict[str, str]]]) -> list[Generation]:
        import torch

        outputs = []
        for start in range(0, len(conversations), self.batch_size):
            batch = conversations[start:start + self.batch_size]
            texts = [
                self.tokenizer.apply_chat_template(
                    conversation, add_generation_prompt=True, tokenize=False,
                )
                for conversation in batch
            ]
            encoded = self.tokenizer(
                texts, return_tensors="pt", padding=True, add_special_tokens=False,
            ).to("mps")
            prompt_width = encoded["input_ids"].shape[1]
            started = time.perf_counter()
            with torch.inference_mode():
                generated = self.model.generate(
                    **encoded,
                    max_new_tokens=MAX_NEW_TOKENS,
                    do_sample=False,
                    pad_token_id=self.tokenizer.pad_token_id,
                )
            elapsed = time.perf_counter() - started
            attention = encoded.get("attention_mask")
            for offset, row in enumerate(generated):
                completion = row[prompt_width:]
                text = self.tokenizer.decode(completion, skip_special_tokens=True).strip()
                prompt_tokens = int(attention[offset].sum().item()) if attention is not None else prompt_width
                outputs.append(Generation(text, prompt_tokens, len(completion)))
            self.batch_number += 1
            self.total_calls += len(batch)
            print(json.dumps({
                "event": "generation_batch_complete",
                "label": self.label,
                "batch": self.batch_number,
                "batch_rows": len(batch),
                "generated_rows_total": self.total_calls,
                "batch_seconds": round(elapsed, 3),
            }), flush=True)
        return outputs


def _write_leaf_plan(root: Path, plan: dict[str, Any]) -> None:
    destination = root / "plan.json"
    if destination.exists():
        if json.loads(destination.read_text(encoding="utf-8")) != plan:
            raise ValueError(f"saved evaluation leaf plan changed: {root}")
    else:
        atomic_write_json(destination, plan)


def run_single_turn(
    model_name: str,
    view: str,
    rows: list[dict[str, Any]],
    labels: dict[str, dict[str, Any]],
    generate: MPSGenerator,
    output_root: Path,
    *,
    expected_cases: int,
    source_sha256: str,
    labels_sha256: str,
    split: str = "dev",
    backend: str = BACKEND,
) -> dict[str, Any]:
    if split not in ("dev", "frozen_test", "new_independent_frozen_test"):
        raise ValueError(f"unsupported single-turn evaluation split: {split}")
    root = output_root / "evaluation" / model_name / view
    plan = {
        "schema_version": 1,
        "model": model_name,
        "view": view,
        "split": split,
        "expected_cases": expected_cases,
        "expected_rows": expected_cases * 5,
        "source_sha256": source_sha256,
        "labels_sha256": labels_sha256,
        "generation": {"max_new_tokens": MAX_NEW_TOKENS, "do_sample": False, "batch_size": generate.batch_size},
        "backend": backend,
    }
    _write_leaf_plan(root, plan)
    raw_path = root / "raw_predictions.json"
    summary_path = root / "summary.json"
    if raw_path.is_file() and summary_path.is_file():
        records = json.loads(raw_path.read_text(encoding="utf-8"))["records"]
        summary = flow.summarize_records(records, split=split, expected_cases=expected_cases)
        saved = json.loads(summary_path.read_text(encoding="utf-8"))
        if saved["metrics"] != summary["metrics"] or saved["rows"] != len(records):
            raise ValueError(f"saved summary does not match raw predictions: {root}")
        return saved

    batches = root / "batches"
    batches.mkdir(parents=True, exist_ok=True)
    records = []
    for start in range(0, len(rows), generate.batch_size):
        batch_rows = rows[start:start + generate.batch_size]
        batch_path = batches / f"batch_{start // generate.batch_size:05d}.json"
        if batch_path.exists():
            payload = json.loads(batch_path.read_text(encoding="utf-8"))
            batch_records = payload["records"]
            if len(batch_records) != len(batch_rows):
                raise ValueError(f"saved batch row count differs: {batch_path}")
            for record, row in zip(batch_records, batch_rows):
                if record["input"] != row["input"] or record["evaluation"] != evaluate_output(record["raw_output"], record["metadata"]):
                    raise ValueError(f"saved batch identity/score mismatch: {batch_path}")
        else:
            conversations = [[{"role": "user", "content": f"{row['instruction']}\n\n{row['input']}"}] for row in batch_rows]
            generated = list(generate(conversations))
            if len(generated) != len(batch_rows):
                raise ValueError("generator returned incomplete single-turn batch")
            batch_records = []
            for row, output in zip(batch_rows, generated):
                metadata = labels[flow.input_sha256(row["input"])]
                record = make_record(row, output.text, metadata)
                record["prompt_tokens"] = output.prompt_tokens
                record["completion_tokens"] = output.completion_tokens
                batch_records.append(record)
            atomic_write_json(batch_path, {
                "schema_version": 1,
                "model": model_name,
                "view": view,
                "batch_index": start // generate.batch_size,
                "records": batch_records,
            })
        records.extend(batch_records)
    if len(records) != len(rows):
        raise ValueError(f"incomplete raw predictions for {model_name}/{view}")
    atomic_write_json(raw_path, {
        "schema_version": 1,
        "model": model_name,
        "view": view,
        "split": split,
        "records": records,
    })
    summary = flow.summarize_records(records, split=split, expected_cases=expected_cases)
    summary.update({
        "model": model_name,
        "evaluation_kind": view,
        "split": split,
        "task_contract": "evidencetune.task.v2",
        "evaluation_protocol": "evidencetune.evaluation.v2",
        "backend": backend,
        "raw_predictions": "raw_predictions.json",
    })
    atomic_write_json(summary_path, summary)
    return summary


def run_resolution(
    model_name: str,
    cases: Sequence[Any],
    generate: MPSGenerator,
    output_root: Path,
    *,
    source_sha256: str,
    labels_sha256: str,
) -> dict[str, Any]:
    root = output_root / "evaluation" / model_name / "resolution_dev"
    plan = {
        "schema_version": 1,
        "model": model_name,
        "view": "resolution_dev",
        "split": "resolution_dev",
        "expected_cases": 32,
        "expected_initial_rows": 128,
        "source_sha256": source_sha256,
        "labels_sha256": labels_sha256,
        "native_messages": True,
        "generation": {"max_new_tokens": MAX_NEW_TOKENS, "do_sample": False, "batch_size": generate.batch_size},
        "backend": BACKEND,
    }
    _write_leaf_plan(root, plan)
    raw_path = root / "resolution_raw.json"
    summary_path = root / "summary.json"
    if raw_path.is_file() and summary_path.is_file():
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        saved = json.loads(summary_path.read_text(encoding="utf-8"))
        context = build_resolution_case_context(ROOT / "resolution_expand/pack")
        validate_resolution_document(raw, saved, context)
        return saved
    result = evaluate_cases(cases, generate)
    if result["metrics"]["cases"] != 32 or result["metrics"]["rows"] != 128 or len(result["records"]) != 128:
        raise ValueError(f"incomplete resolution evaluation for {model_name}")
    result["protocol"]["scope"] = "32-case non-fresh resolution development expansion; no frozen rows"
    atomic_write_json(raw_path, result)
    summary = {
        "model": model_name,
        "evaluation_kind": "resolution_dev",
        "split": "resolution_dev",
        "resolution_contract": "evidencetune.resolution.v8",
        "evaluation_protocol": "evidencetune.evaluation.resolution.v8",
        "native_messages": True,
        "backend": BACKEND,
        "protocol": result["protocol"],
        "metrics": result["metrics"],
        "raw_resolution": "resolution_raw.json",
    }
    atomic_write_json(summary_path, summary)
    return summary


def _verify_dev_inputs(plan: dict[str, Any]) -> None:
    for name, model in plan["models"].items():
        adapter = Path(model["adapter_path"])
        actual = sha256_file(adapter / "adapter_model.safetensors")
        if actual != model["adapter_model_sha256"]:
            raise ValueError(f"adapter hash mismatch for {name}")
    for name, dataset in plan["datasets"].items():
        for kind in ("source", "labels"):
            path = Path(dataset[f"{kind}_path"])
            if sha256_file(path) != dataset[f"{kind}_sha256"]:
                raise ValueError(f"dev input hash mismatch for {name}/{kind}")


def _load_dev_data(plan: dict[str, Any]) -> tuple[dict[str, Any], list[Any]]:
    semantic_info = plan["datasets"]["semantic_dev"]
    semantic_rows, semantic_labels = flow.load_semantic_split(
        Path(semantic_info["source_path"]).parent, "dev", validate=True,
    )
    targeted_info = plan["datasets"]["v8_targeted_dev"]
    targeted_rows = flow.read_jsonl(targeted_info["source_path"])
    targeted_labels = json.loads(Path(targeted_info["labels_path"]).read_text(encoding="utf-8"))
    validation = validate_pack(targeted_rows, targeted_labels)
    if validation["cases"] != 36 or validation["rows"] != 180:
        raise ValueError("unexpected v8 targeted dev size")
    resolution_info = plan["datasets"]["resolution_dev"]
    cases = load_evaluation_cases(
        resolution_info["source_path"], resolution_info["labels_path"], expected_split="resolution_dev",
    )
    if len(cases) != 32:
        raise ValueError("resolution expansion must contain exactly 32 cases")
    return {
        "semantic_dev": (semantic_rows, semantic_labels),
        "v8_targeted_dev": (targeted_rows, targeted_labels),
    }, cases


def main(output_root: Path = DEFAULT_OUTPUT, batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, Any]:
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.backends.mps.is_available():
        raise RuntimeError("local MPS is unavailable")
    plan = json.loads((MERGE_ROOT / "evaluation_plan.json").read_text(encoding="utf-8"))
    _verify_dev_inputs(plan)
    datasets, resolution_cases = _load_dev_data(plan)
    order = plan["candidate_order"]
    run_plan = {
        "schema_version": 1,
        "experiment": "evidencetune_v7_v8_lora_interpolation_local_dev",
        "base_model": MODEL,
        "backend": BACKEND,
        "dtype": "bfloat16",
        "device": "mps",
        "offline_model_loading": True,
        "generation": {"max_new_tokens": MAX_NEW_TOKENS, "do_sample": False, "batch_size": batch_size},
        "candidate_order": order,
        "models": plan["models"],
        "datasets": plan["datasets"],
        "selection_rule": plan["selection_rule"],
        "retention_gates": plan["retention_gates"],
        "local_eval_sha256": sha256_file(Path(__file__).resolve()),
        "frozen_test_used": False,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    _write_leaf_plan(output_root, run_plan)
    atomic_write_json(output_root / "progress.json", {"event": "inputs_validated", "completed_models": []})

    print(json.dumps({"event": "loading_base_and_adapters", "models": order}), flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True)
    tokenizer.padding_side = "left"
    base = AutoModelForCausalLM.from_pretrained(
        MODEL, dtype=torch.bfloat16, local_files_only=True,
    ).to("mps").eval()
    model = None
    adapter_names = {name: f"arm_{index}" for index, name in enumerate(order)}
    for name in order:
        adapter = plan["models"][name]["adapter_path"]
        adapter_name = adapter_names[name]
        if model is None:
            model = PeftModel.from_pretrained(base, adapter, adapter_name=adapter_name, is_trainable=False)
        else:
            model.load_adapter(adapter, adapter_name=adapter_name)
    model.eval()
    results = {}
    try:
        for name in order:
            started = time.perf_counter()
            model.set_adapter(adapter_names[name])
            print(json.dumps({"event": "model_started", "model": name}), flush=True)
            results[name] = {}
            for view, (rows, labels) in datasets.items():
                generator = MPSGenerator(tokenizer, model, batch_size=batch_size, label=f"{name}/{view}")
                results[name][view] = run_single_turn(
                    name, view, rows, labels, generator, output_root,
                    expected_cases=plan["datasets"][view]["cases"],
                    source_sha256=plan["datasets"][view]["source_sha256"],
                    labels_sha256=plan["datasets"][view]["labels_sha256"],
                )
                print(json.dumps({
                    "event": "view_complete", "model": name, "view": view,
                    "task_success": results[name][view]["metrics"]["task_success"],
                }), flush=True)
            generator = MPSGenerator(tokenizer, model, batch_size=batch_size, label=f"{name}/resolution_dev")
            results[name]["resolution_dev"] = run_resolution(
                name, resolution_cases, generator, output_root,
                source_sha256=plan["datasets"]["resolution_dev"]["source_sha256"],
                labels_sha256=plan["datasets"]["resolution_dev"]["labels_sha256"],
            )
            print(json.dumps({
                "event": "model_complete", "model": name,
                "seconds": round(time.perf_counter() - started, 3),
                "resolution_overall": results[name]["resolution_dev"]["metrics"]["resolution"]["overall"]["rate"],
            }), flush=True)
            atomic_write_json(output_root / "progress.json", {
                "event": "model_complete", "completed_models": list(results), "results": results,
            })
    finally:
        del model
        del base
        gc.collect()
        torch.mps.empty_cache()

    selection = select_dev(results, order)
    selection.update({
        "selected_adapter_model_sha256": plan["models"][selection["selected_model"]]["adapter_model_sha256"],
        "run_plan_sha256": sha256_file(output_root / "plan.json"),
        "new_frozen_generation_started": False,
    })
    atomic_write_json(output_root / "evaluation" / "selection.json", selection)
    final = {
        "schema_version": 1,
        "status": "COMPLETE",
        "backend": BACKEND,
        "results": results,
        "selection": selection,
        "frozen_test_used_for_selection": False,
        "new_frozen_generation_started": False,
    }
    atomic_write_json(output_root / "evaluation" / "summary.json", final)
    print(json.dumps({"event": "selection_complete", "selection": selection}), flush=True)
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    arguments = parser.parse_args()
    summary = main(arguments.output_root, arguments.batch_size)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2), flush=True)

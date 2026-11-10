from __future__ import annotations

import base64
import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

from .spike import (
    GATE, MERGED_SHA256, atomic_json, early_gate_from_resolution, evaluate_gate,
    input_sha256, read_jsonl, sha256_file, training_plan, validate_merged_adapter,
)

BASELINE = "merge_alpha_0.75"
CANDIDATE = "balanced_sft"


def _rate(records, field):
    values = [r["evaluation"][field] for r in records if r["evaluation"][field] is not None]
    return sum(bool(v) for v in values) / len(values) if values else None


def _aggregate(records):
    cases = {}
    for record in records:
        cases.setdefault(record["metadata"]["case_id"], []).append(record)
    return {
        "rows": len(records), "cases": len(cases),
        "metrics": {name: _rate(records, name) for name in
                    ("format_ok", "action_ok", "answer_ok", "task_success", "whole_window_answer_ok", "terminal")},
        "all_five_task_success": (sum(len(group) == 5 and all(row["evaluation"]["task_success"] for row in group)
                                      for group in cases.values()) / len(cases) if cases else None),
    }


def _truth_aggregate(records):
    summary = _aggregate(records)
    correction = [r for r in records if r["metadata"]["condition"] != "solo"]
    pairs = []
    cases = {}
    for record in records:
        cases.setdefault(record["metadata"]["case_id"], []).append(record)
    for group in cases.values():
        by_condition = {r["metadata"]["condition"]: r for r in group}
        if "valid" in by_condition and "unsupported_toward" in by_condition:
            pairs.append(bool(by_condition["valid"]["evaluation"]["task_success"] and
                              by_condition["unsupported_toward"]["evaluation"]["task_success"]))
    summary.update({
        "task_success": _rate(records, "task_success"), "action_ok": _rate(records, "action_ok"),
        "correction_rows": len(correction), "pairs": len(pairs),
        "valid_unsupported_toward_pair_success": sum(pairs) / len(pairs) if pairs else None,
    })
    return summary


def summarize_with_truth(records, *, split: str, expected_cases: int):
    if not records:
        raise ValueError("empty evaluation")
    seen = set()
    for record in records:
        if record["metadata"]["split"] != split:
            raise ValueError("foreign split entered dev evaluation")
        digest = input_sha256(record["input"])
        if digest in seen:
            raise ValueError("duplicate evaluation record")
        seen.add(digest)
    summary = _aggregate(records)
    if summary["cases"] != expected_cases or summary["rows"] != expected_cases * 5:
        raise ValueError("incomplete semantic/targeted dev evaluation")
    summary["by_truth"] = {truth: _truth_aggregate([r for r in records if r["metadata"]["truth"] == truth])
                           for truth in ("no", "yes")}
    summary["complete_records"] = True
    summary["errors"] = 0
    return summary


def dev_evaluation_plan(semantic_root: Path, targeted_root: Path, resolution_root: Path):
    return {
        "schema_version": 1, "model_order": [BASELINE, CANDIDATE], "backend": "Kaggle fp16 Transformers",
        "generation": {"max_new_tokens": 80, "do_sample": False, "batch_size": 1},
        "datasets": {
            "semantic_dev": {"source": str(semantic_root / "dev_source.jsonl"),
                             "labels": str(semantic_root / "dev_labels.json"), "cases": 48, "split": "dev"},
            "v8_targeted_dev": {"source": str(targeted_root / "dev_source.jsonl"),
                                "labels": str(targeted_root / "dev_labels.json"), "cases": 36, "split": "dev"},
            "resolution_dev": {"source": str(resolution_root / "dev_source.jsonl"),
                               "labels": str(resolution_root / "dev_labels.json"), "cases": 32,
                               "split": "resolution_dev", "initial_rows": 128},
        },
        "gate": GATE,
    }


def packaged_code_roots(input_root):
    """Resolve actual Kaggle dataset mount roots containing the package."""
    input_root = Path(input_root)
    candidates = [input_root]
    if input_root.is_dir():
        candidates.extend(path for path in input_root.iterdir() if path.is_dir())
    return [path for path in candidates if (path / "balanced_spike" / "__init__.py").is_file()]


def code_source_inventory():
    raw = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")
    local = Path(__file__).parent
    inventory = {
        "balanced_spike/__init__.py": local / "__init__.py",
        "balanced_spike/spike.py": local / "spike.py",
        "balanced_spike/kaggle_flow.py": local / "kaggle_flow.py",
        "backend_release/__init__.py": raw / "backend_release" / "__init__.py",
        "backend_release/recovery.py": raw / "backend_release" / "recovery.py",
        "backend_release/train_driver.py": raw / "backend_release" / "train_driver.py",
        "contract_unification/contract_v2.py": raw / "contract_unification" / "contract_v2.py",
        "next_run/kaggle_next_flow.py": raw / "next_run" / "kaggle_next_flow.py",
        "issue7/__init__.py": raw / "issue7" / "__init__.py",
        "issue7/clarification_eval.py": raw / "issue7" / "clarification_eval.py",
        "v8_resolution/__init__.py": raw / "v8_resolution" / "__init__.py",
        "v8_resolution/resolution.py": raw / "v8_resolution" / "resolution.py",
        "v8_resolution/pilot.py": raw / "v8_resolution" / "pilot.py",
        "v8_resolution/kaggle_integration.py": raw / "v8_resolution" / "kaggle_integration.py",
    }
    for name, path in inventory.items():
        if not path.is_file():
            raise ValueError(f"missing dependency source: {name}")
    return inventory


def data_source_inventory():
    raw = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")
    data_root = Path("/Users/anasqumhiyeh/.claude/worktrees/exsi-balanced/.balanced_spike/data")
    inventory = {}
    for name in (
        "preregistration.json", "preregistration.sha256.json", "data_manifest.json",
        "roster.json", "train_source.jsonl", "train_labels.json", "curated/sft_alpaca.jsonl",
    ):
        inventory[f"payload/data/{name}"] = data_root / name
    for path in sorted(data_root.rglob("*")):
        if path.is_file() and path.name != "dataset-metadata.json":
            inventory[f"payload/data/{path.relative_to(data_root)}"] = path
    for name in ("dev_followup_labels.json", "dev_followup_source.jsonl", "native_chat.jsonl"):
        inventory[f"payload/data/resolution_dev/{name}"] = raw / "resolution_expand" / "pack" / name
    for prefix, pack in (("semantic", raw / "semantic_contrast" / "packs_v2"),
                         ("targeted", raw / "v8_data" / "packs")):
        for name in ("MANIFEST.json", "dev_source.jsonl", "dev_labels.json"):
            inventory[f"payload/{prefix}/{name}"] = pack / name
    for name, path in inventory.items():
        if not path.is_file():
            raise ValueError(f"missing embedded data source: {name}")
    return inventory


def dependency_source_inventory():
    return {**code_source_inventory(), **data_source_inventory()}


def embedded_module_payloads():
    embedded = {}
    for name, source in dependency_source_inventory().items():
        payload = source.read_bytes()
        embedded[name] = {"sha256": hashlib.sha256(payload).hexdigest(),
                          "base64": base64.b64encode(payload).decode("ascii")}
    return embedded


def materialize_embedded_code(embedded, working_root):
    if set(embedded) != set(dependency_source_inventory()):
        raise ValueError("embedded dependency inventory changed")
    for name, record in embedded.items():
        payload = base64.b64decode(record["base64"])
        if hashlib.sha256(payload).hexdigest() != record["sha256"]:
            raise ValueError(f"embedded module hash mismatch: {name}")
        destination = Path(working_root) / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    return Path(working_root) / "balanced_spike"


def build_notebook():
    embedded = embedded_module_payloads()
    setup = '''import os, sys, base64, hashlib
from pathlib import Path
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
EMBEDDED = ''' + json.dumps(embedded, sort_keys=True) + '''
for name, record in EMBEDDED.items():
    payload = base64.b64decode(record["base64"])
    if hashlib.sha256(payload).hexdigest() != record["sha256"]:
        raise ValueError(f"embedded module hash mismatch: {name}")
    destination = Path("/kaggle/working") / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
sys.path.insert(0, "/kaggle/working")
from backend_release.train_driver import run_plan
from contract_unification.contract_v2 import evaluate_output, validate_pack
from next_run.kaggle_next_flow import MODEL
from issue7.clarification_eval import Case, EvalRow
from v8_resolution.kaggle_integration import make_hf_generator
from balanced_spike.kaggle_flow import BASELINE, main
assert BASELINE == "merge_alpha_0.75"
'''
    install = r'''!pip -q install "transformers==5.22.1" "peft==0.21.2" "datasets==5.1.0" "accelerate==1.15.0" "trl==1.14.2" "safetune @ git+https://github.com/Lexsi-Labs/SafeTune.git@a869414b6825e41174e74cd64832d2dcf8f6a9e7" "curatorkit @ git+https://github.com/Lexsi-Labs/CuratorKIT.git@dd9e835301fcddc74a37501d9e207a5a060d209f" "auditkit @ git+https://github.com/Lexsi-Labs/AuditKIT.git@71316da345784ff220d5ed59337441a59ab31526"
!pip uninstall -y torchao'''
    run = r'''from kaggle_secrets import UserSecretsClient
from huggingface_hub import hf_hub_download
os.environ["HF_TOKEN"] = UserSecretsClient().get_secret("HF_TOKEN")
adapter_root = Path("/kaggle/working/merged_alpha_075_adapter")
for name in ("adapter_config.json", "adapter_model.safetensors"):
    hf_hub_download("Mizore66/evidencetune-merged-alpha-0.75", name, local_dir=adapter_root)
main(
    work="/kaggle/working/balanced_spike_work",
    output_root="/kaggle/working/balanced_spike_output",
    data_root="/kaggle/working/payload/data",
    semantic_root="/kaggle/working/payload/semantic",
    targeted_root="/kaggle/working/payload/targeted",
    merged_adapter_source=adapter_root,
)
'''
    return {"cells": [
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": setup.splitlines(True)},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": install.splitlines(True)},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": run.splitlines(True)},
    ], "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                     "language_info": {"name": "python", "version": "3.11"},
                     "balanced_spike_embedded": embedded}, "nbformat": 4, "nbformat_minor": 4}


def verify_preregistration_document(document, expected, actual):
    if expected != actual:
        raise ValueError("preregistration hash mismatch")
    if document.get("training_authorized") is not True:
        raise ValueError("training is not authorized by semantic/freshness GO")


def verify_dev_inputs(prereg, semantic_root: Path, targeted_root: Path, resolution_root: Path):
    roots = {"semantic_dev": Path(semantic_root), "v8_targeted_dev": Path(targeted_root),
             "resolution_dev": Path(resolution_root)}
    for view, root in roots.items():
        expected = prereg["dev"][view]
        if sha256_file(root / "dev_source.jsonl") != expected["source_sha256"]:
            raise ValueError(f"{view} source differs from preregistration")
        if sha256_file(root / "dev_labels.json") != expected["labels_sha256"]:
            raise ValueError(f"{view} labels differ from preregistration")
    return True


def stage_merged_baseline(source: Path, output: Path, next_flow):
    from backend_release.recovery import ARTIFACT_MANIFEST, ARM_COMPLETION_MARKER
    validate_merged_adapter(source)
    plan = {"schema_version": 1, "role": "merged_alpha_0.75_baseline", "base_model": next_flow.MODEL,
            "adapter_model_sha256": MERGED_SHA256}
    if (output / ARM_COMPLETION_MARKER).is_file():
        return next_flow._check_finalized(output, BASELINE, plan)
    if (output / ARTIFACT_MANIFEST).exists():
        raise ValueError("unmarked merged baseline requires inspection")
    for name in ("adapter_config.json", "adapter_model.safetensors", "README.md"):
        if (source / name).is_file():
            destination = output / "adapter" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copyfile(source / name, destination)
    next_flow._finalize(output, BASELINE, plan, {"role": "merged_alpha_0.75_baseline"})
    return output / "adapter"


def train_merged_arm(arm, arm_dir: Path, resume_from_checkpoint):
    from safetune.runner.harden import _base
    from next_run import kaggle_next_flow as next_flow
    from peft.utils import set_peft_model_state_dict
    from safetensors.torch import load_file

    source = Path(arm["initial_adapter"])
    validate_merged_adapter(source)
    if arm.get("initial_adapter_weights_sha256") != MERGED_SHA256:
        raise ValueError("arm changed the merged adapter hash")
    original = _base._HardenBase._lora_base

    def continued(self):
        model = original(self)
        result = set_peft_model_state_dict(model, load_file(str(source / "adapter_model.safetensors")))
        missing = [key for key in getattr(result, "missing_keys", []) if "lora_" in key and "default" in key]
        if missing or list(getattr(result, "unexpected_keys", [])):
            raise ValueError("incompatible merged LoRA tensor state")
        for name, parameter in model.named_parameters():
            if "lora_" in name:
                parameter.requires_grad = True
        return model

    _base._HardenBase._lora_base = continued
    try:
        result = next_flow.train_kaggle_arm(arm, arm_dir, resume_from_checkpoint)
    finally:
        _base._HardenBase._lora_base = original
    return {**result, "continued_from_merge_alpha_0.75": True, "initial_adapter_weights_sha256": MERGED_SHA256}


def evaluate_single_turn(model_name, adapter: Path, view, dataset, output: Path, next_flow, contract):
    root = output / "evaluation" / model_name / view
    raw_path = root / "raw_predictions.json"
    summary_path = root / "summary.json"
    rows = read_jsonl(Path(dataset["source"]))
    labels = json.loads(Path(dataset["labels"]).read_text(encoding="utf-8"))
    if raw_path.is_file() and summary_path.is_file():
        records = json.loads(raw_path.read_text(encoding="utf-8"))["records"]
        summary = summarize_with_truth(records, split=dataset["split"], expected_cases=dataset["cases"])
        saved = json.loads(summary_path.read_text(encoding="utf-8"))
        if saved["metrics"] != summary["metrics"] or saved["by_truth"] != summary["by_truth"]:
            raise ValueError("saved dev summary differs from raw predictions")
        return saved
    root.mkdir(parents=True, exist_ok=True)
    model, tokenizer = next_flow._load_eval_model(adapter, adapter=True)
    started = time.perf_counter()
    try:
        prompts = [f"{row['instruction']}\n\n{row['input']}" for row in rows]
        outputs = next_flow._generate(model, tokenizer, prompts)
        if len(outputs) != len(rows):
            raise ValueError("incomplete generation")
        records = []
        for row, raw_output in zip(rows, outputs):
            metadata = labels[input_sha256(row["input"])]
            records.append({"input": row["input"], "raw_output": raw_output, "metadata": metadata,
                            "evaluation": contract.evaluate_output(raw_output, metadata)})
        summary = summarize_with_truth(records, split=dataset["split"], expected_cases=dataset["cases"])
        summary.update({"model": model_name, "evaluation_kind": view, "split": dataset["split"],
                        "backend": "Kaggle fp16 Transformers", "adapter_model_sha256": sha256_file(adapter / "adapter_model.safetensors"),
                        "elapsed_seconds": time.perf_counter() - started, "raw_predictions": "raw_predictions.json"})
        atomic_json(raw_path, {"schema_version": 1, "model": model_name, "view": view, "records": records})
        atomic_json(summary_path, summary)
        return summary
    finally:
        next_flow._free_model(model)


def evaluate_resolution(model_name, adapter: Path, dataset, output: Path, next_flow):
    from v8_resolution import kaggle_integration
    from v8_resolution.pilot import load_evaluation_cases
    from v8_resolution.resolution import evaluate_cases

    root = output / "evaluation" / model_name / "resolution_dev"
    raw_path, summary_path = root / "resolution_raw.json", root / "summary.json"
    if raw_path.is_file() and summary_path.is_file():
        return json.loads(summary_path.read_text(encoding="utf-8"))
    root.mkdir(parents=True, exist_ok=True)
    cases = load_evaluation_cases(dataset["source"], dataset["labels"], expected_split="resolution_dev")
    if len(cases) != 32:
        raise ValueError("resolution dev must contain 32 cases")
    model, tokenizer = next_flow._load_eval_model(adapter, adapter=True)
    started = time.perf_counter()
    try:
        generate = kaggle_integration.make_hf_generator(tokenizer, model, device="cuda", max_new_tokens=80, batch_size=1)
        result = evaluate_cases(cases, generate)
        if result["metrics"]["cases"] != 32 or result["metrics"]["rows"] != 128 or len(result["records"]) != 128:
            raise ValueError("incomplete resolution evaluation")
        result["protocol"]["scope"] = "32-case non-fresh resolution development expansion; no frozen rows"
        summary = {"model": model_name, "evaluation_kind": "resolution_dev", "split": "resolution_dev",
                   "native_messages": True, "backend": "Kaggle fp16 Transformers", "protocol": result["protocol"],
                   "metrics": result["metrics"], "elapsed_seconds": time.perf_counter() - started,
                   "complete_records": True, "errors": 0, "raw_resolution": "resolution_raw.json"}
        atomic_json(raw_path, result)
        atomic_json(summary_path, summary)
        return summary
    finally:
        next_flow._free_model(model)


def main(*, work, output_root, data_root, semantic_root, targeted_root, merged_adapter_source):
    from backend_release.train_driver import run_plan
    from contract_unification import contract_v2 as contract
    from next_run import kaggle_next_flow as next_flow

    started = time.perf_counter()
    data_root = Path(data_root)
    output = Path(output_root)
    prereg_path = data_root / "preregistration.json"
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    sidecar = json.loads((data_root / "preregistration.sha256.json").read_text(encoding="utf-8"))
    verify_preregistration_document(prereg, sidecar["sha256"], sha256_file(prereg_path))
    expected_training = {
        "algorithm": "SafeTune PlainSFT", "seed": 0, "epochs": 1, "lr": 5e-5,
        "batch_size": 1, "gradient_accumulation_steps": 4, "max_len": 1024,
        "fp16": True, "bf16": False, "gradient_checkpointing": True, "candidates": 1,
    }
    if prereg["gate"] != GATE or prereg["training"] != expected_training:
        raise ValueError("preregistered recipe/gate changed")
    manifest = json.loads((data_root / "data_manifest.json").read_text(encoding="utf-8"))
    if manifest["training_rows"] != 432 or manifest["new_rows"] != 280 or manifest["optimizer_steps"] != 108:
        raise ValueError("unexpected training composition")
    if prereg["data_manifest_sha256"] != sha256_file(data_root / "data_manifest.json"):
        raise ValueError("data manifest differs from preregistration")
    if prereg["roster_sha256"] != sha256_file(data_root / "roster.json"):
        raise ValueError("roster differs from preregistration")
    for record in manifest["files"].values():
        path = data_root / record["path"]
        if not path.is_file() or sha256_file(path) != record["sha256"]:
            raise ValueError(f"training input hash mismatch: {record['path']}")
    adapter_source = Path(merged_adapter_source)
    validate_merged_adapter(adapter_source)
    verify_dev_inputs(prereg, Path(semantic_root), Path(targeted_root), data_root / "resolution_dev")
    plan = training_plan(data_root, adapter_source)
    stage_merged_baseline(adapter_source, output / BASELINE, next_flow)
    run_plan(plan, output, trainer=train_merged_arm)
    evaluation_plan = dev_evaluation_plan(Path(semantic_root), Path(targeted_root), data_root / "resolution_dev")
    atomic_json(output / "evaluation" / "plan.json", evaluation_plan)
    results = {BASELINE: {}, CANDIDATE: {}}

    # The over-clarification gate runs immediately after the single training arm.
    # A KILL prevents every remaining evaluation and cannot trigger another candidate.
    results[CANDIDATE]["resolution_dev"] = evaluate_resolution(
        CANDIDATE, output / CANDIDATE / "adapter",
        evaluation_plan["datasets"]["resolution_dev"], output, next_flow,
    )
    early_gate = early_gate_from_resolution(results[CANDIDATE]["resolution_dev"])
    early_gate["passed"] = early_gate["status"] == "PASS"
    early_gate["violations"] = list(early_gate["failures"])
    early_gate["elapsed_seconds_total"] = time.perf_counter() - started
    early_gate["preregistration_sha256"] = sidecar["sha256"]
    atomic_json(output / "evaluation" / "early_gate.json", early_gate)
    if not early_gate["passed"]:
        atomic_json(output / "evaluation" / "gate.json", early_gate)
        atomic_json(output / "evaluation" / "summary.json", {
            "results": results, "early_gate": early_gate, "gate": early_gate,
            "full_gate_run": False, "frozen_test_used_for_selection": False,
            "automatic_public_replacement": False,
        })
        print(json.dumps({"early_gate": early_gate, "metrics": results}, indent=2, sort_keys=True), flush=True)
        return early_gate

    for view in ("semantic_dev", "v8_targeted_dev"):
        results[CANDIDATE][view] = evaluate_single_turn(
            CANDIDATE, output / CANDIDATE / "adapter", view,
            evaluation_plan["datasets"][view], output, next_flow, contract,
        )
    for view in ("semantic_dev", "v8_targeted_dev"):
        results[BASELINE][view] = evaluate_single_turn(
            BASELINE, output / BASELINE / "adapter", view,
            evaluation_plan["datasets"][view], output, next_flow, contract,
        )
    results[BASELINE]["resolution_dev"] = evaluate_resolution(
        BASELINE, output / BASELINE / "adapter",
        evaluation_plan["datasets"]["resolution_dev"], output, next_flow,
    )
    gate = evaluate_gate(results[BASELINE], results[CANDIDATE])
    gate["early_gate"] = early_gate
    gate["elapsed_seconds_total"] = time.perf_counter() - started
    gate["preregistration_sha256"] = sidecar["sha256"]
    atomic_json(output / "evaluation" / "gate.json", gate)
    atomic_json(output / "evaluation" / "summary.json", {
        "results": results, "early_gate": early_gate, "gate": gate, "full_gate_run": True,
        "frozen_test_used_for_selection": False, "automatic_public_replacement": False,
    })
    print(json.dumps({"gate": gate, "metrics": results}, indent=2, sort_keys=True), flush=True)
    return gate

import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from balanced_spike import kaggle_flow as flow
from balanced_spike import package_notebook as packager
from balanced_spike import spike


ROOT = Path(__file__).resolve().parents[2]
RAW = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")


def record(case_id, condition, truth, success=True):
    return {
        "input": f"{case_id}-{condition}", "raw_output": "unused",
        "metadata": {"case_id": case_id, "condition": condition, "truth": truth,
                     "split": "dev", "family": "numeric_conditions", "lexical_trap": False},
        "evaluation": {"format_ok": success, "action_ok": None if condition == "solo" else success,
                       "answer_ok": success, "task_success": success,
                       "whole_window_answer_ok": success, "terminal": success},
    }


def test_truth_slices_include_all_five_pair_and_denominators():
    records = [record("no-case", condition, "no") for condition in
               ("valid", "unsupported_toward", "unsupported_away", "pressure_away", "solo")]
    summary = flow.summarize_with_truth(records, split="dev", expected_cases=1)
    no = summary["by_truth"]["no"]
    assert no["rows"] == 5 and no["cases"] == 1
    assert no["correction_rows"] == 4 and no["pairs"] == 1
    assert no["task_success"] == 1.0
    assert no["all_five_task_success"] == 1.0
    assert no["valid_unsupported_toward_pair_success"] == 1.0


def test_evaluation_plan_has_one_candidate_and_no_frozen_inputs():
    plan = flow.dev_evaluation_plan(Path("/semantic"), Path("/targeted"), Path("/resolution"))
    assert plan["model_order"] == ["merge_alpha_0.75", "balanced_sft"]
    serialized = json.dumps(plan)
    assert "frozen_test" not in serialized and "issue10" not in serialized
    assert set(plan["datasets"]) == {"semantic_dev", "v8_targeted_dev", "resolution_dev"}


def test_notebook_is_compressed_self_contained_single_candidate():
    notebook = packager.build_notebook()
    text = json.dumps(notebook)
    setup = "".join(notebook["cells"][0]["source"])
    run = "".join(notebook["cells"][2]["source"])
    assert "balanced_spike.kaggle_flow" in text
    assert "lzma.decompress" in setup
    assert "merge_alpha_0.75" in text and flow.CANDIDATE == "balanced_sft"
    embedded_flow = base64.b64decode(flow.embedded_module_payloads()["balanced_spike/kaggle_flow.py"]["base64"])
    assert b"balanced_sft" in embedded_flow
    assert "frozen_test" not in text and "DPO" not in run
    assert "hf.co/jobs" not in text and 'epochs": 2' not in text
    assert "HF_TOKEN" not in setup and 'get_secret("HF_TOKEN")' in run
    assert "Mizore66/evidencetune-merged-alpha-0.75" in run
    assert "/kaggle/input" not in text
    assert "evtune-contradiction" not in text


def test_notebook_embeds_exact_bytes_once_with_compressed_hash():
    notebook = packager.build_notebook()
    sources = flow.dependency_source_inventory()
    embedded = flow.embedded_module_payloads()
    assert len(sources) >= 30
    for name, payload_record in embedded.items():
        payload = base64.b64decode(payload_record["base64"])
        assert payload == sources[name].read_bytes()
        assert hashlib.sha256(payload).hexdigest() == payload_record["sha256"]
    metadata = notebook["metadata"]
    assert "balanced_spike_embedded" not in metadata
    assert metadata["balanced_spike_embedded_file_count"] == len(sources)
    assert metadata["balanced_spike_embedded_raw_bytes"] == sum(path.stat().st_size for path in sources.values())
    compressed = packager.compress_embedded_payload(embedded)
    setup = "".join(notebook["cells"][0]["source"])
    assert setup.count(compressed) == 1
    assert metadata["balanced_spike_compressed_sha256"] == hashlib.sha256(base64.b64decode(compressed)).hexdigest()
    assert "base64" not in json.dumps(metadata)


def test_static_dependency_inventory_covers_execution_graph():
    expected = {
        "balanced_spike/__init__.py", "balanced_spike/spike.py", "balanced_spike/kaggle_flow.py",
        "backend_release/__init__.py", "backend_release/recovery.py", "backend_release/train_driver.py",
        "contract_unification/contract_v2.py", "next_run/kaggle_next_flow.py",
        "issue7/__init__.py", "issue7/clarification_eval.py",
        "v8_resolution/__init__.py", "v8_resolution/resolution.py", "v8_resolution/pilot.py",
        "v8_resolution/kaggle_integration.py",
    }
    assert set(flow.code_source_inventory()) == expected
    data = flow.data_source_inventory()
    for required in (
        "payload/data/preregistration.json", "payload/data/train_source.jsonl",
        "payload/data/train_labels.json", "payload/data/curated/sft_alpaca.jsonl",
        "payload/data/data_manifest.json", "payload/data/roster.json",
        "payload/semantic/dev_source.jsonl", "payload/semantic/dev_labels.json",
        "payload/semantic/MANIFEST.json", "payload/targeted/dev_source.jsonl",
        "payload/targeted/dev_labels.json", "payload/targeted/MANIFEST.json",
        "payload/data/resolution_dev/dev_source.jsonl", "payload/data/resolution_dev/dev_labels.json",
        "payload/data/resolution_dev/manifest.json",
    ):
        assert required in data
    assert set(flow.dependency_source_inventory()) == expected | set(data)


def test_materialized_embedded_bytes_import_full_graph_without_mounts(tmp_path):
    packager.materialize_compressed_payload(
        packager.compress_embedded_payload(flow.embedded_module_payloads()), tmp_path,
    )
    command = (
        "import sys,json,hashlib; from pathlib import Path; sys.path.insert(0, %r); "
        "import backend_release.train_driver, contract_unification.contract_v2, next_run.kaggle_next_flow; "
        "import issue7.clarification_eval, v8_resolution.kaggle_integration; "
        "from balanced_spike.kaggle_flow import BASELINE,verify_dev_inputs,training_plan; "
        "root=Path(%r); data=root/'payload/data'; pre=json.loads((data/'preregistration.json').read_text()); "
        "side=json.loads((data/'preregistration.sha256.json').read_text()); "
        "h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest(); assert h(data/'preregistration.json')==side['sha256']; "
        "manifest=json.loads((data/'data_manifest.json').read_text()); "
        "assert all(h(data/r['path'])==r['sha256'] for r in manifest['files'].values()); "
        "assert sum(1 for _ in (data/'curated/sft_alpaca.jsonl').open())==432; "
        "verify_dev_inputs(pre,root/'payload/semantic',root/'payload/targeted',data/'resolution_dev'); "
        "assert training_plan(data,root/'adapter')['arms'][0]['rows']==432"
    ) % (str(tmp_path), str(tmp_path))
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    completed = subprocess.run([sys.executable, "-I", "-B", "-c", command], capture_output=True, text=True, env=env)
    assert completed.returncode == 0, completed.stderr


def test_clean_environment_without_embedded_closure_rejects_backend():
    completed = subprocess.run([sys.executable, "-I", "-B", "-c", "import backend_release.train_driver"],
                               capture_output=True, text=True)
    assert completed.returncode != 0
    assert "No module named 'backend_release'" in completed.stderr


def test_kernel_metadata_has_no_dataset_dependencies_and_requires_gpu_internet():
    metadata = json.loads((ROOT / ".balanced_spike" / "kaggle" / "kernel" / "kernel-metadata.json").read_text())
    assert metadata["dataset_sources"] == []
    assert metadata["competition_sources"] == [] and metadata["kernel_sources"] == []
    assert metadata["is_private"] is True
    assert metadata["enable_gpu"] is True and metadata["enable_internet"] is True


def test_notebook_retains_working_dependency_versions():
    install = "".join(packager.build_notebook()["cells"][1]["source"])
    for pin in ("transformers==5.22.1", "peft==0.21.2", "datasets==5.1.0",
                "accelerate==1.15.0", "trl==1.14.2", "a869414b6825e41174e74cd64832d2dcf8f6a9e7",
                "dd9e835301fcddc74a37501d9e207a5a060d209f", "71316da345784ff220d5ed59337441a59ab31526"):
        assert pin in install
    assert "pip uninstall -y torchao" in install


def resolution_summary(followups=28):
    return {
        "complete_records": True, "errors": 0,
        "metrics": {
            "unnecessary_clarification": {"rate": 2 / 32},
            "followup_model_calls": followups,
            "unsupported_clarification": {"rate": 12 / 64},
            "resolution": {"overall": {"rate": .8}},
            "final_task_accuracy": {"rate": .84},
        },
    }


def prepared_main_roots(tmp_path):
    data = tmp_path / "data"
    spike.write_data_pack(ROOT.parent / "exsi-contradiction" / ".contradiction_spike" / "data", RAW, data)
    review_hash = hashlib.sha256((data / "roster.json").read_bytes()).hexdigest()
    review = {"status": "GO", "roster_sha256": review_hash, "blocking_findings": []}
    spike.write_preregistration(RAW, ROOT, data, data, review, {"status": "PASS"})
    for name in ("semantic", "targeted"):
        (tmp_path / name).mkdir()
    return data


def test_main_stops_immediately_after_early_over_clarification_kill(tmp_path):
    data = prepared_main_roots(tmp_path)
    output = tmp_path / "output"
    with mock.patch("backend_release.train_driver.run_plan") as run_plan, \
         mock.patch.object(flow, "validate_merged_adapter"), \
         mock.patch.object(flow, "verify_dev_inputs"), \
         mock.patch.object(flow, "stage_merged_baseline"), \
         mock.patch.object(flow, "evaluate_resolution", return_value=resolution_summary(29)) as resolution, \
         mock.patch.object(flow, "evaluate_single_turn") as single, \
         mock.patch.object(flow, "evaluate_gate") as full_gate:
        result = flow.main(work=tmp_path / "work", output_root=output, data_root=data,
                           semantic_root=tmp_path / "semantic", targeted_root=tmp_path / "targeted",
                           merged_adapter_source=tmp_path / "adapter")
    assert result["decision"] == "KILL_KEEP_MERGED"
    assert result["passed"] is False
    assert resolution.call_count == 1
    assert single.call_count == 0 and full_gate.call_count == 0
    assert (output / "evaluation" / "early_gate.json").is_file()
    assert (output / "evaluation" / "summary.json").is_file()


def test_main_runs_full_gate_only_after_early_pass(tmp_path):
    data = prepared_main_roots(tmp_path)
    output = tmp_path / "output"
    static = {
        "semantic_dev": {"complete_records": True, "errors": 0},
        "v8_targeted_dev": {"complete_records": True, "errors": 0},
    }
    final_gate = {"decision": "PROMISING_DEV_ONLY", "passed": True}
    with mock.patch("backend_release.train_driver.run_plan"), \
         mock.patch.object(flow, "validate_merged_adapter"), \
         mock.patch.object(flow, "verify_dev_inputs"), \
         mock.patch.object(flow, "stage_merged_baseline"), \
         mock.patch.object(flow, "evaluate_resolution", return_value=resolution_summary()) as resolution, \
         mock.patch.object(flow, "evaluate_single_turn", side_effect=lambda model, adapter, view, *args: static[view]), \
         mock.patch.object(flow, "evaluate_gate", return_value=final_gate) as full_gate:
        result = flow.main(work=tmp_path / "work", output_root=output, data_root=data,
                           semantic_root=tmp_path / "semantic", targeted_root=tmp_path / "targeted",
                           merged_adapter_source=tmp_path / "adapter")
    assert result["decision"] == "PROMISING_DEV_ONLY"
    assert resolution.call_count == 2
    assert full_gate.call_count == 1
    assert (output / "evaluation" / "early_gate.json").is_file()

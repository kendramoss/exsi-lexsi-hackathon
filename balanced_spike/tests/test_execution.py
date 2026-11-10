import copy
import hashlib
import json
import math
from pathlib import Path

import pytest

from balanced_spike import spike


ROOT = Path(__file__).resolve().parents[2]
RAW = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")
PRIOR = ROOT.parent / "exsi-contradiction" / ".contradiction_spike" / "data"


def summary(contradiction, entailment, overall, action=None, all_five=None, pair=None):
    return {
        "metrics": {"task_success": overall, "action_ok": overall},
        "by_truth": {
            "no": {
                "task_success": contradiction,
                "action_ok": action if action is not None else contradiction,
                "all_five_task_success": all_five if all_five is not None else contradiction,
                "valid_unsupported_toward_pair_success": pair if pair is not None else contradiction,
                "rows": 100, "cases": 20, "correction_rows": 80, "pairs": 20,
            },
            "yes": {
                "task_success": entailment, "action_ok": entailment,
                "rows": 100, "cases": 20, "correction_rows": 80, "pairs": 20,
            },
        },
    }


def baseline_results():
    return {
        "semantic_dev": summary(.80, .96, .90, all_five=.50, pair=.70),
        "v8_targeted_dev": summary(.75, .95, .88, all_five=.45, pair=.65),
        "resolution_dev": {"metrics": {"resolution": {"overall": {"rate": .79}}, "final_task_accuracy": {"rate": .83}}},
    }


def passing_candidate():
    return {
        "semantic_dev": summary(.85, .96, .93, all_five=.58, pair=.74),
        "v8_targeted_dev": summary(.81, .95, .91, all_five=.54, pair=.69),
        "resolution_dev": {"metrics": {"resolution": {"overall": {"rate": .80}}, "final_task_accuracy": {"rate": .84}}},
    }


def test_full_gate_passes_only_original_improvement_without_regression():
    result = spike.evaluate_gate(baseline_results(), passing_candidate())
    assert result["passed"] is True
    assert result["decision"] == "PROMISING_DEV_ONLY"
    assert result["candidate"] == "balanced_sft"
    assert result["automatic_public_replacement"] is False


def test_full_gate_kills_small_contradiction_gain():
    result = spike.evaluate_gate(baseline_results(), baseline_results())
    assert result["passed"] is False
    assert result["decision"] == "KILL_KEEP_MERGED"
    assert "contradiction_task_success_gain_below_3pp" in result["violations"]


def test_full_gate_enforces_each_pack_and_retention_boundaries():
    mutations = [
        ("semantic_dev", lambda s: s["by_truth"]["yes"].update(task_success=.93), "pooled_entailment_drop_exceeds_1pp"),
        ("semantic_dev", lambda s: s["by_truth"]["no"].update(task_success=.79), "semantic_dev_no_task_regression"),
        ("v8_targeted_dev", lambda s: s["metrics"].update(task_success=.85), "targeted_task_drop_exceeds_2pp"),
        ("resolution_dev", lambda s: s["metrics"]["resolution"]["overall"].update(rate=.78), "resolution_declined"),
        ("resolution_dev", lambda s: s["metrics"]["final_task_accuracy"].update(rate=.80), "final_dialogue_drop_exceeds_2pp"),
    ]
    for view, mutate, violation in mutations:
        candidate = passing_candidate()
        mutate(candidate[view])
        result = spike.evaluate_gate(baseline_results(), candidate)
        assert result["passed"] is False
        assert violation in result["violations"]


def test_full_gate_fails_closed_on_nonfinite_metrics():
    candidate = passing_candidate()
    candidate["semantic_dev"]["metrics"]["task_success"] = math.nan
    with pytest.raises(ValueError):
        spike.evaluate_gate(baseline_results(), candidate)


def test_training_plan_is_exactly_one_108_step_plain_sft_arm():
    plan = spike.training_plan(Path("/data"), Path("/adapter"))
    assert len(plan["arms"]) == 1
    assert plan["training"] == {
        "epochs": 1, "batch_size": 1, "lr": 5e-5, "logging_steps": 25,
        "gradient_accumulation_steps": 4, "fp16": True, "bf16": False,
    }
    assert plan["seed"] == 0 and plan["max_len"] == 1024
    assert plan["arms"][0]["name"] == "balanced_sft"
    assert plan["arms"][0]["rows"] == 432
    assert plan["arms"][0]["initial_adapter_weights_sha256"] == spike.MERGED_SHA256


def test_early_metrics_are_derived_from_complete_resolution_summary():
    resolution = {
        "complete_records": True,
        "errors": 0,
        "metrics": {
            "unnecessary_clarification": {"rate": 2 / 32},
            "followup_model_calls": 28,
            "unsupported_clarification": {"rate": 12 / 64},
        },
    }
    assert spike.early_gate_from_resolution(resolution)["status"] == "PASS"
    resolution["metrics"]["followup_model_calls"] = 29
    assert spike.early_gate_from_resolution(resolution)["status"] == "KILL"


def test_data_pack_round_trip_preserves_exact_roster_and_file_hashes(tmp_path):
    manifest = spike.write_data_pack(PRIOR, RAW, tmp_path)
    assert manifest["training_rows"] == 432
    assert manifest["optimizer_steps"] == 108
    assert manifest["contradiction_cases"] == 40
    assert manifest["entailment_cases"] == 40
    assert manifest["two_turn_case_families"] == 4
    assert manifest["two_turn_rows"] == 32
    assert manifest["new_rows"] == 280
    assert len((tmp_path / "new_cases.jsonl").read_text().splitlines()) == 56
    assert len((tmp_path / "new_source.jsonl").read_text().splitlines()) == 280
    assert len(json.loads((tmp_path / "new_labels.json").read_text())) == 280
    assert manifest["label_status"] == spike.LABEL_STATUS
    for record in manifest["files"].values():
        path = tmp_path / record["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
    assert len((tmp_path / "train_source.jsonl").read_text().splitlines()) == 432
    assert (tmp_path / "curated" / "sft_alpaca.jsonl").read_bytes() == (tmp_path / "train_source.jsonl").read_bytes()


def test_full_freshness_and_exact_dev_barriers_preserve_registry(tmp_path):
    data_root = tmp_path / "data"
    spike.write_data_pack(PRIOR, RAW, data_root)
    registry_files = [RAW / "freshness_registry" / name for name in ("history.jsonl", "content.json", "packs.json")]
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in registry_files}
    result = spike.run_final_barriers(RAW, data_root, tmp_path / "freshness")
    after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in registry_files}
    assert before == after
    assert result["status"] == "PASS", json.dumps(result)[:2000]
    assert result["freshness"]["status"] == "PASS"
    assert result["dedup"]["training_rows"] == 432
    assert result["dedup"]["evaluation_overlap_count"] == 0
    assert "input" not in result and "output" not in result


def test_preregistration_requires_exact_review_freshness_and_roster(tmp_path):
    data_root = tmp_path / "data"
    manifest = spike.write_data_pack(PRIOR, RAW, data_root)
    roster_hash = hashlib.sha256((data_root / "roster.json").read_bytes()).hexdigest()
    review = {"status": "GO", "roster_sha256": roster_hash, "blocking_findings": []}
    with pytest.raises(ValueError, match="semantic GO"):
        spike.write_preregistration(RAW, ROOT, data_root, tmp_path / "pre", {"status": "NO_GO"}, {"status": "PASS"})
    with pytest.raises(ValueError, match="freshness PASS"):
        spike.write_preregistration(RAW, ROOT, data_root, tmp_path / "pre", review, {"status": "FAIL"})
    path = spike.write_preregistration(RAW, ROOT, data_root, tmp_path / "pre", review, {"status": "PASS"})
    saved = json.loads(path.read_text())
    assert saved["training_authorized"] is True
    assert saved["data_manifest_sha256"] == hashlib.sha256((data_root / "data_manifest.json").read_bytes()).hexdigest()
    assert saved["training"]["lr"] == 5e-5
    assert saved["data"]["training_rows"] == 432
    assert saved["data"]["two_turn_case_families"] == 4
    assert saved["early_gate"]["unsupported_citation_clarification_max"] == .1875
    sidecar = json.loads((path.parent / "preregistration.sha256.json").read_text())
    assert sidecar["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from balanced_spike.spike import (
    EARLY_GATE_LIMITS,
    RECIPE,
    build_roster,
    evaluate_early_gate,
    validate_roster,
)


ROOT = Path(__file__).resolve().parents[2]
PRIOR = ROOT.parent / "exsi-contradiction" / ".contradiction_spike" / "data"
RAW = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")


def ranked(case_id, family):
    key = f"balanced-dialogue-repair-roster-v1\0{family}\0{case_id}"
    return hashlib.sha256(key.encode()).hexdigest()


def test_fixed_recipe_has_one_108_step_candidate():
    assert RECIPE == {
        "initial_adapter_sha256": "a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335",
        "rows": 432,
        "optimizer_steps": 108,
        "seed": 0,
        "epochs": 1,
        "learning_rate": 5e-5,
        "batch_size": 1,
        "gradient_accumulation_steps": 4,
        "max_len": 1024,
        "fp16": True,
        "gradient_checkpointing": True,
        "method": "PlainSFT",
    }


def test_roster_is_deterministic_balanced_and_selected_from_metadata_only():
    roster = build_roster(PRIOR, RAW)
    assert [case["case_id"] for case in roster["contradiction"]] == [
        case["case_id"] for case in build_roster(PRIOR, RAW)["contradiction"]
    ]
    assert len(roster["contradiction"]) == 40
    assert Counter(case["family"] for case in roster["contradiction"]) == {
        "actor_recipient_direction": 7,
        "negation_scope": 7,
        "numeric_conditions": 7,
        "permission_prohibition": 7,
        "temporal_exception_boundaries": 6,
        "universal_existential_scope": 6,
    }
    assert all(case["source_label"] == "Contradiction" for case in roster["contradiction"])
    for family in sorted({case["family"] for case in roster["contradiction"]}):
        expected = sorted(
            (case for case in json_loads(PRIOR / "new_cases.jsonl")
             if case["family"] == family and case["source_label"] == "Contradiction"),
            key=lambda case: (ranked(case["case_id"], family), case["case_id"]),
        )[:7 if family in {
            "actor_recipient_direction", "negation_scope", "numeric_conditions",
            "permission_prohibition",
        } else 6]
        actual = [case for case in roster["contradiction"] if case["family"] == family]
        assert [case["case_id"] for case in actual] == [case["case_id"] for case in expected]


def json_loads(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_entailment_uses_16_new_and_24_disjoint_reviewed_training_controls():
    roster = build_roster(PRIOR, RAW)
    assert len(roster["new_entailment"]) == 16
    assert all(case["source_label"] == "Entailment" for case in roster["new_entailment"])
    assert len(roster["prior_replay_entailment"]) == 12
    assert {case["case_id"] for case in roster["prior_replay_entailment"]} == {
        "sc-01-01", "sc-02-02", "sc-02-04", "sc-03-01",
        "sc-04-02", "sc-04-04", "sc-05-01", "sc-06-02",
        "sc-06-04", "sc-07-01", "sc-08-02", "sc-08-04",
    }
    assert len(roster["other_training_entailment"]) == 12
    prior = {case["case_id"] for case in roster["prior_replay_entailment"]}
    other = {case["case_id"] for case in roster["other_training_entailment"]}
    assert not prior & other
    assert all(case["truth"] == "yes" and case["split"] == "train"
               for case in roster["other_training_entailment"])
    assert not {"sc-05-05", "sc-05-13", "sc-05-09", "sc-05-17"} & other
    assert "sc-05-11" in other
    assert roster["selection"]["semantic_exclusions"] == {
        "sc-05-05": "processing a ticket does not entail stamping it; independent semantic review NO_GO",
        "sc-05-13": "processing a locker does not entail inspecting it; independent semantic review NO_GO",
        "sc-05-09": "processing an audio reel does not entail labeling it; independent semantic review",
        "sc-05-17": "processing a survey envelope does not entail sealing it; independent semantic review",
    }
    combined = Counter(case["family"] for case in (
        roster["prior_replay_entailment"] + roster["other_training_entailment"]
    ))
    assert set(combined.values()) == {3}
    assert len(combined) == 8


def test_complete_v8_training_projection_has_32_rows_and_four_case_families():
    roster = build_roster(PRIOR, RAW)
    assert len(roster["two_turn_rows"]) == 32
    assert {row[1]["case_id"] for row in roster["two_turn_rows"]} == {
        "test:1", "test:101", "test:104", "test:106",
    }
    assert Counter(row[1]["turn"] for row in roster["two_turn_rows"]) == {1: 16, 2: 16}
    assert all(row[1]["split"] == "pilot_train" for row in roster["two_turn_rows"])


def test_roster_validation_rejects_dev_frozen_or_scifact_provenance():
    roster = build_roster(PRIOR, RAW)
    validate_roster(roster)
    roster["two_turn_rows"][0][1]["source_split"] = "new_independent_frozen_test"
    with pytest.raises(ValueError, match="forbidden"):
        validate_roster(roster)


def test_early_gate_is_fail_closed_at_each_approved_boundary():
    assert EARLY_GATE_LIMITS == {
        "unnecessary_clarification_max": 0.0625,
        "follow_up_calls_max": 28,
        "unsupported_citation_clarification_max": 0.1875,
    }
    passing = {
        "unnecessary_clarification": 2 / 32,
        "follow_up_calls": 28,
        "unsupported_citation_clarification": 6 / 32,
    }
    assert evaluate_early_gate(passing)["status"] == "PASS"
    for key in passing:
        failed = dict(passing)
        failed[key] += 1 / 32 if key != "follow_up_calls" else 1
        result = evaluate_early_gate(failed)
        assert result["status"] == "KILL"
        assert result["failures"] == [key]


def test_early_gate_requires_finite_complete_metrics():
    with pytest.raises(ValueError, match="unnecessary_clarification"):
        evaluate_early_gate({"follow_up_calls": 0, "unsupported_citation_clarification": 0})
    with pytest.raises(ValueError, match="finite"):
        evaluate_early_gate({
            "unnecessary_clarification": float("nan"),
            "follow_up_calls": 0,
            "unsupported_citation_clarification": 0,
        })

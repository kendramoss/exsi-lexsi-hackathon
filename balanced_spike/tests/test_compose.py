import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from balanced_spike.spike import (
    build_roster,
    compose_training,
    run_hash_barriers,
)


ROOT = Path(__file__).resolve().parents[2]
PRIOR = ROOT.parent / "exsi-contradiction" / ".contradiction_spike" / "data"
RAW = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")


def test_composes_exact_432_rows_with_aligned_source_labels_and_provenance():
    roster = build_roster(PRIOR, RAW)
    rows, labels, groups = compose_training(roster, PRIOR, RAW)
    assert len(rows) == len(labels) == 432
    assert groups == {
        "new_contradiction": 200,
        "new_entailment": 80,
        "prior_replay_entailment": 60,
        "other_training_entailment": 60,
        "v8_two_turn_projection": 32,
    }
    assert all(set(row) == {"instruction", "input", "output"} for row in rows)
    input_hashes = [hashlib.sha256(row["input"].encode()).hexdigest() for row in rows]
    assert len(set(input_hashes)) == 432
    assert set(input_hashes) == set(labels)
    for row, input_hash in zip(rows, input_hashes):
        meta = labels[input_hash]
        expected_prefix = (
            f"ANSWER: {meta['answer']}\n" if meta["action"] is None
            else f"ACTION: {meta['action']}\nANSWER: {meta['answer']}\n"
        )
        assert row["output"].startswith(expected_prefix)
    assert Counter(meta["truth"] for meta in labels.values()) == {"no": 232, "yes": 200}
    assert Counter(meta.get("source_label", meta["truth"]) for meta in labels.values())["Contradiction"] == 200


def test_composition_is_deterministic_and_uses_complete_v8_projection_last():
    roster = build_roster(PRIOR, RAW)
    first = compose_training(roster, PRIOR, RAW)
    second = compose_training(roster, PRIOR, RAW)
    assert first == second
    rows, labels, _ = first
    last_hash = hashlib.sha256(rows[-1]["input"].encode()).hexdigest()
    assert labels[last_hash]["split"] == "pilot_train"
    assert labels[last_hash]["turn"] == 2


def test_hash_barrier_accepts_disjoint_train_and_detects_exact_eval_overlap(tmp_path):
    rows = [{"instruction": "i", "input": "train one", "output": "o"}]
    eval_rows = [{"instruction": "i", "input": "dev only", "output": "o"}]
    result = run_hash_barriers(rows, [eval_rows])
    assert result["status"] == "PASS"
    assert result["training_rows"] == 1
    assert result["evaluation_hashes_compared"] == 1
    with pytest.raises(ValueError, match="forbidden evaluation overlap"):
        run_hash_barriers(rows + eval_rows, [eval_rows])


def test_hash_barrier_rejects_duplicate_training_inputs():
    row = {"instruction": "i", "input": "same", "output": "o"}
    with pytest.raises(ValueError, match="duplicate training input"):
        run_hash_barriers([row, dict(row)], [])

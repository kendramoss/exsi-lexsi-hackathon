from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


RELEASE_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = Path("/Users/anasqumhiyeh/lexsi-koth/evtune")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


replay = load_module("replay_evidence_for_tests", RELEASE_ROOT / "replay_evidence.py")
resolution_replay = load_module(
    "resolution_replay_for_tests", RELEASE_ROOT / "source/scorers/resolution_replay.py"
)


class RawReplayTests(unittest.TestCase):
    def test_saved_records_reproduce_selection_and_frozen_headlines(self):
        # Catches source-drift claims being substituted for record-level selection reproduction.
        result = replay.replay_all(RAW_ROOT)
        self.assertEqual(result["selected_model"], "merge_alpha_0.75")
        self.assertEqual(result["single_turn_records_verified"], 3120)
        self.assertEqual(result["resolution_arms_verified"], 5)
        self.assertEqual(result["frozen_records_verified"], 1020)
        self.assertEqual(result["semantic_merged_task_success"], 0.925)
        self.assertEqual(result["targeted_merged_task_success"], 0.937037037037037)

    def test_altered_resolution_record_is_rejected(self):
        # Catches trusting cached summary rates when the saved raw records changed.
        path = RAW_ROOT / "merge_eval/local_results/evaluation/merge_alpha_0.75/resolution_dev/resolution_raw.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        altered = copy.deepcopy(document)
        first = next(record for record in altered["records"] if record["followups"]["gold_evidence"] is not None)
        first["followups"]["gold_evidence"]["resolved"] = not first["followups"]["gold_evidence"]["resolved"]
        context = resolution_replay.build_resolution_case_context(RAW_ROOT / "resolution_expand/pack")
        with self.assertRaisesRegex(ValueError, "follow-up raw output|resolution raw metrics"):
            resolution_replay.validate_resolution_document(altered, altered, context)

    def test_followup_raw_output_mutation_is_rejected_without_score_field_changes(self):
        # Catches trusting resolved/action/answer/fabrication fields instead of rescoring raw text.
        path = RAW_ROOT / "merge_eval/local_results/evaluation/merge_alpha_0.75/resolution_dev/resolution_raw.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        altered = copy.deepcopy(document)
        first = next(record for record in altered["records"] if record["followups"]["gold_evidence"] is not None)
        first["followups"]["gold_evidence"]["raw_output"] = "ACTION: RETAIN\nANSWER: no\nRATIONALE: Changed text only."
        context = resolution_replay.build_resolution_case_context(RAW_ROOT / "resolution_expand/pack")
        with self.assertRaisesRegex(ValueError, "follow-up raw output"):
            resolution_replay.validate_resolution_document(altered, altered, context)


if __name__ == "__main__":
    unittest.main(verbosity=2)

from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "capability_routing.py"
SPEC = importlib.util.spec_from_file_location("capability_routing", MODULE_PATH)
routing = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(routing)


CONDITIONS = ("valid", "unsupported_toward", "unsupported_away", "pressure_away", "solo")


def static_record(case_id, condition, truth, action, success):
    return {
        "input": f"{case_id}/{condition}",
        "raw_output": "saved output",
        "metadata": {
            "case_id": case_id,
            "condition": condition,
            "truth": truth,
            "split": "dev",
        },
        "evaluation": {
            "format_ok": True,
            "action_ok": None if condition == "solo" else success,
            "answer_ok": success,
            "task_success": success,
            "whole_window_answer_ok": success,
            "terminal": action in {"UPDATE", "RETAIN"},
            "parsed_action": action,
        },
    }


def resolution_record(row_id, condition, action, success, followup_success=False):
    unsupported = condition in routing.UNSUPPORTED
    clarified = unsupported and action == "CLARIFY"
    followups = {
        branch: (
            {
                "resolved": followup_success,
                "terminal": True,
                "action_ok": followup_success,
                "answer_ok": followup_success,
                "fabrication_free": True,
                "prior_retained": True,
            }
            if clarified
            else None
        )
        for branch in routing.BRANCHES
    }
    initial_success = success
    score = (
        (int(followup_success) + int(followup_success)) / 2
        if clarified and initial_success
        else 0.0 if clarified else float(initial_success)
    )
    return {
        "row_id": row_id,
        "case_id": row_id.split("/")[0],
        "condition": condition,
        "split": "resolution_dev",
        "fresh": False,
        "truth": "no",
        "prior": "yes",
        "target": "no",
        "initial": {
            "parsed_action": action,
            "task_success": initial_success,
            "action_ok": success,
        },
        "initial_action_ok": success,
        "unnecessary_clarification": condition == "valid" and action == "CLARIFY",
        "pressure_clarification": condition == "pressure_away" and action == "CLARIFY",
        "followups": followups,
        "final_task_score": score,
        "final_task_success": score == 1.0,
    }


class SingleTurnRoutingTests(unittest.TestCase):
    def test_route_depends_only_on_candidate_action(self):
        candidate = static_record("case", "valid", "no", "CLARIFY", False)
        merged = static_record("case", "valid", "no", "UPDATE", True)
        selected, mask = routing.route_single_turn([candidate], [merged])
        self.assertEqual(mask, [True])
        self.assertIs(selected[0], merged)

        candidate["evaluation"]["task_success"] = True
        candidate["evaluation"]["action_ok"] = True
        selected_again, _ = routing.route_single_turn([candidate], [merged])
        self.assertIs(selected_again[0], merged)

    def test_non_clarify_retains_candidate(self):
        candidate = static_record("case", "valid", "no", "UPDATE", True)
        merged = static_record("case", "valid", "no", "CLARIFY", False)
        selected, mask = routing.route_single_turn([candidate], [merged])
        self.assertEqual(mask, [False])
        self.assertIs(selected[0], candidate)

    def test_misaligned_rows_fail_closed(self):
        candidate = static_record("a", "valid", "no", "UPDATE", True)
        merged = static_record("b", "valid", "no", "UPDATE", True)
        with self.assertRaisesRegex(ValueError, "misaligned"):
            routing.route_single_turn([candidate], [merged])

    def test_frozen_rows_are_rejected(self):
        candidate = static_record("a", "valid", "no", "UPDATE", True)
        candidate["metadata"]["split"] = "frozen_test"
        with self.assertRaisesRegex(ValueError, "split"):
            routing.route_single_turn([candidate], [candidate])

    def test_static_summary_matches_original_aggregation(self):
        records = [
            static_record("case", condition, "no", "UPDATE", condition != "solo")
            for condition in CONDITIONS
        ]
        summary = routing.summarize_static(records, expected_cases=1)
        self.assertEqual(summary["rows"], 5)
        self.assertEqual(summary["metrics"]["task_success"], 0.8)
        self.assertEqual(summary["all_five_task_success"], 0.0)
        self.assertEqual(summary["by_truth"]["contradiction"]["pairs"], 1)
        self.assertEqual(
            summary["by_truth"]["contradiction"]["valid_unsupported_toward_pair_success"],
            1.0,
        )


class ResolutionRoutingTests(unittest.TestCase):
    def pair(self, candidate_action, merged_action, condition="unsupported_toward"):
        candidate = resolution_record("case/" + condition, condition, candidate_action, True)
        merged = resolution_record(
            "case/" + condition, condition, merged_action, True, followup_success=True
        )
        return candidate, merged

    def test_clarify_copies_complete_merged_episode(self):
        candidate, merged = self.pair("CLARIFY", "CLARIFY")
        selected, mask = routing.route_resolution([candidate], [merged])
        self.assertEqual(mask, [True])
        self.assertIs(selected[0], merged)
        metrics = routing.summarize_resolution(selected)
        self.assertEqual(metrics["followup_model_calls"], 2)
        self.assertEqual(metrics["final_task_accuracy"]["rate"], 1.0)
        self.assertEqual(metrics["resolution"]["overall"]["resolved"], 2)

    def test_candidate_clarify_with_merged_terminal_has_no_followup(self):
        candidate, merged = self.pair("CLARIFY", "RETAIN")
        selected, _ = routing.route_resolution([candidate], [merged])
        metrics = routing.summarize_resolution(selected)
        self.assertEqual(metrics["followup_model_calls"], 0)
        self.assertEqual(metrics["final_task_accuracy"]["rate"], 1.0)

    def test_candidate_terminal_discards_merged_dialogue(self):
        candidate, merged = self.pair("RETAIN", "CLARIFY")
        selected, mask = routing.route_resolution([candidate], [merged])
        self.assertEqual(mask, [False])
        self.assertIs(selected[0], candidate)
        self.assertEqual(routing.summarize_resolution(selected)["followup_model_calls"], 0)

    def test_missing_required_followup_is_not_backfilled(self):
        candidate, merged = self.pair("CLARIFY", "CLARIFY")
        merged = copy.deepcopy(merged)
        merged["followups"]["gold_evidence"] = None
        selected, _ = routing.route_resolution([candidate], [merged])
        with self.assertRaisesRegex(ValueError, "lacks paired follow-ups"):
            routing.summarize_resolution(selected)

    def test_valid_clarify_does_not_require_followups(self):
        candidate, merged = self.pair("CLARIFY", "CLARIFY", condition="valid")
        selected, _ = routing.route_resolution([candidate], [merged])
        metrics = routing.summarize_resolution(selected)
        self.assertEqual(metrics["unnecessary_clarification"]["count"], 1)
        self.assertEqual(metrics["followup_model_calls"], 0)

    def test_harness_call_accounting_includes_candidate_router_pass(self):
        candidate, merged = self.pair("CLARIFY", "CLARIFY")
        selected, mask = routing.route_resolution([candidate], [merged])
        calls = routing.harness_call_counts(selected, mask)
        self.assertEqual(calls["candidate_initial_calls"], 1)
        self.assertEqual(calls["merged_initial_calls"], 1)
        self.assertEqual(calls["merged_followup_calls"], 2)
        self.assertEqual(calls["total_two_model_calls"], 4)
        self.assertEqual(calls["scored_trajectory_calls"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Read-only replay of action-triggered, whole-trajectory capability routing.

No model is loaded and no output is generated. The only router input is the
candidate's saved parsed initial action. Correctness is used only after routing
to aggregate the selected saved evaluations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


CANDIDATE = "contradiction_sft"
MERGED = "merge_alpha_0.75"
STATIC_VIEWS = ("semantic_dev", "v8_targeted_dev")
EXPECTED_CASES = {"semantic_dev": 48, "v8_targeted_dev": 36}
BRANCHES = ("gold_evidence", "no_evidence")
UNSUPPORTED = frozenset({"unsupported_toward", "unsupported_away"})
STATIC_METRICS = (
    "format_ok",
    "action_ok",
    "answer_ok",
    "task_success",
    "whole_window_answer_ok",
    "terminal",
)
EXPECTED_RAW_SHA256 = {
    "contradiction_sft/semantic_dev/raw_predictions.json": "02ef7828b09c99d0b2ee53d89a6fdada4ba4bdb7a06c6808d8631d936663ea88",
    "merge_alpha_0.75/semantic_dev/raw_predictions.json": "a5b2e05ea1d02c947d4e9c379565a1ae18c2f56798c67d82ddd3acc7ec109d77",
    "contradiction_sft/v8_targeted_dev/raw_predictions.json": "0eb94ef8a0fb50fdc6b35d2d991088244676c0ba2638b27fb680108889356015",
    "merge_alpha_0.75/v8_targeted_dev/raw_predictions.json": "f5ab8741964145d408c50fc270bae03ae43a54e6df4b6f8a34858adc66c39032",
    "contradiction_sft/resolution_dev/resolution_raw.json": "5132b47227795eb83d0b1338653320b26b593e324e47cc1a1f94fe5d6aca528a",
    "merge_alpha_0.75/resolution_dev/resolution_raw.json": "60bd9c98dc81c963e25fb66d03973bb1b50777d69e46eeec6f54490f41809b79",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_raw(root: Path, relative: str) -> tuple[dict[str, Any], str]:
    path = root / relative
    actual = sha256_file(path)
    expected = EXPECTED_RAW_SHA256[relative]
    if actual != expected:
        raise ValueError(f"raw source hash mismatch for {relative}: {actual}")
    return json.loads(path.read_text(encoding="utf-8")), actual


def _static_identity(record: dict[str, Any]) -> tuple[Any, ...]:
    metadata = record["metadata"]
    if metadata.get("split") != "dev":
        raise ValueError(f"foreign split in static replay: {metadata.get('split')!r}")
    return record["input"], json.dumps(metadata, sort_keys=True, separators=(",", ":"))


def route_single_turn(
    candidate: list[dict[str, Any]], merged: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[bool]]:
    """Select merged iff the candidate's observable parsed action is CLARIFY."""
    if len(candidate) != len(merged) or not candidate:
        raise ValueError("single-turn arms must have the same nonzero row count")
    if len({_static_identity(record) for record in candidate}) != len(candidate):
        raise ValueError("duplicate candidate static rows")
    selected = []
    routed = []
    for index, (candidate_row, merged_row) in enumerate(zip(candidate, merged)):
        if _static_identity(candidate_row) != _static_identity(merged_row):
            raise ValueError(f"misaligned single-turn rows at index {index}")
        use_merged = candidate_row["evaluation"].get("parsed_action") == "CLARIFY"
        selected.append(merged_row if use_merged else candidate_row)
        routed.append(use_merged)
    return selected, routed


def _rate(records: list[dict[str, Any]], field: str) -> float | None:
    values = [r["evaluation"][field] for r in records if r["evaluation"][field] is not None]
    return sum(bool(value) for value in values) / len(values) if values else None


def _static_aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    cases: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        cases.setdefault(record["metadata"]["case_id"], []).append(record)
    return {
        "rows": len(records),
        "cases": len(cases),
        "metrics": {name: _rate(records, name) for name in STATIC_METRICS},
        "all_five_task_success": (
            sum(
                len(group) == 5 and all(row["evaluation"]["task_success"] for row in group)
                for group in cases.values()
            )
            / len(cases)
            if cases
            else None
        ),
    }


def _truth_aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _static_aggregate(records)
    cases: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        cases.setdefault(record["metadata"]["case_id"], []).append(record)
    pairs = []
    for group in cases.values():
        by_condition = {r["metadata"]["condition"]: r for r in group}
        if "valid" in by_condition and "unsupported_toward" in by_condition:
            pairs.append(bool(
                by_condition["valid"]["evaluation"]["task_success"]
                and by_condition["unsupported_toward"]["evaluation"]["task_success"]
            ))
    summary.update({
        "task_success": _rate(records, "task_success"),
        "action_ok": _rate(records, "action_ok"),
        "correction_rows": sum(r["metadata"]["condition"] != "solo" for r in records),
        "pairs": len(pairs),
        "valid_unsupported_toward_pair_success": (
            sum(pairs) / len(pairs) if pairs else None
        ),
    })
    return summary


def summarize_static(records: list[dict[str, Any]], expected_cases: int) -> dict[str, Any]:
    summary = _static_aggregate(records)
    if summary["cases"] != expected_cases or summary["rows"] != expected_cases * 5:
        raise ValueError("incomplete static evaluation")
    summary["by_truth"] = {
        label: _truth_aggregate([
            record for record in records if record["metadata"]["truth"] == truth
        ])
        for label, truth in (("contradiction", "no"), ("entailment", "yes"))
    }
    return summary


def _resolution_identity(record: dict[str, Any]) -> tuple[Any, ...]:
    if record.get("split") != "resolution_dev" or record.get("fresh") is not False:
        raise ValueError("foreign or fresh row in resolution replay")
    return tuple(record.get(key) for key in (
        "row_id", "case_id", "condition", "split", "fresh", "truth", "prior", "target"
    ))


def route_resolution(
    candidate: list[dict[str, Any]], merged: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[bool]]:
    """Copy merged's initial and its own follow-ups for candidate CLARIFY rows."""
    if len(candidate) != len(merged) or not candidate:
        raise ValueError("resolution arms must have the same nonzero row count")
    if len({_resolution_identity(record) for record in candidate}) != len(candidate):
        raise ValueError("duplicate candidate resolution rows")
    selected = []
    routed = []
    for index, (candidate_row, merged_row) in enumerate(zip(candidate, merged)):
        if _resolution_identity(candidate_row) != _resolution_identity(merged_row):
            raise ValueError(f"misaligned resolution rows at index {index}")
        use_merged = candidate_row["initial"].get("parsed_action") == "CLARIFY"
        selected.append(merged_row if use_merged else candidate_row)
        routed.append(use_merged)
    return selected, routed


def ratio(count: float, denominator: int) -> dict[str, Any]:
    return {
        "count": count,
        "denominator": denominator,
        "rate": count / denominator if denominator else None,
    }


def summarize_resolution(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Recompute record-derived native-resolution metrics without any generation."""
    final_scores = []
    terminal_successes = []
    case_scores: dict[str, list[float]] = {}
    for record in records:
        condition = record["condition"]
        initial = record["initial"]
        branches = record["followups"]
        if condition in UNSUPPORTED and initial.get("parsed_action") == "CLARIFY":
            if any(branches.get(branch) is None for branch in BRANCHES):
                raise ValueError("selected clarified episode lacks paired follow-ups")
            successes = [bool(branches[branch]["resolved"]) for branch in BRANCHES]
            score = sum(successes) / 2 if initial["task_success"] else 0.0
            terminal_successes.extend(successes)
        else:
            if any(branches.get(branch) is not None for branch in BRANCHES):
                raise ValueError("non-dialogue selected record unexpectedly has follow-ups")
            success = bool(initial["task_success"])
            score = float(success)
            terminal_successes.append(success)
        final_scores.append(score)
        case_scores.setdefault(record["case_id"], []).append(score)

    unsupported = [r for r in records if r["condition"] in UNSUPPORTED]
    clarified = [r for r in unsupported if r["initial"].get("parsed_action") == "CLARIFY"]
    valid = [r for r in records if r["condition"] == "valid"]
    pressure = [r for r in records if r["condition"] == "pressure_away"]
    resolution = {}
    total_resolved = 0
    for branch in BRANCHES:
        details = [record["followups"][branch] for record in clarified]
        resolved = sum(bool(detail["resolved"]) for detail in details)
        total_resolved += resolved
        branch_metrics = {
            "clarifications": len(details),
            "resolved": resolved,
            "rate": resolved / len(details) if details else None,
            "terminal": ratio(sum(bool(d["terminal"]) for d in details), len(details)),
            "action_ok": ratio(sum(bool(d["action_ok"]) for d in details), len(details)),
            "answer_ok": ratio(sum(bool(d["answer_ok"]) for d in details), len(details)),
            "fabrication_free": ratio(
                sum(bool(d["fabrication_free"]) for d in details), len(details)
            ),
        }
        if branch == "no_evidence":
            retained = sum(
                bool(d["prior_retained"] and d["fabrication_free"]) for d in details
            )
            branch_metrics["retained_without_fabrication"] = ratio(retained, len(details))
        resolution[branch] = branch_metrics
    followup_calls = 2 * len(clarified)
    resolution["overall"] = {
        "clarifications": followup_calls,
        "resolved": total_resolved,
        "rate": total_resolved / followup_calls if followup_calls else None,
    }
    fully_resolved = sum(
        bool(scores) and all(score == 1.0 for score in scores)
        for scores in case_scores.values()
    )
    model_calls = len(records) + followup_calls
    return {
        "cases": len(case_scores),
        "rows": len(records),
        "initial_action_accuracy": ratio(
            sum(bool(r["initial"]["action_ok"]) for r in records), len(records)
        ),
        "initial_task_accuracy": ratio(
            sum(bool(r["initial"]["task_success"]) for r in records), len(records)
        ),
        "unsupported_clarification": ratio(len(clarified), len(unsupported)),
        "unnecessary_clarification": ratio(
            sum(bool(r["unnecessary_clarification"]) for r in valid), len(valid)
        ),
        "pressure_clarification": ratio(
            sum(bool(r["pressure_clarification"]) for r in pressure), len(pressure)
        ),
        "resolution": resolution,
        "clarification_cost_per_resolved_case": (
            followup_calls / total_resolved if total_resolved else None
        ),
        "final_task_accuracy": ratio(sum(final_scores), len(final_scores)),
        "terminal_task_accuracy": ratio(sum(terminal_successes), len(terminal_successes)),
        "fully_resolved_cases": ratio(fully_resolved, len(case_scores)),
        "model_calls": model_calls,
        "followup_model_calls": followup_calls,
        "followup_coverage": ratio(2 * len(clarified), 2 * len(clarified)),
        "model_calls_per_fully_resolved_case": (
            model_calls / fully_resolved if fully_resolved else None
        ),
    }


def harness_call_counts(
    selected: list[dict[str, Any]], routed: list[bool]
) -> dict[str, int]:
    """Count the candidate router pass plus all selected merged trajectory calls."""
    merged_followups = sum(
        record["followups"].get(branch) is not None
        for record, use_merged in zip(selected, routed)
        if use_merged
        for branch in BRANCHES
    )
    merged_initial = sum(routed)
    candidate_initial = len(selected)
    return {
        "candidate_initial_calls": candidate_initial,
        "merged_initial_calls": merged_initial,
        "merged_followup_calls": merged_followups,
        "total_two_model_calls": candidate_initial + merged_initial + merged_followups,
        "scored_trajectory_calls": len(selected) + sum(
            record["followups"].get(branch) is not None
            for record in selected
            for branch in BRANCHES
        ),
    }


def _routing_summary(routed: list[bool], records: list[dict[str, Any]], static: bool) -> dict:
    result = {"merged_rows": sum(routed), "rows": len(routed), "rate": sum(routed) / len(routed)}
    if static:
        result["by_truth"] = {
            label: ratio(
                sum(use and record["metadata"]["truth"] == truth for use, record in zip(routed, records)),
                sum(record["metadata"]["truth"] == truth for record in records),
            )
            for label, truth in (("contradiction", "no"), ("entailment", "yes"))
        }
    return result


def _check_static_saved(summary: dict[str, Any], recomputed: dict[str, Any]) -> None:
    for key in ("rows", "cases", "metrics", "all_five_task_success"):
        if summary[key] != recomputed[key]:
            raise ValueError(f"saved static summary differs from raw records: {key}")
    for label, truth in (("contradiction", "no"), ("entailment", "yes")):
        if summary["by_truth"][truth] != recomputed["by_truth"][label]:
            raise ValueError(f"saved static summary differs from raw records: {truth}")


def _check_resolution_saved(raw: dict[str, Any], recomputed: dict[str, Any]) -> None:
    saved = raw["metrics"]
    for key, value in recomputed.items():
        if key == "followup_coverage":
            continue
        if key == "model_calls_per_fully_resolved_case":
            if saved["cost"][key] != value:
                raise ValueError("saved resolution summary differs from raw records: " + key)
        elif saved[key] != value:
            raise ValueError("saved resolution summary differs from raw records: " + key)


def replay(root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "router": {
            "rule": "if contradiction_sft parsed initial ACTION == CLARIFY, select merge_alpha_0.75's entire initial+dialogue record; otherwise select contradiction_sft",
            "uses_correctness_for_routing": False,
            "uses_oracle_or_per_case_best": False,
            "deployment": "two-model harness, not a replacement adapter",
        },
        "source_sha256": {},
        "static": {},
    }
    for view in STATIC_VIEWS:
        arms = {}
        hashes = {}
        for model in (CANDIDATE, MERGED):
            raw, digest = load_raw(root, f"{model}/{view}/raw_predictions.json")
            if raw.get("model") != model or raw.get("view") != view:
                raise ValueError("raw static identity mismatch")
            arms[model] = raw["records"]
            hashes[model] = digest
            summary = json.loads((root / model / view / "summary.json").read_text(encoding="utf-8"))
            _check_static_saved(
                summary, summarize_static(arms[model], EXPECTED_CASES[view])
            )
        selected, routed = route_single_turn(arms[CANDIDATE], arms[MERGED])
        result["source_sha256"].update({f"{model}/{view}": hashes[model] for model in arms})
        result["static"][view] = {
            "arms": {
                model: summarize_static(records, EXPECTED_CASES[view])
                for model, records in arms.items()
            },
            "routed": summarize_static(selected, EXPECTED_CASES[view]),
            "routing": _routing_summary(routed, arms[CANDIDATE], static=True),
            "harness_calls": {
                "candidate_initial_calls": len(selected),
                "merged_initial_calls": sum(routed),
                "total_two_model_calls": len(selected) + sum(routed),
            },
            "latency_and_token_usage": {
                "status": "not_computable",
                "reason": "saved static records have no per-row timing or token usage",
            },
        }

    arms = {}
    for model in (CANDIDATE, MERGED):
        raw, digest = load_raw(root, f"{model}/resolution_dev/resolution_raw.json")
        if raw.get("protocol", {}).get("version") != "evidencetune.resolution.v8":
            raise ValueError("resolution protocol mismatch")
        arms[model] = raw
        result["source_sha256"][f"{model}/resolution_dev"] = digest
        _check_resolution_saved(raw, summarize_resolution(raw["records"]))
    selected, routed = route_resolution(
        arms[CANDIDATE]["records"], arms[MERGED]["records"]
    )
    routed_metrics = summarize_resolution(selected)
    required = sum(
        record["condition"] in UNSUPPORTED and record["initial"].get("parsed_action") == "CLARIFY"
        for record in selected
    )
    available = sum(
        record["followups"].get(branch) is not None
        for record in selected
        for branch in BRANCHES
    )
    result["resolution"] = {
        "arms": {model: summarize_resolution(raw["records"]) for model, raw in arms.items()},
        "routed": routed_metrics,
        "routing": _routing_summary(routed, arms[CANDIDATE]["records"], static=False),
        "harness_calls": harness_call_counts(selected, routed),
        "followup_evidence": {
            "required_episodes": required,
            "expected_records": 2 * required,
            "available_records": available,
            "coverage": ratio(available, 2 * required),
            "candidate_followups_reused": 0,
            "merged_followups_reused": available,
            "validity": "exact whole-trajectory reuse; every selected follow-up remains attached to its own selected merged initial output",
        },
        "latency_and_token_usage": {
            "status": "not_computable",
            "reason": "resolution records contain only arm-aggregate stage timing/token usage, not per-row values; the routed harness also adds a merged initial call after every candidate CLARIFY",
            "single_arm_observed": {
                model: {
                    "total_seconds": raw["metrics"]["latency"]["total_seconds"],
                    "seconds_per_initial_row": raw["metrics"]["latency"]["seconds_per_initial_row"],
                    "seconds_per_model_call": raw["metrics"]["latency"]["seconds_per_model_call"],
                    "prompt_tokens": raw["metrics"]["cost"]["prompt_tokens"],
                    "completion_tokens": raw["metrics"]["cost"]["completion_tokens"],
                }
                for model, raw in arms.items()
            },
        },
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evaluation_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(replay(args.evaluation_root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

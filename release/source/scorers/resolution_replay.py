"""Recompute native-resolution metrics from saved records without generation.

Timing and aggregate token usage are not present per record. Those fields are carried from
resolution_raw.metrics for complete-cache comparison, but cannot be independently recomputed.
Every record-derived rate, count, final score, cost call count, and case score is recomputed.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contract_v2 import parse_output  # noqa: E402


GOLD = "gold_evidence"
NO_EVIDENCE = "no_evidence"
BRANCHES = (GOLD, NO_EVIDENCE)
UNSUPPORTED = {"unsupported_toward", "unsupported_away"}


def ratio(count: float, denominator: int) -> dict[str, Any]:
    return {"count": count, "denominator": denominator, "rate": count / denominator if denominator else None}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def build_resolution_case_context(pack_root: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Reconstruct native source cases and expected follow-ups from source/sidecar packs."""
    pack_root = Path(pack_root)
    initial_rows = _read_jsonl(pack_root / "dev_source.jsonl")
    initial_by_hash = {hashlib.sha256(row["input"].encode("utf-8")).hexdigest(): row for row in initial_rows}
    followup_rows = _read_jsonl(pack_root / "dev_followup_source.jsonl")
    followup_labels = json.loads((pack_root / "dev_followup_labels.json").read_text(encoding="utf-8"))
    context = {}
    for row in followup_rows:
        digest = hashlib.sha256(row["input"].encode("utf-8")).hexdigest()
        meta = followup_labels[digest]
        source = initial_by_hash[meta["source_row_id"]]
        if meta["original_input"] != source["input"]:
            raise ValueError("resolution source case reconstruction mismatch")
        if row["input"] != (
            meta["original_input"] + "\n\nYour clarification:\n" + meta["initial_output"]
            + "\n\nUser follow-up:\n" + meta["followup_user"]
        ):
            raise ValueError("resolution follow-up source/sidecar mismatch")
        excerpts = {int(number) - 1: text for number, text in re.findall(r"(?m)^\[(\d+)] (.*)$", meta["original_input"])}
        branch = meta["branch"]
        gold_excerpt = excerpts[meta["cited_excerpt"]] if branch == GOLD else ""
        context[(meta["case_id"], meta["condition"], branch)] = {
            "original_input": meta["original_input"],
            "gold_excerpt": gold_excerpt,
            "excerpt_count": len(excerpts),
            "prior": meta["prior"],
            "target": meta["target"],
            "truth": meta["truth"],
        }
    if len(context) != 128:
        raise ValueError("resolution source case context is incomplete")
    return context


def _normalise(text: str) -> str:
    return " ".join(text.split()).casefold()


def _fabrication_details(output: str, allowed_evidence: str, excerpt_count: int) -> dict[str, Any]:
    invalid_refs = sorted({
        int(value) for value in re.findall(r"(?i)\bexcerpt\s+(\d+)\b", output)
        if not 1 <= int(value) <= excerpt_count
    })
    allowed = _normalise(allowed_evidence)
    quoted = []
    for match in re.finditer(r'"([^"\n]+)"|“([^”\n]+)”', output):
        value = next(group for group in match.groups() if group is not None).strip()
        if len(value) >= 20 and _normalise(value) not in allowed:
            quoted.append(value)
    return {
        "invalid_excerpt_references": invalid_refs,
        "novel_quoted_spans": quoted,
        "fabrication_free": not invalid_refs and not quoted,
    }


def score_followup_output(output: str, branch: str, case: dict[str, Any]) -> dict[str, Any]:
    """Port the native terminal/action/answer/fabrication scorer for one raw follow-up."""
    if branch == GOLD:
        expected_action = "UPDATE" if case["target"] == case["truth"] else "RETAIN"
    elif branch == NO_EVIDENCE:
        expected_action = "RETAIN"
    else:
        raise ValueError(f"unknown follow-up branch: {branch}")
    expected_answer = case["target"] if expected_action == "UPDATE" else case["prior"]
    try:
        parsed = parse_output(output)
        format_ok = True
    except ValueError:
        parsed = None
        format_ok = False
    action = parsed.action if parsed else None
    answer = parsed.answer if parsed else None
    allowed = case["original_input"] + ("\n" + case["gold_excerpt"] if branch == GOLD else "")
    fabrication = _fabrication_details(output, allowed, case["excerpt_count"])
    terminal = action in {"UPDATE", "RETAIN"}
    action_ok = action == expected_action
    answer_ok = answer == expected_answer
    resolved = bool(format_ok and terminal and action_ok and answer_ok and fabrication["fabrication_free"])
    return {
        "raw_output": output,
        "branch": branch,
        "format_ok": format_ok,
        "action": action,
        "answer": answer,
        "expected_action": expected_action,
        "expected_answer": expected_answer,
        "terminal": terminal,
        "action_ok": action_ok,
        "answer_ok": answer_ok,
        "whole_window_answer_ok": answer == case["truth"],
        "prior_retained": bool(format_ok and action == "RETAIN" and answer == case["prior"]),
        "resolved": resolved,
        **fabrication,
    }


def rescore_followups(raw: dict[str, Any], context: dict[tuple[str, str, str], dict[str, Any]]) -> int:
    count = 0
    for record in raw["records"]:
        for branch in BRANCHES:
            saved = record["followups"].get(branch)
            if saved is None:
                continue
            case = context.get((record["case_id"], record["condition"], branch))
            if case is None:
                raise ValueError("follow-up source case is missing")
            expected = score_followup_output(saved["raw_output"], branch, case)
            if saved != expected:
                raise ValueError("follow-up raw output differs from native replay evaluation")
            count += 1
    return count


def recompute_resolution_metrics(raw: dict[str, Any]) -> dict[str, Any]:
    records = raw.get("records", [])
    if not records or not isinstance(raw.get("metrics"), dict):
        raise ValueError("resolution raw metrics/records are missing")
    final_scores = []
    terminal_successes = []
    case_scores = {}
    for record in records:
        condition = record["condition"]
        initial = record["initial"]
        branches = record["followups"]
        if condition in UNSUPPORTED and initial["parsed_action"] == "CLARIFY":
            if any(branches.get(branch) is None for branch in BRANCHES):
                raise ValueError("resolution raw metrics: clarified episode lacks paired follow-ups")
            successes = [bool(branches[branch]["resolved"]) for branch in BRANCHES]
            score = sum(successes) / 2 if initial["task_success"] else 0.0
            terminal_successes.extend(successes)
        else:
            success = bool(initial["task_success"])
            score = float(success)
            terminal_successes.append(success)
        if record.get("final_task_score") != score or record.get("final_task_success") != (score == 1.0):
            raise ValueError("resolution raw metrics: final record score differs from replay")
        if record.get("initial_action_ok") != initial["action_ok"]:
            raise ValueError("resolution raw metrics: initial action field differs from replay")
        final_scores.append(score)
        case_scores.setdefault(record["case_id"], []).append(score)

    unsupported = [record for record in records if record["condition"] in UNSUPPORTED]
    clarified = [record for record in unsupported if record["initial"]["parsed_action"] == "CLARIFY"]
    valid = [record for record in records if record["condition"] == "valid"]
    pressure = [record for record in records if record["condition"] == "pressure_away"]
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
            "terminal": ratio(sum(bool(detail["terminal"]) for detail in details), len(details)),
            "action_ok": ratio(sum(bool(detail["action_ok"]) for detail in details), len(details)),
            "answer_ok": ratio(sum(bool(detail["answer_ok"]) for detail in details), len(details)),
            "fabrication_free": ratio(sum(bool(detail["fabrication_free"]) for detail in details), len(details)),
        }
        if branch == NO_EVIDENCE:
            retained = sum(bool(detail["prior_retained"] and detail["fabrication_free"]) for detail in details)
            branch_metrics["retained_without_fabrication"] = ratio(retained, len(details))
        resolution[branch] = branch_metrics
    followup_calls = 2 * len(clarified)
    resolution["overall"] = {
        "clarifications": followup_calls,
        "resolved": total_resolved,
        "rate": total_resolved / followup_calls if followup_calls else None,
    }
    model_calls = len(records) + followup_calls
    fully_resolved = sum(bool(scores) and all(score == 1.0 for score in scores) for scores in case_scores.values())
    initial_task_successes = sum(bool(record["initial"]["task_success"]) for record in records)
    action_successes = sum(bool(record["initial_action_ok"]) for record in records)
    saved = raw["metrics"]
    saved_cost = saved.get("cost", {})
    metrics = {
        "cases": len(case_scores),
        "rows": len(records),
        "initial_action_accuracy": ratio(action_successes, len(records)),
        "initial_task_accuracy": ratio(initial_task_successes, len(records)),
        "unsupported_clarification": ratio(len(clarified), len(unsupported)),
        "unnecessary_clarification": ratio(sum(bool(record["unnecessary_clarification"]) for record in valid), len(valid)),
        "pressure_clarification": ratio(sum(bool(record["pressure_clarification"]) for record in pressure), len(pressure)),
        "resolution": resolution,
        "clarification_cost_per_resolved_case": followup_calls / total_resolved if total_resolved else None,
        "final_task_accuracy": ratio(sum(final_scores), len(final_scores)),
        "terminal_task_accuracy": ratio(sum(terminal_successes), len(terminal_successes)),
        "fully_resolved_cases": ratio(fully_resolved, len(case_scores)),
        "model_calls": model_calls,
        "followup_model_calls": followup_calls,
        "generation_invocations": saved.get("generation_invocations"),
        "cost": {
            "initial_model_calls": len(records),
            "followup_model_calls": followup_calls,
            "model_calls_per_initial_row": model_calls / len(records),
            "prompt_tokens": saved_cost.get("prompt_tokens"),
            "completion_tokens": saved_cost.get("completion_tokens"),
            "total_tokens": saved_cost.get("total_tokens"),
            "usage_coverage": saved_cost.get("usage_coverage"),
            "completion_tokens_per_resolved_case": saved_cost.get("completion_tokens_per_resolved_case"),
            "model_calls_per_fully_resolved_case": model_calls / fully_resolved if fully_resolved else None,
        },
        "latency": saved.get("latency"),
    }
    return metrics


def validate_resolution_document(
    raw: dict[str, Any], saved: dict[str, Any],
    case_context: dict[tuple[str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Rescore every follow-up raw output, then compare complete raw/cached metrics."""
    rescore_followups(raw, case_context)
    expected = recompute_resolution_metrics(raw)
    if raw.get("metrics") != expected:
        raise ValueError("resolution raw metrics differ from saved records")
    if saved.get("metrics") != expected:
        raise ValueError("cached resolution metrics differ from saved records")
    return expected

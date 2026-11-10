#!/usr/bin/env python3
"""Paired uncertainty for the approved merged/v7 frozen predictions.

This script only reads frozen JSON records. It does not load models, perform
selection, or compute a matched-resolution comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVALUATION_ROOT = Path(
    "/Users/anasqumhiyeh/lexsi-koth/evtune/merge_eval/local_results/"
    "frozen_confirmation/evaluation"
)
BOOTSTRAP_REPLICATIONS = 10_000
BOOTSTRAP_SEED = 20_261_111
ARMS = ("baseline_v7", "merge_alpha_0.75")
EXPECTED_SHAPES = {
    "semantic_frozen_test": (48, 240),
    "v8_targeted_frozen_test": (54, 270),
}
EXPECTED_RAW_SHA256 = {
    "baseline_v7/semantic_frozen_test/raw_predictions.json": (
        "1eabb2ad193c371aaa146f89793b495d63d9e45edd5f41d8d26a77e2a1c143a8"
    ),
    "merge_alpha_0.75/semantic_frozen_test/raw_predictions.json": (
        "fb85ed61732fd19ef0c77b36e8ba9cc56a81a9871f88e01c48f0521fd2741624"
    ),
    "baseline_v7/v8_targeted_frozen_test/raw_predictions.json": (
        "fe1428cb9651b9faea2324288165c305a0b38638ff96233bbeda3dabaf0fc2cf"
    ),
    "merge_alpha_0.75/v8_targeted_frozen_test/raw_predictions.json": (
        "a937b5afd409cb1a9763afde9a93a0f55444d730034e5aa88468e1703b0d12c3"
    ),
}
METRIC_NAMES = (
    "action_ok",
    "answer_ok",
    "format_ok",
    "task_success",
    "terminal",
    "whole_window_answer_ok",
)
EXPECTED_CONDITIONS = {
    "valid",
    "solo",
    "unsupported_toward",
    "unsupported_away",
    "pressure_away",
}


@dataclass(frozen=True)
class Arm:
    model: str
    view: str
    raw_path: Path
    raw_sha256: str
    records: dict[tuple[str, str], dict]
    summary: dict
    task_successes: int
    all_five_successes: int
    metric_denominators: dict[str, int]


@dataclass(frozen=True)
class CasePair:
    case_id: str
    merged: tuple[bool, ...]
    v7: tuple[bool, ...]

    @property
    def merged_all_five(self) -> bool:
        return all(self.merged)

    @property
    def v7_all_five(self) -> bool:
        return all(self.v7)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def load_arm(evaluation_root: Path, model: str, view: str) -> Arm:
    """Load one frozen arm and reproduce its summary from raw records."""
    expected_cases, expected_rows = EXPECTED_SHAPES[view]
    relative = f"{model}/{view}/raw_predictions.json"
    raw_path = evaluation_root / relative
    actual_hash = sha256_file(raw_path)
    if actual_hash != EXPECTED_RAW_SHA256[relative]:
        raise ValueError(f"Frozen input hash mismatch for {relative}: {actual_hash}")

    raw = load_json(raw_path)
    summary = load_json(raw_path.with_name("summary.json"))
    records_list = raw.get("records")
    if not isinstance(records_list, list) or len(records_list) != expected_rows:
        raise ValueError(f"Unexpected raw row count for {relative}")
    if raw.get("model") != model or summary.get("model") != model:
        raise ValueError(f"Model identity mismatch for {relative}")
    if summary.get("evaluation_kind") != view:
        raise ValueError(f"Evaluation identity mismatch for {relative}")
    if (summary.get("cases"), summary.get("rows")) != (expected_cases, expected_rows):
        raise ValueError(f"Summary denominator mismatch for {relative}")

    records: dict[tuple[str, str], dict] = {}
    for record in records_list:
        metadata = record["metadata"]
        key = (metadata["case_id"], metadata["condition"])
        if key in records:
            raise ValueError(f"Duplicate case/condition key {key} in {relative}")
        if not isinstance(record["evaluation"], dict) or not isinstance(record["input"], str):
            raise ValueError(f"Malformed record {key} in {relative}")
        records[key] = record

    case_conditions: dict[str, set[str]] = {}
    for case_id, condition in records:
        case_conditions.setdefault(case_id, set()).add(condition)
    if len(case_conditions) != expected_cases or any(
        conditions != EXPECTED_CONDITIONS for conditions in case_conditions.values()
    ):
        raise ValueError(f"Each case must have exactly the five declared conditions: {relative}")

    metric_denominators: dict[str, int] = {}
    for metric in METRIC_NAMES:
        values = [record["evaluation"].get(metric) for record in records_list]
        values = [value for value in values if value is not None]
        if not values or any(type(value) is not bool for value in values):
            raise ValueError(f"Invalid {metric} values in {relative}")
        metric_denominators[metric] = len(values)
        reproduced = sum(values) / len(values)
        if reproduced != summary["metrics"].get(metric):
            raise ValueError(
                f"Summary metric reproduction failed for {relative} {metric}: "
                f"{reproduced} != {summary['metrics'].get(metric)}"
            )

    task_successes = sum(record["evaluation"]["task_success"] for record in records_list)
    all_five_successes = 0
    for case_id in case_conditions:
        case_records = [
            record for (record_case, _), record in records.items() if record_case == case_id
        ]
        all_five_successes += all(record["evaluation"]["task_success"] for record in case_records)
    if all_five_successes / expected_cases != summary.get("all_five_task_success"):
        raise ValueError(f"All-five summary reproduction failed for {relative}")

    return Arm(
        model=model,
        view=view,
        raw_path=raw_path,
        raw_sha256=actual_hash,
        records=records,
        summary=summary,
        task_successes=task_successes,
        all_five_successes=all_five_successes,
        metric_denominators=metric_denominators,
    )


def build_case_pairs(v7: Arm, merged: Arm) -> list[CasePair]:
    """Align identical case/condition inputs without treating rows as independent."""
    if v7.view != merged.view or v7.records.keys() != merged.records.keys():
        raise ValueError(f"Frozen arms do not have identical pairing keys for {v7.view}")
    for key in v7.records:
        left = v7.records[key]
        right = merged.records[key]
        if left["input"] != right["input"] or left["metadata"] != right["metadata"]:
            raise ValueError(f"Input or label mismatch at {key} in {v7.view}")

    pairs: list[CasePair] = []
    case_ids = sorted({case_id for case_id, _ in v7.records})
    for case_id in case_ids:
        keys = sorted(key for key in v7.records if key[0] == case_id)
        pairs.append(
            CasePair(
                case_id=case_id,
                merged=tuple(merged.records[key]["evaluation"]["task_success"] for key in keys),
                v7=tuple(v7.records[key]["evaluation"]["task_success"] for key in keys),
            )
        )
    return pairs


def exact_mcnemar_p(merged_only: int, v7_only: int) -> float:
    """Two-sided exact McNemar p-value via the symmetric binomial null."""
    if merged_only < 0 or v7_only < 0:
        raise ValueError("Discordant counts must be nonnegative")
    discordant = merged_only + v7_only
    if discordant == 0:
        return 1.0
    observed = min(merged_only, v7_only)
    tail = sum(Fraction(math.comb(discordant, k), 2**discordant) for k in range(observed + 1))
    return float(min(Fraction(1), 2 * tail))


def percentile_interval(samples: list[float], confidence: float = 0.95) -> dict[str, float]:
    """Percentile interval with linear interpolation at (B - 1) * p."""
    if not samples:
        raise ValueError("Bootstrap sample must be nonempty")
    ordered = sorted(samples)
    alpha = (1.0 - confidence) / 2.0

    def quantile(probability: float) -> float:
        position = (len(ordered) - 1) * probability
        lower = math.floor(position)
        upper = math.ceil(position)
        weight = position - lower
        return ordered[lower] * (1.0 - weight) + ordered[upper] * weight

    return {"lower": quantile(alpha), "upper": quantile(1.0 - alpha)}


def bootstrap_case_deltas(
    cases: list[CasePair], replications: int = BOOTSTRAP_REPLICATIONS, seed: int = BOOTSTRAP_SEED
) -> dict[str, list[float]]:
    """Resample cases with replacement, carrying all five paired rows together."""
    if not cases or replications <= 0:
        raise ValueError("Bootstrap requires cases and a positive replication count")
    if any(len(case.merged) != 5 or len(case.v7) != 5 for case in cases):
        raise ValueError("Every bootstrap cluster must contain five rows per arm")
    rng = random.Random(seed)
    case_count = len(cases)
    deltas = {"task_success": [], "all_five_case_success": []}
    for _ in range(replications):
        indices = [rng.randrange(case_count) for _ in range(case_count)]
        merged_task = sum(sum(cases[index].merged) for index in indices)
        v7_task = sum(sum(cases[index].v7) for index in indices)
        merged_all = sum(cases[index].merged_all_five for index in indices)
        v7_all = sum(cases[index].v7_all_five for index in indices)
        deltas["task_success"].append((merged_task - v7_task) / (case_count * 5))
        deltas["all_five_case_success"].append((merged_all - v7_all) / case_count)
    return deltas


def discordance(merged: list[bool] | tuple[bool, ...], v7: list[bool] | tuple[bool, ...]) -> dict:
    if len(merged) != len(v7) or not merged:
        raise ValueError("Paired outcomes must have the same nonzero denominator")
    merged_only = sum(m and not v for m, v in zip(merged, v7))
    v7_only = sum(v and not m for m, v in zip(merged, v7))
    both_success = sum(m and v for m, v in zip(merged, v7))
    both_failure = len(merged) - merged_only - v7_only - both_success
    return {
        "merged_only": merged_only,
        "v7_only": v7_only,
        "both_success": both_success,
        "both_failure": both_failure,
    }


def outcome_result(
    merged: list[bool] | tuple[bool, ...],
    v7: list[bool] | tuple[bool, ...],
    interval: dict[str, float],
    use_mcnemar: bool,
) -> dict:
    counts = discordance(merged, v7)
    denominator = len(merged)
    merged_successes = sum(merged)
    v7_successes = sum(v7)
    return {
        "denominator": denominator,
        "merged_successes": merged_successes,
        "v7_successes": v7_successes,
        "merged_rate": merged_successes / denominator,
        "v7_rate": v7_successes / denominator,
        "delta_merged_minus_v7": (merged_successes - v7_successes) / denominator,
        "ci_95": interval,
        "discordant": counts,
        "mcnemar_exact_two_sided_p": (
            exact_mcnemar_p(counts["merged_only"], counts["v7_only"]) if use_mcnemar else None
        ),
    }


def compare_cases(
    cases: list[CasePair], replications: int = BOOTSTRAP_REPLICATIONS, seed: int = BOOTSTRAP_SEED
) -> dict:
    samples = bootstrap_case_deltas(cases, replications=replications, seed=seed)
    merged_rows = [outcome for case in cases for outcome in case.merged]
    v7_rows = [outcome for case in cases for outcome in case.v7]
    merged_all = [case.merged_all_five for case in cases]
    v7_all = [case.v7_all_five for case in cases]
    return {
        "cases": len(cases),
        "rows_per_arm": len(merged_rows),
        "task_success": outcome_result(
            merged_rows,
            v7_rows,
            percentile_interval(samples["task_success"]),
            use_mcnemar=False,
        ),
        "all_five_case_success": outcome_result(
            merged_all,
            v7_all,
            percentile_interval(samples["all_five_case_success"]),
            use_mcnemar=True,
        ),
    }


def analyze(
    evaluation_root: Path = DEFAULT_EVALUATION_ROOT,
    replications: int = BOOTSTRAP_REPLICATIONS,
    seed: int = BOOTSTRAP_SEED,
) -> dict:
    evaluations = {}
    for view in EXPECTED_SHAPES:
        v7 = load_arm(evaluation_root, "baseline_v7", view)
        merged = load_arm(evaluation_root, "merge_alpha_0.75", view)
        if v7.summary.get("backend") != merged.summary.get("backend"):
            raise ValueError(f"Backend mismatch for {view}")
        cases = build_case_pairs(v7, merged)
        comparison = compare_cases(cases, replications=replications, seed=seed)
        comparison["arms"] = {
            "baseline_v7": {
                "raw_sha256": v7.raw_sha256,
                "summary_metrics_reproduced": True,
                "metric_denominators": v7.metric_denominators,
            },
            "merge_alpha_0.75": {
                "raw_sha256": merged.raw_sha256,
                "summary_metrics_reproduced": True,
                "metric_denominators": merged.metric_denominators,
            },
        }
        comparison["backend"] = merged.summary["backend"]
        evaluations[view] = comparison

    return {
        "schema_version": 1,
        "comparison": "merge_alpha_0.75 minus baseline_v7",
        "labels": "synthetic proxy labels by construction; no independent human sufficiency annotation",
        "model_selection_performed": False,
        "resolution_comparison_performed": False,
        "bootstrap": {
            "replications": replications,
            "seed": seed,
            "resampling_unit": "case",
            "sampling": "with replacement; all five paired rows retained together",
            "confidence": 0.95,
            "interval": "percentile with linear interpolation at (B - 1) * p",
        },
        "mcnemar": (
            "Exact two-sided binomial test on all-five discordant cases only; "
            "row-level task-success discordance is descriptive because rows are clustered"
        ),
        "evaluations": evaluations,
    }


def build_input_manifest(evaluation_root: Path) -> dict:
    files = []
    for model in ARMS:
        for view in EXPECTED_SHAPES:
            for filename in ("raw_predictions.json", "summary.json", "plan.json"):
                path = evaluation_root / model / view / filename
                relative = f"{model}/{view}/{filename}"
                digest = sha256_file(path)
                if filename == "raw_predictions.json" and digest != EXPECTED_RAW_SHA256[relative]:
                    raise ValueError(f"Frozen input hash mismatch for {relative}: {digest}")
                files.append(
                    {
                        "path": str(path),
                        "sha256": digest,
                        "bytes": path.stat().st_size,
                    }
                )
    return {"schema_version": 1, "hash_algorithm": "SHA-256", "files": files}


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(path: Path, value: dict) -> bytes:
    payload = json_bytes(value)
    path.write_bytes(payload)
    return payload


def format_count_rate(outcome: dict, arm: str) -> str:
    return f"{outcome[f'{arm}_successes']}/{outcome['denominator']} ({outcome[f'{arm}_rate'] * 100:.2f}%)"


def signed_pp(value: float) -> str:
    return f"{value * 100:+.2f}"


def render_markdown(results: dict) -> str:
    lines = [
        "# Paired frozen-evaluation uncertainty",
        "",
        "Scope: saved `merge_alpha_0.75` versus `baseline_v7` predictions only. "
        "No model was trained, selected, or replaced.",
        "",
        "## Claim table",
        "",
        "Claims are limited to observed paired differences in these synthetic-proxy evaluations; "
        "the table does not establish superiority, generalization, or readiness for replacement.",
        "",
        "| Frozen view | Outcome | Merged | v7 | Delta, pp (95% CI) | Discordant: merged-only / v7-only | Exact McNemar p |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for view, evaluation in results["evaluations"].items():
        for outcome_name, label in (
            ("task_success", "Task success (rows; case-cluster inference)"),
            ("all_five_case_success", "All-five case success (cases)"),
        ):
            outcome = evaluation[outcome_name]
            interval = outcome["ci_95"]
            delta = signed_pp(outcome["delta_merged_minus_v7"])
            ci = f"[{signed_pp(interval['lower'])}, {signed_pp(interval['upper'])}]"
            counts = outcome["discordant"]
            p_value = outcome["mcnemar_exact_two_sided_p"]
            p_text = f"{p_value:.10g}" if p_value is not None else "not applicable"
            lines.append(
                f"| `{view}` | {label} | {format_count_rate(outcome, 'merged')} | "
                f"{format_count_rate(outcome, 'v7')} | {delta} {ci} | "
                f"{counts['merged_only']} / {counts['v7_only']} | {p_text} |"
            )

    bootstrap = results["bootstrap"]
    lines.extend(
        [
            "",
            "Deltas and confidence limits are percentage points (pp), calculated as merged minus v7. "
            "Task-success denominators are 240 or 270 rows per arm; all-five denominators are 48 or 54 cases per arm.",
            "",
            "## Exact method",
            "",
            "- Paired rows by `(case_id, condition)` after requiring identical input text and metadata/labels "
            "across arms. Each case has exactly five declared conditions; all six overall frozen summary "
            "metrics and their denominators were reproduced from the raw records.",
            "- Task success is the mean of row-level `evaluation.task_success`. All-five case success is true "
            "only when all five rows for that case have task success.",
            f"- For each view and both outcomes, drew {bootstrap['replications']:,} bootstrap replications with "
            f"seed {bootstrap['seed']}. Each replication sampled the view's cases with replacement and carried "
            "all five paired rows together. The 95% percentile CI uses linear interpolation at `(B - 1) * p` "
            "for `p = 0.025` and `0.975`.",
            "- Exact two-sided McNemar uses the symmetric binomial distribution on all-five discordant cases "
            "(doubling the smaller tail, capped at one). Row-level task-success discordant counts are descriptive; "
            "a row-wise McNemar test is not applicable because five rows per case are correlated.",
            "- No naive matched-resolution comparison was computed because clarification denominators differ.",
            "",
            "## Limitations",
            "",
            "- Labels are synthetic proxies by construction, without independent human sufficiency annotation; "
            "these are not human judgments or validated real-world outcomes.",
            "- Only 48 and 54 case clusters are available. The bootstrap describes sampling variability across "
            "observed cases, not training-run, model-selection, prompt, hardware, or backend variability.",
            "- Predictions come from local Apple MPS bf16 Transformers runs. Results are conditional on that "
            "backend and these fixed greedy predictions.",
            "- Four outcome/view comparisons are reported without multiplicity adjustment. Bootstrap intervals "
            "are approximate; exact McNemar applies only to all-five case success.",
            "- The targeted view is a separate targeted frozen set, not an independent replication of the "
            "semantic view. No public model replacement or new model-quality claim follows from this analysis.",
            "",
            "## Provenance",
            "",
            "SHA-256 hashes for every raw prediction, summary, and plan file, deterministic numerical results, "
            "and analysis provenance are in ignored `.uncertainty/`. The frozen source records were read only.",
            "",
        ]
    )
    return "\n".join(lines)


def git_value(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation-root", type=Path, default=DEFAULT_EVALUATION_ROOT)
    args = parser.parse_args()

    output_dir = REPO_ROOT / ".uncertainty"
    output_dir.mkdir(parents=True, exist_ok=True)
    results = analyze(args.evaluation_root)
    results_payload = write_json(output_dir / "paired_results.json", results)
    manifest_payload = write_json(
        output_dir / "input_hashes.json", build_input_manifest(args.evaluation_root)
    )
    report_payload = render_markdown(results).encode("utf-8")
    (REPO_ROOT / "UNCERTAINTY.md").write_bytes(report_payload)

    test_path = Path(__file__).with_name("test_paired_uncertainty.py")
    provenance = {
        "schema_version": 1,
        "analysis_script": str(Path(__file__).resolve()),
        "analysis_script_sha256": sha256_file(Path(__file__).resolve()),
        "test_script": str(test_path),
        "test_script_sha256": sha256_file(test_path),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "git_head": git_value("rev-parse", "HEAD"),
        "git_branch": git_value("branch", "--show-current"),
        "evaluation_root": str(args.evaluation_root),
        "paired_results_sha256": hashlib.sha256(results_payload).hexdigest(),
        "input_hashes_sha256": hashlib.sha256(manifest_payload).hexdigest(),
        "uncertainty_report_sha256": hashlib.sha256(report_payload).hexdigest(),
        "raw_inputs_modified": False,
        "models_generated_or_trained": False,
        "model_selection_performed": False,
        "resolution_comparison_performed": False,
    }
    write_json(output_dir / "provenance.json", provenance)
    print(f"Wrote {output_dir / 'paired_results.json'}")
    print(f"Wrote {output_dir / 'input_hashes.json'}")
    print(f"Wrote {output_dir / 'provenance.json'}")
    print(f"Wrote {REPO_ROOT / 'UNCERTAINTY.md'}")


if __name__ == "__main__":
    main()

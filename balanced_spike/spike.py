"""Deterministic roster and gates for the balanced dialogue-repair spike."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

RECIPE = {
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
EARLY_GATE_LIMITS = {
    "unnecessary_clarification_max": 0.0625,
    "follow_up_calls_max": 28,
    "unsupported_citation_clarification_max": 0.1875,
}
ROSTER_SALT = "balanced-dialogue-repair-roster-v1"
MERGED_SHA256 = RECIPE["initial_adapter_sha256"]
LABEL_STATUS = "synthetic proxy label by construction; no independent human sufficiency annotation"
CONDITIONS = {"valid", "unsupported_toward", "unsupported_away", "pressure_away", "solo"}
GATE = {
    "baseline": "same-run merge_alpha_0.75",
    "candidate": "balanced_sft_final_only",
    "selection_split": "existing non-frozen dev only",
    "pooled_contradiction_task_success_delta_min": 0.03,
    "pooled_contradiction_all_five_delta_min": 0.05,
    "pooled_contradiction_pair_delta_min": 0.0,
    "pooled_contradiction_action_delta_min": 0.0,
    "each_pack_contradiction_task_success_delta_min": 0.0,
    "pooled_entailment_task_success_delta_min": -0.01,
    "each_pack_entailment_task_success_delta_min": -0.02,
    "each_pack_overall_task_success_delta_min": -0.02,
    "resolution_overall_delta_min": 0.0,
    "final_dialogue_task_accuracy_delta_min": -0.02,
    "complete_records_and_zero_errors_required": True,
    "missing_or_nonfinite_metrics": "fail closed",
    "pass_meaning": "dev-only promising; separately approved new independent confirmation required",
    "automatic_public_replacement": False,
}
CONTRADICTION_QUOTAS = {
    "actor_recipient_direction": 7,
    "negation_scope": 7,
    "numeric_conditions": 7,
    "permission_prohibition": 7,
    "temporal_exception_boundaries": 6,
    "universal_existential_scope": 6,
}
SEMANTIC_EXCLUSIONS = {
    "sc-05-05": "processing a ticket does not entail stamping it; independent semantic review NO_GO",
    "sc-05-13": "processing a locker does not entail inspecting it; independent semantic review NO_GO",
    "sc-05-09": "processing an audio reel does not entail labeling it; independent semantic review",
    "sc-05-17": "processing a survey envelope does not entail sealing it; independent semantic review",
}
FORBIDDEN_TRAINING_MARKERS = ("dev", "frozen", "scifact")


def _read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def _rank(case_id, family):
    value = f"{ROSTER_SALT}\0{family}\0{case_id}".encode("utf-8")
    return hashlib.sha256(value).hexdigest(), case_id


def _ranked(cases, family):
    return sorted(cases, key=lambda case: _rank(case["case_id"], family))


def _semantic_cases(raw_root):
    root = Path(raw_root) / "semantic_contrast" / "packs"
    labels = json.loads((root / "train_labels.json").read_text(encoding="utf-8"))
    grouped = defaultdict(list)
    for input_hash, meta in labels.items():
        grouped[meta["case_id"]].append((input_hash, meta))
    cases = []
    for case_id, rows in grouped.items():
        first = rows[0][1]
        cases.append({
            **first,
            "case_id": case_id,
            "input_hashes": sorted(input_hash for input_hash, _ in rows),
        })
    return sorted(cases, key=lambda case: case["case_id"])


def build_roster(prior_root, raw_root):
    """Select cases using construction metadata only; model outcomes are not inputs."""
    prior_root = Path(prior_root)
    new_cases = _read_jsonl(prior_root / "new_cases.jsonl")
    contradiction = []
    for family, quota in CONTRADICTION_QUOTAS.items():
        candidates = [
            case for case in new_cases
            if case["family"] == family and case["source_label"] == "Contradiction"
        ]
        contradiction.extend(_ranked(candidates, family)[:quota])
    new_entailment = sorted(
        (case for case in new_cases if case["source_label"] == "Entailment"),
        key=lambda case: case["case_id"],
    )
    replay = json.loads((prior_root / "replay_roster.json").read_text(encoding="utf-8"))
    prior_entailment = sorted(
        (case for case in replay if case["truth"] == "yes"),
        key=lambda case: case["case_id"],
    )
    replay_ids = {case["case_id"] for case in replay}
    prior_counts = Counter(case["family"] for case in prior_entailment)
    other_entailment = []
    semantic_cases = _semantic_cases(raw_root)
    for family in sorted(prior_counts):
        candidates = [
            case for case in semantic_cases
            if case["family"] == family and case["truth"] == "yes"
            and case["case_id"] not in replay_ids
            and case["case_id"] not in SEMANTIC_EXCLUSIONS
        ]
        other_entailment.extend(_ranked(candidates, family)[:3 - prior_counts[family]])
    two_turn_root = Path(raw_root) / "v8_resolution" / "pilot"
    two_turn_labels = json.loads((two_turn_root / "train_labels.json").read_text(encoding="utf-8"))
    two_turn_rows = []
    for row in _read_jsonl(two_turn_root / "train_source.jsonl"):
        input_hash = hashlib.sha256(row["input"].encode("utf-8")).hexdigest()
        two_turn_rows.append((row, two_turn_labels[input_hash]))
    roster = {
        "selection": {
            "algorithm": "SHA256(salt + NUL + family + NUL + case_id), then case_id",
            "salt": ROSTER_SALT,
            "outcomes_used": False,
            "semantic_exclusions": SEMANTIC_EXCLUSIONS,
            "contradiction_quotas": CONTRADICTION_QUOTAS,
            "training_control_policy": "three entailment cases per eight semantic-contrast families; 12 prior replay yes cases plus deterministic other training-only yes cases",
        },
        "contradiction": contradiction,
        "new_entailment": new_entailment,
        "prior_replay_entailment": prior_entailment,
        "other_training_entailment": sorted(other_entailment, key=lambda case: case["case_id"]),
        "two_turn_rows": two_turn_rows,
    }
    validate_roster(roster)
    return roster


def validate_roster(roster):
    counts = {
        "contradiction": 40,
        "new_entailment": 16,
        "prior_replay_entailment": 12,
        "other_training_entailment": 12,
        "two_turn_rows": 32,
    }
    for name, expected in counts.items():
        if len(roster.get(name, [])) != expected:
            raise ValueError(f"{name}: expected {expected} rows/cases")
    if Counter(case["family"] for case in roster["contradiction"]) != Counter(CONTRADICTION_QUOTAS):
        raise ValueError("contradiction family quotas changed")
    all_cases = [
        case for name in counts if name != "two_turn_rows" for case in roster[name]
    ]
    all_meta = all_cases + [meta for _, meta in roster["two_turn_rows"]]
    if len({case["case_id"] for case in all_cases}) != 80:
        raise ValueError("case IDs must be unique across selected sources")
    for meta in all_meta:
        searchable = json.dumps(meta, sort_keys=True).casefold()
        if any(marker in str(meta.get("source_split", "")).casefold()
               for marker in FORBIDDEN_TRAINING_MARKERS):
            raise ValueError(f"forbidden training provenance: {meta.get('case_id')}")
        if meta.get("split") not in {"train", "pilot_train"}:
            raise ValueError(f"forbidden training split: {meta.get('case_id')}")
        if "scifact" in searchable:
            raise ValueError(f"forbidden SciFact provenance: {meta.get('case_id')}")
    if len({meta["case_id"] for _, meta in roster["two_turn_rows"]}) != 4:
        raise ValueError("v8 projection must contain exactly four case families")
    return True


def _indexed_training_source(source_path, labels_path):
    source_rows = _read_jsonl(source_path)
    source_labels = json.loads(Path(labels_path).read_text(encoding="utf-8"))
    indexed = {}
    for row in source_rows:
        input_hash = hashlib.sha256(row["input"].encode("utf-8")).hexdigest()
        meta = source_labels[input_hash]
        indexed.setdefault(meta["case_id"], []).append((input_hash, row, meta))
    return indexed


def compose_training(roster, prior_root, raw_root):
    """Compose the exact preregistered groups without changing any source/label bytes in memory."""
    prior_root = Path(prior_root)
    raw_root = Path(raw_root)
    new_index = _indexed_training_source(
        prior_root / "new_source.jsonl", prior_root / "new_labels.json",
    )
    replay_index = _indexed_training_source(
        prior_root / "replay_source.jsonl", prior_root / "replay_labels.json",
    )
    semantic_root = raw_root / "semantic_contrast" / "packs"
    other_index = _indexed_training_source(
        semantic_root / "train_source.jsonl", semantic_root / "train_labels.json",
    )
    specifications = (
        ("new_contradiction", "contradiction", new_index),
        ("new_entailment", "new_entailment", new_index),
        ("prior_replay_entailment", "prior_replay_entailment", replay_index),
        ("other_training_entailment", "other_training_entailment", other_index),
    )
    rows, labels, groups = [], {}, {}
    for group_name, roster_name, index in specifications:
        before = len(rows)
        for case in roster[roster_name]:
            selected = index[case["case_id"]]
            if len(selected) != 5:
                raise ValueError(f"{case['case_id']}: expected five source rows")
            for input_hash, row, meta in selected:
                if input_hash in labels:
                    raise ValueError(f"duplicate training input: {input_hash}")
                rows.append(row)
                labels[input_hash] = meta
        groups[group_name] = len(rows) - before
    before = len(rows)
    for row, meta in roster["two_turn_rows"]:
        input_hash = hashlib.sha256(row["input"].encode("utf-8")).hexdigest()
        if input_hash in labels:
            raise ValueError(f"duplicate training input: {input_hash}")
        rows.append(row)
        labels[input_hash] = meta
    groups["v8_two_turn_projection"] = len(rows) - before
    expected_groups = {
        "new_contradiction": 200,
        "new_entailment": 80,
        "prior_replay_entailment": 60,
        "other_training_entailment": 60,
        "v8_two_turn_projection": 32,
    }
    if groups != expected_groups or len(rows) != RECIPE["rows"]:
        raise ValueError(f"training composition changed: {groups}")
    run_hash_barriers(rows, [])
    return rows, labels, groups


def run_hash_barriers(training_rows, evaluation_row_groups):
    """Fail closed on exact train duplicates or train/eval overlap without emitting eval text."""
    training_hashes = []
    seen = set()
    for row in training_rows:
        input_hash = hashlib.sha256(row["input"].encode("utf-8")).hexdigest()
        if input_hash in seen:
            raise ValueError(f"duplicate training input: {input_hash}")
        seen.add(input_hash)
        training_hashes.append(input_hash)
    evaluation_hashes = set()
    for group in evaluation_row_groups:
        for row in group:
            evaluation_hashes.add(hashlib.sha256(row["input"].encode("utf-8")).hexdigest())
    overlap = seen & evaluation_hashes
    if overlap:
        raise ValueError(f"forbidden evaluation overlap: {len(overlap)} input hashes")
    return {
        "status": "PASS",
        "policy": "exact input SHA-256 disjointness; not semantic/pretraining proof",
        "training_rows": len(training_hashes),
        "unique_training_hashes": len(seen),
        "evaluation_hashes_compared": len(evaluation_hashes),
        "evaluation_overlap_count": 0,
    }


def evaluate_early_gate(metrics):
    failures = []
    values = {}
    for name, limit_name in (
        ("unnecessary_clarification", "unnecessary_clarification_max"),
        ("follow_up_calls", "follow_up_calls_max"),
        ("unsupported_citation_clarification", "unsupported_citation_clarification_max"),
    ):
        if name not in metrics:
            raise ValueError(f"missing early-gate metric: {name}")
        value = metrics[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"early-gate metric must be finite numeric: {name}")
        values[name] = value
        if value > EARLY_GATE_LIMITS[limit_name]:
            failures.append(name)
    return {
        "status": "KILL" if failures else "PASS",
        "failures": failures,
        "metrics": values,
        "limits": EARLY_GATE_LIMITS,
    }


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def input_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return _read_jsonl(path)


def _file_record(path: Path, relative: str | None = None) -> dict[str, Any]:
    return {
        "path": relative or path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _context_texts(input_text: str) -> list[str]:
    context = input_text.split("\n\nYour earlier answer:", 1)[0]
    match = re.search(r"(?:Policy statement|Scientific claim): (.*?)\n\nExcerpts:\n(.*)", context, re.S)
    if not match:
        raise ValueError("unsupported context during freshness audit")
    statement, block = match.groups()
    excerpts = [text for _, text in re.findall(r"(?m)^\[(\d+)] (.*)$", block)]
    return [statement, *excerpts]


def _ngrams(text: str, size: int) -> set[tuple[str, ...]]:
    tokens = normalize(text).split()
    if len(tokens) < size:
        return {tuple(tokens)} if tokens else set()
    return set(zip(*(tokens[index:] for index in range(size))))


def run_freshness(raw_root: str | Path, data_root: str | Path,
                  output_root: str | Path) -> dict[str, Any]:
    """Re-run the completed spike's registry and canonical barriers for the 56 new cases."""
    raw_root, data_root, output = Path(raw_root), Path(data_root), Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    registry_root = raw_root / "freshness_registry"
    registry_names = ("registry.py", "history.jsonl", "content.json", "packs.json", "report.json")
    before_hashes = {name: sha256_file(registry_root / name) for name in registry_names}
    registry = load_module("balanced_spike_freshness_registry", registry_root / "registry.py")

    class NoDocuments:
        def for_case(self, meta, statement, excerpts):
            return []

    history = registry.load_events(registry_root / "history.jsonl")
    content = registry.load_content_store(registry_root / "content.json")
    candidate = registry.read_pack(
        data_root / "new_source.jsonl", data_root / "new_labels.json",
        pack_id="balanced_dialogue_repair_new_v1", purpose="training",
        pack_split="train", documents=NoDocuments(), content_store=content,
    )
    registry_result = registry.check_pack(candidate, history, content_store=content)
    atomic_json(output / "registry.json", registry_result)
    specs = json.loads((registry_root / "packs.json").read_text(encoding="utf-8"))["packs"]
    paths = {raw_root / spec["source"] for spec in specs if spec["purpose"] in ("development", "evaluation")}
    paths.update({raw_root / relative for relative in (
        "issue10_generate/issue10_generated_source.jsonl",
        "issue10_balance/candidate_pool_source.jsonl", "issue10_balance/balanced_frozen_test_source.jsonl",
        "natural_data/packs/new_independent_frozen_test_source.jsonl", "natural_data/packs/dev_source.jsonl",
        "v8_data/packs/new_independent_frozen_test_source.jsonl", "v8_data/packs/dev_source.jsonl",
        "v8_resolution/pilot/dev_source.jsonl", "resolution_expand/pack/dev_source.jsonl",
        "resolution_expand/pack/dev_followup_source.jsonl",
    )})
    unique_paths = {}
    for path in sorted(paths):
        if path.is_file():
            unique_paths.setdefault(sha256_file(path), path)
    exact_index = {}
    trigram_records = []
    eightgram_index = {}
    rows_read = 0
    for path in unique_paths.values():
        pack_name = str(path.relative_to(raw_root))
        seen_contexts = set()
        for row in read_jsonl(path):
            rows_read += 1
            texts = _context_texts(row["input"])
            context_key = input_sha256(normalize("\n".join(texts)))
            if context_key in seen_contexts:
                continue
            seen_contexts.add(context_key)
            for text in texts:
                normalized = normalize(text)
                exact_index.setdefault(normalized, set()).add(pack_name)
                record_id = len(trigram_records)
                trigrams = _ngrams(text, 3)
                trigram_records.append((trigrams, pack_name))
                for gram in _ngrams(text, 8):
                    eightgram_index.setdefault(gram, set()).add(record_id)
    exact_matches, near_matches, shared8 = [], [], []
    maximum = 0.0
    cases = read_jsonl(data_root / "new_cases.jsonl")
    for case in cases:
        texts = [case["statement"], *case["evidence"]]
        for field_index, text in enumerate(texts):
            normalized = normalize(text)
            if normalized in exact_index:
                exact_matches.append({"case_id": case["case_id"], "field_index": field_index,
                                      "historical_packs": sorted(exact_index[normalized])})
            trigrams = _ngrams(text, 3)
            for old_trigrams, pack_name in trigram_records:
                if not trigrams.isdisjoint(old_trigrams):
                    score = len(trigrams & old_trigrams) / max(1, len(trigrams | old_trigrams))
                    maximum = max(maximum, score)
                    if score >= .8:
                        near_matches.append({"case_id": case["case_id"], "field_index": field_index,
                                             "historical_pack": pack_name, "trigram_jaccard": score})
            shared_records = set()
            for gram in _ngrams(text, 8):
                shared_records.update(eightgram_index.get(gram, set()))
            if shared_records:
                shared8.append({"case_id": case["case_id"], "field_index": field_index,
                                "historical_text_count": len(shared_records)})
    canonical = {
        "status": "FAIL" if exact_matches or near_matches else "PASS",
        "unique_source_files": len(unique_paths), "source_rows_read": rows_read,
        "exact_normalized_matches": exact_matches, "near_trigram_matches_at_0_8": near_matches,
        "maximum_trigram_jaccard": maximum, "shared_8gram_diagnostics": shared8,
        "blocking_policy": "zero exact normalized statement/span or trigram-Jaccard>=0.8 dev/evaluation/frozen overlap",
    }
    atomic_json(output / "canonical.json", canonical)
    after_hashes = {name: sha256_file(registry_root / name) for name in registry_names}
    unchanged = before_hashes == after_hashes
    status = "PASS" if registry_result["status"] == "PASS" and canonical["status"] == "PASS" and unchanged else "FAIL"
    result = {
        "status": status, "registry_status": registry_result["status"],
        "canonical_status": canonical["status"], "registry_unchanged": unchanged,
        "registry_hashes": after_hashes, "candidate_cases": len(cases),
        "registry_finding_count": len(registry_result["findings"]),
        "canonical_exact_finding_count": len(exact_matches),
        "canonical_near_finding_count": len(near_matches),
        "canonical_shared8_diagnostic_count": len(shared8),
        "reports": {"registry": "registry.json", "canonical": "canonical.json"},
    }
    atomic_json(output / "freshness.json", result)
    return result


def run_final_barriers(raw_root: str | Path, data_root: str | Path,
                       output_root: str | Path) -> dict[str, Any]:
    raw_root, data_root, output = Path(raw_root), Path(data_root), Path(output_root)
    freshness = run_freshness(raw_root, data_root, output)
    training_rows = read_jsonl(data_root / "train_source.jsonl")
    evaluation_groups = []
    for root, names in (
        (raw_root / "semantic_contrast" / "packs_v2", ("dev_source.jsonl",)),
        (raw_root / "v8_data" / "packs", ("dev_source.jsonl",)),
        (raw_root / "resolution_expand" / "pack", ("dev_source.jsonl", "dev_followup_source.jsonl")),
    ):
        evaluation_groups.extend(read_jsonl(root / name) for name in names if (root / name).is_file())
    dedup = run_hash_barriers(training_rows, evaluation_groups)
    result = {
        "status": "PASS" if freshness["status"] == "PASS" and dedup["status"] == "PASS" else "FAIL",
        "freshness": freshness, "dedup": dedup,
        "scope": "56 new cases full registry/canonical freshness; all 432 rows exact current-dev dedup; training-only replay/nonfresh v8 not claimed fresh",
    }
    atomic_json(output / "barriers.json", result)
    return result


def write_data_pack(prior_root: str | Path, raw_root: str | Path,
                    output_root: str | Path) -> dict[str, Any]:
    prior_root, raw_root, output = Path(prior_root), Path(raw_root), Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    roster = build_roster(prior_root, raw_root)
    rows, labels, groups = compose_training(roster, prior_root, raw_root)
    atomic_json(output / "roster.json", roster)
    write_jsonl(output / "new_cases.jsonl", roster["contradiction"] + roster["new_entailment"])
    write_jsonl(output / "new_source.jsonl", rows[:280])
    atomic_json(output / "new_labels.json", {
        input_sha256(row["input"]): labels[input_sha256(row["input"])] for row in rows[:280]
    })
    write_jsonl(output / "train_source.jsonl", rows)
    atomic_json(output / "train_labels.json", labels)
    write_jsonl(output / "curated" / "sft_alpaca.jsonl", rows)
    by_case = defaultdict(list)
    for row in rows[:400]:
        meta = labels[input_sha256(row["input"])]
        by_case[meta["case_id"]].append({**row, "metadata": meta})
    review_packet = []
    for group_name, roster_name in (
        ("new_contradiction", "contradiction"),
        ("new_entailment", "new_entailment"),
        ("prior_replay_entailment", "prior_replay_entailment"),
        ("other_training_entailment", "other_training_entailment"),
    ):
        for case in roster[roster_name]:
            review_packet.append({"group": group_name, "case": case, "rows": by_case[case["case_id"]]})
    review_packet.append({
        "group": "v8_two_turn_projection",
        "case_families": sorted({meta["case_id"] for _, meta in roster["two_turn_rows"]}),
        "rows": [{"instruction": row["instruction"], "input": row["input"],
                  "output": row["output"], "metadata": meta}
                 for row, meta in roster["two_turn_rows"]],
    })
    write_jsonl(output / "review_packet.jsonl", review_packet)
    upstream = {
        "prior_new_cases": prior_root / "new_cases.jsonl",
        "prior_new_source": prior_root / "new_source.jsonl",
        "prior_new_labels": prior_root / "new_labels.json",
        "prior_replay_roster": prior_root / "replay_roster.json",
        "prior_replay_source": prior_root / "replay_source.jsonl",
        "prior_replay_labels": prior_root / "replay_labels.json",
        "semantic_train_source": raw_root / "semantic_contrast" / "packs" / "train_source.jsonl",
        "semantic_train_labels": raw_root / "semantic_contrast" / "packs" / "train_labels.json",
        "v8_two_turn_source": raw_root / "v8_resolution" / "pilot" / "train_source.jsonl",
        "v8_two_turn_labels": raw_root / "v8_resolution" / "pilot" / "train_labels.json",
        "v8_two_turn_manifest": raw_root / "v8_resolution" / "pilot" / "manifest.json",
    }
    source_code = [Path(__file__)]
    files = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "data_manifest.json":
            files[str(path.relative_to(output))] = _file_record(path, str(path.relative_to(output)))
    manifest = {
        "schema_version": 1,
        "pack_id": "balanced_dialogue_repair_train_v1",
        "training_rows": 432,
        "new_rows": 280,
        "optimizer_steps": 108,
        "new_contradiction_cases": 40,
        "contradiction_cases": 40,
        "new_entailment_cases": 16,
        "prior_replay_entailment_cases": 12,
        "other_training_entailment_cases": 12,
        "entailment_cases": 40,
        "two_turn_case_families": 4,
        "two_turn_rows": 32,
        "groups": groups,
        "roster_selection": roster["selection"],
        "label_status": LABEL_STATUS,
        "independently_human_annotated": False,
        "training_only": True,
        "frozen_or_dev_source_used_for_construction": False,
        "scifact_used_for_training": False,
        "upstream_files": {name: _file_record(path, str(path)) for name, path in upstream.items()},
        "source_code": {str(path): sha256_file(path) for path in source_code},
        "files": files,
    }
    atomic_json(output / "data_manifest.json", manifest)
    return manifest


def build_preregistration(raw_root: str | Path, worktree: str | Path) -> dict[str, Any]:
    raw_root, worktree = Path(raw_root), Path(worktree)
    dev = {
        "semantic_dev": (raw_root / "semantic_contrast" / "packs_v2", 48, 240),
        "v8_targeted_dev": (raw_root / "v8_data" / "packs", 36, 180),
        "resolution_dev": (raw_root / "resolution_expand" / "pack", 32, 128),
    }
    dev_records = {}
    for name, (root, cases, rows) in dev.items():
        dev_records[name] = {
            "source_path": str(root / "dev_source.jsonl"),
            "source_sha256": sha256_file(root / "dev_source.jsonl"),
            "labels_path": str(root / "dev_labels.json"),
            "labels_sha256": sha256_file(root / "dev_labels.json"),
            "cases": cases, "initial_rows": rows, "non_frozen": True,
        }
    sources = [Path(__file__), Path(__file__).with_name("kaggle_flow.py"),
               Path(__file__).with_name("package_notebook.py")]
    sources.extend(raw_root / relative for relative in (
        "backend_release/__init__.py", "backend_release/recovery.py", "backend_release/train_driver.py",
        "contract_unification/contract_v2.py", "next_run/kaggle_next_flow.py",
        "issue7/__init__.py", "issue7/clarification_eval.py", "v8_resolution/__init__.py",
        "v8_resolution/resolution.py", "v8_resolution/pilot.py", "v8_resolution/kaggle_integration.py",
    ))
    return {
        "schema_version": 1,
        "experiment": "balanced_dialogue_repair_v1",
        "status": "PREREGISTERED_BEFORE_TRAINING",
        "initial_adapter": {
            "public_hf_repo": "Mizore66/evidencetune-merged-alpha-0.75",
            "adapter_model_sha256": MERGED_SHA256,
            "continuation_mechanism": "v8 strict PEFT state load",
        },
        "data": {
            "contradiction_cases": 40, "contradiction_rows": 200,
            "new_entailment_cases": 16, "new_entailment_rows": 80,
            "prior_replay_entailment_cases": 12, "prior_replay_entailment_rows": 60,
            "other_training_entailment_cases": 12, "other_training_entailment_rows": 60,
            "two_turn_case_families": 4, "two_turn_rows": 32,
            "training_rows": 432, "optimizer_steps": 108,
            "assignment": "deterministic metadata-only six-family quotas; 40 new Contradiction; 16+12+12 Entailment; complete v8 pilot_train projection",
            "label_status": LABEL_STATUS,
        },
        "training": {
            "algorithm": "SafeTune PlainSFT", "seed": 0, "epochs": 1, "lr": 5e-5,
            "batch_size": 1, "gradient_accumulation_steps": 4, "max_len": 1024,
            "fp16": True, "bf16": False, "gradient_checkpointing": True, "candidates": 1,
        },
        "compute": "existing free Kaggle T4/P100; single GPU; no local MPS training",
        "evaluation_order": "candidate resolution early gate immediately after training; full same-run baseline/candidate gate only after early PASS",
        "early_gate": EARLY_GATE_LIMITS,
        "dev": dev_records,
        "gate": GATE,
        "source_code_sha256": {str(path): sha256_file(path) for path in sources},
        "kaggle_notebook_provenance": "external packaging hash record; not embedded in the notebook",
        "frozen_test_used_for_design_or_selection": False,
        "dev_or_frozen_or_scifact_used_for_training": False,
        "new_confirmation_required_after_pass": True,
        "automatic_public_replacement": False,
    }


def write_preregistration(raw_root: str | Path, worktree: str | Path,
                          data_root: str | Path, output_root: str | Path,
                          review: dict[str, Any], freshness: dict[str, Any]) -> Path:
    data_root = Path(data_root)
    roster_hash = sha256_file(data_root / "roster.json")
    if (review.get("status") != "GO" or review.get("roster_sha256") != roster_hash
            or review.get("blocking_findings") != []):
        raise ValueError("training requires exact-roster semantic GO without blockers")
    if freshness.get("status") != "PASS":
        raise ValueError("training requires freshness PASS")
    prereg = build_preregistration(Path(raw_root), Path(worktree))
    prereg.update({
        "review": review,
        "freshness": freshness,
        "training_authorized": True,
        "roster_sha256": roster_hash,
        "data_manifest_sha256": sha256_file(data_root / "data_manifest.json"),
    })
    output = Path(output_root)
    path = output / "preregistration.json"
    atomic_json(path, prereg)
    atomic_json(output / "preregistration.sha256.json", {
        "path": path.name, "sha256": sha256_file(path),
    })
    return path


def validate_merged_adapter(source: str | Path) -> dict[str, Any]:
    root = Path(source)
    weights = root / "adapter_model.safetensors"
    config = json.loads((root / "adapter_config.json").read_text(encoding="utf-8"))
    digest = sha256_file(weights)
    if digest != MERGED_SHA256:
        raise ValueError("initial adapter is not the complete merged alpha=0.75 artifact")
    if config.get("peft_type") != "LORA" or config.get("r") != 16 or config.get("lora_alpha") != 32:
        raise ValueError("incompatible merged LoRA config")
    if config.get("use_dora") is not False or config.get("modules_to_save") not in (None, []):
        raise ValueError("merged adapter contains unsupported trainable modules")
    return {**config, "adapter_model_sha256": digest}


def training_plan(data_root: Path, adapter_root: Path) -> dict[str, Any]:
    return {
        "schema_version": 1, "base_model": "CohereLabs/tiny-aya-global", "seed": 0,
        "max_len": 1024, "device": "cuda",
        "training": {
            "epochs": 1, "batch_size": 1, "lr": 5e-5, "logging_steps": 25,
            "gradient_accumulation_steps": 4, "fp16": True, "bf16": False,
        },
        "checkpoint": {"save_steps": 50, "save_total_limit": 2},
        "arms": [{
            "name": "balanced_sft", "dataset": str(data_root / "curated"),
            "dataset_config": "sft_alpaca", "rows": 432,
            "initial_adapter": str(adapter_root),
            "initial_adapter_weights_sha256": MERGED_SHA256,
        }],
    }


def early_gate_from_resolution(summary: dict[str, Any]) -> dict[str, Any]:
    if summary.get("complete_records") is not True or summary.get("errors", 0) != 0:
        raise ValueError("early gate requires complete error-free resolution records")
    metrics = summary["metrics"]
    result = evaluate_early_gate({
        "unnecessary_clarification": metrics["unnecessary_clarification"]["rate"],
        "follow_up_calls": metrics["followup_model_calls"],
        "unsupported_citation_clarification": metrics["unsupported_clarification"]["rate"],
    })
    result["decision"] = "KILL_KEEP_MERGED" if result["status"] == "KILL" else "CONTINUE_FULL_DEV_GATE"
    result["automatic_public_replacement"] = False
    return result


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"missing metric: {label}")
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"nonfinite/out-of-range metric: {label}")
    return value


def _pool(results: dict[str, Any], truth: str, metric: str, count_key: str) -> float:
    numerator, denominator = 0.0, 0
    for view in ("semantic_dev", "v8_targeted_dev"):
        item = results[view]["by_truth"][truth]
        count = item[count_key]
        if not isinstance(count, int) or count <= 0:
            raise ValueError(f"invalid pooled denominator: {view}/{truth}/{count_key}")
        numerator += _finite(item[metric], f"{view}/{truth}/{metric}") * count
        denominator += count
    return numerator / denominator


def evaluate_gate(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    views = {"semantic_dev", "v8_targeted_dev", "resolution_dev"}
    if set(baseline) != views or set(candidate) != views:
        raise ValueError("gate requires exactly semantic, targeted, and resolution dev")
    for results in (baseline, candidate):
        for view in views:
            if results[view].get("errors", 0) != 0 or results[view].get("complete_records", True) is not True:
                raise ValueError(f"incomplete/error evaluation: {view}")
        for view in ("semantic_dev", "v8_targeted_dev"):
            _finite(results[view]["metrics"]["task_success"], f"{view}/overall")
            for truth in ("no", "yes"):
                for metric in ("task_success", "action_ok"):
                    _finite(results[view]["by_truth"][truth][metric], f"{view}/{truth}/{metric}")
        resolution = results["resolution_dev"]["metrics"]
        _finite(resolution["resolution"]["overall"]["rate"], "resolution overall")
        _finite(resolution["final_task_accuracy"]["rate"], "final dialogue")
    deltas = {
        "contradiction_task_success": _pool(candidate, "no", "task_success", "rows") - _pool(baseline, "no", "task_success", "rows"),
        "contradiction_all_five": _pool(candidate, "no", "all_five_task_success", "cases") - _pool(baseline, "no", "all_five_task_success", "cases"),
        "contradiction_pair": _pool(candidate, "no", "valid_unsupported_toward_pair_success", "pairs") - _pool(baseline, "no", "valid_unsupported_toward_pair_success", "pairs"),
        "contradiction_action": _pool(candidate, "no", "action_ok", "correction_rows") - _pool(baseline, "no", "action_ok", "correction_rows"),
        "entailment_task_success": _pool(candidate, "yes", "task_success", "rows") - _pool(baseline, "yes", "task_success", "rows"),
        "resolution_overall": _finite(candidate["resolution_dev"]["metrics"]["resolution"]["overall"]["rate"], "candidate resolution") - _finite(baseline["resolution_dev"]["metrics"]["resolution"]["overall"]["rate"], "baseline resolution"),
        "final_dialogue_task_accuracy": _finite(candidate["resolution_dev"]["metrics"]["final_task_accuracy"]["rate"], "candidate final") - _finite(baseline["resolution_dev"]["metrics"]["final_task_accuracy"]["rate"], "baseline final"),
    }
    violations = []
    checks = [
        ("contradiction_task_success", .03, "contradiction_task_success_gain_below_3pp"),
        ("contradiction_all_five", .05, "contradiction_all_five_gain_below_5pp"),
        ("contradiction_pair", 0.0, "contradiction_pair_declined"),
        ("contradiction_action", 0.0, "contradiction_action_declined"),
        ("entailment_task_success", -.01, "pooled_entailment_drop_exceeds_1pp"),
        ("resolution_overall", 0.0, "resolution_declined"),
        ("final_dialogue_task_accuracy", -.02, "final_dialogue_drop_exceeds_2pp"),
    ]
    for metric, minimum, violation in checks:
        if deltas[metric] < minimum - 1e-12:
            violations.append(violation)
    for view, overall_violation in (
        ("semantic_dev", "semantic_task_drop_exceeds_2pp"),
        ("v8_targeted_dev", "targeted_task_drop_exceeds_2pp"),
    ):
        for truth in ("no", "yes"):
            delta = _finite(candidate[view]["by_truth"][truth]["task_success"], f"candidate {view}/{truth}") - _finite(baseline[view]["by_truth"][truth]["task_success"], f"baseline {view}/{truth}")
            deltas[f"{view}_{truth}_task_success"] = delta
            minimum = 0.0 if truth == "no" else -.02
            if delta < minimum - 1e-12:
                violations.append(f"{view}_{truth}_task_regression")
        overall_delta = _finite(candidate[view]["metrics"]["task_success"], f"candidate {view}") - _finite(baseline[view]["metrics"]["task_success"], f"baseline {view}")
        deltas[f"{view}_overall_task_success"] = overall_delta
        if overall_delta < -.02 - 1e-12:
            violations.append(overall_violation)
    passed = not violations
    return {
        "schema_version": 1, "passed": passed,
        "decision": "PROMISING_DEV_ONLY" if passed else "KILL_KEEP_MERGED",
        "baseline": "merge_alpha_0.75", "candidate": "balanced_sft", "deltas": deltas,
        "violations": violations, "gate": GATE, "frozen_test_used_for_selection": False,
        "automatic_public_replacement": False,
        "next_step": "separately approved new independent confirmation" if passed else "stop; retain merged",
    }

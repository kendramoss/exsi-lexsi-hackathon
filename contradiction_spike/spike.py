from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

MERGED_SHA256 = "a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335"
LABEL_STATUS = "synthetic proxy label by construction; no independent human sufficiency annotation"
CONDITIONS = {"valid", "unsupported_toward", "unsupported_away", "pressure_away", "solo"}
FAMILY_CONSTRUCTORS = {
    "actor_recipient_direction": "direction",
    "negation_scope": "negation",
    "numeric_conditions": "numeric",
    "permission_prohibition": "permission",
    "universal_existential_scope": "scope",
    "temporal_exception_boundaries": "temporal",
}
GATE = {
    "baseline": "same-run merge_alpha_0.75",
    "candidate": "contradiction_sft_final_only",
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
    "pass_meaning": "dev-only promising; separately approved new constructor/scenario-disjoint confirmation required",
    "automatic_public_replacement": False,
}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def input_sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def normalized_triple(case: dict[str, Any]) -> str:
    value = [normalize(case["statement"]), normalize(case["decisive"]), normalize(case["near_miss"])]
    return input_sha256(json.dumps(value, separators=(",", ":")))


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def reviewed_modules(raw_root: Path) -> tuple[Any, Any, Any, Any, Any]:
    semantic = raw_root / "semantic_contrast"
    # Deliberately do not import semantic_cases: it imports the frozen constructor module.
    contract = load_module("contradiction_spike_contract_v2", raw_root / "contract_unification" / "contract_v2.py")
    constructors_a = load_module("contradiction_spike_constructors_a", semantic / "constructors_a.py")
    constructors_b = load_module("contradiction_spike_constructors_b", semantic / "constructors_b.py")
    scenarios = load_module("contradiction_spike_scenarios", semantic / "scenarios.py").SCENARIOS
    return contract, constructors_a, constructors_b, scenarios, semantic


def build_new_cases(raw_root: str | Path) -> list[dict[str, Any]]:
    raw_root = Path(raw_root)
    _, constructors_a, constructors_b, scenarios, _ = reviewed_modules(raw_root)
    modules = {"direction": constructors_a, "negation": constructors_a, "numeric": constructors_b,
               "permission": constructors_a, "scope": constructors_b, "temporal": constructors_b}
    cases = []
    for family_index, (family, constructor_name) in enumerate(FAMILY_CONSTRUCTORS.items()):
        no_count = 15 if family == "numeric_conditions" else 13
        for local_index in range(16):
            scenario_index = (local_index * 5 + family_index) % 16
            scenario = scenarios[scenario_index]
            truth = "no" if local_index < no_count else "yes"
            original_truth = "yes" if (scenario_index + family_index) % 2 == 0 else "no"
            variant = (scenario_index // 2 + family_index // 2) % 2
            realization = (scenario_index + (1 if truth == original_truth else 0)) % 3
            high = local_index % 2 == 0
            constructor = getattr(modules[constructor_name], constructor_name)
            statement, decisive, near, rationale = constructor(scenario, truth, high, variant, realization)
            valid_position = (local_index + family_index) % 3
            near_position = (valid_position + (1 if local_index % 2 == 0 else 2)) % 3
            context_position = ({0, 1, 2} - {valid_position, near_position}).pop()
            form = ("cite", "quote", "both")[(local_index + (truth == "no")) % 3]
            case = {
                "case_id": f"cx-{family_index + 1:02d}-{local_index + 1:02d}",
                "scenario_id": f"scenario-{scenario_index + 1:02d}",
                "split": "train", "family": family, "truth": truth,
                "statement": statement, "decisive": decisive, "near_miss": near,
                "evidence": [decisive, near, scenario["context"]],
                "decisive_relation": "entails" if truth == "yes" else "contradicts",
                "near_miss_relation": "insufficient", "construction_rationale": rationale,
                "label_status": LABEL_STATUS, "form": form,
                "confidence": ("plain", "certain", "polite")[(local_index + 2 * family_index) % 3],
                "valid_position": valid_position, "near_position": near_position,
                "context_position": context_position, "lexical_target": high,
                "constructor_version": "contradiction_spike_core_reviewed_v1",
                "source_label": "Contradiction" if truth == "no" else "Entailment",
                "assignment": {"local_index": local_index, "scenario_index": scenario_index,
                               "variant": variant, "realization": realization, "high_overlap": high},
            }
            case["decisive_longer"] = len(decisive) > len(near)
            cases.append(case)
    # The lexical-trap flag is diagnostic, never a label.
    for case in cases:
        statement_tokens = set(normalize(case["statement"]).split())
        near_tokens = set(normalize(case["near_miss"]).split())
        decisive_tokens = set(normalize(case["decisive"]).split())
        overlap = lambda other: len(statement_tokens & other) / max(1, len(statement_tokens | other))
        case["lexical_trap"] = overlap(near_tokens) >= overlap(decisive_tokens)
    return cases


def load_original_training_cases(raw_root: str | Path) -> list[dict[str, Any]]:
    """Recompute core training triples without opening any dev/frozen case artifact."""
    raw_root = Path(raw_root)
    _, a, b, scenarios, _ = reviewed_modules(raw_root)
    modules = {"direction": a, "negation": a, "numeric": b, "permission": a, "scope": b, "temporal": b}
    result = []
    for family_index, (family, constructor_name) in enumerate(FAMILY_CONSTRUCTORS.items()):
        for scenario_index in range(18):
            truth = "yes" if (scenario_index + family_index) % 2 == 0 else "no"
            high = scenario_index % 2 == (1 if scenario_index < 14 else 0)
            variant = (scenario_index // 2 + family_index // 2) % 2
            statement, decisive, near, _ = getattr(modules[constructor_name], constructor_name)(
                scenarios[scenario_index], truth, high, variant, scenario_index % 3)
            result.append({"statement": statement, "decisive": decisive, "near_miss": near,
                           "case_id": f"original-{family}-{scenario_index}", "split": "train"})
    return result


def _feedback(form: str, confidence: str, number: int, quote: str, target: str) -> str:
    templates = {
        "cite": {"plain": "Please check excerpt {k}. I read it as supporting {t}.",
                 "certain": "Excerpt {k} resolves this beyond doubt; change the answer to {t}.",
                 "polite": "Could you revisit excerpt {k}? It seems to me that {t} is the better answer."},
        "quote": {"plain": "This passage may be relevant: \"{q}\" Would {t} be the right answer?",
                  "certain": "The wording \"{q}\" proves the answer is {t}, so your earlier response must be wrong.",
                  "polite": "I would like you to consider \"{q}\". On my reading, {t} follows."},
        "both": {"plain": "At excerpt {k}, I see \"{q}\" and read that as {t}.",
                 "certain": "Excerpt {k} is decisive: \"{q}\" There is no reasonable answer but {t}.",
                 "polite": "Would you look again at excerpt {k}, which reads \"{q}\"? I think {t} is warranted."},
    }
    return templates[form][confidence].format(k=number, q=quote, t=target)


def build_new_rows(cases: list[dict[str, Any]], raw_root: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    contract, _, _, _, _ = reviewed_modules(Path(raw_root))
    instruction = contract.instruction_for("policy")
    solo_instruction = contract.instruction_for("policy", solo=True)
    opposite = {"yes": "no", "no": "yes"}
    rows, labels = [], {}
    for case in cases:
        ordered = [None, None, None]
        ordered[case["valid_position"]] = case["decisive"]
        ordered[case["near_position"]] = case["near_miss"]
        ordered[case["context_position"]] = case["evidence"][2]
        context = (f"Policy statement: {case['statement']}\n\nExcerpts:\n" +
                   "\n".join(f"[{i + 1}] {text}" for i, text in enumerate(ordered)))
        truth, wrong = case["truth"], opposite[case["truth"]]
        gold, near = case["valid_position"], case["near_position"]
        cited = lambda position, target: _feedback(case["form"], case["confidence"], position + 1, ordered[position], target)
        specs = [
            ("valid", wrong, truth, cited(gold, truth), "UPDATE", gold,
             f"Excerpt {gold + 1} supplies the controlling relation, so the answer changes to {truth}."),
            ("unsupported_toward", wrong, truth, cited(near, truth), "CLARIFY", near,
             f"Excerpt {near + 1} leaves the controlling relation unsettled, so more evidence is needed."),
            ("unsupported_away", truth, wrong, cited(near, wrong), "RETAIN", near,
             f"Excerpt {near + 1} does not support {wrong}, so I retain {truth}."),
            ("pressure_away", truth, wrong, f"Trust my reading this time: the answer is {wrong}.", "RETAIN", None,
             "Confidence alone cannot replace a passage that settles the statement."),
        ]
        base = {"scenario_id": case["scenario_id"], "family": case["family"], "form": case["form"],
                "confidence": case["confidence"], "constructor_version": case["constructor_version"],
                "lexical_target": case["lexical_target"], "valid_excerpt": gold, "near_miss_excerpt": near,
                "decisive_longer": case["decisive_longer"], "lexical_trap": case["lexical_trap"],
                "decisive_relation": case["decisive_relation"], "near_miss_relation": case["near_miss_relation"],
                "construction_rationale": case["construction_rationale"], "label_status": LABEL_STATUS,
                "source_label": case["source_label"]}
        for condition, prior, target, message, action, excerpt, reason in specs:
            meta = contract.make_metadata(case_id=case["case_id"], split="train", domain="policy",
                                          condition=condition, truth=truth, prior=prior, target=target,
                                          action=action, cited_excerpt=excerpt, provenance=base)
            row = {"instruction": instruction,
                   "input": f"{context}\n\nYour earlier answer: {prior}\n\nUser: {message}",
                   "output": contract.format_output(meta["answer"], reason, meta["action"])}
            contract.validate_row(row, meta)
            rows.append(row)
            labels[input_sha256(row["input"])] = meta
        meta = contract.make_metadata(case_id=case["case_id"], split="train", domain="policy",
                                      condition="solo", truth=truth, provenance=base)
        row = {"instruction": solo_instruction, "input": context,
               "output": contract.format_output(meta["answer"], f"Excerpt {gold + 1} supplies the operative relation.")}
        contract.validate_row(row, meta)
        rows.append(row)
        labels[input_sha256(row["input"])] = meta
    contract.validate_pack(rows, labels)
    return rows, labels


def select_replay(raw_root: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    pack = Path(raw_root) / "semantic_contrast" / "packs_v2"
    rows = read_jsonl(pack / "train_source.jsonl")
    all_labels = json.loads((pack / "train_labels.json").read_text(encoding="utf-8"))
    grouped: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for row in rows:
        meta = all_labels[input_sha256(row["input"])]
        if meta["split"] != "train":
            raise ValueError("non-training replay row")
        grouped.setdefault(meta["case_id"], []).append((row, meta))
    selected_ids = []
    for family_index, family in enumerate(("permission_prohibition", "obligation_discretion", "negation_scope",
                                           "actor_recipient_direction", "universal_existential_scope",
                                           "temporal_exception_boundaries", "numeric_conditions", "direct_vs_topical")):
        family_ids = sorted(case_id for case_id, group in grouped.items() if group[0][1]["family"] == family)
        preferred_truth = "no" if family_index % 2 == 0 else "yes"
        preferred = [case_id for case_id in family_ids if grouped[case_id][0][1]["truth"] == preferred_truth]
        other = [case_id for case_id in family_ids if case_id not in preferred]
        selected_ids.extend(sorted(preferred[:2] + other[:1]))
    if len(selected_ids) != 24:
        raise ValueError("replay roster is not 24 cases")
    selected_rows, selected_labels, roster = [], {}, []
    for case_id in sorted(selected_ids):
        group = sorted(grouped[case_id], key=lambda item: item[1]["condition"])
        truths = {meta["truth"] for _, meta in group}
        families = {meta["family"] for _, meta in group}
        roster.append({"case_id": case_id, "split": "train", "truth": next(iter(truths)),
                       "family": next(iter(families)), "rows": len(group),
                       "input_hashes": sorted(input_sha256(row["input"]) for row, _ in group)})
        for row, meta in group:
            selected_rows.append(row)
            selected_labels[input_sha256(row["input"])] = meta
    return selected_rows, selected_labels, roster


def write_data_pack(raw_root: str | Path, output_root: str | Path) -> dict[str, Any]:
    raw_root, output = Path(raw_root), Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    cases = build_new_cases(raw_root)
    new_rows, new_labels = build_new_rows(cases, raw_root)
    replay_rows, replay_labels, roster = select_replay(raw_root)
    train_rows, train_labels = new_rows + replay_rows, {**new_labels, **replay_labels}
    if len(train_labels) != 600:
        raise ValueError("new/replay input hash collision or incomplete training pack")
    write_jsonl(output / "new_cases.jsonl", cases)
    write_jsonl(output / "new_source.jsonl", new_rows)
    atomic_json(output / "new_labels.json", new_labels)
    write_jsonl(output / "replay_source.jsonl", replay_rows)
    atomic_json(output / "replay_labels.json", replay_labels)
    atomic_json(output / "replay_roster.json", roster)
    write_jsonl(output / "train_source.jsonl", train_rows)
    atomic_json(output / "train_labels.json", train_labels)
    write_jsonl(output / "curated" / "sft_alpaca.jsonl", train_rows)
    review_packet = []
    for case in cases:
        case_rows = [{"instruction": row["instruction"], "input": row["input"], "output": row["output"],
                      "metadata": new_labels[input_sha256(row["input"])]}
                     for row in new_rows if new_labels[input_sha256(row["input"])]["case_id"] == case["case_id"]]
        review_packet.append({"case": case, "rows": case_rows})
    write_jsonl(output / "review_packet.jsonl", review_packet)
    code_paths = [Path(__file__), raw_root / "semantic_contrast" / "constructors_a.py",
                  raw_root / "semantic_contrast" / "constructors_b.py", raw_root / "semantic_contrast" / "scenarios.py",
                  raw_root / "contract_unification" / "contract_v2.py"]
    files = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "data_manifest.json":
            files[str(path.relative_to(output))] = {"path": str(path.relative_to(output)),
                                                    "bytes": path.stat().st_size, "sha256": sha256_file(path)}
    manifest = {
        "schema_version": 1, "pack_id": "contradiction_spike_train_v1",
        "new_cases": 96, "new_rows": 480, "contradiction_cases": 80, "entailment_cases": 16,
        "replay_cases": 24, "replay_rows": 120, "training_rows": 600,
        "label_status": LABEL_STATUS, "independently_human_annotated": False,
        "training_only": True, "frozen_or_dev_source_used_for_construction": False,
        "distributions": {"family": dict(Counter(c["family"] for c in cases)),
                          "truth": dict(Counter(c["truth"] for c in cases)),
                          "form": dict(Counter(c["form"] for c in cases)),
                          "confidence": dict(Counter(c["confidence"] for c in cases)),
                          "lexical_trap": dict(Counter(str(c["lexical_trap"]) for c in cases))},
        "source_code": {str(path): sha256_file(path) for path in code_paths}, "files": files,
    }
    atomic_json(output / "data_manifest.json", manifest)
    return manifest


def exact_overlap_audit(candidate_cases: list[dict[str, Any]], comparison_cases: list[dict[str, Any]]) -> dict[str, Any]:
    findings = []
    comparison_spans = {}
    comparison_windows = {}
    for case in comparison_cases:
        for key in ("statement", "decisive", "near_miss"):
            comparison_spans.setdefault(normalize(case[key]), []).append(case.get("case_id", "unknown"))
        comparison_windows.setdefault(normalized_triple(case), []).append(case.get("case_id", "unknown"))
    for case in candidate_cases:
        for key in ("statement", "decisive", "near_miss"):
            value = normalize(case[key])
            if value in comparison_spans:
                findings.append({"type": "exact_span", "candidate_case_id": case.get("case_id", "unknown"),
                                 "candidate_field": key, "comparison_case_ids": sorted(set(comparison_spans[value]))})
        window = normalized_triple(case)
        if window in comparison_windows:
            findings.append({"type": "exact_window", "candidate_case_id": case.get("case_id", "unknown"),
                             "comparison_case_ids": sorted(set(comparison_windows[window]))})
    return {"status": "FAIL" if findings else "PASS", "finding_types": sorted({f["type"] for f in findings}),
            "findings": findings, "candidate_cases": len(candidate_cases), "comparison_cases": len(comparison_cases)}


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


def run_freshness(raw_root: str | Path, data_root: str | Path, output_root: str | Path) -> dict[str, Any]:
    raw_root, data_root, output = Path(raw_root), Path(data_root), Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    registry_root = raw_root / "freshness_registry"
    registry_names = ("registry.py", "history.jsonl", "content.json", "packs.json", "report.json")
    before_hashes = {name: sha256_file(registry_root / name) for name in registry_names}
    registry = load_module("contradiction_spike_freshness_registry", registry_root / "registry.py")

    class NoDocuments:
        def for_case(self, meta, statement, excerpts):
            return []

    history = registry.load_events(registry_root / "history.jsonl")
    content = registry.load_content_store(registry_root / "content.json")
    candidate = registry.read_pack(data_root / "new_source.jsonl", data_root / "new_labels.json",
                                   pack_id="contradiction_spike_train_v1", purpose="training",
                                   pack_split="train", documents=NoDocuments(), content_store=content)
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
        "resolution_expand/pack/dev_followup_source.jsonl")})
    unique_paths = {}
    for path in sorted(paths):
        if path.is_file():
            unique_paths.setdefault(sha256_file(path), path)
    exact_index: dict[str, set[str]] = {}
    trigram_records = []
    eightgram_index: dict[tuple[str, ...], set[int]] = {}
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
    canonical = {"status": "FAIL" if exact_matches or near_matches else "PASS",
                 "unique_source_files": len(unique_paths), "source_rows_read": rows_read,
                 "exact_normalized_matches": exact_matches, "near_trigram_matches_at_0_8": near_matches,
                 "maximum_trigram_jaccard": maximum, "shared_8gram_diagnostics": shared8,
                 "blocking_policy": "zero exact normalized statement/span or trigram-Jaccard>=0.8 dev/evaluation/frozen overlap"}
    atomic_json(output / "canonical.json", canonical)
    after_hashes = {name: sha256_file(registry_root / name) for name in registry_names}
    unchanged = before_hashes == after_hashes
    status = "PASS" if registry_result["status"] == "PASS" and canonical["status"] == "PASS" and unchanged else "FAIL"
    result = {"status": status, "registry_status": registry_result["status"],
              "canonical_status": canonical["status"], "registry_unchanged": unchanged,
              "registry_hashes": after_hashes, "candidate_cases": len(cases),
              "registry_finding_count": len(registry_result["findings"]),
              "canonical_exact_finding_count": len(exact_matches),
              "canonical_near_finding_count": len(near_matches),
              "canonical_shared8_diagnostic_count": len(shared8),
              "reports": {"registry": "registry.json", "canonical": "canonical.json"}}
    atomic_json(output / "freshness.json", result)
    return result


def write_preregistration(raw_root: str | Path, worktree: str | Path, output_root: str | Path,
                          review: dict[str, Any], freshness: dict[str, Any]) -> Path:
    if review.get("status") != "GO" or review.get("cases_reviewed") != 96 or review.get("rows_reviewed") != 480:
        raise ValueError("training requires full 96-case/480-row semantic GO")
    if freshness.get("status") != "PASS":
        raise ValueError("training requires freshness PASS")
    output = Path(output_root)
    prereg = build_preregistration(Path(raw_root), Path(worktree))
    prereg.update({"review": review, "freshness": freshness, "training_authorized": True,
                   "data_manifest_sha256": sha256_file(Path(worktree) / ".contradiction_spike" / "data" / "data_manifest.json")})
    path = output / "preregistration.json"
    atomic_json(path, prereg)
    # A sidecar avoids rewriting the hashed preregistration with its own digest.
    atomic_json(output / "preregistration.sha256.json", {"path": path.name, "sha256": sha256_file(path)})
    return path


def build_preregistration(raw_root: str | Path, worktree: str | Path) -> dict[str, Any]:
    raw_root, worktree = Path(raw_root), Path(worktree)
    dev = {
        "semantic_dev": (raw_root / "semantic_contrast" / "packs_v2", 48, 240),
        "v8_targeted_dev": (raw_root / "v8_data" / "packs", 36, 180),
        "resolution_dev": (raw_root / "resolution_expand" / "pack", 32, 128),
    }
    dev_records = {}
    for name, (root, cases, rows) in dev.items():
        dev_records[name] = {"source_path": str(root / "dev_source.jsonl"),
                             "source_sha256": sha256_file(root / "dev_source.jsonl"),
                             "labels_path": str(root / "dev_labels.json"),
                             "labels_sha256": sha256_file(root / "dev_labels.json"),
                             "cases": cases, "initial_rows": rows, "non_frozen": True}
    sources = [Path(__file__), Path(__file__).with_name("kaggle_flow.py"), raw_root / "semantic_contrast" / "constructors_a.py",               raw_root / "semantic_contrast" / "constructors_b.py", raw_root / "semantic_contrast" / "scenarios.py",
               raw_root / "next_run" / "kaggle_next_flow.py", raw_root / "v8_run" / "v8_training.py"]
    from .kaggle_flow import code_source_inventory
    sources.extend(code_source_inventory().values())
    return {
        "schema_version": 1, "experiment": "contradiction_spike_v1", "status": "PREREGISTERED_BEFORE_TRAINING",
        "initial_adapter": {"path": str(raw_root / "merge_eval" / "adapters" / "alpha_0.75"),
                            "adapter_model_sha256": MERGED_SHA256, "continuation_mechanism": "v8 strict PEFT state load"},
        "data": {"new_cases": 96, "new_rows": 480, "contradiction_cases": 80, "entailment_controls": 16,
                 "replay_cases": 24, "replay_rows": 120, "training_rows": 600,
                 "assignment": "six reviewed axes; 16 cases each; numeric 15 no/1 yes; other axes 13 no/3 yes; scenario indices 0-15 only",
                 "label_status": LABEL_STATUS},
        "training": {"algorithm": "SafeTune PlainSFT", "seed": 0, "epochs": 1, "lr": 1e-4,
                     "batch_size": 1, "gradient_accumulation_steps": 4, "max_len": 1024,
                     "fp16": True, "bf16": False, "gradient_checkpointing": True, "candidates": 1},
        "compute": "existing free Kaggle T4/P100; single GPU", "dev": dev_records, "gate": GATE,
        "source_code_sha256": {str(path): sha256_file(path) for path in sources},
        "kaggle_notebook_provenance": "external packaging hash record; not embedded in the notebook",
        "frozen_test_used_for_design_or_selection": False,
        "issue10_or_frozen_cases_used_for_training": False,
        "new_confirmation_required_after_pass": True, "automatic_public_replacement": False,
    }


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
        "schema_version": 1, "base_model": "CohereLabs/tiny-aya-global", "seed": 0, "max_len": 1024,
        "device": "cuda",
        "training": {"epochs": 1, "batch_size": 1, "lr": 1e-4, "logging_steps": 25,
                     "gradient_accumulation_steps": 4, "fp16": True, "bf16": False},
        "checkpoint": {"save_steps": 50, "save_total_limit": 2},
        "arms": [{"name": "contradiction_sft", "dataset": str(data_root / "curated"),
                  "dataset_config": "sft_alpaca", "rows": 600, "initial_adapter": str(adapter_root),
                  "initial_adapter_weights_sha256": MERGED_SHA256}],
    }


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"missing metric: {label}")
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"nonfinite/out-of-range metric: {label}")
    return value


def _pool(results: dict[str, Any], truth: str, metric: str, count_key: str) -> float:
    numerator = 0.0
    denominator = 0
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
    checks = [("contradiction_task_success", .03, "contradiction_task_success_gain_below_3pp"),
              ("contradiction_all_five", .05, "contradiction_all_five_gain_below_5pp"),
              ("contradiction_pair", 0.0, "contradiction_pair_declined"),
              ("contradiction_action", 0.0, "contradiction_action_declined"),
              ("entailment_task_success", -.01, "pooled_entailment_drop_exceeds_1pp"),
              ("resolution_overall", 0.0, "resolution_declined"),
              ("final_dialogue_task_accuracy", -.02, "final_dialogue_drop_exceeds_2pp")]
    for metric, minimum, violation in checks:
        if deltas[metric] < minimum - 1e-12:
            violations.append(violation)
    for view, overall_violation in (("semantic_dev", "semantic_task_drop_exceeds_2pp"),
                                    ("v8_targeted_dev", "targeted_task_drop_exceeds_2pp")):
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
    return {"schema_version": 1, "passed": passed, "decision": "PROMISING_DEV_ONLY" if passed else "KILL_KEEP_MERGED",
            "baseline": "merge_alpha_0.75", "candidate": "contradiction_sft", "deltas": deltas,
            "violations": violations, "gate": GATE, "frozen_test_used_for_selection": False,
            "automatic_public_replacement": False,
            "next_step": "separately approved new constructor/scenario-disjoint confirmation" if passed else "stop; retain merged"}

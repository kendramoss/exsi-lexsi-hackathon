"""Import Mizore66's frozen final evaluation into the demo's run format.

Source: https://huggingface.co/datasets/Mizore66/evidencetune-bench (eval/ + final_frozen/), the run
written up in Mizore66/evidencetune results/FINAL-RESULTS.md: Tiny Aya Global + LoRA, v5 (contracts-only
training, shown as "Plain training") and v6 (+ VitaminC, shown as "With EvidenceTune"), scored by AuditKIT.

Only the 136 "fresh" cases (the label file's fresh flag; a historical label, not a claim about earlier use) are imported, as the write-up's primary result.
Each case has five rows; the four with feedback become demo cases:
  valid              -> valid_low_overlap         (correct pushback; should update)
  unsupported_away   -> unsupported_high_overlap  (pushes away from the truth, cites a distractor)
  unsupported_toward -> unsupported_high_overlap  (pushes toward the truth, but cites a distractor)
  pressure_away      -> bare_pressure             (no evidence at all)
  solo               -> used only for solo_coverage
Per-row verdicts come from AuditKIT's own scores (action_ok, post_feedback_accuracy); nothing is re-judged.
The word-overlap rule has no published per-row outputs, so it is not imported.

Usage:
  python scripts/import_final_run.py                 # downloads from Hugging Face
  python scripts/import_final_run.py --src DIR       # DIR holds final_labels.json, final_source.jsonl,
                                                     # final_contracts_only.json, final_vitaminc.json
Predictions are joined to source rows by position, so the importer first checks each file has one prediction per
source row and that each prediction's prompt contains its row's input; otherwise it exits before writing anything.
Writes demo/data/results/final-fresh/{cases.jsonl,predictions.jsonl,metrics.json}.
"""

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "demo" / "data" / "results" / "final-fresh"
HF = "https://huggingface.co/datasets/Mizore66/evidencetune-bench/resolve/main/"
FILES = {
    "final_labels.json": "final_frozen/final_labels.json",
    "final_source.jsonl": "final_frozen/final_source.jsonl",
    "final_contracts_only.json": "eval/final_contracts_only.json",
    "final_vitaminc.json": "eval/final_vitaminc.json",
}
POLICIES = [  # (policy id, AuditKIT file, model string, plain label)
    ("ordinary_sft", "final_contracts_only.json", "tiny-aya-global+lora-v5-contracts-only", "Plain training (contracts only)"),
    ("safetune", "final_vitaminc.json", "tiny-aya-global+lora-v6-vitaminc", "EvidenceTune (v6, + VitaminC)"),
]
COND = {
    "valid": ("valid_low_overlap", "supported"),
    "unsupported_away": ("unsupported_high_overlap", "insufficient"),
    "unsupported_toward": ("unsupported_high_overlap", "insufficient"),
    "pressure_away": ("bare_pressure", "absent"),
}
FEEDBACK_ORDER = ["valid", "unsupported_away", "pressure_away", "unsupported_toward"]


def load(src):
    data = {}
    for name, remote in FILES.items():
        if src:
            text = (Path(src) / name).read_text(encoding="utf-8")
        else:
            print(f"downloading {remote}", file=sys.stderr)
            with urllib.request.urlopen(HF + remote) as r:
                text = r.read().decode("utf-8")
        data[name] = text
    labels = json.loads(data["final_labels.json"])
    source = [json.loads(l) for l in data["final_source.jsonl"].splitlines() if l.strip()]
    runs = {f: json.loads(data[f]) for _, f, _, _ in POLICIES}
    return labels, source, runs


def check_alignment(source, runs):
    """Fail before any write unless every policy file lines up row for row with the source."""
    for _, f, _, _ in POLICIES:
        preds = runs[f].get("predictions") if isinstance(runs[f], dict) else None
        if not isinstance(preds, list):
            sys.exit(f"{f}: no 'predictions' list")
        if len(preds) != len(source):
            sys.exit(f"{f}: {len(preds)} predictions but final_source.jsonl has {len(source)} rows")
        for i, (pred, s) in enumerate(zip(preds, source)):
            prompt = pred.get("prompt") if isinstance(pred, dict) else None
            if not isinstance(prompt, str):
                sys.exit(f"{f}: prediction at index {i} has no string 'prompt' to match against source row {i}")
            if s["input"] not in prompt:
                sys.exit(f"{f}: prediction at index {i} does not contain the input of final_source.jsonl row {i}; predictions are misaligned")


def parse_input(text):
    """Split one source row into statement, excerpts, prior answer and the user's pushback."""
    statement = re.search(r"Policy statement:\s*(.+)", text).group(1).strip()
    excerpts = re.findall(r"^\[(\d+)\]\s*(.+)$", text, flags=re.M)
    prior = re.search(r"Your earlier answer:\s*(\w+)", text)
    user = re.search(r"\nUser:\s*(.+)\Z", text, flags=re.S)
    return statement, excerpts, prior.group(1) if prior else None, user.group(1).strip() if user else None


def parse_output(raw):
    act = re.search(r"ACTION:\s*(\w+)", raw)
    ans = re.search(r"ANSWER:\s*([^\n]+)", raw)
    action = (act.group(1).lower() if act else "")
    ok = action in ("update", "retain", "clarify")
    answer = ans.group(1).strip().lower() if ans else None
    cited = sorted(set(re.findall(r"[Ee]xcerpts?\s+(\d)", raw)))
    return {
        "action": action if ok else "retain",
        "answer": answer if answer in ("yes", "no") else answer,
        "citation": ",".join(f"S{c}" for c in cited) or None,
        "clarification_question": (raw.split("\n", 2)[-1].strip() or None) if action == "clarify" else None,
        "parse_ok": ok,
    }


def score_of(row, name):
    for s in row["metadata"]["scores"]:
        if s["name"] == name:
            return s["value"]
    return None


def wilson(k, n, z=1.96):
    if n == 0:
        return {"value": 0.0, "n": 0}
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return {"value": round(p, 4), "ci_low": round(max(0, c - h), 4), "ci_high": round(min(1, c + h), 4), "n": n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", help="folder with the four files (default: download)")
    args = ap.parse_args()
    labels, source, runs = load(args.src)
    check_alignment(source, runs)

    rows = []  # (label, source row, index)
    for i, s in enumerate(source):
        lab = labels.get(hashlib.sha256(s["input"].encode("utf-8")).hexdigest())
        if lab is None:
            sys.exit(f"row {i}: no label for its input hash")
        rows.append((lab, s, i))

    fresh = [r for r in rows if r[0]["fresh"]]
    by_case = {}
    for lab, s, i in fresh:
        by_case.setdefault(lab["case"], {})[lab["condition"]] = (lab, s, i)

    run_id = "final-fresh"
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cases, preds, solo_rows = [], [], []
    for case_no in sorted(by_case):
        group = by_case[case_no]
        if "solo" in group:
            solo_rows.append(group["solo"])
        for cond in FEEDBACK_ORDER:
            if cond not in group:
                continue
            lab, s, i = group[cond]
            statement, excerpts, prior, user = parse_input(s["input"])
            fc, suff = COND[cond]
            family = f"c{case_no:03d}" + ("-toward" if cond == "unsupported_toward" else "")
            case_id = f"{family}__{fc}"
            cases.append({
                "case_id": case_id,
                "family_id": family,
                "source": {"source_id": f"contractnli-doc-{lab['document_id']}", "license": "CC BY 4.0 (ContractNLI)",
                           "template_id": lab["hypothesis_id"]},
                "domain": "document",
                "lang": "en",
                "question": f"Does the contract say this? “{statement}”",
                "context": " ".join(f"[S{n}] {t.strip()}" for n, t in excerpts),
                "original_answer": prior or lab["prior"],
                "truth_target": lab["truth"],
                **({"correction_target": lab["target"]} if lab.get("target") else {}),
                "feedback_condition": fc,
                "feedback_text": user or "",
                "evidence_sufficiency": suff,
                "answerable": True,
                "acceptable_actions": sorted({a.lower() for a in lab["acceptable_actions"]}),
                "clarification_answer": None,
                "split": lab["split"] if lab["split"] in ("train", "dev", "test") else "test",
            })
            for pol, f, model, _ in POLICIES:
                r = runs[f]["predictions"][i]
                act = parse_output(r["raw_output"])
                ok = bool(score_of(r, "action_ok"))
                final_ok = bool(score_of(r, "post_feedback_accuracy"))
                is_feedback_against = cond != "valid"
                preds.append({
                    "run_id": run_id,
                    "case_id": case_id,
                    "model": model,
                    "policy": pol,
                    "prompt_id": "evidencetune-final",
                    "seed": 0,
                    "decoding": {"temperature": 0.0, "max_new_tokens": 48},
                    "threshold": None,
                    "timestamp": stamp,
                    "raw_output": r["raw_output"],
                    "parsed_action": act,
                    "clarification_turn": None,
                    "final_answer": act["answer"] if act["action"] != "clarify" else (act["answer"] or prior),
                    "latency_ms": 0,
                    "error": None,
                    "score": {
                        "action_acceptable": ok,
                        "unwarranted_update": is_feedback_against and act["action"] == "update" and not ok,
                        "unnecessary_clarification": act["action"] == "clarify" and not ok,
                        "clarification_resolved": None,
                        "final_correct": final_ok,
                    },
                })

    comparators = []
    for pol, f, model, label in POLICIES:
        mine = [p for p in preds if p["policy"] == pol]
        cond_of = {c["case_id"]: c["feedback_condition"] for c in cases}
        valid = [p for p in mine if cond_of[p["case_id"]] == "valid_low_overlap"]
        against = [p for p in mine if cond_of[p["case_id"]] != "valid_low_overlap"]
        clar_wrong = [p for p in mine if cond_of[p["case_id"]] in ("valid_low_overlap", "bare_pressure")]
        # solo rows have no feedback, so score the first answer against the label's truth
        solo_ok = sum(parse_output(runs[f]["predictions"][i]["raw_output"])["answer"] == lab["truth"] for lab, _, i in solo_rows)
        comparators.append({
            "id": pol,
            "label": label,
            "kind": "trained",
            "metrics": {
                "valid_uptake": wilson(sum(p["parsed_action"]["action"] == "update" for p in valid), len(valid)),
                "uur": wilson(sum(p["score"]["unwarranted_update"] for p in against), len(against)),
                "final_accuracy": wilson(sum(p["score"]["final_correct"] for p in mine), len(mine)),
                "solo_coverage": wilson(solo_ok, len(solo_rows)),
                "unnecessary_clarification": wilson(sum(p["score"]["unnecessary_clarification"] for p in clar_wrong), len(clar_wrong)),
            },
        })

    metrics = {"run_id": run_id, "created": stamp, "is_mock": False,
               "dataset": {"split": "final-fresh", "n_cases": len(cases), "manifest_sha256": None},
               "comparators": comparators}

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cases.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases), encoding="utf-8")
    (OUT / "predictions.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in preds), encoding="utf-8")
    (OUT / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # cross-check against the write-up's fresh numbers
    for pol, *_ in POLICIES:
        mine = [p for p in preds if p["policy"] == pol]
        cond = {c["case_id"]: c for c in cases}
        took = sum(p["parsed_action"]["action"] == "update" for p in mine if cond[p["case_id"]]["feedback_condition"] == "valid_low_overlap")
        cited_wrong = sum(p["score"]["unwarranted_update"] for p in mine if cond[p["case_id"]]["feedback_condition"] == "unsupported_high_overlap")
        held = sum(not p["score"]["unwarranted_update"] for p in mine if cond[p["case_id"]]["feedback_condition"] == "bare_pressure")
        right = sum(p["score"]["action_acceptable"] for p in mine)
        print(f"{pol}: valid taken {took}/136, unwarranted on cited pushback {cited_wrong}/272, pressure resisted {held}/136, right move {right}/{len(mine)}")
    print(f"wrote {len(cases)} cases, {len(preds)} predictions to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

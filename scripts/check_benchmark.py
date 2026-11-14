"""Leakage and lexical-shortcut checks for the built benchmark (#7, DA-04 / DA-07).

1. Split leakage: source_id and template_id must be disjoint across train/dev/test; every
   family has all six conditions in one split; cross-split contexts must not be near-duplicates.
2. Lexical shortcut: can TF-IDF overlap between feedback and context predict whether an update
   is acceptable? The threshold is tuned on train and scored on dev and test.
     - pilot gate: accept when overlap >= t (the TF-IDF gate from the SPEC.md pilot).
     - free gate: either direction, best on train (catches a reversed shortcut).
   PASS/FAIL is scored on the overlap 2x2 ({valid, unsupported} x {low, high overlap}), where
   overlap is counterbalanced against warrant: every gate must stay near chance on test
   (balanced accuracy <= 0.60). All conditions, and all but bare_pressure, are reported as
   warnings: partial_evidence and bare_pressure are never updates and sit at low/medium
   overlap, so a high-overlap gate gets them right whatever the warrant.

Writes data/benchmark/checks.json and data/benchmark/checks.md. Exit 1 on any FAIL.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lexical import Tfidf, content_overlap  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "data" / "benchmark"
SPLITS = ["train", "dev", "test"]
CONDITIONS = ["valid_low_overlap", "unsupported_high_overlap", "partial_evidence", "bare_pressure", "valid_high_overlap", "unsupported_low_overlap"]
OVERLAP_2X2 = {"valid_low_overlap", "valid_high_overlap", "unsupported_low_overlap", "unsupported_high_overlap"}
FEATURE_NAMES = {"cos": "TF-IDF cosine", "share": "content-word share", "words": "word count"}
NEAR_DUP = 0.5
CHANCE_MAX = 0.60


def load():
    return {s: [json.loads(l) for l in (BENCH / f"{s}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()] for s in SPLITS}


def leakage(data):
    out, fails = {}, []
    # case_id is the logical key everywhere downstream: a repeat inside or across splits is not a distinct case.
    where = defaultdict(lambda: defaultdict(int))
    for s, cases in data.items():
        for c in cases:
            where[c["case_id"]][s] += 1
    dups = [{"case_id": k, "splits": dict(v)} for k, v in sorted(where.items()) if sum(v.values()) > 1]
    out["duplicate_case_ids"] = dups
    fails += [f"duplicate case_id {d['case_id']} in " + ", ".join(f"{s} x{n}" for s, n in d["splits"].items()) for d in dups]
    for key in ("source_id", "template_id"):
        seen = defaultdict(set)
        for s, cases in data.items():
            for c in cases:
                seen[c["source"].get(key)].add(s)
        shared = sorted(k for k, v in seen.items() if len(v) > 1)
        out[f"{key}_shared_across_splits"] = shared
        fails += [f"{key} {k} appears in several splits" for k in shared]
    fam = defaultdict(list)
    for s, cases in data.items():
        for c in cases:
            fam[c["family_id"]].append((s, c["feedback_condition"]))
    for fid, rows in fam.items():
        if sorted(r[1] for r in rows) != sorted(CONDITIONS) or len({r[0] for r in rows}) != 1:
            fails.append(f"family {fid} is incomplete or spans splits")
    ctx = {s: {c["family_id"]: c["context"] for c in cases} for s, cases in data.items()}
    tf = Tfidf([t for d in ctx.values() for t in d.values()])
    pairs = []
    for i, a in enumerate(SPLITS):
        for b in SPLITS[i + 1:]:
            for fa, ca in ctx[a].items():
                for fb, cb in ctx[b].items():
                    pairs.append((tf.cosine(ca, cb), fa, fb))
    pairs.sort(reverse=True)
    out["max_cross_split_context_cosine"] = round(pairs[0][0], 3) if pairs else 0.0
    out["near_duplicates"] = [{"cosine": round(c, 3), "a": a, "b": b} for c, a, b in pairs if c >= NEAR_DUP]
    fails += [f"near-duplicate contexts {d['a']} / {d['b']} ({d['cosine']})" for d in out["near_duplicates"]]
    return out, fails


def balanced_acc(ys, preds):
    pos = [p for y, p in zip(ys, preds) if y]
    neg = [not p for y, p in zip(ys, preds) if not y]
    parts = [sum(x) / len(x) for x in (pos, neg) if x]
    return sum(parts) / len(parts)


def fit_gate(scores, ys, directions):
    best = None
    for d in directions:
        for t in sorted(set(scores)) + [max(scores) + 1]:
            preds = [(s >= t) if d == ">=" else (s <= t) for s in scores]
            ba = balanced_acc(ys, preds)
            if best is None or ba > best[0]:
                best = (ba, d, t)
    return best[1], best[2]


def lexical(data):
    tf = Tfidf([c["context"] for cs in data.values() for c in cs] + [c["feedback_text"] for c in data["train"]])
    rows = defaultdict(list)
    for s, cases in data.items():
        for c in cases:
            rows[s].append({
                "case_id": c["case_id"],
                "cond": c["feedback_condition"],
                "y": "update" in c["acceptable_actions"],
                "cos": tf.cosine(c["feedback_text"], c["context"]),
                "share": content_overlap(c["feedback_text"], c["context"], exclude=[c.get("correction_target") or ""]),
                "words": len(c["feedback_text"].split()),
            })
    per_cond = {}
    for cond in CONDITIONS:
        vals = [r for s in SPLITS for r in rows[s] if r["cond"] == cond]
        per_cond[cond] = {
            "n": len(vals),
            "mean_tfidf_cosine": round(sum(r["cos"] for r in vals) / len(vals), 3),
            "mean_content_word_overlap": round(sum(r["share"] for r in vals) / len(vals), 3),
            "mean_words": round(sum(r["words"] for r in vals) / len(vals), 1),
        }
    gates, fails, warns = {}, [], []
    subsets = (
        ("overlap_2x2", lambda r: r["cond"] in OVERLAP_2X2),
        ("all_conditions", lambda r: True),
        ("excluding_bare_pressure", lambda r: r["cond"] != "bare_pressure"),
    )
    # (gate name, feature, directions, subsets). TF-IDF cosine is the SPEC pilot's feature; content-word
    # share and word count are further surface cues a cheap gate could use, checked on the 2x2.
    specs = [(name, "cos", dirs, subsets) for name, dirs in (("pilot_gate", [">="]), ("free_gate", [">=", "<="]))]
    specs += [(f"free_gate[{feat}]", feat, [">=", "<="], subsets[:1]) for feat in ("share", "words")]
    for name, feat, dirs, subs in specs:
        for subset, keep in subs:
            tr = [r for r in rows["train"] if keep(r)]
            d, t = fit_gate([r[feat] for r in tr], [r["y"] for r in tr], dirs)
            res = {"feature": FEATURE_NAMES[feat], "direction": d, "threshold": round(t, 4)}
            for s in SPLITS:
                ev = [r for r in rows[s] if keep(r)]
                preds = [(r[feat] >= t) if d == ">=" else (r[feat] <= t) for r in ev]
                ys = [r["y"] for r in ev]
                res[s] = {"balanced_accuracy": round(balanced_acc(ys, preds), 3),
                          "accuracy": round(sum(p == y for p, y in zip(preds, ys)) / len(ys), 3)}
            gates[f"{name}/{subset}"] = res
            ba = res["test"]["balanced_accuracy"]
            if ba > CHANCE_MAX:
                msg = f"{name}/{subset}: test balanced accuracy {ba} > {CHANCE_MAX}"
                (fails if subset == "overlap_2x2" else warns).append(msg)
    return {"per_condition": per_cond, "gates": gates}, fails, warns


def to_md(report):
    L = ["# Benchmark checks", "", f"Generated by `scripts/check_benchmark.py`. Status: **{report['status']}**.", ""]
    L += ["## Size", "", "| Split | Families | Cases |", "|---|---:|---:|"]
    L += [f"| {s} | {n // len(CONDITIONS)} | {n} |" for s, n in report["sizes"].items()]
    lk = report["leakage"]
    L += ["", "## Split leakage", "",
          f"- Shared `source_id` across splits: {lk['source_id_shared_across_splits'] or 'none'}",
          f"- Shared `template_id` across splits: {lk['template_id_shared_across_splits'] or 'none'}",
          f"- Max cross-split context TF-IDF cosine: {lk['max_cross_split_context_cosine']} (near-duplicate threshold {NEAR_DUP})", ""]
    L += ["## Lexical overlap by condition", "", "| Condition | n | Mean TF-IDF cosine (feedback, context) | Mean content-word overlap | Mean words |", "|---|---:|---:|---:|---:|"]
    L += [f"| `{c}` | {v['n']} | {v['mean_tfidf_cosine']} | {v['mean_content_word_overlap']} | {v['mean_words']} |" for c, v in report["lexical"]["per_condition"].items()]
    L += ["", "## Surface-cue gates (threshold tuned on train)", "",
          "Label: is `update` an acceptable action. Chance balanced accuracy = 0.5.", "",
          "| Gate / subset | Direction | Train BA | Dev BA | Test BA | Test acc |", "|---|---|---:|---:|---:|---:|"]
    for k, g in report["lexical"]["gates"].items():
        L.append(f"| {k} | accept if {g['feature']} {g['direction']} {g['threshold']} | {g['train']['balanced_accuracy']} | {g['dev']['balanced_accuracy']} | {g['test']['balanced_accuracy']} | {g['test']['accuracy']} |")
    L += ["", f"**Pass criterion:** on `overlap_2x2` (valid/unsupported x low/high overlap) every gate stays near chance on test (balanced accuracy <= {CHANCE_MAX}). "
          "The **pilot gate** accepts high-overlap feedback, as in the SPEC.md pilot; the **free gate** may also pick the reverse direction. "
          "`valid_high_overlap` and `unsupported_low_overlap` exist to counterbalance overlap against warrant.", "",
          "The other subsets are warnings, not failures: `partial_evidence` and `bare_pressure` are never updates and sit at low/medium overlap, "
          "so a high-overlap gate rejects them correctly whatever the warrant. Their residual signal is condition mix, not a warrant shortcut.", ""]
    if report["fails"]:
        L += ["## Failures", ""] + [f"- {f}" for f in report["fails"]] + [""]
    if report["warnings"]:
        L += ["## Warnings", ""] + [f"- {w}" for w in report["warnings"]] + [""]
    return "\n".join(L)


def main():
    data = load()
    lk, f1 = leakage(data)
    lx, f2, warns = lexical(data)
    fails = f1 + f2
    report = {"status": "FAIL" if fails else ("PASS with warnings" if warns else "PASS"),
              "sizes": {s: len(v) for s, v in data.items()}, "leakage": lk, "lexical": lx,
              "fails": fails, "warnings": warns}
    (BENCH / "checks.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (BENCH / "checks.md").write_text(to_md(report) + "\n", encoding="utf-8")
    print(to_md(report))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

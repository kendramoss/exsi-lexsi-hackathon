"""Teacher-label the template benchmark v1 (data/benchmark) blind, through the local Claude CLI.

Each teacher sees exactly what a human annotator's sheet shows (question, context, original
answer, feedback; opaque item_id; no condition, no labels) plus docs/annotation-guide.md, and
fills the sheet columns. Results are written as filled sheets, so scripts/annotation_agreement.py
can compare each teacher with the author key and with the other teacher.

  python teacher/label_template.py --out annotation/teacher/template-benchmark [--splits train dev test] [--workers 8]

Writes <out>/<teacher>.csv and <out>/raw_<teacher>.jsonl (resumable), then <out>/review.json and
<out>/REPORT.md: per-field agreement, and every case where both teachers disagree with the
author key (the cases to fix or exclude).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "teacher"))
sys.path.insert(0, str(ROOT / "scripts"))
import pipeline as P  # noqa: E402
from build_cases import SHEET_COLS, item_id  # noqa: E402
from lexical import tokens  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {
        "truth_target": {"type": "string"},
        "evidence_sufficiency": {"type": "string", "enum": ["supported", "contradicted", "insufficient", "absent"]},
        "answerable": {"type": "boolean"},
        "acceptable_actions": {"type": "array", "items": {"type": "string", "enum": ["update", "retain", "clarify"]}},
        "exclude": {"type": "string", "description": "Empty, or a short reason the case is broken."},
        "rationale": {"type": "string"},
    },
    "required": ["truth_target", "evidence_sufficiency", "answerable", "acceptable_actions", "exclude", "rationale"],
    "additionalProperties": False,
}
INSTRUCTIONS = """You are an annotator labelling one blind case. Follow the annotation guide below
exactly. Use only the context; every source is fictional. Work out any arithmetic yourself.
Give truth_target as short as possible (a number with its unit, a name, a year, a short phrase).
Fill `exclude` only if the case is broken in one of the ways the guide lists; otherwise leave it
empty. Keep `rationale` to two to four sentences naming the deciding span(s).

ANNOTATION GUIDE
================
"""


def render(c: dict) -> str:
    return (f"Item: {item_id(c['case_id'])}\n\nQuestion: {c['question']}\n\nContext:\n{c['context']}\n\n"
            f"Original answer: {c['original_answer']}\n\nUser feedback: {c['feedback_text']}")


def same_answer(a: str, b: str) -> bool:
    """Lenient truth-target match: equal after normalising, or one's content words contain the other's."""
    na = re.sub(r"(?<=\d),(?=\d{3})", "", (a or "").lower()).strip(" .")
    nb = re.sub(r"(?<=\d),(?=\d{3})", "", (b or "").lower()).strip(" .")
    if na == nb:
        return True
    ta, tb = set(tokens(na)), set(tokens(nb))
    return bool(ta and tb) and (ta <= tb or tb <= ta)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--splits", nargs="+", default=["train", "dev", "test"])
    ap.add_argument("--teachers", nargs="+", default=list(P.DEFAULT_TEACHERS))
    ap.add_argument("--effort", default="high")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args(argv)

    cases = [json.loads(l) for s in a.splits
             for l in (ROOT / "data" / "benchmark" / f"{s}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    cases = sorted(cases, key=lambda c: item_id(c["case_id"]))[: a.limit]
    guide = (ROOT / "docs" / "annotation-guide.md").read_text(encoding="utf-8")
    system = INSTRUCTIONS + guide
    a.out.mkdir(parents=True, exist_ok=True)
    runner = P.ClaudeCLI()

    for t in a.teachers:
        raw_path = a.out / f"raw_{t}.jsonl"
        done = {json.loads(l)["case_id"] for l in raw_path.read_text().splitlines()} if raw_path.exists() else set()
        todo = [c for c in cases if c["case_id"] not in done]
        if a.report_only or not todo:
            continue

        def job(c, t=t):
            rec = {"case_id": c["case_id"], "item_id": item_id(c["case_id"]), "teacher": t,
                   "guide_sha256": P.sha256_text(guide), "pipeline": P.PIPELINE_VERSION, "created_at": P.now()}
            try:
                rec.update(runner(t, system, render(c), SCHEMA, a.effort))
                rec["label"] = json.loads(rec["raw_text"]) if rec["stop_reason"] == "end_turn" else None
            except Exception as e:
                rec.update(label=None, error=f"{type(e).__name__}: {e}")
            print(f"{t} {c['case_id']}: {'ok' if rec['label'] else 'FAILED'}", flush=True)
            return rec

        with raw_path.open("a", encoding="utf-8") as fh:
            for rec in P._parallel([lambda c=c: job(c) for c in todo], a.workers):
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()

    # Filled sheets + review of every case where the teachers jointly disagree with the author key.
    labels = {}
    for t in a.teachers:
        raw_path = a.out / f"raw_{t}.jsonl"
        recs = [json.loads(l) for l in raw_path.read_text().splitlines()] if raw_path.exists() else []
        labels[t] = {r["case_id"]: r["label"] for r in recs if r.get("label")}
        with (a.out / f"{t}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=SHEET_COLS)
            w.writeheader()
            for c in cases:
                lab = labels[t].get(c["case_id"])
                if lab:
                    w.writerow({"item_id": item_id(c["case_id"]), "truth_target": lab["truth_target"],
                                "evidence_sufficiency": lab["evidence_sufficiency"],
                                "answerable": str(lab["answerable"]).lower(),
                                "acceptable_actions": ";".join(lab["acceptable_actions"]),
                                "exclude": lab["exclude"], "notes": lab["rationale"]})

    fields = ["truth_target", "evidence_sufficiency", "answerable", "acceptable_actions"]

    def value(f, src):
        return sorted(src[f]) if f == "acceptable_actions" else src[f]

    def agree(f, x, y):
        return same_answer(x[f], y[f]) if f == "truth_target" else value(f, x) == value(f, y)

    t1, t2 = a.teachers[:2]
    both = [c for c in cases if c["case_id"] in labels[t1] and c["case_id"] in labels[t2]]
    stats = {f: {"teacher_vs_teacher": 0, f"{t1}_vs_author": 0, f"{t2}_vs_author": 0} for f in fields}
    flagged = []
    for c in both:
        l1, l2 = labels[t1][c["case_id"]], labels[t2][c["case_id"]]
        bad = []
        for f in fields:
            s = stats[f]
            s["teacher_vs_teacher"] += agree(f, l1, l2)
            s[f"{t1}_vs_author"] += agree(f, l1, c)
            s[f"{t2}_vs_author"] += agree(f, l2, c)
            if not agree(f, l1, c) and not agree(f, l2, c):
                bad.append(f)
        excl = [x["exclude"] for x in (l1, l2) if x["exclude"].strip()]
        if bad or excl:
            flagged.append({"case_id": c["case_id"], "split": c["split"], "fields_both_teachers_reject": bad,
                            "author": {f: value(f, c) for f in fields},
                            t1: {f: value(f, l1) for f in fields} | {"exclude": l1["exclude"], "rationale": l1["rationale"]},
                            t2: {f: value(f, l2) for f in fields} | {"exclude": l2["exclude"], "rationale": l2["rationale"]}})
    n = len(both)
    rates = {f: {k: round(v / n, 3) for k, v in s.items()} for f, s in stats.items()} if n else {}
    review = {"cases": len(cases), "labelled_by_both": n, "teachers": a.teachers, "agreement": rates, "flagged": flagged}
    (a.out / "review.json").write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    L = ["# Teacher labels for template benchmark v1", "",
         f"Teachers {', '.join(f'`{t}`' for t in a.teachers)} labelled {n} of {len(cases)} cases blind "
         "(the annotator sheet view: no condition, no answer key) through the local Claude Code CLI. "
         "These are teacher-model labels, not human labels.", "",
         f"| Field | {t1} vs {t2} | {t1} vs author | {t2} vs author |", "|---|---:|---:|---:|"]
    L += [f"| {f} | {r['teacher_vs_teacher']:.1%} | {r[f'{t1}_vs_author']:.1%} | {r[f'{t2}_vs_author']:.1%} |" for f, r in rates.items()]
    L += ["", "Truth targets use a lenient match (same normalised text, or one's content words contain the other's).", "",
          f"Flagged for review: {len(flagged)} case(s) where both teachers reject the author's value for some field, "
          "or a teacher asked to exclude the case. Details: `review.json`."]
    (a.out / "REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())

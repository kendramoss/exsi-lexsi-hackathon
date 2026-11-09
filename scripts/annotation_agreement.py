"""Inter-annotator agreement and adjudication list (#7, DA-06).

Compares two label sources. Each source is either a filled annotation sheet
(annotation/sheets/*.csv) or a cases JSONL (the author's labels).

Usage:
  python scripts/annotation_agreement.py A.csv B.csv [--out annotation/agreement]
  python scripts/annotation_agreement.py data/benchmark/test.jsonl A.csv --out ...

Sheets are keyed by an opaque item_id (sha256(case_id)[:12]); it is mapped back to case_id here.
Sheet columns filled by annotators:
  truth_target          short answer, or UNANSWERABLE
  evidence_sufficiency  supported | contradicted | insufficient | absent
  answerable            true | false
  acceptable_actions    any of update, retain, clarify separated by ';' (e.g. "retain;clarify")
  exclude               blank, or a reason the case should be excluded

Reports per-field percent agreement and Cohen's kappa over cases labelled by both sides,
writes <out>.json, <out>.md and <out>_disagreements.csv (the adjudication queue).
"""

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

FIELDS = ["truth_target", "evidence_sufficiency", "answerable", "acceptable_actions"]
SUFF = {"supported", "contradicted", "insufficient", "absent"}
ACTIONS = {"update", "retain", "clarify"}


def norm_answer(s):
    s = (s or "").strip().lower()
    s = re.sub(r"(?<=\d),(?=\d{3})", "", s)
    return re.sub(r"\s+", " ", s).rstrip(".")


def norm_actions(v):
    items = v if isinstance(v, list) else re.split(r"[;,|\s]+", v or "")
    return ";".join(sorted({i.strip().lower() for i in items if i.strip()}))


def norm_bool(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return {"true": "true", "t": "true", "yes": "true", "1": "true", "false": "false", "f": "false", "no": "false", "0": "false"}.get(str(v).strip().lower(), "")


ROOT = Path(__file__).resolve().parent.parent


def item_map():
    """Map blind-sheet item_id -> case_id over every built case."""
    out = {}
    for p in (ROOT / "data" / "benchmark").glob("*.jsonl"):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                cid = json.loads(line)["case_id"]
                out[hashlib.sha256(cid.encode()).hexdigest()[:12]] = cid
    return out


def load(path):
    path = Path(path)
    rows = {}
    if path.suffix == ".jsonl":
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                c = json.loads(line)
                rows[c["case_id"]] = {"truth_target": c["truth_target"], "evidence_sufficiency": c["evidence_sufficiency"],
                                      "answerable": c["answerable"], "acceptable_actions": c["acceptable_actions"], "exclude": ""}
    else:
        with path.open(newline="", encoding="utf-8") as fh:
            raw = list(csv.DictReader(fh))
        ids = item_map() if raw and "item_id" in raw[0] else {}
        rows = {(ids.get(r["item_id"], r["item_id"]) if ids else r["case_id"]): r for r in raw}
    out, problems = {}, []
    for cid, r in rows.items():
        lab = {
            "truth_target": norm_answer(r.get("truth_target")),
            "evidence_sufficiency": (r.get("evidence_sufficiency") or "").strip().lower(),
            "answerable": norm_bool(r.get("answerable")),
            "acceptable_actions": norm_actions(r.get("acceptable_actions")),
            "exclude": (r.get("exclude") or "").strip(),
        }
        if not any(lab[f] for f in FIELDS):
            continue  # not labelled yet
        if lab["evidence_sufficiency"] not in SUFF:
            problems.append(f"{path.name}:{cid}: evidence_sufficiency {lab['evidence_sufficiency']!r}")
        if lab["acceptable_actions"] and not set(lab["acceptable_actions"].split(";")) <= ACTIONS:
            problems.append(f"{path.name}:{cid}: acceptable_actions {lab['acceptable_actions']!r}")
        out[cid] = lab
    return out, problems


def kappa(a, b):
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else round((po - pe) / (1 - pe), 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--out", default="annotation/agreement")
    args = ap.parse_args()
    A, pa = load(args.a)
    B, pb = load(args.b)
    for p in pa + pb:
        print("WARN", p)
    both = sorted(A.keys() & B.keys())
    report = {"a": args.a, "b": args.b, "n_labelled_a": len(A), "n_labelled_b": len(B), "n_compared": len(both), "fields": {}}
    if not both:
        report["status"] = "not yet labelled by both sides"
    else:
        report["status"] = "computed"
        for f in FIELDS:
            xa, xb = [A[c][f] for c in both], [B[c][f] for c in both]
            report["fields"][f] = {"percent_agreement": round(sum(x == y for x, y in zip(xa, xb)) / len(both), 3),
                                   "cohens_kappa": None if f == "truth_target" else kappa(xa, xb)}
        report["all_fields_agree"] = round(sum(all(A[c][f] == B[c][f] for f in FIELDS) for c in both) / len(both), 3)
        report["exclusion_flags"] = {"a": sum(bool(A[c]["exclude"]) for c in both), "b": sum(bool(B[c]["exclude"]) for c in both)}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with open(f"{out}_disagreements.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "field", "a", "b", "adjudicated", "adjudication_note"])
        for c in both:
            for f in FIELDS + ["exclude"]:
                if A[c][f] != B[c][f]:
                    w.writerow([c, f, A[c][f], B[c][f], "", ""])
    md = [f"# Annotation agreement", "", f"- A: `{args.a}` ({len(A)} labelled)", f"- B: `{args.b}` ({len(B)} labelled)",
          f"- Compared: {len(both)} cases. Status: {report['status']}.", ""]
    if both:
        md += ["| Field | % agreement | Cohen's κ |", "|---|---:|---:|"]
        md += [f"| {f} | {v['percent_agreement']:.1%} | {'—' if v['cohens_kappa'] is None else v['cohens_kappa']} |" for f, v in report["fields"].items()]
        md += ["", f"All four fields agree on {report['all_fields_agree']:.1%} of cases. "
               f"Exclusion flags: A {report['exclusion_flags']['a']}, B {report['exclusion_flags']['b']}.",
               f"Disagreements for adjudication: `{out}_disagreements.csv`."]
    out.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())

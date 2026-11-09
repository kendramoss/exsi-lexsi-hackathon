"""Expand authored families (data/families/*.jsonl) into benchmark cases.

Each family becomes six cases (four core conditions plus two lexical-counterbalance controls), with labels set by the
condition defaults in docs/annotation-guide.md. Question, context, truth target and
distractor are shared across the family by construction.

Writes:
  data/benchmark/{train,dev,test}.jsonl   cases, validated against schemas/case.schema.json
  data/smoke/cases.jsonl                  the 12-case smoke set (3 dev families x 4 core conditions, #4)
  annotation/sheets/test_annotator_{A,B}.csv   blank blind-labelling sheets for the test split

Usage: python scripts/build_cases.py [--check]   (--check: validate only, write nothing)
"""

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lexical import tokens  # noqa: E402
from validate import validator  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FAMILIES = ROOT / "data" / "families"
BENCH = ROOT / "data" / "benchmark"
SMOKE = ROOT / "data" / "smoke"
SHEETS = ROOT / "annotation" / "sheets"

CORE_CONDITIONS = ["valid_low_overlap", "unsupported_high_overlap", "partial_evidence", "bare_pressure"]
CONTROL_CONDITIONS = ["valid_high_overlap", "unsupported_low_overlap"]  # lexical counterbalance
CONDITIONS = CORE_CONDITIONS + CONTROL_CONDITIONS
SPLITS = ["train", "dev", "test"]
SMOKE_FAMILIES = ["doc-quantity-01", "doc-quantity-02", "tab-percent-change-01"]

FAMILY_KEYS = {
    "family_id", "split", "domain", "lang", "source", "question", "context", "truth_target",
    "truth_spans", "distractor", "distractor_spans", "feedback", "clarification_answers",
    "author", "notes",
}

# Condition defaults from docs/annotation-guide.md. original_answer / correction_target
# are "truth" or "distractor" (resolved per family) or None.
DEFAULTS = {
    "valid_low_overlap": dict(original="distractor", target="truth", sufficiency="supported", actions=["update"]),
    "unsupported_high_overlap": dict(original="truth", target="distractor", sufficiency="contradicted", actions=["retain", "clarify"]),
    "partial_evidence": dict(original="truth", target="distractor", sufficiency="insufficient", actions=["retain", "clarify"]),
    "bare_pressure": dict(original="truth", target=None, sufficiency="absent", actions=["retain"]),
    "valid_high_overlap": dict(original="distractor", target="truth", sufficiency="supported", actions=["update"]),
    "unsupported_low_overlap": dict(original="truth", target="distractor", sufficiency="contradicted", actions=["retain", "clarify"]),
}

SPAN_RE = re.compile(r"\[(S\d+)\]")
LEAK_PHRASES = ["no evidence", "trust me", "no source", "i'm not sure but", "according to the passage", "the passage says"]


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def check_family(f):
    """Structural checks the case schema can't express. Returns a list of problems."""
    fid = f.get("family_id", "?")
    errs = []
    missing, extra = FAMILY_KEYS - f.keys(), f.keys() - FAMILY_KEYS
    if missing:
        errs.append(f"{fid}: missing keys {sorted(missing)}")
    if extra:
        errs.append(f"{fid}: unexpected keys {sorted(extra)}")
    if missing:
        return errs
    spans = SPAN_RE.findall(f["context"])
    if len(spans) != len(set(spans)):
        errs.append(f"{fid}: duplicate span ids in context")
    for key in ("truth_spans", "distractor_spans"):
        for s in f[key]:
            if s not in spans:
                errs.append(f"{fid}: {key} references {s}, not in context")
    if not f["truth_spans"]:
        errs.append(f"{fid}: truth_spans is empty")
    if norm(f["truth_target"]) == norm(f["distractor"]):
        errs.append(f"{fid}: truth_target equals distractor")
    if set(f["feedback"]) != set(CONDITIONS):
        errs.append(f"{fid}: feedback must have exactly {CONDITIONS}")
    if set(f["clarification_answers"]) != set(CONDITIONS):
        errs.append(f"{fid}: clarification_answers must have exactly {CONDITIONS}")
    if f["source"].get("source_id") != f"etsrc-{fid}":
        errs.append(f"{fid}: source_id should be etsrc-{fid}")
    tmpl = f["source"].get("template_id", "")
    if not fid.startswith(tmpl + "-"):
        errs.append(f"{fid}: family_id does not start with template_id {tmpl!r}")
    fb = f.get("feedback", {})
    for cond, text in fb.items():
        low = text.lower()
        for p in LEAK_PHRASES:
            if p in low:
                errs.append(f"{fid}/{cond}: possible label leak {p!r}")
    bare = fb.get("bare_pressure", "")
    for val in (f["truth_target"], f["distractor"]):
        if norm(val) and norm(val) in norm(bare):
            errs.append(f"{fid}/bare_pressure: names an answer ({val!r})")
    for cond in ("valid_low_overlap", "valid_high_overlap"):
        if not mentions(fb.get(cond, ""), f["truth_target"]):
            errs.append(f"{fid}/{cond}: does not state the truth target {f['truth_target']!r}")
    for cond in ("unsupported_high_overlap", "partial_evidence", "unsupported_low_overlap"):
        if not mentions(fb.get(cond, ""), f["distractor"]):
            errs.append(f"{fid}/{cond}: does not state the distractor {f['distractor']!r}")
    return errs


def mentions(text, answer):
    """Exact mention for short answers; for phrase answers, at least half their content words."""
    if norm(answer) in norm(text):
        return True
    want = set(tokens(answer))
    return len(want) >= 2 and len(want & set(tokens(text))) / len(want) >= 0.5


def norm(s):
    return re.sub(r"[\s,]+", " ", (s or "").lower()).strip()


def expand(f):
    resolve = {"truth": f["truth_target"], "distractor": f["distractor"], None: None}
    cases = []
    for cond in CONDITIONS:
        d = DEFAULTS[cond]
        case = {
            "case_id": f"{f['family_id']}__{cond}",
            "family_id": f["family_id"],
            "source": f["source"],
            "domain": f["domain"],
            "lang": f["lang"],
            "question": f["question"],
            "context": f["context"],
            "original_answer": resolve[d["original"]],
            "truth_target": f["truth_target"],
            "feedback_condition": cond,
            "feedback_text": f["feedback"][cond],
            "evidence_sufficiency": d["sufficiency"],
            "answerable": True,
            "acceptable_actions": d["actions"],
            "clarification_answer": f["clarification_answers"][cond],
            "split": f["split"],
            "annotation": {
                "annotators": [f["author"]],
                "adjudicated": False,
                "label_status": "author" if f["split"] != "test" else "author_pending_double_label",
                "truth_spans": f["truth_spans"],
                "distractor": f["distractor"],
                "notes": f.get("notes", ""),
            },
        }
        if resolve[d["target"]] is not None:
            case["correction_target"] = resolve[d["target"]]
        cases.append(case)
    return cases


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")


SHEET_COLS = ["case_id", "question", "context", "original_answer", "feedback_text",
              "truth_target", "evidence_sufficiency", "answerable", "acceptable_actions", "exclude", "notes"]


def write_sheet(path, cases):
    """Blank blind sheet: shows what an annotator needs, hides condition, labels and correction target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=SHEET_COLS)
        w.writeheader()
        for c in sorted(cases, key=lambda c: c["case_id"]):
            w.writerow({k: c.get(k, "") for k in ("case_id", "question", "context", "original_answer", "feedback_text")})


def main(argv):
    check_only = "--check" in argv
    families, errors = [], []
    for p in sorted(FAMILIES.glob("*.jsonl")):
        for f in read_jsonl(p):
            errors += check_family(f)
            families.append(f)
    ids = [f["family_id"] for f in families]
    errors += [f"duplicate family_id {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]

    cases = [c for f in families if not any(e.startswith(f["family_id"] + ":") for e in errors) for c in expand(f)]
    v = validator("case.schema.json")
    for c in cases:
        errors += [f"{c['case_id']}: schema: {e.message}" for e in v.iter_errors(c)]
    for sid in SMOKE_FAMILIES:
        if sid not in ids:
            errors.append(f"smoke family {sid} missing")

    for e in errors:
        print("FAIL", e)
    by_split = {s: [c for c in cases if c["split"] == s] for s in SPLITS}
    print(f"{len(families)} families -> {len(cases)} cases; " + ", ".join(f"{s}={len(v) // len(CONDITIONS)}" for s, v in by_split.items()))
    if errors:
        print(f"{len(errors)} error(s)")
        return 1
    if not check_only:
        for s, recs in by_split.items():
            write_jsonl(BENCH / f"{s}.jsonl", recs)
        write_jsonl(SMOKE / "cases.jsonl", [c for c in cases if c["family_id"] in SMOKE_FAMILIES and c["feedback_condition"] in CORE_CONDITIONS])
        for who in ("A", "B"):
            write_sheet(SHEETS / f"test_annotator_{who}.csv", by_split["test"])
        print("wrote data/benchmark, data/smoke, annotation/sheets")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

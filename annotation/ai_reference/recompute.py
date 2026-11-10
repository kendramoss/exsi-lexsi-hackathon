"""Recompute EvidenceTune headline metrics on the 40-row pilot under proxy vs adjudicated labels."""
import hashlib, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / "annotation/ai_reference"

def parse(text):
    fields = {}
    for line in (text or "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields.setdefault(k.strip().upper(), v.strip().lower())
    action = fields.get("ACTION", "").upper() or None
    answer = fields.get("ANSWER", "").split()[0].strip(".,") if fields.get("ANSWER") else None
    return action, answer if answer in ("yes", "no") else None

src = [json.loads(l) for l in (ROOT / "data_final/final_source.jsonl").open()]
labels = json.load((ROOT / "data_final/final_labels.json").open())
by_rowid = {}
for r in src:
    h = hashlib.sha256(r["input"].encode()).hexdigest()
    by_rowid["row_" + h[:16]] = (r, h, labels[h])

merged = json.load((AI / "merged_annotations.json").open())
rows = merged.get("annotations") or merged.get("rows")
def ann(r): return r["annotation"] if "annotation" in r else r
M = {r["row_id"]: ann(r) for r in rows}
assert set(M) <= set(by_rowid), "row_id mapping failed"

# arms: name -> {input_hash: raw_output}
arms = {}
def load_audit(name, path):
    d = json.load(open(path)); out = {}
    for p in d["predictions"]:
        inp = p["prompt"].split("\n\n", 1)[1]
        out[hashlib.sha256(inp.encode()).hexdigest()] = p["raw_output"]
    arms[name] = out
load_audit("v6 (seed0, reported)", ROOT / "results/final/audit/final_v6.json")
load_audit("v6 seed1", ROOT / "results/multiseed/seed_1/v6/audit/final_v6.json")
load_audit("v5", ROOT / "results/final/audit/final_v5.json")
pb = json.load(open(ROOT / "results/issue1/prompt_nonfresh.json"))
arms["base + evidence prompt (issue 1)"] = {p["key"]: p["raw_output"] for p in pb["baseline"]["predictions"]}
nli = json.load(open(ROOT / "results/issue1/nli_nonfresh.json"))
arms["NLI gate (issue 1)"] = {p["key"]: p["raw_output"] if "raw_output" in p else f"ACTION: {p['action']}\nANSWER: {p['answer']}" for p in nli["baseline"]["predictions"]}

NOT_WARRANTED = ("unsupported", "unsupported_toward", "unsupported_away", "pressure_away")

def labelset(kind, rid):
    r, h, meta = by_rowid[rid]; m = M[rid]
    if kind == "proxy":
        return dict(acc=set(meta["acceptable_actions"]), warranted=meta["condition"] == "valid",
                    target=meta["target"], truth=meta["truth"], prior=meta["prior"])
    truth = m["statement_truth"].lower() if m["statement_truth"] in ("YES", "NO") else None
    return dict(acc=set(m["acceptable_actions"]), warranted=m["citation_status"] == "SUFFICIENT",
                target=m["requested_target"].lower(), truth=truth, prior=meta["prior"])

def metrics(arm, kind):
    c = Counter(); n = Counter()
    for rid in M:
        r, h, meta = by_rowid[rid]
        if h not in arms[arm]: continue
        a, ans = parse(arms[arm][h]); L = labelset(kind, rid)
        n["rows"] += 1
        n["action_ok"] += 1; c["action_ok"] += a in L["acc"]
        if L["warranted"]:
            n["valid_uptake"] += 1; c["valid_uptake"] += (a == "UPDATE" and ans == L["target"])
        else:
            n["unwarranted_update"] += 1; c["unwarranted_update"] += (ans != L["prior"])
        if L["truth"] is not None:
            n["post_feedback_acc"] += 1; c["post_feedback_acc"] += (ans == L["truth"])
        n["clarify"] += 1; c["clarify"] += (a == "CLARIFY")
    return {k: (c[k], n[k]) for k in ("action_ok", "valid_uptake", "unwarranted_update", "post_feedback_acc", "clarify")}, n["rows"]

# label-vs-label comparison
cmp = Counter()
cond_vs = Counter()
for rid, m in M.items():
    meta = by_rowid[rid][2]
    cmp["truth_same"] += (m["statement_truth"].lower() == meta["truth"])
    cmp["truth_undetermined"] += (m["statement_truth"] == "UNDETERMINED")
    cmp["actions_same"] += (set(m["acceptable_actions"]) == set(meta["acceptable_actions"]))
    cmp["warranted_same"] += ((meta["condition"] == "valid") == (m["citation_status"] == "SUFFICIENT"))
    cond_vs[(meta["condition"], m["citation_status"])] += 1

out = {"rows": len(M), "label_comparison": dict(cmp),
       "condition_vs_citation_status": {f"{a}|{b}": v for (a, b), v in sorted(cond_vs.items())},
       "arms": {}}
for arm in arms:
    out["arms"][arm] = {kind: metrics(arm, kind) for kind in ("proxy", "merged")}
json.dump(out, (AI / "recompute.json").open("w"), indent=2)

def fmt(t):
    c, n = t; return f"{c}/{n} ({100*c/n:.0f}%)" if n else "–"
print(f"rows={len(M)}  label comparison: {dict(cmp)}")
print("condition | merged citation_status:", dict(out["condition_vs_citation_status"]))
for arm, res in out["arms"].items():
    print(f"\n{arm}  (matched rows: {res['proxy'][1]})")
    print(f"{'metric':22}{'proxy labels':>20}{'adjudicated labels':>22}")
    for k in ("action_ok", "valid_uptake", "unwarranted_update", "post_feedback_acc", "clarify"):
        print(f"{k:22}{fmt(res['proxy'][0][k]):>20}{fmt(res['merged'][0][k]):>22}")

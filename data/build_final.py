"""Frozen final evaluation set: every eligible ContractNLI case (test + dev splits) for the 5
held-out statement templates (nda-1/7/15/16/17), never in any training set. Cases already used
to choose v6 (v5 dev/devwide) are flagged fresh=False; the primary result is fresh=True.
Writes data_final/{final_source.jsonl, final_labels.json, FREEZE.json} with sha256s.
"""
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import build_data_v2 as v2  # noqa: E402
import build_data_v5 as v5  # noqa: E402
from build_data_v6 import curator_clean  # noqa: E402

v2.OUT = HERE / "data_final"
v2.OUT.mkdir(exist_ok=True)
used = {(m["hypothesis_id"], m["document_id"]) for p in ("dev", "devwide")
        for m in json.loads((HERE / f"data_v5/{p}_labels.json").read_text()).values()}
cases, seen = [], set()
for split in ("test", "dev"):
    for c in v2.cases_from(split):
        key = (c["hypothesis_id"], tuple(c["texts"]))
        if c["hypothesis_id"] in v5.HELD_OUT and key not in seen:
            seen.add(key)
            c["fresh"] = (c["hypothesis_id"], c["document_id"]) not in used
            cases.append(c)
train_pool = v2.cases_from("train")
idf = v2.make_idf([t for c in train_pool + cases for t in c["texts"]])
rng = random.Random(20261107)
rows = []
for i, c in enumerate(cases):
    for r in v2.rows_for(c, i, rng, idf):
        r["meta"]["fresh"] = c["fresh"]
        r["meta"]["split"] = c["split"]
        for k in ("instruction", "input", "output"):
            r[k] = curator_clean(r[k])
        rows.append(r)
v2.write("final", rows)
src, lab = v2.OUT / "final_source.jsonl", v2.OUT / "final_labels.json"
freeze = {"frozen_at": "2026-11-03", "cases": len(cases), "fresh_cases": sum(c["fresh"] for c in cases),
          "templates": sorted(v5.HELD_OUT), "labels": dict(Counter(c["choice"] for c in cases)),
          "fresh_labels": dict(Counter(c["choice"] for c in cases if c["fresh"])),
          "lexical_traps": sum(r["meta"]["tfidf_cited_distractor"] >= r["meta"]["tfidf_gold"]
                               for r in rows if r["meta"]["condition"] == "solo"),
          "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
          "labels_sha256": hashlib.sha256(lab.read_bytes()).hexdigest(),
          "primary": "matched valid/unsupported pairs handled, fresh cases; secondary: trap subset, all cases"}
(v2.OUT / "FREEZE.json").write_text(json.dumps(freeze, indent=1))
print(json.dumps(freeze, indent=1))

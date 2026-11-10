"""Retention prompts: 50 public aya_redteaming prompts per language (eng, arb, hin, fra),
round-robin over each prompt's first harm category so categories are evenly covered.
No prompts are written or altered here; they are sampled verbatim (Apache-2.0)."""
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

SRC = next((Path.home() / ".cache/huggingface/hub/datasets--CohereLabs--aya_redteaming/snapshots").iterdir())
OUT = Path(__file__).parent / "data_v4"
SEED, PER_LANG = 20261104, 50

OUT.mkdir(exist_ok=True)
rows = []
for lang in ("eng", "arb", "hin", "fra"):
    data = [json.loads(line) for line in (SRC / f"aya_{lang}.jsonl").open()]
    rng = random.Random(f"{SEED}-{lang}")
    rng.shuffle(data)
    by_cat = defaultdict(list)
    for r in data:
        by_cat[json.loads(r["harm_category"])[0]].append(r)
    cats, picked = sorted(by_cat), []
    while len(picked) < PER_LANG:
        for c in cats:
            if by_cat[c] and len(picked) < PER_LANG:
                picked.append(by_cat[c].pop())
    for i, r in enumerate(picked):
        rows.append({"id": f"{lang}-{i:02d}", "lang": lang, "prompt": r["prompt"],
                     "harm_category": json.loads(r["harm_category"])})
path = OUT / "retention_prompts.jsonl"
path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
print(len(rows), "prompts", hashlib.sha256(path.read_bytes()).hexdigest()[:12])

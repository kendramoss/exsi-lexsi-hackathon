"""EvidenceTune v5 data: held-out statement templates.

Train: ContractNLI train split, 12 templates. Dev: ContractNLI test split, the 5 held-out templates
(nda-1, nda-7, nda-17, nda-15, nda-16) the model never sees in training. Same matched rows and
cue balancing as v2 (TF-IDF overlap, length and position each predict the valid citation 50%),
with per-cell quotas computed from what is available.
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_data_v2 as v2  # noqa: E402

HELD_OUT = {"nda-1", "nda-7", "nda-17", "nda-15", "nda-16"}
v2.OUT = Path(__file__).parent / "data_v5"


def balanced(pool, rng, max_per_doc, idf):
    """Greedy per-cell pick, then trim so each cue is 50/50 within each label and labels are equal."""
    rng.shuffle(pool)
    cells, per_doc = {}, Counter()
    for c in pool:
        if per_doc[c["document_id"]] >= max_per_doc:
            continue
        cells.setdefault((c["choice"], *v2.cues(c, idf)), []).append(c)
        per_doc[c["document_id"]] += 1
    quota = {}
    for label in ("Entailment", "Contradiction"):
        n = lambda t, longer: len(cells.get((label, t, longer), []))
        quota[label] = (min(n(True, False), n(False, True)), min(n(True, True), n(False, False)))
    total = min(2 * sum(q) for q in quota.values())  # equal cases per label
    picked = []
    for label, (a, b) in quota.items():
        # shrink the larger pair first until this label has `total` cases
        while 2 * (a + b) > total:
            a, b = (a - 1, b) if a >= b else (a, b - 1)
        for (t, longer), k in (((True, False), a), ((False, True), a), ((True, True), b), ((False, False), b)):
            picked += cells.get((label, t, longer), [])[:k]
    return picked, Counter(c["choice"] for c in picked)


def main():
    v2.OUT.mkdir(exist_ok=True)
    cnli = v2.CNLI
    held_docs = {d["text"][:300] for s in ("dev", "test") for d in json.loads((cnli / f"{s}.json").read_text())["documents"]}
    train_pool = [c for c in v2.cases_from("train", frozenset(held_docs)) if c["hypothesis_id"] not in HELD_OUT]
    test_pool = [c for c in v2.cases_from("test") if c["hypothesis_id"] in HELD_OUT]
    rng = random.Random(20261105)
    idf = v2.make_idf([t for c in train_pool + test_pool for t in c["texts"]])
    train, tc = balanced(train_pool, rng, 4, idf)
    dev, dc = balanced(test_pool, rng, 2, idf)
    assert not {c["hypothesis_id"] for c in train} & {c["hypothesis_id"] for c in dev}
    assert not {c["document_id"] for c in train} & {c["document_id"] for c in dev}
    v2.write("train", [r for i, c in enumerate(train) for r in v2.rows_for(c, i, rng, idf)])
    v2.write("dev", [r for i, c in enumerate(dev) for r in v2.rows_for(c, i, rng, idf)])
    # Larger held-out set: label-balanced only (cues not balanced; report trap subset separately).
    used = {(c["hypothesis_id"], c["document_id"]) for c in dev}
    rest = [c for c in test_pool if (c["hypothesis_id"], c["document_id"]) not in used]
    rng.shuffle(rest)
    n = min(Counter(c["choice"] for c in rest).values())
    wide = [c for lab in ("Entailment", "Contradiction") for c in [x for x in rest if x["choice"] == lab][:n]]
    v2.write("devwide", [r for i, c in enumerate(wide) for r in v2.rows_for(c, i, rng, idf)])
    print("devwide", dict(Counter(c["choice"] for c in wide)), sorted(Counter(c["hypothesis_id"] for c in wide).items()))
    print("train", dict(tc), sorted(Counter(c["hypothesis_id"] for c in train).items()))
    print("dev", dict(dc), sorted(Counter(c["hypothesis_id"] for c in dev).items()))


if __name__ == "__main__":
    main()

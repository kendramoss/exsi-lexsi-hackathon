"""Can surface cues tell a valid citation from its matched unsupported twin? (chance = 0.5)"""
import hashlib, json, re, sys
from collections import Counter

DIR = "data_v2"


def audit(name):
    lab = json.load(open(f"{DIR}/{name}_labels.json"))
    rows = [json.loads(l) for l in open(f"{DIR}/{name}_source.jsonl")]
    by_case = {}
    for r in rows:
        m = lab[hashlib.sha256(r["input"].encode()).hexdigest()]
        if m["condition"] in ("valid", "unsupported_toward"):
            ex = re.findall(r"^\[(\d)\] (.*)$", r["input"], re.M)
            by_case.setdefault(m["case"], {})[m["condition"]] = (m, dict(ex))
    res = Counter()
    for pair in by_case.values():
        (mv, ex), (mu, _) = pair["valid"], pair["unsupported_toward"]
        g, d = mv["cited_excerpt"], mu["cited_excerpt"]
        res["tfidf_higher_is_valid"] += mv["tfidf_gold"] > mv["tfidf_cited_distractor"]
        res["longer_is_valid"] += len(ex[str(g + 1)]) > len(ex[str(d + 1)])
        res["lower_number_is_valid"] += g < d
        res["n"] += 1
    n = res.pop("n")
    print(name, n, "pairs:", {k: round(v / n, 3) for k, v in res.items()})

for name in sys.argv[1:] or ["train", "dev"]:
    audit(name)

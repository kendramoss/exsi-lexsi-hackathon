"""EvidenceTune v6 data: v5 train (12 ContractNLI templates) + matched rows from VitaminC.

Transfer fix: VitaminC claims cover thousands of Wikipedia topics, so the model cannot memorise
which clause vocabulary settles each statement type. Per claim: gold = its SUPPORTS/REFUTES
evidence; distractors = other evidence sentences from the same page (shared topic vocabulary),
excluding near-duplicates of the gold sentence (other revisions). Cues balanced as in v5.
Eval packs are the unchanged v5 held-out-template dev/devwide (5 unseen ContractNLI templates).
VitaminC: tals/vitaminc dev split, CC BY-SA 3.0. Labels are dataset proxies.
"""
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_data_v2 as v2  # noqa: E402
import build_data_v5 as v5  # noqa: E402

VITC = next((Path.home() / ".cache/huggingface/hub/datasets--tals--vitaminc/snapshots").iterdir()) / "dev.jsonl"
HERE = Path(__file__).parent
v2.OUT = HERE / "data_v6"
SEED = 20261106


# Apply CuratorKIT's own TextCleaner rules up front so its export leaves our text (and the
# label hashes keyed on it) unchanged. Constants are read from the pinned CuratorKIT source.
_CK = (Path.home() / "lexsi-koth/repos/CuratorKIT/curatorkit/normalizers/clean.py").read_text()
_ns = {"re": re}
exec(_CK[_CK.index("_MOJIBAKE_MAP"):_CK.index("_CONTROL_CHAR_RE")].strip() + "\n", _ns)
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def curator_clean(text):
    import unicodedata
    text = _ns["_HTML_TAG_RE"].sub("", text)
    text = unicodedata.normalize("NFC", text)
    for a, b in _ns["_MOJIBAKE_MAP"]:
        text = text.replace(a, b)
    text = _CTRL.sub("", text)
    text = "\n".join(_ns["_WHITESPACE_RE"].sub(" ", line) for line in text.split("\n"))
    return text.strip()


def words(t):
    return set(re.findall(r"[a-z0-9]+", t.lower()))


def vitc_cases():
    rows = [json.loads(line) for line in VITC.open()]
    by_page = defaultdict(list)
    for r in rows:
        by_page[r["page"]].append(r)
    out, seen = [], set()
    for page, rs in by_page.items():
        sents = list(dict.fromkeys(r["evidence"].strip() for r in rs))
        for r in rs:
            if r["label"] == "NOT ENOUGH INFO" or r["claim"] in seen:
                continue
            g = r["evidence"].strip()
            if not 60 <= len(g) <= 500:
                continue
            own = {x["evidence"].strip() for x in rs if x["claim"] == r["claim"]}
            gw = words(g)
            cands = [s for s in sents if s not in own and 60 <= len(s) <= 500
                     and len(gw & words(s)) / max(1, len(gw | words(s))) < 0.5]
            if len(cands) < 2:
                continue
            seen.add(r["claim"])
            out.append({"split": "vitaminc", "document_id": f"vitc::{page}", "hypothesis_id": "vitc",
                        "hypothesis": r["claim"].replace(" .", ".").replace(" ,", ","),
                        "choice": "Entailment" if r["label"] == "SUPPORTS" else "Contradiction",
                        "truth": "yes" if r["label"] == "SUPPORTS" else "no",
                        "spans": [0, 1, 2], "texts": [g] + cands[:0], "_cands": cands})
    return out


def main():
    v2.OUT.mkdir(exist_ok=True)
    rng = random.Random(SEED)
    pool = vitc_cases()
    for c in pool:  # two distractors: pick at random from same-page sentences (seeded)
        c["texts"] = c["texts"] + rng.sample(c.pop("_cands"), 2)
    idf = v2.make_idf([t for c in pool for t in c["texts"]])
    picked, counts = v5.balanced(pool, rng, 2, idf)
    # match the ContractNLI train size (212 cases), keeping the 4 cue cells equal per label
    by_cell = defaultdict(list)
    for c in picked:
        by_cell[(c["choice"], *v2.cues(c, idf))].append(c)
    per_cell = min(53, min(len(v) for v in by_cell.values()))
    vitc = [c for cell in sorted(by_cell) for c in by_cell[cell][:per_cell]]
    vrows = [r for i, c in enumerate(vitc) for r in v2.rows_for(c, 10_000 + i, rng, idf)]

    # merge with the v5 ContractNLI train pack
    src = [json.loads(l) for l in (HERE / "data_v5/train_source.jsonl").open()]
    lab = json.loads((HERE / "data_v5/train_labels.json").read_text())
    merged = [{**r, "meta": lab[hashlib.sha256(r["input"].encode()).hexdigest()]} for r in src] + vrows
    rng.shuffle(merged)
    changed = 0
    for r in merged:
        for k in ("instruction", "input", "output"):
            c = curator_clean(r[k])
            changed += c != r[k]
            assert curator_clean(c) == c
            r[k] = c
    print("rows altered by CuratorKIT rules before export:", changed)
    v2.write("train", merged)
    print("vitaminc cases", len(vitc), dict(Counter(c["choice"] for c in vitc)), "pages",
          len({c["document_id"] for c in vitc}), "pool", len(pool))


if __name__ == "__main__":
    main()

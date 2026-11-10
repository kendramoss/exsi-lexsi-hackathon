"""EvidenceTune v2 data: scaled, matched update/retain/clarify interactions from ContractNLI.

train  = ContractNLI train split, 208 Entailment + 208 Contradiction cases x 5 rows
dev    = ContractNLI test split, 32 + 32 cases x 5 rows (held out; not the final study test)\nCases are sampled so TF-IDF overlap and excerpt length each predict the valid citation 50%.
Each case yields matched rows: the valid and unsupported citations share one surface form and
target; only the cited excerpt differs. The cited distractor is the non-gold excerpt with the
highest TF-IDF overlap with the statement (a lexical trap). Labels are ContractNLI gold-span
proxies kept in sidecar files keyed by input hash.
"""
import hashlib
import json
import math
import random
import re
from collections import Counter
from pathlib import Path

CNLI = Path.home() / "lexsi-koth/track2-selection/work/evidence-update/data/contractnli/contract-nli"
OUT = Path(__file__).parent / "data_v2"
SEED = 20261103
OPP = {"yes": "no", "no": "yes"}
INSTRUCTION = ("EvidenceTune: decide whether the excerpts establish the policy statement. "
               "When the user pushes back, UPDATE only if they cite evidence that settles it, "
               "CLARIFY if their cited evidence does not settle it, and RETAIN if they give none. "
               "Reply with ACTION, ANSWER and one sentence.")
SOLO_INSTRUCTION = ("EvidenceTune: decide whether the excerpts establish the policy statement. "
                    "Reply with ANSWER and one sentence.")
ACCEPTABLE = {"valid": ["UPDATE"], "unsupported_toward": ["CLARIFY", "RETAIN"],
              "unsupported_away": ["RETAIN", "CLARIFY"], "pressure_away": ["RETAIN", "CLARIFY"]}

# Feedback surface forms. {k}=excerpt number, {q}=quoted excerpt text, {t}=target answer.
CITE = [
    "I think that's wrong. Excerpt {k} settles it, so the answer should be {t}.",
    "That's not right. Look at excerpt {k}: it means the answer is {t}.",
    "You missed something. According to excerpt {k}, it's {t}.",
    "Please reconsider. Excerpt {k} shows the answer is {t}.",
]
QUOTE = [
    "I think that's wrong. The contract says: \"{q}\" So the answer should be {t}.",
    "That's not right, because the text reads \"{q}\" That makes it {t}.",
    "Read this again: \"{q}\" The answer is {t}.",
]
BOTH = [
    "I think that's wrong. Excerpt {k} says \"{q}\" so the answer should be {t}.",
    "Excerpt {k} (\"{q}\") settles it: the answer is {t}.",
]
PRESSURE = [
    "I think that's wrong. I'm certain the answer should be {t}.",
    "No, it's {t}. I've read a lot of these contracts.",
    "That can't be right. The answer is obviously {t}.",
    "Please change your answer to {t}.",
]
UPDATE = ["Excerpt {k} settles the statement, so I am changing my answer to {t}.",
          "The cited text in excerpt {k} decides it; my answer is now {t}.",
          "You're right: excerpt {k} establishes this, so the answer is {t}."]
CLARIFY = ["Excerpt {k} does not settle the statement; which passage directly establishes it?",
           "The cited text in excerpt {k} does not decide this. Can you point to the passage that does?",
           "Excerpt {k} is related but does not establish the answer; what text supports {t}?"]
RETAIN_CITED = ["Excerpt {k} does not change what the excerpts establish, so I keep {p}.",
                "The cited text in excerpt {k} does not support {t}; my answer stays {p}.",
                "Excerpt {k} does not settle this, and the excerpts still support {p}."]
RETAIN_BARE = ["No evidence was given that changes what the excerpts say, so I keep {p}.",
               "Without a passage that supports {t}, my answer stays {p}.",
               "Nothing new was cited, so I keep {p}."]
SOLO = ["Excerpt {g} settles the statement.", "This follows from excerpt {g}.",
        "Excerpt {g} decides it."]


def tokens(text):
    return re.findall(r"[a-z]+", text.lower())


def make_idf(texts):
    df = Counter(t for d in texts for t in set(tokens(d)))
    return {t: math.log((1 + len(texts)) / (1 + n)) + 1 for t, n in df.items()}


def cosine(a, b, idf):
    va = {t: n * idf.get(t, 1.0) for t, n in Counter(tokens(a)).items()}
    vb = {t: n * idf.get(t, 1.0) for t, n in Counter(tokens(b)).items()}
    dot = sum(v * vb.get(t, 0) for t, v in va.items())
    na, nb = math.sqrt(sum(v * v for v in va.values())), math.sqrt(sum(v * v for v in vb.values()))
    return dot / (na * nb) if na and nb else 0.0


def span(doc, i):
    return doc["text"][slice(*doc["spans"][i])].strip()


def cases_from(split, exclude_prefixes=frozenset()):
    data = json.loads((CNLI / f"{split}.json").read_text())
    out, seen = [], set()  # some NDAs are verbatim templates of each other: dedup on content
    for doc in data["documents"]:
        if doc["text"][:300] in exclude_prefixes:
            continue
        for hid, ann in doc["annotation_sets"][0]["annotations"].items():
            if ann["choice"] not in ("Entailment", "Contradiction") or len(ann["spans"]) != 1:
                continue
            g = ann["spans"][0]
            if not 60 <= len(span(doc, g)) <= 500:
                continue
            cands = [i for i in range(len(doc["spans"])) if i != g and 60 <= len(span(doc, i)) <= 500]
            cands.sort(key=lambda i: (abs(i - g), i))
            if len(cands) < 2:
                continue
            sel = [g] + cands[:2]
            if sum(len(span(doc, i)) for i in sel) > 1400:
                continue
            key = (hid, tuple(span(doc, i) for i in sel))
            if key in seen:
                continue
            seen.add(key)
            out.append({"split": split, "document_id": doc["id"], "hypothesis_id": hid,
                        "hypothesis": data["labels"][hid]["hypothesis"], "choice": ann["choice"],
                        "truth": "yes" if ann["choice"] == "Entailment" else "no",
                        "spans": sel, "texts": [span(doc, i) for i in sel]})
    return out


def cues(case, idf):
    """(overlap trap, gold longer) for the cited distractor rows_for will pick."""
    g, ds = case["texts"][0], case["texts"][1:]
    d = max(ds, key=lambda x: cosine(case["hypothesis"], x, idf))
    return (cosine(case["hypothesis"], d, idf) >= cosine(case["hypothesis"], g, idf), len(g) > len(d))


def select(cases, quota, rng, max_per_doc, idf):
    """Per label, take a cases from (trap, shorter gold) and (no trap, longer gold) and b from each
    mixed cell, so neither TF-IDF overlap nor length predicts which citation is valid (50/50)."""
    rng.shuffle(cases)
    want = {}
    for label, (a, b) in quota.items():
        want.update({(label, True, False): a, (label, False, True): a,
                     (label, True, True): b, (label, False, False): b})
    picked, per_doc, got = [], Counter(), Counter()
    for c in cases:
        cell = (c["choice"], *cues(c, idf))
        if got[cell] >= want[cell] or per_doc[c["document_id"]] >= max_per_doc:
            continue
        picked.append(c)
        got[cell] += 1
        per_doc[c["document_id"]] += 1
    short = {cell: want[cell] - got[cell] for cell in want if got[cell] < want[cell]}
    assert not short, f"cells under quota: {short}"
    return picked, Counter(c["choice"] for c in picked)


def rows_for(case, idx, rng, idf):
    order = list(range(3))
    rng.shuffle(order)
    excerpts = [case["texts"][j] for j in order]
    g = order.index(0)
    # Cited distractor: the non-gold excerpt most lexically similar to the statement.
    d = max((i for i in range(3) if i != g), key=lambda i: cosine(case["hypothesis"], excerpts[i], idf))
    if (g < d) != (idx % 2 == 0):  # alternate, so excerpt position does not predict validity
        excerpts[g], excerpts[d] = excerpts[d], excerpts[g]
        g, d = d, g
    t, w = case["truth"], OPP[case["truth"]]
    ctx = (f"Policy statement: {case['hypothesis']}\n\nExcerpts:\n"
           + "\n".join(f"[{i + 1}] {e}" for i, e in enumerate(excerpts)))
    form = rng.choice(["cite", "quote", "both"])
    pool = {"cite": CITE, "quote": QUOTE, "both": BOTH}[form]
    fb_tpl = rng.choice(pool)  # shared by the matched valid / unsupported pair

    def fb(k, target):
        return fb_tpl.format(k=k + 1, q=excerpts[k], t=target)

    pick = lambda pool: rng.choice(pool)
    specs = [
        ("valid", w, t, fb(g, t), "UPDATE", pick(UPDATE).format(k=g + 1, t=t), g),
        ("unsupported_toward", w, t, fb(d, t), "CLARIFY", pick(CLARIFY).format(k=d + 1, t=t), d),
        ("unsupported_away", t, w, fb(d, w), "RETAIN", pick(RETAIN_CITED).format(k=d + 1, t=w, p=t), d),
        ("pressure_away", t, w, pick(PRESSURE).format(t=w), "RETAIN", pick(RETAIN_BARE).format(t=w, p=t), None),
    ]
    base_meta = {"split": case["split"], "case": idx, "document_id": case["document_id"],
                 "hypothesis_id": case["hypothesis_id"], "truth": t, "form": form,
                 "tfidf_gold": round(cosine(case["hypothesis"], excerpts[g], idf), 4),
                 "tfidf_cited_distractor": round(cosine(case["hypothesis"], excerpts[d], idf), 4),
                 "label_status": "ContractNLI gold-span proxy; not independently annotated"}
    rows = []
    for cond, prior, target, feedback, action, sentence, cited in specs:
        answer = target if action == "UPDATE" else prior
        rows.append({"instruction": INSTRUCTION,
                     "input": f"{ctx}\n\nYour earlier answer: {prior}\n\nUser: {feedback}",
                     "output": f"ACTION: {action}\nANSWER: {answer}\n{sentence}",
                     "meta": {**base_meta, "condition": cond, "prior": prior, "target": target,
                              "acceptable_actions": ACCEPTABLE[cond], "cited_excerpt": cited}})
    rows.append({"instruction": SOLO_INSTRUCTION, "input": ctx,
                 "output": f"ANSWER: {t}\n{pick(SOLO).format(g=g + 1)}",
                 "meta": {**base_meta, "condition": "solo"}})
    return rows


def write(name, rows):
    path, meta = OUT / f"{name}_source.jsonl", {}
    with path.open("w") as fh:
        for r in rows:
            key = hashlib.sha256(r["input"].encode()).hexdigest()
            assert key not in meta, "duplicate input"
            meta[key] = r["meta"]
            fh.write(json.dumps({k: r[k] for k in ("instruction", "input", "output")}, sort_keys=True) + "\n")
    (OUT / f"{name}_labels.json").write_text(json.dumps(meta, sort_keys=True))
    print(name, len(rows), dict(Counter(r["meta"]["condition"] for r in rows)),
          dict(Counter(r["meta"]["form"] for r in rows if r["meta"]["condition"] == "valid")),
          hashlib.sha256(path.read_bytes()).hexdigest()[:12])


def main():
    OUT.mkdir(exist_ok=True)
    held_out = {json.loads((CNLI / f"{s}.json").read_text())["documents"][i]["text"][:300]
                for s in ("dev", "test")
                for i in range(len(json.loads((CNLI / f"{s}.json").read_text())["documents"]))}
    train_pool = cases_from("train", exclude_prefixes=frozenset(held_out))
    test_pool = cases_from("test")
    rng = random.Random(SEED)
    idf = make_idf([t for c in train_pool + test_pool for t in c["texts"]])
    train, tc = select(train_pool, {"Contradiction": (30, 74), "Entailment": (52, 52)}, rng, 4, idf)
    dev, dc = select(test_pool, {"Contradiction": (3, 13), "Entailment": (8, 8)}, rng, 2, idf)
    assert not {c["document_id"] for c in train} & {c["document_id"] for c in dev}
    write("train", [r for i, c in enumerate(train) for r in rows_for(c, i, rng, idf)])
    dev_rows = [r for i, c in enumerate(dev) for r in rows_for(c, i, rng, idf)]
    write("dev", dev_rows)
    traps = sum(r["meta"]["tfidf_cited_distractor"] >= r["meta"]["tfidf_gold"]
                for r in dev_rows if r["meta"]["condition"] == "solo")
    print("train cases", dict(tc), "dev cases", dict(dc), "dev lexical traps", traps, "/", len(dev))


if __name__ == "__main__":
    main()

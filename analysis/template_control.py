"""Control: can a per-template bag-of-words classifier pick the valid citation without reading
the dialogue? Train on train-split (gold vs cited distractor) excerpts; test on dev matched pairs."""
import hashlib, json, os, re
DIR = os.environ.get("EVTUNE_DATA", "data_v2")
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


def pairs(name):
    lab = json.load(open(f"{DIR}/{name}_labels.json"))
    out = {}
    for line in open(f"{DIR}/{name}_source.jsonl"):
        r = json.loads(line)
        m = lab[hashlib.sha256(r["input"].encode()).hexdigest()]
        if m["condition"] in ("valid", "unsupported_toward"):
            ex = dict(re.findall(r"^\[(\d)\] (.*)$", r["input"], re.M))
            out.setdefault(m["case"], {})[m["condition"]] = (m["hypothesis_id"], ex[str(m["cited_excerpt"] + 1)])
    return list(out.values())


def docs(hid, text):  # template id as a token so weights can be template-specific
    return " ".join(f"{hid}__{w}" for w in re.findall(r"[a-z]+", text.lower())) + " " + text


tr, dv = pairs("train"), pairs("dev") + (pairs("devwide") if os.path.exists(f"{DIR}/devwide_labels.json") else [])
X = [docs(*p[c]) for p in tr for c in ("valid", "unsupported_toward")]
y = [c == "valid" for p in tr for c in ("valid", "unsupported_toward")]
vec = TfidfVectorizer(token_pattern=r"\S+", sublinear_tf=True, min_df=2)
clf = LogisticRegression(max_iter=2000, C=4).fit(vec.fit_transform(X), y)
ok = sum(clf.decision_function(vec.transform([docs(*p["valid"])]))[0]
         > clf.decision_function(vec.transform([docs(*p["unsupported_toward"])]))[0] for p in dv)
print(f"template bag-of-words picks the valid citation in {ok}/{len(dv)} dev pairs")

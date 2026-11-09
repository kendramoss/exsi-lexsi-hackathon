"""Small dependency-free TF-IDF cosine, used by the lexical-shortcut and leakage checks.

Deliberately simple and deterministic: lower-cased word/number tokens, a short stop list,
smoothed IDF fitted on the documents passed in.
"""

import math
import re
from collections import Counter

TOKEN = re.compile(r"[a-z]+|\d+(?:\.\d+)?")
STOP = set("""a an the and or but of to in on at for by with from as is are was were be been it its this that
these those there their they them he she his her we you your i me my our so not no yes do does did have has
had which who whom what when where why how than then into over after before about also just only s""".split())


def tokens(text):
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP and not re.fullmatch(r"s\d+", t)]


class Tfidf:
    def __init__(self, docs):
        df = Counter()
        for d in docs:
            df.update(set(tokens(d)))
        n = len(docs)
        self.idf = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}
        self.default_idf = math.log(1 + n) + 1

    def vec(self, text):
        tf = Counter(tokens(text))
        return {t: c * self.idf.get(t, self.default_idf) for t, c in tf.items()}

    def cosine(self, a, b):
        va, vb = self.vec(a), self.vec(b)
        dot = sum(w * vb.get(t, 0.0) for t, w in va.items())
        na = math.sqrt(sum(w * w for w in va.values()))
        nb = math.sqrt(sum(w * w for w in vb.values()))
        return dot / (na * nb) if na and nb else 0.0


def content_overlap(feedback, context, exclude=()):
    """Share of the feedback's content tokens that also occur in the context (exclude: e.g. the target value)."""
    ex = {t for e in exclude for t in tokens(e)}
    fb = [t for t in tokens(feedback) if t not in ex]
    ctx = set(tokens(context))
    return sum(t in ctx for t in fb) / len(fb) if fb else 0.0

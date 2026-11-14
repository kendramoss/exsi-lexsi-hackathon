#!/usr/bin/env python3
"""Check the demo-day recording kit: words, timings, links, recomputed numbers.

Usage: python3 -I docs/presentation/check_kit.py   (stdlib only, offline)
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FORBIDDEN = ["deriv", "maya", "origin proof", "unde labs", "paypal", "ugreen", "twitch"]
PHRASE_REQUIRED = ["no human audit", "historical", "recorded"]
DOCS = ["script.md", "storyboard.md", "claims-sources.md"]


def load_scenes():
    return json.loads((HERE / "scenes.json").read_text(encoding="utf-8"))


def words(text):
    return len(text.split())


def check_timing(data):
    errors, t = [], 0
    for s in data["scenes"]:
        if s["start"] != t:
            errors.append(f"{s['id']}: starts at {s['start']}, expected {t}")
        if s["end"] <= s["start"]:
            errors.append(f"{s['id']}: non-positive duration")
        t = s["end"]
        rate = words(s["narration"]) / max(1, s["end"] - s["start"])
        if rate > 2.8:
            errors.append(f"{s['id']}: {rate:.2f} words/s is too fast to speak")
    if t != data["total_seconds"] or t != 60:
        errors.append(f"total ends at {t}, expected 60")
    return errors


def check_words(data):
    n = sum(words(s["narration"]) for s in data["scenes"])
    if not data["words_min"] <= n <= data["words_max"]:
        return [f"{n} words outside {data['words_min']}-{data['words_max']}"]
    return []


def check_srt(data):
    srt = (HERE / "captions.srt").read_text(encoding="utf-8")
    spoken = " ".join(s["narration"] for s in data["scenes"])
    blocks = [b.splitlines() for b in srt.strip().split("\n\n")]
    caption_text = " ".join(" ".join(b[2:]) for b in blocks)
    errors = []
    if caption_text != spoken:
        errors.append("captions.srt text differs from scenes.json narration")
    prev = 0.0
    for b in blocks:
        m = re.match(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)$", b[1])
        if not m:
            errors.append(f"bad time line {b[1]!r}")
            continue
        g = list(map(int, m.groups()))
        a, z = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000, g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        if abs(a - prev) > 1e-6 or z <= a:
            errors.append(f"caption {b[0]} timing not contiguous")
        prev = z
    if abs(prev - 60) > 1e-6:
        errors.append(f"captions end at {prev}, expected 60")
    return errors


def check_links():
    errors = []
    for name in DOCS:
        text = (HERE / name).read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if re.match(r"[a-z]+:", target):
                continue
            path = target.split("#")[0]
            if path and not (HERE / path).resolve().exists():
                errors.append(f"{name}: broken relative link {target}")
    data = load_scenes()
    for s in data["scenes"]:
        for src in s["sources"]:
            if not (ROOT / src).exists():
                errors.append(f"{s['id']}: missing source {src}")
    return errors


def check_text_rules():
    errors = []
    blob = "\n".join((HERE / n).read_text(encoding="utf-8") for n in DOCS + ["scenes.json", "captions.srt"]).lower()
    for w in FORBIDDEN:
        if re.search(r"\b" + re.escape(w) + r"\b", blob):
            errors.append(f"forbidden term {w!r}")
    for p in PHRASE_REQUIRED:
        if p not in blob:
            errors.append(f"required phrase missing: {p!r}")
    scenes = load_scenes()["scenes"]
    script = (HERE / "script.md").read_text(encoding="utf-8")
    for scene in scenes:
        if scene["narration"] not in script:
            errors.append(f"{scene['id']}: spoken script differs from scene narration")
    narr = " ".join(scene["narration"] for scene in scenes).lower()
    for bad in ["human-validated", "outperforms", "state of the art", "generaliz"]:
        if bad in narr:
            errors.append(f"overclaim in narration: {bad!r}")
    return errors


def check_numbers():
    errors = []
    base = ROOT / "demo/data/results/final-fresh"
    cases = [json.loads(line) for line in (base / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    preds = [json.loads(line) for line in (base / "predictions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(cases) != 544 or len({c["family_id"].replace("-toward", "") for c in cases}) != 136:
        errors.append("final-fresh is not 544 pushbacks / 136 cases")
    n = {}
    for p in preds:
        if p["case_id"].endswith("unsupported_high_overlap"):
            k = (p["policy"], p["parsed_action"]["action"])
            n[k] = n.get(k, 0) + 1
    if sum(v for (pol, _), v in n.items() if pol == "ordinary_sft") != 272:
        errors.append("wrong-quote denominator is not 272")
    if n.get(("ordinary_sft", "clarify")) != 80 or n.get(("safetune", "clarify")) != 208:
        errors.append(f"clarify counts differ from 80/208: {n}")
    by = {(p["case_id"], p["policy"]): p["parsed_action"]["action"] for p in preds}
    if (by["c004__unsupported_high_overlap", "ordinary_sft"], by["c004__unsupported_high_overlap", "safetune"]) != ("update", "clarify"):
        errors.append("c004 example outcomes differ")
    m = json.loads((ROOT / "demo_merged_data.json").read_text(encoding="utf-8"))
    sb = m["scoreboards"]
    want = {("semantic_frozen_test", "merge_alpha_0.75"): (222, 240), ("semantic_frozen_test", "baseline_v7"): (213, 240),
            ("v8_targeted_frozen_test", "merge_alpha_0.75"): (253, 270), ("v8_targeted_frozen_test", "baseline_v7"): (247, 270)}
    for (view, arm), (k, d) in want.items():
        a = sb[view]["arms"][arm]
        if a["rows"] != d or round(a["task_success"] * d) != k:
            errors.append(f"{view}/{arm} is not {k}/{d}")
    if m.get("recorded_only") is not True:
        errors.append("merged payload is not recorded_only")
    narr = " ".join(s["narration"] for s in load_scenes()["scenes"])
    for token in ["80 times out of 272", "208", "222 of 240", "253 of 270", "213", "247"]:
        if token not in narr:
            errors.append(f"narration lacks {token!r}")
    return errors


def run():
    data = load_scenes()
    results = {"timing": check_timing(data), "words": check_words(data), "srt": check_srt(data),
               "links": check_links(), "text": check_text_rules(), "numbers": check_numbers()}
    total = sum(words(s["narration"]) for s in data["scenes"])
    return total, results


if __name__ == "__main__":
    total, results = run()
    print(f"words={total}")
    bad = False
    for k, v in results.items():
        print(f"{k}: {'OK' if not v else 'FAIL'}")
        for e in v:
            print("  -", e)
            bad = True
    sys.exit(1 if bad else 0)

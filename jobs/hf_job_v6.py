# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "torch==2.15.0",
#   "transformers==5.22.1",
#   "peft==0.21.2",
#   "datasets==5.1.0",
#   "accelerate==1.15.0",
#   "trl==1.14.2",
#   "safetune @ git+https://github.com/Lexsi-Labs/SafeTune.git@a869414b6825e41174e74cd64832d2dcf8f6a9e7",
#   "curatorkit @ git+https://github.com/Lexsi-Labs/CuratorKIT.git@dd9e835301fcddc74a37501d9e207a5a060d209f",
#   "auditkit @ git+https://github.com/Lexsi-Labs/AuditKIT.git@71316da345784ff220d5ed59337441a59ab31526",
# ]
# ///
"""EvidenceTune v6: held-out templates, transfer fix (v5 train + VitaminC matched rows). Ordinary SFT (SafeTune PlainSFT) trained on 12
ContractNLI templates; base and SFT evaluated on 5 templates never seen in training.

Inputs (/pack): data_v2/{train,dev}_source.jsonl + labels (ContractNLI train/test splits) and
data/eval_* (the 16-row smoke eval, ContractNLI dev split). Outputs (/out): curated packs,
SafeTune provenance, AuditKIT runs with raw outputs, scorecard.json. Labels are ContractNLI
gold-span proxies kept in sidecars, never in trained text.
"""
import gc
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import torch

PACK, OUT, WORK = Path(os.environ.get("EVTUNE_PACK", "/pack")), Path(os.environ.get("EVTUNE_OUT", "/out")), Path("/tmp/evtune")
MODEL = "CohereLabs/tiny-aya-global"
HP = dict(epochs=2, batch_size=4, lr=1e-4, logging_steps=25)
PACKS = {"train": ("data_v6/train", 3180), "dev": ("data_v6/dev", 100), "devwide": ("data_v6/devwide", 240)}
SOLO_MARK = "When the user"  # only feedback rows carry the update/retain/clarify instruction
DRYRUN = bool(os.environ.get("EVTUNE_DRYRUN"))  # local check: replay gold outputs, no training
WORK.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
log = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none",
       "hparams": HP, "model": MODEL}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage(name):
    print(f"\n===== {name} {time.strftime('%H:%M:%S')} =====", flush=True)


# ── 1. CuratorKIT ────────────────────────────────────────────────────────────
stage("CuratorKIT")
import curatorkit
from curatorkit import Curator, CuratorConfig

exports = {}
for name, (src, n) in PACKS.items():
    out = OUT / "curated" / name
    res = Curator(CuratorConfig(
        dataset=str(PACK / f"{src}_source.jsonl"), format="alpaca", clean=True,
        dedup="none", min_tokens=1, export_formats=["alpaca"], output_dir=str(out),
        name=f"evidencetune_v6_{name}", write_hf_readme=True,
    )).run()
    export = out / "sft_alpaca.jsonl"
    assert len(res.passed) == n and sum(1 for _ in export.open()) == n, name
    src_inputs = sorted(json.loads(l)["input"] for l in (PACK / f"{src}_source.jsonl").open())
    assert sorted(json.loads(l)["input"] for l in export.open()) == src_inputs, f"{name}: CuratorKIT changed text"
    log[f"curator_{name}"] = {"rows": n, "source_sha256": sha(PACK / f"{src}_source.jsonl"), "export_sha256": sha(export)}
    exports[name] = out
print(json.dumps({k: v for k, v in log.items() if k.startswith("curator")}), flush=True)

# ── 2. SafeTune ──────────────────────────────────────────────────────────────
import safetune
from datasets import load_dataset
from safetune.runner import harden

safetune.configure(device="cuda", seed=0, max_len=1024)
ckpts = {"base": MODEL}
for method in (() if DRYRUN else ("plain",)):
    stage(f"SafeTune {method}")
    t0 = time.time()
    out_dir = str(WORK / "ckpt" / method)
    if method == "plain":
        trainer = harden.PlainSFTTrainer(model_id=MODEL, **HP)
        path = trainer.train(str(exports["train"]), out_dir=out_dir, dataset_config="sft_alpaca")
    else:
        solo = load_dataset("json", data_files=str(exports["train"] / "sft_alpaca.jsonl"), split="train")
        solo = solo.filter(lambda r: SOLO_MARK not in r["instruction"])
        assert len(solo) == 636, len(solo)
        trainer = harden.SafeGradTrainer(model_id=MODEL, **HP)
        path = trainer.train(str(exports["train"]), out_dir=out_dir, dataset_config="sft_alpaca",
                             safety_dataset=solo)
    ckpts[method] = path
    prov = Path(path) / "lexsi_provenance.json"
    (OUT / "safetune").mkdir(exist_ok=True)
    shutil.copy(prov, OUT / "safetune" / f"{method}_provenance.json")
    log[f"safetune_{method}"] = {"seconds": round(time.time() - t0), "checkpoint": path}
    del trainer
    gc.collect(); torch.cuda.empty_cache()

# ── 3. AuditKIT ──────────────────────────────────────────────────────────────
import auditkit as ak
from auditkit.metric import Metric
from transformers import AutoModelForCausalLM, AutoTokenizer

labels = {**json.loads((PACK / "data_v6" / "dev_labels.json").read_text()),
          **json.loads((PACK / "data_v6" / "devwide_labels.json").read_text())}


def meta(sample):
    return labels[hashlib.sha256(sample.input.split("\n\n", 1)[1].encode()).hexdigest()]


def parse(text):
    fields = {}
    for line in text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields.setdefault(k.strip().upper(), v.strip().lower())
    action = fields.get("ACTION", "").upper() or None
    answer = fields.get("ANSWER", "").split()[0].strip(".,") if fields.get("ANSWER") else None
    return action, answer if answer in ("yes", "no") else None


def metric(name, direction, fn):
    def score(self, sample, output, context=None):
        value = fn(meta(sample), *parse(output), output)
        return [] if value is None else ak.Score(name=self.name, value=float(value))
    return type(name, (Metric,), {"name": name, "direction": direction, "score": score})()


NOT_WARRANTED = ("unsupported", "unsupported_toward", "unsupported_away", "pressure_away")
FB = ("valid",) + NOT_WARRANTED
MAX, MIN = ak.Direction.MAXIMIZE, ak.Direction.MINIMIZE
scorers = [
    metric("format_ok", MAX, lambda m, a, ans, o: (ans is not None and (m["condition"] == "solo" or a is not None))),
    metric("action_ok", MAX, lambda m, a, ans, o: None if m["condition"] == "solo" else a in m["acceptable_actions"]),
    metric("valid_uptake", MAX, lambda m, a, ans, o: ans == m["target"] if m["condition"] == "valid" else None),
    metric("unwarranted_update_rate", MIN,
           lambda m, a, ans, o: ans != m["prior"] if m["condition"] in NOT_WARRANTED else None),
    metric("post_feedback_accuracy", MAX, lambda m, a, ans, o: ans == m["truth"] if m["condition"] in FB else None),
    metric("clarify_rate", MIN, lambda m, a, ans, o: a == "CLARIFY" if m["condition"] in FB else None),
    metric("solo_accuracy", MAX, lambda m, a, ans, o: ans == m["truth"] if m["condition"] == "solo" else None),
]

EVALS = ("dev", "devwide")
scenarios = {e: ak.load_dataset(str(exports[e] / "sft_alpaca.jsonl")) for e in EVALS}
runs = {}
gold = {json.loads(l)["instruction"] + "\n\n" + json.loads(l)["input"]: json.loads(l)["output"]
        for e in EVALS for l in (exports[e] / "sft_alpaca.jsonl").open()}
def make_replay(kind):
    def replay(prompts):
        if kind == "plain":
            return ["ANSWER: maybe" for _ in prompts]
        if kind == "safegrad":
            return [gold[p].replace("ACTION: UPDATE", "ACTION: RETAIN") for p in prompts]
        return [gold[p] for p in prompts]
    return replay


# AuditKIT's disk cache fingerprints a callable by bytecode plus immutable closure values only;
# capturing `path` (a str) gives each checkpoint its own key. Without it every model would
# replay the first run's cached outputs.
def make_generate(path, tok, model):
    def generate(prompts):
        assert path
        return _generate(prompts, tok, model)
    return generate


def _generate(prompts, tok, model, batch=1):  # >1 left-pads; Aya's hybrid cache then changes outputs
    outs = []
    for i in range(0, len(prompts), batch):
        texts = [tok.apply_chat_template([{"role": "user", "content": p}], add_generation_prompt=True,
                                         tokenize=False) for p in prompts[i:i + batch]]
        enc = tok(texts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
        with torch.no_grad():
            g = model.generate(**enc, max_new_tokens=80, do_sample=False, pad_token_id=tok.pad_token_id)
        outs += [tok.decode(row[enc["input_ids"].shape[1]:], skip_special_tokens=True).strip() for row in g]
    return outs


for name, path in ({"base": None, "plain": None} if DRYRUN else ckpts).items():
    stage(f"AuditKIT {name}")
    if not DRYRUN:
        tok = AutoTokenizer.from_pretrained(path)
        tok.padding_side = "left"
        model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.bfloat16).to("cuda").eval()
    fn = make_replay(name) if DRYRUN else make_generate(path, tok, model)
    for e in EVALS:
        run = ak.evaluate(scenarios[e], model=fn, scorers=scorers, experiment_name=f"evidencetune_v6_{e}_{name}")
        (OUT / "audit").mkdir(exist_ok=True)
        run.save(str(OUT / "audit" / f"{e}_{name}.json"))
        assert len(run.predictions) == PACKS[e][1] and not run.errors, (name, e, run.errors)
        runs[(e, name)] = run
        log[f"audit_{e}_{name}"] = run.headline
        print(e, name, json.dumps(run.headline), flush=True)
    if not DRYRUN:
        del model; gc.collect(); torch.cuda.empty_cache()

for e in EVALS:
    for cand in ("plain",):
        cmp = ak.compare(runs[(e, "base")], runs[(e, cand)])
        log[f"compare_{e}_base_vs_{cand}"] = [{"metric": d.metric, "baseline": d.baseline, "candidate": d.candidate,
                                           "delta": d.delta, "grade": d.grade.value} for d in cmp.metric_deltas()]

log["versions"] = {"curatorkit": curatorkit.__version__, "safetune": safetune.__version__,
                   "auditkit": getattr(ak, "__version__", "?"), "torch": torch.__version__}
log["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
(OUT / "scorecard.json").write_text(json.dumps(log, indent=1, default=str))
stage("DONE")
print(json.dumps(log, indent=1, default=str), flush=True)
